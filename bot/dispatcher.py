import asyncio
import os
import sys
from aiogram import Bot, Dispatcher
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.db import init_db, list_completed_tasks_since
from shared.logger import get_logger
from bot.handlers import (
    general_router,
    management_router,
    settings_router,
    notifications_router,
    tasks_router,
)
from bot.handlers.notifications import (
    process_completed_task,
    check_new_analyses,
)

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not found in environment variables")

logger = get_logger(__name__)

bot = Bot(token=BOT_TOKEN)

dp = Dispatcher()
dp.include_router(management_router)
dp.include_router(settings_router)
dp.include_router(notifications_router)
dp.include_router(tasks_router)
dp.include_router(general_router)


async def main() -> None:
    logger.info("Starting Telegram bot...")

    await init_db()
    logger.info("Database initialized for bot")

    # Start background task to check for new analyses
    logger.info("Starting background analysis checker...")
    asyncio.create_task(check_new_analyses(bot))
    logger.info("Background analysis checker started")

    logger.info("Telegram bot ready to work")

    # Start background task to process completed tasks (DB polling)
    async def check_completed_tasks():
        last_checked_id = 0
        while True:
            try:
                tasks = await list_completed_tasks_since(last_checked_id)
                for task in tasks:
                    await process_completed_task(bot, task)
                    last_checked_id = max(last_checked_id, task.id)
                await asyncio.sleep(2)
            except Exception as e:
                logger.error(f"Error in completed tasks checker: {e}")
                await asyncio.sleep(5)

    asyncio.create_task(check_completed_tasks())

    # Start the bot
    logger.info("Starting bot polling...")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
