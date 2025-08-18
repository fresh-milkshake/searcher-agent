from aiogram import Router, F
from aiogram.filters import Command, StateFilter
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    CallbackQuery,
)


from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
import re
from textwrap import dedent
from datetime import datetime

from bot.utils import cut_text, escape_html
from shared.db import (
    get_or_create_user,
    get_user_tasks,
    create_user_task_with_queue,
    check_user_can_create_task,
    check_rate_limit,
    get_or_create_task_statistics,
    list_recent_analyses_for_user,
    update_queue_positions,
    UserPlan,
    TaskStatus,
    # Integration functions
    get_user_task_results,
)
from shared.logging import get_logger


router = Router(name="tasks")
logger = get_logger(__name__)


class TaskCreationStates(StatesGroup):
    """States for task creation flow."""

    waiting_for_description = State()


def format_time_estimate(seconds: float) -> str:
    """Format time estimate in human readable format.

    :param seconds: Time in seconds
    :returns: Formatted time string
    """
    if seconds < 60:
        return f"{int(seconds)}s"
    elif seconds < 3600:
        return f"{int(seconds // 60)}m {int(seconds % 60)}s"
    else:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours}h {minutes}m"


def get_plan_display_name(plan: UserPlan) -> str:
    """Get display name for user plan.

    :param plan: User plan enum
    :returns: Display name
    """
    return "🆓 Free" if plan == UserPlan.FREE else "⭐ Premium"


def get_status_emoji(status) -> str:
    """Get emoji for task status.

    :param status: Task status (enum or string)
    :returns: Emoji string
    """
    # Handle enum by getting its value
    if hasattr(status, "value"):
        status_str = status.value.lower()
    else:
        status_str = str(status).lower()

    return {
        "queued": "⏳",
        "processing": "🔄",
        "completed": "✅",
        "failed": "❌",
        "cancelled": "🚫",
        "paused": "⏸️",
        "active": "🔄",
    }.get(status_str, "❓")


async def rate_limit_check(message: Message, action_type: str) -> bool:
    """Check rate limits for user action and send error message if exceeded.

    :param message: Telegram message
    :param action_type: Type of action being performed
    :returns: True if allowed, False if rate limited
    """
    if not message.from_user:
        return False

    user = await get_or_create_user(message.from_user.id)
    allowed, reason = await check_rate_limit(user.id, action_type)

    if not allowed:
        await message.answer(
            f"🚫 <b>Rate limit exceeded!</b>\n\n{escape_html(reason)}\n\n"
            "Please wait before trying again.",
            parse_mode=ParseMode.HTML,
        )
        logger.warning(f"Rate limit exceeded for user {user.telegram_id}: {reason}")

    return allowed


@router.message(Command("task"))
async def command_create_task(message: Message, state: FSMContext) -> None:
    """Create a new autonomous search task: /task <description> or /task to start interactive mode."""
    try:
        if not message.from_user:
            await message.answer("❌ Error: could not determine user.")
            return

        # Rate limiting check
        if not await rate_limit_check(message, "task_create"):
            return

        user = await get_or_create_user(
            telegram_id=message.from_user.id,
            username=message.from_user.username,
            first_name=message.from_user.first_name,
            last_name=message.from_user.last_name,
        )

        text = message.text or ""

        # Check if description is provided directly
        m = re.match(r"/task\s+\"([^\"]+)\"\s*(.*)$", text, re.DOTALL)
        if m:
            # Direct task creation with description in quotes
            description = m.group(1).strip()
            await create_task_for_user(user, description, message)
            return

        # Check for description without quotes
        m = re.match(r"/task\s+(.+)$", text, re.DOTALL)
        if m:
            # Direct task creation with description (no quotes)
            description = m.group(1).strip()
            await create_task_for_user(user, description, message)
            return

        # No description provided - start interactive mode
        await start_interactive_task_creation(user, message, state)

    except Exception as error:
        logger.error(f"Error in /task command: {error}")
        await message.answer("❌ An error occurred while processing your request.")


