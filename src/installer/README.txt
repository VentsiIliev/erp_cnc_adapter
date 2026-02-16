# ERP-CNC Adapter

## Installation Complete!

The ERP-CNC Adapter has been installed and configured to run via Windows Task Scheduler.

### Task Information

- **Task Name:** ERPCNCAdapter
- **Status:** Running (starts automatically on boot)
- **Trigger:** At system startup

### Access the Application

- **Web Interface:** http://localhost:8002
- **API Documentation:** http://localhost:8002/docs
- **Health Check:** http://localhost:8002/api/health

### Management

**Check Status:**
```
schtasks /Query /TN ERPCNCAdapter
```

**Start:**
```
schtasks /Run /TN ERPCNCAdapter
```

**Stop:**
```
taskkill /F /IM erp-cnc-adapter.exe
```

**Restart:**
```
taskkill /F /IM erp-cnc-adapter.exe & schtasks /Run /TN ERPCNCAdapter
```

### View Logs

Logs are stored in the `logs` folder within the installation directory.

To view recent logs:
```
Get-Content logs\adapter.log -Tail 20
```

To monitor logs in real-time:
```
Get-Content logs\adapter.log -Wait
```

### Support

For issues or questions, contact your system administrator.

---

**Installation Directory:** Check Program Files
**Runs:** Automatically on Windows startup via Task Scheduler
**Log Files:** Installation directory\logs\adapter.log
