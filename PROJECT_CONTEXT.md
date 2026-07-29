# Project Context For Future Sessions

This file is intentionally plain and practical. It captures the context that matters when debugging or extending this adapter.

## What This Project Is

ERP CNC Adapter is a Windows Python/FastAPI app that talks to Eding CNC through `cncapi.dll` and `CncServer.exe`.

It is usually installed to run in the background from Windows Scheduled Task. The browser dashboard is only a control surface. The dashboard user is not necessarily the same Windows account as the adapter process.

The Python runtime and Eding CNC DLL are 32-bit. Keep that constraint in mind for packaging and direct DLL calls.

## Dumb But Important Facts

- Do not assume the Eding CNC GUI is running.
- Do not use GUI-only CNC API actions as backend solutions unless the user explicitly accepts the GUI dependency.
- The adapter may run as `SYSTEM`, but `SYSTEM` usually cannot access network shares.
- If UNC paths fail while files are visible in Explorer, suspect the scheduled task account.
- CNC files are expected under paths like `\\192.168.2.11\Production\CNC\Mills\<job_number>`.
- Test UNC access as the adapter task account, not only as the interactive desktop user.
- Check logs for `Running as Windows user:` during job lookup.
- `CncServer.exe` may already be running. Starting another copy can trigger desktop error dialogs.
- Startup must be idempotent: already-running CNC Server is success, not an error.
- Keep background adapter paths quiet. Avoid desktop dialogs or visible windows from background tasks.
- The operator does not watch backend logs while jogging; CNC errors must be surfaced in the jog pad UI.

## Important Paths

- API routes: `src/api/`
- Startup/service container: `src/core/app_state.py`
- CNC client and monitor: `src/cnc/`
- Shared CncServer launcher: `src/core/cnc_server_process.py`
- Scheduled task helper: `src/core/task_config.py`
- Installer worker: `src/installer/worker.py`
- Dashboard UI: `src/web/templates/dashboard.html`
- Jog pad package: `src/jog_pad/`
- Installer/runtime scripts: `scripts/`
- PyInstaller spec: `util_scripts/erp-cnc-adapter.spec`

## Current Job Flow Notes

- Load job endpoint: `src/api/job_load.py`
- Start job endpoint: `src/api/job_start.py`
- Unload job endpoint: `src/api/job_unload.py`
- Job status endpoint: `src/api/job_status.py`

There is no reliable non-GUI CNC API call found for unloading a job. The current approach is to load a placeholder file:

- Placeholder file: `resources/no_job_loaded.cnc`
- Placeholder helper: `src/core/placeholder_job.py`

Status should hide the placeholder name so UI/API consumers see no loaded job.

The start-job endpoint has intentionally been made to return early for now with the start endpoint disabled. Do not remove the existing implementation behind that early return unless the user asks.

After successful load-job, the adapter opens the custom jog pad so the operator can home/jog/set offsets before proceeding. The jog pad close/proceed button is the operator confirmation that the machine is positioned.

## Jog Pad Notes

The jog pad is a PyQt5 desktop tool under `src/jog_pad/`. It was split from one large `jog_pad.py` into MVC-ish modules:

- `app.py` for QApplication/window entry
- `pad.py` for main widget/controller wiring
- `client.py` for adapter HTTP calls
- `workers.py` for background request workers
- `widgets.py` for UI widgets
- `config.py` for constants/config
- `jog_pad.py` remains the compatibility launcher/shim

The jog pad intentionally sends requests to the adapter HTTP API, not directly to Eding CNC. Reasons:

- Keeps one owner of `cncapi.dll` state.
- Reuses adapter config such as port and DLL/INI paths.
- Keeps error translation and CNC FIFO message handling in one place.
- Avoids multiple processes talking to the CNC DLL/server independently.

The adapter URL must be config-aware. Default remains `ERP_CNC_ADAPTER_URL` or `http://127.0.0.1:8002`, but launcher code passes the configured adapter URL/port.

The jog pad uses Eding/CNC messages from the CNC FIFO where possible instead of invented success text. Clear FIFO when showing the jog pad, then show operation messages gathered after each action.

Position polling should run only while the jog pad is visible. When hiding/closing the pad, stop coordinate polling and pause-hold. Do not poll homed status continuously; the home button should remain available like Eding GUI.

Jog pad UI preferences:

