@echo off
setlocal EnableDelayedExpansion

echo ========================================
echo  ERP-CNC Adapter Uninstaller
echo ========================================
echo.

REM Check admin privileges.
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: This uninstaller must be run as Administrator!
    echo.
    echo Right-click this file and select "Run as administrator"
    pause
    exit /b 1
)

for %%I in ("%~dp0..") do set "INSTALL_DIR=%%~fI"
cd /d "%SystemRoot%"

set FOUND_SOMETHING=0

echo Step 1: Stopping and removing old Windows service...
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    set FOUND_SOMETHING=1
    sc query ERPCNCAdapter | find "RUNNING" >nul 2>&1
    if !errorlevel! equ 0 (
        echo   Stopping service...
        net stop ERPCNCAdapter >nul 2>&1
        timeout /t 3 >nul
    )
    echo   Removing service registration...
    sc delete ERPCNCAdapter >nul 2>&1
    echo   Service removed
) else (
    echo   No service found
)

echo.
echo Step 2: Stopping and removing scheduled tasks...
for %%T in (ERPCNCAdapterStatusIndicator ERPCNCAdapterEdingHandoff ERPCNCAdapterManualStart ERPCNCAdapterWatchdog ERPCNCAdapter) do (
    schtasks /Query /TN %%T >nul 2>&1
    if !errorlevel! equ 0 (
        set FOUND_SOMETHING=1
        echo   Removing %%T...
        schtasks /End /TN %%T >nul 2>&1
        timeout /t 1 >nul
        schtasks /Delete /TN %%T /F >nul 2>&1
        if !errorlevel! equ 0 (
            echo   %%T removed
        ) else (
            echo   WARNING: Could not remove %%T
        )
    )
)

echo.
echo Step 3: Stopping adapter, Eding GUI, CNC Server, and script launchers...
if exist "%INSTALL_DIR%\scripts\status_indicator.ps1" (
    powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "$target = Join-Path '%INSTALL_DIR%' 'scripts\status_indicator.ps1'; $currentPid = $PID; Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $currentPid -and ($_.Name -ieq 'powershell.exe' -or $_.Name -ieq 'pwsh.exe') -and $_.CommandLine -and $_.CommandLine.IndexOf($target, [StringComparison]::OrdinalIgnoreCase) -ge 0 } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }" >nul 2>&1
)
for %%P in (erp-cnc-adapter.exe cnc4.03.exe cnc.exe CncServer.exe wscript.exe) do (
    tasklist /FI "IMAGENAME eq %%P" 2>nul | find /I "%%P" >nul 2>&1
    if !errorlevel! equ 0 (
        set FOUND_SOMETHING=1
        echo   Stopping %%P...
        taskkill /F /T /IM %%P >nul 2>&1
    )
)
timeout /t 3 >nul

echo.
echo Step 4: Removing START-CNC desktop shortcut...
for %%S in ("%PUBLIC%\Desktop\START-CNC.lnk" "%USERPROFILE%\Desktop\START-CNC.lnk") do (
    if exist %%S (
        del /F /Q %%S >nul 2>&1
        echo   Removed %%S
    )
)

echo.
echo Step 5: Removing firewall rule...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
if %errorlevel% equ 0 (
    echo   Firewall rule removed
) else (
    echo   No firewall rule found
)

echo.
echo Step 6: Removing installation folder...
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -Command "Start-Sleep -Seconds 3; Remove-Item -LiteralPath '%INSTALL_DIR%' -Recurse -Force -ErrorAction SilentlyContinue" >nul 2>&1

echo.
echo ========================================
echo  ERP-CNC Adapter uninstall requested
echo ========================================
echo.
echo Installation folder: %INSTALL_DIR%
echo If the folder remains, reboot Windows and delete it once more.
echo To reinstall, run the installer again.
echo.
exit /b 0
