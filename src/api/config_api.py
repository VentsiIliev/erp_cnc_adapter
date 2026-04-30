"""Configuration management API endpoints."""

import logging
import socket
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from src.core.config_persistence import update_persisted_config
from src.core.task_config import (
    configure_task_launch_account,
    get_task_launch_settings,
    restart_scheduled_adapter_task,
)

logger = logging.getLogger(__name__)
router = APIRouter()


class ConfigUpdate(BaseModel):
    """Configuration update request."""
    machine_number: str | None = Field(None, min_length=1, max_length=50, description="Machine identifier (e.g., CNC1, CNC2)")
    dll_path: str | None = Field(None, min_length=1, max_length=500, description="Path to cncapi.dll")
    ini_path: str | None = Field(None, min_length=1, max_length=500, description="Path to cnc.ini")
    job_done_report_url: str | None = Field(None, min_length=1, max_length=500, description="URL to report job completion")
    base_dir: str | None = Field(None, min_length=1, max_length=500, description="Base directory for job files")
    run_as_windows_user: bool | None = Field(None, description="Run scheduled startup tasks under a Windows user instead of SYSTEM")
    task_username: str | None = Field(None, min_length=1, max_length=200, description=r"Windows account in DOMAIN\username or .\username form")
    task_password: str | None = Field(None, min_length=1, max_length=500, description="Windows password for the scheduled task account")
    restart_adapter_task: bool | None = Field(None, description="Restart the scheduled adapter task immediately after applying configuration")
    port: int | None = Field(None, ge=1, le=65535, description="HTTP port for the adapter; restart required to bind the new port")
    cnc_retry_interval: int | None = Field(None, ge=1, le=300, description="Seconds between connection retries")
    cnc_health_interval: int | None = Field(None, ge=1, le=300, description="Seconds between heartbeat checks")
    job_monitor_poll_interval: float | None = Field(None, ge=0.1, le=60.0, description="Seconds between job monitor status checks")


class ConfigResponse(BaseModel):
    """Current configuration response."""
    machine_number: str
    job_done_report_url: str
    base_dir: str
    run_as_windows_user: bool
    task_username: str
    task_password_configured: bool
    dll_path: str
    ini_path: str
    host: str
    local_ip: str
    port: int
    log_level: str
    cnc_retry_interval: int
    cnc_health_interval: int
    job_monitor_poll_interval: float


def get_machine_ip() -> str:
    """Best-effort LAN IP for operators to reach this adapter."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except OSError:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except OSError:
            ip = "127.0.0.1"
    finally:
        sock.close()
    return ip


@router.get("/api/config", response_model=ConfigResponse)
async def get_config(request: Request):
    """Get current configuration."""
    logger.debug("GET /api/config - Retrieve current configuration")

    try:
        services = request.app.state.services
        settings = services.settings
        try:
            launch_settings = get_task_launch_settings()
        except Exception as task_exc:
            logger.warning("Could not query scheduled task launch settings: %s", task_exc)
            launch_settings = {
                "run_as_windows_user": bool(settings.task_username),
                "task_username": settings.task_username,
                "task_password_configured": bool(settings.task_username),
            }

        return ConfigResponse(
            machine_number=settings.machine_number,
            job_done_report_url=settings.job_done_report_url,
            base_dir=settings.base_dir,
            run_as_windows_user=bool(launch_settings["run_as_windows_user"]),
            task_username=str(launch_settings["task_username"]),
            task_password_configured=bool(launch_settings["task_password_configured"]),
            dll_path=settings.dll_path,
            ini_path=settings.ini_path,
            host=settings.host,
            local_ip=get_machine_ip(),
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
        task_config_changed = any(
            value is not None
            for value in (config.run_as_windows_user, config.task_username, config.task_password)
        )

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
        if config.dll_path is not None:
            old_value = settings.dll_path
            settings.dll_path = config.dll_path
            changes.append(f"dll_path: '{old_value}' -> '{config.dll_path}'")
            logger.info("Updated dll_path: %s -> %s", old_value, config.dll_path)

        if config.ini_path is not None:
            old_value = settings.ini_path
            settings.ini_path = config.ini_path
            changes.append(f"ini_path: '{old_value}' -> '{config.ini_path}'")
            logger.info("Updated ini_path: %s -> %s", old_value, config.ini_path)

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
        if config.port is not None:
            old_value = settings.port
            settings.port = config.port
            changes.append(f"port: {old_value} -> {config.port} (restart required)")
            logger.info("Updated adapter port: %s -> %s", old_value, config.port)

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

        if task_config_changed:
            requested_run_as_user = (
                config.run_as_windows_user
                if config.run_as_windows_user is not None
                else bool(settings.task_username)
            )
            requested_username = (
                config.task_username.strip()
                if config.task_username is not None
                else settings.task_username
            )
            requested_password = config.task_password or ""

            if requested_run_as_user:
                if not requested_username:
                    return {
                        "success": False,
                        "message": "A Windows task username is required when 'Run as Windows user' is enabled.",
                        "changes": [],
                    }
                if not requested_password:
                    return {
                        "success": False,
                        "message": "A Windows task password is required to create or update scheduled task credentials.",
                        "changes": [],
                    }
            else:
                requested_username = ""

            launch_settings = configure_task_launch_account(
                task_username=requested_username,
                task_password=requested_password,
            )
            old_username = settings.task_username
            settings.task_username = str(launch_settings["task_username"])
            if requested_run_as_user:
                changes.append(f"task_username: '{old_username or 'SYSTEM'}' -> '{requested_username}'")
            else:
                changes.append(f"task_username: '{old_username or 'SYSTEM'}' -> 'SYSTEM'")
            logger.info("Updated scheduled task launch account")

        if config.restart_adapter_task:
            restart_scheduled_adapter_task()
            changes.append("adapter_task: restart requested")
            logger.info("Requested scheduled adapter task restart")

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
        if config.dll_path is not None:
            persist_dict["dll_path"] = config.dll_path
        if config.ini_path is not None:
            persist_dict["ini_path"] = config.ini_path
        if config.job_done_report_url is not None:
            persist_dict["job_done_report_url"] = config.job_done_report_url
        if config.base_dir is not None:
            persist_dict["base_dir"] = config.base_dir
        if task_config_changed:
            persist_dict["task_username"] = settings.task_username
        if config.port is not None:
            persist_dict["port"] = config.port
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

