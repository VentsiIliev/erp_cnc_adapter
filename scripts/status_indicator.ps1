$ErrorActionPreference = 'SilentlyContinue'

$createdNew = $false
$mutex = New-Object System.Threading.Mutex($true, 'Global\ERP_CNC_Adapter_Status_Indicator', [ref]$createdNew)
if (-not $createdNew) { exit 0 }

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Split-Path -Parent $scriptDir
$iconPath = Join-Path $installDir 'resources\logo.ico'
$configPath = Join-Path $installDir 'config.json'
$defaultPort = 8002
$pollIntervalMs = 1000
$requestTimeoutMs = 2000
$isClosing = $false
$isPolling = $false

function Get-AdapterUrl {
  $port = $defaultPort
  if (Test-Path -LiteralPath $configPath) {
    try {
      $config = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
      if ($config.port) { $port = [int]$config.port }
    } catch {}
  }
  return "http://127.0.0.1:$port"
}

function Get-HealthPayload {
  $url = (Get-AdapterUrl).TrimEnd('/') + '/api/status/indicator'
  try {
    $request = [System.Net.HttpWebRequest]::Create($url)
    $request.Method = 'GET'
    $request.Timeout = $requestTimeoutMs
    $request.ReadWriteTimeout = $requestTimeoutMs
    $response = $request.GetResponse()
    try {
      $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
      $body = $reader.ReadToEnd()
      return @{ Ok = $true; Payload = ($body | ConvertFrom-Json); Error = $null }
    } finally {
      if ($reader) { $reader.Dispose() }
      if ($response) { $response.Dispose() }
    }
  } catch [System.Net.WebException] {
    $webResponse = $_.Exception.Response
    if ($webResponse -ne $null) {
      try {
        $reader = New-Object System.IO.StreamReader($webResponse.GetResponseStream())
        $body = $reader.ReadToEnd()
        return @{ Ok = $true; Payload = ($body | ConvertFrom-Json); Error = $null }
      } catch {
        return @{ Ok = $false; Payload = $null; Error = $_.Exception.Message }
      } finally {
        if ($reader) { $reader.Dispose() }
        if ($webResponse) { $webResponse.Dispose() }
      }
    }
    return @{ Ok = $false; Payload = $null; Error = $_.Exception.Message }
  } catch {
    return @{ Ok = $false; Payload = $null; Error = $_.Exception.Message }
  }
}

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
[System.Windows.Forms.Application]::EnableVisualStyles()

$form = New-Object System.Windows.Forms.Form
$form.Text = 'ERP-CNC Status'
$form.Width = 360
$form.Height = 132
$form.FormBorderStyle = 'FixedDialog'
$form.StartPosition = 'Manual'
$form.ShowInTaskbar = $false
$form.TopMost = $true
$form.ControlBox = $false
$form.MinimizeBox = $false
$form.MaximizeBox = $false
$form.BackColor = [System.Drawing.Color]::FromArgb(248, 250, 252)
if (Test-Path -LiteralPath $iconPath) {
  try { $form.Icon = New-Object System.Drawing.Icon($iconPath) } catch {}
}

$workArea = [System.Windows.Forms.Screen]::PrimaryScreen.WorkingArea
$form.Left = [Math]::Max(0, $workArea.Right - $form.Width - 16)
$form.Top = [Math]::Max(0, $workArea.Bottom - $form.Height - 16)

$title = New-Object System.Windows.Forms.Label
$title.Text = 'ERP-CNC Status'
$title.Left = 12
$title.Top = 8
$title.Width = 320
$title.Height = 18
$title.Font = New-Object System.Drawing.Font('Segoe UI', 9, [System.Drawing.FontStyle]::Bold)
$title.ForeColor = [System.Drawing.Color]::FromArgb(17, 24, 39)
$form.Controls.Add($title)

function New-Dot($left, $top) {
  $dot = New-Object System.Windows.Forms.Label
  $dot.Left = $left
  $dot.Top = $top
  $dot.Width = 13
  $dot.Height = 13
  $dot.BackColor = [System.Drawing.Color]::Gray
  $dot.BorderStyle = 'FixedSingle'
  return $dot
}

$adapterDot = New-Dot 14 42
$form.Controls.Add($adapterDot)
$adapterLabel = New-Object System.Windows.Forms.Label
$adapterLabel.Left = 34
$adapterLabel.Top = 38
$adapterLabel.Width = 300
$adapterLabel.Height = 24
$adapterLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$adapterLabel.Text = 'Adapter: checking'
$form.Controls.Add($adapterLabel)

$cncDot = New-Dot 14 76
$form.Controls.Add($cncDot)
$cncLabel = New-Object System.Windows.Forms.Label
$cncLabel.Left = 34
$cncLabel.Top = 72
$cncLabel.Width = 300
$cncLabel.Height = 24
$cncLabel.Font = New-Object System.Drawing.Font('Segoe UI', 9)
$cncLabel.Text = 'Interpreter: checking'
$form.Controls.Add($cncLabel)

