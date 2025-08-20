import asyncio
import json
from textwrap import dedent
from typing import Any

from aiogram import Bot
from aiogram.enums import ParseMode

from agents import Agent, Runner
from shared.llm import AGENT_MODEL
from bot.utils import escape_html
from shared.db import (
    ensure_connection,
    get_analysis_with_entities,
    get_user_settings,
    list_new_analyses_since,
    mark_task_sent,
    mark_analysis_notified,
)
from shared.logging import get_logger


logger = get_logger(__name__)


async def get_target_chat_id(user_id: int) -> int:
    """Return group chat ID if configured, otherwise personal user ID.

    :param user_id: Telegram user identifier.
    :returns: The target chat ID for notifications.
    """
    try:
        ensure_connection()
        settings = await get_user_settings(user_id)
        current_group = getattr(settings, "group_chat_id", None) if settings else None
        logger.info(
            f"User {user_id} settings: group_chat_id={current_group if current_group is not None else 'None'}"
        )
        if settings and current_group:
            chat_id = int(current_group)  # type: ignore[arg-type]
            logger.info(f"Routing notifications for user {user_id} to group {chat_id}")
            return chat_id
        logger.info(f"Routing notifications for user {user_id} to personal chat")
        return user_id
    except Exception:
        logger.error(
            f"Failed to get target chat for user {user_id}, fallback to personal"
        )
        return user_id


_simplifier_agent = Agent(
    name="Notification Simplifier",
    model=AGENT_MODEL,
    instructions=dedent(
        """
        You rewrite technical research notifications into clear, friendly messages for a general audience.

        Goals:
        - Explain the finding in simple words (what was found and why it matters)
        - Avoid jargon and numbers unless essential
        - Keep it short and helpful

        Output format:
        - 1 short title (no emojis in title)
        - 1–3 short lines with the essence and usefulness
        - Final line: a call to action with the link label 'Open on arXiv: <link>'

        Rules:
        - Use a warm tone, simple vocabulary, and short sentences
        - No markdown or HTML tags, only plain text
        - Max length 600 characters total
        """
    ),
)


async def simplify_for_layperson(text: str) -> str:
    """Return a simplified plain-text version of a notification.

    :param text: Input facts block.
    :returns: Simplified text without markup, friendly to non-technical readers.
    """
    try:
        result: Any = await Runner.run(_simplifier_agent, text)
        simplified = (
            str(getattr(result, "final_output", "")).strip() or str(result).strip()
        )
        # Basic post-clean: remove any stray tags just in case
        return simplified.replace("<", "").replace(">", "")
    except Exception as error:
        logger.error(f"Notification simplification failed: {error}")
        return text


async def send_message_to_target_chat(
    bot: Bot, chat_id: int, text: str, user_id: int | None = None
) -> None:
    """Send a message to a chat. Fallback to personal chat if group send fails.

    :param bot: Aiogram bot instance.
    :param chat_id: Target chat id (group or user).
    :param text: Message text (Telegram HTML allowed).
    :param user_id: Optional user id for fallback delivery.
    :returns: ``None``.
    """

    def _split_message(msg: str, max_len: int = 4000) -> list[str]:
        if len(msg) <= max_len:
            return [msg]
        parts: list[str] = []
        remaining = msg
        while len(remaining) > max_len:
            # Try to split on paragraph boundary
            cut = remaining.rfind("\n\n", 0, max_len)
            if cut == -1:
                cut = remaining.rfind("\n", 0, max_len)
            if cut == -1:
                cut = max_len
            parts.append(remaining[:cut].strip())
            remaining = remaining[cut:].lstrip()
        if remaining:
            parts.append(remaining)
        return parts

    try:
        for part in _split_message(text):
            await bot.send_message(
                chat_id=chat_id, text=part, parse_mode=ParseMode.HTML
            )
        logger.info(f"Message sent to chat {chat_id}")
    except Exception as error:
        logger.error(f"Error sending message to chat {chat_id}: {error}")
        if user_id is not None and chat_id != user_id:
            try:
                fallback_text = (
                    f"⚠️ <b>Failed to send notification to group chat</b>\n\n{text}"
                )
                for part in _split_message(fallback_text):
                    await bot.send_message(
                        chat_id=user_id, text=part, parse_mode=ParseMode.HTML
                    )
                logger.info(f"Fallback message sent to user {user_id}")
            except Exception as fallback_error:
                logger.error(
                    f"Error sending fallback message to user {user_id}: {fallback_error}"
                )