- Use `resources/logo.ico` for window icon.
- Use icons from `resources/jogpad` for jog/home/reset controls; avoid mismatched Z/Y icons.
- Use `resources/home.bmp` for home where relevant and `resources/reset.bmp` for reset.
- Use configured accent color `ACCENT_BLUE = "#7A4FBF"` for buttons/slider/coordinate widgets.
- Coordinate display should visually resemble Eding CNC machine/work coordinate panels.
- Window should be topmost/elevated above the browser when opened from dashboard.
- Hide native close/minimize buttons; operator should close/proceed from the pad's own button.
- Startup appearance matters: show the window first, then start polling/pause-hold via delayed `QTimer.singleShot`.
- Prefer hiding/reusing the jog pad instead of destroying/recreating where practical.

Pause-hold notes:

- Pause-hold was added to keep sending job pause while jog pad is open, but it can interfere with homing/jogging if enabled.
- Default pause-hold interval should be `0` / disabled.
- If enabled, stop the pause-hold worker/thread when jog pad hides/closes.
- If pause-hold causes motion stop, the UI should indicate pause-hold was responsible rather than showing a misleading drive/E-stop error.

## Homing Notes

Current deterministic home command should be the macro call:

```text
CncRunSingleLine("gosub home_all")
CncWaitSingleLine(...)
```

Do not silently fall back to `M_HOME`. The user wanted deterministic behavior and tested that `gosub home_all` is the one that actually works after a job is loaded.

Observed Eding FIFO output for successful home:

```text
Home Z
Home Y
Home X
home complete!
```

The custom jog pad should show those actual FIFO messages, not generic `gosub home_all returned 0` text.

Other homing experiments and findings:

- `CncSendToGUI(CNC_UIOACTION_HOMESEQ, 0, 0)` may return accepted but did nothing when Eding GUI was not running.
- GUI home behavior depends on Eding GUI/interpreter state and macros; avoid making backend behavior GUI-dependent.
- `CncRunSingleLine("gosub home_all")` can be rejected with `No Job loaded`; user tested and it worked once a job was loaded.
- `CncGetAllAxesHomed` only reads homed state; it does not perform homing.

## Work Coordinates / Zeroing Notes

Machine coordinates are absolute machine position. Work coordinates are offsets in the active work coordinate system.

Eding GUI work-coordinate zeroing can use either G92 or G10 L20 depending on interpreter setting `useG10L20ForZeroing`:

- If enabled, active coordinate system G54-G59.3 is zeroed.
- Otherwise global G92 offset is used.

In Eding GUI, clicking a work coordinate shows a popup like `G92X` with a value field. Custom jog pad should only show zeroing/value controls on the Work tab, not Machine tab.

## CNC Error / Message Notes

Prefer actual Eding/CNC FIFO messages when available. The CNC log FIFO appears to store messages with code/errorClass/subCode/text/function/source. Useful examples observed:

- `No Job loaded`
- `Home Z`, `Home Y`, `Home X`, `home complete!`
- `Server priority not REALTIME, please start as administrator`
- `CPU State = SIMULATION`

For operation results, drain/clear before relevant actions when appropriate, then collect messages after the DLL call and use those for the API response message.

## Startup And Recovery Notes

CNC server startup is shared through `src/core/cnc_server_process.py`. Both adapter startup and `/api/cnc/start` should use the shared helper instead of launching `CncServer.exe` directly.

The adapter now watches for `CncServer.exe` disappearing after startup. When the server disappears, the adapter requests a recovery restart via the installed `scripts/restart.bat`, then exits so the DLL state is recreated in a fresh adapter process.

Why this matters:

- Eding GUI can start/own/kill `CncServer.exe`.
- If `CncServer.exe` is killed and restarted behind the adapter, the old DLL/client state may still point at the old server instance.
- Restarting the adapter is safer than trying to reuse stale DLL state.

`ConnectionManager` treats machine states `1` and `2` as ready-capable. State `2` has been observed as `READY`.

Startup timings added in:

- `main.py`
- `src/app.py`
- `src/core/app_state.py`
- `src/core/task_config.py`

Typical observed installed startup on test machine:

- process entry to app ready: about 0.5-0.8s
- AppState.start: about 0.1-0.3s
- CncServer start: about 0.1-0.3s
- CNC connection ready: about 3-5s
- operator ready message: about 1.5-2s

Daily START-CNC path currently has overhead:

