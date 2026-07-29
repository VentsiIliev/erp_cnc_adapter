## v1.0.6 - 2026-07-29

- Testing make release script

## v1.0.5 - 2026-07-29

- Added dashboard fields for SVN update username and password
- Persisted update credentials through /api/config so operators no longer edit config.json manually
- Kept update password masked in dashboard status and logs

# Changelog

All notable changes to ERP-CNC Adapter are documented here.

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


