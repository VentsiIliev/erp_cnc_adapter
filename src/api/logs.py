"""Logs API endpoint for retrieving server logs."""

import asyncio
import logging
from pathlib import Path
from fastapi import APIRouter
import sys

logger = logging.getLogger(__name__)
router = APIRouter()


def _read_log_lines(log_file: Path, lines: int) -> list[str]:
    with log_file.open("r", encoding="utf-8", errors="replace") as f:
        content = f.readlines()[-lines:]
    return [line.rstrip('\n\r') for line in content if line.strip()]


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

        content = await asyncio.to_thread(_read_log_lines, log_file, lines)

        # logger.debug("Retrieved %d log lines from %s", len(content), log_file)
        return {"lines": content}

    except Exception as e:
        logger.error("Error reading log file: %s", e, exc_info=True)
        return {"lines": [], "error": str(e)}