```text
START-CNC shortcut
-> powershell.exe start_cnc_feedback.ps1
-> schtasks /Run ERPCNCAdapterManualStart
-> wscript.exe run_start_cnc_hidden.vbs
-> cmd.exe /c restart.bat
-> powershell.exe Stop-Process
-> timeout 2s
-> powershell.exe read config
-> schtasks /Run ERPCNCAdapter
-> adapter starts/connects
```

Possible daily START-CNC optimizations to consider next:

- Remove/replace fixed 2-second wait in `restart.bat` with process-disappearance polling.
- Avoid PowerShell just to read config in `restart.bat` when Eding GUI auto-start is disabled.
- Disable `show_operator_ready_message` by default because START-CNC feedback already shows readiness.
- Consider one-folder PyInstaller packaging for the adapter runtime to avoid one-file extraction/AV scan on weak PCs.
- Add launcher timestamp before starting adapter to measure pre-log PyInstaller/scheduled-task overhead.

## Installer And Task Notes

Installed task names:

- `ERPCNCAdapter`
- `ERPCNCAdapterWatchdog`
- `ERPCNCAdapterManualStart`
- `ERPCNCAdapterEdingHandoff`

The installer supports passwordless local users by creating interactive scheduled tasks with `-LogonType Interactive -RunLevel Highest` instead of storing a password.

For remote CNC files, configure the scheduled task to run as a Windows user with share access. Running at boot with SYSTEM usually will not access UNC paths.

The watchdog runs every 2 minutes. It previously launched `watchdog.bat` directly and caused a brief CMD window flash. It should now run through hidden VBS:

```text
wscript.exe scripts\watchdog_hidden.vbs
```

Both installer creation and dashboard launch-account reconfiguration should preserve the hidden watchdog action. If a machine still flashes a CMD every 2 minutes, query:

```powershell
schtasks /Query /TN ERPCNCAdapterWatchdog /V /FO LIST
```

The task action should not be direct `watchdog.bat`.

Recent installer speed finding on weak AMD E2-9000e machine:

- Total install was about 32s.
- START-CNC operator task/shortcut setup was about 13.9s.
- Manual START-CNC task registration was about 7.1s.
- Eding handoff task registration was about 2.3s.

Installation speed is less important than daily START-CNC speed because installation is done once.

## Packaging Notes

When adding runtime resource files, update `util_scripts/erp-cnc-adapter.spec`.

The placeholder unload file must be bundled into the installed app.

UPX is disabled in the PyInstaller spec (`upx=False`) to reduce startup/AV overhead on CNC PCs.

Consider one-folder packaging for the adapter runtime if daily startup is still slow. One-file EXEs extract to `_MEI...` on every launch, which can be slow on weak CPUs/disks and antivirus-scanned systems.

## Useful Test Commands

From repo root:

```powershell
.\.venv\Scripts\python.exe -m pytest tests\test_cnc_start_stop.py tests\test_cnc_server_process.py tests\test_app_state.py
.\.venv\Scripts\python.exe -m pytest tests\test_job_load.py tests\test_job_start.py tests\test_job_unload.py tests\test_job_status.py
.\.venv\Scripts\python.exe -m pytest tests\test_request_response_logging.py
.\.venv\Scripts\python.exe -m pytest tests\test_installer_machine_id.py tests\test_task_config.py tests\test_restart_script.py
```

Compile-check changed Python files:

```powershell
.\.venv\Scripts\python.exe -m py_compile <changed-files>
```

## Human Preference Notes

- User wants practical fixes, not theoretical workarounds.
- User prefers deterministic CNC behavior over fallback chains.
- User explicitly rejected GUI-dependent backend behavior where GUI will not be running.
- User wants noisy desktop dialogs/windows stopped.
- User wants monitor/dashboard behavior compact and operational.
- User cares more about daily START-CNC speed than one-time installation speed.
- When something fails on the machine, surface messages to the operator UI, not only logs.

## Future Update Strategy

Current dashboard update flow replaces only `erp-cnc-adapter.exe`. It does not update installed `scripts/`, external `resources/`, task definitions, docs, `VERSION.txt`, or other payload files. Keep this in mind when a release changes runtime resources or installer/runtime scripts.

Future direction: use SVN tags/releases as the source of truth for deployed update packages. A release should be built from a tag such as `/tags/v1.0.2`, include the full runtime payload plus a manifest with version/files/checksums/install actions, and preserve machine-local files such as `config.json` and logs during installation. This would let Git and SVN tags represent the same known release and avoid updating machines with only a standalone EXE swap.

