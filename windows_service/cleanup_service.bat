@echo off
REM Complete cleanup script for ERP-CNC Adapter service
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

echo Step 1: Stopping any running service...
net stop ERPCNCAdapter >nul 2>&1
sc stop ERPCNCAdapter >nul 2>&1
timeout /t 2 >nul

echo Step 2: Removing service registration...
sc delete ERPCNCAdapter 2>nul
timeout /t 1 >nul

echo Step 3: Killing any orphan processes...
taskkill /F /IM erp-cnc-adapter.exe /T 2>nul
taskkill /F /IM python.exe /FI "WINDOWTITLE eq *service_exe*" /T 2>nul

echo.
echo ========================================
echo  Cleanup Complete!
echo ========================================
echo.
echo All service processes have been terminated.
echo Service registration has been removed.
echo.
echo To reinstall:
echo   Right-click: windows_service\install_service.bat
echo   Select: "Run as administrator"
echo.
pause

