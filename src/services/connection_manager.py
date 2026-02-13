import asyncio
import logging
from datetime import datetime, timezone

from src.config import Settings
from src.services.cnc_client import (
    CNC_RC_OK,
    CNC_RC_ALREADY_CONNECTED,
    CNC_RC_ALREADY_RUNS,
    CNC_RC_ERR_SERVER_NOT_RUNNING,
)
from src.services.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)


class ConnectionManager:
    """Background service that maintains the CNC connection.

    - Retries ``connect()`` on a fixed interval when not connected.
    - Periodically pings via ``is_server_connected()`` once connected.
    - Exposes status information consumed by the health endpoint.
    """

    def __init__(self, client: CncClientProtocol, settings: Settings) -> None:
        self._client = client
        self._retry_interval = settings.cnc_retry_interval
        self._health_interval = settings.cnc_health_interval

        self._state: str = "disconnected"
        self._retry_count: int = 0
        self._last_error: str | None = None
        self._last_connected_at: datetime | None = None
        self._task: asyncio.Task | None = None
        self._nudge_event: asyncio.Event = asyncio.Event()

    # -- public properties ---------------------------------------------------

    @property
    def state(self) -> str:
        return self._state

    @property
    def connected(self) -> bool:
        return self._state == "connected"

    @property
    def retry_count(self) -> int:
        return self._retry_count

    @property
    def last_error(self) -> str | None:
        return self._last_error

    @property
    def uptime_seconds(self) -> float | None:
        if self._last_connected_at is None:
            return None
        return (datetime.now(timezone.utc) - self._last_connected_at).total_seconds()

    # -- lifecycle -----------------------------------------------------------

    def nudge(self) -> None:
        """Wake the retry/heartbeat sleep so it retries immediately."""
        logger.info("ConnectionManager nudged — will retry now")
        self._nudge_event.set()

    async def _interruptible_sleep(self, seconds: float) -> None:
        """Sleep that can be cut short by a nudge() call."""
        self._nudge_event.clear()
        try:
            await asyncio.wait_for(self._nudge_event.wait(), timeout=seconds)
        except asyncio.TimeoutError:
            pass

    def start(self) -> None:
        """Schedule the background loop on the running event loop."""
        if self._task is not None:
            return
        self._task = asyncio.create_task(self._run())
        logger.info("ConnectionManager background task started")

    async def stop(self) -> None:
        """Cancel the background loop and wait for it to finish."""
        if self._task is None:
            return
        self._task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(self._task), timeout=3.0)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        self._task = None
        self._state = "disconnected"
        logger.info("ConnectionManager background task stopped")

    # -- background loop -----------------------------------------------------

    async def _run(self) -> None:
        while True:
            try:
                if not self._client.is_connected:
                    await self._retry_loop()
                else:
                    await self._heartbeat_loop()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Unexpected error in ConnectionManager loop")
                await asyncio.sleep(self._retry_interval)

    async def _retry_loop(self) -> None:
        """Keep trying to connect until successful."""
        while True:
            # Check if the CNC server process is running at all
            try:
                process_alive = await asyncio.wait_for(
                    asyncio.to_thread(self._client.is_server_process_alive),
                    timeout=3.0,
                )
            except (asyncio.TimeoutError, Exception) as e:
                if isinstance(e, asyncio.TimeoutError):
                    logger.warning("is_server_process_alive() timed out")
                process_alive = False

            if not process_alive:
                self._state = "cnc_not_running"
                self._last_error = "CncServer.exe not found"
                logger.info("CNC server not running, waiting...")
                await self._interruptible_sleep(self._retry_interval)
                continue

            self._state = "retrying"
            logger.info(
                "Attempting CNC connection (retry #%d)...", self._retry_count,
            )
            try:
                rc = await asyncio.wait_for(
                    asyncio.to_thread(self._client.connect),
                    timeout=10.0,
                )
                if rc in (CNC_RC_OK, CNC_RC_ALREADY_RUNS, CNC_RC_ALREADY_CONNECTED):
                    self._state = "connected"
                    self._last_error = None
                    self._retry_count = 0
                    self._last_connected_at = datetime.now(timezone.utc)
                    logger.info("CNC connection established")
                    return
                elif rc == CNC_RC_ERR_SERVER_NOT_RUNNING:
                    self._state = "cnc_not_running"
                    self._last_error = "CNC server not running"
                else:
                    self._last_error = f"connect() returned code {rc}"
            except asyncio.TimeoutError:
                self._last_error = "connect() timed out (DLL hung)"
                logger.warning("CNC connect timed out after 10s")
            except Exception as exc:
                self._last_error = str(exc)
                logger.warning("CNC connect failed: %s", exc)

            self._retry_count += 1
            await self._interruptible_sleep(self._retry_interval)

    async def _heartbeat_loop(self) -> None:
        """Periodically check the connection is still alive."""
        self._state = "connected"
        while True:
            await self._interruptible_sleep(self._health_interval)
            try:
                alive = await asyncio.wait_for(
                    asyncio.to_thread(self._client.is_server_connected),
                    timeout=5.0,
                )
                logger.debug("Heartbeat check: alive=%s", alive)
            except asyncio.TimeoutError:
                logger.warning("Heartbeat check timed out (DLL hung)")
                alive = False
            except Exception as exc:
                logger.warning("Heartbeat check failed: %s", exc)
                alive = False

            if not alive:
                # Mark client as disconnected so retry_loop will call connect()
                self._client._connected = False  # noqa: SLF001

                try:
                    process_up = await asyncio.wait_for(
                        asyncio.to_thread(self._client.is_server_process_alive),
                        timeout=3.0,
                    )
                except (asyncio.TimeoutError, Exception) as e:
                    if isinstance(e, asyncio.TimeoutError):
                        logger.warning("is_server_process_alive() timed out in heartbeat")
                    process_up = False

                if process_up:
                    logger.warning("CNC heartbeat lost — connection dropped")
                    self._state = "retrying"
                    self._last_error = "heartbeat lost"
                else:
                    logger.warning("CNC server process stopped")
                    self._state = "cnc_not_running"
                    self._last_error = "CncServer.exe exited"
                return
