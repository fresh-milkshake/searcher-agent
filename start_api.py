#!/usr/bin/env python3
"""
Entrypoint to run the REST API service with uvicorn.
"""

import uvicorn


def main() -> None:
    """Start the FastAPI app using uvicorn."""

    uvicorn.run(
        "api.app:app",
        host="0.0.0.0",
        port=8000,
        reload=False,
        log_level="info",
    )


if __name__ == "__main__":
    main()


