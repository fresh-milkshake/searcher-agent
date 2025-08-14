from aiogram import Router

from aiogram.filters import CommandStart, Command
from aiogram.types import Message
from aiogram.enums import ParseMode
from textwrap import dedent
from shared.logging import get_logger

router = Router(name="general")

logger = get_logger(__name__)


@router.message(CommandStart())
async def command_start_handler(message: Message) -> None:
    user_name = "user"
    if message.from_user and message.from_user.full_name:
        user_name = message.from_user.full_name

    help_text = dedent(f"""
    🔬 Hello, {user_name}! I'm your assistant that explores research sources and finds items useful for your goals.

    📌 <b>How it works</b>
    1. You create a task, for example: /task "AI for medical imaging"
    2. I search arXiv, Google Scholar, PubMed, and GitHub, evaluate relevance, and send you clear summaries.
    3. At the end of 50 search cycles, I send you a report with the most relevant and interesting items.

    📋 <b>Main commands</b>
    • /task "description" — create a new research task
    • /status — show current status of your task
    • /history — recent findings that I found interesting
    
    Also, you can add me to your group chat and I will search for you there!
    To achive this, you need to add me to the group chat and use command /set_group.
    If you want to unset group, use command /unset_group.
    
    To see all available commands, use /help.

    🧭 <b>Tip</b>
    Make your task as specific as possible, so I can find the most relevant items for you.
    """)

    await message.answer(help_text, parse_mode=ParseMode.HTML)


@router.message(Command("help"))
async def command_help_handler(message: Message) -> None:
    """Show help message"""

    help_text = dedent("""
    <b>How it works</b>
    1. You create a task, for example: /task "AI for medical imaging"
    2. I search arXiv, Google Scholar, PubMed, and GitHub, evaluate relevance, and send you clear summaries.
    3. At the end of 50 search cycles, I send you a report with the most relevant and interesting items.
    
    <b>Main commands</b>
    /task "description" — create a new research task
    /status — show current status of your task
    /history — recent findings that I found interesting
    
    <b>Group chat commands</b>
    /set_group — add me to your group chat
    /unset_group — remove me from your group chat
    
    <b>Tip</b>
    Make your task as specific as possible, so I can find the most relevant items for you.
    """)

    await message.answer(
        help_text,
        parse_mode=ParseMode.HTML,
    )
