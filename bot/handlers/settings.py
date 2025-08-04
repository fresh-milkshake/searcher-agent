from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import re

from bot.utils import escape_html
from shared.database import UserSettings, ensure_connection
from peewee import DoesNotExist
from shared.logger import get_logger

router = Router(name="settings")

logger = get_logger(__name__)


@router.message(Command("settings"))
async def command_settings_handler(message: Message) -> None:
    """Show current settings"""
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
        except DoesNotExist:
            # Create default settings
            settings = UserSettings.create(user_id=user_id)

        status_text = "Enabled" if settings.monitoring_enabled else "Disabled"
        
        # Check group chat configuration
        group_info = ""
        if settings.group_chat_id:
            group_info = f"\n📬 <b>Group Chat:</b> Configured (ID: {settings.group_chat_id})"
        else:
            group_info = "\n📬 <b>Group Chat:</b> Not configured (using personal chat)"

        settings_text = f"""
⚙️ <b>Analysis Settings</b>

📊 <b>Relevance Thresholds:</b>
• Search Area: {settings.min_search_area_relevance:.1f}%
• Target Topic: {settings.min_target_topic_relevance:.1f}%
• Overall Score: {settings.min_overall_relevance:.1f}%

🔔 <b>Notifications:</b>
• Instant: ≥{settings.instant_notification_threshold:.1f}%
• Daily Digest: ≥{settings.daily_digest_threshold:.1f}%
• Weekly Digest: ≥{settings.weekly_digest_threshold:.1f}%
{group_info}

🤖 <b>Status:</b> {escape_html(status_text)}

⚙️ <b>Settings Commands:</b>
• /set_relevance [area|topic|overall] [value] - Set relevance thresholds
• /set_notification [instant|daily|weekly] [value] - Set notification thresholds
• /reset_settings - Reset to default values

🗣️ <b>Group Chat Commands:</b>
• /set_group - Configure group notifications (use in group)
• /unset_group - Return to personal notifications
        """

        await message.answer(settings_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in /settings command: {e}")
        await message.answer("❌ An error occurred while getting settings.")


@router.message(Command("set_relevance"))
async def command_set_relevance_handler(message: Message) -> None:
    """Set relevance thresholds"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Parse command arguments
        pattern = r'/set_relevance\s+(\w+)\s+(\d+(?:\.\d+)?)'
        match = re.search(pattern, command_text)

        if not match:
            await message.answer(
                "❌ <b>Invalid format</b>\n\n"
                "✅ Correct format:\n"
                "/set_relevance [type] [value]\n\n"
                "📝 Types: area, topic, overall\n"
                "📊 Value: 0-100 (percentage)\n\n"
                "💡 Examples:\n"
                "• /set_relevance area 60\n"
                "• /set_relevance topic 70\n"
                "• /set_relevance overall 65",
                parse_mode=ParseMode.HTML,
            )
            return

        threshold_type = match.group(1).lower()
        value = float(match.group(2))

        if not (0 <= value <= 100):
            await message.answer("❌ Value must be between 0 and 100.")
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            # Get or create user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
            except DoesNotExist:
                settings = UserSettings.create(user_id=user_id)

            # Update the appropriate threshold
            if threshold_type == "area":
                settings.min_search_area_relevance = value
                threshold_name = "Search Area"
            elif threshold_type == "topic":
                settings.min_target_topic_relevance = value
                threshold_name = "Target Topic"
            elif threshold_type == "overall":
                settings.min_overall_relevance = value
                threshold_name = "Overall Score"
            else:
                await message.answer(
                    "❌ Invalid threshold type. Use: area, topic, or overall."
                )
                return

            settings.save()

            await message.answer(
                f"✅ <b>{threshold_name} threshold updated</b>\n\n"
                f"📊 New value: {value:.1f}%\n"
                f"📋 Use /settings to view all current settings.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} updated {threshold_type} relevance threshold to {value}")

        except Exception as db_error:
            logger.error(f"Database error in /set_relevance: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as e:
        logger.error(f"Error in /set_relevance command: {e}")
        await message.answer("❌ An error occurred while setting relevance threshold.")


@router.message(Command("set_notification"))
async def command_set_notification_handler(message: Message) -> None:
    """Set notification thresholds"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Parse command arguments
        pattern = r'/set_notification\s+(\w+)\s+(\d+(?:\.\d+)?)'
        match = re.search(pattern, command_text)

        if not match:
            await message.answer(
                "❌ <b>Invalid format</b>\n\n"
                "✅ Correct format:\n"
                "/set_notification [type] [value]\n\n"
                "📝 Types: instant, daily, weekly\n"
                "📊 Value: 0-100 (percentage)\n\n"
                "💡 Examples:\n"
                "• /set_notification instant 80\n"
                "• /set_notification daily 50\n"
                "• /set_notification weekly 30",
                parse_mode=ParseMode.HTML,
            )
            return

        notification_type = match.group(1).lower()
        value = float(match.group(2))

        if not (0 <= value <= 100):
            await message.answer("❌ Value must be between 0 and 100.")
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            # Get or create user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
            except DoesNotExist:
                settings = UserSettings.create(user_id=user_id)

            # Update the appropriate threshold
            if notification_type == "instant":
                settings.instant_notification_threshold = value
                threshold_name = "Instant Notification"
            elif notification_type == "daily":
                settings.daily_digest_threshold = value
                threshold_name = "Daily Digest"
            elif notification_type == "weekly":
                settings.weekly_digest_threshold = value
                threshold_name = "Weekly Digest"
            else:
                await message.answer(
                    "❌ Invalid notification type. Use: instant, daily, or weekly."
                )
                return

            settings.save()

            await message.answer(
                f"✅ <b>{threshold_name} threshold updated</b>\n\n"
                f"📊 New value: {value:.1f}%\n"
                f"📋 Use /settings to view all current settings.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} updated {notification_type} notification threshold to {value}")

        except Exception as db_error:
            logger.error(f"Database error in /set_notification: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as e:
        logger.error(f"Error in /set_notification command: {e}")
        await message.answer("❌ An error occurred while setting notification threshold.")


@router.message(Command("set_search_depth"))
async def command_set_search_depth_handler(message: Message) -> None:
    """Set search depth in days"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Parse command arguments
        pattern = r'/set_search_depth\s+(\d+)'
        match = re.search(pattern, command_text)

        if not match:
            await message.answer(
                "❌ <b>Invalid format</b>\n\n"
                "✅ Correct format:\n"
                "/set_search_depth [days]\n\n"
                "📝 Days: 1-30 (how far back to search)\n\n"
                "💡 Examples:\n"
                "• /set_search_depth 7 (search last week)\n"
                "• /set_search_depth 14 (search last 2 weeks)\n"
                "• /set_search_depth 30 (search last month)",
                parse_mode=ParseMode.HTML,
            )
            return

        days = int(match.group(1))

        if not (1 <= days <= 30):
            await message.answer("❌ Days must be between 1 and 30.")
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            # Get or create user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
            except DoesNotExist:
                settings = UserSettings.create(user_id=user_id)

            settings.days_back_to_search = str(days)
            settings.save()

            await message.answer(
                f"✅ <b>Search depth updated</b>\n\n"
                f"📅 New value: {days} days\n"
                f"📋 Use /settings to view all current settings.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} updated search depth to {days} days")

        except Exception as db_error:
            logger.error(f"Database error in /set_search_depth: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as e:
        logger.error(f"Error in /set_search_depth command: {e}")
        await message.answer("❌ An error occurred while setting search depth.")


@router.message(Command("reset_settings"))
async def command_reset_settings_handler(message: Message) -> None:
    """Reset settings to default values"""
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
            # Get or create user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                # Preserve group_chat_id when resetting
                group_chat_id = settings.group_chat_id
            except DoesNotExist:
                group_chat_id = None

            # Delete and recreate with defaults
            if 'settings' in locals():
                settings.delete_instance()

            settings = UserSettings.create(
                user_id=user_id,
                group_chat_id=group_chat_id  # Preserve group chat setting
            )

            await message.answer(
                "✅ <b>Settings reset to defaults</b>\n\n"
                "📊 <b>Default values:</b>\n"
                "• Search Area: 50.0%\n"
                "• Target Topic: 50.0%\n"
                "• Overall Score: 60.0%\n"
                "• Instant Notifications: 80.0%\n"
                "• Daily Digest: 50.0%\n"
                "• Weekly Digest: 30.0%\n"
                "• Search Depth: 7 days\n\n"
                "💡 Group chat settings were preserved.\n"
                "📋 Use /settings to view current settings.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} reset settings to defaults")

        except Exception as db_error:
            logger.error(f"Database error in /reset_settings: {db_error}")
            await message.answer("❌ An error occurred while resetting settings.")

    except Exception as e:
        logger.error(f"Error in /reset_settings command: {e}")
        await message.answer("❌ An error occurred while resetting settings.")


@router.message(Command("set_group"))
async def command_set_group_handler(message: Message) -> None:
    """Set group chat for notifications"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        chat_id = message.chat.id

        # Check if this is a group or supergroup
        if message.chat.type not in ["group", "supergroup"]:
            await message.answer(
                "❌ <b>This command can only be used in group chats</b>\n\n"
                "Add this bot to a group chat and use the command there.",
                parse_mode=ParseMode.HTML,
            )
            return

        # Ensure database connection
        try:
            ensure_connection()
        except Exception as e:
            logger.error(f"Failed to connect to database: {e}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            # Get or create user settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
            except DoesNotExist:
                settings = UserSettings.create(user_id=user_id)

            # Set group chat ID
            settings.group_chat_id = chat_id
            settings.save()

            await message.answer(
                "✅ <b>Group chat configured</b>\n\n"
                "📬 All notifications will now be sent to this group chat.\n"
                "💡 Use /unset_group to return to personal notifications.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} set group chat {chat_id} for notifications")

        except Exception as db_error:
            logger.error(f"Database error in /set_group: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as e:
        logger.error(f"Error in /set_group command: {e}")
        await message.answer("❌ An error occurred while setting group chat.")


@router.message(Command("unset_group"))
async def command_unset_group_handler(message: Message) -> None:
    """Unset group chat for notifications (return to personal chat)"""
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
            
            if not settings.group_chat_id:
                await message.answer(
                    "ℹ️ <b>Group chat not configured</b>\n\n"
                    "Notifications are already being sent to your personal chat.",
                    parse_mode=ParseMode.HTML,
                )
                return

            # Clear group chat ID
            old_group_id = settings.group_chat_id
            settings.group_chat_id = None
            settings.save()

            await message.answer(
                "✅ <b>Group chat unset</b>\n\n"
                "📬 Notifications will now be sent to your personal chat.\n"
                "💡 Use /set_group in a group chat to configure group notifications.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} unset group chat {old_group_id} for notifications")

        except DoesNotExist:
            await message.answer("❌ User settings not found.")

    except Exception as e:
        logger.error(f"Error in /unset_group command: {e}")
        await message.answer("❌ An error occurred while unsetting group chat.")