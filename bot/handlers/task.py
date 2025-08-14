from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.enums import ParseMode
import re
from textwrap import dedent

from shared.db import (
    ensure_connection,
    create_user_task,
    get_user_tasks,
    update_user_task_status_for_user,
)
from shared.logging import get_logger


router = Router(name="tasks")
logger = get_logger(__name__)


@router.message(Command("task"))
async def command_create_task(message: Message) -> None:
    """Create a new autonomous search task: /task "Title" description"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        text = message.text or ""

        m = re.match(r"/task\s+\"([^\"]+)\"\s*(.*)$", text, re.DOTALL)
        if not m:
            await message.answer(
                dedent(
                    """
                    ❌ Invalid format

                    ✅ Correct format:
                    /task "Short title" Brief description of your goal
                    """
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        title = m.group(1).strip()
        description = (m.group(2) or "").strip() or title

        ensure_connection()
        task = await create_user_task(user_id, title, description)

        await message.answer(
            dedent(
                f"""
                ✅ Task created

                Title: <b>{title}</b>
                The assistant will now start exploring arXiv and send you useful findings.
                """
            ),
            parse_mode=ParseMode.HTML,
        )

        logger.info(f"User {user_id} created task {task.id}: {title}")

    except Exception as error:
        logger.error(f"Error in /task command: {error}")
        await message.answer("❌ An error occurred while creating a task.")


@router.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """Show current monitoring status"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id  # noqa: F841

        # TODO: get status of the task from database and show it

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        await message.answer(
            "❌ An error occurred while getting status. Try again in a few minutes."
        )


@router.message(Command("history"))
async def command_history_handler(message: Message) -> None:
    """Show recent found topic intersections"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id  # noqa: F841

        # TODO: get last 5 relevant analyses from database and show them

    except Exception as e:
        logger.error(f"Error in /history command: {e}")
        await message.answer("❌ An error occurred while getting history.")
