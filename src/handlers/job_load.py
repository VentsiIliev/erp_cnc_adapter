import json
import logging
import re

from fastapi import APIRouter, Depends, Request
from fastapi.routing import APIRoute

from src.app_state import get_cnc_client
from src.schemas.job import LoadJobRequest, LoadJobResponse
from src.services.cnc_client_protocol import CncClientProtocol

logger = logging.getLogger(__name__)

# Double every backslash that is NOT right before a double-quote.
# This preserves \" (JSON string delimiter) while escaping bare
# backslashes that come from pasted Windows paths.
_BARE_BACKSLASH = re.compile(rb'\\(?!")')


class BackslashFixRoute(APIRoute):
    """Custom route that auto-fixes Windows paths with unescaped backslashes.

    If the raw body is already valid JSON it is used as-is.
    Otherwise bare backslashes are doubled so the JSON parser accepts them.
    """

    def get_route_handler(self):
        original = super().get_route_handler()

        async def handler(request: Request):
            body = await request.body()
            try:
                json.loads(body)
            except (json.JSONDecodeError, ValueError):
                request._body = _BARE_BACKSLASH.sub(rb"\\\\", body)
            return await original(request)

        return handler


router = APIRouter(route_class=BackslashFixRoute)


@router.post("/api/cnc/job/load", response_model=LoadJobResponse)
async def load_job(
    request: LoadJobRequest,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    logger.info("LOAD JOB request — fileName=%s", request.file_name)

    try:
        result = client.load_job(request.file_name)
        if result == 0:
            message = "Job loaded successfully"
            logger.info(message)
        else:
            message = f"Load failed with error code: {result}"
            logger.error(message)
    except Exception as exc:
        result = -1
        message = f"Exception calling LoadJob: {exc}"
        logger.error(message)

    return LoadJobResponse.model_construct(
        status=result, message=message, fileName=request.file_name
    )
