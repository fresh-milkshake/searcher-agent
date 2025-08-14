import re

from aiogram import Router
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.types import Message

from bot.utils import escape_html
from shared.db import (
    ensure_connection,
    get_user_settings,
    update_user_settings,
)
from shared.logging import get_logger
from .service import simplify_for_layperson


router = Router(name="notifications")
logger = get_logger(__name__)


@router.message(Command("set_notification"))
async def command_set_notification_handler(message: Message) -> None:
    """Set notification thresholds."""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        pattern = r"/set_notification\s+(\w+)\s+(\d+(?:\.\d+)?)"
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

        try:
            ensure_connection()
        except Exception as conn_error:
            logger.error(f"Failed to connect to database: {conn_error}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            if notification_type == "instant":
                await update_user_settings(
                    user_id, instant_notification_threshold=value
                )
                threshold_name = "Instant Notification"
            elif notification_type == "daily":
                await update_user_settings(user_id, daily_digest_threshold=value)
                threshold_name = "Daily Digest"
            elif notification_type == "weekly":
                await update_user_settings(user_id, weekly_digest_threshold=value)
                threshold_name = "Weekly Digest"
            else:
                await message.answer(
                    "❌ Invalid notification type. Use: instant, daily, or weekly."
                )
                return

            human = await simplify_for_layperson(
                f"Notification preference changed: {threshold_name} >= {value:.1f}%"
            )
            await message.answer(
                f"✅ Saved: {threshold_name} = {value:.1f}%\n{escape_html(human)}",
                parse_mode=ParseMode.HTML,
            )

            logger.info(
                f"User {user_id} updated {notification_type} notification threshold to {value}"
            )

        except Exception as db_error:
            logger.error(f"Database error in /set_notification: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as error:
        logger.error(f"Error in /set_notification command: {error}")
        await message.answer(
            "❌ An error occurred while setting notification threshold."
        )


@router.message(Command("set_group"))
async def command_set_group_handler(message: Message) -> None:
    """Set group chat for notifications."""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        chat_id = message.chat.id

        if message.chat.type not in ["group", "supergroup"]:
            await message.answer(
                "❌ <b>This command can only be used in group chats</b>\n\n"
                "Add this bot to a group chat and use the command there.",
                parse_mode=ParseMode.HTML,
            )
            return

        try:
            ensure_connection()
        except Exception as conn_error:
            logger.error(f"Failed to connect to database: {conn_error}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            await update_user_settings(user_id, group_chat_id=chat_id)
            # Re-read to confirm
            settings = await get_user_settings(user_id)
            logger.info(
                f"Confirmed group_chat_id for user {user_id}: {getattr(settings, 'group_chat_id', None)}"
            )
            human = await simplify_for_layperson(
                "Group chat configured for notifications."
            )
            await message.answer(
                f"✅ Group notifications enabled\n{escape_html(human)}",
                parse_mode=ParseMode.HTML,
            )
            logger.info(f"User {user_id} set group chat {chat_id} for notifications")
        except Exception as db_error:
            logger.error(f"Database error in /set_group: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as error:
        logger.error(f"Error in /set_group command: {error}")
        await message.answer("❌ An error occurred while setting group chat.")


@router.message(Command("unset_group"))
async def command_unset_group_handler(message: Message) -> None:
    """Unset group chat for notifications (return to personal chat)."""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id

        try:
            ensure_connection()
        except Exception as conn_error:
            logger.error(f"Failed to connect to database: {conn_error}")
            await message.answer("❌ Database connection error. Please try again.")
            return

        try:
            settings = await get_user_settings(user_id)

            if not (settings and getattr(settings, "group_chat_id", None)):
                await message.answer(
                    "ℹ️ <b>Group chat not configured</b>\n\n"
                    "Notifications are already being sent to your personal chat.",
                    parse_mode=ParseMode.HTML,
                )
                return

            old_group_id = getattr(settings, "group_chat_id", None)
            await update_user_settings(user_id, group_chat_id=None)

            human = await simplify_for_layperson(
                "Notifications will now arrive in your personal chat."
            )
            await message.answer(
                f"✅ Back to personal notifications\n{escape_html(human)}",
                parse_mode=ParseMode.HTML,
            )

            logger.info(
                f"User {user_id} unset group chat {old_group_id} for notifications"
            )

        except Exception:
            await message.answer("❌ User settings not found.")

    except Exception as error:
        logger.error(f"Error in /unset_group command: {error}")
        await message.answer("❌ An error occurred while unsetting group chat.")
