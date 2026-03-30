"""Configuration management API endpoints."""

import logging
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from src.core.config_persistence import update_persisted_config

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    machine_number: str | None = Field(None, min_length=1, max_length=50, description="Machine identifier (e.g., CNC1, CNC2)")
    job_done_report_url: str | None = Field(None, min_length=1, max_length=500, description="URL to report job completion")
    base_dir: str | None = Field(None, min_length=1, max_length=500, description="Base directory for job files")
    cnc_retry_interval: int | None = Field(None, ge=1, le=300, description="Seconds between connection retries")
    cnc_health_interval: int | None = Field(None, ge=1, le=300, description="Seconds between heartbeat checks")
    job_monitor_poll_interval: float | None = Field(None, ge=0.1, le=60.0, description="Seconds between job monitor status checks")


class ConfigResponse(BaseModel):
    """Current configuration response."""
    machine_number: str
    job_done_report_url: str
    base_dir: str
    dll_path: str
    ini_path: str
    host: str
    port: int
    log_level: str
    cnc_retry_interval: int
    cnc_health_interval: int
    job_monitor_poll_interval: float


@router.get("/api/config", response_model=ConfigResponse)
async def get_config(request: Request):
    """Get current configuration."""
    logger.info("GET /api/config - Retrieve current configuration")

    try:
        services = request.app.state.services
        settings = services.settings

        return ConfigResponse(
            machine_number=settings.machine_number,
            job_done_report_url=settings.job_done_report_url,
            base_dir=settings.base_dir,
            dll_path=settings.dll_path,
            ini_path=settings.ini_path,
            host=settings.host,
            port=settings.port,
            log_level=settings.log_level,
            cnc_retry_interval=settings.cnc_retry_interval,
            cnc_health_interval=settings.cnc_health_interval,
            job_monitor_poll_interval=settings.job_monitor_poll_interval,
        )
    except Exception as e:
        logger.error("Error getting configuration: %s", e)
        raise


@router.post("/api/config")
async def update_config(request: Request, config: ConfigUpdate):
    """Update configuration (changes apply immediately without restart)."""
    logger.info("POST /api/config - Update configuration")

    try:
        services = request.app.state.services
        settings = services.settings

        changes = []

        # Update machine number
        if config.machine_number is not None:
            old_value = settings.machine_number
            settings.machine_number = config.machine_number
            changes.append(f"machine_number: '{old_value}' -> '{config.machine_number}'")
            logger.info("Updated machine_number: %s -> %s", old_value, config.machine_number)

            # Update the job monitor's stored job info with new machine number
            if hasattr(services, 'job_monitor') and services.job_monitor is not None:
                if services.job_monitor._job_info:
                    # Preserve existing job number and step, update machine number
                    services.job_monitor._job_info["machine_number"] = config.machine_number
                    logger.info("Updated job monitor machine number to: %s", config.machine_number)

            # Update last_loaded_job if it exists
            if hasattr(services, 'last_loaded_job') and services.last_loaded_job:
                services.last_loaded_job["machine_number"] = config.machine_number
                logger.info("Updated last_loaded_job machine number to: %s", config.machine_number)

        # Update report URL
        if config.job_done_report_url is not None:
            old_value = settings.job_done_report_url
            settings.job_done_report_url = config.job_done_report_url
            changes.append(f"job_done_report_url: '{old_value}' -> '{config.job_done_report_url}'")
            logger.info("Updated job_done_report_url: %s -> %s", old_value, config.job_done_report_url)

            # Update the monitor's report URL if it exists
            if hasattr(services, 'job_monitor') and services.job_monitor is not None:
                services.job_monitor._report_url = config.job_done_report_url
                logger.info("Updated active job monitor report URL")

        # Update base directory
        if config.base_dir is not None:
            old_value = settings.base_dir
            settings.base_dir = config.base_dir
            changes.append(f"base_dir: '{old_value}' -> '{config.base_dir}'")
            logger.info("Updated base_dir: %s -> %s", old_value, config.base_dir)

        # Update CNC retry interval
        if config.cnc_retry_interval is not None:
            old_value = settings.cnc_retry_interval
            settings.cnc_retry_interval = config.cnc_retry_interval
            changes.append(f"cnc_retry_interval: {old_value} -> {config.cnc_retry_interval}")
            logger.info("Updated cnc_retry_interval: %s -> %s", old_value, config.cnc_retry_interval)

            if hasattr(services, 'connection_manager') and services.connection_manager is not None:
                services.connection_manager._retry_interval = config.cnc_retry_interval
                logger.info("Updated active connection manager retry interval")

        # Update CNC health interval
        if config.cnc_health_interval is not None:
            old_value = settings.cnc_health_interval
            settings.cnc_health_interval = config.cnc_health_interval
            changes.append(f"cnc_health_interval: {old_value} -> {config.cnc_health_interval}")
            logger.info("Updated cnc_health_interval: %s -> %s", old_value, config.cnc_health_interval)

            if hasattr(services, 'connection_manager') and services.connection_manager is not None:
                services.connection_manager._health_interval = config.cnc_health_interval
                logger.info("Updated active connection manager health interval")

        # Update job monitor poll interval
        if config.job_monitor_poll_interval is not None:
            old_value = settings.job_monitor_poll_interval
            settings.job_monitor_poll_interval = config.job_monitor_poll_interval
            changes.append(f"job_monitor_poll_interval: {old_value} -> {config.job_monitor_poll_interval}")
            logger.info("Updated job_monitor_poll_interval: %s -> %s", old_value, config.job_monitor_poll_interval)

            if hasattr(services, 'job_monitor') and services.job_monitor is not None:
                services.job_monitor._poll_interval = config.job_monitor_poll_interval
                logger.info("Updated active job monitor poll interval")

        if not changes:
            return {
                "success": True,
                "message": "No changes requested",
                "changes": []
            }

        # Persist configuration changes to file
        persist_dict = {}
        if config.machine_number is not None:
            persist_dict["machine_number"] = config.machine_number
        if config.job_done_report_url is not None:
            persist_dict["job_done_report_url"] = config.job_done_report_url
        if config.base_dir is not None:
            persist_dict["base_dir"] = config.base_dir
        if config.cnc_retry_interval is not None:
            persist_dict["cnc_retry_interval"] = config.cnc_retry_interval
        if config.cnc_health_interval is not None:
            persist_dict["cnc_health_interval"] = config.cnc_health_interval
        if config.job_monitor_poll_interval is not None:
            persist_dict["job_monitor_poll_interval"] = config.job_monitor_poll_interval

        if persist_dict:
            if update_persisted_config(persist_dict):
                logger.info("Configuration persisted to disk: %s", list(persist_dict.keys()))
            else:
                logger.warning("Failed to persist configuration to disk")

        logger.info("Configuration updated successfully: %s", ", ".join(changes))

        return {
            "success": True,
            "message": "Configuration updated successfully",
            "changes": changes
        }

    except Exception as e:
        logger.error("Error updating configuration: %s", e)
        return {
            "success": False,
            "message": f"Error updating configuration: {str(e)}",
            "changes": []
        }

