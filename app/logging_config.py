"""Настройка логирования и отдельный логгер для тезисов."""

from __future__ import annotations

import logging
from pathlib import Path

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
THESIS_LOGGER_NAME = "theses"


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """Настроить вывод логов в консоль и, опционально, в файл."""
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(logging.FileHandler(log_file, encoding="utf-8"))

    logging.basicConfig(level=level.upper(), format=LOG_FORMAT, handlers=handlers)


def get_theses_logger() -> logging.Logger:
    """Вернуть логгер, в который пишутся только извлечённые тезисы."""
    return logging.getLogger(THESIS_LOGGER_NAME)
