"""REST API service package for the research pipeline.

Exposes FastAPI endpoints that wrap the agent pipeline without modifying
other services. Import `api.app.app` to run the server.
"""

__all__ = [
    "__version__",
]

__version__ = "0.1.0"
