# Setup 32-bit Python Virtual Environment for CNC DLL
# Automatically downloads and installs 32-bit Python if missing.
# Run from any location - all paths are resolved dynamically.

# --- Configurable variables --------------------------------------------------
$Python32Version    = "3.11.9"
$Python32InstallDir = "C:\Python311-32"
$Python32Url        = "https://www.python.org/ftp/python/$Python32Version/python-$Python32Version.exe"
# -----------------------------------------------------------------------------

# Resolve paths relative to this script's location
$scriptDir    = $PSScriptRoot                     # .../util_scripts
$projectRoot  = Split-Path $scriptDir -Parent     # .../erp_cnc_adapter
$venvPath     = Join-Path $projectRoot ".venv"
$reqPath      = Join-Path $projectRoot "requirements.txt"
$python32Path = Join-Path $Python32InstallDir "python.exe"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "32-bit Python Setup for CNC Adapter" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Project root : $projectRoot" -ForegroundColor DarkGray
Write-Host "Venv path    : $venvPath" -ForegroundColor DarkGray
Write-Host "Python 32-bit: $python32Path" -ForegroundColor DarkGray
Write-Host ""

# --- Step 1: Install 32-bit Python if missing --------------------------------
if (-Not (Test-Path $python32Path)) {
    Write-Host "[*] 32-bit Python not found. Downloading Python $Python32Version (32-bit)..." -ForegroundColor Yellow
    Write-Host "    URL: $Python32Url" -ForegroundColor DarkGray

    $installerPath = Join-Path $env:TEMP "python-$Python32Version-x86.exe"

    try {
        # Use curl.exe when available (faster); fall back to Invoke-WebRequest
        if (Get-Command curl.exe -ErrorAction SilentlyContinue) {
            curl.exe -L --progress-bar -o $installerPath $Python32Url
        } else {
            $ProgressPreference = 'SilentlyContinue'
            Invoke-WebRequest -Uri $Python32Url -OutFile $installerPath
            $ProgressPreference = 'Continue'
        }
    } catch {
        Write-Host "[ERROR] Download failed: $_" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Host "[OK] Download complete. Installing to $Python32InstallDir ..." -ForegroundColor Green

    # Silent install flags:
    #   /quiet             - no UI
    #   InstallAllUsers=0  - current user only (no elevation required)
    #   TargetDir          - custom install path
    #   PrependPath=0      - do not modify PATH (avoids conflict with 64-bit Python)
    #   Include_launcher=0 - skip py.exe launcher
    $installArgs = "/quiet InstallAllUsers=0 TargetDir=`"$Python32InstallDir`" PrependPath=0 Include_launcher=0"

    Write-Host "[*] Running installer (this may take a minute) " -ForegroundColor Yellow -NoNewline
    $proc = Start-Process -FilePath $installerPath -ArgumentList $installArgs -PassThru
    $spinChars = @('|', '/', '-', '\')
    $i = 0
    while (-not $proc.HasExited) {
        Write-Host "`b$($spinChars[$i % 4])" -NoNewline -ForegroundColor Yellow
        $i++
        Start-Sleep -Milliseconds 150
    }
    Write-Host "`b " # clear the spinner character

    Remove-Item $installerPath -ErrorAction SilentlyContinue

    if ($proc.ExitCode -ne 0) {
        Write-Host "[ERROR] Python installer exited with code $($proc.ExitCode)" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    if (-Not (Test-Path $python32Path)) {
        Write-Host "[ERROR] Installation finished but python.exe not found at $python32Path" -ForegroundColor Red
        Read-Host "Press Enter to exit"
        exit 1
    }

    Write-Host "[OK] Python $Python32Version (32-bit) installed successfully." -ForegroundColor Green
    Write-Host ""
} else {
    Write-Host "[OK] 32-bit Python found at $python32Path" -ForegroundColor Green
}

# --- Step 2: Verify the Python binary is actually 32-bit ---------------------
Write-Host "[*] Verifying Python architecture..." -ForegroundColor Yellow
$bitCheck = & $python32Path -c "import struct; print(struct.calcsize('P') * 8)" 2>&1

if ($bitCheck -ne "32") {
    Write-Host "[ERROR] Python at $python32Path reports $bitCheck-bit, expected 32-bit." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$pyVersion = & $python32Path --version 2>&1
Write-Host "[OK] Confirmed 32-bit Python ($pyVersion)" -ForegroundColor Green
Write-Host ""

# --- Step 3: Remove stale venv if it exists ----------------------------------
if (Test-Path $venvPath) {
    Write-Host "[*] Removing existing virtual environment..." -ForegroundColor Yellow
    Remove-Item -Recurse -Force $venvPath
    Write-Host "[OK] Old venv removed." -ForegroundColor Green
    Write-Host ""
}

# --- Step 4: Create new 32-bit venv ------------------------------------------
Write-Host "[*] Creating 32-bit virtual environment at $venvPath ..." -ForegroundColor Yellow
& $python32Path -m venv $venvPath

if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Failed to create virtual environment." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Virtual environment created." -ForegroundColor Green
Write-Host ""

# --- Step 5: Install dependencies --------------------------------------------
$pipPath        = Join-Path $venvPath "Scripts\pip.exe"
$pythonVenvPath = Join-Path $venvPath "Scripts\python.exe"

Write-Host "[*] Upgrading pip..." -ForegroundColor Yellow
& $pipPath install --upgrade pip --quiet

if (Test-Path $reqPath) {
    Write-Host "[*] Installing dependencies from requirements.txt..." -ForegroundColor Yellow
    & $pipPath install -r $reqPath
} else {
    Write-Host "[WARNING] requirements.txt not found at $reqPath" -ForegroundColor Yellow
    Write-Host "[*] Installing default packages..." -ForegroundColor Yellow
    & $pipPath install fastapi "uvicorn[standard]" python-multipart pywin32
}

Write-Host ""
Write-Host "[OK] Dependencies installed." -ForegroundColor Green
Write-Host ""

# --- Step 6: Final verification ----------------------------------------------
Write-Host "[*] Verifying virtual environment..." -ForegroundColor Yellow
$venvBitCheck = & $pythonVenvPath -c "import struct; print(struct.calcsize('P') * 8)"

if ($venvBitCheck -ne "32") {
    Write-Host "[ERROR] Venv Python reports $venvBitCheck-bit -- something went wrong." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

Write-Host "[OK] Virtual environment Python is 32-bit." -ForegroundColor Green
Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "[SUCCESS] Setup Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "Run the server:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\python.exe main.py" -ForegroundColor White
Write-Host ""
Write-Host "Activate the virtual environment:" -ForegroundColor Cyan
Write-Host "  .venv\Scripts\Activate.ps1" -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to exit"