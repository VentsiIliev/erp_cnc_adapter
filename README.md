# ERP-CNC Adapter

ERP-CNC Adapter is a FastAPI service that sits between ERP software and a CNC controller. It connects to the CNC server, loads and starts jobs from shared job folders, reports job state, exposes a small operations dashboard, and supports in-place updates with rollback.

## What It Does

- Starts and stops the CNC server process
- Loads CNC jobs from the configured job directory
- Starts, unloads, and monitors the current job
- Exposes health, monitor, log, and configuration endpoints
- Provides a browser dashboard for operations and maintenance
- Supports staged EXE updates and rollback from backups
- Persists configuration updates without wiping `config.json`

## Environment Setup

This project is Windows-first. For source development, use Python 3.11 and create a virtual environment in the project root.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Local development entry point:

```powershell
python main.py
```

The server listens on the host and port from `Settings` in `src/core/config.py` and defaults to `0.0.0.0:8002`.

## Build Process

The repository already includes the build scripts used by the project.

### Test First

```powershell
cd util_scripts
.\run_tests.bat
```

### Build the Application Package

```powershell
cd util_scripts
.\build.bat
```

`build.bat` does the following:

1. Reads the version from `version.py`
2. Stamps the build date into `version.py`
3. Runs the test suite with `pytest`
4. Builds `erp-cnc-adapter.exe` with PyInstaller
5. Creates a versioned distribution folder under `dist\dist_v<version>\`
6. Copies the EXE, scripts, resources, logs folder, and build metadata

### Build the Installer

```powershell
cd util_scripts
.\build_installer.bat
```

`build_installer.bat` first calls `build.bat`, then packages the GUI installer into a single self-contained EXE and places it in the same versioned distribution folder.

## Configuration

Runtime settings are persisted in `config.json`. The configuration API updates only the fields you send and keeps the rest of the file intact. That means existing machine, path, and timing values are preserved unless you explicitly change them.

The main settings include:

- `machine_number`
- `dll_path`
- `ini_path`
- `job_done_report_url`
- `base_dir`
- `run_as_windows_user`
- `task_username`
- `task_password`
- `port`
- `cnc_retry_interval`
- `cnc_health_interval`
- `auto_start_adapter_on_logon`
- `adapter_startup_delay_seconds`
- `job_monitor_poll_interval`
- `jog_pad_pause_hold_interval_ms`

## API Endpoints

### Status and Dashboard

- `GET /`  
  Returns JSON status by default, or the HTML health dashboard when the request accepts `text/html`.

- `GET /api/health`  
  JSON health check with CNC connection state, retry count, uptime, and version.

- `GET /dashboard`  
  Unified dashboard in the overview view.

- `GET /config`  
  Unified dashboard focused on configuration.

- `GET /monitor`  
  Unified dashboard focused on live monitoring.

- `GET /test`  
  Unified dashboard focused on testing tools.

- `GET /update`  
  Unified dashboard focused on maintenance and updates.

### CNC Control

- `GET /api/cnc/start`  
  Starts `CncServer.exe`. No request parameters.

- `GET /api/cnc/stop`  
  Stops `cnc.exe` and `CncServer.exe`. No request parameters.

- `GET /api/cnc/job/load/{job_number}/{step}/{qty}`  
  Path parameters:
  - `job_number`: exactly 12 digits
  - `step`: numeric step identifier
  - `qty`: quantity/repeat count, validated from 1 to 9999

  The adapter looks for `Setup_{step}*.nc` or `Setup_{step}*.cnc` inside `base_dir/<job_number>/`. The handler currently accepts `qty` for validation but sets the CNC quantity to `1` in code.

- `GET /api/cnc/job/start`  
  Starts or resumes the loaded job. No request parameters.

- `POST /api/cnc/job/pause`  
  Sends `CncPauseJob()` through the CNC DLL. The jog pad calls this periodically while it is open.

- `GET /api/cnc/job/status`  
  Returns current CNC state, job metadata, progress, timing, and repeat counters. No request parameters.

- `GET /api/cnc/job/unload`  
  Loads the placeholder no-job file so the adapter behaves as if no job is loaded. No request parameters.

- `GET /api/cnc/monitor/status`  
  Returns the live monitor snapshot together with current CNC state and job data. No request parameters.

- `POST /api/jog-pad/open`  
  Opens the desktop jog pad and passes the configured adapter URL and pause-hold interval.

### Update Management

- `POST /api/update`  
  Multipart form upload with one required field:
  - `file`: the new application EXE, and it must end in `.exe`

  The uploaded file is staged as `staged-update.exe`, backups are rotated, and the detached update worker is started.

- `POST /api/update/rollback`  
  Re-stages the newest backup and starts the rollback worker. No request parameters.

- `GET /api/update/backups`  
  Lists available backup EXEs. No request parameters.

### Configuration API

- `GET /api/config`  
  Returns current configuration plus derived values such as the machine IP and scheduled-task launch settings. No request parameters.

- `POST /api/config`  
  JSON body with any of these optional fields:
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
  - `auto_start_adapter_on_logon`
  - `adapter_startup_delay_seconds`
  - `job_monitor_poll_interval`
  - `jog_pad_pause_hold_interval_ms`

  Only supplied fields are applied and persisted. Task credential updates require a username when `run_as_windows_user` is enabled; passwordless Windows accounts use an interactive logon task. Set `auto_start_adapter_on_logon` to `false` for manual starts. `adapter_startup_delay_seconds` delays scheduled boot/logon startup so CNC services and the desktop can settle before the adapter starts. Port changes are saved immediately but require an adapter restart before the HTTP listener moves to the new port.

### Logging and Test Hooks

- `GET /api/logs?lines=200`  
  Returns the last `lines` entries from `logs/adapter.log`. The `lines` query parameter is optional and defaults to `200`.

- `GET /actions/cnc_job_done.php?m=...&c=...&s=...`  
  Local test endpoint for job-done callbacks.
  - `m`: machine number
  - `c`: job number
  - `s`: step number

### Support Routes

- `GET /favicon.ico`  
  Returns the configured favicon when present.

- `GET /static/*`  
  Serves static assets used by the dashboard.

## Repository Layout

- `src/` - application code, API handlers, CNC client wrappers, config, installer UI, and web assets
- `tests/` - pytest suite
- `scripts/` - installation and service management helpers
- `util_scripts/` - build and test scripts
- `resources/` - icons and job placeholders
- `main.py` - application entry point
- `run_installer.py` - installer entry point
- `version.py` - version and build metadata

## Notes

- The adapter is designed for a Windows deployment with Task Scheduler-based startup.
- Update operations are staged and rolled back through backups if startup verification fails.
- The README intentionally matches the current route set so operators can trace each endpoint back to its request parameters.
