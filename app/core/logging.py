import logging
import sys
from typing import Any, Dict
from app.core.config import settings

def setup_logging() -> None:
    """Setup structured application logging."""
    logger = logging.getLogger("cryvex")
    
    level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(level)

    # Prevent propagation to the root logger to avoid duplicate logs
    logger.propagate = False

    # Create console handler if no handlers exist
    if not logger.handlers:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(level)
        
        # Consistent format: timestamp - level - logger - [request_id] - message
        # We use standard library logging formatting here. The middleware
        # will handle injecting request_id where appropriate.
        formatter = logging.Formatter(
            fmt="%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    # Also configure uvicorn loggers to match our level if possible
    for logger_name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(logger_name)
        uvicorn_logger.setLevel(level)

def get_logger(name: str) -> logging.Logger:
    """Get a named logger."""
    return logging.getLogger(f"cryvex.{name}")

# Centralized logger instance for general use
logger = get_logger("app")
