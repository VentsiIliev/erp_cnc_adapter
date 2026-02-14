import logging
import os
import shutil
import subprocess
import sys

from fastapi import APIRouter, UploadFile, File

from src.schemas.update import (
    BackupInfo,
    BackupListResponse,
    RollbackResponse,
    UpdateResponse,
)
from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/update", tags=["update"])

EXE_NAME = "erp-cnc-adapter.exe"
SERVICE_NAME = "ERPCNCAdapter"
MAX_BACKUPS = 5


def _get_project_root() -> str:
    """Project root: two levels up from this file (src/handlers/ -> project root)."""
    # When running from PyInstaller, sys.executable points to the actual EXE
    # When running from source, use the file path
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running from source
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_exe_path() -> str:
    """Find the EXE path using the same logic as service_exe.py."""
    root = _get_project_root()
    candidate = os.path.join(root, EXE_NAME)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(root, "dist", EXE_NAME)


def _get_exe_dir() -> str:
    return os.path.dirname(_get_exe_path())


def _list_backups() -> list[BackupInfo]:
    """List backup files sorted newest-first."""
    exe_dir = _get_exe_dir()
    backups = []
    try:
        for f in os.listdir(exe_dir):
            # Match both formats:
            # Old: erp-cnc-adapter.exe.bak.20260213_160042
            # New: erp-cnc-adapter.exe.v1.0.0.bak.20260213_160042
            if ".bak." in f and f.startswith(EXE_NAME):
                full = os.path.join(exe_dir, f)
                # Extract timestamp (last part after .bak.)
                parts = f.split(".bak.")
                if len(parts) == 2:
                    ts_part = parts[1]
                    size_mb = round(os.path.getsize(full) / (1024 * 1024), 2)
                    backups.append(BackupInfo(filename=f, timestamp=ts_part, size_mb=size_mb))
    except OSError:
        pass
    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return backups


def _rotate_backups() -> None:
    """Keep at most MAX_BACKUPS backup files; delete the oldest."""
    backups = _list_backups()
    if len(backups) <= MAX_BACKUPS:
        return
    exe_dir = _get_exe_dir()
    for old in backups[MAX_BACKUPS:]:
        path = os.path.join(exe_dir, old.filename)
        logger.info("Rotating out old backup: %s", old.filename)
        try:
            os.remove(path)
        except OSError as e:
            logger.warning("Failed to remove old backup %s: %s", old.filename, e)


def _spawn_updater(exe_path: str, staged_path: str) -> None:
    """Spawn update_worker.py as a fully detached process."""
    exe_dir = os.path.dirname(exe_path)

    # Find Python interpreter
    if getattr(sys, 'frozen', False):
        # Running as PyInstaller executable - find system Python
        python_paths = [
            r"C:\Python311-32\python.exe",
            r"C:\Python311\python.exe",
            r"C:\Python310-32\python.exe",
            r"C:\Python310\python.exe",
            r"C:\Python39-32\python.exe",
            r"C:\Python39\python.exe",
            shutil.which("python"),  # Try PATH
        ]
        python_exe = None
        for path in python_paths:
            if path and os.path.exists(path):
                python_exe = path
                break

        if not python_exe:
            logger.error("Could not find Python interpreter for update worker")
            raise RuntimeError("Python interpreter not found. Please ensure Python is installed.")

        # When frozen, update_worker.py is in sys._MEIPASS/src/update_worker.py
        # Copy it to the installation directory so it's accessible after this process ends
        worker_source = os.path.join(sys._MEIPASS, "src", "update_worker.py")
        worker = os.path.join(exe_dir, "update_worker.py")

        if not os.path.exists(worker_source):
            logger.error("Update worker script not found at: %s", worker_source)
            raise RuntimeError(f"Update worker script not found: {worker_source}")

        # Copy the worker script to installation directory
        try:
            shutil.copy2(worker_source, worker)
            logger.info("Copied update worker to: %s", worker)
        except Exception as e:
            logger.error("Failed to copy update worker: %s", e)
            raise RuntimeError(f"Failed to copy update worker: {e}")
    else:
        # Running from source
        python_exe = sys.executable
        worker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update_worker.py")

        if not os.path.exists(worker):
            logger.error("Update worker script not found at: %s", worker)
            raise RuntimeError(f"Update worker script not found: {worker}")

    # Build command for update worker
    worker_cmd = f'"{python_exe}" "{worker}" --exe-path "{exe_path}" --staged-path "{staged_path}" --service-name {SERVICE_NAME}'

    logger.info("Spawning update worker: %s", worker_cmd)

    try:
        # Use CREATE_NO_WINDOW to hide console, and CREATE_NEW_PROCESS_GROUP for independence
        # This combination should work reliably even from a service
        CREATE_NO_WINDOW = 0x08000000
        CREATE_NEW_PROCESS_GROUP = 0x00000200

        subprocess.Popen(
            [python_exe, worker, "--exe-path", exe_path, "--staged-path", staged_path, "--service-name", SERVICE_NAME],
            creationflags=CREATE_NO_WINDOW | CREATE_NEW_PROCESS_GROUP,
            close_fds=False,
        )
        logger.info("Update worker spawned successfully")
    except Exception as e:
        logger.error("Failed to spawn update worker: %s", e)
        raise


