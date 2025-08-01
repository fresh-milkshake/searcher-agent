#!/usr/bin/env python3
"""
Скрипт для запуска только ИИ агента
"""

import asyncio
from agent.manager import main

if __name__ == "__main__":
    asyncio.run(main())
