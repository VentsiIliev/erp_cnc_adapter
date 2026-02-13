# Update System - Current Status & Testing Plan

## What We've Built

### Version Progression
- **1.0.0** → Initial release
- **1.0.3** → Added python-multipart, fixed paths
- **1.0.4** → First attempt with dedicated update page
- **1.0.5** → Removed 2-second delay, increased stop wait
- **1.0.6** → VBScript launcher implementation
- **1.0.7** → Currently building (VBScript launcher + all fixes)

## Current Situation

You have **v1.0.6 installed** and running from:
- Installation: `C:\Users\Notebook 1\Desktop\test_install\`
- Running as: Windows Service (ERPCNCAdapter)

## The VBScript Fix

### What Changed in v1.0.6/1.0.7

**Previous attempts that failed:**
- Direct subprocess.Popen() - didn't survive
- DETACHED_PROCESS flags - didn't start
- cmd.exe START command - didn't execute
- Batch file launcher - didn't work

**Current method (VBScript):**
```python
# Create VBScript
vbs_content = '''Set objShell = CreateObject("WScript.Shell")
objShell.Run "python.exe update_worker.py ...", 0, False
'''

# Execute VBScript
subprocess.Popen(["cscript.exe", "//nologo", vbs_file], ...)
```

### Why VBScript Should Work

1. **Windows native automation** - designed for this
2. **Run(..., 0, False)** - hide window, don't wait
3. **Process independence** - survives parent termination
4. **Proven technology** - used in enterprise apps

## Testing Plan for v1.0.7

### Step 1: Install/Run v1.0.7
Once build completes:
```
Option A: Run installer
  dist\ERP-CNC-Adapter-Setup-v1.0.7.exe

Option B: Copy files manually  
  Copy dist\dist_v1.0.7\* to test location
  Install service via windows_service\install_service.bat
```

### Step 2: Upload v1.0.7 Again (Self-Update Test)
1. Navigate to `http://localhost:8002/update`
2. Upload `dist\dist_v1.0.7\erp-cnc-adapter.exe`
3. Click "Upload & Update"

### Step 3: Watch for Success Indicators

**Immediate (< 5 seconds):**
- ✅ Message: "Update scheduled. The service will restart shortly..."
- ✅ Check logs: `logs\adapter.log` shows "spawned successfully via VBScript"

**Files Created:**
- ✅ `launch_update.vbs` - VBScript launcher
- ✅ `update_worker.py` - Update worker script
- ✅ `staged-update.exe` - Uploaded EXE

**During Update (5-30 seconds):**
- ✅ Check logs: `logs\update.log` should be created
- ✅ Service stops (connection manager logs stop)
- ✅ Python process visible in Task Manager briefly

**After Update (~30 seconds):**
- ✅ Service restarts (new logs in adapter.log)
- ✅ Version still shows 1.0.7 (no change expected - same version)
- ✅ Backup created: `erp-cnc-adapter.exe.bak.YYYYMMDD_HHMMSS`

### Step 4: Test Version Change (1.0.7 → 1.0.8)

If Step 3 works, build v1.0.8 and upload it to verify version actually changes.

## What to Look For

### Success Signs ✅
```
adapter.log:
  [INFO] src.handlers.update: Created VBScript launcher
  [INFO] src.handlers.update: Update worker spawned successfully via VBScript

update.log (NEW FILE!):
  INFO - Update worker started
  INFO - Stopping service 'ERPCNCAdapter'...
  INFO - Waiting for service to fully stop...
  INFO - Backing up current EXE
  INFO - Replacing EXE with staged update...
  INFO - Starting service 'ERPCNCAdapter'...
  INFO - Service started successfully. Update complete!

adapter.log (after restart):
  [INFO] root: Logging initialized
  [INFO] __main__: Starting ERP-CNC Adapter
```

### Failure Signs ❌
- No `launch_update.vbs` file created
- No `update.log` file created
- No Python process in Task Manager
- Service doesn't restart
- Version doesn't change

## Troubleshooting

### If VBScript Also Fails

Check if scripts are blocked:
```powershell
Get-ExecutionPolicy
# Should NOT be "Restricted"
```

Check if VBScript can run:
```powershell
# Test VBScript execution
echo 'WScript.Echo "Test"' > test.vbs
cscript.exe //nologo test.vbs
# Should output: Test
```

### Alternative Methods (Last Resort)

1. **PowerShell launcher** instead of VBScript
2. **Windows Task Scheduler** - schedule immediate one-time task
3. **Separate update service** - dedicated Windows service for updates
4. **Manual update mode** - require service stop before upload

## Current Build Status

Building v1.0.7 with:
- ✅ Dedicated `/update` page
- ✅ Fixed PyInstaller paths
- ✅ VBScript launcher for update worker
- ✅ Removed unnecessary delays
- ✅ 5-second service stop wait
- ✅ All 74 tests passing

## Summary

We've tried multiple approaches to spawn the update worker. VBScript is the most reliable Windows-native method for creating truly detached processes. This should finally work!

**Next**: Wait for v1.0.7 build to complete, then test the update mechanism.

