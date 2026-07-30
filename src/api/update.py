import asyncio
import base64
import json
import logging
import os
import shutil
import ssl
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request

from fastapi import APIRouter, UploadFile, File

from .schemas.update import BackupInfo, BackupListResponse, RollbackResponse, UpdateCheckResponse, UpdateResponse
from version import VERSION

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/update", tags=["update"])

EXE_NAME = "erp-cnc-adapter.exe"
SERVICE_NAME = "ERPCNCAdapter"
MAX_BACKUPS = 5
ZIP_UPDATE_SUFFIX = ".zip"
EXE_UPDATE_SUFFIX = ".exe"
DEFAULT_LATEST_JSON_URL = "https://192.168.2.101:8443/svn/2245_RouterRetrofit/trunk/release/latest.json"
UPDATE_DOWNLOAD_TIMEOUT_SECONDS = 30
UPDATE_VERIFY_TLS_ENV = "ERP_CNC_UPDATE_VERIFY_TLS"
UPDATE_USERNAME_ENV = "ERP_CNC_UPDATE_USERNAME"
UPDATE_PASSWORD_ENV = "ERP_CNC_UPDATE_PASSWORD"



def _get_project_root() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _get_exe_path() -> str:
    root = _get_project_root()
    candidate = os.path.join(root, EXE_NAME)
    if os.path.exists(candidate):
        return candidate
    return os.path.join(root, "dist", EXE_NAME)


def _get_exe_dir() -> str:
    return os.path.dirname(_get_exe_path())


def _backup_search_dirs() -> list[str]:
    exe_dir = _get_exe_dir()
    return [exe_dir, os.path.join(exe_dir, "backups")]


def _backup_info_from_file(directory: str, filename: str) -> BackupInfo | None:
    is_legacy_exe = filename.startswith(EXE_NAME) and ".bak." in filename
    is_full_backup = filename.startswith("install-backup-v") and filename.lower().endswith(".zip")
    if not is_legacy_exe and not is_full_backup:
        return None

    if is_legacy_exe:
        timestamp = filename.split(".bak.")[-1]
    else:
        base = filename[:-4]
        timestamp = base.rsplit(".", 1)[-1] if "." in base else "unknown"

    full = os.path.join(directory, filename)
    size_mb = round(os.path.getsize(full) / (1024 * 1024), 2)
    return BackupInfo(filename=filename, timestamp=timestamp, size_mb=size_mb)


def _list_backups() -> list[BackupInfo]:
    backups: list[BackupInfo] = []
    seen: set[tuple[str, str]] = set()
    for directory in _backup_search_dirs():
        try:
            for filename in os.listdir(directory):
                key = (directory, filename)
                fallback_key = ("", filename)
                if key in seen or fallback_key in seen:
                    continue
                info = _backup_info_from_file(directory, filename)
                if info is not None:
                    backups.append(info)
                    seen.add(key)
                    seen.add(fallback_key)
        except OSError:
            continue
    backups.sort(key=lambda b: b.timestamp, reverse=True)
    return backups


def _backup_path(filename: str) -> str:
    for directory in _backup_search_dirs():
        candidate = os.path.join(directory, filename)
        if os.path.exists(candidate):
            return candidate
    return os.path.join(_get_exe_dir(), filename)


def _rotate_backups() -> None:
    backups = _list_backups()
    if len(backups) <= MAX_BACKUPS:
        return
    for old in backups[MAX_BACKUPS:]:
        path = _backup_path(old.filename)
        logger.info("Rotating out old backup: %s", path)
        try:
            os.remove(path)
        except OSError as exc:
            logger.warning("Failed to remove old backup %s: %s", old.filename, exc)


def _package_kind(path: str) -> str:
    return "zip" if path.lower().endswith(ZIP_UPDATE_SUFFIX) else "exe"


def _latest_json_url() -> str:
    return os.environ.get("ERP_CNC_UPDATE_LATEST_URL", DEFAULT_LATEST_JSON_URL)


