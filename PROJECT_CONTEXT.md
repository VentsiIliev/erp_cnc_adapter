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


## Current Context Snapshot - 2026-07-30

This section captures the latest state from the long stabilization session. It intentionally includes decisions, release/update workflow, CNC behavior, known machine quirks, and test coverage notes, not only test details.

## Current Working State

Recent test audit result:

```text
512 passed in 16.37s
38 test files
about 502 explicit test functions
```

Dirty files observed during the audit:

```text
D adapter.pid
M scripts/start_cnc_splash.ps1
```

Do not assume those are safe to revert. `adapter.pid` is runtime state. `scripts/start_cnc_splash.ps1` may contain ongoing splash-screen work.

## Corrected Job Start Context

The old note above saying the start-job endpoint is disabled is stale.

Current behavior:

- Start job endpoint is enabled: `src/api/job_start.py`.
- It calls Eding via `client.run_job()`, which maps to `CncRunOrResumeJob()`.
- The monitor `_was_running` gate was removed because it blocked valid resume attempts.
- Real machines can show CNC state `6` even after the operator pressed pause/feed-hold, so state `6` is no longer an automatic adapter-side rejection.
- Error states `3`, `4`, and `5` should still be rejected before calling Eding.
- If Eding rejects the call, prefer Eding/FIFO messages where available rather than inventing generic text.

The production issue that led to this: physical RUN started a job correctly, PAUSE paused it, but pressing RUN again returned “cannot start another job while one is executing” while CNC state still showed running. The fix direction was to let `CncRunOrResumeJob()` decide instead of blocking on monitor state or state `6`.

## Physical RUN/PAUSE Buttons

Physical button polling is backend-owned now, not jog-pad-owned. The operator must be able to start/pause from physical buttons even if the jog pad is closed.

Implementation:

- Backend monitor/service: `src/cnc/physical_button_monitor.py`
- AppState starts/stops the service with the adapter.
- Jog pad indicators are display-only diagnostics and should not duplicate backend start/pause commands.
- Config setting: `physical_button_poll_interval_ms`
- Current intended default: 50 ms

Observed input behavior:

- RUN line can read true while released, false while pressed, then true again when released.
- RUN action is therefore release-confirmed: initially released does nothing, press marks intent, release triggers start/resume.
- PAUSE behaves as pressed=true edge logic.

Important edge cases:

- RUN should be ignored in CNC error states.
- PAUSE should only call pause when a running job is active.
- The real machine still needs a manual test for start, pause, then RUN resume while state is still `6`.

## CNC FIFO / Operator Messages

Current direction: prefer real Eding CNC FIFO messages over custom invented messages.

Implementation:

- Backend message service: `src/cnc/message_monitor.py`
- Recent messages endpoint: `/api/cnc/messages/recent?limit=N`
- Clear endpoint: `/api/cnc/messages/clear`
- Jog pad displays recent messages in a fixed-height scrollable message area.

Known good FIFO messages observed:

```text
Home Z
Home Y
Home X
home complete!
No Job loaded
Server priority not REALTIME, please start as administrator
CPU State = SIMULATION
```

Current UI principle:

- Do not wire every button to a made-up message if the FIFO can provide real Eding text.
- Reset/home/jog responses should prefer FIFO messages when available.
- The operator should see important CNC messages in the jog pad/dashboard, not only backend logs.

## Homing

Current deterministic homing behavior should remain:

```text
CncRunSingleLine("gosub home_all")
CncWaitSingleLine(...)
```

Do not silently fall back to `M_HOME`. The user explicitly wanted deterministic behavior and tested that `gosub home_all` is the command that runs successfully once a job is loaded.

Findings:

- `CncSendToGUI(CNC_UIOACTION_HOMESEQ, 0, 0)` may return accepted but did nothing when Eding GUI was not running.
- GUI-dependent backend behavior is not acceptable unless the user explicitly asks for it.
- `CncRunSingleLine("gosub home_all")` can return `No Job loaded`; after loading a job, it worked.
- `CncGetAllAxesHomed` only reads homed state and does not perform homing.

