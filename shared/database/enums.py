"""Database enums and constants."""

from enum import Enum


class UserPlan(str, Enum):
    """User subscription plan types."""

    FREE = "free"
    PREMIUM = "premium"


class TaskStatus(str, Enum):
    """Task status types."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    PAUSED = "paused"
    ACTIVE = "active"  # Legacy compatibility
