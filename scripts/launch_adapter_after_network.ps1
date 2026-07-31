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
$diagnosticLogSeconds = 15

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

function Get-UncHost($path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return '' }
    if (-not $path.StartsWith('\\')) { return '' }
    $trimmed = $path.TrimStart('\')
    return ($trimmed -split '\\')[0]
}
function Get-UncShareRoot($path) {
    if ([string]::IsNullOrWhiteSpace($path)) { return '' }
    if (-not $path.StartsWith('\\')) { return '' }
    $parts = $path.TrimStart('\') -split '\\'
    if ($parts.Count -lt 2) { return '' }
    return ('\\{0}\{1}' -f $parts[0], $parts[1])
}

function Connect-UncShare($path) {
    $shareRoot = Get-UncShareRoot $path
    if ([string]::IsNullOrWhiteSpace($shareRoot)) { return 'not_applicable' }

    try {
        $output = & cmd.exe /c net use $shareRoot /persistent:no 2>&1
        $message = (($output | Out-String).Trim() -replace "\r?\n", ' | ')
        if ([string]::IsNullOrWhiteSpace($message)) { $message = 'no output' }
        return ('net use {0} exit={1}: {2}' -f $shareRoot, $LASTEXITCODE, $message)
    } catch {
        return ('net use {0} exception: {1}' -f $shareRoot, $_.Exception.Message)
    }
}

function Test-TcpPort($hostName, $port, $timeoutMs) {
    if ([string]::IsNullOrWhiteSpace($hostName)) { return 'not_applicable' }
    $client = $null
    try {
        $client = New-Object System.Net.Sockets.TcpClient
        $async = $client.BeginConnect($hostName, [int]$port, $null, $null)
        if (-not $async.AsyncWaitHandle.WaitOne([int]$timeoutMs, $false)) {
            return 'timeout'
        }
        $client.EndConnect($async)
        return 'open'
    } catch {
        return ('failed: {0}' -f $_.Exception.Message)
    } finally {
        if ($client) { $client.Close() }
    }
}

function Get-JobShareProbe($path) {
    if ([string]::IsNullOrWhiteSpace($path)) {
        return @{ Ready = $true; Message = 'no path configured' }
    }
    if (-not $path.StartsWith('\\')) {
        return @{ Ready = $true; Message = 'local path; network preflight not required' }
    }

    $hostName = Get-UncHost $path
    $tcp445 = Test-TcpPort $hostName 445 1000

    try {
        $exists = Test-Path -LiteralPath $path -ErrorAction Stop
    } catch {
        return @{ Ready = $false; Message = ('host={0} tcp445={1} Test-Path exception: {2}' -f $hostName, $tcp445, $_.Exception.Message) }
    }

    if (-not $exists) {
        return @{ Ready = $false; Message = ('host={0} tcp445={1} Test-Path returned false' -f $hostName, $tcp445) }
    }

    try {
        Get-ChildItem -LiteralPath $path -ErrorAction Stop | Select-Object -First 1 | Out-Null
        return @{ Ready = $true; Message = ('host={0} tcp445={1} directory enumeration OK' -f $hostName, $tcp445) }
    } catch {
        return @{ Ready = $false; Message = ('host={0} tcp445={1} Get-ChildItem exception: {2}' -f $hostName, $tcp445, $_.Exception.Message) }
    }
}

function Write-StartupContext($baseDir) {
    try {
        $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    } catch {
        $identity = ('unknown: {0}' -f $_.Exception.Message)
    }

    try {
        $sessionId = (Get-Process -Id $PID -ErrorAction Stop).SessionId
    } catch {
        $sessionId = 'unknown'
    }

    Write-StartupLog ('Startup preflight context: pid={0} user={1} session={2} install_dir={3} base_dir={4}' -f $PID, $identity, $sessionId, $installDir, $baseDir)
}

function Test-JobShareReady($path) {
    $probe = Get-JobShareProbe $path
    return [bool]$probe.Ready
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
    Write-StartupContext $baseDir
    if ($baseDir -and $baseDir.StartsWith('\\')) {
        Write-StartupLog ('Ensuring SMB session for CNC job share: {0}' -f (Connect-UncShare $baseDir))
        Write-StartupLog ('Waiting for resolved CNC job share: {0}' -f $baseDir)
        $start = Get-Date
        $lastDiagnostic = (Get-Date).AddSeconds(-1 * $diagnosticLogSeconds)
        while (((Get-Date) - $start).TotalSeconds -lt $timeoutSeconds) {
            $probe = Get-JobShareProbe $baseDir
            if ($probe.Ready) {
                $elapsed = [int]((Get-Date) - $start).TotalSeconds
                Write-StartupLog ('CNC job share is ready after {0}s: {1}; {2}' -f $elapsed, $baseDir, $probe.Message)
                break
            }

            if (((Get-Date) - $lastDiagnostic).TotalSeconds -ge $diagnosticLogSeconds) {
                $elapsed = [int]((Get-Date) - $start).TotalSeconds
                Write-StartupLog ('Still waiting for CNC job share after {0}s: {1}; {2}' -f $elapsed, $baseDir, $probe.Message)
                Write-StartupLog ('Retrying SMB session for CNC job share: {0}' -f (Connect-UncShare $baseDir))
                $lastDiagnostic = Get-Date
            }
            Start-Sleep -Seconds $pollSeconds
        }

        $finalProbe = Get-JobShareProbe $baseDir
        if (-not $finalProbe.Ready) {
            Write-StartupLog ('ERROR: CNC job share was not ready within {0}s; adapter was not started: {1}; {2}' -f $timeoutSeconds, $baseDir, $finalProbe.Message)
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