## Jog Pad Current Context

Jog pad lives under `src/jog_pad/` and is split into MVC-ish modules:

- `app.py` for QApplication/window entry
- `pad.py` for main widget/controller wiring
- `client.py` for adapter HTTP calls
- `workers.py` for background worker threads
- `widgets.py` for UI widgets
- `config.py` for constants/theme/icons
- `jog_pad.py` compatibility launcher/shim

Important behavior:

- Jog pad sends requests to the adapter HTTP API, not directly to Eding CNC.
- This keeps one owner of `cncapi.dll` state and centralizes error/FIFO handling.
- Window should appear quickly; show the window first, then start pollers with delayed `QTimer.singleShot`.
- When hiding/closing the pad, stop coordinate polling and pause-hold.
- Do not continuously poll homed status; home buttons should remain available like Eding GUI.
- Pause-hold default should be `0` / disabled.
- If pause-hold is enabled and causes motion stop, UI should say pause-hold did it instead of implying drives/E-stop.

UI preferences:

- Use `resources/logo.ico` as window icon.
- Use `resources/home.bmp` for home-all where relevant.
- Use `resources/reset.bmp` for reset.
- Use original Eding-style icons from `resources/jogpad`.
- Use configured accent/button color consistently on buttons, slider, coordinate widgets.
- Coordinate panels should resemble Eding machine/work coordinate widgets.
- Reset button should be top-right; home-all belongs with other homing controls.
- FIFO message section must not squash or overlap jog controls; use a fixed-height scroll area.

Known recent issue:

- Adding the message section initially squashed top buttons; fixed direction was a scrollable fixed-height message area.

## START-CNC, Splash, And Shortcut Context

User wants daily START-CNC to be quiet and fast:

- No visible terminal window.
- Splash/feedback should use `resources/logo.ico`.
- Old “CNC started” popup should be removed/suppressed because splash/feedback should handle readiness.

Known installed shortcut issue:

A machine still showed the Public Desktop START-CNC shortcut targeting PowerShell directly:

```text
TargetPath: C:\WINDOWS\System32\WindowsPowerShell\v1.0\powershell.exe
Arguments: -NoProfile -ExecutionPolicy Bypass -File "C:\Program Files (x86)\ERP-CNC Adapter\scripts\start_cnc_feedback.ps1"
WorkingDirectory: C:\Program Files (x86)\ERP-CNC Adapter\scripts
IconLocation: C:\Program Files (x86)\ERP-CNC Adapter\resources\logo.ico,0
```

That shortcut is old and will show a terminal. Desired direction is a hidden `wscript.exe`/VBS launcher path, for example `scripts/start_cnc_hidden.vbs`, which then starts the feedback/splash path hidden.

If splash is not visible:

- Check whether installed `scripts/start_cnc_splash.ps1` exists and is packaged.
- Check generated `start_cnc_hidden.vbs` and `start_cnc_feedback.ps1` contents.
- Check whether update worker repaired the Public Desktop shortcut.
- Check whether the shortcut still points directly to PowerShell.
- Check whether the script is running in a non-interactive context where WPF cannot show.

## Startup And Recovery

CNC server startup is shared through `src/core/cnc_server_process.py`.

The adapter watches for `CncServer.exe` disappearing after startup. When the server disappears, the adapter requests a recovery restart via installed `scripts/restart.bat`, then exits so DLL state is recreated in a fresh process.

Reason:

- Eding GUI can start/own/kill `CncServer.exe`.
- If the server is killed and restarted behind the adapter, old DLL state may still point at the old server instance.
- Restarting the adapter is safer than trying to reuse stale DLL state.

Known daily START-CNC overhead path:

```text
START-CNC shortcut
-> hidden VBS / feedback script
-> scheduled task ERPCNCAdapterManualStart
-> restart.bat
-> stop adapter / Eding GUI / CncServer
-> read config
-> schtasks /Run ERPCNCAdapter
-> adapter starts/connects
```

Possible startup optimizations:

