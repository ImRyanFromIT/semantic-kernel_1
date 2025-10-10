import logging
import os


def setup_logging() -> None:
    """Configure structured-ish logging suitable for a PoC.

    Uses environment variable LOG_LEVEL if present.
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


