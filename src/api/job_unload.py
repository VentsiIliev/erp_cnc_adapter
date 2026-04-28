import logging

from fastapi import APIRouter, Depends, Request

from src.api.schemas.job import LoadJobResponse
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.error_translator import translate_error
from src.core.app_state import get_cnc_client
from src.core.placeholder_job import get_placeholder_job_path

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/api/cnc/job/unload", response_model=LoadJobResponse)
async def unload_job(
    request: Request,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Load a no-op placeholder job so the adapter behaves as if no job is loaded."""
    file_path = ""

    try:
        try:
            current_state = client.get_state()
        except Exception as state_exc:
            current_state = None
            logger.debug("Could not check CNC state before unload: %s", state_exc)

        if current_state == 0:
            return LoadJobResponse.model_construct(
                status=22,
                message="CNC Server is not running or not ready. Start CNC Server before unloading the job",
                fileName="",
            )

        if current_state == 6:
            return LoadJobResponse.model_construct(
                status=6,
                message="Cannot unload job while a job is running. Wait for it to finish or stop it first",
                fileName="",
            )

        if current_state == 12:
            return LoadJobResponse.model_construct(
                status=10,
                message="Cannot unload job while a job is paused. Resume and finish it, or reset the machine first",
                fileName="",
            )

        file_path = str(get_placeholder_job_path())
        logger.info("UNLOAD JOB request - loading placeholder file: %s", file_path)

        result = client.load_job(file_path)
        if result == 0:
            message = "Job unloaded successfully"
            services = request.app.state.services
            services.last_loaded_job = None

            monitor = getattr(services, "job_monitor", None)
            if monitor is not None:
                clear_job_info = getattr(monitor, "clear_job_info", None)
                if callable(clear_job_info):
                    clear_job_info()
                monitor._job_info = {}
                monitor._current_job_name = ""
                monitor._was_running = False

            try:
                client.set_job_quantity(1)
            except Exception as qty_exc:
                logger.debug("Could not reset placeholder job quantity: %s", qty_exc)

            logger.info("Job unloaded by loading placeholder CNC file")
        else:
            error_info = translate_error(result)
            message = f"{error_info['message']}. {error_info['suggestion']}"
            logger.error("Unload job failed with code %d: %s", result, message)

    except FileNotFoundError as exc:
        result = 20
        message = f"Placeholder job file not found: {exc}"
        logger.error(message)
        file_path = ""
    except Exception as exc:
        result = -1
        message = f"Exception unloading job: {exc}"
        logger.error(message, exc_info=True)
        file_path = ""

    return LoadJobResponse.model_construct(
        status=result,
        message=message,
        fileName=file_path,
    )