- Remove fixed sleeps in restart scripts where process polling is enough.
- Avoid PowerShell where batch can do the work.
- Keep Eding GUI auto-start disabled unless explicitly needed.
- Consider one-folder PyInstaller packaging if one-file extraction/AV scan remains slow on weak CNC PCs.

## Update System Current Context

The old note above saying dashboard update only replaces the EXE is stale.

Current dashboard update flow is full-package based:

1. Check `trunk/release/latest.json` in SVN.
2. Download the tagged update ZIP.
3. Stage as `staged-update.zip` in install dir.
4. Copy the current EXE to temp and run it as `--update-worker`.
5. Stop installed adapter processes.
6. Backup the full install directory.
7. Install the package.
8. Preserve local machine files.
9. Restart scheduled task `ERPCNCAdapter`.

Important files:

- API: `src/api/update.py`
- Worker: `src/update_worker.py`
- Package builder: `util_scripts/create_update_package.py`
- Release script: `util_scripts/release.ps1`

Preserve during update/rollback:

- `config.json`
- `logs/*`
- `adapter.pid`
- `.update-lock`
- `backups/*`
- `staged-update.*`
- generated/local launcher scripts where applicable

Update worker lessons:

- Do not run update worker from installed `erp-cnc-adapter.exe` and then try to replace that same EXE.
- Copy worker EXE to temp first.
- Do not taskkill by image name; it can kill the temp update worker.
- Kill only the launcher adapter PID and other processes whose executable path exactly equals installed adapter EXE path.
- PowerShell/CIM process enumeration can time out on weak PCs; WMIC fallback exists.
- If target EXE remains locked, fail cleanly and keep backup.
- Rollback must restore the whole previous install directory, not only the EXE.

Update credentials:

- Dashboard can save SVN credentials to `config.json` as `update_username` and `update_password`.
- Environment overrides: `ERP_CNC_UPDATE_USERNAME`, `ERP_CNC_UPDATE_PASSWORD`.
- Never log raw passwords; use masked form like `N***1`.

Current SVN URL shape:

```text
latest:
https://192.168.2.101:8443/svn/2245_RouterRetrofit/trunk/release/latest.json

package:
https://192.168.2.101:8443/svn/2245_RouterRetrofit/tags/vX.Y.Z/release/erp-cnc-adapter-update-vX.Y.Z.zip

manifest:
https://192.168.2.101:8443/svn/2245_RouterRetrofit/tags/vX.Y.Z/release/manifest.json
```

Manual URL test:

```powershell
curl.exe -k -u USER:PASS "https://192.168.2.101:8443/svn/2245_RouterRetrofit/trunk/release/latest.json"
```

## Release / Versioning Context

User prefers GitHub but company requires local SVN too. Release flow should keep both aligned.

Known repo paths:

- Git repo: `C:\Users\Notebook 1\Desktop\github_repos\erp_cnc_adapter`
- SVN working copy: `C:\Users\Notebook 1\Desktop\erp_cnc_adapter_svn`
- SVN repo: `https://192.168.2.101:8443/svn/2245_RouterRetrofit`

Release script:

- `util_scripts/release.ps1`
- Supports `-NoInstaller` for update-only releases.
- Should build update package and optionally installer.
- Should commit/tag/push Git.
- Should mirror trunk to SVN.
- Should create SVN tag.
- Should import release package files.
- Should update `trunk/release/latest.json`.

Known SVN issue:

- Large `svn import` uploads can fail with `An existing connection was forcibly closed by the remote host`.
- Retrying the single failed import usually works once network/server is reachable.
- Verify release state with:

```powershell
svn ls "https://192.168.2.101:8443/svn/2245_RouterRetrofit/tags/vX.Y.Z/release"
svn cat "https://192.168.2.101:8443/svn/2245_RouterRetrofit/trunk/release/latest.json"
```

Release notes/changelog:

- Maintain `CHANGELOG.md` for Git and SVN users.
- Release notes should be operational and specific, not generic.
- For update-only releases use `-NoInstaller` where appropriate.

Version history landmarks:

