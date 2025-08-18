"""Database operations package."""

from .user import (
    get_or_create_user,
    upgrade_user_plan,
    reset_daily_counters_if_needed,
    check_user_can_create_task,
)

from .rate_limit import (
    check_rate_limit,
)

from .queue import (
    add_task_to_queue,
    update_queue_positions,
    get_next_task_from_queue,
)

from .task_statistics import (
    get_or_create_task_statistics,
    update_task_statistics,
)

from .task import (
    create_user_task_with_queue,
    get_user_tasks,
    update_user_task_status,
    update_user_task_status_for_user,
    deactivate_user_tasks,
    list_active_user_tasks,
    get_most_recent_active_user_task,
    list_user_tasks,
)

from .search import (
    list_active_queries_for_task,
    create_search_query,
    update_search_query_stats,
    record_finding,
)

from .legacy import (
    get_user_settings,
    get_or_create_user_settings,
    update_user_settings,
    deactivate_user_topics,
    create_research_topic,
    get_active_topic_by_user,
    list_active_topics,
    get_topic_by_user_and_text,
)

from .paper import (
    get_arxiv_paper_by_arxiv_id,
    create_arxiv_paper,
    has_paper_analysis,
    create_paper_analysis,
    list_new_analyses_since,
    get_analysis_with_entities,
    mark_analysis_notified,
    mark_analysis_queued,
)

from .agent import (
    update_agent_status,
    get_agent_status,
    count_analyses_for_user,
    count_relevant_analyses_for_user,
    list_recent_analyses_for_user,
    swap_user_active_topics,
)

from .generic_task import (
    create_task,
    list_pending_tasks,
    mark_task_completed,
    mark_task_failed,
    list_completed_tasks_since,
    mark_task_sent,
    get_task,
)

from .integration import (
    get_next_queued_task,
    start_task_processing,
    complete_task_processing,
    create_research_topic_for_user_task,
    link_analysis_to_user_task,
    get_user_task_results,
    create_user_task,
)

__all__ = [
    # User operations
    "get_or_create_user",
    "upgrade_user_plan",
    "reset_daily_counters_if_needed",
    "check_user_can_create_task",
    # Rate limit operations
    "check_rate_limit",
    # Queue operations
    "add_task_to_queue",
    "update_queue_positions",
    "get_next_task_from_queue",
    # Task statistics operations
    "get_or_create_task_statistics",
    "update_task_statistics",
    # Task operations
    "create_user_task_with_queue",
    "get_user_tasks",
    "update_user_task_status",
    "update_user_task_status_for_user",
    "deactivate_user_tasks",
    "list_active_user_tasks",
    "get_most_recent_active_user_task",
    "list_user_tasks",
    # Search operations
    "list_active_queries_for_task",
    "create_search_query",
    "update_search_query_stats",
    "record_finding",
    # Legacy operations
    "get_user_settings",
    "get_or_create_user_settings",
    "update_user_settings",
    "deactivate_user_topics",
    "create_research_topic",
    "get_active_topic_by_user",
    "list_active_topics",
    "get_topic_by_user_and_text",
    # Paper operations
    "get_arxiv_paper_by_arxiv_id",
    "create_arxiv_paper",
    "has_paper_analysis",
    "create_paper_analysis",
    "list_new_analyses_since",
    "get_analysis_with_entities",
    "mark_analysis_notified",
    "mark_analysis_queued",
    # Agent operations
    "update_agent_status",
    "get_agent_status",
    "count_analyses_for_user",
    "count_relevant_analyses_for_user",
    "list_recent_analyses_for_user",
    "swap_user_active_topics",
    # Generic task operations
    "create_task",
    "list_pending_tasks",
    "mark_task_completed",
    "mark_task_failed",
    "list_completed_tasks_since",
    "mark_task_sent",
    "get_task",
    # Integration operations
    "get_next_queued_task",
    "start_task_processing",
    "complete_task_processing",
    "create_research_topic_for_user_task",
    "link_analysis_to_user_task",
    "get_user_task_results",
    "create_user_task",
]
