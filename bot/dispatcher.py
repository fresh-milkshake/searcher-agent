import asyncio
import os
import json
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from bot.utils import escape_html
from shared.database import (
    Task,
    ResearchTopic,
    PaperAnalysis,
    ArxivPaper,
    UserSettings,
    init_db,
    ensure_connection,
)
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import Event
from bot.handlers import general_router, management_router, settings_router

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

logger = get_logger(__name__)

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()
dp.include_router(management_router)
dp.include_router(settings_router)
dp.include_router(general_router)


async def handle_task_completion(event: Event):
    """Task completion handler - sends reports and notifications"""
    try:
        task_id = event.data.get("task_id") if event.data else None
        result = event.data.get("result") if event.data else None
        task_type = event.data.get("task_type", "unknown") if event.data else "unknown"

        if not task_id:
            logger.warning(f"Task completion event without ID: {event.data}")
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            return

        try:
            task = Task.get(Task.id == task_id)

            # Get task data
            task_data = json.loads(task.data) if task.data else {}
            user_id = task_data.get("user_id")

            if not user_id:
                logger.warning(f"Task {task_id} does not contain user_id")
                return

            # Get target chat ID (group chat or personal chat)
            target_chat_id = await get_target_chat_id(user_id)

            # Handle different task types
            if task_type == "analysis_complete":
                # Send report about found relevant article
                analysis_id = task_data.get("analysis_id")
                if analysis_id:
                    await send_analysis_report(user_id, analysis_id)

            elif task_type == "monitoring_started":
                # Monitoring start confirmation
                await send_message_to_target_chat(
                    target_chat_id,
                    "🤖 <b>Monitoring started!</b>\n\nAI agent has begun searching for relevant articles.",
                    user_id
                )

            elif task_type in ["start_monitoring", "restart_monitoring"]:
                # Monitoring setup confirmation
                result_text = (
                    escape_html(result) if result else "✅ Monitoring configured"
                )
                await send_message_to_target_chat(target_chat_id, result_text, user_id)

            elif result:
                # General responses for other task types
                await send_message_to_target_chat(
                    target_chat_id,
                    escape_html(result),
                    user_id
                )

            # Mark task as sent
            task.status = "sent"
            task.save()

            logger.info(f"Processed task completion {task_id} of type {task_type}")

        except DoesNotExist:
            logger.error(f"Task {task_id} not found in database")

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error processing task completion: {e}")
        # Don't close connection in exception handler either


async def get_target_chat_id(user_id: int) -> int:
    """Get target chat ID - group chat if configured, otherwise personal chat"""
    try:
        ensure_connection()
        settings = UserSettings.get(UserSettings.user_id == user_id)
        return settings.group_chat_id if settings.group_chat_id else user_id
    except DoesNotExist:
        return user_id


async def send_message_to_target_chat(chat_id: int, text: str, user_id: int | None = None):
    """Send message to target chat with error handling"""
    try:
        await bot.send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=ParseMode.HTML,
        )
        logger.info(f"Message sent to chat {chat_id}")
    except Exception as e:
        logger.error(f"Error sending message to chat {chat_id}: {e}")
        
        # If failed to send to group chat, try to send to personal chat
        if user_id is not None and chat_id != user_id:
            try:
                fallback_text = f"⚠️ <b>Failed to send notification to group chat</b>\n\n{text}"
                await bot.send_message(
                    chat_id=user_id,
                    text=fallback_text,
                    parse_mode=ParseMode.HTML,
                )
                logger.info(f"Fallback message sent to user {user_id}")
            except Exception as fallback_error:
                logger.error(f"Error sending fallback message to user {user_id}: {fallback_error}")


