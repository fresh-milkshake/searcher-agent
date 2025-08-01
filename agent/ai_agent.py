import asyncio
import os
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import db, Task, init_db
from peewee import DoesNotExist
from shared.llm import AGENT_MODEL
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events
from agents import Agent, Runner

load_dotenv()

logger = get_logger(__name__)


class AIAgent:
    def __init__(self):
        # Создаем агента с системным промптом
        self.agent = Agent(
            name="AI Assistant",
            model=AGENT_MODEL,
            instructions="Ты полезный ИИ-ассистент. Отвечай на вопросы пользователя кратко и информативно.",
        )

    async def process_message(self, message_text: str) -> str:
        """Обрабатывает сообщение с помощью agents SDK"""
        try:
            # Используем Runner для обработки сообщения
            result = await Runner.run(self.agent, message_text)

            if result and result.final_output:
                return str(result.final_output).strip()
            else:
                return "Извините, не удалось получить ответ от ИИ."

        except Exception as e:
            error_msg = str(e)
            logger.error(
                f"Ошибка при обработке сообщения через agents SDK: {error_msg}"
            )
            return f"Извините, произошла ошибка при обработке вашего сообщения: {error_msg}"

    async def process_task(self, task: Task) -> str:
        """Обрабатывает конкретную задачу в зависимости от её типа"""
        try:
            logger.info(f"Начинаю обработку задачи {task.id} типа {task.task_type}")

            if task.task_type == "process_message":
                result = await self.process_message(str(task.data))
                logger.info(
                    f"Задача {task.id} успешно обработана, результат: {len(result)} символов"
                )
                return result
            else:
                error_msg = f"Неизвестный тип задачи: {task.task_type}"
                logger.warning(error_msg)
                return error_msg

        except Exception as e:
            error_msg = f"Ошибка обработки: {str(e)}"
            logger.error(f"Ошибка при обработке задачи {task.id}: {e}")
            return error_msg


async def handle_task_creation(event: Event):
    """Обработчик создания новых задач - обрабатывает задачи по мере поступления"""
    try:
        task_id = event.data.get("task_id")
        task_type = event.data.get("task_type")

        if not task_id:
            logger.warning(f"Получено событие создания задачи без ID: {event.data}")
            return

        logger.info(
            f"🚀 РЕАЛЬНЫЙ АГЕНТ: Получено уведомление о новой задаче {task_id} типа {task_type}"
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
            agent = AIAgent()
            result = await agent.process_task(task)

            # Сохраняем результат
            task.result = result
            task.status = "completed"
            task.save()

            # Уведомляем о завершении через систему событий
            task_events.task_completed(task_id=task.id, result=result)

            logger.info(f"Задача {task_id} успешно завершена и результат отправлен")

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


async def main():
    """Основной цикл ИИ агента - гибридный подход"""
    logger.info("Запуск ИИ агента...")

    init_db()
    agent = AIAgent()

    # ПЛАН A: Подписываемся на события для новых задач
    event_bus = get_event_bus()
    task_events.subscribe_to_creations(handle_task_creation)

    logger.info("ИИ агент готов к обработке задач (гибридный режим)")
    logger.info("- События: для новых задач")
    logger.info("- Polling: для пропущенных задач")

    # Запускаем обработку событий в фоне
    asyncio.create_task(event_bus.start_processing(poll_interval=0.5))

    # ПЛАН B: Параллельно проверяем необработанные задачи каждые 10 секунд
    while True:
        try:
            # Проверяем необработанные задачи
            await check_and_process_pending_tasks(agent)
            await asyncio.sleep(10)  # Проверяем каждые 10 секунд

        except Exception as e:
            logger.error(f"Ошибка в цикле проверки задач: {e}")
            await asyncio.sleep(5)


async def check_and_process_pending_tasks(agent: AIAgent):
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
                    logger.info(f"🔄 Обрабатываем пропущенную задачу {task.id}")

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


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("ИИ агент остановлен пользователем")
    except Exception as e:
        logger.error(f"Критическая ошибка ИИ агента: {e}")
        raise
