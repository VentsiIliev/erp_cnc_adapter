# ERP-CNC Adapter Developer Guide

ERP-CNC Adapter is a Windows FastAPI/Uvicorn service that bridges ERP systems with EdingCNC machines. It talks to the controller through the 32-bit `cncapi.dll`, exposes operational HTTP endpoints and a dashboard, and is packaged with PyInstaller for Task Scheduler-based deployment.

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Running the Server](#2-running-the-server)
3. [Project Structure](#3-project-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [HTTP Logging](#5-http-logging)
6. [Dashboard Behavior](#6-dashboard-behavior)
7. [Endpoints](#7-endpoints)
8. [Adding a New API Endpoint](#8-adding-a-new-api-endpoint)
9. [Testing](#9-testing)
10. [Build Workflow](#10-build-workflow)
11. [Deployment and Operations](#11-deployment-and-operations)
12. [Configuration Reference](#12-configuration-reference)
13. [CNC Client Layer](#13-cnc-client-layer)
14. [Update Mechanism](#14-update-mechanism)
15. [Documentation Maintenance](#15-documentation-maintenance)
16. [Troubleshooting](#16-troubleshooting)

## 1. Environment Setup

### Prerequisites

- Windows 10/11
- Git
- Python 3.11, 32-bit, for loading the 32-bit EdingCNC DLL
- Administrator rights for installer, firewall, and scheduled-task testing

### Automated Setup

```powershell
git clone https://github.com/VentsiIliev/erp_cnc_adapter.git
cd erp_cnc_adapter
powershell -ExecutionPolicy Bypass -File util_scripts\setup_32bit_venv.ps1
```

The setup script installs or reuses Python 3.11.9 32-bit, creates `.venv`, and installs `requirements.txt`.

### Manual Setup

```powershell
C:\Python311-32\python.exe -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` includes runtime dependencies such as FastAPI, Uvicorn, Pydantic, `python-multipart`, plus build/test dependencies including PyInstaller, pytest, httpx, and PyQt5.

## 2. Running the Server

```powershell
.venv\Scripts\activate
python main.py
```

`main.py` currently sets `dev_mode = False`, so it uses the real CNC client path by default. For local hardware-free development, instantiate `Settings(dev_mode=True)` in tests or in a local-only edit that is not committed.

The default bind is `0.0.0.0:8002`, unless `config.json` overrides `port`. Useful URLs:

| URL | Purpose |
|---|---|
| `http://localhost:8002/` | Dashboard for browser requests, JSON status for API requests |
| `http://localhost:8002/dashboard` | Unified dashboard overview |
| `http://localhost:8002/config` | Dashboard configuration view |
| `http://localhost:8002/monitor` | Dashboard monitor view |
| `http://localhost:8002/test` | Dashboard testing view |
| `http://localhost:8002/update` | Dashboard maintenance/update view |
| `http://localhost:8002/api/health` | JSON health status |
| `http://localhost:8002/docs` | Swagger/OpenAPI docs |

## 3. Project Structure

```text
erp_cnc_adapter/
|-- main.py                         # Server entry point
|-- run_installer.py                # Installer entry point
|-- version.py                      # VERSION and BUILD_DATE
|-- requirements.txt                # Runtime, build, and test dependencies
|-- README.md                       # User/operator documentation
|-- DEV_GUIDE.md                    # Developer documentation
|-- pytest.ini                      # pytest config
|
|-- src/
|   |-- app.py                      # FastAPI app factory, middleware, static mount
|   |-- update_worker.py            # Detached update process
|   |
|   |-- api/                        # HTTP endpoints
|   |   |-- __init__.py             # Assembles api_router
|   |   |-- health.py               # GET /, GET /api/health
|   |   |-- dashboard_page.py       # GET /dashboard and dashboard renderer
|   |   |-- config_page.py          # GET /config
|   |   |-- monitor_page.py         # GET /monitor
|   |   |-- test_page.py            # GET /test
|   |   |-- update_page.py          # GET /update
|   |   |-- config_api.py           # GET/POST /api/config
|   |   |-- logs.py                 # GET /api/logs
|   |   |-- monitor_status.py       # GET /api/cnc/monitor/status
|   |   |-- cnc_start.py            # GET /api/cnc/start
|   |   |-- cnc_stop.py             # GET /api/cnc/stop
|   |   |-- job_load.py             # GET /api/cnc/job/load/{job_number}/{step}/{qty}
|   |   |-- job_start.py            # GET /api/cnc/job/start
|   |   |-- job_status.py           # GET /api/cnc/job/status
|   |   |-- job_unload.py           # GET /api/cnc/job/unload
|   |   |-- update.py               # POST /api/update, rollback, backups
|   |   |-- schemas/                # Pydantic models
|   |
|   |-- core/                       # Settings, app state, logging, persistence
|   |-- cnc/                        # Real/mock CNC clients, protocol, monitor
|   |-- installer/                  # PyQt5 installer UI
|   |-- web/                        # Dashboard templates and static assets
|
|-- cncapi/                         # ctypes structs/enums for cncapi.dll
|-- tests/                          # pytest suite
|-- scripts/                        # Install, uninstall, restart, status helpers
|-- util_scripts/                   # Build/test/setup scripts and PyInstaller spec
|-- resources/                      # Icon and placeholder CNC resources
|-- dist/                           # Build output
```

## 4. Architecture Overview

### Request Flow

```text
HTTP request
  -> FastAPI app from src/app.py
  -> log_http_request_response middleware, unless path is excluded
  -> api_router from src/api/__init__.py
  -> endpoint handler
  -> AppState services through FastAPI dependencies
  -> CncClientProtocol implementation
  -> cncapi.dll or test/mock implementation
```

### Key Components

`AppState` in `src/core/app_state.py` is the service container stored at `app.state.services`. It owns settings, the CNC client, the connection manager, and the job monitor.

`Settings` in `src/core/config.py` is a dataclass. It loads persisted overrides from `config.json` during `__post_init__`.

`ConnectionManager` in `src/cnc/connection_manager.py` maintains the CNC connection, retries on failure, reports state, and can be nudged after `/api/cnc/start`.

`CncClientProtocol` defines the common contract used by the real CNC client, mock client, unavailable client, and tests.

`JobMonitor` tracks active jobs and reports completion to the configured `job_done_report_url`.

### Router Assembly

All routers are imported and registered in `src/api/__init__.py`. After adding a new endpoint module, include its router there. `src/app.py` then calls `app.include_router(api_router)`.

## 5. HTTP Logging

The app installs `log_http_request_response` from `src/core/http_logging.py` as HTTP middleware. It logs one `HTTP REQUEST` line before the handler and one `HTTP RESPONSE` line after the handler for non-excluded paths.

Behavior:

- Logs method, path, query string, status code, elapsed milliseconds, and formatted body.
- JSON bodies are compacted before logging.
- Bodies longer than `MAX_LOG_BODY_CHARS` are truncated.
- The middleware rebuilds the response after reading the body iterator so response bodies and headers are preserved.

Excluded exact paths:

- `/`
- `/favicon.ico`
- `/api/config`
- `/api/health`
- `/api/logs`
- `/api/update/backups`
- `/api/cnc/job/status`

Excluded prefixes:

- `/static/`
- `/api/cnc/monitor/`

These exclusions keep high-frequency dashboard polling, logs, static assets, and health/config reads from flooding `adapter.log`. `POST /api/config` still logs its own configuration update events through the endpoint logger.

## 6. Dashboard Behavior

The dashboard is unified in `src/web/templates/dashboard.html` and rendered through `src/api/dashboard_page.py`.

Routes:

- `/dashboard` opens the overview view.
- `/config` opens the configuration view.
- `/monitor` opens the monitor view.
- `/test` opens the testing view.
- `/update` opens the maintenance view.
- `/` returns the dashboard for browser `Accept: text/html` requests.

`dashboard_response()` sets these headers on dashboard HTML responses:

- `Cache-Control: no-store`
- `Pragma: no-cache`
- `Expires: 0`

Recent dashboard controls and indicators:

- The testing view includes an `Unload Job` button that calls `GET /api/cnc/job/unload`.
- The hero area displays machine ID and adapter IP/port using `GET /api/config`.
- The configuration view can edit the adapter `port`; the new port is persisted, but a restart is required before Uvicorn binds the new port.
- The dashboard log panels intentionally do not force-scroll while users inspect older log lines.

## 7. Endpoints

### Status, Pages, and Assets

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/` | Header-sensitive `Accept` | Browser requests get dashboard HTML; API requests get status JSON. |
| GET | `/api/health` | None | JSON health, version, CNC connection state, retry count, last error, uptime. |
| GET | `/dashboard` | None | Unified dashboard overview. |
| GET | `/config` | None | Unified dashboard configuration view. |
| GET | `/monitor` | None | Unified dashboard monitor view. |
| GET | `/test` | None | Unified dashboard testing view. |
| GET | `/update` | None | Unified dashboard maintenance view. |
| GET | `/favicon.ico` | None | Returns `resources/logo.ico` when available, otherwise 204. |
| GET | `/static/*` | Path | Serves dashboard static assets. |

### CNC Operations

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/cnc/start` | None | Starts `CncServer.exe`, nudges the connection manager, redirects to `/` on success. |
| GET | `/api/cnc/stop` | None | Disconnects adapter and stops `cnc.exe` plus `CncServer.exe`, then redirects to `/`. |
| GET | `/api/cnc/job/load/{job_number}/{step}/{qty}` | `job_number`: exactly 12 digits; `step`: numeric; `qty`: 1-9999 | Finds `Setup_{step}*.nc` or `.cnc` in `base_dir/<job_number>/`, loads it, stores job metadata, renders the job. The code currently accepts `qty` but forces quantity to 1. |
| GET | `/api/cnc/job/start` | None | Starts or resumes the loaded job after state checks. |
| GET | `/api/cnc/job/status` | None | Returns CNC state, job name, progress, timing, repeat fields, and computed percentage/current repeat. |
| GET | `/api/cnc/job/unload` | None | Loads the placeholder no-job CNC file and clears last loaded job/monitor state. |
| GET | `/api/cnc/monitor/status` | None | Returns job monitor status plus live CNC/job fields when available. |

### Configuration

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/api/config` | None | Returns current configuration, local IP, and scheduled-task launch settings. Excluded from HTTP body logging. |
| POST | `/api/config` | JSON body with optional fields listed below | Updates in-memory settings and persists supplied fields to `config.json`. |

`POST /api/config` optional JSON fields:

- `machine_number`
- `dll_path`
- `ini_path`
- `job_done_report_url`
- `base_dir`
- `run_as_windows_user`
- `task_username`
- `task_password`
- `restart_adapter_task`
- `port`
- `cnc_retry_interval`
- `cnc_health_interval`
- `job_monitor_poll_interval`

Notes:

- `port` is validated from 1 to 65535 and persisted, but restart is required to bind it.
- Task user updates require `task_username` and `task_password` when `run_as_windows_user` is enabled.
- `restart_adapter_task` can restart the scheduled adapter task after applying configuration.
- The persistence layer updates provided keys without wiping unrelated `config.json` values.

### Update and Logs

| Method | Path | Parameters | Notes |
|---|---|---|---|
| POST | `/api/update` | Multipart `file` field ending in `.exe` | Stages the upload as `staged-update.exe`, rotates backups, spawns the update worker. |
| POST | `/api/update/rollback` | None | Stages the newest backup and spawns the update worker. |
| GET | `/api/update/backups` | None | Lists backup EXEs. Excluded from HTTP body logging. |
| GET | `/api/logs` | Optional query `lines`, default 200 | Returns recent `logs/adapter.log` lines. Excluded from HTTP body logging. |

### Local Test Hook

| Method | Path | Parameters | Notes |
|---|---|---|---|
| GET | `/actions/cnc_job_done.php` | Query `m`, `c`, `s` | Local mock endpoint for job-done reports. |

## 8. Adding a New API Endpoint

1. Add a response/request model in `src/api/schemas/` if the endpoint needs structured data.
2. Create a route module in `src/api/` with `router = APIRouter()`.
3. Use the full path in the decorator unless the module has a clear, established prefix.
4. Inject app services with dependencies from `src/core/app_state.py`.
5. Catch DLL/client exceptions and return structured error data where existing endpoint patterns do so.
6. Register the router in `src/api/__init__.py`.
7. Add focused tests using the existing `client`, `fake_client`, `settings`, and `connection_manager` fixtures.
8. If the route imports new third-party packages, update `requirements.txt` and the PyInstaller spec as needed.
9. If the route serves new runtime files, make sure the spec bundles them.
10. Update `README.md` and this guide when endpoint behavior changes.

Minimal pattern:

```python
import logging

from fastapi import APIRouter, Depends

from src.cnc.cnc_client_protocol import CncClientProtocol
from src.core.app_state import get_cnc_client

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cnc/example")
async def example(client: CncClientProtocol = Depends(get_cnc_client)):
    try:
        state = client.get_state()
        return {"status": 0, "state": state}
    except Exception as exc:
        logger.error("Example endpoint failed: %s", exc, exc_info=True)
        return {"status": -1, "message": str(exc)}
```

## 9. Testing

Run all tests:

```powershell
python -m pytest tests/ -v --timeout=15
```

Or use:

```powershell
util_scripts\run_tests.bat
```

Important conventions:

| Convention | Detail |
|---|---|
| Framework | pytest + pytest-asyncio |
| Async mode | `auto` from `pytest.ini` |
| HTTP client | `httpx.AsyncClient` over `ASGITransport` |
| Test app | Built in `tests/conftest.py` with fake services |
| CNC stub | `FakeCncClient`, configured by mutating `_state`, `_job_status`, return-code fields |
| OS/process work | Mock Windows APIs, filesystem calls, and subprocess calls |
| Docs checks | `tests/test_docs_and_requirements.py` covers README and requirements completeness |
| Dashboard checks | `tests/test_dashboard_template.py` covers key dashboard controls and no-cache headers |
| Logging checks | `tests/test_request_response_logging.py` covers request/response body logging and exclusions |

Builds call the test suite before packaging, so failing tests stop `util_scripts\build.bat`.

## 10. Build Workflow

### Build Application EXE

```powershell
util_scripts\build.bat
```

`build.bat`:

1. Uses `.venv\Scripts\python.exe` and `.venv\Scripts\pyinstaller.exe`.
2. Reads `VERSION` from `version.py`.
3. Stamps today's `BUILD_DATE` into `version.py`.
4. Runs `python -m pytest tests/ --timeout=15 -q`.
5. Runs PyInstaller with `util_scripts\erp-cnc-adapter.spec`.
6. Creates `dist\dist_v<VERSION>\`.
7. Copies the app EXE, scripts, resources, `logs\`, `VERSION.txt`, and distribution README.

### Build Installer

```powershell
util_scripts\build_installer.bat
```

`build_installer.bat`:

1. Verifies PyQt5, installing it into the venv if needed.
2. Calls `build.bat`.
3. Copies the distribution payload into `src\installer\payload\`.
4. Builds `ERP-CNC-Adapter-Setup-v<VERSION>.exe` with PyInstaller.
5. Moves the installer into the matching `dist\dist_v<VERSION>\` folder.
6. Removes temporary payload/build artifacts.

### PyInstaller Notes

The spec is `util_scripts/erp-cnc-adapter.spec`. Check it when adding:

- New `src.*` modules that PyInstaller may not discover.
- Runtime data files.
- New packages that need hidden imports.

## 11. Deployment and Operations

### Script Install

```powershell
scripts\install.bat
```

Run as Administrator. The installer/scripts configure scheduled tasks, firewall, logs, and immediate startup.

### Common Commands

```powershell
scripts\status.bat
scripts\restart.bat
scripts\uninstall.bat
```

`scripts\uninstall.bat` removes scheduled tasks/firewall entries and stops processes. It does not delete installed files.

### Logs

| Log | Purpose |
|---|---|
| `logs/adapter.log` | Main application log and non-excluded HTTP request/response logs |
| `logs/installation.log` | Installer log |
| `logs/update.log` | Update worker log |
| `logs/service.log` | Service/task helper log when present |

Monitor live:

```powershell
Get-Content logs\adapter.log -Wait -Tail 20
```

### Scheduled Tasks

| Task | Purpose |
|---|---|
| `ERPCNCAdapter` | Starts the adapter at boot |
| `ERPCNCAdapterWatchdog` | Periodically restarts the adapter if it is not running |

## 12. Configuration Reference

Settings live in `src/core/config.py`, and persisted overrides are loaded from `config.json`.

| Field | Default | Notes |
|---|---|---|
| `dll_path` | `C:\CNC4.03\cncapi.dll` | EdingCNC DLL path |
| `ini_path` | `C:\CNC4.03\cnc.ini` | CNC server INI path |
| `host` | `0.0.0.0` | Uvicorn bind address |
| `port` | `8002` | Adapter HTTP port; configurable via dashboard/API; restart required |
| `log_level` | `DEBUG` | Logging level |
| `cnc_retry_interval` | `5` | Seconds between reconnect attempts |
| `cnc_health_interval` | `10` | Seconds between heartbeat checks |
| `job_monitor_poll_interval` | `1.0` | Seconds between monitor polls |
| `machine_number` | `CNC1` | Machine identifier shown in dashboard and reported on job completion |
| `task_username` | empty | Empty means scheduled task runs as SYSTEM |
| `job_done_report_url` | `https://pl.skycode.com/actions/cnc_job_done.php` | Completion callback URL |
| `dev_mode` | `False` | Use mock CNC client when true |
| `base_dir` | `\\192.168.2.11\Production\CNC\Mills` | Root folder for job files |

`POST /api/config` updates only supplied values and then calls the config persistence helper. Do not wipe `config.json` during updates; preserve unrelated keys.

## 13. CNC Client Layer

Core protocol methods:

```text
connect() -> int
disconnect() -> None
is_connected -> bool
is_server_connected() -> bool
is_server_process_alive() -> bool
get_state() -> int
get_job_status() -> dict
load_job(file_name: str) -> int
set_job_quantity(quantity: int) -> int
render_job() -> int
run_job() -> int
```

Common CNC return codes:

| Code | Meaning |
|---|---|
| `0` | Success |
| `6` | Already running |
| `7` | Already connected |
| `10` | Invalid state |
| `20` | File open/file not found problem |
| `22` | CNC server not running |
| `24` | Not connected |
| `-1` | Generic/busy/exception fallback |

Key CNC states:

| Code | State |
|---|---|
| `0` | Power-up |
| `1` | Idle |
| `2` | Ready |
| `3` | Execution error |
| `4` | Internal error |
| `5` | Aborted |
| `6` | Running job |
| `11-15` | Paused states |
| `21` | Rendering graph |

Full maps live in `src/api/job_status.py` and `src/api/monitor_status.py`.

## 14. Update Mechanism

### API Update Flow

1. Client uploads a non-empty `.exe` to `POST /api/update` as multipart field `file`.
2. The endpoint stages it as `staged-update.exe`.
3. Existing backups are rotated, keeping the newest five.
4. `_spawn_updater()` launches `src/update_worker.py` detached.
5. The worker stops the adapter, backs up the old EXE, replaces it, restarts, and verifies startup.

### Rollback

`POST /api/update/rollback` copies the newest backup to `staged-update.exe` and uses the same worker flow.

### Manual Update Script

```powershell
python scripts\update_adapter.py C:\path\to\new\erp-cnc-adapter.exe
```

## 15. Documentation Maintenance

Keep these files aligned when behavior changes:

- `README.md` for operator-facing setup, build, and endpoint docs.
- `DEV_GUIDE.md` for implementation patterns, testing, logging, dashboard, and build details.
- `requirements.txt` when source, installer, build scripts, or tests import a new third-party package.
- `tests/test_docs_and_requirements.py` when README/requirements expectations intentionally change.

Recent docs updates added README coverage for current endpoints/build flow and made `pydantic` explicit in `requirements.txt`.

## 16. Troubleshooting

### DLL load failed: error code 193

Python and DLL architecture do not match. Confirm the venv is 32-bit:

```powershell
.venv\Scripts\python.exe -c "import struct; print(struct.calcsize('P') * 8)"
```

Expected output is `32`.

### Server starts on the wrong port

Check `config.json` for a persisted `port` override. Updating the port through `/api/config` or the dashboard persists the value, but the running Uvicorn process must restart before it binds the new port.

### Port 8002 already in use

```powershell
netstat -ano | findstr :8002
taskkill /F /PID <pid>
```

Or stop the packaged process:

```powershell
taskkill /F /IM erp-cnc-adapter.exe
```

### CncServer.exe not found

`/api/cnc/start` looks for `CncServer.exe` in the directory containing `dll_path`. Check the configured `dll_path` in `/api/config`.

### Tests hang or timeout

The test timeout is 15 seconds. Mock sleeps, process calls, Windows shell calls, DLL calls, and filesystem waits in tests.

### PyInstaller build misses a module or asset

Update `util_scripts/erp-cnc-adapter.spec` with the needed hidden import or data file.

### Dashboard shows stale data after an update

Dashboard responses are sent with no-cache headers. If stale data remains, verify the browser is actually hitting the restarted adapter and the configured port.
