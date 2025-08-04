from aiogram import Router
from datetime import datetime

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from shared.database import (
    ResearchTopic,
    UserSettings,
    PaperAnalysis,
    ArxivPaper,
    AgentStatus,
    ensure_connection,
)
from peewee import DoesNotExist
from shared.logger import get_logger

router = Router(name="general")

logger = get_logger(__name__)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = "user"
    if message.from_user and message.from_user.full_name:
        user_name = message.from_user.full_name

    help_text = f"""
🔬 Hello, {user_name}! I'm a bot for automatic analysis of arXiv scientific articles.

I can find intersections between scientific fields and discover interesting interdisciplinary research.

📋 <b>Main commands:</b>
🎯 /topic "target topic" "search area" - set topics for analysis
📊 /status - current monitoring status  
🔄 /switch_themes - swap topics
⏸️ /pause - pause analysis
▶️ /resume - resume work
📚 /history - recent found intersections

⚙️ <b>Settings commands:</b>
📋 /settings - view current settings
🔧 /set_relevance [area|topic|overall] [value] - set relevance thresholds
🔔 /set_notification [instant|daily|weekly] [value] - set notification thresholds
📅 /set_search_depth [days] - set search depth in days
🔄 /reset_settings - reset to default values

🗣️ <b>Group chat commands:</b>
📬 /set_group - configure group notifications (use in group chat)
📱 /unset_group - return to personal notifications

<b>Usage example:</b>
/topic "machine learning" "medicine"

This will find articles in the field of medicine that use machine learning methods.

💡 <b>Group chat usage:</b>
Add this bot to a group chat and use /set_group to receive notifications there!
    """

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
        try:
            topic = ResearchTopic.get(
                ResearchTopic.user_id == user_id, ResearchTopic.is_active
            )

            # Get settings
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                monitoring_status = (
                    "🟢 Active" if settings.monitoring_enabled else "🔴 Paused"
                )
            except DoesNotExist:
                monitoring_status = "🟢 Active"

            # Analysis statistics
            analyses_count = (
                PaperAnalysis.select()
                .join(ResearchTopic)
                .where(ResearchTopic.user_id == user_id)
                .count()
            )

            # Found relevant articles
            relevant_count = (
                PaperAnalysis.select()
                .join(ResearchTopic)
                .where(
                    ResearchTopic.user_id == user_id,
                    PaperAnalysis.overall_relevance >= 50.0,  # type: ignore
                )
                .count()
            )

            # Get agent status
            agent_info = ""
            try:
                agent_status = AgentStatus.get(AgentStatus.agent_id == "main_agent")
                time_diff = datetime.now() - agent_status.last_activity

                if time_diff.total_seconds() < 600:  # Less than 10 minutes
                    agent_active = "🟢 Active"
                    activity_info = (
                        f"🔄 <b>Current activity:</b> {agent_status.activity}"
                    )

                    # Show current processing info if available
                    if agent_status.current_user_id:
                        if agent_status.current_user_id == user_id:
                            activity_info += "\n📍 <b>Processing your topics</b>"
                        else:
                            activity_info += f"\n📍 <b>Processing topics for user {agent_status.current_user_id}</b>"

                    session_info = "📊 <b>Session statistics:</b>\n"
                    session_info += (
                        f"• Papers processed: {agent_status.papers_processed}\n"
                    )
                    session_info += (
                        f"• Relevant papers found: {agent_status.papers_found}\n"
                    )
                    session_info += f"• Started: {agent_status.session_start.strftime('%d.%m.%Y %H:%M')}"

                else:
                    agent_active = "🔴 Inactive"
                    activity_info = f"⏰ <b>Last activity:</b> {agent_status.last_activity.strftime('%d.%m.%Y %H:%M')}"
                    session_info = ""

                agent_info = f"""

🤖 <b>AI Agent Status:</b> {agent_active}
{activity_info}
{session_info}
"""
            except DoesNotExist:
                agent_info = "\n🤖 <b>AI Agent Status:</b> ❓ Unknown"

            status_text = f"""
📊 <b>Monitoring Status</b>

🎯 <b>Target Topic:</b> {topic.target_topic}
🔍 <b>Search Area:</b> {topic.search_area}
📅 <b>Created:</b> {topic.created_at.strftime('%d.%m.%Y %H:%M')}

🤖 <b>Monitoring:</b> {monitoring_status}
📈 <b>Papers Analyzed:</b> {analyses_count}
⭐ <b>Relevant Found:</b> {relevant_count}
{agent_info}

🔧 Use /settings to configure parameters
            """

            await message.answer(status_text, parse_mode=ParseMode.HTML)

        except DoesNotExist:
            await message.answer(
                "❌ <b>Topics not set</b>\n\n"
                'Use command /topic "target topic" "search area" '
                "to start monitoring.",
                parse_mode=ParseMode.HTML,
            )

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
        analyses = (
            PaperAnalysis.select(PaperAnalysis, ArxivPaper, ResearchTopic)
            .join(ArxivPaper)
            .switch(PaperAnalysis)
            .join(ResearchTopic)
            .where(
                ResearchTopic.user_id == user_id,
                PaperAnalysis.overall_relevance >= 50.0,  # type: ignore
            )
            .order_by(PaperAnalysis.created_at.desc())
            .limit(5)
        )

        if not analyses:
            await message.answer(
                "📚 <b>History is empty</b>\n\n"
                "Relevant articles not found yet.\n"
                "Try expanding search criteria through /settings.",
                parse_mode=ParseMode.HTML,
            )
            return

        history_text = "📚 <b>Recent found topic intersections:</b>\n\n"

        for analysis in analyses:
            paper = analysis.paper
            title_preview = (
                paper.title[:80] + "..." if len(paper.title) > 80 else paper.title
            )
            authors_preview = (
                paper.authors.split(",")[0]
                if paper.authors
                else "Authors not specified"
            )

            history_text += f"""
📄 <b>{title_preview}</b>
👥 {authors_preview}
📊 Relevance: {analysis.overall_relevance:.1f}%
📅 {analysis.created_at.strftime('%d.%m.%Y')}
🔗 {paper.abs_url}

"""
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
            "Use /start to view available commands.\n\n"
            "🔬 I specialize in analyzing arXiv scientific articles. "
            "Set topics for analysis with /topic command.",
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"Error processing unknown message: {e}")
        await message.answer("❌ An error occurred while processing message.")
