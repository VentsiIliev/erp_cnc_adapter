import logging

from fastapi import APIRouter, Depends

from src.core.app_state import get_cnc_client
from .schemas.job import RunJobResponse
from src.cnc.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)

router = APIRouter()


@router.post("/api/cnc/job/start", response_model=RunJobResponse)
async def start_job(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    logger.info("START JOB request")

    try:
        result = client.run_job()
        if result == 0:
            message = "Job started successfully"
            logger.info(message)
        else:
            message = f"Start failed with error code: {result}"
            logger.error(message)
    except Exception as exc:
        result = -1
        message = f"Exception calling RunJob: {exc}"
        logger.error(message)

    return RunJobResponse(status=result, message=message)
