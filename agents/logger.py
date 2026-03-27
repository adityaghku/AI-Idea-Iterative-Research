from __future__ import annotations

import logging
import sys
from pathlib import Path

from agents.config import DEFAULT_VERBOSE

LOG_DIR = Path("logs")


def setup_logging(verbose: bool = DEFAULT_VERBOSE) -> logging.Logger:
    level = logging.INFO if verbose else logging.ERROR
    logger = logging.getLogger("idea_harvester")
    logger.setLevel(level)

    if logger.handlers:
        return logger

    console = logging.StreamHandler(sys.stdout)
    console.setLevel(level)
    console.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S"
    ))
    logger.addHandler(console)

    LOG_DIR.mkdir(exist_ok=True)
    from datetime import datetime
    log_file = LOG_DIR / f"harvester_{datetime.now():%Y%m%d_%H%M%S}.log"
    file_handler = logging.FileHandler(log_file)
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(message)s"
    ))
    logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("idea_harvester")


def log_structured(event: str, iteration: int = 0, **kwargs) -> None:
    """Log structured JSON for dashboard integration."""
    import json
    log_entry = {
        "event": event,
        "iteration": iteration,
        **kwargs,
    }
    logger = get_logger()
    logger.info(json.dumps(log_entry))