$tray = New-Object System.Windows.Forms.NotifyIcon
$tray.Text = 'ERP-CNC Status'
$tray.Visible = $true
if (Test-Path -LiteralPath $iconPath) {
  try { $tray.Icon = New-Object System.Drawing.Icon($iconPath) } catch { $tray.Icon = [System.Drawing.SystemIcons]::Application }
} else {
  $tray.Icon = [System.Drawing.SystemIcons]::Application
}

$menu = New-Object System.Windows.Forms.ContextMenuStrip
$showItem = $menu.Items.Add('Show status')
$hideItem = $menu.Items.Add('Hide window')
$menu.Items.Add('-') | Out-Null
$exitItem = $menu.Items.Add('Exit indicator')
$showItem.Add_Click({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() })
$hideItem.Add_Click({ $form.Hide() })
$exitItem.Add_Click({ $script:isClosing = $true; if ($timer) { $timer.Stop() }; $tray.Visible = $false; [System.Windows.Forms.Application]::Exit() })
$tray.ContextMenuStrip = $menu
$tray.Add_DoubleClick({ $form.Show(); $form.WindowState = 'Normal'; $form.Activate() })

function Set-TrayText([string]$text) {
  if ([string]::IsNullOrWhiteSpace($text)) { $text = 'ERP-CNC Status' }
  if ($text.Length -gt 63) { $text = $text.Substring(0, 60) + '...' }
  $tray.Text = $text
}

function Set-DotColor($dot, [string]$name) {
  switch ($name) {
    'green' { $dot.BackColor = [System.Drawing.Color]::FromArgb(22, 163, 74) }
    'yellow' { $dot.BackColor = [System.Drawing.Color]::FromArgb(217, 119, 6) }
    'red' { $dot.BackColor = [System.Drawing.Color]::FromArgb(220, 38, 38) }
    default { $dot.BackColor = [System.Drawing.Color]::FromArgb(107, 114, 128) }
  }
}

function Update-Status {
  $health = Get-HealthPayload
  if (-not $health.Ok -or $health.Payload -eq $null) {
    $title.Text = 'ERP-CNC Status'
    Set-DotColor $adapterDot 'red'
    Set-DotColor $cncDot 'gray'
    $adapterLabel.Text = 'Adapter: offline'
    $cncLabel.Text = 'Interpreter: unknown'
    Set-TrayText 'ERP-CNC: adapter offline'
    return
  }

  $payload = $health.Payload
  $interpreter = $payload.interpreter
  $version = if ($payload.version) { [string]$payload.version } else { 'unknown' }
  $title.Text = "ERP-CNC v$version"
  Set-DotColor $adapterDot 'green'
  $adapterLabel.Text = 'Adapter: running'

  if (-not $interpreter) {
    Set-DotColor $cncDot 'gray'
    $cncLabel.Text = 'Interpreter: unknown'
  } elseif ($interpreter.status -eq 'ready') {
    Set-DotColor $cncDot 'green'
    $cncLabel.Text = 'Interpreter: Ready'
  } elseif ($interpreter.status -eq 'error') {
    Set-DotColor $cncDot 'red'
    $cncLabel.Text = 'Interpreter: error'
  } elseif ($interpreter.online -eq $true) {
    Set-DotColor $cncDot 'yellow'
    $stateText = if ($interpreter.machine_state_text) { $interpreter.machine_state_text } elseif ($interpreter.connection_state) { $interpreter.connection_state } else { 'not ready' }
    $cncLabel.Text = "Interpreter: $stateText"
  } else {
    Set-DotColor $cncDot 'red'
    $stateText = if ($interpreter.connection_state) { $interpreter.connection_state } else { 'offline' }
    $cncLabel.Text = "Interpreter: $stateText"
  }
  Set-TrayText ($adapterLabel.Text + ' | ' + $cncLabel.Text)
}

$timer = New-Object System.Windows.Forms.Timer
$timer.Interval = $pollIntervalMs
$timer.Add_Tick({
  if ($script:isClosing -or $script:isPolling) { return }
  $script:isPolling = $true
  try {
    Update-Status
  } catch [System.Management.Automation.PipelineStoppedException] {
    $script:isClosing = $true
    if ($timer) { $timer.Stop() }
  } catch {
    Set-DotColor $adapterDot 'red'
    Set-DotColor $cncDot 'gray'
    $adapterLabel.Text = 'Adapter: status error'
    $cncLabel.Text = 'Interpreter: unknown'
    Set-TrayText 'ERP-CNC: status error'
  } finally {
    $script:isPolling = $false
  }
})
$form.Add_Shown({ Update-Status; $timer.Start() })
$form.Add_FormClosing({
  if ($script:isClosing) {
    if ($timer) { $timer.Stop() }
    return
  }
  if ($_.CloseReason -eq [System.Windows.Forms.CloseReason]::UserClosing) {
    $_.Cancel = $true
    return
  } else {
    $script:isClosing = $true
    if ($timer) { $timer.Stop() }
  }
})

try {
  [System.Windows.Forms.Application]::Run($form)
} finally {
  $script:isClosing = $true
  try { if ($timer) { $timer.Stop() } } catch {}
  try { $tray.Visible = $false; $tray.Dispose() } catch {}
  try { $mutex.ReleaseMutex() | Out-Null } catch {}
  try { $mutex.Dispose() } catch {}
}
