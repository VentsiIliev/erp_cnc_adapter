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

    def load_job(self, file_name: str) -> int:
        return 24

    def set_job_quantity(self, quantity: int) -> int:
        return 24

    def render_job(self) -> int:
        return 24

    def run_job(self) -> int:
        return 24
