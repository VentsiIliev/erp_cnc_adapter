@echo off
echo ========================================
echo  ERP-CNC Adapter Status
echo ========================================
echo.

cd /d "%~dp0.."

REM Check scheduled task
schtasks /Query /TN ERPCNCAdapter >nul 2>&1
if %errorlevel% neq 0 (
    echo Startup Task: NOT INSTALLED
    echo.
    echo To install: Run scripts\install.bat as Administrator
    goto :check_process
)

echo Startup Task: INSTALLED
schtasks /Query /TN ERPCNCAdapter /V /FO LIST | findstr /I "Status Last"
echo.

:check_process
echo Process Status:
tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" 2>nul | find /I "erp-cnc-adapter.exe" >nul 2>&1
if %errorlevel% equ 0 (
    echo   erp-cnc-adapter.exe is RUNNING
    tasklist /FI "IMAGENAME eq erp-cnc-adapter.exe" /FO TABLE
) else (
    echo   erp-cnc-adapter.exe is NOT RUNNING
)

echo.
echo Recent Log Entries:
echo ----------------------------------------
if exist "logs\adapter.log" (
    powershell -Command "Get-Content logs\adapter.log -Tail 15"
) else (
    echo No log file found
)
echo ----------------------------------------

echo.
pause