@router.post("", response_model=UpdateResponse)
async def upload_update(file: UploadFile = File(...)):
    """Accept a new EXE upload and schedule a self-update."""
    # Validate filename
    if not file.filename or not file.filename.lower().endswith(".exe"):
        return UpdateResponse(status=1, message="Uploaded file must be an .exe file.")

    # Read content and validate size
    content = await file.read()
    if len(content) == 0:
        return UpdateResponse(status=1, message="Uploaded file is empty.")

    exe_path = _get_exe_path()
    exe_dir = _get_exe_dir()
    staged_path = os.path.join(exe_dir, "staged-update.exe")

    # Ensure target directory exists
    os.makedirs(exe_dir, exist_ok=True)

    # Write staged file
    try:
        with open(staged_path, "wb") as f:
            f.write(content)
    except OSError as e:
        logger.error("Failed to write staged update: %s", e)
        return UpdateResponse(status=1, message=f"Failed to save staged file: {e}")

    size_mb = round(len(content) / (1024 * 1024), 2)

    # Log detailed update information
    logger.info("=" * 60)
    logger.info("UPDATE REQUEST RECEIVED")
    logger.info("  Current version: %s", VERSION)
    logger.info("  Uploaded file: %s", file.filename)
    logger.info("  File size: %.2f MB", size_mb)
    logger.info("  Staged at: %s", staged_path)
    logger.info("  Target EXE: %s", exe_path)
    logger.info("=" * 60)

    logger.info("Staged update saved: %s (%.2f MB)", staged_path, size_mb)

    # Rotate old backups
    _rotate_backups()

    # Spawn detached updater
    try:
        _spawn_updater(exe_path, staged_path)
    except Exception as e:
        logger.error("Failed to spawn update worker: %s", e)
        return UpdateResponse(status=1, message=f"Update failed: {e}")

    return UpdateResponse(
        status=0,
        message="Update scheduled. The service will restart shortly with the new version.",
        version_info=f"Uploaded {file.filename} ({size_mb} MB)",
    )


@router.post("/rollback", response_model=RollbackResponse)
async def rollback():
    """Revert to the most recent backup."""
    backups = _list_backups()
    if not backups:
        return RollbackResponse(status=1, message="No backups available for rollback.")

    latest = backups[0]
    exe_path = _get_exe_path()
    exe_dir = _get_exe_dir()
    backup_path = os.path.join(exe_dir, latest.filename)

    # Stage the backup as the update, then use the normal update flow
    staged_path = os.path.join(exe_dir, "staged-update.exe")
    try:
        shutil.copy2(backup_path, staged_path)
    except OSError as e:
        logger.error("Failed to stage backup for rollback: %s", e)
        return RollbackResponse(status=1, message=f"Failed to stage rollback: {e}")

    try:
        _spawn_updater(exe_path, staged_path)
    except Exception as e:
        logger.error("Failed to spawn rollback worker: %s", e)
        return RollbackResponse(status=1, message=f"Rollback failed: {e}")

    return RollbackResponse(
        status=0,
        message=f"Rollback to {latest.filename} scheduled. The service will restart shortly.",
    )


@router.get("/backups", response_model=BackupListResponse)
async def list_backups():
    """List available backup versions."""
    backups = _list_backups()
    return BackupListResponse(
        status=0,
        message=f"Found {len(backups)} backup(s).",
        backups=backups,
    )
