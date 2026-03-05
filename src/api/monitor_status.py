"""Monitor status API endpoint for the test page."""

import logging
from fastapi import APIRouter, Request

logger = logging.getLogger(__name__)
router = APIRouter()

# CNC state map
STATE_MAP = {
    0: "Power-up", 1: "Idle", 2: "Ready", 3: "Execution error", 4: "Internal error",
    5: "Aborted", 6: "Running job", 7: "Running line", 8: "Running sub",
    9: "Running sub search", 10: "Running line search", 11: "Paused (line)",
    12: "Paused (job)", 13: "Paused (sub)", 14: "Paused (line search)",
    15: "Paused (sub search)", 16: "Running handwheel", 17: "Running line handwheel",
    18: "Running line paused", 19: "Running axis jog", 20: "Running IP jog",
    21: "Rendering graph", 22: "Searching", 23: "Search done",
}


@router.get("/api/cnc/monitor/status")
async def get_monitor_status(request: Request):
    """Get the current job monitor status with real-time job data."""
    try:
        services = request.app.state.services

        if not hasattr(services, 'job_monitor') or services.job_monitor is None:
            return {
                "monitoring": False,
                "current_job": "",
                "job_info": {},
                "last_report_status": None,
                "state": 0,
                "stateText": "Unknown",
            }

        monitor = services.job_monitor
        status = monitor.get_current_status()

        # Get real-time job status from CNC
        try:
            cnc_client = services.cnc_client
            state = cnc_client.get_state()
            state_text = STATE_MAP.get(state, f"Unknown state: {state}")
            job_status = cnc_client.get_job_status()

            # Combine monitor status with real-time job data
            return {
                "monitoring": status.get("monitoring", False),
                "was_running": status.get("was_running", False),
                "current_job": status.get("current_job", ""),
                "job_info": status.get("job_info", {}),
                "last_report_status": status.get("last_report_status"),

                # Real-time CNC state and job data
                "state": state,
                "stateText": state_text,
                "jobName": job_status.get("jobName", ""),
                "totalJobLengthMm": job_status.get("totalJobLengthMm", 0),
                "jobProgressMm": job_status.get("jobProgressMm", 0),
                "jobProgressPercentage": job_status.get("jobProgressPercentage", 0),
                "jobActualRunningTimeSeconds": job_status.get("jobActualRunningTimeSeconds", 0),
                "jobRemainingRunningTimeSeconds": job_status.get("jobRemainingRunningTimeSeconds", 0),
                "jobEstimatedTimeSeconds": job_status.get("jobEstimatedTimeSeconds", 0),
                "currentRepeat": job_status.get("currentRepeat", 0),
                "nrOfJobRepeatsSet": job_status.get("nrOfJobRepeatsSet", 0),
            }
        except Exception as job_exc:
            logger.debug("Could not get job status: %s", job_exc)
            # Return monitor status only if can't get job data
            return {
                "monitoring": status.get("monitoring", False),
                "was_running": status.get("was_running", False),
                "current_job": status.get("current_job", ""),
                "job_info": status.get("job_info", {}),
                "last_report_status": status.get("last_report_status"),
                "state": 0,
                "stateText": "Unknown",
            }

    except Exception as exc:
        logger.error("Error getting monitor status: %s", exc)
        return {
            "monitoring": False,
            "current_job": "",
            "job_info": {},
            "last_report_status": None,
            "state": 0,
            "stateText": "Unknown",
            "error": str(exc),
        }

