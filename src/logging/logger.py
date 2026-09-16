"""Structured logging setup shared across the pipeline.

Every pipeline stage logs through the named "STAGE" markers below so a
reviewer can grep the log file for BOT_STARTED / RECORD_EXTRACTED / etc.
and reconstruct exactly what the run did.
"""
from __future__ import annotations

import logging
import sys
from pathlib import Path


class Stage:
    BOT_STARTED = "BOT_STARTED"
    PAGE_LOADED = "PAGE_LOADED"
    RECORD_DISCOVERED = "RECORD_DISCOVERED"
    RECORD_EXTRACTED = "RECORD_EXTRACTED"
    RECORD_EXTRACTION_FAILED = "RECORD_EXTRACTION_FAILED"
    RECORD_VALIDATED = "RECORD_VALIDATED"
    RECORD_REJECTED = "RECORD_REJECTED"
    DUPLICATE_SKIPPED = "DUPLICATE_SKIPPED"
    CRM_SYNC_ATTEMPTED = "CRM_SYNC_ATTEMPTED"
    CRM_SYNC_SUCCESS = "CRM_SYNC_SUCCESS"
    CRM_SYNC_FAILURE = "CRM_SYNC_FAILURE"
    CRM_SYNC_RETRY = "CRM_SYNC_RETRY"
    SCREENSHOT_SAVED = "SCREENSHOT_SAVED"
    BOT_COMPLETED = "BOT_COMPLETED"


_CONFIGURED = False


def configure_logging(log_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Configure the root "leadbot" logger once, with console + file handlers."""
    global _CONFIGURED
    logger = logging.getLogger("leadbot")
    if _CONFIGURED:
        return logger

    logger.setLevel(level)
    fmt = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(stage)-24s | %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S%z",
    )

    class StageFilter(logging.Filter):
        def filter(self, record: logging.LogRecord) -> bool:
            if not hasattr(record, "stage"):
                record.stage = "-"
            return True

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)
    console_handler.addFilter(StageFilter())

    log_dir.mkdir(parents=True, exist_ok=True)
    file_handler = logging.FileHandler(log_dir / "run.log", mode="a", encoding="utf-8")
    file_handler.setFormatter(fmt)
    file_handler.addFilter(StageFilter())

    logger.addHandler(console_handler)
    logger.addHandler(file_handler)
    logger.propagate = False
    _CONFIGURED = True
    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("leadbot")


def log_stage(logger: logging.Logger, stage: str, message: str, level: int = logging.INFO) -> None:
    logger.log(level, message, extra={"stage": stage})
