#!/usr/bin/env python3
"""
Script to start only the AI agent
"""

import asyncio
from agent.manager import main

if __name__ == "__main__":
    asyncio.run(main())
