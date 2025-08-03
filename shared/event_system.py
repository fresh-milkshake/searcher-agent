"""
Event system for more elegant interaction between services
Uses SQLite as a message queue with NOTIFY/LISTEN mechanism
"""

import asyncio
import sqlite3
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional
from dataclasses import dataclass

from .logger import get_logger

logger = get_logger(__name__)


class EventType(Enum):
    """Event types in the system"""

    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MESSAGE_RECEIVED = "message_received"
    RESPONSE_READY = "response_ready"


@dataclass
class Event:
    """Event in the system"""

    id: Optional[int] = None
    event_type: EventType = EventType.TASK_CREATED
    data: Optional[Dict[str, Any]] = None
    created_at: Optional[datetime] = None
    processed: bool = False

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.created_at is None:
            self.created_at = datetime.now()


class EventBus:
    """
    Event bus with async/await support
    Uses SQLite for persistence and inter-process communication
    """

    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.running = False
        self._init_db()

    def _init_db(self):
        """Initialize database for events"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    event_type TEXT NOT NULL,
                    data TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    processed BOOLEAN DEFAULT FALSE
                )
            """)

            # Create indexes for fast search
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_type_processed 
                ON events(event_type, processed)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_events_created_at 
                ON events(created_at)
            """)

            conn.commit()
            conn.close()

            logger.info(f"Event database initialized: {self.db_path}")

        except Exception as e:
            logger.error(f"Error initializing event database: {e}")
            raise

    def publish(self, event: Event) -> bool:
        """
        Publish event

        Args:
            event: Event to publish

        Returns:
            True if event successfully published
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            import json

            # Safe serialization - convert everything to strings if needed
            try:
                data_json = json.dumps(event.data)
            except TypeError as json_error:
                logger.warning(
                    f"Object not JSON serializable, converting to string: {json_error}"
                )
                # Convert all values to strings for safe serialization
                safe_data = {}
                if event.data is not None:
                    for key, value in event.data.items():
                        if isinstance(
                            value, (str, int, float, bool, list, dict, type(None))
                        ):
                            safe_data[key] = value
                        else:
                            safe_data[key] = str(
                                value
                            )  # Convert complex objects to string
                data_json = json.dumps(safe_data)

            cursor.execute(
                """
                INSERT INTO events (event_type, data, created_at, processed)
                VALUES (?, ?, ?, ?)
            """,
                (event.event_type.value, data_json, event.created_at, False),
            )

            event.id = cursor.lastrowid
            conn.commit()
            conn.close()

            logger.info(f"Published event {event.event_type.value} with ID {event.id}")
            return True

        except Exception as e:
            logger.error(f"Error publishing event: {e}")
            return False

    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Subscribe to event

        Args:
            event_type: Event type
            callback: Callback function
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        self.subscribers[event_type].append(callback)
        logger.info(
            f"Added subscription to event {event_type.value} (total subscribers: {len(self.subscribers[event_type])})"
        )

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """
        Unsubscribe from event

        Args:
            event_type: Event type
            callback: Callback function
        """
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
                logger.info(f"Removed subscription to event {event_type.value}")
            except ValueError:
                logger.warning(
                    f"Subscription to {event_type.value} not found for removal"
                )

    async def start_processing(self, poll_interval: float = 0.5):
        """
        Start event processing

        Args:
            poll_interval: Event polling interval in seconds
        """
        self.running = True
        logger.info("Event processing started")

        while self.running:
            try:
                await self._process_events()
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Error in event processing loop: {e}")
                await asyncio.sleep(poll_interval)

    def stop_processing(self):
        """Stop event processing"""
        self.running = False
        logger.info("Event processing stopped")

    async def _process_events(self):
        """Process unprocessed events"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)  # Increase timeout
            cursor = conn.cursor()

            # Get unprocessed events
            cursor.execute("""
                SELECT id, event_type, data, created_at
                FROM events
                WHERE processed = FALSE
                ORDER BY created_at ASC
                LIMIT 100
            """)

            events = cursor.fetchall()

            if events:
                logger.info(f"Found {len(events)} unprocessed events")

            for event_row in events:
                event_id, event_type_str, data_json, created_at = event_row

                try:
                    import json

                    event_type = EventType(event_type_str)
                    data = json.loads(data_json)

                    # Create event object
                    event = Event(
                        id=event_id,
                        event_type=event_type,
                        data=data,
                        created_at=datetime.fromisoformat(created_at)
                        if isinstance(created_at, str)
                        else created_at,
                        processed=False,
                    )

                    # Call subscribers
                    if event_type in self.subscribers and self.subscribers[event_type]:
                        logger.info(
                            f"Found {len(self.subscribers[event_type])} subscribers for event {event_type.value}"
                        )
                        for callback in self.subscribers[event_type]:
                            try:
                                logger.info(
                                    f"Calling handler for event {event_type.value} (ID: {event_id})"
                                )
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(event)
                                else:
                                    callback(event)
                                logger.info(
                                    f"Event handler {event_type.value} (ID: {event_id}) completed successfully"
                                )
                            except Exception as e:
                                logger.error(
                                    f"Error in event handler {event_type.value}: {e}"
                                )
                    else:
                        logger.warning(
                            f"No subscribers for event {event_type.value} (ID: {event_id})"
                        )

                    # Mark event as processed
                    cursor.execute(
                        """
                        UPDATE events SET processed = TRUE WHERE id = ?
                    """,
                        (event_id,),
                    )

                except Exception as e:
                    logger.error(f"Error processing event {event_id}: {e}")
                    # Mark as processed to avoid infinite loop
                    cursor.execute(
                        """
                        UPDATE events SET processed = TRUE WHERE id = ?
                    """,
                        (event_id,),
                    )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error processing events: {e}")

    def cleanup_old_events(self, days_old: int = 7):
        """
        Clean up old processed events

        Args:
            days_old: Number of days to keep events
        """
        try:
            cutoff_date = datetime.now() - timedelta(days=days_old)

            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            cursor.execute(
                """
                DELETE FROM events 
                WHERE processed = TRUE AND created_at < ?
            """,
                (cutoff_date,),
            )

            deleted_count = cursor.rowcount
            conn.commit()
            conn.close()

            if deleted_count > 0:
                logger.info(f"Deleted {deleted_count} old events")

        except Exception as e:
            logger.error(f"Error cleaning up old events: {e}")


# Global event bus instance
_event_bus = None


def get_event_bus() -> EventBus:
    """Get global event bus instance"""
    global _event_bus
    if _event_bus is None:
        # Use absolute path for all processes to share the same event database
        import os

        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        events_db_path = os.path.join(base_dir, "events.db")
        _event_bus = EventBus(db_path=events_db_path)
        logger.info(f"Created new EventBus instance with path: {events_db_path}")

        # Initialize subscribers dictionary if not exists
        if not hasattr(_event_bus, "subscribers"):
            _event_bus.subscribers = {}

    return _event_bus


class TaskEventManager:
    """Task event manager - simplified interface"""

    def __init__(self):
        self.event_bus = get_event_bus()

    def task_created(self, task_id: int, task_type: str, data: Any = None):
        """Notify about task creation"""
        logger.info(f"Creating TASK_CREATED event for task {task_id}")
        event = Event(
            event_type=EventType.TASK_CREATED,
            data={"task_id": task_id, "task_type": task_type, "data": data},
        )
        success = self.event_bus.publish(event)
        if success:
            logger.info(f"TASK_CREATED event successfully published for task {task_id}")
        else:
            logger.error(f"Error publishing TASK_CREATED event for task {task_id}")

    def task_completed(self, task_id: int, result: Any = None):
        """Notify about task completion"""
        logger.info(f"Creating TASK_COMPLETED event for task {task_id}")

        # Ensure result is string or None
        safe_result = None
        if result is not None:
            if isinstance(result, str):
                safe_result = result
            else:
                safe_result = str(result)  # Convert any object to string
                logger.warning(
                    f"Task {task_id} result converted to string: {type(result)}"
                )

        event = Event(
            event_type=EventType.TASK_COMPLETED,
            data={"task_id": task_id, "result": safe_result},
        )
        success = self.event_bus.publish(event)
        if success:
            logger.info(
                f"TASK_COMPLETED event successfully published for task {task_id}"
            )
        else:
            logger.error(f"Error publishing TASK_COMPLETED event for task {task_id}")

    def task_failed(self, task_id: int, error: str):
        """Notify about task error"""
        event = Event(
            event_type=EventType.TASK_FAILED, data={"task_id": task_id, "error": error}
        )
        self.event_bus.publish(event)

    def subscribe_to_completions(self, callback: Callable):
        """Subscribe to task completions"""
        self.event_bus.subscribe(EventType.TASK_COMPLETED, callback)

    def subscribe_to_creations(self, callback: Callable):
        """Subscribe to task creations"""
        self.event_bus.subscribe(EventType.TASK_CREATED, callback)


# Global task event manager
task_events = TaskEventManager()
