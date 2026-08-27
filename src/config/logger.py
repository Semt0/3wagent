import logging
from pathlib import Path

from qwen_agent.log import logger
from src.config.runtime import get_logs_dir

_handler: logging.FileHandler | None = None


def attach_run_log(model_name: str) -> None:
    """Attach a file handler writing to the current run's logs directory.

    Called at the start of each run; the previous run's handler is removed so
    log lines are not duplicated across run files.
    """
    global _handler
    if _handler is not None:
        logger.removeHandler(_handler)
    logs_dir = get_logs_dir()
    logs_dir.mkdir(parents=True, exist_ok=True)
    current_log = logs_dir / f"{model_name}.log"
    _handler = logging.FileHandler(current_log, encoding="utf-8")
    _handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(filename)s - %(lineno)d - %(levelname)s - %(message)s'
    ))
    logger.addHandler(_handler)
