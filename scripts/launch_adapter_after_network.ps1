$ErrorActionPreference = 'SilentlyContinue'

$installDir = Split-Path -Parent $PSScriptRoot
$exePath = Join-Path $installDir 'erp-cnc-adapter.exe'
$configPath = Join-Path $installDir 'config.json'
$logDir = Join-Path $installDir 'logs'
$logPath = Join-Path $logDir 'adapter-startup.log'
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
    if (-not (Test-Path -LiteralPath $configPath)) { return $null }
    try {
        $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
        if ($config.base_dir) { return [string]$config.base_dir }
    } catch {
        Write-StartupLog ('Could not read config.json for network preflight: {0}' -f $_.Exception.Message)
    }
    return $null
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

$baseDir = Get-ConfiguredBaseDir
if ($baseDir -and $baseDir.StartsWith('\\')) {
    Write-StartupLog ('Waiting for configured CNC job share: {0}' -f $baseDir)
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

try {
    Write-StartupLog ('Starting adapter: {0}' -f $exePath)
    Start-Process -FilePath $exePath -WorkingDirectory $installDir -WindowStyle Hidden
    exit 0
} catch {
    Write-StartupLog ('ERROR: Failed to start adapter: {0}' -f $_.Exception.Message)
    exit 4
}