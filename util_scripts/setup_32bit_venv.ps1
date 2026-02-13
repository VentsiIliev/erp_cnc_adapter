# Setup 32-bit Python Virtual Environment for CNC DLL
# Run this script after installing 32-bit Python to C:\Python311-32\

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "32-bit Python Setup for CNC Adapter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Check if 32-bit Python is installed
$python32Path = "C:\Python311-32\python.exe"

if (-Not (Test-Path $python32Path)) {
    Write-Host "[ERROR] 32-bit Python not found at $python32Path" -ForegroundColor Red
    Write-Host ""
    Write-Host "Please install 32-bit Python first:" -ForegroundColor Yellow
    Write-Host "1. Download from: https://www.python.org/ftp/python/3.11.9/python-3.11.9.exe" -ForegroundColor Yellow
    Write-Host "2. Install to: C:\Python311-32\" -ForegroundColor Yellow
    Write-Host "3. Then run this script again" -ForegroundColor Yellow
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# Verify it's 32-bit
Write-Host "[*] Checking Python architecture..." -ForegroundColor Yellow
$bitCheck = & $python32Path -c "import struct; print(struct.calcsize('P') * 8)"

if ($bitCheck -ne "32") {
    Write-Host "[ERROR] Python at $python32Path is not 32-bit!" -ForegroundColor Red
    Write-Host "It appears to be $bitCheck-bit" -ForegroundColor Red
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Found 32-bit Python" -ForegroundColor Green
Write-Host ""

# Remove old venv if exists
$venvPath = "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter\.venv"
if (Test-Path $venvPath) {
    Write-Host "[*] Removing old virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
    Write-Host "[OK] Old venv removed" -ForegroundColor Green
}

# Create new 32-bit venv
Write-Host ""
Write-Host "[*] Creating new 32-bit virtual environment..." -ForegroundColor Yellow
& $python32Path -m venv $venvPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create virtual environment" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Virtual environment created" -ForegroundColor Green
Write-Host ""

# Activate and install dependencies
Write-Host "[*] Installing dependencies..." -ForegroundColor Yellow
$pipPath = "$venvPath\Scripts\pip.exe"
$pythonVenvPath = "$venvPath\Scripts\python.exe"

# Upgrade pip
& $pipPath install --upgrade pip

# Install requirements
$reqPath = "C:\Users\Notebook 1\Desktop\erp_cnc_adapter\erp_cnc_adapter\requirements.txt"
if (Test-Path $reqPath) {
    & $pipPath install -r $reqPath
} else {
    Write-Host "[WARNING] requirements.txt not found, installing manually..." -ForegroundColor Yellow
    & $pipPath install fastapi "uvicorn[standard]" requests pydantic
}

Write-Host ""
Write-Host "[OK] Dependencies installed" -ForegroundColor Green
Write-Host ""

# Verify final setup
Write-Host "[*] Verifying setup..." -ForegroundColor Yellow
$venvBitCheck = & $pythonVenvPath -c "import struct; print(struct.calcsize('P') * 8)"
Write-Host "Virtual environment Python is: $venvBitCheck-bit" -ForegroundColor Cyan

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "To run your server:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\python.exe .\main.py" -ForegroundColor White
Write-Host ""
Write-Host "To activate the virtual environment:" -ForegroundColor Cyan
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"

