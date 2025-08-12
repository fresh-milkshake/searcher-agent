from aiogram import Router
from datetime import datetime

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from textwrap import dedent
from shared.db import (
    ensure_connection,
    get_active_topic_by_user,
    get_user_settings,
    count_analyses_for_user,
    count_relevant_analyses_for_user,
    get_agent_status,
    list_recent_analyses_for_user,
)
from shared.logger import get_logger

router = Router(name="general")

logger = get_logger(__name__)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = "user"
    if message.from_user and message.from_user.full_name:
        user_name = message.from_user.full_name

    help_text = dedent(f"""
    🔬 Hello, {user_name}! I'm your assistant that explores research sources and finds items useful for your goals.

    📌 <b>How it works</b>
    • You create a task. I search arXiv, Google Scholar, PubMed, and GitHub, evaluate relevance, and send you clear summaries.

    📋 <b>Main commands</b>
    • /task "Title" description — create a new autonomous search task
    • /status_task — show your tasks
    • /pause_task &lt;id&gt;, /resume_task &lt;id&gt; — pause/resume a task
    • /history — recent findings
    • /status — system status

    ⚙️ <b>Settings</b>
    • /settings — view current settings
    • /set_relevance relevance &lt;0-100&gt; — set relevance threshold
    • /set_notification [instant|daily|weekly] &lt;0-100&gt;
    • /reset_settings — defaults
    • /set_group — route notifications to this group (run in group chat)
    • /unset_group — back to personal chat

    🧭 <b>Tip</b>
    Start with something like:
    /task "AI for medical imaging" Find practical studies, datasets, and evaluation results
    """)

    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """Show current monitoring status"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        # Ensure database connection
        ensure_connection()

        # Get active topic
        topic = await get_active_topic_by_user(user_id)
        if not topic:
            await message.answer(
                "ℹ️ No legacy topics configured. Use /task to create a new autonomous task.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Get settings
        settings = await get_user_settings(user_id)
        monitoring_status = (
            "🟢 Active"
            if (settings and getattr(settings, "monitoring_enabled", True))
            else "🔴 Paused"
        )

        # Analysis statistics
        analyses_count = await count_analyses_for_user(user_id)
        relevant_count = await count_relevant_analyses_for_user(user_id, 50.0)

        # Get agent status
        agent_info = ""
        agent_status = await get_agent_status("main_agent")
        if agent_status:
            time_diff = datetime.now() - agent_status.last_activity
            if time_diff.total_seconds() < 600:
                agent_active = "🟢 Active"
                activity_info = f"🔄 <b>Current activity:</b> {agent_status.activity}"
                if agent_status.current_user_id:
                    if agent_status.current_user_id == user_id:
                        activity_info += "\n📍 <b>Processing your topics</b>"
                    else:
                        activity_info += f"\n📍 <b>Processing topics for user {agent_status.current_user_id}</b>"
                session_info = "📊 <b>Session statistics:</b>\n"
                session_info += f"• Papers processed: {agent_status.papers_processed}\n"
                session_info += (
                    f"• Relevant papers found: {agent_status.papers_found}\n"
                )
                session_info += f"• Started: {agent_status.session_start.strftime('%d.%m.%Y %H:%M')}"
            else:
                agent_active = "🔴 Inactive"
                activity_info = f"⏰ <b>Last activity:</b> {agent_status.last_activity.strftime('%d.%m.%Y %H:%M')}"
                session_info = ""
            agent_info = dedent(f"""

            🤖 <b>AI Agent Status:</b> {agent_active}
            {activity_info}
            {session_info}
            """)
        else:
            agent_info = "\n🤖 <b>AI Agent Status:</b> ❓ Unknown"

        status_text = dedent(f"""
        📊 <b>Monitoring Status</b>

        🎯 <b>Legacy Target Topic:</b> {topic.target_topic}
        🔍 <b>Legacy Search Area:</b> {topic.search_area}
        📅 <b>Created:</b> {topic.created_at.strftime("%d.%m.%Y %H:%M")}

        🤖 <b>Monitoring:</b> {monitoring_status}
        📈 <b>Papers Analyzed:</b> {analyses_count}
        ⭐ <b>Relevant Found:</b> {relevant_count}
        {agent_info}

        🔧 Use /settings to configure parameters
        """)

        await message.answer(status_text, parse_mode=ParseMode.HTML)

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        await message.answer("❌ An error occurred while getting status.")


@router.message(Command("history"))
async def command_history_handler(message: Message) -> None:
    """Show recent found topic intersections"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        # Ensure database connection
        ensure_connection()

        # Get last 5 relevant analyses
        items = await list_recent_analyses_for_user(user_id, limit=5)
        if not items:
            await message.answer(
                "📚 <b>History is empty</b>\n\n"
                "Relevant articles not found yet.\n"
                "Create a task with /task to get started.",
                parse_mode=ParseMode.HTML,
            )
            return

        history_text = "📚 <b>Recent found topic intersections:</b>\n\n"

        for analysis, paper in items:
            title_preview = (
                paper.title[:80] + "..." if len(paper.title) > 80 else paper.title
            )
            authors_preview = (
                paper.authors.split(",")[0]
                if paper.authors
                else "Authors not specified"
            )

            history_text += dedent(f"""
            📄 <b>{title_preview}</b>
            👥 {authors_preview}
            📊 Relevance: {analysis.relevance:.1f}%
            📅 {analysis.created_at.strftime("%d.%m.%Y")}
            🔗 {paper.abs_url}

            """)
        await message.answer(history_text, parse_mode=ParseMode.HTML)
        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /history command: {e}")
        await message.answer("❌ An error occurred while getting history.")


@router.message()
async def unknown_message_handler(message: Message) -> None:
    """Handler for unknown messages"""
    try:
        if not message.from_user or not message.from_user.id:
            logger.warning("Received message without user information")
            await message.answer("Error: could not determine user.")
            return

        await message.answer(
            "❓ <b>Unknown command</b>\n\n"
            "Use /start to see commands.\n\n"
            "💡 You can create a task like:\n"
            '<code>/task "AI for medical imaging" Find practical studies and datasets</code>',
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"Error processing unknown message: {e}")
        await message.answer("❌ An error occurred while processing message.")
