from __future__ import annotations

import json
import urllib.request
from typing import Optional

from .config import POSITION_READ_TIMEOUT_SECONDS, resolve_adapter_url


class AdapterJogClient:
    """Small stdlib HTTP client for the adapter jog endpoints."""

    def __init__(self, base_url: Optional[str] = None, timeout_seconds: float = 2.0) -> None:
        self.base_url = resolve_adapter_url(base_url)
        self.timeout_seconds = timeout_seconds

    def start_continuous_jog(self, axis: str, direction: int, speed_percent: float) -> dict:
        return self._post_json(
            "/api/cnc/jog",
            {
                "axis": axis,
                "direction": direction,
                "step": 1.0,
                "velocity_factor": self._velocity_factor(speed_percent),
                "continuous": True,
            },
        )

    def stop_continuous_jog(self) -> dict:
        return self._post_json("/api/cnc/jog/stop", None)

    def get_positions(self) -> dict:
        return self._get_json("/api/cnc/position", timeout_seconds=min(self.timeout_seconds, POSITION_READ_TIMEOUT_SECONDS))

    def get_physical_button_status(self) -> dict:
        return self._get_json("/api/cnc/physical-buttons", timeout_seconds=min(self.timeout_seconds, 0.75))

    def home_all_axes(self) -> dict:
        return self._post_json("/api/cnc/home", None)

    def clear_cnc_messages(self) -> dict:
        return self._post_json("/api/cnc/messages/clear", None, timeout_seconds=min(self.timeout_seconds, 1.0))

    def get_recent_cnc_messages(self, limit: int = 10) -> dict:
        path = "/api/cnc/messages/recent?limit=" + str(int(limit))
        return self._get_json(path, timeout_seconds=min(self.timeout_seconds, 0.75))

    def start_job(self) -> dict:
        return self._get_json("/api/cnc/job/start", timeout_seconds=max(self.timeout_seconds, 5.0))

    def pause_job(self) -> dict:
        return self._post_json("/api/cnc/job/pause", None, timeout_seconds=max(self.timeout_seconds, 25.0))

    def reset(self) -> dict:
        return self._post_json("/api/cnc/reset", None)

    def move_relative(self, axis: str, signed_distance: float, speed_percent: float) -> dict:
        direction = 1 if signed_distance >= 0 else -1
        return self._post_json(
            "/api/cnc/jog",
            {
                "axis": axis,
                "direction": direction,
                "step": abs(float(signed_distance)),
                "velocity_factor": self._velocity_factor(speed_percent),
                "continuous": False,
            },
        )

    def zero_work_axis(self, axis: str) -> dict:
        return self._post_json("/api/cnc/zero", {"axis": axis})

    def set_work_coordinate(self, axis: str, value: float) -> dict:
        return self._post_json("/api/cnc/work-coordinate", {"axis": axis, "value": float(value)})

    def _get_json(self, path: str, timeout_seconds: Optional[float] = None) -> dict:
        request = urllib.request.Request(f"{self.base_url}{path}", method="GET")
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {"status": response.status, "message": "No response body"}
            return json.loads(response_body)

    def _post_json(self, path: str, payload: Optional[dict], timeout_seconds: Optional[float] = None) -> dict:
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}{path}",
            data=body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        timeout = self.timeout_seconds if timeout_seconds is None else timeout_seconds
        with urllib.request.urlopen(request, timeout=timeout) as response:
            response_body = response.read().decode("utf-8")
            if not response_body:
                return {"status": response.status, "message": "No response body"}
            return json.loads(response_body)

    @staticmethod
    def _velocity_factor(speed_percent: float) -> float:
        return max(0.01, min(1.0, float(speed_percent) / 100.0))
