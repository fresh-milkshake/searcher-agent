from .general import router as general_router
from .management import router as management_router
from .settings import router as settings_router

__all__ = ["general_router", "management_router", "settings_router"]
