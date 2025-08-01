"""
Система событий для более элегантного взаимодействия между сервисами
Использует SQLite как очередь сообщений с NOTIFY/LISTEN механизмом
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
    """Типы событий в системе"""

    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    MESSAGE_RECEIVED = "message_received"
    RESPONSE_READY = "response_ready"


@dataclass
class Event:
    """Событие в системе"""

    id: Optional[int] = None
    event_type: EventType = EventType.TASK_CREATED
    data: Dict[str, Any] = None
    created_at: datetime = None
    processed: bool = False

    def __post_init__(self):
        if self.data is None:
            self.data = {}
        if self.created_at is None:
            self.created_at = datetime.now()


class EventBus:
    """
    Шина событий с поддержкой async/await
    Использует SQLite для персистентности и межпроцессного взаимодействия
    """

    def __init__(self, db_path: str = "events.db"):
        self.db_path = db_path
        self.subscribers: Dict[EventType, List[Callable]] = {}
        self.running = False
        self._init_db()

    def _init_db(self):
        """Инициализация базы данных для событий"""
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

            # Создаем индексы для быстрого поиска
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

            logger.info(f"Инициализирована база данных событий: {self.db_path}")

        except Exception as e:
            logger.error(f"Ошибка инициализации базы событий: {e}")
            raise

    def publish(self, event: Event) -> bool:
        """
        Публикация события

        Args:
            event: Событие для публикации

        Returns:
            True если событие успешно опубликовано
        """
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            import json

            # Безопасная сериализация - конвертируем все в строки если нужно
            try:
                data_json = json.dumps(event.data)
            except TypeError as json_error:
                logger.warning(f"Объект не сериализуется в JSON, конвертируем в строку: {json_error}")
                # Конвертируем все значения в строки для безопасной сериализации
                safe_data = {}
                for key, value in event.data.items():
                    if isinstance(value, (str, int, float, bool, list, dict, type(None))):
                        safe_data[key] = value
                    else:
                        safe_data[key] = str(value)  # Конвертируем сложные объекты в строку
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

            logger.info(
                f"Опубликовано событие {event.event_type.value} с ID {event.id}"
            )
            return True

        except Exception as e:
            logger.error(f"Ошибка публикации события: {e}")
            return False

    def subscribe(self, event_type: EventType, callback: Callable):
        """
        Подписка на событие

        Args:
            event_type: Тип события
            callback: Функция обратного вызова
        """
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []

        self.subscribers[event_type].append(callback)
        logger.info(f"Добавлена подписка на событие {event_type.value}")

    def unsubscribe(self, event_type: EventType, callback: Callable):
        """
        Отписка от события

        Args:
            event_type: Тип события
            callback: Функция обратного вызова
        """
        if event_type in self.subscribers:
            try:
                self.subscribers[event_type].remove(callback)
                logger.info(f"Удалена подписка на событие {event_type.value}")
            except ValueError:
                logger.warning(
                    f"Подписка на {event_type.value} не найдена для удаления"
                )

    async def start_processing(self, poll_interval: float = 0.5):
        """
        Запуск обработки событий

        Args:
            poll_interval: Интервал опроса событий в секундах
        """
        self.running = True
        logger.info("Запущена обработка событий")

        while self.running:
            try:
                await self._process_events()
                await asyncio.sleep(poll_interval)

            except Exception as e:
                logger.error(f"Ошибка в цикле обработки событий: {e}")
                await asyncio.sleep(poll_interval)

    def stop_processing(self):
        """Остановка обработки событий"""
        self.running = False
        logger.info("Остановлена обработка событий")

    async def _process_events(self):
        """Обработка необработанных событий"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            # Получаем необработанные события
            cursor.execute("""
                SELECT id, event_type, data, created_at
                FROM events
                WHERE processed = FALSE
                ORDER BY created_at ASC
                LIMIT 100
            """)

            events = cursor.fetchall()
            
            if events:
                logger.info(f"Найдено {len(events)} необработанных событий")
            
            for event_row in events:
                event_id, event_type_str, data_json, created_at = event_row

                try:
                    import json

                    event_type = EventType(event_type_str)
                    data = json.loads(data_json)

                    # Создаем объект события
                    event = Event(
                        id=event_id,
                        event_type=event_type,
                        data=data,
                        created_at=datetime.fromisoformat(created_at)
                        if isinstance(created_at, str)
                        else created_at,
                        processed=False,
                    )

                    # Вызываем подписчиков
                    if event_type in self.subscribers:
                        logger.info(f"Найдено {len(self.subscribers[event_type])} подписчиков для события {event_type.value}")
                        for callback in self.subscribers[event_type]:
                            try:
                                logger.info(f"Вызываем обработчик для события {event_type.value} (ID: {event_id})")
                                if asyncio.iscoroutinefunction(callback):
                                    await callback(event)
                                else:
                                    callback(event)
                                logger.info(f"Обработчик события {event_type.value} (ID: {event_id}) выполнен успешно")
                            except Exception as e:
                                logger.error(
                                    f"Ошибка в обработчике события {event_type.value}: {e}"
                                )
                    else:
                        logger.warning(f"Нет подписчиков для события {event_type.value} (ID: {event_id})")

                    # Помечаем событие как обработанное
                    cursor.execute(
                        """
                        UPDATE events SET processed = TRUE WHERE id = ?
                    """,
                        (event_id,),
                    )

                except Exception as e:
                    logger.error(f"Ошибка обработки события {event_id}: {e}")
                    # Помечаем как обработанное, чтобы не зациклиться
                    cursor.execute(
                        """
                        UPDATE events SET processed = TRUE WHERE id = ?
                    """,
                        (event_id,),
                    )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Ошибка при обработке событий: {e}")

    def cleanup_old_events(self, days_old: int = 7):
        """
        Очистка старых обработанных событий

        Args:
            days_old: Количество дней для хранения событий
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
                logger.info(f"Удалено {deleted_count} старых событий")

        except Exception as e:
            logger.error(f"Ошибка при очистке старых событий: {e}")


# Глобальный экземпляр шины событий
_event_bus = None


def get_event_bus() -> EventBus:
    """Получение глобального экземпляра шины событий"""
    global _event_bus
    if _event_bus is None:
        # Используем фиксированный путь для всех процессов
        _event_bus = EventBus(db_path="events.db")
        logger.info(f"Создан новый экземпляр EventBus с путем: events.db")
    return _event_bus


class TaskEventManager:
    """Менеджер событий для задач - упрощенный интерфейс"""

    def __init__(self):
        self.event_bus = get_event_bus()

    def task_created(self, task_id: int, task_type: str, data: Any = None):
        """Уведомление о создании задачи"""
        logger.info(f"Создаем событие TASK_CREATED для задачи {task_id}")
        event = Event(
            event_type=EventType.TASK_CREATED,
            data={"task_id": task_id, "task_type": task_type, "data": data},
        )
        success = self.event_bus.publish(event)
        if success:
            logger.info(f"Событие TASK_CREATED успешно опубликовано для задачи {task_id}")
        else:
            logger.error(f"Ошибка публикации события TASK_CREATED для задачи {task_id}")

    def task_completed(self, task_id: int, result: Any = None):
        """Уведомление о завершении задачи"""
        logger.info(f"Создаем событие TASK_COMPLETED для задачи {task_id}")
        
        # Гарантируем, что result - это строка или None
        safe_result = None
        if result is not None:
            if isinstance(result, str):
                safe_result = result
            else:
                safe_result = str(result)  # Конвертируем любой объект в строку
                logger.warning(f"Результат задачи {task_id} конвертирован в строку: {type(result)}")
        
        event = Event(
            event_type=EventType.TASK_COMPLETED,
            data={"task_id": task_id, "result": safe_result},
        )
        success = self.event_bus.publish(event)
        if success:
            logger.info(f"Событие TASK_COMPLETED успешно опубликовано для задачи {task_id}")
        else:
            logger.error(f"Ошибка публикации события TASK_COMPLETED для задачи {task_id}")

    def task_failed(self, task_id: int, error: str):
        """Уведомление об ошибке в задаче"""
        event = Event(
            event_type=EventType.TASK_FAILED, data={"task_id": task_id, "error": error}
        )
        self.event_bus.publish(event)

    def subscribe_to_completions(self, callback: Callable):
        """Подписка на завершение задач"""
        self.event_bus.subscribe(EventType.TASK_COMPLETED, callback)

    def subscribe_to_creations(self, callback: Callable):
        """Подписка на создание задач"""
        self.event_bus.subscribe(EventType.TASK_CREATED, callback)


# Глобальный менеджер событий задач
task_events = TaskEventManager()
