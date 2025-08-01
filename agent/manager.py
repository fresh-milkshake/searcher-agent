import asyncio
import os
import json
from datetime import datetime, timedelta
from typing import Dict, Any
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import (
    db, Task, ResearchTopic, UserSettings, init_db
)
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from agent.agent import ArxivAnalysisAgent

load_dotenv()

logger = get_logger(__name__)


async def handle_task_creation(event: Event):
    """Обработчик создания новых задач - обрабатывает задачи по мере поступления"""
    try:
        task_id = event.data.get("task_id")
        task_type = event.data.get("task_type")

        if not task_id:
            logger.warning(f"Получено событие создания задачи без ID: {event.data}")
            return

        logger.info(
            f"🚀 arXiv АГЕНТ: Получено уведомление о новой задаче {task_id} типа {task_type}"
        )

        db.connect()

        try:
            # Получаем задачу из базы данных
            task = Task.get(Task.id == task_id)

            if task.status != "pending":
                logger.info(
                    f"Задача {task_id} уже обрабатывается (статус: {task.status})"
                )
                return

            # Помечаем задачу как обрабатываемую
            task.status = "processing"
            task.save()

            # Создаем агента и обрабатываем задачу
            agent = ArxivAnalysisAgent()
            result = await agent.process_task(task)

            # Сохраняем результат
            task.result = result
            task.status = "completed"
            task.save()

            # Уведомляем о завершении через систему событий
            task_events.task_completed(task_id=task.id, result=result)

            logger.info(f"Задача {task_id} успешно завершена: {result}")

        except DoesNotExist:
            logger.error(f"Задача {task_id} не найдена в базе данных")
        except Exception as e:
            logger.error(f"Ошибка при обработке задачи {task_id}: {e}")
            # Помечаем задачу как неудачную
            try:
                task = Task.get(Task.id == task_id)
                task.status = "failed"
                task.result = f"Ошибка: {str(e)}"
                task.save()
                task_events.task_failed(task_id=task_id, error=str(e))
            except Exception:
                pass

        db.close()

    except Exception as e:
        logger.error(f"Критическая ошибка в обработчике создания задач: {e}")


async def check_and_process_pending_tasks(agent: ArxivAnalysisAgent):
    """Проверка и обработка необработанных задач"""
    try:
        db.connect()

        # Ищем необработанные задачи
        pending_tasks = Task.select().where(Task.status == "pending")

        if pending_tasks.count() > 0:
            logger.info(
                f"🔍 Найдено {pending_tasks.count()} необработанных задач, обрабатываем..."
            )

            for task in pending_tasks:
                try:
                    logger.info(f"🔄 Обрабатываем пропущенную задачу {task.id} типа {task.task_type}")

                    # Помечаем как обрабатываемую
                    task.status = "processing"
                    task.save()

                    # Обрабатываем
                    result = await agent.process_task(task)

                    # Сохраняем результат
                    task.result = result
                    task.status = "completed"
                    task.save()

                    # Уведомляем о завершении
                    task_events.task_completed(task_id=task.id, result=result)

                    logger.info(f"✅ Пропущенная задача {task.id} успешно обработана")

                except Exception as e:
                    logger.error(f"❌ Ошибка при обработке задачи {task.id}: {e}")
                    task.status = "failed"
                    task.result = f"Ошибка: {str(e)}"
                    task.save()

        db.close()

    except Exception as e:
        logger.error(f"Ошибка при проверке необработанных задач: {e}")


async def periodic_monitoring(agent: ArxivAnalysisAgent):
    """Периодический мониторинг активных исследовательских тем"""
    try:
        db.connect()
        
        # Получаем все активные темы
        active_topics = ResearchTopic.select().where(ResearchTopic.is_active)
        
        for topic in active_topics:
            try:
                # Проверяем, включен ли мониторинг для пользователя
                try:
                    settings = UserSettings.get(UserSettings.user_id == topic.user_id)
                    if not settings.monitoring_enabled:
                        continue
                except DoesNotExist:
                    continue
                
                # Проверяем, когда последний раз мониторили эту тему
                user_monitoring = agent.monitoring_active.get(topic.user_id)
                if user_monitoring:
                    last_check = user_monitoring.get("last_check", datetime.now() - timedelta(hours=1))
                    if datetime.now() - last_check < timedelta(minutes=30):
                        continue  # Слишком рано для повторной проверки
                
                logger.info(f"Периодический мониторинг темы {topic.id} для пользователя {topic.user_id}")
                
                # Выполняем поиск новых статей
                await agent.perform_arxiv_search(
                    topic.user_id, 
                    topic.target_topic, 
                    topic.search_area, 
                    topic.id
                )
                
                # Обновляем время последней проверки
                if topic.user_id in agent.monitoring_active:
                    agent.monitoring_active[topic.user_id]["last_check"] = datetime.now()
                
            except Exception as e:
                logger.error(f"Ошибка при мониторинге темы {topic.id}: {e}")
        
        db.close()
        
    except Exception as e:
        logger.error(f"Ошибка при периодическом мониторинге: {e}")
        db.close()


async def main():
    """Основной цикл arXiv анализа агента"""
    logger.info("Запуск arXiv анализа агента...")

    init_db()
    agent = ArxivAnalysisAgent()

    # Подписываемся на события для новых задач
    event_bus = get_event_bus()
    task_events.subscribe_to_creations(handle_task_creation)

    logger.info("arXiv агент готов к работе!")
    logger.info("- Мониторинг arXiv статей")
    logger.info("- Двухэтапный анализ тем")
    logger.info("- Автоматические отчеты")

    # Запускаем обработку событий в фоне
    asyncio.create_task(event_bus.start_processing(poll_interval=0.5))

    # Основной цикл - периодический мониторинг активных тем
    while True:
        try:
            # Проверяем необработанные задачи
            await check_and_process_pending_tasks(agent)
            
            # Выполняем периодический мониторинг активных тем
            await periodic_monitoring(agent)
            
            await asyncio.sleep(300)  # Проверяем каждые 5 минут

        except Exception as e:
            logger.error(f"Ошибка в главном цикле агента: {e}")
            await asyncio.sleep(60)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ИИ агент остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка ИИ агента: {e}")
        raise
