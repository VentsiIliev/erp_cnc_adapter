@echo off
REM Pure Windows Service Installation (No Python Required)
REM Uses NSSM (Non-Sucking Service Manager) or sc.exe directly

echo ========================================
echo  ERP-CNC Adapter Service Installer
echo  (Python-Free Version)
echo ========================================
echo.

REM Check admin
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Must run as Administrator
    pause
    exit /b 1
)

cd /d "%~dp0.."

REM Check if EXE exists
if not exist "erp-cnc-adapter.exe" (
    echo ERROR: erp-cnc-adapter.exe not found
    pause
    exit /b 1
)

set EXE_PATH=%CD%\erp-cnc-adapter.exe

echo Creating Windows Service...
echo EXE: %EXE_PATH%

REM Stop and remove old service if it exists
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    echo Stopping existing service...
    net stop ERPCNCAdapter >nul 2>&1
    echo Removing existing service...
    sc delete ERPCNCAdapter
    timeout /t 2 >nul
)

REM Create service using sc.exe (built into Windows)
echo Installing service...
sc create ERPCNCAdapter ^
    binPath= "\"%EXE_PATH%\"" ^
    DisplayName= "ERP-CNC Adapter Service" ^
    start= auto

if %errorlevel% neq 0 (
    echo ERROR: Failed to create service
    pause
    exit /b 1
)

REM Configure service description
sc description ERPCNCAdapter "REST API service for CNC machine control"

REM Configure failure recovery
sc failure ERPCNCAdapter reset= 86400 actions= restart/5000/restart/10000/restart/30000

echo.
echo Starting service...
net start ERPCNCAdapter

if %errorlevel% neq 0 (
    echo WARNING: Service created but failed to start
    echo Check logs at: %CD%\logs\adapter.log
) else (
    echo.
    echo ========================================
    echo  Installation Complete!
    echo ========================================
    echo.
    echo Service: ERPCNCAdapter
    echo Status: Running
    echo Port: 8002
    echo URL: http://localhost:8002
)

pause

