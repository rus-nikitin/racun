import logging

from src.config import settings


def setup_logging():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] [%(message)s]",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[
            logging.FileHandler("app_logs.log"),  # Логи будут записываться в файл app_logs.log
            logging.StreamHandler()  # Также вывод логов будет на консоль
        ]
    )