- v1.0.0: baseline current-state build.
- v1.0.1: physical RUN reading/inversion explanation.
- v1.0.2: SVN update metadata and release package direction.
- v1.0.3-v1.0.17: dashboard updates, credentials, full update packages, worker lock fixes, physical buttons, release automation.
- v1.1.0: dedicated CNC FIFO message listener and scrollable jog pad message panel.
- v1.2.x: splash/START-CNC hidden launch work; installed shortcut behavior still needed verification.

PowerShell release command examples:

```powershell
.\util_scripts\release.ps1 -Version 1.1.0 -NoInstaller -Notes "Added dedicated CNC FIFO message listener and scrollable jog pad CNC message panel. Fixed layout so messages do not squash jog controls."
```

If multiple notes are needed, check the current release script param block first. Previous attempts showed `-ChangeLog` was not a parameter and passing multiple bare strings to `-Notes` was interpreted incorrectly.

## Test Coverage Audit - 2026-07-30

Current result:

```text
512 passed in 16.37s
```

Coverage is strong for:

- FastAPI app creation/routes/errors.
- AppState startup, PID handling, stale process cleanup, CNC server loss recovery.
- Connection manager retry/heartbeat/lifecycle.
- CNC server launcher.
- CNC motion endpoints: position, jog, stop jog, move, zero, reset, home, messages, physical buttons.
- Job load/start/status/unload and placeholder unload strategy.
- Dashboard update check/download/apply/rollback flow.
- Full update package installation/removal/preserve behavior.
- Installer worker and task configuration.
- Release/build script structure.
- Jog pad adapter HTTP client and launcher.
- Backend physical button monitor.
- Backend CNC FIFO message service.

Main remaining risk areas:

1. Real Eding CNC integration is not covered by automated tests. CI uses fake/mock clients, not real `cncapi.dll`, `CncServer.exe`, or hardware states.
2. Physical RUN/PAUSE behavior needs real-machine validation for start, pause, and resume while Eding reports state `6`.
3. Jog pad PyQt UI layout/touch behavior is lightly tested. Continuous touch jog, timers stopping on hide, icon rendering, and no-overlap should be manually or offscreen tested.
4. Update worker tests mock process replacement. Real Program Files permissions, locked EXE, antivirus, scheduled task, and weak PC timing still need manual validation.
5. START-CNC splash/hidden shortcut behavior is not fully proven by automated tests. Existing installations may retain old shortcuts.
6. Dashboard navigation/update UI is template-tested, not browser-tested.
7. SVN release automation needs validation that `latest.json` points to existing package/manifest and that large imports finished.
8. UNC path/job discovery is mocked; real scheduled-task account permissions remain a manual deployment check.
9. Credentials should have explicit masking tests for HTTP logs/dashboard/update logs.
10. FIFO behavior should be tested for delayed messages, duplicate messages, read failures, and clear-while-polling races.

Recommended pre-wrap manual checklist:

- Install fresh on target CNC PC.
- START-CNC from Public Desktop shortcut: no terminal window, splash visible, adapter reachable.
- Load job from UNC under scheduled task account.
- Open jog pad quickly and verify layout/no overlap at real screen resolution.
- Continuous jog with touchscreen press-and-hold.
- Home all with loaded job; verify FIFO shows `Home Z | Home Y | Home X | home complete!` or equivalent actual Eding messages.
- Reset CNC; verify operator sees actual Eding/FIFO message where available.
- Physical RUN starts job with jog pad closed.
- Physical PAUSE pauses job with jog pad closed.
- Physical RUN resumes after pause/feed-hold.
- Dashboard update from previous version to latest.
- Confirm update restarts adapter and preserves `config.json` and logs.
- Rollback test from dashboard if a backup exists.
- Close Eding GUI and verify adapter recovery behavior if CncServer is killed.

## Operator-Facing Principles

- Prefer actual Eding messages over generic adapter guesses.
- Keep daily startup fast and quiet.
- Avoid visible CMD/PowerShell windows from background tasks.
- Keep CNC behavior deterministic; avoid hidden fallback chains unless explicitly requested.
- Surface actionable failures in jog pad/dashboard, not only logs.
- Do not depend on Eding GUI unless the feature explicitly requires GUI and user accepts it.
