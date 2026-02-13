# Testing Graceful Shutdown

## How to Test CNC Disconnect on Shutdown

### Method 1: Ctrl+C (Recommended)

1. Start the server:
   ```powershell
   .\.venv\Scripts\python.exe .\main.py
   ```

2. Wait for startup to complete (you should see):
   ```
   INFO: CNC client initialized and connected
   INFO: Uvicorn running on http://0.0.0.0:8002
   ```

3. Press **Ctrl+C** to stop the server

4. Verify you see the cleanup logs:
   ```
   Shutdown signal received, cleaning up...
   Shutting down CNC client...
   Disconnecting from CNC...
   CNC disconnected successfully
   CNC client shutdown complete
   Cleanup complete, exiting
   ```

### Method 2: Kill Process

1. Start the server in background:
   ```powershell
   Start-Process -FilePath ".\.venv\Scripts\python.exe" -ArgumentList ".\main.py"
   ```

2. Find the process ID:
   ```powershell
   Get-Process python | Where-Object {$_.Path -like "*erp_cnc_adapter*"}
   ```

3. Stop it gracefully:
   ```powershell
   Stop-Process -Id <PID> -Force
   ```

### Method 3: From Another Terminal

While server is running, in another PowerShell window:

```powershell
# Find the process
$process = Get-Process python | Where-Object {$_.MainWindowTitle -like "*python*"}

# Send Ctrl+C signal
$process | Stop-Process
```

## What Should Happen

**On Startup:**
```
INFO: Initializing CNC client...
INFO: CNC DLL loaded: C:\CNC4.03\cncapi.dll
INFO: Connecting to CNC...
INFO: CNC connected successfully
INFO: CNC client initialized and connected
INFO: Application startup complete
```

**On Shutdown:**
```
INFO: Shutdown signal received, cleaning up...
INFO: Shutting down CNC client...
INFO: Disconnecting from CNC...
INFO: CNC disconnected successfully
INFO: CNC client shutdown complete
INFO: Cleanup complete, exiting
```

## Troubleshooting

### "Disconnect logs not showing"
- Make sure log level is set to INFO or DEBUG in `src/config.py`
- Check if you're looking at the correct terminal window

### "CNC disconnect error"
- This is normal if the CNC server was already disconnected
- You should still see "CNC client shutdown complete"

### "Process hangs on shutdown"
- Wait 5-10 seconds for uvicorn to finish
- If it still hangs, use `Stop-Process -Force`

## Verification

After shutdown, verify the CNC server is no longer connected by checking the CNC software GUI - it should show "Disconnected" or similar status.

