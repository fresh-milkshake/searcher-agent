#!/usr/bin/env python3
"""
Script to start only the Telegram bot
"""

import asyncio
from bot.dispatcher import main

if __name__ == "__main__":
    asyncio.run(main())
