# Windows Service Installation Guide

## Overview

This guide explains how to install the ERP-CNC Adapter as a Windows service, allowing it to:

- **Start automatically** when Windows boots
- **Run in the background** without a visible window
- **Continue running** when the PC sleeps or wakes up
- **Automatically restart** if it crashes
- **Run without user login** (optional configuration)

## Prerequisites

1. **Python 3.8 or higher** (32-bit if using CNC API)
2. **Administrator privileges** to install Windows services
3. All project dependencies installed

## Quick Installation

### Step 1: Install Dependencies

Open PowerShell as **Administrator** in the project directory and run:

```powershell
pip install -r requirements.txt
```

This will install:
- `fastapi` - Web framework
- `uvicorn` - ASGI server
- `pywin32` - Windows service support

### Step 2: Install the Service

Run the installation script:

```powershell
.\install_service.ps1
```

This script will:
1. Install all required dependencies
2. Register the Windows service
3. Configure auto-start on boot
4. Configure automatic restart on failure
5. Start the service immediately

### Step 3: Verify Installation

Check the service status:

```powershell
.\service_status.ps1
```

Or use Windows commands:

```powershell
Get-Service ERPCNCAdapter
```

Access the web interface at: **http://localhost:8000**

## Manual Installation

If you prefer manual installation:

### 1. Install Service

```powershell
python service.py install
```

### 2. Configure Auto-Start

```powershell
sc.exe config ERPCNCAdapter start= auto
```

### 3. Configure Auto-Recovery

```powershell
sc.exe failure ERPCNCAdapter reset= 86400 actions= restart/5000/restart/10000/restart/30000
```

This configures the service to restart:
- After 5 seconds on first failure
- After 10 seconds on second failure  
- After 30 seconds on subsequent failures
- Reset failure count after 24 hours (86400 seconds)

### 4. Start Service

```powershell
python service.py start
```

Or:

```powershell
net start ERPCNCAdapter
```

## Service Management

### Check Status

```powershell
# Using PowerShell script
.\service_status.ps1

# Or using Windows commands
Get-Service ERPCNCAdapter
sc.exe query ERPCNCAdapter
```

### Start Service

```powershell
# Using Python script
python service.py start

# Or using Windows commands
net start ERPCNCAdapter
Start-Service ERPCNCAdapter
```

### Stop Service

```powershell
# Using Python script
python service.py stop

# Or using Windows commands
net stop ERPCNCAdapter
Stop-Service ERPCNCAdapter
```

### Restart Service

```powershell
# Using Windows commands
net stop ERPCNCAdapter
net start ERPCNCAdapter

# Or using PowerShell
Restart-Service ERPCNCAdapter
```

### Uninstall Service

```powershell
# Using PowerShell script
.\uninstall_service.ps1

# Or manually
python service.py stop
python service.py remove
```

## Service Configuration

### Service Properties

- **Name:** `ERPCNCAdapter`
- **Display Name:** `ERP-CNC Adapter Service`
- **Startup Type:** Automatic
- **Recovery:** Auto-restart on failure
- **Log Level:** Configured via environment variables (see below)

### Environment Variables

You can configure the service using environment variables. Set them system-wide:

```powershell
# Set system environment variables (requires Admin)
[System.Environment]::SetEnvironmentVariable('CNC_HOST', '0.0.0.0', 'Machine')
[System.Environment]::SetEnvironmentVariable('CNC_PORT', '8000', 'Machine')
[System.Environment]::SetEnvironmentVariable('LOG_LEVEL', 'INFO', 'Machine')
```

After changing environment variables, restart the service:

```powershell
net stop ERPCNCAdapter
net start ERPCNCAdapter
```

### Application Settings

The service reads configuration from `src/config.py`. Default settings:

```python
HOST = "0.0.0.0"  # Listen on all interfaces
PORT = 8000        # Default HTTP port
LOG_LEVEL = "INFO" # Logging verbosity
```

## Logs and Monitoring

### Service Logs

Service logs are written to: `logs/service.log`

View recent logs:

```powershell
# Last 20 lines
Get-Content logs\service.log -Tail 20

# Monitor in real-time
Get-Content logs\service.log -Wait
```

### Windows Event Viewer

The service also logs to Windows Event Viewer:

1. Open Event Viewer (`eventvwr.msc`)
2. Navigate to: **Windows Logs** > **Application**
3. Filter by source: **ERPCNCAdapter**

### Application Logs

Application logs are controlled by `src/logging_config.py` and may write to additional locations.

## Troubleshooting

### Service Won't Start

**Check logs:**
```powershell
Get-Content logs\service.log -Tail 50
```

**Common issues:**

1. **Port already in use:**
   - Another service is using port 8000
   - Solution: Change port in config or stop conflicting service

2. **Missing dependencies:**
   - Run: `pip install -r requirements.txt`

3. **Permission issues:**
   - Ensure you ran installation as Administrator

**Verify installation:**
```powershell
sc.exe qc ERPCNCAdapter
```

### Service Crashes on Startup

1. Check `logs\service.log` for Python errors
2. Test the application manually:
   ```powershell
   python main.py
   ```
3. If manual start works, reinstall service:
   ```powershell
   .\uninstall_service.ps1
   .\install_service.ps1
   ```

### CNC Connection Issues

1. Verify CNC software is running
2. Check connection settings in config
3. Review logs for connection errors:
   ```powershell
   Get-Content logs\service.log | Select-String "error" -CaseSensitive:$false
   ```

### Service Won't Stop

If the service hangs during shutdown:

```powershell
# Force stop
Stop-Service ERPCNCAdapter -Force

# If still running, kill process
Get-Process python | Where-Object {$_.Path -like "*erp_cnc_adapter*"} | Stop-Process -Force
```

