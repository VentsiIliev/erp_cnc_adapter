@echo off
echo ========================================
echo  ERP-CNC Adapter Uninstaller
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

set FOUND_SOMETHING=0

REM ── Step 1: Stop and remove Windows Service (if exists) ──────────────
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    set FOUND_SOMETHING=1
    echo Step 1a: Stopping Windows Service...
    sc query ERPCNCAdapter | find "RUNNING" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Service is running, stopping...
        net stop ERPCNCAdapter >nul 2>&1
        timeout /t 3 >nul
    ) else (
        echo   Service is already stopped
    )

    echo   Removing service registration...
    sc delete ERPCNCAdapter >nul 2>&1
    echo   Done.
) else (
    echo Step 1a: No Windows Service found (skipped)
)

echo.

REM ── Step 1b: Stop and remove Scheduled Tasks (if exist) ──────────────
schtasks /Query /TN ERPCNCAdapterWatchdog >nul 2>&1
if %errorlevel% equ 0 (
    set FOUND_SOMETHING=1
    echo Step 1b: Removing Watchdog Task...
    schtasks /End /TN ERPCNCAdapterWatchdog >nul 2>&1
    schtasks /Delete /TN ERPCNCAdapterWatchdog /F >nul 2>&1
    echo   Watchdog task removed
)

schtasks /Query /TN ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    set FOUND_SOMETHING=1
    echo   Removing Startup Task...
    schtasks /End /TN ERPCNCAdapter >nul 2>&1
    timeout /t 2 >nul
    schtasks /Delete /TN ERPCNCAdapter /F >nul 2>&1
    if %errorlevel% equ 0 (
        echo   Startup task removed
    ) else (
        echo   WARNING: Could not remove scheduled task
    )
) else (
    echo Step 1b: No Scheduled Tasks found (skipped)
)

echo.

REM ── Step 2: Kill any running process ─────────────────────────────────
echo Step 2: Stopping erp-cnc-adapter.exe process...
tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" 2>nul | find /I "erp-cnc-adapter.exe" >nul 2>&1
if %errorlevel% equ 0 (
    set FOUND_SOMETHING=1
    echo   Process is running, killing...
    taskkill /F /IM erp-cnc-adapter.exe /T >nul 2>&1
    timeout /t 2 >nul
    REM Verify it's actually dead
    tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" 2>nul | find /I "erp-cnc-adapter.exe" >nul 2>&1
    if %errorlevel% equ 0 (
        echo   WARNING: Process still running, retrying...
        timeout /t 3 >nul
        taskkill /F /IM erp-cnc-adapter.exe /T >nul 2>&1
    )
    echo   Done.
) else (
    echo   Process is not running
)

echo.

REM ── Step 3: Remove firewall rule ─────────────────────────────────────
echo Step 3: Removing firewall rule...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
if %errorlevel% equ 0 (
    echo   Firewall rule removed
) else (
    echo   No firewall rule found
)

echo.
echo ========================================
if %FOUND_SOMETHING% equ 1 (
    echo  SUCCESS! ERP-CNC Adapter uninstalled
    echo ========================================
    echo.
    echo The adapter has been fully stopped and removed.
) else (
    echo  Nothing to uninstall
    echo ========================================
    echo.
    echo No service, scheduled task, or running process was found.
)
echo.
echo To reinstall: Run windows_service\install_service.bat
echo.
pause
