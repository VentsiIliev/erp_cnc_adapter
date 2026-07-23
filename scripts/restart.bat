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

echo Stopping adapter... >> "!LOG_FILE!"
taskkill /F /T /IM erp-cnc-adapter.exe >> "!LOG_FILE!" 2>&1

echo Stopping Eding CNC GUI... >> "!LOG_FILE!"
taskkill /F /T /IM cnc4.03.exe >> "!LOG_FILE!" 2>&1
taskkill /F /T /IM cnc.exe >> "!LOG_FILE!" 2>&1

echo Stopping CNC Server... >> "!LOG_FILE!"
taskkill /F /T /IM CncServer.exe >> "!LOG_FILE!" 2>&1

timeout /t 2 >nul
set "AUTO_GUI=0"
for /f "usebackq delims=" %%G in (`powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "$p='!INSTALL_DIR!\config.json'; if (Test-Path -LiteralPath $p) { try { $c = Get-Content -LiteralPath $p -Raw | ConvertFrom-Json; if ($c.auto_start_eding_gui) { '1' } else { '0' } } catch { '0' } } else { '0' }"`) do set "AUTO_GUI=%%G"

if "!AUTO_GUI!"=="1" (
    echo Auto GUI is enabled; starting Eding GUI before adapter... >> "!LOG_FILE!"
    powershell.exe -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "!INSTALL_DIR!\scripts\start_eding_handoff.ps1" >> "!LOG_FILE!" 2>&1
    if errorlevel 1 (
        echo ERROR: Eding GUI startup failed. >> "!LOG_FILE!"
        exit /b 1
    )
    timeout /t 15 >nul
) else (
    echo Deferring Eding GUI launch until adapter readiness is confirmed... >> "!LOG_FILE!"
    echo 1 > "!INSTALL_DIR!\manual_start_defer_gui.flag"
)

echo Starting adapter... >> "!LOG_FILE!"
schtasks /Run /TN ERPCNCAdapter >> "!LOG_FILE!" 2>&1
if errorlevel 1 (
    set "ADAPTER_EXE=!INSTALL_DIR!\erp-cnc-adapter.exe"
    set "HIDDEN_LAUNCHER=!INSTALL_DIR!\scripts\launch_adapter_hidden.vbs"
    if exist "!HIDDEN_LAUNCHER!" (
        echo Scheduled task is disabled or unavailable; starting adapter through hidden launcher... >> "!LOG_FILE!"
        wscript.exe //B //Nologo "!HIDDEN_LAUNCHER!" >> "!LOG_FILE!" 2>&1
    ) else if exist "!ADAPTER_EXE!" (
        echo Scheduled task is disabled or unavailable; starting adapter directly... >> "!LOG_FILE!"
        start "" /B /D "!INSTALL_DIR!" "!ADAPTER_EXE!" >> "!LOG_FILE!" 2>&1
    ) else (
        echo ERROR: Could not find "!ADAPTER_EXE!". >> "!LOG_FILE!"
        exit /b 1
    )
)

echo Adapter restart requested. >> "!LOG_FILE!"
exit /b 0
