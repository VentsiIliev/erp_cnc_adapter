import logging

from fastapi import APIRouter, Depends, Request

from src.core.app_state import get_cnc_client, get_settings
from src.core.config import Settings
from .schemas.job import RunJobResponse
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.error_translator import translate_error, format_error

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/api/cnc/job/start", response_model=RunJobResponse)
async def start_job(
    request: Request,
    client: CncClientProtocol = Depends(get_cnc_client),
    settings: Settings = Depends(get_settings),
):
    """Start a CNC job. The persistent monitor will detect state changes automatically."""
    logger.debug("START JOB request")

    try:
        # Check monitor state first to avoid unnecessary API call
        services = request.app.state.services
        if services.job_monitor and services.job_monitor._was_running:
            logger.warning("Job start rejected: Monitor indicates job is already running")
            return RunJobResponse(
                status=6,
                message="Job is already running. Cannot start another job while one is executing. Wait for current job to finish"
            )

        # Check current CNC state - must be READY or PAUSED to start
        try:
            current_state = client.get_state()

            # State 0 = Power-up / Initialization (CNC Server not running or just started)
            if current_state == 0:
                logger.warning("Job start rejected: Machine in Power-up state (CNC Server not running or starting)")
                return RunJobResponse(
                    status=22,  # CNC_RC_ERR_SERVER_NOT_RUNNING
                    message="CNC Server is not running or not ready. Start CNC Server using /api/cnc/start and wait for it to initialize"
                )

            # State 1 = Idle (not ready yet)
            elif current_state == 1:
                logger.warning("Job start rejected: Machine is Idle (not ready)")
                return RunJobResponse(
                    status=10,
                    message="Machine is Idle and not ready. Try loading a job first or check machine status"
                )

            # State 6 = Running Job
            elif current_state == 6:
                logger.warning("Job start rejected: CNC state is 6 (Running Job)")
                return RunJobResponse(
                    status=6,
                    message="Job is already running. Cannot start another job while one is executing. Wait for current job to finish"
                )

            # State 3, 4, 5 = Error states
            elif current_state in (3, 4, 5):
                state_names = {3: "Execution Error", 4: "Internal Error", 5: "Aborted"}
                logger.warning("Job start rejected: Machine in error state %d (%s)", current_state, state_names.get(current_state))
                return RunJobResponse(
                    status=10,
                    message=f"Machine is in error state: {state_names.get(current_state)}. Reset or clear the error before starting a job"
                )

            # State 12 = Paused - OK, will resume
            elif current_state == 12:
                logger.info("Job is paused - will resume")

            # State 2 = Ready - OK to start

        except Exception as state_exc:
            logger.debug("Could not check state before start: %s", state_exc)

        # Call the CNC API to start/resume job
        logger.debug("About to call client.run_job()")
        result = client.run_job()
        logger.debug("Start job result code: %d", result)

        if result != 0:
            # Translate error code to human-readable message
            error_info = translate_error(result)
            message = format_error(result, "Start job")
            logger.error("%s (code: %d)", message, result)
            logger.error("START JOB FAILED — result_code=%d, message=%s", result, message)

            # Special handling for common errors
            if result == 6:  # CNC_RC_ALREADY_RUNS
                message = "Job is already running. Cannot start another job while one is executing"
            elif result == 10:  # CNC_RC_ERR_STATE
                try:
                    state = client.get_state()
                    state_text = {
                        1: "Idle", 2: "Ready", 3: "Execution Error", 4: "Internal Error",
                        5: "Aborted", 6: "Running Job", 12: "Paused"
                    }.get(state, f"State {state}")
                    message = f"Cannot start job in current state: {state_text}. {error_info['suggestion']}"
                except Exception:
                    message = f"{error_info['message']}. {error_info['suggestion']}"
            elif result == -1:
                message = "Cannot start job - machine is busy or in invalid state. Check machine status"
            else:
                message = f"{error_info['message']}. {error_info['suggestion']}"

            # Return error with detailed information
            return RunJobResponse(status=result, message=message)

        # Job started successfully
        message = "Job started successfully"
        logger.debug(message)
        logger.debug("START JOB response — status=%d, message=%s", result, message)

        # Ensure job monitor has the latest job info (should already be set from load_job)
        if hasattr(services, 'last_loaded_job') and services.last_loaded_job and services.job_monitor:
            job_info = services.last_loaded_job
            services.job_monitor.set_job_info(
                job_number=job_info.get("job_number", ""),
                step=job_info.get("step", ""),
                machine_number=job_info.get("machine_number", settings.machine_number)
            )
            logger.debug("Job monitor has job info - will automatically track completion")

        return RunJobResponse(status=result, message=message)

    except Exception as exc:
        result = -1
        error_info = translate_error(result)
        message = f"Exception calling RunJob: {exc}. {error_info['suggestion']}"
        logger.error(message, exc_info=True)
        logger.error("START JOB ERROR — Exception occurred: %s", str(exc))
        return RunJobResponse(status=result, message=message)