async def send_analysis_report(user_id: int, analysis_id: int):
    """Sends structured report about found article"""
    try:
        # Ensure database connection
        ensure_connection()

        # Get analysis with article and topic data
        analysis = (
            PaperAnalysis.select(PaperAnalysis, ArxivPaper, ResearchTopic)
            .join(ArxivPaper)
            .switch(PaperAnalysis)
            .join(ResearchTopic)
            .where(PaperAnalysis.id == analysis_id)
            .get()
        )

        paper = analysis.paper
        topic = analysis.topic

        # Form report according to idea.md
        # Handle published date - it might be a string or datetime
        try:
            if hasattr(paper.published, "strftime"):
                published_date = paper.published.strftime("%d.%m.%Y")
            else:
                published_date = str(paper.published)
        except Exception as e:
            logger.error(f"Error getting published date: {e}")
            published_date = "Not specified"

        try:
            authors = json.loads(paper.authors)
            if authors:
                authors = ", ".join(f"<code>{author}</code>" for author in authors)
            else:
                authors = "Not specified"
        except Exception as e:
            logger.error(f"Error getting authors: {e}")
            authors = "Not specified"

        report = f"""
🔬 <b>Found topic intersection: <u>"{topic.target_topic}"</u> in area <u>"{topic.search_area}"</u></b>

📄 <b>Title:</b> <code>{paper.title}</code>
👥 <b>Authors:</b> {authors}
📅 <b>Publication date:</b> <code>{published_date}</code>
📚 <b>arXiv category:</b> <code>{paper.primary_category or 'Not specified'}</code>

🔗 <b>Link:</b> {paper.abs_url}

📊 <b>Topic intersection analysis:</b>
• Target topic relevance: {analysis.target_topic_relevance:.1f}%

📋 <b>Brief summary:</b>
<blockquote expandable>{analysis.summary or 'Analysis in progress'}</blockquote>
        """

        # Add key fragments if available
        if analysis.key_fragments:
            try:
                fragments = json.loads(analysis.key_fragments)
                if fragments:
                    report += "\n\n🔍 <b>Key fragments:</b>\n"
                    for fragment in fragments[:3]:  # Maximum 3 fragments
                        report += f"• {fragment}\n"
            except json.JSONDecodeError:
                pass

        # Add contextual reasoning
        if analysis.contextual_reasoning:
            report += (
                f"\n\n💡 <b>Contextual reasoning:</b>\n{analysis.contextual_reasoning}"
            )

        # Clean HTML tags that are not supported by Telegram
        import re

        cleaned_report = re.sub(r"<think>.*?</think>", "", report, flags=re.DOTALL)

        # Get target chat ID (group chat or personal chat)
        target_chat_id = await get_target_chat_id(user_id)
        
        # Send report to target chat
        await send_message_to_target_chat(target_chat_id, cleaned_report, user_id)

        # Mark analysis as sent
        analysis.status = "sent"
        analysis.save()

        logger.info(f"Report sent to chat {target_chat_id} for analysis {analysis_id}")
        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error sending analysis report {analysis_id}: {e}")
        # Don't close connection in exception handler either


async def check_new_analyses():
    """Background task to check for new analyses and send notifications"""
    logger.info("Starting background analysis checker")

    # Track last checked analysis ID
    last_checked_id = 0

    while True:
        try:
            # Ensure database connection
            ensure_connection()

            # Get new analyses that haven't been sent yet
            new_analyses = (
                PaperAnalysis.select(PaperAnalysis, ArxivPaper, ResearchTopic)
                .join(ArxivPaper)
                .switch(PaperAnalysis)
                .join(ResearchTopic)
                .where(
                    PaperAnalysis.id > last_checked_id,  # type: ignore
                    PaperAnalysis.status == "analyzed",  # Check for analyzed articles
                    PaperAnalysis.overall_relevance >= 60.0,  # type: ignore
                )
                .order_by(PaperAnalysis.created_at.asc())
            )

            for analysis in new_analyses:
                try:
                    # Get user settings to check notification threshold
                    user_id = analysis.topic.user_id
                    settings = UserSettings.get(UserSettings.user_id == user_id)

                    # Check if analysis meets instant notification threshold
                    if (
                        analysis.overall_relevance
                        >= settings.instant_notification_threshold
                    ):
                        logger.info(
                            f"Found new high-relevance analysis {analysis.id} for user {user_id}"
                        )
                        await send_analysis_report(user_id, analysis.id)

                    last_checked_id = max(last_checked_id, analysis.id)

                except Exception as e:
                    logger.error(f"Error processing analysis {analysis.id}: {e}")

            # Wait before next check
            await asyncio.sleep(10)  # Check every 10 seconds

        except Exception as e:
            logger.error(f"Error in background analysis checker: {e}")
            await asyncio.sleep(30)  # Wait longer on error


async def main() -> None:
    logger.info("Starting Telegram bot...")

    init_db()
    logger.info("Database initialized for bot")

    # Start background task to check for new analyses
    logger.info("Starting background analysis checker...")
    asyncio.create_task(check_new_analyses())
    logger.info("Background analysis checker started")

    logger.info("Telegram bot ready to work")

    # Start the bot
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
