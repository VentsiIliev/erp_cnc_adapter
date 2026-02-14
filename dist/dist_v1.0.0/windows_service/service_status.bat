@echo off
echo ========================================
echo  ERP-CNC Adapter Service Status
echo ========================================
echo.

cd /d "%~dp0.."

sc query ERPCNCAdapter 2>nul | find "STATE" >nul
if %errorlevel% neq 0 (
    echo Status: NOT INSTALLED
    echo.
    echo To install: Run windows_service\install_service.bat as Administrator
    goto :end
)

echo Service Information:
sc query ERPCNCAdapter
echo.

echo Recent Log Entries:
echo ----------------------------------------
if exist "logs\service.log" (
    powershell -Command "Get-Content logs\service.log -Tail 15"
) else (
    echo No log file found
)
echo ----------------------------------------

:end
echo.
pause

