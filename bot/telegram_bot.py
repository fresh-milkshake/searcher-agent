import asyncio
import os
from aiogram import Bot, Dispatcher
from aiogram.filters import CommandStart
from aiogram.types import Message
from dotenv import load_dotenv
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.database import db, Message as DBMessage, Task, init_db
from peewee import DoesNotExist
from shared.logger import get_logger
from shared.event_system import get_event_bus, Event, task_events

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN не найден в переменных окружения")

logger = get_logger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


@dp.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = "пользователь"
    if message.from_user and message.from_user.full_name:
        user_name = message.from_user.full_name
    
    await message.answer(
        f"Привет, {user_name}! Я бот с ИИ агентом. Отправь мне любое сообщение, и я обработаю его с помощью ИИ."
    )


@dp.message()
async def message_handler(message: Message) -> None:
    try:
        # Проверяем обязательные поля
        if not message.from_user or not message.from_user.id:
            logger.warning("Получено сообщение без информации о пользователе")
            await message.answer("Ошибка: не удалось определить пользователя.")
            return
            
        if not message.text:
            logger.warning("Получено пустое сообщение")
            await message.answer("Пожалуйста, отправьте текстовое сообщение.")
            return
        
        user_id = message.from_user.id
        message_text = message.text
        
        logger.info(
            f"Получено сообщение от пользователя {user_id}: {message_text[:50]}..."
        )

        db.connect()

        # Сохраняем сообщение пользователя в базу данных
        db_message = DBMessage.create(
            user_id=user_id,
            content=message_text,
            message_type="user",
            status="pending",
        )

        # Создаем задачу для ИИ агента
        task = Task.create(
            message_id=db_message.id,
            task_type="process_message",
            data=message_text,
            status="pending",
        )

        # Уведомляем через систему событий о создании задачи
        task_events.task_created(
            task_id=task.id,
            task_type="process_message",
            data={"user_id": user_id, "message_text": message_text},
        )

        await message.answer("Сообщение получено! Обрабатываю с помощью ИИ...")
        logger.info(f"Создана задача {task.id} для пользователя {user_id}")

        db.close()

    except Exception as e:
        logger.error(f"Ошибка при обработке сообщения: {e}")
        await message.answer("Произошла ошибка при обработке сообщения.")


async def handle_task_completion(event: Event):
    """Обработчик завершения задач - отправляет ответы пользователям"""
    try:
        task_id = event.data.get("task_id")
        result = event.data.get("result")

        if not task_id or not result:
            logger.warning(f"Неполные данные в событии завершения задачи: {event.data}")
            return

        db.connect()

        # Получаем задачу из базы данных
        try:
            task = Task.get(Task.id == task_id)
            if not task.message_id:
                logger.warning(f"Задача {task_id} не связана с сообщением")
                return

            message_obj = task.message_id

            # Отправляем ответ пользователю
            await bot.send_message(
                chat_id=message_obj.user_id, text=f"Ответ ИИ: {result}"
            )

            # Помечаем задачу как отправленную
            task.status = "sent"
            task.save()

            logger.info(
                f"Отправлен ответ пользователю {message_obj.user_id} для задачи {task_id}"
            )

        except DoesNotExist:
            logger.error(f"Задача {task_id} не найдена в базе данных")

        db.close()

    except Exception as e:
        logger.error(f"Ошибка при обработке завершения задачи: {e}")


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