async def create_task_for_user(user, description: str, message: Message) -> None:
    """Create task for user with full validation and queue management.

    :param user: User instance
    :param description: Task description
    :param message: Telegram message
    """
    # Check if user can create task
    can_create, reason = await check_user_can_create_task(user)
    if not can_create:
        await message.answer(
            f"🚫 <b>Cannot create task</b>\n\n{escape_html(reason)}",
            parse_mode=ParseMode.HTML,
        )
        return

    # Validate description
    if len(description) < 5:
        await message.answer(
            "❌ <b>Description too short</b>\n\n"
            "Please provide a description with at least 5 characters.",
            parse_mode=ParseMode.HTML,
        )
        return

    if len(description) > 1000:
        await message.answer(
            "❌ <b>Description too long</b>\n\n"
            "Please keep your description under 1000 characters.",
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        # Create task and add to queue
        task, queue_entry = await create_user_task_with_queue(user, description)

        # Get statistics for estimates
        stats = await get_or_create_task_statistics()

        # Calculate remaining slots
        user_tasks = await get_user_tasks(user.id)
        active_tasks = len(
            [t for t in user_tasks if str(t.status) in ["queued", "processing"]]
        )
        slots_left = user.concurrent_task_limit - active_tasks

        # Format estimated time
        estimated_time = format_time_estimate(
            stats.median_processing_time * queue_entry.queue_position
        )

        # Update queue positions
        await update_queue_positions()

        await message.answer(
            dedent(
                f"""
                ✅ <b>Task #{task.id} created successfully!</b>
                
                📝 <b>Description:</b> {escape_html(cut_text(description, 200))}
                
                📊 <b>Your Plan:</b> {get_plan_display_name(user.plan)}
                🎯 <b>Max Cycles:</b> {task.max_cycles}
                
                📍 <b>Queue Position:</b> #{queue_entry.queue_position}
                📈 <b>Task Slots Left:</b> {slots_left}/{user.concurrent_task_limit}
                ⏱️ <b>Estimated Start:</b> {estimated_time}
                
                🏃‍♂️ <b>Daily Tasks:</b> {user.daily_tasks_created}/{user.daily_task_limit}
                
                Use /status to check your tasks progress.
                """
            ),
            parse_mode=ParseMode.HTML,
        )

        logger.info(
            f"User {user.telegram_id} created task {task.id}: {description[:100]}"
        )

    except Exception as error:
        logger.error(f"Error creating task for user {user.telegram_id}: {error}")
        await message.answer("❌ An error occurred while creating the task.")


async def start_interactive_task_creation(
    user, message: Message, state: FSMContext
) -> None:
    """Start interactive task creation flow.

    :param user: User instance
    :param message: Telegram message
    :param state: FSM context
    """
    # Check if user can create task
    can_create, reason = await check_user_can_create_task(user)
    if not can_create:
        await message.answer(
            f"🚫 <b>Cannot create task</b>\n\n{escape_html(reason)}",
            parse_mode=ParseMode.HTML,
        )
        return

    # Create cancel keyboard
    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="❌ Cancel", callback_data="cancel_task_creation"
                )
            ]
        ]
    )

    await message.answer(
        dedent(
            f"""
            📝 <b>Create New Task</b>
            
            👋 Hi! Please send me the description for your research task.
            
            📊 <b>Your Plan:</b> {get_plan_display_name(user.plan)}
            🎯 <b>Max Cycles:</b> {100 if user.plan == UserPlan.PREMIUM else 5}
            🏃‍♂️ <b>Daily Tasks:</b> {user.daily_tasks_created}/{user.daily_task_limit}
            📈 <b>Concurrent Slots:</b> {user.concurrent_task_limit}
            
            <b>Examples:</b>
            • "Latest advances in quantum computing"
            • "Machine learning applications in healthcare"
            • "Sustainable energy storage technologies"
            
            <i>Your description should be 5-1000 characters long.</i>
            """
        ),
        reply_markup=keyboard,
        parse_mode=ParseMode.HTML,
    )

    await state.set_state(TaskCreationStates.waiting_for_description)


@router.callback_query(F.data == "cancel_task_creation")
async def cancel_task_creation(callback: CallbackQuery, state: FSMContext) -> None:
    """Cancel task creation process."""
    await state.clear()
    try:
        if callback.message:
            await callback.message.edit_text(  # type: ignore
                "❌ <b>Task creation cancelled</b>", parse_mode=ParseMode.HTML
            )
    except Exception:
        pass  # Message might be inaccessible
    await callback.answer()


@router.message(StateFilter(TaskCreationStates.waiting_for_description))
async def process_task_description(message: Message, state: FSMContext) -> None:
    """Process task description in interactive mode."""
    if not message.from_user or not message.text:
        await message.answer("❌ Please send a text description.")
        return

    description = message.text.strip()

    user = await get_or_create_user(message.from_user.id)
    await create_task_for_user(user, description, message)
    await state.clear()


