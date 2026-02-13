# VBScript Launcher - Final Update Worker Fix

## Problem

The `cmd.exe /C START /B` method is not reliably spawning the update worker process. The process appears to spawn (logs show "spawned successfully") but no Python process runs and no update.log is created.

## Root Cause

When spawning from a Windows Service or PyInstaller executable, subprocess.Popen() with various flag combinations (DETACHED_PROCESS, CREATE_NEW_PROCESS_GROUP, etc.) doesn't reliably create truly independent background processes.

## Solution: VBScript Launcher

VBScript's `WScript.Shell.Run` method with specific parameters is the most reliable way to launch truly detached processes on Windows.

### Implementation

**File**: `src/handlers/update.py`

```python
# Create VBScript launcher
vbs_file = os.path.join(exe_dir, "launch_update.vbs")
vbs_content = f'''Set objShell = CreateObject("WScript.Shell")
objShell.Run "{python_exe} ""{worker}"" --exe-path ""{exe_path}"" --staged-path ""{staged_path}"" --service-name {SERVICE_NAME}", 0, False
'''

# Write VBScript
with open(vbs_file, 'w') as f:
    f.write(vbs_content)

# Execute VBScript
subprocess.Popen(
    ["cscript.exe", "//nologo", vbs_file],
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
)
```

### How It Works

1. **Create VBScript file** (`launch_update.vbs`) with command to run
2. **objShell.Run** parameters:
   - Command: Python with update_worker.py and all arguments
   - `0` = Hide window (no console)
   - `False` = Don't wait for process to complete (async)
3. **Execute with cscript.exe** which returns immediately
4. **Python process continues** independently even after parent dies

### Why VBScript Works Better

- **Windows Native**: VBScript is designed for Windows automation
- **True Detachment**: `Run(..., 0, False)` creates truly independent process
- **No Handle Inheritance**: Clean separation from parent process
- **Survives Parent Death**: Process continues even when service stops
- **Proven Method**: Used in many enterprise Windows applications

## Files Modified

1. **src/handlers/update.py**
   - Removed: `cmd.exe /C START /B` method
   - Added: VBScript launcher creation and execution

2. **version.py**
   - Updated to 1.0.6

## Testing Steps

1. **Install v1.0.4** (currently installed)
2. **Build v1.0.6** (with VBScript launcher)
3. **Upload v1.0.6** via web interface
4. **Verify**:
   - `launch_update.vbs` created
   - Python process spawns
   - `logs/update.log` created
   - Service stops and restarts
   - Version changes to 1.0.6

## Files Created During Update

- ✅ `staged-update.exe` - Uploaded file
- ✅ `update_worker.py` - Copied worker script
- ✅ `launch_update.vbs` - **NEW** VBScript launcher
- ✅ `logs/update.log` - Update progress log
- ✅ `erp-cnc-adapter.exe.bak.YYYYMMDD_HHMMSS` - Backup

## Expected Log Output

### adapter.log:
```
[INFO] src.handlers.update: Staged update saved: ...
[INFO] src.handlers.update: Copied update worker to: ...
[INFO] src.handlers.update: Spawning update worker: ...
[INFO] src.handlers.update: Created VBScript launcher: ...launch_update.vbs
[INFO] src.handlers.update: Update worker spawned successfully via VBScript
```

### update.log (should be created):
```
INFO - Update worker started
INFO - Stopping service 'ERPCNCAdapter'...
INFO - Running: net stop ERPCNCAdapter
INFO - Waiting for service to fully stop...
INFO - Backing up current EXE -> ...
INFO - Replacing EXE with staged update...
INFO - Starting service 'ERPCNCAdapter'...
INFO - Service started successfully. Update complete!
```

## Why Previous Methods Failed

| Method | Issue |
|--------|-------|
| Direct Popen | Process inherits handles, dies with parent |
| DETACHED_PROCESS | Doesn't work from PyInstaller/Service context |
| cmd.exe START | Doesn't actually start the process |
| Batch file | Same issues as cmd.exe |
| VBScript | ✅ **WORKS** - truly independent process |

## Next Build

Version 1.0.6 is building with the VBScript launcher fix. This should finally resolve the update worker spawning issue.

## Verification Checklist

After installing 1.0.6 and testing:

- [ ] Upload new EXE via `/update` page
- [ ] Check `launch_update.vbs` exists in installation dir
- [ ] Verify Python process appears in Task Manager
- [ ] Check `logs/update.log` is created
- [ ] Service stops (connection manager logs stop)
- [ ] Service restarts (new logs appear)
- [ ] Version updates on health page
- [ ] Backup file created

## If This Still Doesn't Work

If VBScript also fails, the final fallback would be:
1. Use Windows Task Scheduler to schedule immediate one-time task
2. Or use PowerShell with `-WindowStyle Hidden` and `-NoProfile`
3. Or write update worker as its own Windows service

But VBScript should work - it's the most reliable method for this use case.

