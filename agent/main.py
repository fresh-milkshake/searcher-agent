#!/usr/bin/env python3
"""
Main entry point for the arXiv Analysis Agent

This file serves as the entry point for running the agent system.
It imports and runs the manager which handles all the task processing
and monitoring functionality.
"""

import asyncio
import sys
import os

# Add the parent directory to the path so we can import shared modules
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from shared.logger import get_logger
from agent.manager import main

logger = get_logger(__name__)


if __name__ == "__main__":
    try:
        logger.info("Starting arXiv Analysis Agent...")
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Agent stopped by user (Ctrl+C)")
    except Exception as e:
        logger.error(f"Critical error in agent main: {e}")
        sys.exit(1)
