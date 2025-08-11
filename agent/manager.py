"""Autonomous agent manager loop.

Polls active user tasks, runs a single pipeline iteration per task, persists
results (unless dry-run), and triggers Telegram notifications via DB tasks.
"""

import asyncio
import json
import os
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from shared.logger import get_logger
from shared.db import (
    UserSettings,
    UserTask,
    create_arxiv_paper,
    create_paper_analysis,
    create_task,
    get_user_settings,
    list_active_user_tasks,
    update_agent_status,
    get_arxiv_paper_by_arxiv_id,
)

from agent.pipeline.pipeline import run_pipeline
from agent.pipeline.models import PipelineOutput, PipelineTask


logger = get_logger(__name__)


@dataclass
class RuntimeConfig:
    poll_seconds: int = 30
    dry_run: bool = False
    agent_id: str = "main_agent"
    test_user_id: Optional[int] = None


def _read_config() -> RuntimeConfig:
    """Load runtime config from environment variables."""
    poll = int(os.getenv("AGENT_POLL_SECONDS", "30"))
    dry = os.getenv("AGENT_DRY_RUN", "0").lower() in {"1", "true", "yes"}
    agent_id = os.getenv("AGENT_ID", "main_agent")
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
    *, user_task: UserTask, settings: Optional[UserSettings]
) -> PipelineTask:
    """Convert DB `UserTask` into a `PipelineTask` for the pipeline."""
    query = (user_task.description or user_task.title or "").strip()
    min_rel = float(getattr(settings, "min_relevance", 50.0)) if settings else 50.0
    return PipelineTask(query=query, min_relevance=min_rel)


async def _persist_selected(
    output: PipelineOutput, *, user_id: int
) -> List[Tuple[int, int]]:
    """Persist selected items into DB: ensure paper and create analysis.

    Returns list of (analysis_id, paper_id).
    """
    saved: List[Tuple[int, int]] = []
    for s in output.selected:
        c = s.result.candidate
        # Ensure paper exists
        existing = await get_arxiv_paper_by_arxiv_id(c.arxiv_id)
        if existing is None:
            paper = await create_arxiv_paper(
                {
                    "arxiv_id": c.arxiv_id,
                    "title": c.title,
                    "authors": json.dumps([]),  # unknown authors here
                    "summary": c.summary,
                    "categories": json.dumps(c.categories or []),
                    "published": c.published or c.updated,
                    "updated": c.updated or c.published,
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
            topic_id=0,  # topic not used for UserTask; keep 0 or make a dedicated mapping
            relevance=float(s.overall_score),
            summary=s.result.summary,
            key_fragments=s.result.key_fragments,
            contextual_reasoning=s.result.contextual_reasoning,
        )
        saved.append((analysis.id, paper.id))
    return saved


async def _notify_report(user_id: int, report_text: str) -> None:
    """Create a completed Task row that the bot will pick up and send to the user."""
    data = {"task_type": "agent_report", "user_id": user_id}
    logger.info(f"Enqueuing completed agent_report for user {user_id}")
    await create_task(
        task_type="agent_report", data=data, status="completed", result=report_text
    )


async def _process_user_task(rt: RuntimeConfig, user_task: UserTask) -> None:
    settings = await get_user_settings(user_task.user_id)
    pipeline_task = _build_pipeline_task(user_task=user_task, settings=settings)

    await update_agent_status(
        agent_id=rt.agent_id,
        status="running",
        activity=f"processing user task {user_task.id}",
        current_user_id=user_task.user_id,
    )

    output: PipelineOutput = await run_pipeline(pipeline_task)

    if output.should_notify and output.report_text:
        # Dry-run: send report without persisting analyses
        target_user = rt.test_user_id or user_task.user_id
        await _notify_report(target_user, output.report_text)

    if not rt.dry_run and output.selected:
        try:
            await _persist_selected(output, user_id=user_task.user_id)
        except Exception as e:
            logger.error(f"Persist selected failed for task {user_task.id}: {e}")

    await update_agent_status(
        agent_id=rt.agent_id,
        status="idle",
        activity="waiting",
        current_user_id=None,
    )


async def main() -> None:
    """Agent main loop: poll tasks and process them autonomously."""
    cfg = _read_config()
    logger.info(
        f"Agent starting (poll={cfg.poll_seconds}s, dry_run={'yes' if cfg.dry_run else 'no'}, agent_id={cfg.agent_id})"
    )

    # Simple change detection by content hash
    last_fingerprint: Dict[int, str] = {}

    while True:
        try:
            tasks = await list_active_user_tasks()
            if not tasks:
                await update_agent_status(
                    agent_id=cfg.agent_id,
                    status="idle",
                    activity="waiting",
                )
            for t in tasks:
                text = f"{t.title}\n{t.description}".strip()
                if last_fingerprint.get(t.id) != text:
                    logger.info(f"Detected new/changed task {t.id}; running iteration")
                    await _process_user_task(cfg, t)
                    last_fingerprint[t.id] = text
                else:
                    # Periodic exploration — run anyway on a schedule
                    await _process_user_task(cfg, t)
            await asyncio.sleep(cfg.poll_seconds)
        except Exception as loop_error:
            logger.error(f"Agent loop error: {loop_error}")
            await asyncio.sleep(min(60, cfg.poll_seconds))
