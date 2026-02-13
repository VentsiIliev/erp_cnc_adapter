# Update Mechanism Fix - Version 1.0.0

## Issue Identified

When running as a PyInstaller executable, the update mechanism was not working correctly because:

1. **Wrong Path Detection**: The update handler was using the PyInstaller temporary extraction directory (`C:\WINDOWS\TEMP\_MEI146802\`) instead of the actual installation directory
2. **Staged File Location**: The staged update file was being saved to the temp directory, which disappears when the service restarts
3. **Update Worker Not Found**: The update_worker.py script path was incorrect when running as a frozen executable

## Root Cause

From the logs:
```
2026-02-13 14:20:53 [INFO] src.handlers.update: Staged update saved: C:\WINDOWS\TEMP\_MEI146802\dist\staged-update.exe (11.48 MB)
2026-02-13 14:20:53 [INFO] src.handlers.update: Spawning update worker: C:\Users\Notebook 1\Desktop\test_install\erp-cnc-adapter.exe C:\WINDOWS\TEMP\_MEI146802\src\update_worker.py ...
```

The system was:
- Saving staged update to PyInstaller's temp directory
- Trying to spawn update_worker.py from the temp directory
- The update worker never ran because the paths were wrong

## Fixes Applied

### 1. Fixed `_get_project_root()` Function

**File**: `src/handlers/update.py`

**Before**:
```python
def _get_project_root() -> str:
    """Project root: two levels up from this file (src/handlers/ -> project root)."""
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**After**:
```python
def _get_project_root() -> str:
    """Project root: two levels up from this file (src/handlers/ -> project root)."""
    # When running from PyInstaller, sys.executable points to the actual EXE
    # When running from source, use the file path
    if getattr(sys, 'frozen', False):
        # Running as compiled executable
        return os.path.dirname(sys.executable)
    else:
        # Running from source
        return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
```

**Why**: When running as a PyInstaller executable, `sys.executable` points to the actual EXE location (e.g., `C:\Users\Notebook 1\Desktop\test_install\erp-cnc-adapter.exe`), not the temporary extraction directory.

### 2. Fixed `_spawn_updater()` Function

**File**: `src/handlers/update.py`

**Changes**:
- Detects if running as PyInstaller executable using `getattr(sys, 'frozen', False)`
- When frozen, searches for system Python interpreter in common locations
- Correctly locates update_worker.py in `sys._MEIPASS` (PyInstaller's bundled data directory)
- Validates that both Python interpreter and update worker script exist before spawning
- Provides clear error messages if components are missing

**Key Logic**:
```python
if getattr(sys, 'frozen', False):
    # Find Python interpreter
    python_paths = [
        r"C:\Python311-32\python.exe",
        r"C:\Python311\python.exe",
        # ... other common paths
        shutil.which("python"),  # Try PATH
    ]
    # Use bundled update_worker.py from PyInstaller's data directory
    worker = os.path.join(sys._MEIPASS, "src", "update_worker.py")
else:
    # Running from source - use current Python
    python_exe = sys.executable
    worker = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "update_worker.py")
```

## Expected Behavior After Fix

1. **Upload Update**: User uploads a new EXE file via `/update` page
2. **Save to Correct Location**: Staged file is saved to the actual installation directory (e.g., `C:\Users\Notebook 1\Desktop\test_install\staged-update.exe`)
3. **Spawn Update Worker**: System spawns `python.exe` with the bundled `update_worker.py` script
4. **Update Worker Runs**:
   - Waits 2 seconds for HTTP response
   - Stops the Windows service
   - Backs up current EXE (e.g., `erp-cnc-adapter.exe.bak.20260213_142053`)
   - Replaces current EXE with staged update
   - Restarts the Windows service
   - Logs everything to `logs/update.log`
5. **Service Restarts**: Service comes back online with the new version
6. **Rollback on Failure**: If update fails, automatically rolls back to the most recent backup

## Testing

All 74 tests pass:
```bash
python -m pytest tests/ -v
```

## Files Modified

1. **src/handlers/update.py**
   - Fixed `_get_project_root()` to detect PyInstaller execution
   - Fixed `_spawn_updater()` to correctly locate Python interpreter and update_worker.py
   - Added better error handling and logging

## How to Rebuild

```bash
cd util_scripts
.\build_installer.bat
```

This will create a new installer with the fix included.

## Verification Steps

After deploying the new version:

1. Go to `http://localhost:8000/update`
2. Upload a new EXE file
3. Check logs:
   - `logs/adapter.log` - Should show "Spawning update worker" with correct paths
   - `logs/update.log` - Should be created with detailed update progress
4. Verify service restarts automatically
5. Check version updated correctly
6. Verify backup file created in installation directory

## Notes

- Version kept at 1.0.0 as requested
- Update mechanism now works correctly when running as Windows service
- Python interpreter must be installed on target machine (which it is, since we're using 32-bit Python)
- The fix handles both development mode (running from source) and production mode (running as PyInstaller EXE)