def _config_update_credentials() -> tuple[str, str]:
    config_path = os.path.join(_get_project_root(), "config.json")
    try:
        exists = os.path.exists(config_path)
        size = os.path.getsize(config_path) if exists else 0
        logger.info("Update credential config lookup: path=%s exists=%s size=%s", config_path, exists, size)
        with open(config_path, "r", encoding="utf-8-sig") as handle:
            data = json.load(handle)
    except Exception as exc:
        logger.warning("Update credential config read failed: path=%s error=%s", config_path, exc)
        return "", ""

    keys = sorted(str(key) for key in data.keys()) if isinstance(data, dict) else []
    logger.info("Update credential config parsed: path=%s keys=%s", config_path, keys)
    if not isinstance(data, dict):
        return "", ""

    username = str(data.get("update_username", "") or "")
    password = str(data.get("update_password", "") or "")
    logger.info(
        "Update credential config values: username_present=%s password_present=%s",
        bool(username),
        bool(password),
    )
    return username, password


def _update_credentials_with_source() -> tuple[str, str, str]:
    username = os.environ.get(UPDATE_USERNAME_ENV, "")
    password = os.environ.get(UPDATE_PASSWORD_ENV, "")
    if username or password:
        return username, password, "environment"

    config_path = os.path.join(_get_project_root(), "config.json")
    config_username, config_password = _config_update_credentials()
    return config_username, config_password, f"config:{config_path}"


def _update_credentials() -> tuple[str, str]:
    username, password, _source = _update_credentials_with_source()
    return username, password


def _mask_secret(value: str) -> str:
    if not value:
        return "<empty>"
    if len(value) <= 2:
        return "*" * len(value)
    return f"{value[0]}***{value[-1]} ({len(value)} chars)"


def _add_update_auth_header(request: urllib.request.Request) -> None:
    username, password, source = _update_credentials_with_source()
    if not username or not password:
        logger.info(
            "No complete update credentials configured for %s: source=%s username_present=%s password_present=%s",
            request.full_url,
            source,
            bool(username),
            bool(password),
        )
        return

    token = base64.b64encode(f"{username}:{password}".encode("utf-8")).decode("ascii")
    request.add_header("Authorization", f"Basic {token}")
    logger.info(
        "Using update credentials for %s: source=%s username=%s password=%s",
        request.full_url,
        source,
        username,
        _mask_secret(password),
    )


def _friendly_update_error(exc: Exception) -> str:
    if isinstance(exc, urllib.error.HTTPError) and exc.code == 401:
        return (
            "SVN update server requires credentials. Configure "
            f"{UPDATE_USERNAME_ENV} and {UPDATE_PASSWORD_ENV}, or set "
            "update_username/update_password in config.json."
        )
    return str(exc)


def _version_tuple(version: str) -> tuple[int, ...]:
    cleaned = version.strip().lower().lstrip("v")
    parts: list[int] = []
    for part in cleaned.split("."):
        digits = "".join(ch for ch in part if ch.isdigit())
        parts.append(int(digits or "0"))
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts)


def _is_newer_version(latest: str, current: str) -> bool:
    return _version_tuple(latest) > _version_tuple(current)


def _verify_update_tls() -> bool:
    value = os.environ.get(UPDATE_VERIFY_TLS_ENV, "0").strip().lower()
    return value in {"1", "true", "yes", "on"}


def _update_ssl_context():
    if _verify_update_tls():
        return None
    return ssl._create_unverified_context()


def _urlopen_update(request: urllib.request.Request):
    return urllib.request.urlopen(
        request,
        timeout=UPDATE_DOWNLOAD_TIMEOUT_SECONDS,
        context=_update_ssl_context(),
    )


def _read_remote_json(url: str) -> dict:
    request = urllib.request.Request(url, method="GET")
    _add_update_auth_header(request)
    with _urlopen_update(request) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _download_remote_file(url: str) -> bytes:
    request = urllib.request.Request(url, method="GET")
    _add_update_auth_header(request)
    with _urlopen_update(request) as response:
        return response.read()


def _load_latest_update_info() -> dict:
    latest_url = _latest_json_url()
    data = _read_remote_json(latest_url)
    version = str(data.get("version", "")).strip().lstrip("v")
    package_url = str(data.get("package_url", "")).strip()
    manifest_url = str(data.get("manifest_url", "")).strip()
    if not version:
        raise RuntimeError("latest.json is missing version")
    if not package_url:
        raise RuntimeError("latest.json is missing package_url")
    return {
        "version": version,
        "package_url": package_url,
        "manifest_url": manifest_url,
        "latest_json_url": latest_url,
    }


