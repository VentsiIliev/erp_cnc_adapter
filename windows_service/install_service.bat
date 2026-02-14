@echo off
echo ========================================
echo  ERP-CNC Adapter Service Installer
echo ========================================
echo.

REM Check admin privileges
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This installer must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

REM Change to project root (parent of windows_service)
cd /d "%~dp0.."

REM Check if EXE exists - check both dev mode and distribution mode
if exist "erp-cnc-adapter.exe" (
    echo Found EXE in distribution mode
    set EXE_PATH=%CD%\erp-cnc-adapter.exe
    goto :exe_found
)

if exist "dist\erp-cnc-adapter.exe" (
    echo Found EXE in development mode
    set EXE_PATH=%CD%\dist\erp-cnc-adapter.exe
    goto :exe_found
)

echo ERROR: erp-cnc-adapter.exe not found!
echo.
echo Expected locations:
echo   Distribution mode: erp-cnc-adapter.exe (current folder)
echo   Development mode:  dist\erp-cnc-adapter.exe
echo.
echo Please build the EXE first by running: build.bat
pause
exit /b 1

:exe_found
echo.
echo EXE: %EXE_PATH%

echo.
echo Step 1: Checking for existing service/task...

REM Remove old pywin32-based service if exists
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    echo Stopping existing service...
    net stop ERPCNCAdapter >nul 2>&1
    echo Removing existing service...
    sc delete ERPCNCAdapter
    timeout /t 2 >nul
)

REM Remove old scheduled task if exists
schtasks /Delete /TN "ERPCNCAdapter" /F >nul 2>&1

echo.
echo Step 2: Creating startup task (with working directory)...

set INSTALL_DIR=%CD%
powershell -NoProfile -Command "$action = New-ScheduledTaskAction -Execute '\"%EXE_PATH%\"' -WorkingDirectory '\"%INSTALL_DIR%\"'; $trigger = New-ScheduledTaskTrigger -AtStartup; $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest; $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1); Register-ScheduledTask -TaskName 'ERPCNCAdapter' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force"
if %errorlevel% neq 0 (
    echo ERROR: Failed to create startup task
    pause
    exit /b 1
)
echo   Startup task created successfully

echo.
echo Step 3: Creating watchdog task...

if exist "windows_service\watchdog.bat" (
    schtasks /Delete /TN "ERPCNCAdapterWatchdog" /F >nul 2>&1
    schtasks /Create /TN "ERPCNCAdapterWatchdog" /TR "\"%CD%\windows_service\watchdog.bat\"" /SC MINUTE /MO 2 /RU SYSTEM /RL HIGHEST /F
    if %errorlevel% equ 0 (
        echo   Watchdog task created (checks every 2 minutes)
    ) else (
        echo   WARNING: Watchdog task creation failed (non-critical)
    )
) else (
    echo   Watchdog script not found, skipping
)

echo.
echo Step 4: Configuring Windows Firewall...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
netsh advfirewall firewall add rule name="ERP-CNC Adapter" dir=in action=allow protocol=TCP localport=8002 enable=yes profile=any description="Allow incoming connections to ERP-CNC Adapter API"
if %errorlevel% equ 0 (
    echo   Firewall rule added successfully
) else (
    echo   WARNING: Failed to add firewall rule - manual configuration may be needed
)

echo.
echo Step 5: Starting application...
start "" /D "%INSTALL_DIR%" "%EXE_PATH%"
timeout /t 3 >nul
tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" 2>nul | find /I "erp-cnc-adapter.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  SUCCESS! Application installed and running
    echo ========================================
    echo.
    echo Task Name:    ERPCNCAdapter
    echo Status:       Running
    echo Startup:      Automatic (on boot)
    echo.
    echo Access the adapter at: http://localhost:8002
    echo API Documentation:     http://localhost:8002/docs
    echo.
    echo Application logs: logs\adapter.log
    echo.
    echo Management:
    echo   Start:   schtasks /Run /TN "ERPCNCAdapter"
    echo   Stop:    taskkill /F /IM erp-cnc-adapter.exe
    echo   Status:  tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe"
    echo.
    echo To uninstall: Run windows_service\uninstall_service.bat
) else (
    echo.
    echo Application configured but could not start immediately.
    echo It will start automatically on next boot.
)

echo.
pause
