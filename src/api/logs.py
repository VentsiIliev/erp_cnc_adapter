"""Logs API endpoint for retrieving server logs."""

import logging
from pathlib import Path
from fastapi import APIRouter
import sys

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/logs")
async def get_logs(lines: int = 200):
    """Get the last N lines from the adapter log file."""
    try:
        if getattr(sys, "frozen", False):
            base = Path(sys.executable).parent
        else:
            base = Path(__file__).resolve().parent.parent.parent

        log_file = base / "logs" / "adapter.log"

        if not log_file.exists():
            logger.warning("Log file not found: %s", log_file)
            return {"lines": []}

        with log_file.open("r", encoding="utf-8", errors="replace") as f:
            content = f.readlines()[-lines:]

        # Strip newlines and filter out empty lines
        content = [line.rstrip('\n\r') for line in content if line.strip()]

        # logger.debug("Retrieved %d log lines from %s", len(content), log_file)
        return {"lines": content}

    except Exception as e:
        logger.error("Error reading log file: %s", e, exc_info=True)
        return {"lines": [], "error": str(e)}
