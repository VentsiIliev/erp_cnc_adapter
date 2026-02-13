# Service Cleanup & Reinstallation Guide

## Issue: Service Uninstalled but Process Still Running

After uninstalling the service, you may see the process still running in Task Manager. This happens because:

1. **Service registration removed** - Windows no longer manages it
2. **Process still running** - The EXE continues in background
3. **Orphan process** - No longer controlled by service manager

---

## ✅ Solution: Complete Cleanup

### Option 1: Use Cleanup Script (Recommended)

From the `windows_service` folder, run as **Administrator**:
```batch
cleanup_service.bat
```

This will:
- Stop any running service
- Remove service registration
- Kill all orphan processes
- Prepare for clean reinstall

### Option 2: Manual Cleanup

Run these commands as **Administrator**:

```powershell
# Stop service
net stop ERPCNCAdapter

# Remove service registration
sc delete ERPCNCAdapter

# Kill orphan processes
taskkill /F /IM erp-cnc-adapter.exe

# Verify cleanup
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" }
```

---

## 🔄 Reinstalling the Service

After cleanup, reinstall:

### Step 1: Navigate to Distribution
```powershell
cd dist\dist_v1.0.0
```

### Step 2: Install Service
Right-click: `windows_service\install_service.bat`
Select: **"Run as administrator"**

### Step 3: Verify Installation
```powershell
sc query ERPCNCAdapter
```

Should show: **STATE: RUNNING**

### Step 4: Test
Open: http://localhost:8000

---

## 🔍 Checking for Orphan Processes

### In Task Manager
1. Open Task Manager (Ctrl+Shift+Esc)
2. Go to "Details" tab
3. Look for: `erp-cnc-adapter.exe` or `python.exe`
4. If found, right-click → End Task

### In PowerShell
```powershell
# Check for ERP-CNC processes
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" }

# Kill if found
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" } | Stop-Process -Force

# Verify
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" }
```

---

## 🛠️ Updated Uninstall Script

The `uninstall_service.bat` has been updated to:
1. Stop the service gracefully
2. Remove service registration
3. **Kill any orphan processes** ✓ NEW
4. Clean up completely

Now when you uninstall, it will automatically clean everything.

---

## 📋 Troubleshooting Checklist

**Problem: Service shows "NOT INSTALLED" but process runs**

- [ ] Check Task Manager for `erp-cnc-adapter.exe`
- [ ] Run `cleanup_service.bat` as admin
- [ ] Verify no processes: `Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" }`
- [ ] Reinstall service

**Problem: Can't reinstall - "service already exists"**

- [ ] Run: `sc delete ERPCNCAdapter` as admin
- [ ] Wait 10 seconds
- [ ] Try install again

**Problem: Port 8000 already in use**

- [ ] Kill orphan process: `taskkill /F /IM erp-cnc-adapter.exe`
- [ ] Or restart computer
- [ ] Then reinstall

**Problem: Service won't start after reinstall**

- [ ] Check logs: `type logs\service.log`
- [ ] Verify EXE exists: `dir erp-cnc-adapter.exe`
- [ ] Try manual EXE: `.\erp-cnc-adapter.exe` (to see errors)
- [ ] Reinstall with clean slate

---

## 🎯 Clean Reinstall Procedure

For a completely fresh start:

### Step 1: Complete Cleanup
```powershell
# As Administrator
cd windows_service
.\cleanup_service.bat
```

### Step 2: Verify Clean State
```powershell
# No service
sc query ERPCNCAdapter
# Should say: "The specified service does not exist"

# No processes
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" }
# Should return nothing
```

### Step 3: Reinstall
```powershell
cd ..\dist\dist_v1.0.0
# Right-click windows_service\install_service.bat
# Select "Run as administrator"
```

### Step 4: Verify Success
```powershell
# Service running
sc query ERPCNCAdapter
# Should show: STATE: RUNNING

# Test API
curl http://localhost:8000/api/health
# or open in browser
```

---

## 📝 Prevention Tips

To avoid orphan processes in the future:

1. **Always use the uninstall script** (now improved)
2. **Wait 5 seconds** after stopping before restarting
3. **Check Task Manager** before reinstalling
4. **Use cleanup script** if you see issues

---

## 🆘 Emergency Cleanup

If nothing works:

```powershell
# Nuclear option - kill everything
Get-Process | Where-Object { $_.ProcessName -like "*erp-cnc*" -or $_.ProcessName -eq "python" } | Stop-Process -Force

# Remove service
sc delete ERPCNCAdapter

# Reboot (cleanest solution)
Restart-Computer
```

After reboot, reinstall normally.

---

## ✅ Files Updated

- **`cleanup_service.bat`** - NEW cleanup script
- **`uninstall_service.bat`** - Now kills orphan processes
- This guide - Complete troubleshooting reference

---

## 📞 Quick Commands

```powershell
# Clean everything
.\windows_service\cleanup_service.bat  # as admin

# Install fresh
.\windows_service\install_service.bat  # as admin

# Check status
sc query ERPCNCAdapter

# View logs
Get-Content logs\service.log -Tail 20
```

---

**Your service cleanup is complete and ready for reinstallation!**