@router.message(Command("status"))
async def command_status_handler(message: Message) -> None:
    """Show current task status with enhanced information."""
    try:
        if not message.from_user:
            await message.answer("❌ Error: could not determine user.")
            return

        # Rate limiting check
        if not await rate_limit_check(message, "command"):
            return

        user = await get_or_create_user(message.from_user.id)
        user_tasks = await get_user_tasks(user.id)

        if not user_tasks:
            await message.answer(
                dedent(
                    f"""
                    ⚠️ <b>No tasks found!</b>
                    
                    📊 <b>Your Plan:</b> {get_plan_display_name(user.plan)}
                    🏃‍♂️ <b>Daily Tasks:</b> {user.daily_tasks_created}/{user.daily_task_limit}
                    📈 <b>Concurrent Slots:</b> {user.concurrent_task_limit}
                    
                    To create a new task, use:
                    <code>/task "your research description"</code>
                    
                    Or simply type <code>/task</code> for interactive mode.
                    """
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        # Group tasks by status
        active_tasks = [
            t
            for t in user_tasks
            if t.status in [TaskStatus.QUEUED, TaskStatus.PROCESSING]
        ]
        completed_tasks = [t for t in user_tasks if t.status == TaskStatus.COMPLETED]
        failed_tasks = [t for t in user_tasks if t.status == TaskStatus.FAILED]
        other_tasks = [
            t
            for t in user_tasks
            if t.status
            not in [
                TaskStatus.QUEUED,
                TaskStatus.PROCESSING,
                TaskStatus.COMPLETED,
                TaskStatus.FAILED,
            ]
        ]

        status_text = dedent(
            f"""
            📊 <b>Task Status Dashboard</b>
            
            👤 <b>User:</b> {escape_html(user.first_name or "User")} ({get_plan_display_name(user.plan)})
            🏃‍♂️ <b>Daily Usage:</b> {user.daily_tasks_created}/{user.daily_task_limit}
            📈 <b>Active Slots:</b> {len(active_tasks)}/{user.concurrent_task_limit}
            """
        )

        # Show active tasks
        if active_tasks:
            status_text += "\n🔄 <b>Active Tasks:</b>\n"
            for task in active_tasks[:5]:  # Show max 5 active tasks
                emoji = get_status_emoji(task.status)
                cycles = f"{task.cycles_completed}/{task.max_cycles}"
                status_text += f"{emoji} <b>#{task.id}</b> {escape_html(cut_text(task.description, 40))}\n"
                status_text += f"   Cycles: {cycles} | Status: {task.status}\n"

                # Show queue information if available through eager loading
                if hasattr(task, "queue_entry") and task.queue_entry:
                    try:
                        if task.queue_entry.queue_position:
                            status_text += f"   Queue position: #{task.queue_entry.queue_position}\n"
                        if task.queue_entry.estimated_start_time:
                            est_time = (
                                task.queue_entry.estimated_start_time - datetime.now()
                            )
                            if est_time.total_seconds() > 0:
                                status_text += f"   Est. start: {format_time_estimate(est_time.total_seconds())}\n"
                            else:
                                status_text += "   Est. start: Now\n"
                    except Exception:
                        # Skip queue info if not available
                        pass
                status_text += "\n"

        # Show completed tasks summary
        if completed_tasks:
            recent_completed = sorted(
                completed_tasks,
                key=lambda t: t.updated_at or datetime.now(),
                reverse=True,
            )[:3]
            status_text += (
                f"\n✅ <b>Recent Completed ({len(completed_tasks)} total):</b>\n"
            )
            for task in recent_completed:
                status_text += f"✅ <b>#{task.id}</b> {escape_html(cut_text(task.description, 40))}\n"
                status_text += (
                    f"   Cycles: {task.cycles_completed}/{task.max_cycles}\n\n"
                )

        # Show failed tasks if any
        if failed_tasks:
            status_text += f"\n❌ <b>Failed Tasks:</b> {len(failed_tasks)}\n"

        # Show other tasks if any
        if other_tasks:
            status_text += f"\n⏸️ <b>Other Tasks:</b> {len(other_tasks)}\n"

        # Add footer with commands
        status_text += dedent(
            """
            
            📚 <b>Commands:</b>
            /history - View task results
            /task - Create new task
            """
        )

        await message.answer(status_text, parse_mode=ParseMode.HTML)

    except Exception as e:
        logger.error(f"Error in /status command: {e}")
        await message.answer("❌ An error occurred while getting status.")


@router.message(Command("history"))
async def command_history_handler(message: Message) -> None:
    """Show task history with selection and pagination."""
    try:
        if not message.from_user:
            await message.answer("❌ Error: could not determine user.")
            return

        # Rate limiting check
        if not await rate_limit_check(message, "command"):
            return

        user = await get_or_create_user(message.from_user.id)
        user_tasks = await get_user_tasks(user.id)

        if not user_tasks:
            await message.answer(
                dedent(
                    """
                    ⚠️ <b>No tasks found!</b>
                    
                    Create your first task to see results here:
                    <code>/task "your research description"</code>
                    """
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        # Filter tasks that have completed or are active
        relevant_tasks = [
            t
            for t in user_tasks
            if t.status
            in [TaskStatus.COMPLETED, TaskStatus.PROCESSING, TaskStatus.FAILED]
        ]

        if not relevant_tasks:
            await message.answer(
                dedent(
                    """
                    ⚠️ <b>No completed tasks found!</b>
                    
                    Your tasks are still processing or haven't started yet.
                    Use /status to check current progress.
                    """
                ),
                parse_mode=ParseMode.HTML,
            )
            return

        # Create task selection keyboard
        keyboard_buttons = []
        for task in relevant_tasks[:10]:  # Show max 10 tasks
            emoji = get_status_emoji(task.status)
            button_text = f"{emoji} #{task.id}: {cut_text(task.description, 25)}"
            callback_data = f"history_task_{task.id}"
            keyboard_buttons.append(
                [InlineKeyboardButton(text=button_text, callback_data=callback_data)]
            )

        # Add recent analyses option
        keyboard_buttons.append(
            [
                InlineKeyboardButton(
                    text="📊 Recent Analyses (All Tasks)",
                    callback_data="history_recent_all",
                )
            ]
        )

        keyboard = InlineKeyboardMarkup(inline_keyboard=keyboard_buttons)

        await message.answer(
            dedent(
                f"""
                📚 <b>Task History</b>
                
                Select a task to view its detailed results:
                
                📊 <b>Your Stats:</b>
                • Total tasks: {len(user_tasks)}
                • Completed: {len([t for t in user_tasks if t.status == TaskStatus.COMPLETED])}
                • Processing: {len([t for t in user_tasks if t.status == TaskStatus.PROCESSING])}
                • Failed: {len([t for t in user_tasks if t.status == TaskStatus.FAILED])}
                """
            ),
            reply_markup=keyboard,
            parse_mode=ParseMode.HTML,
        )

    except Exception as e:
        logger.error(f"Error in /history command: {e}")
        await message.answer("❌ An error occurred while getting history.")


@router.callback_query(F.data.startswith("history_task_"))
async def show_task_history(callback: CallbackQuery) -> None:
    """Show detailed history for a specific task."""
    try:
        if not callback.data:
            await callback.answer("❌ Invalid callback data.")
            return
        task_id = int(callback.data.split("_")[-1])

        if not callback.from_user:
            await callback.answer("❌ Error: could not determine user.")
            return

        user = await get_or_create_user(callback.from_user.id)
        user_tasks = await get_user_tasks(user.id)

        # Find the requested task and verify ownership
        task = next((t for t in user_tasks if t.id == task_id), None)
        if not task:
            await callback.answer("❌ Task not found or access denied.")
            return

        # Get analysis results for this specific task
        task_results = await get_user_task_results(task.id)
        analyses = task_results[:5]  # Limit to 5 results

        history_text = dedent(
            f"""
            📋 <b>Task #{task.id} Details</b>
            
            📝 <b>Description:</b> {escape_html(task.description)}
            📊 <b>Status:</b> {get_status_emoji(task.status)} {task.status}
            🔄 <b>Cycles:</b> {task.cycles_completed}/{task.max_cycles}
            
            ⏰ <b>Created:</b> {task.created_at.strftime("%Y-%m-%d %H:%M")}
            """
        )

        if task.processing_started_at:
            history_text += f"🚀 <b>Started:</b> {task.processing_started_at.strftime('%Y-%m-%d %H:%M')}\n"

        if task.processing_completed_at:
            history_text += f"✅ <b>Completed:</b> {task.processing_completed_at.strftime('%Y-%m-%d %H:%M')}\n"
            if task.processing_started_at:
                duration = task.processing_completed_at - task.processing_started_at
                history_text += f"⏱️ <b>Duration:</b> {format_time_estimate(duration.total_seconds())}\n"

        if task.error_message:
            history_text += (
                f"\n❌ <b>Error:</b> {escape_html(cut_text(task.error_message, 200))}\n"
            )

        # Show recent analyses
        if analyses:
            history_text += "\n📊 <b>Recent Analysis Results:</b>\n"
            for i, (analysis, paper) in enumerate(analyses[:5], 1):
                relevance = analysis.relevance
                history_text += (
                    f"\n{i}. <b>{escape_html(cut_text(paper.title, 60))}</b>\n"
                )
                history_text += f"   📈 Relevance: {relevance:.1f}%\n"
                if analysis.summary:
                    history_text += (
                        f"   💭 {escape_html(cut_text(analysis.summary, 100))}\n"
                    )
        else:
            if task.status == TaskStatus.COMPLETED:
                history_text += "\n📊 <b>No analysis results found for this task.</b>\n"
            elif task.status == TaskStatus.PROCESSING:
                history_text += (
                    "\n🔄 <b>Task is still processing... Check back later!</b>\n"
                )
            else:
                history_text += "\n⏳ <b>No results yet - task hasn't completed.</b>\n"

        # Create navigation keyboard
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="📊 Show More Results",
                        callback_data=f"history_more_{task_id}",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Task List", callback_data="history_back"
                    )
                ],
            ]
        )

        try:
            if callback.message:
                await callback.message.edit_text(  # type: ignore
                    history_text, reply_markup=keyboard, parse_mode=ParseMode.HTML
                )
        except Exception:
            pass  # Message might be inaccessible
        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing task history: {e}")
        await callback.answer("❌ An error occurred while loading task history.")


