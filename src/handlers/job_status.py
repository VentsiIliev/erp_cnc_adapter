import logging

from fastapi import APIRouter, Depends

from src.app_state import get_cnc_client
from src.schemas.job import JobStatusResponse
from src.services.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)
router = APIRouter()

# CNC_IE_* interpreter execution states from cncenums.py
STATE_MAP = {
    0: "Power-up",
    1: "Idle",
    2: "Ready",
    3: "Execution error",
    4: "Internal error",
    5: "Aborted",
    6: "Running job",
    7: "Running line",
    8: "Running sub",
    9: "Running sub search",
    10: "Running line search",
    11: "Paused (line)",
    12: "Paused (job)",
    13: "Paused (sub)",
    14: "Paused (line search)",
    15: "Paused (sub search)",
    16: "Running handwheel",
    17: "Running line handwheel",
    18: "Running line paused",
    19: "Running axis jog",
    20: "Running IP jog",
    21: "Rendering graph",
    22: "Searching",
    23: "Search done",
}


@router.get("/api/cnc/job/status", response_model=JobStatusResponse)
async def get_job_status(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    logger.info("GET job status request")
    try:
        state = client.get_state()
        state_text = STATE_MAP.get(state, f"Unknown state: {state}")
        job = client.get_job_status()
        logger.info("State: %s (code %d), job: %s", state_text, state, job.get("jobName", ""))
        return JobStatusResponse(state=state, stateText=state_text, **job)
    except Exception as exc:
        logger.error("Error getting job status: %s", exc)
        return JobStatusResponse(state=-1, stateText=f"Error: {exc}")
