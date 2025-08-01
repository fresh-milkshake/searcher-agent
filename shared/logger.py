"""
Настройка логгирования для проекта
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Настройка логгера с записью в файл по дате

    Args:
        name: Имя логера
        log_level: Уровень логирования

    Returns:
        Настроенный логер
    """
    # Создаем папку для логов
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Имя файла с текущей датой
    log_filename = f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_filepath = logs_dir / log_filename

    # Создаем логер
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Проверяем, есть ли уже обработчики (избегаем дублирования)
    if logger.handlers:
        return logger

    # Создаем форматтер
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Создаем обработчик для записи в файл
    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Создаем обработчик для вывода в консоль
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Добавляем обработчики к логеру
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Получение настроенного логера

    Args:
        name: Имя логера

    Returns:
        Логер
    """
    return setup_logger(name)
