from __future__ import annotations

import sys
from loguru import logger


def setup_logging(level: str = "INFO") -> None:
    logger.remove()
    logger.add(sys.stdout, level=level, format="<green>{time:HH:mm:ss}</green> | <level>{level}</level> | {message}")


__all__ = ["logger", "setup_logging"]