@router.callback_query(F.data == "history_recent_all")
async def show_recent_analyses_all(callback: CallbackQuery) -> None:
    """Show recent analyses from all user tasks."""
    try:
        if not callback.from_user:
            await callback.answer("❌ Error: could not determine user.")
            return

        user = await get_or_create_user(callback.from_user.id)
        analyses = await list_recent_analyses_for_user(user.id, limit=10)

        if not analyses:
            try:
                if callback.message:
                    await callback.message.edit_text(  # type: ignore
                        dedent(
                            """
                            📊 <b>Recent Analysis Results</b>
                            
                            ⚠️ No analysis results found yet.
                            
                            Results will appear here as your tasks complete their research cycles.
                            """
                        ),
                        reply_markup=InlineKeyboardMarkup(
                            inline_keyboard=[
                                [
                                    InlineKeyboardButton(
                                        text="🔙 Back", callback_data="history_back"
                                    )
                                ]
                            ]
                        ),
                        parse_mode=ParseMode.HTML,
                    )
            except Exception:
                pass  # Message might be inaccessible
            await callback.answer()
            return

        results_text = "📊 <b>Recent Analysis Results (All Tasks)</b>\n\n"

        for i, (analysis, paper) in enumerate(analyses, 1):
            relevance = analysis.relevance
            results_text += f"{i}. <b>{escape_html(cut_text(paper.title, 60))}</b>\n"
            results_text += f"   📈 Relevance: {relevance:.1f}%\n"
            results_text += f"   📅 {analysis.created_at.strftime('%m/%d %H:%M')}\n"
            if analysis.summary:
                results_text += f"   💭 {escape_html(cut_text(analysis.summary, 80))}\n"
            results_text += "\n"

        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="🔙 Back to Task List", callback_data="history_back"
                    )
                ]
            ]
        )

        try:
            if callback.message:
                await callback.message.edit_text(  # type: ignore
                    results_text, reply_markup=keyboard, parse_mode=ParseMode.HTML
                )
        except Exception:
            pass  # Message might be inaccessible
        await callback.answer()

    except Exception as e:
        logger.error(f"Error showing recent analyses: {e}")
        await callback.answer("❌ An error occurred while loading analyses.")


@router.callback_query(F.data == "history_back")
async def history_back_to_list(callback: CallbackQuery) -> None:
    """Go back to task history list."""
    # Re-trigger the history command logic
    if callback.message and callback.from_user:
        # Create a mock message object to reuse the history handler logic
        await command_history_handler(callback.message)
    await callback.answer()
