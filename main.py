import asyncio
import subprocess
import signal
import sys
from multiprocessing import Process
from shared.db import init_db


def run_bot():
    """Starts the Telegram bot"""
    subprocess.run([sys.executable, "start_bot.py"])


def run_agent():
    """Starts the AI agent"""
    subprocess.run([sys.executable, "start_agent.py"])


def signal_handler(sig, frame):
    """Signal handler for graceful shutdown"""
    print("\nShutting down services...")
    sys.exit(0)


async def main():
    """Main function to start all services"""
    print("Initializing database...")
    await init_db()
    print("Database initialized!")

    print("Starting services...")

    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)

    # Start processes
    bot_process = Process(target=run_bot)
    agent_process = Process(target=run_agent)

    try:
        bot_process.start()
        print("Telegram bot started")

        agent_process.start()
        print("AI agent started")

        print("All services started! Press Ctrl+C to stop.")

        # Wait for processes to finish
        bot_process.join()
        agent_process.join()

    except KeyboardInterrupt:
        print("\nShutting down services...")
        bot_process.terminate()
        agent_process.terminate()
        bot_process.join()
        agent_process.join()
        print("All services stopped.")


if __name__ == "__main__":
    asyncio.run(main())
