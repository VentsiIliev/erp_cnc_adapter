# Service Startup Troubleshooting Guide

## Problem: Service shows RUNNING but adapter not accessible on http://localhost:8002

### Symptoms
- Service status shows `STATE: 4 RUNNING`
- No response from `http://localhost:8002` or `http://localhost:8002/health`
- Logs show app started but may show immediate shutdown
- Restarting service fixes it temporarily

### Root Causes & Solutions

#### 1. ✅ FIXED: Console Mode Issue
**Problem:** EXE built with `console=False` causes process to hang when started by Windows service.

**Solution Applied:**
- Changed `erp-cnc-adapter.spec` from `console=False` to `console=True`
- Service startup uses `SW_HIDE` to hide the console window
- This allows proper I/O handling for uvicorn/FastAPI

**Verify Fix:**
```python
# In erp-cnc-adapter.spec
exe = EXE(
    ...
    console=True,  # Must be True for services
    ...
)
```

#### 2. ✅ FIXED: Stdout/Stderr Pipe Blocking
**Problem:** `subprocess.Popen` with `stdout=PIPE` and `stderr=PIPE` can cause process to hang if pipes aren't read.

**Solution Applied:**
- Removed `stdout=subprocess.PIPE` and `stderr=subprocess.PIPE` from service_exe.py
- App logs to its own file (`logs/adapter.log`) instead
- Service no longer needs to capture output

**Verify Fix:**
```python
# In windows_service/service_exe.py
self.process = subprocess.Popen(
    [EXE_PATH],
    cwd=PROJECT_ROOT,
    startupinfo=startupinfo,
    creationflags=subprocess.CREATE_NO_WINDOW
    # No stdout/stderr pipes!
)
```

---

## Diagnostic Steps

### 1. Check if service is actually running
```powershell
.\windows_service\service_status.bat
```

Expected output:
```
STATE: 4  RUNNING
```

### 2. Check adapter process
```powershell
Get-Process erp-cnc-adapter -ErrorAction SilentlyContinue
```

Should show PID and memory usage. If no output, process isn't running.

### 3. Check if port 8002 is listening
```powershell
netstat -ano | Select-String "8002"
```

Expected output:
```
TCP    0.0.0.0:8002           0.0.0.0:0              LISTENING       12345
```

If nothing shows, the adapter isn't listening.

### 4. Check service logs
```powershell
Get-Content logs\service.log -Tail 20
```

Look for:
- `Service starting`
- `Adapter started (PID: xxxxx)`
- `Process crashed with code: x` (indicates crash)

### 5. Check adapter logs
```powershell
Get-Content logs\adapter.log -Tail 20
```

Look for:
- `Starting ERP-CNC Adapter on 0.0.0.0:8002`
- `ConnectionManager background task started`
- Continuous heartbeat logs every 10 seconds

If you see:
```
INFO: Started server process [xxxxx]
INFO: Waiting for application startup.
INFO: Application startup complete.
INFO: Uvicorn running on http://0.0.0.0:8002
```
Then the server is running properly.

If logs stop abruptly after startup, the process crashed.

---

## Quick Fixes

### Fix 1: Restart Service
```powershell
.\windows_service\restart_service.bat
```
This kills the old process cleanly and starts fresh.

### Fix 2: Rebuild and Reinstall
If restart doesn't help, rebuild with fixes:

```powershell
# 1. Uninstall (as Admin)
.\windows_service\uninstall_service.bat

# 2. Rebuild
.\build.bat

# 3. Reinstall (as Admin)
cd dist\dist_v1.0.0\windows_service
.\install_service.bat
```

### Fix 3: Check for Port Conflicts
Another app might be using port 8002:

```powershell
# Check what's using port 8002
netstat -ano | Select-String "8002"
```

If something else is using it, either:
- Stop that application
- Change adapter port in `src\config.py`:
  ```python
  port: int = 8003  # Change to different port
  ```

### Fix 4: Manual Start for Testing
Test the EXE directly to see if it works outside the service:

```powershell
cd dist\dist_v1.0.0
.\erp-cnc-adapter.exe
```

Press Ctrl+C to stop. If this works but service doesn't, it's a service startup issue.

---

## Common Service Startup Issues

### Issue: "Process crashed with code: -1073741510"
**Meaning:** Missing DLL dependency

**Fix:**
1. Check if `cncapi.dll` exists at `C:\CNC4.03\cncapi.dll`
2. Check if all Python dependencies are installed
3. Try running EXE manually to see actual error

### Issue: "Process crashed with code: 1"
**Meaning:** Python exception during startup

**Fix:**
1. Check `logs\adapter.log` for full traceback
2. Likely configuration or import error
3. Test EXE manually

### Issue: Service starts then stops immediately
**Meaning:** Process exits before service detects it's running

**Fix:**
1. Check both service.log and adapter.log
2. Look for uncaught exceptions
3. Verify all paths in config.py

### Issue: Port already in use
**Meaning:** Another process is using port 8002

**Fix:**
```powershell
# Find the process using port 8002
netstat -ano | Select-String "8002"
# Kill it (if safe to do so)
Stop-Process -Id <PID> -Force
# Or change adapter port in config.py
```

---

## Testing After Fix

### 1. Test Local Access
```powershell
# Should return JSON with health status
curl http://localhost:8002/health

# Should show API documentation
Start-Process http://localhost:8002/docs
```

### 2. Test Network Access
From another machine on the network:
```bash
curl http://192.168.222.10:8002/health
```

### 3. Test Service Persistence
```powershell
# Stop and start service
net stop ERPCNCAdapter
net start ERPCNCAdapter

# Test immediately after start
curl http://localhost:8002/health
```

Should work on first try, not require multiple restarts.

### 4. Test After Reboot
```powershell
# Reboot machine
Restart-Computer

# After reboot, check service
sc query ERPCNCAdapter

# Should be RUNNING automatically
# Test adapter
curl http://localhost:8002/health
```

---

## Advanced Debugging

### Enable Debug Logging
Edit `src\config.py`:
```python
log_level: str = "DEBUG"  # Was "INFO"
```

Rebuild and reinstall. Logs will be much more verbose.

### Watch Logs Live
```powershell
# In one terminal
Get-Content -Wait logs\adapter.log

# In another terminal
Get-Content -Wait logs\service.log
```

### Manual Service Control
```powershell
# Install service
python windows_service\service_exe.py install

# Start service
python windows_service\service_exe.py start

# Stop service
python windows_service\service_exe.py stop

# Remove service
python windows_service\service_exe.py remove

# Debug mode (runs in console, not as service)
python windows_service\service_exe.py debug
```

The `debug` command is useful for seeing what the service is doing in real-time.

---

## Summary of Fixes Applied

| Issue | Fix | File Changed |
|-------|-----|--------------|
| Service hangs on startup | `console=False` → `console=True` | `erp-cnc-adapter.spec` |
| Process blocks on I/O | Removed `stdout/stderr` pipes | `windows_service/service_exe.py` |
| Not accessible from network | Added firewall rule | `windows_service/install_service.bat` |
| Service freezes after 2-3 min | Added timeout to `is_server_process_alive()` | `src/services/connection_manager.py` |

After applying these fixes, the service should:
- Start reliably on first install
- Not require service restart to work
- Be accessible immediately after start
- Continue running indefinitely
- Be accessible from other machines on network

