from aiogram import Router

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from shared.database import (
    db,
    ResearchTopic,
    UserSettings,
    PaperAnalysis,
    ArxivPaper,
)
from peewee import DoesNotExist
from shared.logger import get_logger

router = Router(name="general")

logger = get_logger(__name__)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = "пользователь"
    if message.from_user and message.from_user.full_name:
        user_name = message.from_user.full_name

    help_text = f"""
🔬 Привет, {user_name}! Я бот для автоматического анализа научных статей arXiv.

Я умею искать пересечения между научными областями и находить интересные междисциплинарные исследования.

📋 **Доступные команды:**

🎯 `/topic "целевая тема" "область поиска"` - задать темы для анализа
📊 `/status` - текущее состояние мониторинга  
🔄 `/switch_themes` - поменять местами темы
⏸️ `/pause` - приостановить анализ
▶️ `/resume` - возобновить работу
📚 `/history` - последние найденные пересечения
⚙️ `/settings` - настройки фильтрации

**Пример использования:**
`/topic "машинное обучение" "медицина"`

Это найдет статьи в области медицины, которые используют методы машинного обучения.
    """

    await message.answer(help_text)


@router.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """Показать текущее состояние мониторинга"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        # Получаем активную тему
        try:
            topic = ResearchTopic.get(
                ResearchTopic.user_id == user_id, ResearchTopic.is_active
            )

            # Получаем настройки
            try:
                settings = UserSettings.get(UserSettings.user_id == user_id)
                monitoring_status = (
                    "🟢 Активен" if settings.monitoring_enabled else "🔴 Приостановлен"
                )
            except DoesNotExist:
                monitoring_status = "🟢 Активен"

            # Статистика анализов
            analyses_count = (
                PaperAnalysis.select()
                .join(ResearchTopic)
                .where(ResearchTopic.user_id == user_id)
                .count()
            )

            # Найденные релевантные статьи
            relevant_count = (
                PaperAnalysis.select()
                .join(ResearchTopic)
                .where(
                    ResearchTopic.user_id == user_id,
                    PaperAnalysis.overall_relevance >= 50.0,  # type: ignore
                )
                .count()
            )

            status_text = f"""
📊 **Статус мониторинга**

🎯 **Целевая тема:** {topic.target_topic}
🔍 **Область поиска:** {topic.search_area}
📅 **Создано:** {topic.created_at.strftime('%d.%m.%Y %H:%M')}

🤖 **Состояние:** {monitoring_status}
📈 **Проанализировано статей:** {analyses_count}
⭐ **Найдено релевантных:** {relevant_count}

🔧 Используйте `/settings` для настройки параметров
            """

            await message.answer(status_text)

        except DoesNotExist:
            await message.answer(
                "❌ **Темы не заданы**\n\n"
                'Используйте команду `/topic "целевая тема" "область поиска"` '
                "для начала мониторинга."
            )

        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /status: {e}")
        await message.answer("❌ Произошла ошибка при получении статуса.")


@router.message(Command("history"))
async def command_history_handler(message: Message) -> None:
    """Показать последние найденные пересечения тем"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        # Получаем последние 5 релевантных анализов
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
                "📚 **История пуста**\n\n"
                "Релевантные статьи пока не найдены.\n"
                "Попробуйте расширить критерии поиска через `/settings`."
            )
            return

        history_text = "📚 **Последние найденные пересечения тем:**\n\n"

        for analysis in analyses:
            paper = analysis.paper
            history_text += f"""
📄 **{paper.title[:80]}{"..." if len(paper.title) > 80 else ""}**
👥 {paper.authors.split(',')[0] if paper.authors else 'Авторы не указаны'}
📊 Релевантность: {analysis.overall_relevance:.1f}%
📅 {analysis.created_at.strftime('%d.%m.%Y')}
🔗 {paper.abs_url}

"""

        await message.answer(history_text)
        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /history: {e}")
        await message.answer("❌ Произошла ошибка при получении истории.")


@router.message()
async def unknown_message_handler(message: Message) -> None:
    """Обработчик неизвестных сообщений"""
    try:
        if not message.from_user or not message.from_user.id:
            logger.warning("Получено сообщение без информации о пользователе")
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        await message.answer(
            "❓ **Неизвестная команда**\n\n"
            "Используйте `/start` для просмотра доступных команд.\n\n"
            "🔬 Я специализируюсь на анализе научных статей arXiv. "
            "Задайте темы для анализа командой `/topic`."
        )

    except Exception as e:
        logger.error(f"Ошибка при обработке неизвестного сообщения: {e}")
        await message.answer("❌ Произошла ошибка при обработке сообщения.")
