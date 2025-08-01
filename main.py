import asyncio
import subprocess
import signal
import sys
from multiprocessing import Process
from shared.database import init_db


def run_bot():
    """Запускает телеграм бота"""
    subprocess.run([sys.executable, "bot/telegram_bot.py"])


def run_agent():
    """Запускает ИИ агента"""
    subprocess.run([sys.executable, "agent/main.py"])


def signal_handler(sig, frame):
    """Обработчик сигнала для корректного завершения"""
    print("\nЗавершение работы сервисов...")
    sys.exit(0)


async def main():
    """Основная функция запуска всех сервисов"""
    print("Инициализация базы данных...")
    init_db()
    print("База данных инициализирована!")

    print("Запуск сервисов...")

    # Устанавливаем обработчик сигнала
    signal.signal(signal.SIGINT, signal_handler)

    # Запускаем процессы
    bot_process = Process(target=run_bot)
    agent_process = Process(target=run_agent)

    try:
        bot_process.start()
        print("Телеграм бот запущен")

        agent_process.start()
        print("ИИ агент запущен")

        print("Все сервисы запущены! Нажмите Ctrl+C для завершения.")

        # Ожидаем завершения процессов
        bot_process.join()
        agent_process.join()

    except KeyboardInterrupt:
        print("\nЗавершение работы сервисов...")
        bot_process.terminate()
        agent_process.terminate()
        bot_process.join()
        agent_process.join()
        print("Все сервисы остановлены.")


if __name__ == "__main__":
    asyncio.run(main())
