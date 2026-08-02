## v1.0.16 - 2026-07-29

- Allow the start job endpoint to call Eding CncRunOrResumeJob when CNC state is Running, so a feed-hold paused job can resume instead of being blocked as already running.

## v1.0.15 - 2026-07-29

- Allow the start job endpoint to call Eding CncRunOrResumeJob when CNC state is Running, so a feed-hold paused job can resume instead of being blocked as already running.

## v1.0.15 - 2026-07-29

- Allow the start job endpoint to call Eding CncRunOrResumeJob when CNC state is Running, so a feed-hold paused job can resume instead of being blocked as already running.

## v1.0.14 - 2026-07-29

- Increased the buttons poller interval from 500ms to 50ms

## v1.0.13 - 2026-07-29

- Remove the temporary start-job gate so /api/cnc/job/start sends the actual CNC start job request again

## v1.0.12 - 2026-07-29

- Fix dashboard navigation buttons so Overview, Live Monitor, Configuration, Maintenance, and Testing scroll to their content sections instead of the sidebar buttons

## v1.0.11 - 2026-07-29

- Testing make release script build installer

## v1.0.10 - 2026-07-29

- Run frozen update worker from a temporary EXE so the installed adapter EXE can be replaced
- Preserve installer-generated VBS and handoff scripts during full ZIP updates

## v1.0.9 - 2026-07-29

- Testing make release script build installer

## v1.0.8 - 2026-07-29

- Fix updater to stop all installed adapter processes before replacing erp-cnc-adapter.exe

## v1.0.7 - 2026-07-29

- Testing make release script build installer

## v1.0.6 - 2026-07-29

- Testing make release script

## v1.0.5 - 2026-07-29

- Added dashboard fields for SVN update username and password
- Persisted update credentials through /api/config so operators no longer edit config.json manually
- Kept update password masked in dashboard status and logs

# Changelog

All notable changes to ERP-CNC Adapter are documented here.

## v1.4.1 - 2026-08-02

- latest

## v1.4.0 - 2026-07-31

- latest

## v1.3.9 - 2026-07-31

- Changed:

## v1.3.8 - 2026-07-31

- Changed:

## v1.3.8 - 2026-07-31

- What changed:

## v1.3.7 - 2026-07-31

- Changed:

## v1.3.6 - 2026-07-31

- updated the preflight to establish the SMB session inside the preflight process itself:

## v1.3.5 - 2026-07-31

- startup preflight PID, Windows user, session ID, install dir, and resolved base_dir

## v1.3.4 - 2026-07-31

- Added a startup lock in [launch_adapter_after_network.ps1](C:\Users\Notebook

## v1.3.3 - 2026-07-31

- launch_adapter_after_network.ps1 now resolves the job share like this:

## v1.3.2 - 2026-07-31

- scripts/restart.bat now creates a start-cnc.lock during manual START-CNC so duplicate invocations are ignored instead of overlapping.

## v1.3.1 - 2026-07-30

- Added scripts/launch_adapter_after_network.ps1.

## v1.3.0 - 2026-07-30

- Added scripts/launch_adapter_after_network.ps1.

## v1.3.0 - 2026-07-30

- fixing no access to mills after boot

## v1.2.9 - 2026-07-30

- Start the physical RUN/PAUSE button monitor only after CNC is connected and interpreter state is ready.

## v1.2.8 - 2026-07-30

- 

## v1.2.7 - 2026-07-30

- Added sstatus indicator poll, fixed watchdog trigger because of dashboard updates, and fixed watchdog trigger when startup is slow and it triggeres reset before even cnc has ever been in ready state

## v1.2.6 - 2026-07-30

- Added sstatus indicator poll, fixed watchdog trigger because of dashboard updates, and fixed watchdog trigger when startup is slow and it triggeres reset before even cnc has ever been in ready state

## v1.2.5 - 2026-07-30

- fixed splash not visible (removed the startup terminal)

## v1.2.4 - 2026-07-30

- fixed splash not visible (removed the startup terminal)

## v1.2.3 - 2026-07-30

- fixed splash not visible

## v1.2.2 - 2026-07-30

- removed adapter ready message popup

## v1.2.1 - 2026-07-30

- Added START-CNC splash screen using the ERP-CNC logo.

## v1.1.1 - 2026-07-30

- Added START-CNC splash screen using the ERP-CNC logo.

## v1.1.1 - 2026-07-30

- Fixed update worker process handling so it cannot terminate itself during an update.

## v1.1.0 - 2026-07-30

- Fixed update worker process handling so it cannot terminate itself during an update.

## v1.1.0 - 2026-07-30

- Added dedicated CNC FIFO message listener.
- Added scrollable jog pad CNC message panel showing recent Eding messages.
- Fixed jog pad layout so the message
  panel does not squash or overlap jog controls.

## v1.0.19 - 2026-07-30

- testing no installer release script flag

## v1.0.18 - 2026-07-30

- Added the PL logo icon to the jog pad title bar by enabling the native window system-menu icon area.

## v1.0.17 - 2026-07-29

- Moved physical RUN/PAUSE button handling from the jog pad into the adapter backend, so the operator buttons keep working even when the jog pad is closed.

## v1.0.1 - 2026-07-29

- Added read-only physical RUN/PAUSE button diagnostics through `/api/cnc/physical-buttons`.
- Added temporary jog pad indicators for RUN, PAUSE, HOLD, and MOTION so machine testing does not depend on fast-moving logs.
- Interpreted physical RUN input as active-low: `raw=1` while released displays inactive, and `raw=0` while pressed displays active.
- Kept PAUSE using the Eding CNC DLL logical reading because it reports active when pressed on the tested machine.
- Exposed `runRaw`, `pauseRaw`, `runLogical`, and `pauseLogical` in diagnostics to make input wiring and inversion visible during testing.
- Fixed the jog pad all-home button to use `resources/home.bmp` while keeping per-axis work-zero icons separate.

## v1.0.0 - 2026-07-28

- Initial stable release baseline for ERP-CNC Adapter.
- Added adapter dashboard, installer workflow, scheduled task setup, watchdog/restart support, CNC job load/start/status behavior, and PyQt5 jog pad integration.











































