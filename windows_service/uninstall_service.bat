@echo off
echo ========================================
echo  ERP-CNC Adapter Service Uninstaller
echo ========================================
echo.

REM Check admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This uninstaller must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

REM Change to project root
cd /d "%~dp0.."

REM Check if service exists
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% neq 0 (
    echo Service is not installed.
    pause
    exit /b 0
)

echo Step 1: Stopping service...
sc query ERPCNCAdapter | find "RUNNING" >nul 2>&1
if %errorlevel% equ 0 (
    echo Service is running, stopping...
    python windows_service\service_exe.py stop 2>nul
    net stop ERPCNCAdapter >nul 2>&1
    timeout /t 2 >nul
) else (
    echo Service is already stopped
)

echo.
echo Step 2: Removing service...
python windows_service\service_exe.py remove 2>nul
set REMOVE_RESULT=%errorlevel%
sc delete ERPCNCAdapter >nul 2>&1

echo.
echo Step 3: Cleaning up any orphan processes...
taskkill /F /IM erp-cnc-adapter.exe /T 2>nul
REM Don't wait - taskkill is instant if process exists

echo.
echo Step 4: Removing firewall rule...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
if %errorlevel% equ 0 (
    echo Firewall rule removed
) else (
    echo No firewall rule found
)

echo.
echo ========================================
if %REMOVE_RESULT% equ 0 (
    echo  SUCCESS! Service uninstalled
    echo ========================================
    echo.
    echo The ERP-CNC Adapter service has been removed.
) else (
    echo  WARNING: Service may not have been fully removed
    echo ========================================
    echo.
    echo The service registration has been cleared.
)
echo.
echo To reinstall: Run windows_service\install_service.bat

echo.
pause

