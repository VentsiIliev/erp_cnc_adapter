@echo off
REM Complete cleanup script for ERP-CNC Adapter
echo ========================================
echo  ERP-CNC Adapter - Complete Cleanup
echo ========================================
echo.

REM Check admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This script must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

echo Step 1: Removing scheduled tasks...
schtasks /End /TN ERPCNCAdapter >nul 2>&1
schtasks /Delete /TN ERPCNCAdapter /F >nul 2>&1
schtasks /End /TN ERPCNCAdapterWatchdog >nul 2>&1
schtasks /Delete /TN ERPCNCAdapterWatchdog /F >nul 2>&1

echo Step 2: Removing old service registration (if any)...
net stop ERPCNCAdapter >nul 2>&1
sc delete ERPCNCAdapter >nul 2>&1
timeout /t 1 >nul

echo Step 3: Killing any running processes...
taskkill /F /IM erp-cnc-adapter.exe /T >nul 2>&1

echo Step 4: Removing firewall rule...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1

echo.
echo ========================================
echo  Cleanup Complete!
echo ========================================
echo.
echo All processes, tasks, and rules have been removed.
echo.
echo To reinstall:
echo   Right-click: scripts\install.bat
echo   Select: "Run as administrator"
echo.
pause
