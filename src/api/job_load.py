import json
import logging
import re

from fastapi import APIRouter, Depends, Request, Path
from fastapi.routing import APIRoute

from src.core.app_state import get_cnc_client, get_settings
from src.core.config import Settings
from .schemas.job import LoadJobRequest, LoadJobResponse
from src.cnc.cnc_client_protocol import CncClientProtocol

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




@router.get("/api/cnc/job/load/{job_number}/{step}/{qty}", response_model=LoadJobResponse)
async def load_job(
    job_number: str = Path(..., min_length=12, max_length=12, pattern=r'^\d{12}$', description="12-digit job number"),
    step: str = Path(..., min_length=1, max_length=3, pattern=r'^\d+$', description="Numeric step identifier (1-999)"),
    qty: int = Path(..., ge=1, le=9999, description="Quantity/number of repeats (1-9999)"),
    client: CncClientProtocol = Depends(get_cnc_client),
    settings: Settings = Depends(get_settings),
):
    # Construct the request object from path parameters and settings
    request = LoadJobRequest(job_number=job_number, step=step, base_dir=settings.base_dir)
    # For now accept the qty parameter but keep it = 1 !
    qty = 1
    logger.info(
        "LOAD JOB request — job_number=%s, step=%s, qty=%d, job_dir=%s",
        job_number, step, qty, request.job_dir
    )

    try:
        # Find the .nc file matching Setup_{step}*.nc pattern
        file_path = request.find_nc_file()
        logger.info("Found NC file: %s", file_path)

        # Load the job using the found file path
        result = client.load_job(file_path)
        if result == 0:
            message = "Job loaded successfully"
            logger.info(message)

            # Always set job quantity (ensures repeat flag is configured)
            if qty >= 1:
                try:
                    qty_result = client.set_job_quantity(qty)
                    if qty_result == 0:
                        if qty > 1:
                            message += f" with quantity: {qty}"
                        logger.info("Job quantity set to %d", qty)
                    else:
                        logger.warning("Failed to set job quantity: error code %d", qty_result)
                        message += f" (quantity set failed: {qty_result})"
                except Exception as qty_exc:
                    logger.warning("Exception setting job quantity: %s", qty_exc)
                    message += f" (quantity set error: {qty_exc})"

            # Render the job so the CNC computes toolpath, progress, and time estimates
            try:
                render_result = client.render_job()
                if render_result == 0:
                    logger.info("Job render started")
                else:
                    logger.warning("Failed to start job render: error code %d", render_result)
            except Exception as render_exc:
                logger.warning("Exception starting job render: %s", render_exc)
        else:
            message = f"Load failed with error code: {result}"
            logger.error(message)
    except FileNotFoundError as exc:
        result = -1
        message = f"File not found: {exc}"
        logger.error(message)
        file_path = ""
    except ValueError as exc:
        result = -1
        message = f"File search error: {exc}"
        logger.error(message)
        file_path = ""
    except Exception as exc:
        result = -1
        message = f"Exception calling LoadJob: {exc}"
        logger.error(message)
        file_path = ""

    return LoadJobResponse.model_construct(
        status=result, message=message, fileName=file_path
    )
