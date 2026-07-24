import logging

logger = logging.getLogger(__name__)


class MockCncClient:
    """Stub CNC client for development without the real DLL."""

    def __init__(self) -> None:
        self._connected = False
        logger.warning("Using MockCncClient — no real CNC hardware")

    @property
    def is_connected(self) -> bool:
        return self._connected

    def connect(self) -> int:
        logger.info("[MOCK] connect()")
        self._connected = True
        return 0

    def disconnect(self) -> None:
        logger.info("[MOCK] disconnect()")
        self._connected = False

    def is_server_connected(self) -> bool:
        return self._connected

    @staticmethod
    def is_server_process_alive() -> bool:
        return False

    def get_state(self) -> int:
        return 0

    def get_job_status(self) -> dict:
        return {
            "jobName": "",
            "jobLoadCounter": 0,
            "totalJobLengthMm": 0.0,
            "jobProgressMm": 0.0,
            "jobActualRunningTimeSeconds": 0.0,
            "jobRemainingRunningTimeSeconds": 0.0,
            "jobEstimatedTimeSeconds": 0.0,
            "doRepeatJob": 0,
            "nrOfJobRepeatsSet": 0,
            "nrOfRepeatsActual": 0,
        }

    def get_positions(self) -> dict:
        return {
            "work": {"x": 0.0, "y": 0.0, "z": 0.0, "a": 0.0, "b": 0.0, "c": 0.0},
            "machine": {"x": 0.0, "y": 0.0, "z": 0.0, "a": 0.0, "b": 0.0, "c": 0.0},
        }

    def get_all_axes_homed(self) -> bool:
        return False

    def is_motion_enabled(self) -> bool:
        return True

    def home_all_axes_g28(self) -> int:
        logger.info("[MOCK] home_all_axes_g28()")
        return 0

    def load_job(self, file_name: str) -> int:
        logger.info("[MOCK] load_job('%s')", file_name)
        return 0

    def set_job_quantity(self, quantity: int) -> int:
        logger.info("[MOCK] set_job_quantity(%d)", quantity)
        return 0

    def render_job(self) -> int:
        logger.info("[MOCK] render_job()")
        return 0

    def run_job(self) -> int:
        logger.info("[MOCK] run_job()")
        return 0

    def pause_job(self) -> int:
        logger.info("[MOCK] pause_job()")
        return 0


    def start_jog(
        self,
        axis: str,
        direction: int,
        step: float,
        velocity_factor: float,
        continuous: bool,
    ) -> int:
        logger.info(
            "[MOCK] start_jog(axis=%s, direction=%s, step=%s, velocity_factor=%s, continuous=%s)",
            axis,
            direction,
            step,
            velocity_factor,
            continuous,
        )
        return 0

    def stop_jog(self, axis: str | None = None) -> int:
        logger.info("[MOCK] stop_jog(axis=%s)", axis)
        return 0

    def move_to(self, axis: str, position: float, velocity_factor: float) -> int:
        logger.info(
            "[MOCK] move_to(axis=%s, position=%s, velocity_factor=%s)",
            axis,
            position,
            velocity_factor,
        )
        return 0

    def zero_work_axis(self, axis: str) -> int:
        logger.info("[MOCK] zero_work_axis(axis=%s)", axis)
        return 0

    def set_work_coordinate(self, axis: str, value: float) -> int:
        logger.info("[MOCK] set_work_coordinate(axis=%s, value=%s)", axis, value)
        return 0
