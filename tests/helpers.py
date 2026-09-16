import logging


def make_test_logger() -> logging.Logger:
    """A logger usable by production code that expects a `stage=` LogRecord extra."""
    logger = logging.getLogger("leadbot.tests")
    logger.setLevel(logging.CRITICAL + 1)  # silence during test runs
    if not logger.handlers:
        logger.addHandler(logging.NullHandler())
    return logger
