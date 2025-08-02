import asyncio
import os
import json
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from bot.utils import format_html
from shared.database import db, Task, ResearchTopic, PaperAnalysis, ArxivPaper, init_db
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from bot.handlers import general_router, management_router

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

logger = get_logger(__name__)

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()
dp.include_router(management_router)
dp.include_router(general_router)


async def handle_task_completion(event: Event):
    """Task completion handler - sends reports and notifications"""
    try:
        task_id = event.data.get("task_id")
        result = event.data.get("result")
        task_type = event.data.get("task_type", "unknown")

        if not task_id:
            logger.warning(f"Task completion event without ID: {event.data}")
            return

        # Check if database is already connected
        if hasattr(db, "is_closed") and db.is_closed():
            db.connect()
        elif hasattr(db.database, "is_closed") and db.database.is_closed():
            db.connect()

        try:
            task = Task.get(Task.id == task_id)

            # Get task data
            task_data = json.loads(task.data) if task.data else {}
            user_id = task_data.get("user_id")

            if not user_id:
                logger.warning(f"Task {task_id} does not contain user_id")
                return

            # Handle different task types
            if task_type == "analysis_complete":
                # Send report about found relevant article
                analysis_id = task_data.get("analysis_id")
                if analysis_id:
                    await send_analysis_report(user_id, analysis_id)

            elif task_type == "monitoring_started":
                # Monitoring start confirmation
                await bot.send_message(
                    chat_id=user_id,
                    text=format_html(
                        "🤖 **Monitoring started!**\n\nAI agent has begun searching for relevant articles."
                    ),
                    parse_mode="HTML",
                )

            elif task_type in ["start_monitoring", "restart_monitoring"]:
                # Monitoring setup confirmation
                result_text = (
                    format_html(result)
                    if result
                    else format_html("✅ Monitoring configured")
                )
                await bot.send_message(
                    chat_id=user_id, text=result_text, parse_mode="HTML"
                )

            elif result:
                # General responses for other task types
                await bot.send_message(
                    chat_id=user_id,
                    text=format_html(result),
                    parse_mode="HTML",
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


async def send_analysis_report(user_id: int, analysis_id: int):
    """Sends structured report about found article"""
    try:
        # Check if database is already connected
        if hasattr(db, "is_closed") and db.is_closed():
            db.connect()

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
        report = f"""
🔬 **Found topic intersection: "{topic.target_topic}" in area "{topic.search_area}"**

📄 **Title:** {paper.title}

👥 **Authors:** {paper.authors if paper.authors else 'Not specified'}

📅 **Publication date:** {paper.published.strftime('%d.%m.%Y')}

📚 **arXiv category:** {paper.primary_category or 'Not specified'}

🔗 **Link:** {paper.abs_url}

📊 **Topic intersection analysis:**
• Search area relevance: {analysis.search_area_relevance:.1f}%
• Target topic content: {analysis.target_topic_relevance:.1f}%
• **Overall score: {analysis.overall_relevance:.1f}%**

📋 **Brief summary:**
{analysis.summary or 'Analysis in progress'}
        """

        # Add key fragments if available
        if analysis.key_fragments:
            try:
                fragments = json.loads(analysis.key_fragments)
                if fragments:
                    report += "\n\n🔍 **Key fragments:**\n"
                    for fragment in fragments[:3]:  # Maximum 3 fragments
                        report += f"• {fragment}\n"
            except json.JSONDecodeError:
                pass

        # Add contextual reasoning
        if analysis.contextual_reasoning:
            report += (
                f"\n\n💡 **Contextual reasoning:**\n{analysis.contextual_reasoning}"
            )

        await bot.send_message(
            chat_id=user_id,
            text=format_html(report),
            parse_mode=ParseMode.HTML,
        )

        # Mark analysis as sent
        analysis.status = "sent"
        analysis.save()

        logger.info(f"Report sent to user {user_id} for analysis {analysis_id}")
        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error sending analysis report {analysis_id}: {e}")
        # Don't close connection in exception handler either


async def main() -> None:
    logger.info("Starting Telegram bot...")

    init_db()
    logger.info("Database initialized for bot")

    # Get event bus and subscribe to task completions
    logger.info("Getting event bus...")
    event_bus = get_event_bus()
    logger.info("Event bus obtained successfully")

    logger.info("Subscribing to task completions...")
    task_events.subscribe_to_completions(handle_task_completion)
    logger.info("Successfully subscribed to task completions")

    # Start event processing in background
    logger.info("Starting event processing in background...")
    asyncio.create_task(event_bus.start_processing(poll_interval=0.5))
    logger.info("Background event processing started")

    logger.info("Telegram bot ready to work")

    # Start the bot
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
