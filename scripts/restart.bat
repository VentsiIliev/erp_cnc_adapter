@echo off
setlocal EnableDelayedExpansion
for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
set "LOG_DIR=!INSTALL_DIR!\logs"
set "LOG_FILE=!LOG_DIR!\start-cnc.log"
if not exist "!LOG_DIR!" mkdir "!LOG_DIR!" >nul 2>&1

if not "%ERPCNC_MANUAL_TASK%"=="1" (
    schtasks /Run /TN ERPCNCAdapterManualStart >nul 2>&1
    if not errorlevel 1 (
        exit /b 0
    )
    echo [%date% %time%] ERROR: Could not start elevated manual START-CNC task. Reinstall the adapter or run START-CNC as administrator once. > "!LOG_FILE!"
    exit /b 1
)

echo [%date% %time%] Restarting ERP-CNC Adapter... > "!LOG_FILE!"
call :log "Restart context: install_dir=!INSTALL_DIR! manual_task=%ERPCNC_MANUAL_TASK% username=%USERNAME% computer=%COMPUTERNAME%"
call :log "Restart context: PATH=%PATH%"

if not "%ERPCNC_SHOW_SPLASH%"=="0" (
    if exist "!INSTALL_DIR!\scripts\start_cnc_splash.ps1" (
        call :log "Starting START-CNC splash screen..."
        start "" powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "!INSTALL_DIR!\scripts\start_cnc_splash.ps1"
    ) else (
        call :log "START-CNC splash script missing; continuing without splash."
    )
)

call :log "Stopping adapter, Eding CNC GUI, and CNC Server..."
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "'erp-cnc-adapter','cnc4.03','cnc','CncServer' | ForEach-Object { $name = $_; $procs = Get-Process -Name $name -ErrorAction SilentlyContinue; if ($procs) { $procs | ForEach-Object { Write-Output ('Stopping {0} pid={1}' -f $_.ProcessName,$_.Id) }; $procs | Stop-Process -Force -ErrorAction SilentlyContinue } else { Write-Output ('Not running: {0}' -f $name) } }" >> "!LOG_FILE!" 2>&1
set "STOP_EXIT=!errorlevel!"
call :log "Stop-Process command exit code: !STOP_EXIT!"

call :log "Remaining target processes after stop request:"
powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "'erp-cnc-adapter','cnc4.03','cnc','CncServer' | ForEach-Object { Get-Process -Name $_ -ErrorAction SilentlyContinue | ForEach-Object { '{0} pid={1} responding={2}' -f $_.ProcessName,$_.Id,$_.Responding } }" >> "!LOG_FILE!" 2>&1

call :log "Waiting 2 seconds before reading configuration..."
timeout /t 2 >nul
set "AUTO_GUI=0"
call :log "Reading auto_start_eding_gui from !INSTALL_DIR!\config.json"
for /f "usebackq delims=" %%G in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p='!INSTALL_DIR!\config.json'; if (Test-Path -LiteralPath $p) { try { $c = Get-Content -LiteralPath $p -Raw | ConvertFrom-Json; if ($c.auto_start_eding_gui) { '1' } else { '0' } } catch { '0' } } else { '0' }"`) do set "AUTO_GUI=%%G"
call :log "Configuration decision: AUTO_GUI=!AUTO_GUI!"

if "!AUTO_GUI!"=="1" (
    call :log "Auto GUI is enabled; starting Eding GUI before adapter..."
    powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "!INSTALL_DIR!\scripts\start_eding_handoff.ps1" >> "!LOG_FILE!" 2>&1
    set "GUI_EXIT=!errorlevel!"
    call :log "Eding GUI handoff exit code: !GUI_EXIT!"
    if not "!GUI_EXIT!"=="0" (
        call :log "ERROR: Eding GUI startup failed."
        exit /b 1
    )
    call :log "Waiting 15 seconds for Eding GUI startup..."
    timeout /t 15 >nul
) else (
    call :log "Deferring Eding GUI launch until adapter readiness is confirmed..."
    echo 1 > "!INSTALL_DIR!\manual_start_defer_gui.flag"
    call :log "Wrote manual_start_defer_gui.flag"
)

call :log "Starting adapter via scheduled task ERPCNCAdapter..."
schtasks /Run /TN ERPCNCAdapter >> "!LOG_FILE!" 2>&1
set "TASK_EXIT=!errorlevel!"
call :log "schtasks /Run ERPCNCAdapter exit code: !TASK_EXIT!"
if not "!TASK_EXIT!"=="0" (
    set "ADAPTER_EXE=!INSTALL_DIR!\erp-cnc-adapter.exe"
    set "HIDDEN_LAUNCHER=!INSTALL_DIR!\scripts\launch_adapter_hidden.vbs"
    if exist "!HIDDEN_LAUNCHER!" (
        call :log "Scheduled task is disabled or unavailable; starting adapter through hidden launcher..."
        wscript.exe //B //Nologo "!HIDDEN_LAUNCHER!" >> "!LOG_FILE!" 2>&1
        call :log "Hidden launcher exit code: !errorlevel!"
    ) else if exist "!ADAPTER_EXE!" (
        call :log "Scheduled task is disabled or unavailable; starting adapter directly..."
        start "" /B /D "!INSTALL_DIR!" "!ADAPTER_EXE!" >> "!LOG_FILE!" 2>&1
        call :log "Direct adapter start command exit code: !errorlevel!"
    ) else (
        call :log "ERROR: Could not find !ADAPTER_EXE!."
        exit /b 1
    )
)

call :log "Adapter restart requested."
exit /b 0

:log
echo [%date% %time%] %~1 >> "!LOG_FILE!"
exit /b 0
