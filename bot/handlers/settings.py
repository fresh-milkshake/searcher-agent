from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import re
from textwrap import dedent

from bot.utils import escape_html
from shared.db import (
    ensure_connection,
    get_or_create_user_settings,
    update_user_settings,
)
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

        settings = await get_or_create_user_settings(user_id)

        status_text = "Enabled" if settings.monitoring_enabled else "Disabled"

        # Check group chat configuration
        group_info = ""
        if settings.group_chat_id:
            group_info = (
                f"\n📬 <b>Group Chat:</b> Configured (ID: {settings.group_chat_id})"
            )
        else:
            group_info = "\n📬 <b>Group Chat:</b> Not configured (using personal chat)"

        settings_text = dedent(f"""
        ⚙️ <b>Assistant Settings</b>

        📊 <b>Relevance</b>
        • Threshold: {settings.min_relevance:.1f}%

        🔔 <b>Notifications</b>
        • Instant: ≥{settings.instant_notification_threshold:.1f}%
        • Daily Digest: ≥{settings.daily_digest_threshold:.1f}%
        • Weekly Digest: ≥{settings.weekly_digest_threshold:.1f}%
        {group_info}

        🤖 <b>Status</b>
        • Monitoring: {escape_html(status_text)}

        🛠️ <b>Commands</b>
        • /set_relevance relevance [0-100]
        • /set_notification [instant|daily|weekly] [0-100]
        • /set_search_depth [days]
        • /reset_settings
        • /set_group, /unset_group
        """)

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
        pattern = r"/set_relevance\s+(\w+)\s+(\d+(?:\.\d+)?)"
        match = re.search(pattern, command_text)

        if not match:
            await message.answer(
                "❌ <b>Invalid format</b>\n\n"
                "✅ Correct format:\n"
                "/set_relevance [type] [value]\n\n"
                "📝 Types: relevance\n"
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
            # Update the appropriate threshold
            if threshold_type == "relevance":
                await update_user_settings(user_id, min_relevance=value)
                threshold_name = "Relevance"
            else:
                await message.answer("❌ Invalid threshold type. Use: relevance.")
                return

            await message.answer(
                f"✅ Saved: {threshold_name} = {value:.1f}%\n"
                f"📋 See /settings for details.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(
                f"User {user_id} updated {threshold_type} relevance threshold to {value}"
            )

        except Exception as db_error:
            logger.error(f"Database error in /set_relevance: {db_error}")
            await message.answer("❌ An error occurred while saving settings.")

    except Exception as e:
        logger.error(f"Error in /set_relevance command: {e}")
        await message.answer("❌ An error occurred while setting relevance threshold.")


@router.message(Command("set_notification"))
async def deprecated_set_notification_handler(message: Message) -> None:
    """Deprecated: moved to notifications module. Kept for compatibility and guidance."""
    try:
        await message.answer(
            dedent(
                """
                ℹ️ Command moved.

                Use /set_notification as before — it is now handled by the notifications module.
                """
            ),
            parse_mode=ParseMode.HTML,
        )
    except Exception:
        pass


@router.message(
    Command("set_search_depth")
)  # TODO: удалить или изменить все старые хэндлеры оставшиеся в коде от версии поисковика а не ассистента
async def command_set_search_depth_handler(message: Message) -> None:
    """Set search depth in days"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Parse command arguments
        pattern = r"/set_search_depth\s+(\d+)"
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
            await update_user_settings(user_id, days_back_to_search=str(days))

            await message.answer(
                f"✅ Saved: search depth = {days} days\n📋 See /settings for details.",
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
            settings = await get_or_create_user_settings(user_id)
            group_chat_id = getattr(settings, "group_chat_id", None)
            await update_user_settings(
                user_id,
                min_relevance=50.0,
                instant_notification_threshold=80.0,
                daily_digest_threshold=50.0,
                weekly_digest_threshold=30.0,
                days_back_to_search="7",
                group_chat_id=group_chat_id,
                monitoring_enabled=True,
            )

            await message.answer(
                "✅ Settings restored to defaults\n\n"
                "• Relevance: 50%\n"
                "• Instant: 80%\n"
                "• Daily: 50%\n"
                "• Weekly: 30%\n"
                "• Search Depth: 7 days\n\n"
                "💡 Group chat preserved. See /settings.",
                parse_mode=ParseMode.HTML,
            )

            logger.info(f"User {user_id} reset settings to defaults")

        except Exception as db_error:
            logger.error(f"Database error in /reset_settings: {db_error}")
            await message.answer("❌ An error occurred while resetting settings.")

    except Exception as e:
        logger.error(f"Error in /reset_settings command: {e}")
        await message.answer("❌ An error occurred while resetting settings.")
