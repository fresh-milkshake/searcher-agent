"""Logging configuration using Loguru.

- File sink: captures ALL logs (DEBUG+) to `logs/YYYY-MM-DD.log`
- Console sink: level is configurable per process (default INFO)
"""

import logging
import sys
from datetime import datetime
from pathlib import Path

from loguru import logger as _loguru_logger


_CONFIGURED: bool = False


def _configure_loguru(console_level: int = logging.INFO) -> None:
    """Configure Loguru sinks once per process."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    logs_dir = Path("logs")
    logs_dir.mkdir(exist_ok=True)
    log_filename = f"{datetime.now().strftime('%Y-%m-%d')}.log"
    log_filepath = logs_dir / log_filename

    # Remove default sink to avoid duplicate outputs
    try:
        _loguru_logger.remove()
    except Exception:
        pass

    # Console sink (level configurable)
    _loguru_logger.add(
        sys.stdout,
        level=console_level,
        format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
        enqueue=True,
        diagnose=False,
        backtrace=False,
    )

    # File sink (always DEBUG and above)
    _loguru_logger.add(
        str(log_filepath),
        level="DEBUG",
        format="{time:YYYY-MM-DD HH:mm:ss} - {name} - {level} - {message}",
        rotation="00:00",
        encoding="utf-8",
        enqueue=True,
        diagnose=False,
        backtrace=False,
    )

    _CONFIGURED = True


def setup_logger(name: str, log_level: int = logging.INFO):
    """Return a Loguru logger bound for module usage.

    Note: ``name`` is not required by Loguru to display the module name; the
    format uses ``{name}`` from the call site. We keep the signature for
    backward compatibility.
    """
    _configure_loguru(console_level=log_level)
    return _loguru_logger


def get_logger(name: str):
    """Get configured Loguru logger."""
    return setup_logger(name)
