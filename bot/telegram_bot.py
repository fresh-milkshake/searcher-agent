import asyncio
import os
import json
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import db, Task, ResearchTopic, PaperAnalysis, ArxivPaper, init_db
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from bot.handlers import general_router, management_router

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

logger = get_logger(__name__)

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()
dp.include_router(general_router)
dp.include_router(management_router)


async def handle_task_completion(event: Event):
    """Обработчик завершения задач - отправляет отчеты и уведомления"""
    try:
        task_id = event.data.get("task_id")
        result = event.data.get("result")
        task_type = event.data.get("task_type", "unknown")

        if not task_id:
            logger.warning(f"Событие завершения задачи без ID: {event.data}")
            return

        db.connect()

        try:
            task = Task.get(Task.id == task_id)

            # Получаем данные задачи
            task_data = json.loads(task.data) if task.data else {}
            user_id = task_data.get("user_id")

            if not user_id:
                logger.warning(f"Задача {task_id} не содержит user_id")
                return

            # Обрабатываем разные типы задач
            if task_type == "analysis_complete":
                # Отправляем отчет о найденной релевантной статье
                analysis_id = task_data.get("analysis_id")
                if analysis_id:
                    await send_analysis_report(user_id, analysis_id)

            elif task_type == "monitoring_started":
                # Подтверждение начала мониторинга
                await bot.send_message(
                    chat_id=user_id,
                    text="🤖 **Мониторинг запущен!**\n\nИИ-агент начал поиск релевантных статей.",
                )

            elif task_type in ["start_monitoring", "restart_monitoring"]:
                # Подтверждение настройки мониторинга
                await bot.send_message(
                    chat_id=user_id,
                    text=f"✅ {result}" if result else "✅ Мониторинг настроен",
                )

            elif result:
                # Общие ответы для других типов задач
                await bot.send_message(chat_id=user_id, text=result)

            # Помечаем задачу как отправленную
            task.status = "sent"
            task.save()

            logger.info(f"Обработано завершение задачи {task_id} типа {task_type}")

        except DoesNotExist:
            logger.error(f"Задача {task_id} не найдена в базе данных")

        db.close()

    except Exception as e:
        logger.error(f"Ошибка при обработке завершения задачи: {e}")


async def send_analysis_report(user_id: int, analysis_id: int):
    """Отправляет структурированный отчет о найденной статье"""
    try:
        db.connect()

        # Получаем анализ с данными статьи и темы
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

        # Формируем отчет согласно idea.md
        report = f"""
🔬 **Найдено пересечение тем: "{topic.target_topic}" в области "{topic.search_area}"**

📄 **Название:** {paper.title}

👥 **Авторы:** {paper.authors if paper.authors else 'Не указаны'}

📅 **Дата публикации:** {paper.published.strftime('%d.%m.%Y')}

📚 **Категория arXiv:** {paper.primary_category or 'Не указана'}

🔗 **Ссылка:** {paper.abs_url}

📊 **Анализ пересечения тем:**
• Релевантность области поиска: {analysis.search_area_relevance:.1f}%
• Содержание целевой темы: {analysis.target_topic_relevance:.1f}%
• **Интегральная оценка: {analysis.overall_relevance:.1f}%**

📋 **Краткое резюме:**
{analysis.summary or 'Анализ в процессе'}
        """

        # Добавляем ключевые фрагменты если есть
        if analysis.key_fragments:
            try:
                fragments = json.loads(analysis.key_fragments)
                if fragments:
                    report += "\n\n🔍 **Ключевые фрагменты:**\n"
                    for fragment in fragments[:3]:  # Максимум 3 фрагмента
                        report += f"• {fragment}\n"
            except json.JSONDecodeError:
                pass

        # Добавляем контекстуальное обоснование
        if analysis.contextual_reasoning:
            report += f"\n\n💡 **Контекстуальное обоснование:**\n{analysis.contextual_reasoning}"

        await bot.send_message(chat_id=user_id, text=report)

        # Помечаем анализ как отправленный
        analysis.status = "sent"
        analysis.save()

        logger.info(f"Отправлен отчет пользователю {user_id} по анализу {analysis_id}")
        db.close()

    except Exception as e:
        logger.error(f"Ошибка при отправке отчета анализа {analysis_id}: {e}")
        db.close()


async def main() -> None:
    logger.info("Запуск телеграм бота...")

    init_db()

    # Получаем шину событий и подписываемся на завершение задач
    event_bus = get_event_bus()
    task_events.subscribe_to_completions(handle_task_completion)

    # Запускаем обработку событий в фоне
    asyncio.create_task(event_bus.start_processing(poll_interval=0.5))

    logger.info("Телеграм бот готов к работе")

    # Запускаем бота
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
