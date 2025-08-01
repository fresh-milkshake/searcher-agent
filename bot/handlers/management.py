from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
import re
import json

from shared.database import db, ResearchTopic, UserSettings, Task
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import task_events

router = Router(name="management")

logger = get_logger(__name__)


@router.message(Command("topic"))
async def command_topic_handler(message: Message) -> None:
    """Обработчик команды /topic для задания тем анализа"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        command_text = message.text or ""

        # Парсим аргументы команды (ожидаем две темы в кавычках)
        pattern = r'/topic\s+"([^"]+)"\s+"([^"]+)"'
        match = re.search(pattern, command_text)

        if not match:
            await message.answer(
                "❌ Неверный формат команды.\n\n"
                "✅ Правильный формат:\n"
                '`/topic "целевая тема" "область поиска"`\n\n'
                "📝 Примеры:\n"
                '• `/topic "машинное обучение" "медицина"`\n'
                '• `/topic "квантовые вычисления" "криптография"`\n'
                '• `/topic "блокчейн" "логистика"`'
            )
            return

        target_topic = match.group(1).strip()
        search_area = match.group(2).strip()

        if len(target_topic) < 2 or len(search_area) < 2:
            await message.answer("❌ Темы должны содержать минимум 3 символа.")
            return

        db.connect()

        # Деактивируем предыдущие темы пользователя
        ResearchTopic.update(is_active=False).where(
            ResearchTopic.user_id == user_id, ResearchTopic.is_active
        ).execute()

        # Создаем новую тему
        topic = ResearchTopic.create(
            user_id=user_id,
            target_topic=target_topic,
            search_area=search_area,
            is_active=True,
        )

        # Создаем настройки пользователя если их нет
        try:
            UserSettings.get(UserSettings.user_id == user_id)
        except DoesNotExist:
            UserSettings.create(user_id=user_id)

        # Создаем задачу для ИИ агента на начало мониторинга
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

        # Уведомляем агента
        task_events.task_created(
            task_id=task.id,
            task_type="start_monitoring",
            data={"user_id": user_id, "topic_id": topic.id},
        )

        await message.answer(
            f"✅ **Темы для анализа установлены!**\n\n"
            f"🎯 **Целевая тема:** {target_topic}\n"
            f"🔍 **Область поиска:** {search_area}\n\n"
            f"🤖 ИИ-агент начал мониторинг arXiv для поиска пересечений тем.\n"
            f"📬 Я буду присылать уведомления о найденных релевантных статьях.\n\n"
            f"📊 Используйте `/status` для проверки состояния."
        )

        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /topic: {e}")
        await message.answer("❌ Произошла ошибка при установке тем.")


@router.message(Command("switch_themes"))
async def command_switch_themes_handler(message: Message) -> None:
    """Поменять местами целевую тему и область поиска"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        try:
            topic = ResearchTopic.get(
                ResearchTopic.user_id == user_id, ResearchTopic.is_active
            )

            # Меняем местами темы
            old_target = topic.target_topic
            old_area = topic.search_area

            topic.target_topic = old_area
            topic.search_area = old_target
            topic.save()

            # Создаем задачу для перезапуска мониторинга
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

            await message.answer(
                f"🔄 **Темы поменяны местами!**\n\n"
                f"🎯 **Новая целевая тема:** {topic.target_topic}\n"
                f"🔍 **Новая область поиска:** {topic.search_area}\n\n"
                f"🤖 Мониторинг перезапущен с новыми параметрами."
            )

        except DoesNotExist:
            await message.answer(
                "❌ **Темы не заданы**\n\n"
                "Сначала используйте `/topic` для задания тем."
            )

        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /switch_themes: {e}")
        await message.answer("❌ Произошла ошибка при смене тем.")


@router.message(Command("pause"))
async def command_pause_handler(message: Message) -> None:
    """Приостановить мониторинг"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        try:
            settings = UserSettings.get(UserSettings.user_id == user_id)
            settings.monitoring_enabled = False
            settings.save()

            await message.answer(
                "⏸️ **Мониторинг приостановлен**\n\n"
                "Используйте `/resume` для возобновления."
            )

        except DoesNotExist:
            await message.answer("❌ Настройки пользователя не найдены.")

        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /pause: {e}")
        await message.answer("❌ Произошла ошибка при приостановке.")


@router.message(Command("resume"))
async def command_resume_handler(message: Message) -> None:
    """Возобновить мониторинг"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        try:
            settings = UserSettings.get(UserSettings.user_id == user_id)
            settings.monitoring_enabled = True
            settings.save()

            await message.answer(
                "▶️ **Мониторинг возобновлен**\n\n"
                "ИИ-агент продолжил поиск релевантных статей."
            )

        except DoesNotExist:
            await message.answer("❌ Настройки пользователя не найдены.")

        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /resume: {e}")
        await message.answer("❌ Произошла ошибка при возобновлении.")


@router.message(Command("settings"))
async def command_settings_handler(message: Message) -> None:
    """Показать текущие настройки"""
    try:
        if not message.from_user:
            await message.answer("Ошибка: не удалось определить пользователя.")
            return

        user_id = message.from_user.id
        db.connect()

        try:
            settings = UserSettings.get(UserSettings.user_id == user_id)
        except DoesNotExist:
            # Создаем настройки по умолчанию
            settings = UserSettings.create(user_id=user_id)

        settings_text = f"""
⚙️ **Настройки анализа**

📊 **Пороги релевантности:**
• Область поиска: {settings.min_search_area_relevance:.1f}%
• Целевая тема: {settings.min_target_topic_relevance:.1f}%
• Общая оценка: {settings.min_overall_relevance:.1f}%

🔔 **Уведомления:**
• Мгновенные: ≥{settings.instant_notification_threshold:.1f}%
• Дневная сводка: ≥{settings.daily_digest_threshold:.1f}%
• Недельный дайджест: ≥{settings.weekly_digest_threshold:.1f}%

⏰ **Временные фильтры:**
• Глубина поиска: {settings.days_back_to_search} дней

🤖 **Состояние:** {"Включен" if settings.monitoring_enabled else "Выключен"}

💡 Для изменения настроек свяжитесь с разработчиком.
        """

        await message.answer(settings_text)
        db.close()

    except Exception as e:
        logger.error(f"Ошибка в команде /settings: {e}")
        await message.answer("❌ Произошла ошибка при получении настроек.")
