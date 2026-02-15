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
            "numLinesInJob": 0,
            "numLinesInMacro": 0,
            "numLinesInUserMacro": 0,
            "isLongJob": 0,
            "isSuperLongJob": 0,
            "jobIsRendered": 0,
            "totalJobLength": 0.0,
            "jobProgress": 0.0,
            "jobActualRunningTime": 0.0,
            "jobRemainingRunningTime": 0.0,
            "jobEstimatedTime": 0.0,
            "TCACollision": 0,
            "MCACollision": 0,
            "xCollision": 0.0,
            "yCollision": 0.0,
            "zCollision": 0.0,
            "jobRenderLine": 0,
            "jobRenderProgressPercentage": 0.0,
            "curIpLine": 0,
            "curExLine": 0,
            "lastKnownExecutedLineNumber": 0,
            "lastKnownToolChangeLineNumber": 0,
            "doRepeatJob": 0,
            "nrOfJobRepeatsSet": 0,
            "nrOfRepeatsActual": 0,
            "extraLineWhenEndOfJob": "",
            "stockDiameterTurning": 0.0,
            "stockLengthTurning": 0.0,
            "stockZAtWorkOffset": 0.0,
        }

    def load_job(self, file_name: str) -> int:
        logger.info("[MOCK] load_job('%s')", file_name)
        return 0

    def run_job(self) -> int:
        logger.info("[MOCK] run_job()")
        return 0