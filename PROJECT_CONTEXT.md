# Project Context For Future Sessions

This file is intentionally plain and a little repetitive. It captures the practical context that matters when debugging this adapter.

## What This Project Is

ERP CNC Adapter is a Windows Python/FastAPI app that talks to CNC via `cncapi.dll` and `CncServer.exe`.

It is usually installed to run in the background from Windows Scheduled Task. The browser dashboard is only a control surface. The dashboard user is not necessarily the same Windows account as the adapter process.

## Dumb But Important Facts

- Do not assume the CNC GUI is running.
- Do not use GUI-only CNC API actions as backend solutions.
- The adapter may run as `SYSTEM`, but `SYSTEM` usually cannot access network shares.
- If UNC paths fail while files are visible in Explorer, suspect the scheduled task account.
- The CNC files are expected under paths like `\\192.168.2.11\Production\CNC\Mills\<job_number>`.
- Test UNC access as the adapter task account, not only as the interactive desktop user.
- Check logs for `Running as Windows user:` during job lookup.
- `CncServer.exe` may already be running. Starting another copy can trigger desktop error dialogs.
- Startup must be idempotent: already-running CNC Server is success, not an error.
- Keep the desktop quiet from background code paths.

## Current Job Flow Notes

- Load job endpoint: `src/api/job_load.py`
- Start job endpoint: `src/api/job_start.py`
- Unload job endpoint: `src/api/job_unload.py`
- Job status endpoint: `src/api/job_status.py`
- Dashboard template: `src/web/templates/dashboard.html`

There is no reliable non-GUI CNC API call found for unloading a job. The current approach is to load a placeholder file:

- Placeholder file: `resources/no_job_loaded.cnc`
- Placeholder helper: `src/core/placeholder_job.py`

Status should hide the placeholder name so UI/API consumers see no loaded job.

## Startup Notes

CNC server startup is shared through:

- `src/core/cnc_server_process.py`

Both adapter startup and `/api/cnc/start` should use the shared helper instead of launching `CncServer.exe` directly.

## Installer And Task Notes

- Scheduled task helper: `src/core/task_config.py`
- Installer worker: `src/installer/worker.py`
- Batch installer: `scripts/install.bat`

For remote CNC files, configure the scheduled task to run as a Windows user with share access and a password, then restart the task. Running at boot still works with a configured Windows task account.

## Packaging Notes

When adding runtime resource files, update:

- `util_scripts/erp-cnc-adapter.spec`

The placeholder unload file must be bundled into the installed app.

## Useful Test Commands

From repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cnc_start_stop.py tests\test_cnc_server_process.py tests\test_app_state.py
.\.venv\Scripts\python.exe -m pytest tests\test_job_load.py tests\test_job_start.py tests\test_job_unload.py tests\test_job_status.py
.\.venv\Scripts\python.exe -m pytest tests\test_request_response_logging.py
```

Compile-check changed Python files:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed-files>
```

## Human Preference Notes

- User wants practical fixes, not theoretical workarounds.
- User explicitly rejected GUI-dependent unload behavior because GUI will not be running.
- User wants noisy desktop dialogs stopped.
- User wants monitor/dashboard behavior compact and operational.
