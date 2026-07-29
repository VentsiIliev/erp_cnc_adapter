import logging

from fastapi import APIRouter, Depends

from src.cnc.cnc_client_protocol import CncClientProtocol
from src.cnc.error_translator import format_error
from src.core.app_state import get_cnc_client

from .schemas.job import CncHomedResponse, CncMotionResponse, CncPhysicalButtonStatusResponse, CncPositionResponse, JogCommandRequest, MoveCommandRequest, SetWorkCoordinateRequest, ZeroAxisRequest

logger = logging.getLogger(__name__)

router = APIRouter()

PAUSE_HOLD_JOB_RUNNING_STATES = {6}
PAUSED_STATES = {11, 12, 13, 14, 15}


def _axis(value: str) -> str:
    return value.upper()


def _message(
    result: int,
    operation: str,
    success_message: str,
    client: CncClientProtocol | None = None,
) -> str:
    if client is not None:
        cnc_message = client.get_last_cnc_message()
        if cnc_message:
            return cnc_message
    if result == 0:
        return success_message
    return format_error(result, operation)



@router.post("/api/cnc/messages/clear", response_model=CncMotionResponse)
async def clear_cnc_messages(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Clear stale operator-facing CNC FIFO messages."""
    logger.info("CNC message FIFO clear requested")
    client.clear_cnc_messages()
    return CncMotionResponse(
        status=0,
        message="CNC message FIFO cleared",
        command="clear_messages",
        dry_run=False,
    )

@router.get("/api/cnc/position", response_model=CncPositionResponse)
async def get_position(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Return current CNC work and machine coordinates."""
    positions = client.get_positions()
    return CncPositionResponse(
        status=0,
        message="CNC position read successfully",
        work=positions.get("work", {}),
        machine=positions.get("machine", {}),
    )



@router.get("/api/cnc/physical-buttons", response_model=CncPhysicalButtonStatusResponse)
async def get_physical_button_status(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Return physical run/pause input states for diagnostics only."""
    status = client.get_physical_button_status()
    return CncPhysicalButtonStatusResponse(
        status=0,
        message="CNC physical button status read successfully",
        runInput=bool(status.get("runInput", False)),
        pauseInput=bool(status.get("pauseInput", False)),
        runRaw=int(status.get("runRaw", 0)),
        pauseRaw=int(status.get("pauseRaw", 0)),
        runLogical=int(status.get("runLogical", 0)),
        pauseLogical=int(status.get("pauseLogical", 0)),
    )


@router.get("/api/cnc/homed", response_model=CncHomedResponse)
async def get_homed_status(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Return whether all CNC axes are homed."""
    all_axes_homed = client.get_all_axes_homed()
    return CncHomedResponse(
        status=0,
        message="All axes are homed" if all_axes_homed else "Not all axes are homed",
        all_axes_homed=all_axes_homed,
    )



@router.post("/api/cnc/home", response_model=CncMotionResponse)
async def home_all_axes(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Run the configured Eding CNC home_all macro."""
    logger.info("CNC all-axis home requested via macro: gosub home_all")
    result = client.home_all_axes_sequence()
    return CncMotionResponse(
        status=result,
        message=_message(result, "Home all axes", "CNC home_all macro completed: gosub home_all returned 0", client),
        command="home",
        dry_run=False,
    )


@router.post("/api/cnc/reset", response_model=CncMotionResponse)
async def reset_cnc(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Recover CNC from error states via the DLL reset function."""
    logger.info("CNC reset requested")
    result = client.reset()
    return CncMotionResponse(
        status=result,
        message=_message(result, "Reset", "CNC DLL accepted reset command: CncReset returned 0", client),
        command="reset",
        dry_run=False,
    )


@router.post("/api/cnc/job/pause", response_model=CncMotionResponse)
async def pause_job(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Keep the CNC job paused without blocking when no job is running."""
    logger.info("CNC job pause requested")
    try:
        state = client.get_state()
    except Exception as exc:
        logger.debug("Could not read CNC state before pause: %s", exc)
        state = None

    if state in PAUSED_STATES:
        return CncMotionResponse(
            status=0,
            message=f"Pause hold active: CNC is already paused (state {state})",
            command="pause_job",
            dry_run=False,
        )

    if state not in PAUSE_HOLD_JOB_RUNNING_STATES:
        return CncMotionResponse(
            status=0,
            message=f"Pause hold idle: no running job is active (state {state})",
            command="pause_job",
            dry_run=False,
        )

    result = client.pause_job()
    message = (
        "Pause hold active: running job was paused by the jog pad hold. "
        "Press Proceed to release the jog pad hold before continuing."
        if result == 0
        else format_error(result, "Pause job")
    )
    return CncMotionResponse(
        status=result,
        message=message,
        command="pause_job",
        dry_run=False,
    )

@router.post("/api/cnc/jog", response_model=CncMotionResponse)
async def jog_axis(
    payload: JogCommandRequest,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Send a single-axis jog command to CNC."""
    axis = _axis(payload.axis)
    logger.info(
        "CNC jog requested: axis=%s direction=%s step=%s velocity_factor=%s continuous=%s",
        axis,
        payload.direction,
        payload.step,
        payload.velocity_factor,
        payload.continuous,
    )
    try:
        motion_enabled = client.is_motion_enabled()
        if not motion_enabled:
            logger.info("CNC motionEnabled is false before jog; continuing because CncStartJog2 is authoritative")
    except Exception as exc:
        logger.debug("Could not read CNC motion-enabled status before jog: %s", exc)

    result = client.start_jog(
        axis=axis,
        direction=payload.direction,
        step=payload.step,
        velocity_factor=payload.velocity_factor,
        continuous=payload.continuous,
    )
    return CncMotionResponse(
        status=result,
        message=_message(result, "Jog", "CNC DLL accepted jog command: CncStartJog2 returned 0", client),
        command="jog",
        dry_run=False,
        axis=axis,
        direction=payload.direction,
        step=payload.step,
        velocity_factor=payload.velocity_factor,
        continuous=payload.continuous,
    )


@router.post("/api/cnc/jog/stop", response_model=CncMotionResponse)
async def stop_jog(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Stop any active CNC jog."""
    logger.info("CNC jog stop requested")
    result = client.stop_jog()
    return CncMotionResponse(
        status=result,
        message=_message(result, "Stop jog", "CNC DLL accepted jog stop command: CncStopJog returned 0", client),
        command="jog_stop",
        dry_run=False,
    )


@router.post("/api/cnc/move", response_model=CncMotionResponse)
async def move_axis(
    payload: MoveCommandRequest,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Move one axis to an absolute machine position."""
    axis = _axis(payload.axis)
    logger.info(
        "CNC move requested: axis=%s position=%s velocity_factor=%s",
        axis,
        payload.position,
        payload.velocity_factor,
    )
    result = client.move_to(
        axis=axis,
        position=payload.position,
        velocity_factor=payload.velocity_factor,
    )
    return CncMotionResponse(
        status=result,
        message=_message(result, "Move", "CNC DLL accepted move command: CncMoveTo returned 0", client),
        command="move",
        dry_run=False,
        axis=axis,
        position=payload.position,
        velocity_factor=payload.velocity_factor,
    )

@router.post("/api/cnc/zero", response_model=CncMotionResponse)
async def zero_axis(
    payload: ZeroAxisRequest,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Set the current position as work zero for one axis."""
    axis = _axis(payload.axis)
    logger.info("CNC work zero requested: axis=%s", axis)
    result = client.zero_work_axis(axis=axis)
    return CncMotionResponse(
        status=result,
        message=_message(result, "Zero work axis", "CNC DLL zeroed work axis: G10 L20 and CncStoreIniFile returned 0", client),
        command="zero",
        dry_run=False,
        axis=axis,
    )

@router.post("/api/cnc/work-coordinate", response_model=CncMotionResponse)
async def set_work_coordinate(
    payload: SetWorkCoordinateRequest,
    client: CncClientProtocol = Depends(get_cnc_client),
):
    """Set the displayed work coordinate value for one axis using G92."""
    axis = _axis(payload.axis)
    logger.info("CNC G92 work coordinate requested: axis=%s value=%s", axis, payload.value)
    result = client.set_work_coordinate(axis=axis, value=payload.value)
    return CncMotionResponse(
        status=result,
        message=_message(result, "Set work coordinate", "CNC DLL set work coordinate: G92 and CncStoreIniFile returned 0", client),
        command="set_work_coordinate",
        dry_run=False,
        axis=axis,
        position=payload.value,
    )
