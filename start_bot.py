#!/usr/bin/env python3
"""
Скрипт для запуска только телеграм бота
"""

import asyncio
from bot.telegram_bot import main

if __name__ == "__main__":
    asyncio.run(main())