### High CPU/Memory Usage

Monitor resource usage:

```powershell
Get-Process | Where-Object {$_.ProcessName -eq "python"} | Select-Object ProcessName, CPU, WS
```

Check logs for errors or excessive connection retries.

## Sleep/Wake Behavior

### How It Works

The Windows service handles power events:

- **Sleep:** Service continues running, maintains state
- **Wake:** Service automatically resumes operations
- **CNC Connection:** Automatically reconnects if lost during sleep

### Testing Sleep/Wake

1. Verify service is running:
   ```powershell
   Get-Service ERPCNCAdapter
   ```

2. Put PC to sleep (Windows + X > Sleep)

3. Wake the PC

4. Verify service is still running:
   ```powershell
   .\service_status.ps1
   ```

5. Check for connection events in logs:
   ```powershell
   Get-Content logs\service.log -Tail 20
   ```

### Known Limitations

- **Network connections:** May drop during sleep, but will auto-reconnect
- **CNC API:** Some CNC systems may disconnect during sleep; service will retry
- **Long sleep duration:** After extended sleep (>24h), service may need manual restart

## Advanced Configuration

### Run as Specific User

By default, services run as Local System. To run as a specific user:

1. Open Services (`services.msc`)
2. Right-click **ERP-CNC Adapter Service** > Properties
3. Go to **Log On** tab
4. Select **This account** and enter credentials
5. Click **Apply**, then restart the service

**Note:** User account must have "Log on as a service" permission.

### Network Access Configuration

To access from other machines on the network:

1. Ensure `HOST = "0.0.0.0"` in config (default)
2. Configure Windows Firewall:

```powershell
New-NetFirewallRule -DisplayName "ERP-CNC Adapter" -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow
```

3. Restart service:
```powershell
Restart-Service ERPCNCAdapter
```

### Change Port

Edit `src/config.py` or set environment variable:

```powershell
[System.Environment]::SetEnvironmentVariable('CNC_PORT', '9000', 'Machine')
Restart-Service ERPCNCAdapter
```

### Enable Debug Logging

For troubleshooting:

```powershell
[System.Environment]::SetEnvironmentVariable('LOG_LEVEL', 'DEBUG', 'Machine')
Restart-Service ERPCNCAdapter
```

**Warning:** Debug logging generates large log files.

## Security Considerations

### Network Security

- Service listens on all interfaces (0.0.0.0) by default
- Use firewall rules to restrict access
- Consider using HTTPS in production (requires additional configuration)

### Access Control

- Service runs with elevated privileges
- Restrict physical access to the machine
- Use strong authentication if implementing user accounts

### Updates and Patches

Keep dependencies updated:

```powershell
pip install --upgrade pip
pip install --upgrade -r requirements.txt
```

After updating, restart the service:

```powershell
Restart-Service ERPCNCAdapter
```

## Backup and Recovery

### Backup Configuration

Important files to backup:

- `src/config.py` - Application configuration
- `service.py` - Service wrapper
- Environment variables (export via PowerShell)

### Disaster Recovery

To restore service on new machine:

1. Install Python (same version and architecture)
2. Copy project directory
3. Install dependencies: `pip install -r requirements.txt`
4. Run: `.\install_service.ps1`
5. Restore configuration files
6. Restart service

## Performance Tuning

### Optimize for Production

1. **Set appropriate log level:**
   ```powershell
   [System.Environment]::SetEnvironmentVariable('LOG_LEVEL', 'WARNING', 'Machine')
   ```

2. **Limit log file size:** Configure log rotation in `src/logging_config.py`

3. **Monitor resource usage:** Use Task Manager or Performance Monitor

### Scaling Considerations

- Single instance handles multiple concurrent API requests
- FastAPI uses async/await for efficient I/O
- For high load, consider load balancer with multiple instances on different ports

## Getting Help

### Check Documentation

- API Documentation: http://localhost:8000/docs
- Project README: `README.md`
- API Specifications: `docs/ERP_CNC_Adapter_API_Documentation.md`

### Debug Checklist

- [ ] Service is installed and running
- [ ] Logs show no errors
- [ ] Port is not blocked by firewall
- [ ] CNC software is running
- [ ] Network connectivity is working
- [ ] Configuration is correct

### Log Collection

For support requests, collect:

```powershell
# Create support bundle
$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$bundleName = "erp_cnc_support_$timestamp"

New-Item -ItemType Directory -Path $bundleName
Copy-Item logs\service.log "$bundleName\"
sc.exe qc ERPCNCAdapter > "$bundleName\service_config.txt"
Get-Service ERPCNCAdapter | Format-List * > "$bundleName\service_status.txt"
python --version > "$bundleName\python_version.txt"
pip freeze > "$bundleName\installed_packages.txt"

Compress-Archive -Path $bundleName -DestinationPath "$bundleName.zip"
Write-Host "Support bundle created: $bundleName.zip"
```

---

## Quick Reference

### Common Commands

```powershell
# Install service
.\install_service.ps1

# Check status
.\service_status.ps1

# Start service
net start ERPCNCAdapter

# Stop service
net stop ERPCNCAdapter

# Restart service
Restart-Service ERPCNCAdapter

# View logs
Get-Content logs\service.log -Tail 20 -Wait

# Uninstall service
.\uninstall_service.ps1
```

### Important Paths

- **Service script:** `service.py`
- **Service logs:** `logs/service.log`
- **Main application:** `main.py`
- **Configuration:** `src/config.py`
- **API docs:** http://localhost:8000/docs

### Service Information

- **Service Name:** ERPCNCAdapter
- **Display Name:** ERP-CNC Adapter Service
- **Default Port:** 8000
- **Log Level:** INFO
- **Startup:** Automatic
- **Recovery:** Auto-restart on failure

