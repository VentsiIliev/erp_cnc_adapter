from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.cnc.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CncMessage:
    timestamp_utc: str
    text: str

    def as_dict(self) -> dict:
        return {"timestampUtc": self.timestamp_utc, "text": self.text}


class CncMessageService:
    """Background FIFO listener that keeps recent operator-facing CNC messages."""

    def __init__(self, cnc_client: CncClientProtocol, poll_interval_ms: int = 100, max_messages: int = 50) -> None:
        self._client = cnc_client
        self._poll_interval = max(0.02, int(poll_interval_ms) / 1000.0)
        self._messages: deque[CncMessage] = deque(maxlen=max(1, int(max_messages)))
        self._monitoring = False
        self._task: Optional[asyncio.Task] = None
        self._last_error: Optional[str] = None

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    async def start_monitoring(self) -> None:
        if self._monitoring:
            logger.warning("CNC message monitor already running")
            return
        logger.info("Starting CNC message monitor (poll interval: %.0fms)", self._poll_interval * 1000)
        self._monitoring = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        if not self._monitoring:
            return
        logger.info("Stopping CNC message monitor")
        self._monitoring = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._last_error = None

    async def _monitor_loop(self) -> None:
        try:
            while self._monitoring:
                try:
                    await self.poll_once()
                except Exception as exc:
                    error_text = str(exc)
                    if error_text != self._last_error:
                        logger.warning("CNC message monitor poll failed: %s", exc)
                    self._last_error = error_text
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            logger.debug("CNC message monitor loop cancelled")
            raise

    async def poll_once(self) -> list[CncMessage]:
        texts = await asyncio.to_thread(self._client.poll_cnc_messages)
        self._last_error = None
        captured: list[CncMessage] = []
        for text in texts:
            message = CncMessage(
                timestamp_utc=datetime.now(timezone.utc).isoformat(),
                text=str(text),
            )
            self._messages.append(message)
            captured.append(message)
        return captured

    def recent_messages(self, limit: int = 10) -> list[dict]:
        safe_limit = max(1, int(limit))
        return [message.as_dict() for message in list(self._messages)[-safe_limit:]]

    def clear(self) -> None:
        self._messages.clear()