def _spawn_updater(exe_path: str, staged_path: str, package_kind: str | None = None) -> None:
    exe_dir = os.path.dirname(exe_path)
    package_kind = package_kind or _package_kind(staged_path)

    if getattr(sys, "frozen", False):
        temp_worker = os.path.join(tempfile.gettempdir(), f"erp-cnc-adapter-update-worker-{os.getpid()}.exe")
        shutil.copy2(sys.executable, temp_worker)
        logger.info("Copied update worker executable to temporary path: %s", temp_worker)
        command = [
            temp_worker,
            "--update-worker",
            "--exe-path",
            exe_path,
            "--staged-path",
            staged_path,
            "--service-name",
            SERVICE_NAME,
            "--package-kind",
            package_kind,
            "--adapter-pid",
            str(os.getpid()),
        ]
    else:
        worker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update_worker.py")
        if not os.path.exists(worker):
            logger.error("Update worker script not found at: %s", worker)
            raise RuntimeError(f"Update worker script not found: {worker}")
        command = [
            sys.executable,
            worker,
            "--exe-path",
            exe_path,
            "--staged-path",
            staged_path,
            "--service-name",
            SERVICE_NAME,
            "--package-kind",
            package_kind,
            "--adapter-pid",
            str(os.getpid()),
        ]

    logger.info("Spawning update worker: %s", command)
    try:
        create_no_window = 0x08000000
        create_new_process_group = 0x00000200
        subprocess.Popen(
            command,
            cwd=exe_dir,
            creationflags=create_no_window | create_new_process_group,
            close_fds=False,
        )
        logger.info("Update worker spawned successfully")
    except Exception as exc:
        logger.error("Failed to spawn update worker: %s", exc)
        raise


@router.get("/check", response_model=UpdateCheckResponse)
async def check_for_updates():
    try:
        info = _load_latest_update_info()
    except Exception as exc:
        logger.error("Failed to check for updates: %s", exc)
        return UpdateCheckResponse(
            status=1,
            message=f"Failed to check for updates: {_friendly_update_error(exc)}",
            current_version=VERSION,
        )

    update_available = _is_newer_version(info["version"], VERSION)
    message = (
        f"Update available: v{info['version']}"
        if update_available
        else f"No update available. Current version v{VERSION} is up to date."
    )
    return UpdateCheckResponse(
        status=0,
        message=message,
        current_version=VERSION,
        latest_version=info["version"],
        update_available=update_available,
        package_url=info["package_url"],
        manifest_url=info["manifest_url"],
    )


@router.post("/apply-latest", response_model=UpdateResponse)
async def apply_latest_update():
    try:
        info = _load_latest_update_info()
    except Exception as exc:
        logger.error("Failed to read latest update info: %s", exc)
        return UpdateResponse(status=1, message=f"Failed to read latest update info: {_friendly_update_error(exc)}")

    if not _is_newer_version(info["version"], VERSION):
        return UpdateResponse(status=1, message=f"No update available. Current version v{VERSION} is up to date.")

    try:
        content = _download_remote_file(info["package_url"])
    except Exception as exc:
        logger.error("Failed to download update package: %s", exc)
        return UpdateResponse(status=1, message=f"Failed to download update package: {_friendly_update_error(exc)}")

    if not content:
        return UpdateResponse(status=1, message="Downloaded update package is empty.")

    exe_path = _get_exe_path()
    exe_dir = _get_exe_dir()
    staged_path = os.path.join(exe_dir, "staged-update.zip")
    os.makedirs(exe_dir, exist_ok=True)
    try:
        with open(staged_path, "wb") as handle:
            handle.write(content)
    except OSError as exc:
        logger.error("Failed to write staged downloaded update: %s", exc)
        return UpdateResponse(status=1, message=f"Failed to save downloaded update: {exc}")

    size_mb = round(len(content) / (1024 * 1024), 2)
    logger.info("Latest update downloaded: version=%s size=%.2fMB staged=%s", info["version"], size_mb, staged_path)
    _rotate_backups()
    try:
        _spawn_updater(exe_path, staged_path, "zip")
    except Exception as exc:
        logger.error("Failed to spawn latest update worker: %s", exc)
        return UpdateResponse(status=1, message=f"Update failed: {exc}")

    return UpdateResponse(
        status=0,
        message=f"Update to v{info['version']} scheduled. The adapter will restart shortly.",
        version_info=f"Downloaded {info['package_url']} ({size_mb} MB)",
    )


