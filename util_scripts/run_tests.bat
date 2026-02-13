@echo off
echo ============================================
echo   ERP-CNC Adapter - Test Suite
echo ============================================
echo.

cd /d "%~dp0.."

:: Activate virtual environment if it exists
if exist ".venv\Scripts\activate.bat" (
    call .venv\Scripts\activate.bat
)

:: Run pytest with verbose output and timeout
python -m pytest tests/ -v --timeout=15 %*

echo.
echo ============================================
echo   Tests complete
echo ============================================
pause