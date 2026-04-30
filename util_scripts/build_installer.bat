@echo off
REM Build self-contained installer using PyInstaller (no external tools needed!)
REM This creates a single EXE that contains everything

cd /d "%~dp0.."

set "VENV_PYTHON=.venv\Scripts\python.exe"

if not exist "%VENV_PYTHON%" (
    echo ERROR: Virtual environment Python not found at %VENV_PYTHON%
    echo Create the project venv and install requirements before building the installer.
    pause
    exit /b 1
)

echo ========================================
echo  Building Self-Contained Installer
echo ========================================
echo.

REM Check PyQt5 is installed (build dependency — has 32-bit Windows wheels)
"%VENV_PYTHON%" -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo PyQt5 not found. Installing build dependency...
    "%VENV_PYTHON%" -m pip install --only-binary :all: PyQt5
)
"%VENV_PYTHON%" -c "import PyQt5" >nul 2>&1
if %errorlevel% neq 0 (
    echo ERROR: Failed to install PyQt5.
    pause
    exit /b 1
)

REM Step 1: Build the main application (skip pause so we continue automatically)
echo Step 1: Building application...
set BUILD_NO_PAUSE=1
call "%~dp0build.bat"
set BUILD_NO_PAUSE=
if %errorlevel% neq 0 (
    echo ERROR: Failed to build application
    pause
    exit /b 1
)

REM Read version (build.bat already validated it)
for /f "tokens=3 delims= " %%a in ('findstr /B "VERSION" version.py') do set VERSION=%%a
set VERSION=%VERSION:"=%

echo.
echo Step 2: Preparing installer payload...

REM Create payload directory
if exist "src\installer\payload" rd /s /q "src\installer\payload"
mkdir "src\installer\payload"

REM Copy dist folder contents to payload
xcopy /E /I /Y "dist\dist_v%VERSION%\*" "src\installer\payload\"

echo.
echo Step 3: Building installer EXE...

REM Check if icon exists
set ICON_ARG=
if exist "resources\logo.ico" (
    set ICON_ARG=--icon "resources\logo.ico"
    echo Using custom icon: resources\logo.ico
) else if exist "src\installer\icon.ico" (
    set ICON_ARG=--icon "src\installer\icon.ico"
    echo Using custom icon: src\installer\icon.ico
) else (
    echo Using default icon
)

REM Build the installer using PyInstaller
REM PyQt6 needs explicit hidden imports when frozen
"%VENV_PYTHON%" -m PyInstaller --clean --noconfirm ^
    --name "ERP-CNC-Adapter-Setup-v%VERSION%" ^
    --onefile ^
    --windowed ^
    --add-data "src\installer\payload;payload" ^
    --add-data "resources\logo.ico;resources" ^
    --hidden-import PyQt5 ^
    --hidden-import PyQt5.QtWidgets ^
    --hidden-import PyQt5.QtCore ^
    --hidden-import PyQt5.QtGui ^
    %ICON_ARG% ^
    "run_installer.py"

if %errorlevel% neq 0 (
    echo ERROR: Failed to build installer
    pause
    exit /b 1
)

echo.
echo Step 4: Moving installer to distribution folder...
move /Y "dist\ERP-CNC-Adapter-Setup-v%VERSION%.exe" "dist\dist_v%VERSION%\" >nul

REM Cleanup
if exist "src\installer\payload" rd /s /q "src\installer\payload"
if exist "build" rd /s /q "build"
if exist "ERP-CNC-Adapter-Setup-v%VERSION%.spec" del /q "ERP-CNC-Adapter-Setup-v%VERSION%.spec"

echo.
echo ========================================
echo  SUCCESS! Installer Created
echo ========================================
echo.

REM Find the installer in the distribution folder
for %%A in ("dist\dist_v%VERSION%\ERP-CNC-Adapter-Setup-*.exe") do (
    echo Installer: %%~nxA
    echo Location: %%~fA
    echo Size: %%~zA bytes
)

echo.
echo Distribution folder: dist\dist_v%VERSION%\
echo.
echo This folder contains:
echo   - erp-cnc-adapter.exe (the application)
echo   - ERP-CNC-Adapter-Setup-v%VERSION%.exe (the installer)
echo   - scripts\ (management scripts)
echo   - logs\ (empty directory)
echo   - VERSION.txt, README.txt
echo.
echo This is a SINGLE FILE that contains everything!
echo.
echo Distribution:
echo   1. Copy this single EXE to target machines
echo   2. Users right-click and "Run as administrator"
echo   3. Follow the wizard to install
echo   4. Done! Application running automatically
echo.
echo No external tools or installers needed!
echo.

pause
