$ErrorActionPreference = 'SilentlyContinue'

$installDir = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $installDir 'erp-cnc-adapter.exe'
$configPath = Join-Path $installDir 'config.json'
$logDir = Join-Path $installDir 'logs'
$logPath = Join-Path $logDir 'adapter-startup.log'
$startupLock = Join-Path $logDir 'adapter-startup.lock'
$defaultBaseDir = '\\192.168.2.11\Production\CNC\Mills'
$timeoutSeconds = 300
$pollSeconds = 2

function Write-StartupLog($message) {
    try {
        if (-not (Test-Path -LiteralPath $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }
        $stamp = Get-Date -Format 'yyyy-MM-dd HH:mm:ss'
        Add-Content -LiteralPath $logPath -Value ('[{0}] {1}' -f $stamp, $message)
    } catch {}
}

function Get-ConfiguredBaseDir {
    $baseDir = $defaultBaseDir
    if (-not (Test-Path -LiteralPath $configPath)) { return $baseDir }
    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if ($config.base_dir -and -not [string]::IsNullOrWhiteSpace([string]$config.base_dir)) {
            $baseDir = [string]$config.base_dir
        }
    } catch {
        Write-StartupLog ('Could not read config.json for network preflight: {0}' -f $_.Exception.Message)
    }
    return $baseDir
}

function Test-JobShareReady($path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return $true }
    if (-not $path.StartsWith('\\')) { return $true }

    try {
        if (-not (Test-Path -LiteralPath $path)) { return $false }
        Get-ChildItem -LiteralPath $path -ErrorAction Stop | Select-Object -First 1 | Out-Null
        return $true
    } catch {
        return $false
    }
}

function Test-AdapterProcessRunning {
    try {
        $resolvedExe = $exePath
        try {
            $resolvedExe = (Resolve-Path -LiteralPath $exePath -ErrorAction Stop).Path
        } catch {}

        $process = Get-CimInstance Win32_Process -Filter "Name = 'erp-cnc-adapter.exe'" -ErrorAction Stop |
            Where-Object { $_.ExecutablePath -eq $resolvedExe } |
            Select-Object -First 1
        return $null -ne $process
    } catch {
        return $null -ne (Get-Process -Name 'erp-cnc-adapter' -ErrorAction SilentlyContinue | Select-Object -First 1)
    }
}

function New-StartupLock {
    try {
        if (-not (Test-Path -LiteralPath $logDir)) {
            New-Item -ItemType Directory -Path $logDir -Force | Out-Null
        }

        if (Test-Path -LiteralPath $startupLock) {
            $lockItem = Get-Item -LiteralPath $startupLock -ErrorAction SilentlyContinue
            if ($lockItem) {
                $lockAgeSeconds = [int]((Get-Date) - $lockItem.CreationTime).TotalSeconds
                if ($lockAgeSeconds -gt ($timeoutSeconds + 60)) {
                    Write-StartupLog ('Removing stale adapter startup lock after {0}s: {1}' -f $lockAgeSeconds, $startupLock)
                    Remove-Item -LiteralPath $startupLock -Recurse -Force -ErrorAction SilentlyContinue
                }
            }
        }

        New-Item -ItemType Directory -Path $startupLock -ErrorAction Stop | Out-Null
        Write-StartupLog ('Acquired adapter startup lock: {0}' -f $startupLock)
        return $true
    } catch {
        return $false
    }
}

if (-not (New-StartupLock)) {
    if (Test-AdapterProcessRunning) {
        Write-StartupLog 'Adapter is already running; duplicate startup request ignored.'
    } else {
        Write-StartupLog ('Adapter startup is already in progress; duplicate startup request ignored: {0}' -f $startupLock)
    }
    exit 0
}

try {
    if (Test-AdapterProcessRunning) {
        Write-StartupLog 'Adapter is already running before preflight; no new process started.'
        exit 0
    }

    $baseDir = Get-ConfiguredBaseDir
    if ($baseDir -and $baseDir.StartsWith('\\')) {
        Write-StartupLog ('Waiting for resolved CNC job share: {0}' -f $baseDir)
        $start = Get-Date
        while (((Get-Date) - $start).TotalSeconds -lt $timeoutSeconds) {
            if (Test-JobShareReady $baseDir) {
                $elapsed = [int]((Get-Date) - $start).TotalSeconds
                Write-StartupLog ('CNC job share is ready after {0}s: {1}' -f $elapsed, $baseDir)
                break
            }
            Start-Sleep -Seconds $pollSeconds
        }

        if (-not (Test-JobShareReady $baseDir)) {
            Write-StartupLog ('ERROR: CNC job share was not ready within {0}s; adapter was not started: {1}' -f $timeoutSeconds, $baseDir)
            exit 2
        }
    }

    if (-not (Test-Path -LiteralPath $exePath)) {
        Write-StartupLog ('ERROR: Adapter executable missing: {0}' -f $exePath)
        exit 3
    }

    if (Test-AdapterProcessRunning) {
        Write-StartupLog 'Adapter started while preflight was waiting; no new process started.'
        exit 0
    }

    try {
        Write-StartupLog ('Starting adapter: {0}' -f $exePath)
        Start-Process -FilePath $exePath -WorkingDirectory $installDir -WindowStyle Hidden
        exit 0
    } catch {
        Write-StartupLog ('ERROR: Failed to start adapter: {0}' -f $_.Exception.Message)
        exit 4
    }
} catch {
    Write-StartupLog ('ERROR: Adapter startup preflight failed: {0}' -f $_.Exception.Message)
    exit 5
} finally {
    Remove-Item -LiteralPath $startupLock -Recurse -Force -ErrorAction SilentlyContinue
}
