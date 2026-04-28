@echo off
setlocal EnableExtensions

echo ========================================
echo  ERP-CNC Adapter Installer
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

REM Change to project root (parent of scripts)
cd /d "%~dp0.."

REM Check if EXE exists - check both dev mode and distribution mode
if exist "erp-cnc-adapter.exe" (
    echo Found EXE in distribution mode
    set "EXE_PATH=%CD%\erp-cnc-adapter.exe"
    goto :exe_found
)

if exist "dist\erp-cnc-adapter.exe" (
    echo Found EXE in development mode
    set "EXE_PATH=%CD%\dist\erp-cnc-adapter.exe"
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

set "INSTALL_DIR=%CD%"

set "TASK_USER="
echo.
echo Task account configuration
echo ----------------------------------------
echo Leave this blank to run as SYSTEM.
echo If the CNC files are on a remote share, enter a Windows account
echo that has access to that share, for example DOMAIN\username.
echo.
set /p "TASK_USER=Run scheduled tasks as user: "
if "%TASK_USER%"=="" (
    echo Scheduled tasks will run as SYSTEM.
) else (
    echo Scheduled tasks will run as %TASK_USER%.
    echo Windows will ask for this account password when creating the tasks.
)

echo.
echo Step 1: Checking for existing installation...

REM Remove old pywin32-based service if exists
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    echo Stopping existing service...
    net stop ERPCNCAdapter >nul 2>&1
    echo Removing existing service...
    sc delete ERPCNCAdapter
    timeout /t 2 >nul
)

REM Remove old scheduled tasks if they exist
schtasks /Delete /TN "ERPCNCAdapter" /F >nul 2>&1
schtasks /Delete /TN "ERPCNCAdapterWatchdog" /F >nul 2>&1

echo.
echo Step 2: Creating startup task (with working directory)...

REM Write PowerShell script to temp file to avoid quoting issues with spaces in paths.
REM If TASK_USER is set, Register-ScheduledTask stores that credential so the task
REM can run at boot in the background and access remote SMB shares as that account.
set "PS_SCRIPT=%TEMP%\erp_cnc_install_task.ps1"
(
echo $ErrorActionPreference = 'Stop'
echo $exePath = $env:ERP_CNC_EXE_PATH
echo $installDir = $env:ERP_CNC_INSTALL_DIR
echo $taskUser = $env:ERP_CNC_TASK_USER
echo $watchdogPath = Join-Path $installDir 'scripts\watchdog.bat'
echo $action = New-ScheduledTaskAction -Execute $exePath -WorkingDirectory $installDir
echo $trigger = New-ScheduledTaskTrigger -AtStartup
echo $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -RestartCount 3 -RestartInterval ^(New-TimeSpan -Minutes 1^)
echo if ^([string]::IsNullOrWhiteSpace^($taskUser^)^) {
echo     $principal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
echo     Register-ScheduledTask -TaskName 'ERPCNCAdapter' -Action $action -Trigger $trigger -Principal $principal -Settings $settings -Force ^| Out-Null
echo } else {
echo     $credential = Get-Credential -UserName $taskUser -Message 'Enter the password for the ERP-CNC Adapter scheduled task account.'
echo     Register-ScheduledTask -TaskName 'ERPCNCAdapter' -Action $action -Trigger $trigger -Settings $settings -User $credential.UserName -Password $credential.GetNetworkCredential^(^).Password -RunLevel Highest -Force ^| Out-Null
echo }
echo if ^(Test-Path $watchdogPath^) {
echo     $watchdogAction = New-ScheduledTaskAction -Execute $watchdogPath -WorkingDirectory $installDir
echo     $watchdogTrigger = New-ScheduledTaskTrigger -Once -At ^(Get-Date^) -RepetitionInterval ^(New-TimeSpan -Minutes 2^) -RepetitionDuration ^(New-TimeSpan -Days 3650^)
echo     $watchdogSettings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
echo     if ^([string]::IsNullOrWhiteSpace^($taskUser^)^) {
echo         $watchdogPrincipal = New-ScheduledTaskPrincipal -UserId 'SYSTEM' -LogonType ServiceAccount -RunLevel Highest
echo         Register-ScheduledTask -TaskName 'ERPCNCAdapterWatchdog' -Action $watchdogAction -Trigger $watchdogTrigger -Principal $watchdogPrincipal -Settings $watchdogSettings -Force ^| Out-Null
echo     } else {
echo         Register-ScheduledTask -TaskName 'ERPCNCAdapterWatchdog' -Action $watchdogAction -Trigger $watchdogTrigger -Settings $watchdogSettings -User $credential.UserName -Password $credential.GetNetworkCredential^(^).Password -RunLevel Highest -Force ^| Out-Null
echo     }
echo }
) > "%PS_SCRIPT%"

set "ERP_CNC_EXE_PATH=%EXE_PATH%"
set "ERP_CNC_INSTALL_DIR=%INSTALL_DIR%"
set "ERP_CNC_TASK_USER=%TASK_USER%"
powershell -NoProfile -ExecutionPolicy Bypass -File "%PS_SCRIPT%"
set "PS_RESULT=%errorlevel%"
set "ERP_CNC_EXE_PATH="
set "ERP_CNC_INSTALL_DIR="
set "ERP_CNC_TASK_USER="
del /q "%PS_SCRIPT%" >nul 2>&1
if %PS_RESULT% neq 0 (
    echo ERROR: Failed to create scheduled tasks
    pause
    exit /b 1
)
echo   Startup task created successfully
if exist "%INSTALL_DIR%\scripts\watchdog.bat" (
    echo   Watchdog task created (checks every 2 minutes)
) else (
    echo   Watchdog script not found, skipping
)

echo.
echo Step 3: Configuring Windows Firewall...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
netsh advfirewall firewall add rule name="ERP-CNC Adapter" dir=in action=allow protocol=TCP localport=8002 enable=yes profile=any description="Allow incoming connections to ERP-CNC Adapter API"
if %errorlevel% equ 0 (
    echo   Firewall rule added successfully
) else (
    echo   WARNING: Failed to add firewall rule - manual configuration may be needed
)

echo.
echo Step 4: Starting application...
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
    if "%TASK_USER%"=="" (
        echo Run As:       SYSTEM
    ) else (
        echo Run As:       %TASK_USER%
    )
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
    echo To uninstall: Run scripts\uninstall.bat
) else (
    echo.
    echo Application configured but could not start immediately.
    echo It will start automatically on next boot.
)

echo.
pause
