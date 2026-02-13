# Update Worker Issue Analysis & Solution

## Problem Discovery

When testing the update mechanism, we discovered that the update_worker.py script was **not actually executing** even though:
- The staged EXE file was saved correctly ✅
- The update_worker.py was copied to the installation directory ✅
- The spawn command looked correct in logs ✅

## Root Cause

The issue has TWO parts:

### Part 1: Process Not Starting
The update worker process spawned with `DETACHED_PROCESS` flag was not actually starting. When we manually ran the command, it worked perfectly:

```
C:\Python311-32\python.exe "C:\Users\Notebook 1\Desktop\test_install\update_worker.py" --exe-path ... --staged-path ... --service-name ERPCNCAdapter
```

This revealed that the subprocess.Popen() with DETACHED_PROCESS flags was failing silently.

### Part 2: File Lock Issue  
When we manually ran the update worker, it failed with:
```
PermissionError: [Errno 13] Permission denied: 'C:\\Users\\Notebook 1\\Desktop\\test_install\\erp-cnc-adapter.exe'
```

This is because **the service was still running** and had the EXE file locked.

## Solution Implemented

### 1. Use Batch File Launcher ✅

Modified `src/handlers/update.py` to create a batch file that launches the update worker:

```python
# Create a batch file to launch the update worker as a truly detached process
batch_file = os.path.join(exe_dir, "run_update.bat")
batch_content = f'''@echo off
start "Update Worker" /B "{python_exe}" "{worker}" --exe-path "{exe_path}" --staged-path "{staged_path}" --service-name {SERVICE_NAME}
'''

with open(batch_file, 'w') as f:
    f.write(batch_content)

# Execute the batch file detached
subprocess.Popen(
    [batch_file],
    shell=True,
    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP | subprocess.DETACHED_PROCESS,
)
```

**Why this works**: The Windows `START /B` command is specifically designed to start background processes that survive the parent process termination.

### 2. Removed Unnecessary Delay ✅

Removed the arbitrary 2-second wait at the start of update_worker.py:

```python
# REMOVED: time.sleep(2) for "HTTP response to complete"
```

The HTTP response completes independently since the worker is detached.

### 3. Increased Service Stop Wait Time ✅

Increased the wait time after stopping the service from 3 to 5 seconds to ensure the EXE file handle is fully released:

```python
time.sleep(5)  # Wait for service to fully stop and release file handles
```

## Expected Behavior After Fix

1. **User uploads EXE** via `/update` page
2. **Staged file saved** to installation directory (e.g., `C:\Users\...\test_install\staged-update.exe`)
3. **Update worker copied** to installation directory
4. **Batch launcher created** (`run_update.bat`)
5. **Batch file executed** as detached process
6. **HTTP response sent** immediately to user ("Update scheduled...")
7. **Update worker runs independently**:
   - Stops Windows service
   - Waits 5 seconds for file handles to release
   - Backs up current EXE
   - Replaces with staged EXE
   - Starts Windows service
   - Logs everything to `logs/update.log`
8. **Service restarts** with new version
9. **Automatic rollback** if anything fails

## Files Modified

1. **src/handlers/update.py**
   - Changed `_spawn_updater()` to use batch file launcher
   - More reliable process detachment

2. **src/update_worker.py**
   - Removed unnecessary 2-second delay
   - Increased service stop wait from 3 to 5 seconds
   - Better logging

## Testing

### Manual Test That Worked
```powershell
Start-Process -FilePath "C:\Python311-32\python.exe" -ArgumentList "`"C:\Users\Notebook 1\Desktop\test_install\update_worker.py`" --exe-path `"C:\Users\Notebook 1\Desktop\test_install\erp-cnc-adapter.exe`" --staged-path `"C:\Users\Notebook 1\Desktop\test_install\staged-update.exe`" --service-name ERPCNCAdapter" -NoNewWindow
```

This confirmed:
- Update worker script works correctly
- Service stop/start logic works
- Backup creation works
- File replacement works (when service is stopped)

### Next Build Test

After rebuilding with these fixes, the update should work automatically via the web interface.

## Why Batch File Method Works

The batch file method is more reliable because:

1. **Windows Native**: `START /B` is designed for background processes
2. **Process Detachment**: The batch file exits immediately after starting the Python process
3. **Survives Parent Death**: The spawned Python process continues even after the service stops
4. **No Handle Inheritance Issues**: Cleaner separation between processes

## Verification Checklist

After deploying the new build:

- [ ] Upload EXE via `/update` page
- [ ] Check `logs/adapter.log` for "Spawning update worker" message
- [ ] Verify `run_update.bat` is created in installation directory  
- [ ] Check `logs/update.log` is created with update progress
- [ ] Service stops automatically
- [ ] EXE is replaced
- [ ] Backup file created (`.bak.YYYYMMDD_HHMMSS`)
- [ ] Service restarts automatically
- [ ] Version updates correctly
- [ ] Cleanup: `run_update.bat` and `update_worker.py` remain in directory for future updates

## Notes

- The batch file and update_worker.py files remain in the installation directory after the update completes - this is by design for future updates
- Python interpreter must be installed (C:\Python311-32\python.exe or similar)
- The update worker has automatic rollback on failure
- Maximum 5 backups are kept (older ones auto-deleted)

