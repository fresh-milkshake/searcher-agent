from aiogram import Router
from shared.logger import get_logger

router = Router(name="management")
logger = get_logger(__name__)

# Legacy topic-based commands have been removed as they are not used in the current
# agent interaction model. This router remains for future management features.
