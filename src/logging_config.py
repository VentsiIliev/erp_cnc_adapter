import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path


def setup_logging(level: str = "INFO") -> None:
    """
    Configure logging to write to both file and console.

    Logs are written to:
    - logs/adapter.log (rotated at 10MB, keeps 5 backups)
    - Console/stdout (when running manually)

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
    """
    # Create logs directory if it doesn't exist
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    log_file = log_dir / "adapter.log"

    # Define log format
    log_format = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    date_format = "%Y-%m-%d %H:%M:%S"

    # Get the root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    # Remove any existing handlers
    root_logger.handlers.clear()

    # Create formatters
    formatter = logging.Formatter(log_format, datefmt=date_format)

    # File handler with rotation (10MB max, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.DEBUG)  # Log everything to file
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # Console handler (for when running manually/debugging)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)  # Less verbose on console
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # Log the startup
    logging.info(f"Logging initialized - File: {log_file.absolute()}, Level: {level}")

