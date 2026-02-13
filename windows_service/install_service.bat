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
    set EXE_MODE=DIST
    goto :exe_found
)

if exist "dist\erp-cnc-adapter.exe" (
    echo Found EXE in development mode
    set EXE_MODE=DEV
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
echo Step 1: Checking dependencies
python -c "import win32serviceutil" >nul 2>&1
if %errorlevel% equ 0 (
    echo   pywin32 is already installed
) else (
    echo   Installing pywin32 (this may take 1-2 minutes^)
    python -m pip install pywin32
    if %errorlevel% neq 0 (
        echo ERROR: Failed to install pywin32
        pause
        exit /b 1
    )
)

echo.
echo Step 2: Checking for existing service...
sc query ERPCNCAdapter >nul 2>&1
if %errorlevel% equ 0 (
    echo Stopping existing service...
    net stop ERPCNCAdapter >nul 2>&1
    echo Removing existing service...
    python windows_service\service_exe.py remove
    timeout /t 2 >nul
)

echo.
echo Step 3: Installing Windows service...
python windows_service\service_exe.py install
if %errorlevel% neq 0 (
    echo ERROR: Failed to install service
    pause
    exit /b 1
)

echo.
echo Step 4: Configuring auto-start and recovery...
sc config ERPCNCAdapter start= auto
sc failure ERPCNCAdapter reset= 86400 actions= restart/5000/restart/10000/restart/30000

echo.
echo Step 4a: Configuring Windows Firewall...
echo   Adding firewall rule for port 8002...
netsh advfirewall firewall delete rule name="ERP-CNC Adapter" >nul 2>&1
netsh advfirewall firewall add rule name="ERP-CNC Adapter" dir=in action=allow protocol=TCP localport=8002 enable=yes profile=any description="Allow incoming connections to ERP-CNC Adapter API"
if %errorlevel% equ 0 (
    echo   Firewall rule added successfully
) else (
    echo   WARNING: Failed to add firewall rule - manual configuration may be needed
)

echo.
echo Step 5: Starting service...
python windows_service\service_exe.py start
if %errorlevel% neq 0 (
    echo ERROR: Failed to start service
    echo Check logs\service.log for details
    pause
    exit /b 1
)

timeout /t 3 >nul

REM Verify service is running
sc query ERPCNCAdapter | find "RUNNING" >nul
if %errorlevel% equ 0 (
    echo.
    echo ========================================
    echo  SUCCESS! Service installed and running
    echo ========================================
    echo.
    echo Service Name: ERPCNCAdapter
    echo Display Name: ERP-CNC Adapter Service
    echo Status: Running
    echo Startup Type: Automatic
    echo.
    echo Access the adapter at: http://localhost:8000
    echo API Documentation: http://localhost:8000/docs
    echo.
    echo Service logs: logs\service.log
    echo.
    echo Management commands:
    echo   Start:   net start ERPCNCAdapter
    echo   Stop:    net stop ERPCNCAdapter
    echo   Restart: net stop ERPCNCAdapter ^& net start ERPCNCAdapter
    echo   Status:  sc query ERPCNCAdapter
    echo.
    echo To uninstall: Run windows_service\uninstall_service.bat
) else (
    echo.
    echo WARNING: Service installed but not running!
    echo Check logs\service.log for details
)

echo.
pause

