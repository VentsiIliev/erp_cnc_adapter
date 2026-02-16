# ERP-CNC Adapter — Developer Guide

A Windows REST API service (FastAPI/Uvicorn) that bridges ERP systems with CNC machines running EdingCNC software. Communicates with CNC hardware via `cncapi.dll` (32-bit Windows DLL), packaged as a single EXE with PyInstaller, deployed as a Windows Scheduled Task.

---

## Table of Contents

1. [Environment Setup](#1-environment-setup)
2. [Running the Server](#2-running-the-server)
3. [Project Structure](#3-project-structure)
4. [Architecture Overview](#4-architecture-overview)
5. [Adding a New API Endpoint](#5-adding-a-new-api-endpoint)
6. [Testing](#6-testing)
7. [Building the EXE](#7-building-the-exe)
8. [Building the Installer](#8-building-the-installer)
9. [Deployment & Operations](#9-deployment--operations)
10. [Configuration Reference](#10-configuration-reference)
11. [CNC Client Layer](#11-cnc-client-layer)
12. [Update Mechanism](#12-update-mechanism)
13. [Troubleshooting](#13-troubleshooting)

---

## 1. Environment Setup

### Prerequisites

- **Python 3.11, 32-bit** — required to load `cncapi.dll` (32-bit DLL)
- **Git**
- **Windows 10/11** — the adapter uses Windows-only APIs (Task Scheduler, ctypes/windll, netsh)

### First-Time Setup (Automated)

The project includes a script that downloads 32-bit Python and creates the venv:

```powershell
git clone https://github.com/VentsiIliev/erp_cnc_adapter.git
cd erp_cnc_adapter
powershell -ExecutionPolicy Bypass -File util_scripts\setup_32bit_venv.ps1
```

This will:
1. Download and install Python 3.11.9 (32-bit) to `C:\Python311-32\` if not present
2. Create `.venv\` using that 32-bit interpreter
3. Install all dependencies from `requirements.txt`

### First-Time Setup (Manual)

```powershell
git clone https://github.com/VentsiIliev/erp_cnc_adapter.git
cd erp_cnc_adapter

# Use 32-bit Python (adjust path if needed)
C:\Python311-32\python.exe -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

### Dev Mode (No CNC Hardware Needed)

`main.py` ships with `dev_mode=True` by default, which uses `MockCncClient` instead of the real DLL. You do not need CNC hardware or the DLL to develop and test.

---

## 2. Running the Server

```powershell
.venv\Scripts\activate
python main.py
```

The server starts on `http://0.0.0.0:8002`. Key URLs:

| URL | Description |
|-----|-------------|
| `http://localhost:8002/` | Health dashboard (HTML) |
| `http://localhost:8002/api/health` | Health status (JSON) |
| `http://localhost:8002/update` | Update page |
| `http://localhost:8002/docs` | Swagger interactive API docs |

---

## 3. Project Structure

```
erp_cnc_adapter/
├── main.py                          # Server entry point
├── run_installer.py                 # Installer entry point
├── version.py                       # VERSION and BUILD_DATE
├── requirements.txt                 # Python dependencies
├── pytest.ini                       # Pytest config (asyncio_mode = auto)
│
├── src/
│   ├── app.py                       # FastAPI app factory
│   ├── update_worker.py             # Detached self-update process
│   │
│   ├── api/                         # All HTTP endpoints
│   │   ├── __init__.py              # Assembles api_router
│   │   ├── health.py                # GET /, GET /api/health
│   │   ├── cnc_start.py             # POST /api/cnc/start
│   │   ├── cnc_stop.py              # POST /api/cnc/stop
│   │   ├── job_load.py              # POST /api/cnc/job/load
│   │   ├── job_start.py             # POST /api/cnc/job/start
│   │   ├── job_status.py            # GET /api/cnc/job/status
│   │   ├── update.py                # POST /api/update, rollback, backups
│   │   ├── update_page.py           # GET /update (HTML page)
│   │   └── schemas/                 # Pydantic request/response models
│   │       ├── job.py
│   │       └── update.py
│   │
│   ├── core/                        # Application infrastructure
│   │   ├── config.py                # Settings dataclass
│   │   ├── app_state.py             # Service container + DI getters
│   │   └── logging_config.py        # File + console logging setup
│   │
│   ├── cnc/                         # CNC communication layer
│   │   ├── cnc_client_protocol.py   # Protocol (interface)
│   │   ├── cnc_client.py            # Real DLL wrapper
│   │   ├── mock_cnc_client.py       # Dev-mode stub
│   │   └── connection_manager.py    # Async reconnection loop
│   │
│   ├── installer/                   # PyQt5 GUI installer
│   └── web/                         # Static assets + HTML templates
│
├── cncapi/                          # ctypes struct/enum definitions
├── tests/                           # Pytest test suite
├── scripts/                         # Deployment scripts (install, uninstall, etc.)
├── util_scripts/                    # Developer build tools
├── resources/                       # logo.ico
└── dist/                            # Build output
```

---

## 4. Architecture Overview

### Request Flow

```
HTTP Request
    → FastAPI (src/app.py)
        → api_router (src/api/__init__.py)
            → endpoint handler (e.g. src/api/job_load.py)
                → CncClientProtocol via Depends(get_cnc_client)
                    → CncClient (real DLL) or MockCncClient (dev mode)
```

### Key Components

**AppState** (`src/core/app_state.py`) — central service container stored at `app.state.services`. Created during app startup, holds the CNC client and connection manager. Provides two FastAPI dependency functions:

```python
def get_cnc_client(request: Request) -> CncClientProtocol
def get_connection_manager(request: Request) -> ConnectionManager
```

**ConnectionManager** (`src/cnc/connection_manager.py`) — async background task that maintains the CNC connection. Retries on failure, sends heartbeat pings when connected. States: `disconnected` → `cnc_not_running` → `retrying` → `connected`.

**CncClientProtocol** (`src/cnc/cnc_client_protocol.py`) — structural typing interface. Both `CncClient` and `MockCncClient` implement it.

### Router Assembly

All routers are combined in `src/api/__init__.py`:

```python
api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(job_status.router)
api_router.include_router(job_load.router)
# ... etc
```

Then included in the app via `app.include_router(api_router)` in `src/app.py`.

---

## 5. Adding a New API Endpoint

### Step-by-step example: adding `GET /api/cnc/position`

#### 5.1. Define the response schema

Create or edit a file in `src/api/schemas/`. For a new schema:

```python
# src/api/schemas/job.py  (or a new file if unrelated)

class PositionResponse(BaseModel):
    status: int
    x: float = 0.0
    y: float = 0.0
    z: float = 0.0
```

#### 5.2. Create the handler module

Create `src/api/position.py`:

```python
import logging

from fastapi import APIRouter, Depends

from src.core.app_state import get_cnc_client
from src.cnc.cnc_client_protocol import CncClientProtocol
from .schemas.job import PositionResponse

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/api/cnc/position", response_model=PositionResponse)
async def get_position(
    client: CncClientProtocol = Depends(get_cnc_client),
):
    logger.info("GET position request")
    try:
        pos = client.get_position()  # you'd add this to the protocol
        return PositionResponse(status=0, x=pos["x"], y=pos["y"], z=pos["z"])
    except Exception as exc:
        logger.error("Error getting position: %s", exc)
        return PositionResponse(status=-1)
```

Key patterns:
- Use `APIRouter()` (not `APIRouter(prefix=...)` — the full path goes in the decorator)
- Inject dependencies via `Depends(get_cnc_client)` or `Depends(get_connection_manager)`
- Return the response model directly (FastAPI handles serialization)
- Wrap CNC calls in try/except — the DLL can throw at any time

#### 5.3. Register the router

Edit `src/api/__init__.py`:

```python
from src.api import cnc_start, cnc_stop, health, job_load, job_start, job_status, update, update_page, position

api_router = APIRouter()
# ... existing routers ...
api_router.include_router(position.router)
```

#### 5.4. If the endpoint needs a new CNC client method

1. Add the method signature to the protocol (`src/cnc/cnc_client_protocol.py`):
   ```python
   def get_position(self) -> dict: ...
   ```

2. Implement it in the real client (`src/cnc/cnc_client.py`):
   ```python
   def get_position(self) -> dict:
       # Call DLL function via ctypes
       ...
   ```

3. Implement the mock (`src/cnc/mock_cnc_client.py`):
   ```python
   def get_position(self) -> dict:
       return {"x": 0.0, "y": 0.0, "z": 0.0}
   ```

4. Add the method to `FakeCncClient` in `tests/conftest.py`:
   ```python
   def get_position(self) -> dict:
       return self._position  # add _position to __init__
   ```

#### 5.5. Write tests

Create `tests/test_position.py`:

```python
import pytest

pytestmark = pytest.mark.asyncio


class TestPosition:

    async def test_returns_coordinates(self, client, fake_client):
        fake_client._position = {"x": 10.0, "y": 20.0, "z": 5.0}

        resp = await client.get("/api/cnc/position")

        assert resp.status_code == 200
        body = resp.json()
        assert body["status"] == 0
        assert body["x"] == 10.0

    async def test_exception_returns_error(self, client, fake_client):
        def raise_error():
            raise RuntimeError("DLL error")
        fake_client.get_position = raise_error

        resp = await client.get("/api/cnc/position")

        body = resp.json()
        assert body["status"] == -1
```

Test patterns used in this project:
- `client` fixture — async httpx client from `conftest.py`
- `fake_client` fixture — `FakeCncClient` instance, mutate `._xxx` attributes to set up state
- `connection_manager` fixture — real `ConnectionManager` wired to fake client
- No `@pytest.mark.asyncio` needed (pytest.ini sets `asyncio_mode = auto`)
- Group tests in classes (`class TestPosition:`)
- For OS/subprocess mocks, use `@patch("src.api.module_name.thing")`

#### 5.6. If the endpoint serves an HTML page

Follow the pattern in `update_page.py`:

1. Create an HTML template in `src/web/templates/`
2. Use `string.Template` with `$variable` placeholders
3. Load the template at module level (handles frozen vs. source paths)
4. Return `HTMLResponse(content=rendered_html)`
5. Add the template path to the PyInstaller spec's `datas` list if not already covered by the `src/web/templates/` glob

#### 5.7. Update the PyInstaller spec (if needed)

If your new endpoint imports new third-party packages, add them to `hiddenimports` in `util_scripts/erp-cnc-adapter.spec`. If it reads files at runtime, add them to `datas`.

---

## 6. Testing

### Run all tests

```powershell
python -m pytest tests/ -v --timeout=15
```

Or use the convenience script:

```powershell
util_scripts\run_tests.bat
```

### Test conventions

| Convention | Detail |
|---|---|
| Framework | pytest + pytest-asyncio |
| Async mode | `auto` (no decorator needed on async tests) |
| Timeout | 15 seconds per test |
| HTTP tests | `async def` using `client` fixture (httpx AsyncClient over ASGITransport) |
| Unit tests | Plain `def` methods in classes |
| CNC mocking | Mutate `fake_client._xxx` attributes before making requests |
| OS mocking | `@patch("src.api.module.os.xxx")` |
| Validation | `pytest.raises(ValidationError)` for Pydantic |

### Fixtures (from `tests/conftest.py`)

| Fixture | Returns |
|---|---|
| `fake_client` | `FakeCncClient()` — in-memory stub |
| `settings` | `Settings(dll_path=..., port=9999, ...)` |
| `connection_manager` | `ConnectionManager(fake_client, settings)` (not started) |
| `test_app` | `FastAPI` app wired with fakes |
| `client` | `httpx.AsyncClient` for HTTP requests against `test_app` |

### Build gate

`util_scripts\build.bat` runs the full test suite before building. If any test fails, the build aborts.

---

## 7. Building the EXE

### Prerequisites

- 32-bit `.venv` set up (see section 1)
- PyInstaller installed (`pip install pyinstaller`)

### Build command

```powershell
util_scripts\build.bat
```

This will:
1. Run the test suite — abort on failure
2. Run PyInstaller with `util_scripts/erp-cnc-adapter.spec`
3. Create `dist/dist_v<VERSION>/` containing:
   - `erp-cnc-adapter.exe` (single-file EXE)
   - `scripts/` (install.bat, uninstall.bat, restart.bat, status.bat, watchdog.bat, update_adapter.py)
   - `logs/` (empty directory)
   - `VERSION.txt`, `README.txt`

### Before building

1. Update `version.py` with the new version and build date:
   ```python
   VERSION = "1.0.6"
   BUILD_DATE = "2026-02-16"
   ```
2. Make sure all tests pass

### PyInstaller spec highlights

The spec file is at `util_scripts/erp-cnc-adapter.spec`. Key settings:

- **Entry point:** `main.py`
- **Bundled data files:** `src/update_worker.py`, `src/web/templates/`, `src/web/static/`
- **Hidden imports:** all `uvicorn` internals, all `src.*` submodules, `version`, `multipart`
- **Single-file:** yes
- **Console:** yes (shows console when run manually)
- **Icon:** `resources/logo.ico`

If you add new submodules or data files, update the spec's `hiddenimports` and `datas` lists accordingly.

---

## 8. Building the Installer

### Build command

```powershell
util_scripts\build_installer.bat
```

This will:
1. Verify PyQt5 is installed
2. Run `build.bat` (tests + EXE build)
3. Copy the dist package into `src/installer/payload/`
4. Build the installer EXE with PyInstaller (`--onefile --windowed`)
5. Output: `dist/dist_v<VERSION>/ERP-CNC-Adapter-Setup-v<VERSION>.exe`
6. Clean up temporary files

### What the installer does

The installer is a frameless PyQt5 wizard (4 steps: Welcome, Choose Path, Installing, Done). On install it:

1. Extracts files to the chosen directory (default: `C:\Program Files\ERP-CNC Adapter`)
2. Creates scheduled task `ERPCNCAdapter` (runs as SYSTEM at startup)
3. Creates watchdog task `ERPCNCAdapterWatchdog` (every 2 minutes)
4. Opens firewall port 8002
5. Launches the adapter immediately

### Running the installer UI in dev mode

```powershell
python src/installer/ui/run.py
```

This skips the admin check and opens the Qt window directly.

---

## 9. Deployment & Operations

### Install (via scripts)

```powershell
# Run as Administrator
scripts\install.bat
```

### Check status

```powershell
scripts\status.bat
```

Shows task scheduler status, running processes, and recent log output.

### Restart

```powershell
scripts\restart.bat
```

### Uninstall

```powershell
# Run as Administrator
scripts\uninstall.bat
```

Removes scheduled tasks, firewall rule, and kills the process. Does not delete installed files.

### Logs

| Log | Location | Purpose |
|-----|----------|---------|
| `logs/adapter.log` | Install dir | Main application log (rotating, 10 MB, 5 backups) |
| `logs/installation.log` | Install dir | Created by installer |
| `logs/update.log` | Install dir | Created by update worker |

Monitor live:
```powershell
Get-Content logs\adapter.log -Wait -Tail 20
```

### Windows Scheduled Tasks

| Task | Trigger | Purpose |
|------|---------|---------|
| `ERPCNCAdapter` | At startup | Run the adapter |
| `ERPCNCAdapterWatchdog` | Every 2 min | Restart if crashed |

```powershell
# Query task status
schtasks /Query /TN ERPCNCAdapter /V /FO LIST

# Manual start
schtasks /Run /TN ERPCNCAdapter

# Remove
schtasks /Delete /TN ERPCNCAdapter /F
schtasks /Delete /TN ERPCNCAdapterWatchdog /F
```

---

## 10. Configuration Reference

Settings are defined in `src/core/config.py` as a dataclass:

| Field | Default | Description |
|-------|---------|-------------|
| `dll_path` | `C:\CNC4.03\cncapi.dll` | Path to the EdingCNC DLL |
| `ini_path` | `C:\CNC4.03\cnc.ini` | CNC server config file |
| `host` | `0.0.0.0` | Bind address |
| `port` | `8002` | HTTP port |
| `log_level` | `DEBUG` | Logging level |
| `cnc_retry_interval` | `5` | Seconds between reconnect attempts |
| `cnc_health_interval` | `10` | Seconds between heartbeat pings |
| `dev_mode` | `False` | Use MockCncClient (no DLL needed) |

Settings are passed to `create_app()` in `main.py`. In production the EXE uses the defaults. In development, `main.py` sets `dev_mode=True`.

---

## 11. CNC Client Layer

### Protocol

All CNC clients implement `CncClientProtocol` (structural typing):

```
connect() -> int          # 0 = success, 22 = server not running
disconnect() -> None
is_connected -> bool      # property
is_server_connected() -> bool
is_server_process_alive() -> bool
get_state() -> int        # 0-23 (CNC_IE_* enum)
get_job_status() -> dict  # ~30 fields
load_job(file_name) -> int
run_job() -> int
```

### Return codes

| Code | Constant | Meaning |
|------|----------|---------|
| 0 | `CNC_RC_OK` | Success |
| 6 | `CNC_RC_ALREADY_RUNS` | Server already running |
| 7 | `CNC_RC_ALREADY_CONNECTED` | Already connected |
| 22 | `CNC_RC_ERR_SERVER_NOT_RUNNING` | CncServer.exe not started |
| 24 | `CNC_RC_ERR_NOT_CONNECTED` | Not connected |

### CNC states (from `get_state()`)

| Code | State |
|------|-------|
| 0 | Power-up |
| 1 | Idle |
| 2 | Ready |
| 3 | Execution error |
| 5 | Aborted |
| 6 | Running job |
| 11-15 | Various paused states |
| 21 | Rendering graph |

Full map in `src/api/job_status.py:STATE_MAP`.

### Connection Manager states

```
disconnected → cnc_not_running → retrying → connected
                                     ↑          │
                                     └──────────┘ (heartbeat fails)
```

The `nudge()` method (called by `POST /api/cnc/start`) wakes the retry sleep so reconnection happens immediately instead of waiting for the next interval.

---

## 12. Update Mechanism

### API-based update flow

1. Client uploads new EXE via `POST /api/update` (multipart file)
2. Server validates filename (`.exe`) and content (non-empty)
3. Saves as `staged-update.exe`
4. Rotates old backups (keeps last 5)
5. Spawns `update_worker.py` as a detached process
6. Worker: stops adapter, backs up old EXE, replaces with staged, restarts

### Rollback

`POST /api/update/rollback` copies the most recent `.bak.*` file to `staged-update.exe` and spawns the update worker.

### Manual update

```powershell
python scripts\update_adapter.py C:\path\to\new\erp-cnc-adapter.exe
```

---

## 13. Troubleshooting

### "DLL load failed: error code 193"

Architecture mismatch. Your Python is 64-bit but the DLL is 32-bit. Use the 32-bit venv:
```powershell
.venv\Scripts\python.exe -c "import struct; print(struct.calcsize('P') * 8)"
# Must print: 32
```

### Tests hang or timeout

Check for `time.sleep()` in mocked functions that run on thread pool. Use short sleeps or mock them out. The test timeout is 15 seconds.

### "CncServer.exe not found" in health endpoint

In dev mode this is expected — `MockCncClient.is_server_process_alive()` returns `False`. The connection manager will stay in `cnc_not_running` state, which is normal for development.

### PyInstaller build fails with missing module

Add the module to `hiddenimports` in `util_scripts/erp-cnc-adapter.spec`. Common additions: new `src.*` submodules, `uvicorn` plugins, or any package not statically imported.

### Port 8002 already in use

Another adapter instance is running. Kill it:
```powershell
taskkill /F /IM erp-cnc-adapter.exe
# or
taskkill /F /PID <pid_from_adapter.pid>
```

### Firewall blocking connections

```powershell
# Check if rule exists
netsh advfirewall firewall show rule name="ERP-CNC Adapter"

# Add rule
netsh advfirewall firewall add rule name="ERP-CNC Adapter" dir=in action=allow protocol=TCP localport=8002 enable=yes profile=any
```
