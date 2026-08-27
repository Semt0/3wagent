import logging
import os
import time

from src.tools.common import PROJECT_ROOT

LOGS_DIR = PROJECT_ROOT / "workspace" / "logs"


def SetUpHandler(model_name: str):
    os.makedirs(LOGS_DIR, exist_ok=True)
    current_log = LOGS_DIR / (model_name + str(time.ctime()) + ".log")
    file_handler = logging.FileHandler(current_log, encoding="utf-8")
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s"
        )
    )
    return file_handler
