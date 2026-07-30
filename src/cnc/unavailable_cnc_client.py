import logging


logger = logging.getLogger(__name__)


class UnavailableCncClient:
    """Fallback CNC client used when the real DLL cannot be loaded."""

    def __init__(self, startup_error: str) -> None:
        self._connected = False
        self.startup_error = startup_error
        logger.error("Using UnavailableCncClient: %s", startup_error)

    @property
    def is_connected(self) -> bool:
        return False

    def connect(self) -> int:
        raise RuntimeError(self.startup_error)

    def disconnect(self) -> None:
        self._connected = False

    def is_server_connected(self) -> bool:
        return False

    def is_server_process_alive(self) -> bool:
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

    def get_physical_button_status(self) -> dict:
        return {
            "runInput": False,
            "pauseInput": False,
            "runRaw": 0,
            "pauseRaw": 0,
            "runLogical": 0,
            "pauseLogical": 0,
        }

    def get_all_axes_homed(self) -> bool:
        return False

    def is_motion_enabled(self) -> bool:
        return False

    def get_last_cnc_message(self) -> str | None:
        return None

    def clear_cnc_messages(self) -> None:
        return None

    def poll_cnc_messages(self) -> list[str]:
        return []

    def home_all_axes_gui_sequence(self) -> int:
        return 24

    def home_all_axes_sequence(self) -> int:
        return 24

    def load_job(self, file_name: str) -> int:
        return 24

    def set_job_quantity(self, quantity: int) -> int:
        return 24

    def render_job(self) -> int:
        return 24

    def run_job(self) -> int:
        return 24

    def pause_job(self) -> int:
        return 24

    def reset(self) -> int:
        return 24

    def start_jog(self, axis: str, direction: int, step: float, velocity_factor: float, continuous: bool) -> int:
        return 24

    def stop_jog(self, axis: str | None = None) -> int:
        return 24

    def move_to(self, axis: str, position: float, velocity_factor: float) -> int:
        return 24

    def zero_work_axis(self, axis: str) -> int:
        return 24

    def set_work_coordinate(self, axis: str, value: float) -> int:
        return 24