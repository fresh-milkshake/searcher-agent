"""Autonomous agent manager loop.

Polls active user tasks, runs a single pipeline iteration per task, persists
results (unless dry-run), and triggers Telegram notifications via DB tasks.
"""

import asyncio
from datetime import datetime
import json
import os
from dataclasses import dataclass
from typing import List, Optional, Tuple

from shared.logging import get_logger
from shared.db import (
    UserSettings,
    UserTask,
    create_arxiv_paper,
    create_paper_analysis,
    create_task,
    get_user_settings,
    list_active_queries_for_task,
    update_agent_status,
    get_arxiv_paper_by_arxiv_id,
    # Integration functions
    get_next_queued_task,
    start_task_processing,
    complete_task_processing,
    create_research_topic_for_user_task,
    link_analysis_to_user_task,
    cleanup_orphaned_queue_entries,
)

from agent.pipeline.pipeline import run_pipeline
from agent.pipeline.models import PipelineOutput, PipelineTask


logger = get_logger(__name__)


@dataclass
class RuntimeConfig:
    """In-memory configuration for the agent manager.

    :ivar poll_seconds: Poll interval in seconds for the main loop.
    :ivar dry_run: If ``True``, do not persist analyses; only notify.
    :ivar agent_id: Identifier reported in status updates.
    :ivar test_user_id: Optional override to send notifications to a test user.
    """

    poll_seconds: int = 10
    dry_run: bool = False
    agent_id: str = "main_agent"
    test_user_id: Optional[int] = None


def _read_config() -> RuntimeConfig:
    """Load runtime config from environment variables.

    :returns: A populated :class:`RuntimeConfig` instance.
    """
    try:
        poll = int(os.getenv("AGENT_POLL_SECONDS", "10"))
        dry = os.getenv("AGENT_DRY_RUN", "0").lower() in {"1", "true", "yes"}
        agent_id = os.getenv("AGENT_ID", "main_agent")
    except Exception as e:
        logger.error(f"Error reading config: {e}")
        poll = 10
        dry = False
        agent_id = "main_agent"

    test_uid: Optional[int] = None
    if os.getenv("AGENT_TEST_USER_ID"):
        try:
            test_uid = int(os.getenv("AGENT_TEST_USER_ID", "").strip())
        except Exception:
            test_uid = None
    return RuntimeConfig(
        poll_seconds=poll, dry_run=dry, agent_id=agent_id, test_user_id=test_uid
    )


def _build_pipeline_task(
    *,
    user_task: UserTask,
    settings: Optional[UserSettings],
    explicit_queries: Optional[List[str]] = None,
) -> PipelineTask:
    """Convert DB ``UserTask`` into a :class:`PipelineTask` for the pipeline.

    Tries to extract optional fields (``queries``, ``categories``) from the task
    description if it contains JSON.

    :param user_task: Source task from the database.
    :param settings: Per-user settings influencing thresholds.
    :param explicit_queries: Optional explicit queries associated with the task.
    :returns: A :class:`PipelineTask` ready for execution.
    """
    raw_text = (user_task.description or user_task.title or "").strip()
    min_rel = float(getattr(settings, "min_relevance", 50.0)) if settings else 50.0

    queries: Optional[List[str]] = explicit_queries if explicit_queries else None
    categories: Optional[List[str]] = None
    query_text: str = raw_text

    # Attempt to parse JSON payloads in description for advanced control
    try:
        data = json.loads(raw_text)
        if isinstance(data, dict):
            if isinstance(data.get("query"), str):
                query_text = data["query"].strip()
            if isinstance(data.get("queries"), list):
                queries = [str(x) for x in data["queries"] if str(x).strip()]
            if isinstance(data.get("categories"), list):
                categories = [str(x) for x in data["categories"] if str(x).strip()]
    except Exception:
        # Not JSON, use raw text
        pass

    return PipelineTask(
        query=query_text,
        min_relevance=min_rel,
        queries=queries,
        categories=categories,
    )


async def _persist_selected(
    output: PipelineOutput, *, user_task: UserTask, topic_id: int = 0
) -> List[Tuple[int, int]]:
    """Persist selected items into DB: ensure paper and create analysis.

    :param output: Pipeline output with selected items.
    :param user_task: The UserTask instance for proper integration.
    :param topic_id: Research topic ID for legacy compatibility.
    :returns: List of ``(analysis_id, paper_id)`` pairs.
    """
    saved: List[Tuple[int, int]] = []
    for s in output.selected:
        c = s.result.candidate
        # Ensure paper exists
        existing = await get_arxiv_paper_by_arxiv_id(c.arxiv_id)
        if existing is None:
            # Fallbacks for non-arXiv items that may lack timestamps
            published_ts: datetime = c.published or c.updated or datetime.now()
            updated_ts: datetime = c.updated or c.published or published_ts
            paper = await create_arxiv_paper(
                {
                    "arxiv_id": c.arxiv_id,
                    "title": c.title,
                    "authors": json.dumps([]),  # unknown authors here
                    "summary": c.summary,
                    "categories": json.dumps(c.categories or []),
                    "published": published_ts,
                    "updated": updated_ts,
                    "pdf_url": c.pdf_url or "",
                    "abs_url": c.abs_url or "",
                    "journal_ref": c.journal_ref,
                    "doi": c.doi,
                    "comment": c.comment,
                    "primary_category": c.primary_category,
                }
            )
        else:
            paper = existing

        # Create analysis row
        analysis = await create_paper_analysis(
            paper_id=paper.id,
            topic_id=topic_id,
            relevance=float(s.overall_score),
            summary=s.result.summary,
            key_fragments=s.result.key_fragments,
            contextual_reasoning=s.result.contextual_reasoning,
        )

        # Link analysis to user task through Finding
        await link_analysis_to_user_task(analysis, user_task)

        saved.append((analysis.id, paper.id))
    return saved


