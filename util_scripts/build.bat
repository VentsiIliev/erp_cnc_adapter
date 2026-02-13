@echo off
cd /d "%~dp0.."

REM Get version from version.py - simple findstr approach
for /f "tokens=3 delims= " %%a in ('findstr /B "VERSION" version.py') do (
    set VERSION=%%a
)
REM Remove quotes
set VERSION=%VERSION:"=%

if "%VERSION%"=="" (
    echo ERROR: Could not extract version from version.py
    echo Make sure version.py contains: VERSION = "x.x.x"
    pause
    exit /b 1
)

echo ========================================
echo  Building ERP-CNC Adapter v%VERSION%
echo ========================================
echo.

REM Step 0: Run tests first — abort on any failure
echo Step 0: Running test suite...
python -m pytest tests/ --timeout=15 -q
if %errorlevel% neq 0 (
    echo.
    echo ERROR: Tests failed! Fix failing tests before building.
    pause
    exit /b 1
)
echo   All tests passed.
echo.

REM Step 1: Build EXE
echo Step 1: Building EXE with PyInstaller...
.venv\Scripts\pyinstaller.exe util_scripts\erp-cnc-adapter.spec --clean

if %errorlevel% neq 0 (
    echo ERROR: Build failed!
    pause
    exit /b 1
)

REM Step 2: Create versioned distribution package
echo.
echo Step 2: Creating distribution package v%VERSION%...

set DIST_FOLDER=dist\dist_v%VERSION%

REM Remove old dist version if exists
if exist "%DIST_FOLDER%" rd /s /q "%DIST_FOLDER%"

REM Create directory structure
mkdir "%DIST_FOLDER%"
mkdir "%DIST_FOLDER%\windows_service"
mkdir "%DIST_FOLDER%\logs"

REM Copy EXE
echo   Copying EXE...
copy "dist\erp-cnc-adapter.exe" "%DIST_FOLDER%\" >nul

REM Copy service files
echo   Copying service files...
copy "windows_service\service_exe.py" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\install_service.bat" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\uninstall_service.bat" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\update_adapter.py" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\service_status.bat" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\restart_service.bat" "%DIST_FOLDER%\windows_service\" >nul
copy "windows_service\README.md" "%DIST_FOLDER%\windows_service\" >nul

REM Copy documentation
echo   Copying documentation...
if exist "SERVICE_SETUP.md" copy "SERVICE_SETUP.md" "%DIST_FOLDER%\" >nul
if exist "IMPLEMENTATION_SUMMARY.txt" copy "IMPLEMENTATION_SUMMARY.txt" "%DIST_FOLDER%\" >nul

REM Create version info file
echo   Creating version info...
(
echo ERP-CNC Adapter
echo Version: %VERSION%
echo Build Date: %DATE% %TIME%
echo.
echo This is a distribution package ready for deployment.
) > "%DIST_FOLDER%\VERSION.txt"

REM Create distribution README
echo   Creating README...
(
echo ================================================================
echo  ERP-CNC Adapter v%VERSION% - Distribution Package
echo ================================================================
echo.
echo QUICK START:
echo   1. Ensure Python 3.8+ ^(32-bit^) is installed on target machine
echo   2. Right-click: windows_service\install_service.bat
echo   3. Select: "Run as administrator"
echo   4. Access: http://localhost:8000
echo.
echo CONTENTS:
echo   erp-cnc-adapter.exe    - The application
echo   windows_service\       - Service installation and management
echo   logs\                  - Log directory ^(auto-populated^)
echo   VERSION.txt            - Build information
echo.
echo DOCUMENTATION:
echo   windows_service\README.md - Complete service documentation
echo.
echo MANAGEMENT:
echo   Start:     net start ERPCNCAdapter
echo   Stop:      net stop ERPCNCAdapter
echo   Status:    windows_service\service_status.bat
echo   Uninstall: windows_service\uninstall_service.bat
echo.
echo UPDATING:
echo   python windows_service\update_adapter.py path\to\new-exe
echo.
echo For detailed instructions, see windows_service\README.md
echo.
echo ================================================================
) > "%DIST_FOLDER%\README.txt"

echo.
echo ========================================
echo  Build Complete!
echo ========================================
echo.
echo Version: %VERSION%
echo Distribution: %DIST_FOLDER%\
echo.
echo Contents:
echo   [√] erp-cnc-adapter.exe
echo   [√] windows_service\ (7 files)
echo   [√] logs\ (empty directory)
echo   [√] VERSION.txt
echo   [√] README.txt
echo.
echo Ready to deploy! Copy the dist_v%VERSION% folder to target machines.
echo.
echo Next steps for local installation:
echo   cd %DIST_FOLDER%
echo   Right-click windows_service\install_service.bat
echo   Select "Run as administrator"
echo.
REM Only pause when run directly (not called from build_installer.bat)
if "%BUILD_NO_PAUSE%"=="" pause
