from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalButtonMonitorUpdate:
    indicators: dict
    actions: tuple[str, ...]
    log_message: str


class PhysicalButtonMonitor:
    """Tracks physical button transitions for jog pad diagnostics/actions."""

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
