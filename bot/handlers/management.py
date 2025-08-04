from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import re
import json

from bot.utils import escape_html
from shared.database import db, ResearchTopic, UserSettings, Task, ensure_connection
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import task_events

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
        ResearchTopic.update(is_active=False).where(
            ResearchTopic.user_id == user_id, ResearchTopic.is_active
        ).execute()

        # Create new topic
        topic = ResearchTopic.create(
            user_id=user_id,
            target_topic=target_topic,
            search_area=search_area,
            is_active=True,
        )

        # Create user settings if they don't exist
        try:
            UserSettings.get(UserSettings.user_id == user_id)
        except DoesNotExist:
            UserSettings.create(user_id=user_id)

        # Create task for AI agent to start monitoring
        task = Task.create(
            task_type="start_monitoring",
            data=json.dumps(
                {
                    "user_id": user_id,
                    "topic_id": topic.id,
                    "target_topic": target_topic,
                    "search_area": search_area,
                }
            ),
            status="pending",
        )

        # Notify agent
        task_events.task_created(
            task_id=task.id,
            task_type="start_monitoring",
            data={"user_id": user_id, "topic_id": topic.id},
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
            topic = ResearchTopic.get(
                ResearchTopic.user_id == user_id, ResearchTopic.is_active
            )

            # Swap topics
            old_target = topic.target_topic
            old_area = topic.search_area

            topic.target_topic = old_area
            topic.search_area = old_target
            topic.save()

            # Create task to restart monitoring
            task = Task.create(
                task_type="restart_monitoring",
                data=json.dumps(
                    {
                        "user_id": user_id,
                        "topic_id": topic.id,
                        "target_topic": topic.target_topic,
                        "search_area": topic.search_area,
                    }
                ),
                status="pending",
            )

            task_events.task_created(
                task_id=task.id,
                task_type="restart_monitoring",
                data={"user_id": user_id, "topic_id": topic.id},
            )

            message_text = (
                f"🔄 <b>Topics swapped</b>\n\n"
                f"🎯 <b>New target topic:</b> {escape_html(topic.target_topic)}\n"
                f"🔍 <b>New search area:</b> {escape_html(topic.search_area)}\n\n"
                f"🤖 Monitoring restarted with new parameters."
            )

            await message.answer(message_text, parse_mode=ParseMode.HTML)

        except DoesNotExist:
            await message.answer(
                "❌ <b>Topics not set</b>\n\n" "First use /topic to set topics.",
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
            settings = UserSettings.get(UserSettings.user_id == user_id)
            settings.monitoring_enabled = False
            settings.save()

            await message.answer(
                "⏸️ <b>Monitoring paused</b>\n\n" "Use /resume to resume.",
                parse_mode=ParseMode.HTML,
            )

        except DoesNotExist:
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
            settings = UserSettings.get(UserSettings.user_id == user_id)
            settings.monitoring_enabled = True
            settings.save()

            await message.answer(
                "▶️ <b>Monitoring resumed</b>\n\n"
                "AI agent has continued searching for relevant articles.",
                parse_mode=ParseMode.HTML,
            )

        except DoesNotExist:
            await message.answer("❌ User settings not found.")

        # Don't close connection here - let the caller manage it

    except Exception as e:
        logger.error(f"Error in /resume command: {e}")
        await message.answer("❌ An error occurred while resuming.")



