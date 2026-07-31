import ctypes
import getpass
import glob
import json
import logging
import os
import subprocess
import re

from fastapi import APIRouter, Depends, Request, Path
from fastapi.routing import APIRoute

from src.core.app_state import get_cnc_client, get_settings
from src.core.config import Settings
from .schemas.job import LoadJobRequest, LoadJobResponse
from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.error_translator import translate_error, format_error
from src.api.jog_pad_launcher import _adapter_base_url, launch_jog_pad

logger = logging.getLogger(__name__)

# Double every backslash that is NOT right before a double-quote.
# This preserves \" (JSON string delimiter) while escaping bare
# backslashes that come from pasted Windows paths.
_BARE_BACKSLASH = re.compile(rb'\\(?!")')


class BackslashFixRoute(APIRoute):
    """Custom route that auto-fixes Windows paths with unescaped backslashes.

    If the raw body is already valid JSON it is used as-is.
    Otherwise, bare backslashes are doubled so the JSON parser accepts them.
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


def _run_diag_command(command: list[str], timeout: float = 5.0) -> dict[str, object]:
    try:
        completed = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return {
            "returnCode": completed.returncode,
            "stdout": completed.stdout.strip(),
            "stderr": completed.stderr.strip(),
        }
    except Exception as exc:
        return {"error": f"{type(exc).__name__}: {exc}"}


def _current_session_id() -> int | None:
    if os.name != "nt":
        return None
    session_id = ctypes.c_uint()
    ok = ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(session_id))
    return int(session_id.value) if ok else None


def _is_elevated() -> bool | None:
    if os.name != "nt":
        return None
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return None




@router.get("/api/debug/job-path/{job_number}/{step}")
async def debug_job_path(
    job_number: str = Path(..., min_length=12, max_length=12, pattern=r'^\d{12}$'),
    step: str = Path(..., min_length=1, max_length=3, pattern=r'^\d+$'),
    settings: Settings = Depends(get_settings),
):
    """Report adapter-process filesystem diagnostics for a CNC job path."""
    load_request = LoadJobRequest(job_number=job_number, step=step, base_dir=settings.base_dir)
    job_dir = load_request.job_dir
    pattern_nc = os.path.join(job_dir, f"Setup_{step}*.nc")
    pattern_cnc = os.path.join(job_dir, f"Setup_{step}*.cnc")

    try:
        listdir_result = os.listdir(job_dir)
        listdir_error = None
    except Exception as exc:
        listdir_result = []
        listdir_error = f"{type(exc).__name__}: {exc}"

    diagnostics = {
        "process": {
            "pid": os.getpid(),
            "parentPid": os.getppid(),
            "sessionId": _current_session_id(),
            "user": getpass.getuser(),
            "envUserDomain": os.environ.get("USERDOMAIN"),
            "envUsername": os.environ.get("USERNAME"),
            "cwd": os.getcwd(),
            "executable": os.environ.get("_MEIPASS") or "",
            "elevated": _is_elevated(),
        },
        "paths": {
            "baseDir": settings.base_dir,
            "jobDir": job_dir,
            "patternNc": pattern_nc,
            "patternCnc": pattern_cnc,
        },
        "pythonFilesystem": {
            "baseDirIsDir": os.path.isdir(settings.base_dir),
            "jobDirIsDir": os.path.isdir(job_dir),
            "globNc": glob.glob(pattern_nc),
            "globCnc": glob.glob(pattern_cnc),
            "listdir": listdir_result[:50],
            "listdirError": listdir_error,
        },
        "subprocess": {
            "powershellTestPath": _run_diag_command([
                "powershell", "-NoProfile", "-ExecutionPolicy", "Bypass",
                "-Command", f"Test-Path -LiteralPath '{job_dir.replace(chr(39), chr(39) + chr(39))}'",
            ]),
            "cmdDir": _run_diag_command(["cmd.exe", "/c", "dir", job_dir]),
            "netUse": _run_diag_command(["cmd.exe", "/c", "net", "use"]),
            "cmdkey": _run_diag_command(["cmdkey.exe", "/list:192.168.2.11"]),
        },
    }
    logger.info("Job path diagnostic: %s", diagnostics)
    return diagnostics


@router.get("/api/cnc/job/load/{job_number}/{step}/{qty}", response_model=LoadJobResponse)
async def load_job(
    request: Request,
    job_number: str = Path(..., min_length=12, max_length=12, pattern=r'^\d{12}$', description="12-digit job number"),
    step: str = Path(..., min_length=1, max_length=3, pattern=r'^\d+$', description="Numeric step identifier (1-999)"),
    qty: int = Path(..., ge=1, le=9999, description="Quantity/number of repeats (1-9999)"),
    client: CncClientProtocol = Depends(get_cnc_client),
    settings: Settings = Depends(get_settings),
):
    # Construct the request object from path parameters and settings
    load_request = LoadJobRequest(job_number=job_number, step=step, base_dir=settings.base_dir)
    # For now accept the qty parameter but keep it = 1 !
    qty = 1
    logger.info(
        "LOAD JOB request — job_number=%s, step=%s, qty=%d, job_dir=%s",
        job_number, step, qty, load_request.job_dir
    )
    logger.debug("Load job request details: job_number=%s, step=%s, base_dir=%s", job_number, step, settings.base_dir)

    try:
        # Check monitor state first to avoid unnecessary API call and get immediate feedback
        services = request.app.state.services
        if services.job_monitor and services.job_monitor._was_running:
            logger.warning("Load job rejected: Monitor indicates job is already running")
            return LoadJobResponse.model_construct(
                status=6,
                message="Cannot load job while another job is running. Wait for current job to finish or stop it first",
                fileName=""
            )

        # Check current CNC state - must be READY to load a new job
        try:
            current_state = client.get_state()

            # State 6 = Running Job
            if current_state == 6:
                logger.warning("Load job rejected: CNC state is 6 (Running Job)")
                return LoadJobResponse.model_construct(
                    status=6,
                    message="Cannot load job while another job is running. Wait for current job to finish or stop it first",
                    fileName=""
                )

            # State 12 = Paused Job
            elif current_state == 12:
                logger.warning("Load job rejected: CNC state is 12 (Paused Job)")
                return LoadJobResponse.model_construct(
                    status=10,
                    message="Cannot load job while a job is paused. Resume and finish current job, or reset machine first",
                    fileName=""
                )

            # State 3, 4, 5 = Error states
            elif current_state in (3, 4, 5):
                state_names = {3: "Execution Error", 4: "Internal Error", 5: "Aborted"}
                logger.warning("Load job rejected: Machine in error state %d (%s)", current_state, state_names.get(current_state))
                return LoadJobResponse.model_construct(
                    status=10,
                    message=f"Machine is in error state: {state_names.get(current_state)}. Reset or clear the error before loading a job",
                    fileName=""
                )

            # State 2 = Ready - OK to load

        except Exception as state_exc:
            logger.debug("Could not check state before load: %s", state_exc)

        # Find the .nc file matching Setup_{step}*.nc pattern
        file_path = load_request.find_nc_file()
        logger.debug("Found NC file: %s", file_path)

        # Load the job using the found file path
        logger.debug("About to call client.load_job() with file_path: %s", file_path)
        result = client.load_job(file_path)
        logger.info("Load job result code: %d (file: %s)", result, file_path)
        if result == 0:
            message = "Job loaded successfully"
            logger.info(message)

            # Store job info in app state for the monitor to use
            request.app.state.services.last_loaded_job = {
                "job_number": job_number,
                "step": step,
                "machine_number": settings.machine_number,
            }
            logger.debug("Stored job info: Machine=%s, Job=%s, Step=%s",
                        settings.machine_number, job_number, step)

            # Update the persistent job monitor with new job info
            monitor = request.app.state.services.job_monitor
            if monitor is not None:
                monitor.set_job_info(job_number, step, settings.machine_number)
                # logger.debug("Updated job monitor with job info")

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

            jog_pad_launcher = getattr(request.app.state.services, "jog_pad_launcher", launch_jog_pad)
            jog_pad_response = jog_pad_launcher(
                _adapter_base_url(request),
                settings.jog_pad_pause_hold_interval_ms,
            )
            if jog_pad_response.status == 0:
                logger.info("Jog pad opened after successful job load")
                message += ". Jog pad opened for operator positioning"
            else:
                logger.warning("Job loaded, but jog pad did not open: %s", jog_pad_response.message)
                message += f". Jog pad launch failed: {jog_pad_response.message}"

            # Render the job so the CNC computes toolpath, progress, and time estimates
            try:
                render_result = client.render_job()
                if render_result == 0:
                    logger.info("Job render started")
                else:
                    render_error = format_error(render_result, "Render job")
                    logger.warning("%s (code: %d)", render_error, render_result)
            except Exception as render_exc:
                logger.warning("Exception starting job render: %s", render_exc)
        else:
            # Translate error code to human-readable message
            error_info = translate_error(result)
            message = format_error(result, "Load job")
            logger.error("%s (code: %d)", message, result)
            logger.error("LOAD JOB FAILED — job_number=%s, step=%s, result_code=%d, message=%s", job_number, step, result, message)

            # Special handling for -1 (machine busy/running)
            if result == -1:
                try:
                    state = client.get_state()
                    state_text = {
                        1: "Idle", 2: "Ready", 3: "Execution Error", 4: "Internal Error",
                        5: "Aborted", 6: "Running Job", 12: "Paused"
                    }.get(state, f"State {state}")

                    if state == 6:  # Running
                        message = "Cannot load job while another job is running. Wait for current job to finish or stop it first"
                        logger.error("Load rejected: Machine is currently running a job (state 6)")
                    elif state == 12:  # Paused
                        message = "Cannot load job while a job is paused. Resume and finish current job, or reset machine first"
                        logger.error("Load rejected: Machine has a paused job (state 12)")
                    else:
                        message = f"Cannot load job - machine in state: {state_text}. {error_info['suggestion']}"
                        logger.error(f"Load rejected: Machine state {state} ({state_text})")
                except Exception as state_exc:
                    logger.debug("Could not check machine state: %s", state_exc)
                    message = f"{error_info['message']}. {error_info['suggestion']}"
            else:
                # Add detailed info to message for other errors
                message = f"{error_info['message']}. {error_info['suggestion']}"
    except FileNotFoundError as exc:
        result = 20  # CNC_RC_ERR_FILEOPEN
        error_info = translate_error(result)
        message = f"File not found: {exc}. {error_info['suggestion']}"
        logger.error(message)
        file_path = ""
    except ValueError as exc:
        result = 9  # CNC_RC_ERR_PAR
        error_info = translate_error(result)
        message = f"File search error: {exc}. {error_info['suggestion']}"
        logger.error(message)
        file_path = ""
    except Exception as exc:
        import traceback
        traceback.print_exc()
        result = -1
        error_info = translate_error(result)
        message = f"Exception calling LoadJob: {exc}. {error_info['suggestion']}"
        logger.error(message, exc_info=True)  # Log full stack trace
        file_path = ""

    logger.debug("LOAD JOB response — status=%d, message=%s, fileName=%s", result, message, file_path)
    return LoadJobResponse.model_construct(
        status=result, message=message, fileName=file_path
    )