@router.post("", response_model=UpdateResponse)
async def upload_update(file: UploadFile = File(...)):
    """Accept a full ZIP update package or legacy EXE and schedule a self-update."""
    if not file.filename:
        return UpdateResponse(status=1, message="Uploaded file must be a .zip update package or legacy .exe file.")

    lower_name = file.filename.lower()
    if not (lower_name.endswith(ZIP_UPDATE_SUFFIX) or lower_name.endswith(EXE_UPDATE_SUFFIX)):
        return UpdateResponse(status=1, message="Uploaded file must be a .zip update package or legacy .exe file.")

    content = await file.read()
    if len(content) == 0:
        return UpdateResponse(status=1, message="Uploaded file is empty.")

    exe_path = _get_exe_path()
    exe_dir = _get_exe_dir()
    package_kind = "zip" if lower_name.endswith(ZIP_UPDATE_SUFFIX) else "exe"
    staged_name = "staged-update.zip" if package_kind == "zip" else "staged-update.exe"
    staged_path = os.path.join(exe_dir, staged_name)

    os.makedirs(exe_dir, exist_ok=True)
    try:
        with open(staged_path, "wb") as handle:
            handle.write(content)
    except OSError as exc:
        logger.error("Failed to write staged update: %s", exc)
        return UpdateResponse(status=1, message=f"Failed to save staged file: {exc}")

    size_mb = round(len(content) / (1024 * 1024), 2)
    logger.info("=" * 60)
    logger.info("UPDATE REQUEST RECEIVED")
    logger.info("  Current version: %s", VERSION)
    logger.info("  Uploaded file: %s", file.filename)
    logger.info("  Package kind: %s", package_kind)
    logger.info("  File size: %.2f MB", size_mb)
    logger.info("  Staged at: %s", staged_path)
    logger.info("  Target EXE: %s", exe_path)
    logger.info("=" * 60)

    _rotate_backups()
    try:
        _spawn_updater(exe_path, staged_path, package_kind)
    except Exception as exc:
        logger.error("Failed to spawn update worker: %s", exc)
        return UpdateResponse(status=1, message=f"Update failed: {exc}")

    return UpdateResponse(
        status=0,
        message="Update scheduled. The adapter will restart shortly with the uploaded package.",
        version_info=f"Uploaded {file.filename} ({size_mb} MB)",
    )


@router.post("/rollback", response_model=RollbackResponse)
async def rollback():
    """Revert to the most recent full install backup, or legacy EXE backup if that is all that exists."""
    backups = _list_backups()
    if not backups:
        return RollbackResponse(status=1, message="No backups available for rollback.")

    latest = backups[0]
    exe_path = _get_exe_path()
    exe_dir = _get_exe_dir()
    backup_path = _backup_path(latest.filename)
    package_kind = "restore" if latest.filename.lower().endswith(".zip") else "exe"
    staged_path = os.path.join(exe_dir, "staged-update.zip" if package_kind == "restore" else "staged-update.exe")

    try:
        shutil.copy2(backup_path, staged_path)
    except OSError as exc:
        logger.error("Failed to stage backup for rollback: %s", exc)
        return RollbackResponse(status=1, message=f"Failed to stage rollback: {exc}")

    try:
        _spawn_updater(exe_path, staged_path, package_kind)
    except Exception as exc:
        logger.error("Failed to spawn rollback worker: %s", exc)
        return RollbackResponse(status=1, message=f"Rollback failed: {exc}")

    return RollbackResponse(
        status=0,
        message=f"Rollback to {latest.filename} scheduled. The adapter will restart shortly.",
    )


@router.get("/backups", response_model=BackupListResponse)
async def list_backups():
    backups = await asyncio.to_thread(_list_backups)
    return BackupListResponse(status=0, message=f"Found {len(backups)} backup(s).", backups=backups)
