def get_general_router():
    """Lazy import of general router."""
    from .general import router
    return router

def get_settings_router():
    """Lazy import of settings router."""
    from .settings import router
    return router

def get_notifications_router():
    """Lazy import of notifications router."""
    from .notifications import router
    return router

def get_tasks_router():
    """Lazy import of tasks router."""
    from .task import router
    return router

# For backward compatibility  
general_router = property(lambda self: get_general_router())
settings_router = property(lambda self: get_settings_router())
notifications_router = property(lambda self: get_notifications_router())
tasks_router = property(lambda self: get_tasks_router())

__all__ = [
    "general_router",
    "settings_router", 
    "notifications_router",
    "tasks_router",
    "get_general_router",
    "get_settings_router",
    "get_notifications_router", 
    "get_tasks_router",
]
