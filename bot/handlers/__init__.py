from .general import router as general_router
from .settings import router as settings_router
from .notifications import router as notifications_router
from .task import router as tasks_router

__all__ = [
    "general_router",
    "settings_router",
    "notifications_router",
    "tasks_router",
]
