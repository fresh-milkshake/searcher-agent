"""
Logging configuration for the project
"""

import logging
from datetime import datetime
from pathlib import Path


def setup_logger(name: str, log_level: int = logging.INFO) -> logging.Logger:
    """
    Configure logger with date-based file logging

    Args:
        name: Logger name
        log_level: Logging level

    Returns:
        Configured logger
    """
    # Create logs directory
    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)

    # Filename with current date
    log_filename = f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_filepath = logs_dir / log_filename

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(log_level)

    # Check if handlers already exist (avoid duplication)
    if logger.handlers:
        return logger

    # Create formatter
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Create file handler
    file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
    file_handler.setLevel(log_level)
    file_handler.setFormatter(formatter)

    # Create console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)

    # Add handlers to logger
    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger


def get_logger(name: str) -> logging.Logger:
    """
    Get configured logger

    Args:
        name: Logger name

    Returns:
        Logger
    """
    return setup_logger(name)
