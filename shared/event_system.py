"""Compatibility facade for events.

Subscriptions are removed by design. The app uses DB polling (see Task table)
for coordination between components.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, Optional

from .logging import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Event types used for high-level coordination."""

    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MESSAGE_RECEIVED = "message_received"
    RESPONSE_READY = "response_ready"


@dataclass
class Event:
    """Simple event record used by the compatibility facade.

    :ivar event_type: Category of the event.
    :ivar data: Optional payload with event-specific fields.
    :ivar created_at: Creation timestamp.
    """

    event_type: EventType
    data: Optional[Dict[str, Any]] = None
    created_at: datetime = field(default_factory=datetime.now)
