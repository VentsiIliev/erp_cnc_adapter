# ERP-CNC Adapter

## Installation Complete!

The ERP-CNC Adapter has been installed and configured as a Windows service.

### Service Information

- **Service Name:** ERPCNCAdapter
- **Display Name:** ERP-CNC Adapter Service
- **Status:** Running (should start automatically)
- **Startup Type:** Automatic (starts on boot)

### Access the Application

- **Web Interface:** http://localhost:8002
- **API Documentation:** http://localhost:8002/docs
- **Health Check:** http://localhost:8002/api/health

### Service Management

**Start Service:**
```
net start ERPCNCAdapter
```

**Stop Service:**
```
net stop ERPCNCAdapter
```

**Restart Service:**
```
net stop ERPCNCAdapter & net start ERPCNCAdapter
```

**Check Status:**
```
sc query ERPCNCAdapter
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

### Configuration

Edit configuration settings in the installation directory if needed.

### Support

For issues or questions, contact your system administrator.

---

**Installation Directory:** Check Start Menu or Program Files
**Service Runs:** Automatically on Windows startup
**Log Files:** Installation directory\logs\adapter.log

