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
from shared.logger import get_logger


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


@router.message(Command("status_task"))
async def command_status_task(message: Message) -> None:
    """Show user's tasks and their status"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return

        user_id = message.from_user.id
        ensure_connection()
        tasks = await get_user_tasks(user_id)
        if not tasks:
            await message.answer(
                'ℹ️ You have no tasks yet. Create one with /task "Title" description.'
            )
            return
        text = "<b>Your tasks:</b>\n\n"
        for t in tasks[:10]:
            text += f"• <b>{t.title}</b> — {t.status}\n"
        await message.answer(text, parse_mode=ParseMode.HTML)
    except Exception as error:
        logger.error(f"Error in /status_task: {error}")
        await message.answer("❌ An error occurred while getting task status.")


@router.message(Command("pause_task"))
async def command_pause_task(message: Message) -> None:
    """Pause a task by id: /pause_task <task_id>"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return
        parts = (message.text or "").split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Usage: /pause_task <task_id>")
            return
        task_id = int(parts[1])
        ensure_connection()
        if await update_user_task_status_for_user(
            message.from_user.id, task_id, "paused"
        ):
            await message.answer(f"⏸️ Task {task_id} paused")
        else:
            await message.answer("❌ Task not found or not yours")
    except Exception as error:
        logger.error(f"Error in /pause_task: {error}")
        await message.answer("❌ An error occurred while pausing task.")


@router.message(Command("resume_task"))
async def command_resume_task(message: Message) -> None:
    """Resume a task by id: /resume_task <task_id>"""
    try:
        if not message.from_user:
            await message.answer("Error: could not determine user.")
            return
        parts = (message.text or "").split()
        if len(parts) < 2 or not parts[1].isdigit():
            await message.answer("Usage: /resume_task <task_id>")
            return
        task_id = int(parts[1])
        ensure_connection()
        if await update_user_task_status_for_user(
            message.from_user.id, task_id, "active"
        ):
            await message.answer(f"▶️ Task {task_id} resumed")
        else:
            await message.answer("❌ Task not found or not yours")
    except Exception as error:
        logger.error(f"Error in /resume_task: {error}")
        await message.answer("❌ An error occurred while resuming task.")
