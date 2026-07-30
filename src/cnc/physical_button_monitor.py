from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from src.cnc.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PhysicalButtonMonitorUpdate:
    indicators: dict
    actions: tuple[str, ...]
    log_message: str


class PhysicalButtonMonitor:
    """Tracks physical RUN/PAUSE button transitions."""

    ACTION_START_JOB = "start_job"
    ACTION_PAUSE_JOB = "pause_job"

    def __init__(self) -> None:
        self._run_press_seen = False
        self._run_release_confirmed = False
        self._pause_pressed_last = False

    def reset(self) -> None:
        self._run_press_seen = False
        self._run_release_confirmed = False
        self._pause_pressed_last = False

    def update(self, payload: dict) -> PhysicalButtonMonitorUpdate:
        """Return display-ready state and edge-triggered actions."""
        actions: list[str] = []

        run_released = bool(payload.get("runInput"))
        if not run_released:
            self._run_press_seen = True
            self._run_release_confirmed = False
        elif self._run_press_seen and not self._run_release_confirmed:
            self._run_release_confirmed = True
            actions.append(self.ACTION_START_JOB)

        pause_pressed = bool(payload.get("pauseInput"))
        if pause_pressed and not self._pause_pressed_last:
            actions.append(self.ACTION_PAUSE_JOB)
        self._pause_pressed_last = pause_pressed

        indicators = dict(payload)
        indicators["runInput"] = self._run_release_confirmed
        indicators["pauseInput"] = pause_pressed

        return PhysicalButtonMonitorUpdate(
            indicators=indicators,
            actions=tuple(actions),
            log_message=self._log_message(payload, actions),
        )

    def _log_message(self, payload: dict, actions: list[str]) -> str:
        action_text = ",".join(actions) if actions else "none"
        return (
            "Physical buttons: "
            f"runReleased={payload.get('runInput')} "
            f"runConfirmed={self._run_release_confirmed} "
            f"pause={payload.get('pauseInput')} "
            f"runRaw={payload.get('runRaw')} "
            f"pauseRaw={payload.get('pauseRaw')} "
            f"runLogical={payload.get('runLogical')} "
            f"pauseLogical={payload.get('pauseLogical')} "
            f"actions={action_text}"
        )


class PhysicalButtonService:
    """Adapter-owned physical RUN/PAUSE poller independent of the jog pad UI."""

    ERROR_STATES = {3, 4, 5}
    RUNNING_JOB_STATE = 6

    def __init__(self, cnc_client: CncClientProtocol, poll_interval_ms: int = 50) -> None:
        self._client = cnc_client
        self._poll_interval = max(0.01, int(poll_interval_ms) / 1000.0)
        self._monitor = PhysicalButtonMonitor()
        self._monitoring = False
        self._task: Optional[asyncio.Task] = None
        self._last_payload: Optional[dict] = None
        self._last_error: Optional[str] = None

    @property
    def is_monitoring(self) -> bool:
        return self._monitoring

    async def start_monitoring(self) -> None:
        if self._monitoring:
            logger.warning("Physical button monitor already running")
            return
        logger.info("Starting physical button monitor (poll interval: %.0fms)", self._poll_interval * 1000)
        self._monitoring = True
        self._task = asyncio.create_task(self._monitor_loop())

    async def stop_monitoring(self) -> None:
        if not self._monitoring:
            return
        logger.info("Stopping physical button monitor")
        self._monitoring = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
            self._task = None
        self._monitor.reset()
        self._last_payload = None
        self._last_error = None

    async def _monitor_loop(self) -> None:
        try:
            while self._monitoring:
                try:
                    await self.poll_once()
                except Exception as exc:
                    error_text = str(exc)
                    if error_text != self._last_error:
                        logger.warning("Physical button monitor poll failed: %s", exc)
                    self._last_error = error_text
                await asyncio.sleep(self._poll_interval)
        except asyncio.CancelledError:
            logger.debug("Physical button monitor loop cancelled")
            raise

    async def poll_once(self) -> PhysicalButtonMonitorUpdate:
        payload = await asyncio.to_thread(self._client.get_physical_button_status)
        self._last_error = None
        update = self._monitor.update(payload)
        if update.actions and not self._client.is_connected:
            logger.info(
                "Physical button actions ignored because CNC is not connected yet: %s",
                ",".join(update.actions),
            )
            update = PhysicalButtonMonitorUpdate(
                indicators=update.indicators,
                actions=(),
                log_message=update.log_message.rsplit("actions=", 1)[0] + "actions=none ignored=cnc_not_connected",
            )
        if update.actions or payload != self._last_payload:
            logger.info(update.log_message)
        self._last_payload = dict(payload)
        await self._dispatch_actions(update)
        return update

    async def _dispatch_actions(self, update: PhysicalButtonMonitorUpdate) -> None:
        for action in update.actions:
            if action == PhysicalButtonMonitor.ACTION_START_JOB:
                await asyncio.to_thread(self._start_or_resume_job)
            elif action == PhysicalButtonMonitor.ACTION_PAUSE_JOB:
                await asyncio.to_thread(self._pause_running_job)

    def _start_or_resume_job(self) -> None:
        try:
            state = self._client.get_state()
        except Exception as exc:
            logger.debug("Could not read CNC state before physical RUN: %s", exc)
            state = None

        if state in self.ERROR_STATES:
            logger.warning("Physical RUN ignored because CNC is in error state %s", state)
            return

        result = self._client.run_job()
        logger.info("Physical RUN triggered CncRunOrResumeJob() returned %s", result)

    def _pause_running_job(self) -> None:
        try:
            state = self._client.get_state()
        except Exception as exc:
            logger.debug("Could not read CNC state before physical PAUSE: %s", exc)
            state = None

        if state != self.RUNNING_JOB_STATE:
            logger.info("Physical PAUSE ignored because no running job is active (state %s)", state)
            return

        result = self._client.pause_job()
        logger.info("Physical PAUSE triggered CncPauseJob() returned %s", result)