async def _notify_report(user_id: int, report_text: str) -> None:
    """Create a completed Task row that the bot will pick up and send to the user.

    :param user_id: Telegram or internal user identifier.
    :param report_text: Plain-text report to be delivered.
    :returns: ``None``.
    """
    data = {"task_type": "agent_report", "user_id": user_id}
    logger.info(f"Enqueuing completed agent_report for user {user_id}")
    await create_task(
        task_type="agent_report", data=data, status="completed", result=report_text
    )


async def _process_user_task(rt: RuntimeConfig, user_task: UserTask) -> None:
    """Process one user task: run pipeline, persist, and notify if needed.

    :param rt: Runtime configuration.
    :param user_task: Task pulled from the database queue.
    :returns: ``None``.
    """
    task_success = False
    error_message = None

    try:
        # Start task processing
        if not await start_task_processing(user_task.id):
            logger.error(f"Failed to start processing task {user_task.id}")
            return

        # Create research topic for legacy compatibility
        research_topic = await create_research_topic_for_user_task(user_task)
        if research_topic is None:
            logger.error(f"Failed to create research topic for task {user_task.id}")
            await complete_task_processing(
                user_task.id, False, "Failed to create research topic"
            )
            return

        # Get user settings (using telegram_id for legacy compatibility)
        settings = await get_user_settings(research_topic.user_id)

        # Load explicit queries if configured for the task
        explicit_queries: Optional[List[str]] = None
        try:
            active_queries = await list_active_queries_for_task(user_task.id)
            if active_queries:
                explicit_queries = [
                    q.query_text for q in active_queries if q.query_text
                ]
        except Exception:
            explicit_queries = None

        pipeline_task = _build_pipeline_task(
            user_task=user_task, settings=settings, explicit_queries=explicit_queries
        )

        await update_agent_status(
            agent_id=rt.agent_id,
            status="running",
            activity=f"processing user task {user_task.id}",
            current_user_id=research_topic.user_id,  # Use telegram_id for status
        )

        logger.info(
            f"Running pipeline for task {user_task.id}: {user_task.description[:50]}..."
        )
        output: PipelineOutput = await run_pipeline(pipeline_task)

        # Handle notifications
        if output.should_notify and output.report_text:
            target_user = rt.test_user_id or research_topic.user_id
            await _notify_report(target_user, output.report_text)

        # Persist results if not dry run
        if not rt.dry_run and output.selected:
            try:
                await _persist_selected(
                    output, user_task=user_task, topic_id=research_topic.id
                )
                logger.info(
                    f"Persisted {len(output.selected)} results for task {user_task.id}"
                )
            except Exception as e:
                logger.error(f"Persist selected failed for task {user_task.id}: {e}")
                error_message = f"Failed to persist results: {str(e)}"
                raise

        task_success = True
        logger.info(f"Successfully completed task {user_task.id}")

    except Exception as e:
        logger.error(f"Error processing task {user_task.id}: {e}")
        error_message = str(e)
        task_success = False

    finally:
        # Complete task processing and update status
        await complete_task_processing(user_task.id, task_success, error_message)

        await update_agent_status(
            agent_id=rt.agent_id,
            status="idle",
            activity="waiting",
            current_user_id=None,
        )


async def main() -> None:
    """Agent main loop: poll tasks and process them autonomously.

    :returns: ``None``.
    """
    cfg = _read_config()
    logger.info(
        f"Agent starting (poll={cfg.poll_seconds}s, dry_run={'yes' if cfg.dry_run else 'no'}, agent_id={cfg.agent_id})"
    )

    # Clean up orphaned queue entries on startup
    try:
        cleaned_count = await cleanup_orphaned_queue_entries()
        if cleaned_count > 0:
            logger.info(f"Cleaned up {cleaned_count} orphaned queue entries on startup")
    except Exception as cleanup_error:
        logger.error(f"Failed to clean up orphaned queue entries: {cleanup_error}")

    while True:
        try:
            # Get next task from queue (QUEUED status)
            task = await get_next_queued_task()
            if not task:
                await update_agent_status(
                    agent_id=cfg.agent_id,
                    status="idle",
                    activity="waiting for queued tasks",
                )
                await asyncio.sleep(cfg.poll_seconds)
                continue

            # Process the next queued task
            logger.info(f"Processing queued task {task.id}: {task.description[:50]}...")
            await _process_user_task(cfg, task)

            # Brief pause between tasks to allow for proper status updates (reduced delay)
            await asyncio.sleep(0.1)

        except Exception as loop_error:
            logger.error(f"Agent loop error: {loop_error}")
            await update_agent_status(
                agent_id=cfg.agent_id,
                status="error",
                activity=f"error: {str(loop_error)[:100]}",
            )
            await asyncio.sleep(min(60, cfg.poll_seconds))
