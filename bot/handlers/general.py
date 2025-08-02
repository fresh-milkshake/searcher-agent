from aiogram import Router
from datetime import datetime

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from bot.utils import format_html
from shared.database import (
    db,
    ResearchTopic,
    UserSettings,
    PaperAnalysis,
    ArxivPaper,
    AgentStatus,
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

📋 **Available commands:**

🎯 /topic "target topic" "search area" - set topics for analysis
📊 /status - current monitoring status  
🔄 /switch_themes - swap topics
⏸️ /pause - pause analysis
▶️ /resume - resume work
📚 /history - recent found intersections
⚙️ /settings - filtering settings

**Usage example:**
/topic "machine learning" "medicine"

This will find articles in the field of medicine that use machine learning methods.
    """

    await message.answer(format_html(help_text), parse_mode=ParseMode.HTML)


@router.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """Show current monitoring status"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user\\.")
            return

        user_id = message.from_user.id
        db.connect()

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
                    agent_active = "🟢 Активен"
                    activity_info = (
                        f"🔄 **Текущая активность:** {agent_status.activity}"
                    )

                    # Show current processing info if available
                    if agent_status.current_user_id:
                        if agent_status.current_user_id == user_id:
                            activity_info += "\n📍 **Обрабатывает ваши топики**"
                        else:
                            activity_info += f"\n📍 **Обрабатывает топики пользователя {agent_status.current_user_id}**"

                    session_info = "📊 **Статистика сессии:**\n"
                    session_info += (
                        f"• Обработано статей: {agent_status.papers_processed}\n"
                    )
                    session_info += (
                        f"• Найдено релевантных: {agent_status.papers_found}\n"
                    )
                    session_info += f"• Запущен: {agent_status.session_start.strftime('%d.%m.%Y %H:%M')}"

                else:
                    agent_active = "🔴 Неактивен"
                    activity_info = f"⏰ **Последняя активность:** {agent_status.last_activity.strftime('%d.%m.%Y %H:%M')}"
                    session_info = ""

                agent_info = f"""

🤖 **Статус AI агента:** {agent_active}
{activity_info}
{session_info}
"""
            except DoesNotExist:
                agent_info = "\n🤖 **Статус AI агента:** ❓ Неизвестен"

            status_text = f"""
📊 **Статус мониторинга**

🎯 **Целевая тема:** {topic.target_topic}
🔍 **Область поиска:** {topic.search_area}
📅 **Создан:** {topic.created_at.strftime('%d.%m.%Y %H:%M')}

🤖 **Мониторинг:** {monitoring_status}
📈 **Статей проанализировано:** {analyses_count}
⭐ **Найдено релевантных:** {relevant_count}
{agent_info}

🔧 Используйте /settings для настройки параметров
            """

            await message.answer(
                format_html(status_text), parse_mode=ParseMode.HTML
            )

        except DoesNotExist:
            await message.answer(
                format_html(
                    "❌ **Topics not set**\n\n"
                    'Use command /topic "target topic" "search area" '
                    "to start monitoring\\."
                ),
                parse_mode=ParseMode.HTML,
            )

        db.close()

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        await message.answer("❌ An error occurred while getting status\\.")


@router.message(Command("history"))
async def command_history_handler(message: Message) -> None:
    """Show recent found topic intersections"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user\\.")
            return

        user_id = message.from_user.id
        db.connect()

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
                format_html("📚 **History is empty**\n\n"
                "Relevant articles not found yet\\.\n"
                "Try expanding search criteria through /settings\\."),
                parse_mode=ParseMode.HTML,
            )
            return

        history_text = "📚 **Recent found topic intersections:**\n\n"

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
📄 **{title_preview}**
👥 {authors_preview}
📊 Relevance: {analysis.overall_relevance:.1f}%
📅 {analysis.created_at.strftime('%d.%m.%Y')}
🔗 {paper.abs_url}

"""
        await message.answer(
            format_html(history_text), parse_mode=ParseMode.HTML
        )
        db.close()

    except Exception as e:
        logger.error(f"Error in /history command: {e}")
        await message.answer("❌ An error occurred while getting history\\.")


@router.message()
async def unknown_message_handler(message: Message) -> None:
    """Handler for unknown messages"""
    try:
        if not message.from_user or not message.from_user.id:
            logger.warning("Received message without user information")
            await message.answer("Error: could not determine user\\.")
            return

        await message.answer(
            format_html("❓ **Unknown command**\n\n"
            "Use /start to view available commands\\.\n\n"
            "🔬 I specialize in analyzing arXiv scientific articles\\. "
            "Set topics for analysis with /topic command\\."),
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"Error processing unknown message: {e}")
        await message.answer("❌ An error occurred while processing message\\.")
