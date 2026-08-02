"""Configuration management API endpoints."""

import asyncio
import logging
import socket
from fastapi import APIRouter, Request
from pydantic import BaseModel, Field
from src.core.config_persistence import get_persisted_config, update_persisted_config
from src.core.task_config import (
    configure_task_launch_account,
    get_task_launch_settings,
    restart_scheduled_adapter_task,
    set_adapter_autostart_enabled,
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
    cnc_share_username: str | None = Field(None, min_length=1, max_length=200, description="Username for authenticating the CNC job file share")
    cnc_share_password: str | None = Field(None, min_length=1, max_length=500, description="Password for authenticating the CNC job file share")
    run_as_windows_user: bool | None = Field(None, description="Run scheduled startup tasks under a Windows user instead of SYSTEM")
    task_username: str | None = Field(None, min_length=1, max_length=200, description=r"Windows account in DOMAIN\username or .\username form")
    task_password: str | None = Field(None, min_length=1, max_length=500, description="Windows password for the scheduled task account")
    restart_adapter_task: bool | None = Field(None, description="Restart the scheduled adapter task immediately after applying configuration")
    port: int | None = Field(None, ge=1, le=65535, description="HTTP port for the adapter; restart required to bind the new port")
    cnc_retry_interval: int | None = Field(None, ge=1, le=300, description="Seconds between connection retries")
    cnc_health_interval: int | None = Field(None, ge=1, le=300, description="Seconds between heartbeat checks")
    cnc_startup_ready_timeout: int | None = Field(None, ge=5, le=600, description="Seconds to wait for CNC machine readiness after connecting")
    auto_start_adapter_on_logon: bool | None = Field(None, description="Start the adapter automatically when the configured Windows account logs on")
    adapter_startup_delay_seconds: int | None = Field(None, ge=0, le=600, description="Delay before scheduled boot/logon adapter startup")
    auto_start_cnc_server: bool | None = Field(None, description="Start CncServer.exe automatically when the adapter starts")
    auto_start_eding_gui: bool | None = Field(None, description="Start the Eding CNC GUI after the adapter confirms CNC readiness")
    show_operator_ready_message: bool | None = Field(None, description="Legacy ready popup setting; START-CNC splash/feedback is used for normal readiness display")
    job_monitor_poll_interval: float | None = Field(None, ge=0.1, le=60.0, description="Seconds between job monitor status checks")
    jog_pad_pause_hold_interval_ms: int | None = Field(None, ge=0, le=10000, description="Milliseconds between jog-pad pause hold requests; 0 disables")
    physical_button_poll_interval_ms: int | None = Field(None, ge=20, le=10000, description="Milliseconds between backend physical RUN/PAUSE input checks")
    update_username: str | None = Field(None, min_length=1, max_length=200, description="Username for authenticated update catalog/package downloads")
    update_password: str | None = Field(None, min_length=1, max_length=500, description="Password for authenticated update catalog/package downloads")


class ConfigResponse(BaseModel):
    """Current configuration response."""
    machine_number: str
    job_done_report_url: str
    base_dir: str
    cnc_share_username: str
    cnc_share_password_configured: bool
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
    cnc_startup_ready_timeout: int
    auto_start_adapter_on_logon: bool
    adapter_startup_delay_seconds: int
    auto_start_cnc_server: bool
    auto_start_eding_gui: bool
    show_operator_ready_message: bool
    job_monitor_poll_interval: float
    jog_pad_pause_hold_interval_ms: int
    physical_button_poll_interval_ms: int
    update_username: str
    update_password_configured: bool


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
            launch_settings = await asyncio.to_thread(get_task_launch_settings)
        except Exception as task_exc:
            logger.warning("Could not query scheduled task launch settings: %s", task_exc)
            launch_settings = {
                "run_as_windows_user": bool(settings.task_username),
                "task_username": settings.task_username,
                "task_password_configured": bool(settings.task_username),
                "auto_start_adapter_on_logon": settings.auto_start_adapter_on_logon,
                "adapter_startup_delay_seconds": settings.adapter_startup_delay_seconds,
            }

        persisted_config = await asyncio.to_thread(get_persisted_config)

        return ConfigResponse(
            machine_number=settings.machine_number,
            job_done_report_url=settings.job_done_report_url,
            base_dir=settings.base_dir,
            cnc_share_username=str(persisted_config.get("cnc_share_username", settings.cnc_share_username) or ""),
            cnc_share_password_configured=bool(persisted_config.get("cnc_share_password", settings.cnc_share_password)),
            run_as_windows_user=bool(launch_settings["run_as_windows_user"]),
            task_username=str(launch_settings["task_username"]),
            task_password_configured=bool(launch_settings["task_password_configured"]),
            dll_path=settings.dll_path,
            ini_path=settings.ini_path,
            host=settings.host,
            local_ip=await asyncio.to_thread(get_machine_ip),
            port=settings.port,
            log_level=settings.log_level,
            cnc_retry_interval=settings.cnc_retry_interval,
            cnc_health_interval=settings.cnc_health_interval,
            cnc_startup_ready_timeout=settings.cnc_startup_ready_timeout,
            auto_start_adapter_on_logon=bool(launch_settings.get("auto_start_adapter_on_logon", settings.auto_start_adapter_on_logon)),
            adapter_startup_delay_seconds=int(launch_settings.get("adapter_startup_delay_seconds", settings.adapter_startup_delay_seconds)),
            auto_start_cnc_server=settings.auto_start_cnc_server,
            auto_start_eding_gui=settings.auto_start_eding_gui,
            show_operator_ready_message=settings.show_operator_ready_message,
            job_monitor_poll_interval=settings.job_monitor_poll_interval,
            jog_pad_pause_hold_interval_ms=settings.jog_pad_pause_hold_interval_ms,
            physical_button_poll_interval_ms=settings.physical_button_poll_interval_ms,
            update_username=str(persisted_config.get("update_username", "") or ""),
            update_password_configured=bool(persisted_config.get("update_password", "")),
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

        if config.cnc_share_username is not None:
            old_value = settings.cnc_share_username
            settings.cnc_share_username = config.cnc_share_username
            changes.append("cnc_share_username: updated")
            logger.info("Updated cnc_share_username: %s -> %s", old_value, config.cnc_share_username)

        if config.cnc_share_password is not None:
            settings.cnc_share_password = config.cnc_share_password
            changes.append("cnc_share_password: updated")
            logger.info("Updated cnc_share_password: configured")

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

        # Update CNC startup ready timeout
        if config.cnc_startup_ready_timeout is not None:
            old_value = settings.cnc_startup_ready_timeout
            settings.cnc_startup_ready_timeout = config.cnc_startup_ready_timeout
            changes.append(f"cnc_startup_ready_timeout: {old_value} -> {config.cnc_startup_ready_timeout}")
            logger.info("Updated cnc_startup_ready_timeout: %s -> %s", old_value, config.cnc_startup_ready_timeout)

            if hasattr(services, 'connection_manager') and services.connection_manager is not None:
                services.connection_manager._startup_ready_timeout = config.cnc_startup_ready_timeout
                logger.info("Updated active connection manager startup ready timeout")

        if config.auto_start_cnc_server is not None:
            old_value = settings.auto_start_cnc_server
            settings.auto_start_cnc_server = config.auto_start_cnc_server
            changes.append(f"auto_start_cnc_server: {old_value} -> {config.auto_start_cnc_server}")
            logger.info("Updated auto_start_cnc_server: %s -> %s", old_value, config.auto_start_cnc_server)

        if config.auto_start_adapter_on_logon is not None:
            old_value = settings.auto_start_adapter_on_logon
            settings.auto_start_adapter_on_logon = config.auto_start_adapter_on_logon
            if old_value != config.auto_start_adapter_on_logon:
                set_adapter_autostart_enabled(config.auto_start_adapter_on_logon)
            changes.append(f"auto_start_adapter_on_logon: {old_value} -> {config.auto_start_adapter_on_logon}")
            logger.info("Updated auto_start_adapter_on_logon: %s -> %s", old_value, config.auto_start_adapter_on_logon)

        if config.adapter_startup_delay_seconds is not None:
            old_value = settings.adapter_startup_delay_seconds
            settings.adapter_startup_delay_seconds = config.adapter_startup_delay_seconds
            if old_value != config.adapter_startup_delay_seconds:
                launch_settings = configure_task_launch_account(
                    task_username=settings.task_username,
                    task_password="",
                    auto_start_enabled=settings.auto_start_adapter_on_logon,
                    startup_delay_seconds=settings.adapter_startup_delay_seconds,
                )
                settings.task_username = str(launch_settings["task_username"])
            changes.append(f"adapter_startup_delay_seconds: {old_value} -> {config.adapter_startup_delay_seconds}")
            logger.info("Updated adapter_startup_delay_seconds: %s -> %s", old_value, config.adapter_startup_delay_seconds)

        if config.auto_start_eding_gui is not None:
            old_value = settings.auto_start_eding_gui
            settings.auto_start_eding_gui = config.auto_start_eding_gui
            changes.append(f"auto_start_eding_gui: {old_value} -> {config.auto_start_eding_gui}")
            logger.info("Updated auto_start_eding_gui: %s -> %s", old_value, config.auto_start_eding_gui)

        if config.show_operator_ready_message is not None:
            old_value = settings.show_operator_ready_message
            settings.show_operator_ready_message = config.show_operator_ready_message
            changes.append(f"show_operator_ready_message: {old_value} -> {config.show_operator_ready_message}")
            logger.info("Updated show_operator_ready_message: %s -> %s", old_value, config.show_operator_ready_message)

        # Update job monitor poll interval
        if config.job_monitor_poll_interval is not None:
            old_value = settings.job_monitor_poll_interval
            settings.job_monitor_poll_interval = config.job_monitor_poll_interval
            changes.append(f"job_monitor_poll_interval: {old_value} -> {config.job_monitor_poll_interval}")
            logger.info("Updated job_monitor_poll_interval: %s -> %s", old_value, config.job_monitor_poll_interval)

            if hasattr(services, 'job_monitor') and services.job_monitor is not None:
                services.job_monitor._poll_interval = config.job_monitor_poll_interval
                logger.info("Updated active job monitor poll interval")

        # Update jog pad pause hold interval
        if config.jog_pad_pause_hold_interval_ms is not None:
            old_value = settings.jog_pad_pause_hold_interval_ms
            settings.jog_pad_pause_hold_interval_ms = config.jog_pad_pause_hold_interval_ms
            changes.append(f"jog_pad_pause_hold_interval_ms: {old_value} -> {config.jog_pad_pause_hold_interval_ms}")
            logger.info("Updated jog_pad_pause_hold_interval_ms: %s -> %s", old_value, config.jog_pad_pause_hold_interval_ms)

        # Update backend physical button poll interval
        if config.physical_button_poll_interval_ms is not None:
            old_value = settings.physical_button_poll_interval_ms
            settings.physical_button_poll_interval_ms = config.physical_button_poll_interval_ms
            changes.append(f"physical_button_poll_interval_ms: {old_value} -> {config.physical_button_poll_interval_ms}")
            logger.info("Updated physical_button_poll_interval_ms: %s -> %s", old_value, config.physical_button_poll_interval_ms)

            if hasattr(services, "physical_button_service") and services.physical_button_service is not None:
                services.physical_button_service._poll_interval = max(0.01, config.physical_button_poll_interval_ms / 1000.0)
                logger.info("Updated active physical button monitor poll interval")

        # Update SVN/update credentials
        if config.update_username is not None:
            changes.append("update_username: updated")
            logger.info("Updated update_username: %s", config.update_username)

        if config.update_password is not None:
            changes.append("update_password: updated")
            logger.info("Updated update_password: configured")

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
            else:
                requested_username = ""

            launch_settings = configure_task_launch_account(
                task_username=requested_username,
                task_password=requested_password,
                auto_start_enabled=settings.auto_start_adapter_on_logon,
                startup_delay_seconds=settings.adapter_startup_delay_seconds,
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
        if config.cnc_share_username is not None:
            persist_dict["cnc_share_username"] = config.cnc_share_username
        if config.cnc_share_password is not None:
            persist_dict["cnc_share_password"] = config.cnc_share_password
        if task_config_changed:
            persist_dict["task_username"] = settings.task_username
        if config.port is not None:
            persist_dict["port"] = config.port
        if config.cnc_retry_interval is not None:
            persist_dict["cnc_retry_interval"] = config.cnc_retry_interval
        if config.cnc_health_interval is not None:
            persist_dict["cnc_health_interval"] = config.cnc_health_interval
        if config.cnc_startup_ready_timeout is not None:
            persist_dict["cnc_startup_ready_timeout"] = config.cnc_startup_ready_timeout
        if config.auto_start_cnc_server is not None:
            persist_dict["auto_start_cnc_server"] = config.auto_start_cnc_server
        if config.auto_start_adapter_on_logon is not None:
            persist_dict["auto_start_adapter_on_logon"] = config.auto_start_adapter_on_logon
        if config.adapter_startup_delay_seconds is not None:
            persist_dict["adapter_startup_delay_seconds"] = config.adapter_startup_delay_seconds
        if config.auto_start_eding_gui is not None:
            persist_dict["auto_start_eding_gui"] = config.auto_start_eding_gui
        if config.show_operator_ready_message is not None:
            persist_dict["show_operator_ready_message"] = config.show_operator_ready_message
        if config.job_monitor_poll_interval is not None:
            persist_dict["job_monitor_poll_interval"] = config.job_monitor_poll_interval
        if config.jog_pad_pause_hold_interval_ms is not None:
            persist_dict["jog_pad_pause_hold_interval_ms"] = config.jog_pad_pause_hold_interval_ms
        if config.physical_button_poll_interval_ms is not None:
            persist_dict["physical_button_poll_interval_ms"] = config.physical_button_poll_interval_ms
        if config.update_username is not None:
            persist_dict["update_username"] = config.update_username
        if config.update_password is not None:
            persist_dict["update_password"] = config.update_password

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
