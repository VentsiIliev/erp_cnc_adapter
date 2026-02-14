# ERP-CNC Adapter Windows Service

This folder contains the Windows service wrapper and installation scripts for running the ERP-CNC Adapter as a Windows service.

## Quick Start

### 1. Build the EXE

From the project root, run:
```batch
build.bat
```

This creates `dist/erp-cnc-adapter.exe`

### 2. Install the Service

Navigate to the `windows_service` folder and:
- Right-click `install_service.bat`
- Select **"Run as administrator"**

The service will be installed, configured for auto-start, and started immediately.

### 3. Access the Adapter

Open your browser to: **http://localhost:8000**

API Documentation: **http://localhost:8000/docs**

## Service Management

### Start/Stop/Restart

```batch
net start ERPCNCAdapter
net stop ERPCNCAdapter

# Or use the provided script:
restart_service.bat
```

### Check Status

```batch
# Quick status
sc query ERPCNCAdapter

# Detailed status with logs
service_status.bat
```

### View Logs

Service logs are written to: `logs/service.log`

```batch
# View last 20 lines
powershell Get-Content logs\service.log -Tail 20

# Monitor in real-time
powershell Get-Content logs\service.log -Wait
```

### Uninstall

- Right-click `uninstall_service.bat`
- Select **"Run as administrator"**

## Updating the Adapter

To update the adapter EXE to a new version:

```batch
python update_adapter.py path\to\new-erp-cnc-adapter.exe
```

This will:
1. Stop the service
2. Backup the current EXE
3. Replace with the new EXE
4. Restart the service
5. Verify the update succeeded
6. Rollback automatically if the update fails

### Example Update

```batch
python update_adapter.py C:\Downloads\erp-cnc-adapter-v2.0.exe
```

## Service Features

✅ **Auto-start on boot** - Service starts automatically when Windows starts
✅ **Runs in background** - No console window, completely hidden
✅ **Auto-restart on crash** - Configured to restart after 5s/10s/30s delays
✅ **Survives sleep/wake** - Service continues running through sleep cycles
✅ **Full logging** - All activity logged to `logs/service.log`
✅ **Easy updates** - Update script with automatic rollback
✅ **No Python required** - Target machines only need Python for service installation

## Distribution

To deploy to other machines, copy:

1. **Essential files:**
   - `dist/erp-cnc-adapter.exe` (the application)
   - `windows_service/` folder (all service files)

2. **On target machine:**
   - Ensure Python 3.8+ is installed (only needed for installation)
   - Run `windows_service/install_service.bat` as Administrator
   - Python is NOT needed to run the service, only to install it

## File Structure

```
windows_service/
├── service_exe.py              - Service wrapper (runs the EXE)
├── install_service.bat         - Install and start service
├── uninstall_service.bat       - Stop and remove service
├── update_adapter.py           - Update EXE with rollback
├── service_status.bat          - Check service status
├── restart_service.bat         - Quick restart
└── README.md                   - This file
```

## Troubleshooting

### Service won't start

1. Check if EXE exists: `dist/erp-cnc-adapter.exe`
2. View logs: `type logs\service.log`
3. Try starting EXE manually to see errors: `dist\erp-cnc-adapter.exe`

### Service crashes immediately

Check `logs/service.log` for error messages. Common issues:
- Port 8000 already in use
- Missing dependencies in the EXE build
- Configuration errors

### Update fails

The update script includes automatic rollback. If an update fails:
1. The service will automatically restart with the previous version
2. Check `logs/service.log` for error details
3. Backup files are saved in `dist/` with timestamps

## Advanced Configuration

### Change Service Settings

To modify service configuration:

```batch
# Change startup type
sc config ERPCNCAdapter start= manual    # Manual start
sc config ERPCNCAdapter start= auto      # Auto start (default)
sc config ERPCNCAdapter start= disabled  # Disabled

# Change recovery options
sc failure ERPCNCAdapter reset= 86400 actions= restart/5000/restart/10000/restart/30000
```

### Service Account

By default, the service runs as Local System. To run as a different user:

1. Open Services (`services.msc`)
2. Find "ERP-CNC Adapter Service"
3. Right-click → Properties → Log On tab
4. Select "This account" and enter credentials

## Support

For issues or questions:
1. Check `logs/service.log`
2. Run `service_status.bat` to see current state
3. Try manual EXE execution to isolate issues
4. Review Windows Event Viewer → Application logs

---

**Service installed and working?** Access your adapter at http://localhost:8000 🚀

