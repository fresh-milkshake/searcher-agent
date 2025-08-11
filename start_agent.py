#!/usr/bin/env python3
"""
Script to start only the AI agent
"""

import asyncio
from agent.manager import main
from shared.db import init_db

if __name__ == "__main__":
    asyncio.run(init_db())
    asyncio.run(main())
