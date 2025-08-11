from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import re

from bot.utils import escape_html
from shared.db import (
    ensure_connection,
    deactivate_user_topics,
    create_research_topic,
    get_or_create_user_settings,
    create_task,
    swap_user_active_topics,
    update_user_settings,
)
from shared.logger import get_logger

router = Router(name="management")

logger = get_logger(__name__)


@router.message(Command("topic"))
async def command_topic_handler(message: Message) -> None:
    """Handler for /topic command to set analysis topics"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Parse command arguments (expect two topics in quotes)
        pattern = r'/topic\s+"([^"]+)"\s+"([^"]+)"'
        match = re.search(pattern, command_text)

        if not match:
            message_text = (
                "❌ Invalid command format.\n\n"
                "✅ Correct format:\n"
                '/topic "target topic" "search area"\n\n'
                "📝 Examples:\n"
                '• `/topic "machine learning" "medicine"`\n'
                '• `/topic "quantum computing" "cryptography"`\n'
                '• `/topic "blockchain" "logistics"`'
            )
            await message.answer(message_text, parse_mode=ParseMode.HTML)
            return

        target_topic = match.group(1).strip()
        search_area = match.group(2).strip()

        if len(target_topic) < 2 or len(search_area) < 2:
            await message.answer("❌ Topics must contain at least 3 characters.")
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        # Deactivate previous user topics
        await deactivate_user_topics(user_id)

        # Create new topic
        topic = await create_research_topic(user_id, target_topic, search_area)

        # Create user settings if they don't exist
        await get_or_create_user_settings(user_id)

        # Create task for AI agent to start monitoring
        await create_task(
            task_type="start_monitoring",
            data={
                "user_id": user_id,
                "topic_id": topic.id,
                "target_topic": target_topic,
                "search_area": search_area,
            },
            status="pending",
        )

        message_text = (
            f"✅ <b>Analysis topics set</b>\n\n"
            f"🎯 <b>Target topic:</b> {escape_html(target_topic)}\n"
            f"🔍 <b>Search area:</b> {escape_html(search_area)}\n\n"
            f"🤖 AI agent has started monitoring arXiv for topic intersections.\n"
            f"📬 I will send notifications about found relevant articles.\n\n"
            f"📊 Use `/status` to check status."
        )

        await message.answer(message_text, parse_mode=ParseMode.HTML)

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /topic command: {e}")
        await message.answer("❌ An error occurred while setting topics.")


@router.message(Command("switch_themes"))
async def command_switch_themes_handler(message: Message) -> None:
    """Swap target topic and search area"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            topic = await swap_user_active_topics(user_id)
            if topic is None:
                await message.answer(
                    "❌ <b>Topics not set</b>\n\nFirst use /topic to set topics.",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Create task to restart monitoring
            await create_task(
                task_type="restart_monitoring",
                data={
                    "user_id": user_id,
                    "topic_id": topic.id,
                    "target_topic": topic.target_topic,
                    "search_area": topic.search_area,
                },
                status="pending",
            )

            message_text = (
                f"🔄 <b>Topics swapped</b>\n\n"
                f"🎯 <b>New target topic:</b> {escape_html(topic.target_topic)}\n"
                f"🔍 <b>New search area:</b> {escape_html(topic.search_area)}\n\n"
                f"🤖 Monitoring restarted with new parameters."
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML)

        except Exception:
            await message.answer(
                "❌ <b>Topics not set</b>\n\nFirst use /topic to set topics.",
                parse_mode=ParseMode.HTML,
            )

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /switch_themes command: {e}")
        await message.answer("❌ An error occurred while switching topics.")


@router.message(Command("pause"))
async def command_pause_handler(message: Message) -> None:
    """Pause monitoring"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            await update_user_settings(user_id, monitoring_enabled=False)

            await message.answer(
                "⏸️ <b>Monitoring paused</b>\n\nUse /resume to resume.",
                parse_mode=ParseMode.HTML,
            )

        except Exception:
            await message.answer("❌ User settings not found.")

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /pause command: {e}")
        await message.answer("❌ An error occurred while pausing.")


@router.message(Command("resume"))
async def command_resume_handler(message: Message) -> None:
    """Resume monitoring"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            await update_user_settings(user_id, monitoring_enabled=True)

            await message.answer(
                "▶️ <b>Monitoring resumed</b>\n\n"
                "AI agent has continued searching for relevant articles.",
                parse_mode=ParseMode.HTML,
            )

        except Exception:
            await message.answer("❌ User settings not found.")

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /resume command: {e}")
        await message.answer("❌ An error occurred while resuming.")