async def send_analysis_report(bot: Bot, user_id: int, analysis_id: int) -> None:
    """Send a structured Telegram report for a particular analysis to the target chat.

    :param bot: Aiogram bot instance.
    :param user_id: Telegram user identifier.
    :param analysis_id: Identifier of the analysis to render and deliver.
    :returns: ``None``.
    """
    try:
        ensure_connection()
        result = await get_analysis_with_entities(analysis_id)
        if not result:
            logger.error(f"Analysis {analysis_id} not found")
            return
        analysis, paper, topic = result

        # We do not surface the date in simplified message; compute defensively for potential future use
        try:
            _ = (
                paper.published.strftime("%d.%m.%Y")
                if hasattr(paper.published, "strftime")
                else str(paper.published)
            )
        except Exception as date_error:
            logger.error(f"Error getting published date: {date_error}")

        # Authors are not included in the simplified message; still parse to keep parity and logs healthy
        try:
            _authors_list = json.loads(paper.authors)
        except Exception as authors_error:
            logger.error(f"Error getting authors: {authors_error}")
            _authors_list = []

        # Prepare human-facing facts and simplify with AI
        facts = dedent(
            f"""
            Title: {paper.title}
            Target topic: {topic.target_topic}
            Search area: {topic.search_area}
            Summary: {analysis.summary or "No summary"}
            Why relevant (score): {analysis.relevance:.1f}%
            Link: {paper.abs_url}
            """
        )

        simple_text = await simplify_for_layperson(facts)

        target_chat_id = await get_target_chat_id(user_id)
        await send_message_to_target_chat(
            bot,
            target_chat_id,
            escape_html(simple_text),
            user_id,
        )
        await mark_analysis_notified(analysis_id)
        logger.info(f"Report sent to chat {target_chat_id} for analysis {analysis_id}")
    except Exception as error:
        logger.error(f"Error sending analysis report {analysis_id}: {error}")


async def process_completed_task(bot: Bot, task: Any) -> None:
    """Process a completed task and send appropriate notifications.

    :param bot: Aiogram bot instance.
    :param task: Database task model (completed state) with payload.
    :returns: ``None``.
    """
    try:
        try:
            task_data = json.loads(str(task.data)) if task.data else {}
        except json.JSONDecodeError as json_error:
            logger.error(f"Failed to parse task data as JSON: {json_error}")
            task_data = {}
        task_type = task_data.get("task_type", getattr(task, "task_type", "unknown"))
        result = task.result
        user_id = task_data.get("user_id")

        if not user_id:
            logger.warning(f"Task {task.id} does not contain user_id")
            return

        ensure_connection()
        target_chat_id = await get_target_chat_id(user_id)
        logger.info(
            f"Sending task {task.id} (type={task_type}) for user {user_id} to chat {target_chat_id}"
        )

        if task_type == "analysis_complete":
            analysis_id = task_data.get("analysis_id")
            if analysis_id:
                await send_analysis_report(bot, user_id, analysis_id)
        elif task_type == "monitoring_started":
            await send_message_to_target_chat(
                bot,
                target_chat_id,
                dedent(
                    """
                    🤖 <b>Monitoring started!</b>

                    AI agent has begun searching for relevant articles.
                    """
                ),
                user_id,
            )
        elif task_type in ["start_monitoring", "restart_monitoring"]:
            result_text = (
                escape_html(str(result)) if result else "✅ Monitoring configured"
            )
            await send_message_to_target_chat(bot, target_chat_id, result_text, user_id)
        elif task_type == "cycle_limit_notification":
            # Send cycle limit notification (result already contains HTML formatting)
            await send_message_to_target_chat(bot, target_chat_id, str(result), user_id)
        elif result:
            await send_message_to_target_chat(
                bot, target_chat_id, escape_html(str(result)), user_id
            )

        await mark_task_sent(task.id)
        logger.info(f"Processed completed task {task.id} of type {task_type}")
    except Exception as error:
        logger.error(f"Error processing completed task {task.id}: {error}")


async def check_new_analyses(bot: Bot) -> None:
    """Background task to check for new analyses and send instant notifications.

    :param bot: Aiogram bot instance.
    :returns: ``None``.
    """
    logger.info("Starting background analysis checker")
    last_checked_id = 0
    while True:
        try:
            ensure_connection()
            analyses = await list_new_analyses_since(last_checked_id, 0.0)
            for analysis in analyses:
                try:
                    result = await get_analysis_with_entities(analysis.id)
                    if not result:
                        continue
                    analysis_obj, _paper, topic = result
                    user_id = topic.user_id
                    settings = await get_user_settings(user_id)
                    threshold = getattr(
                        settings, "instant_notification_threshold", 80.0
                    )
                    if analysis_obj.relevance >= float(threshold):  # type: ignore[arg-type]
                        if getattr(analysis_obj, "status", "") in {
                            "queued",
                            "notified",
                        }:
                            last_checked_id = max(last_checked_id, analysis_obj.id)
                            continue
                        logger.info(
                            f"Found new high-relevance analysis {analysis_obj.id} for user {user_id}"
                        )
                        # Mark as queued to prevent duplicates under race conditions
                        try:
                            from shared.db import (
                                mark_analysis_queued,
                            )  # local import to avoid cycles

                            await mark_analysis_queued(analysis_obj.id)
                        except Exception as queue_error:
                            logger.error(
                                f"Failed to mark analysis queued: {queue_error}"
                            )
                        await send_analysis_report(bot, user_id, analysis_obj.id)
                    last_checked_id = max(last_checked_id, analysis_obj.id)
                except Exception as inner_error:
                    logger.error(
                        f"Error processing analysis {getattr(analysis, 'id', 'unknown')}: {inner_error}"
                    )
            await asyncio.sleep(10)
        except Exception as loop_error:
            logger.error(f"Error in background analysis checker: {loop_error}")
            await asyncio.sleep(30)
