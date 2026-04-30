# ERP CNC Adapter Agent Notes

## Start Here

Also read `PROJECT_CONTEXT.md` for practical debugging context from prior sessions.

## Project Shape

This is a Windows Python/FastAPI adapter for CNC control. It is usually run as a background process from Windows Scheduled Task, not as an interactive desktop app.

Important paths:

- API routes: `src/api/`
- Startup/service container: `src/core/app_state.py`
- CNC client and monitor: `src/cnc/`
- Dashboard UI: `src/web/templates/dashboard.html`
- Installer/task logic: `src/installer/`, `scripts/`, `src/core/task_config.py`
- PyInstaller spec: `util_scripts/erp-cnc-adapter.spec`

## Rules Of Thumb

- Do not assume the CNC GUI is running. Backend operations must work without GUI interaction.
- Treat `CncServer.exe` startup as idempotent. If it is already running, log and skip launching another instance.
- Avoid desktop dialogs or visible windows from background adapter paths.
- Scheduled task identity matters. UNC paths must be accessible by the adapter task account, not just the browser user.
- Do not revert unrelated dirty work in this repo.
- Keep changes focused and add tests around changed behavior.

## CNC Job Behavior

- Load route: `src/api/job_load.py`
- Start route: `src/api/job_start.py`
- Unload route: `src/api/job_unload.py`
- Placeholder unload file: `resources/no_job_loaded.cnc`
- Placeholder path helper: `src/core/placeholder_job.py`

There is no reliable non-GUI CNC API unload call. Use the placeholder file strategy and hide that placeholder name from status/UI consumers.

## Remote Files

If a UNC path such as `\\192.168.2.11\Production\CNC\Mills` fails while the file exists, suspect the Windows account running the adapter. Check logs for `Running as Windows user:` during job lookup.

## Verification

Run focused tests from the repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cnc_start_stop.py tests\test_cnc_server_process.py tests\test_app_state.py
.\.venv\Scripts\python.exe -m pytest tests\test_job_load.py tests\test_job_start.py tests\test_job_unload.py tests\test_job_status.py
.\.venv\Scripts\python.exe -m pytest tests\test_request_response_logging.py
```

Compile-check changed Python files when useful:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed-files>
```
