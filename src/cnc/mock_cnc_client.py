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

