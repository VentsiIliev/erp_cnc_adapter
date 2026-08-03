param(
  [ValidateSet('Start', 'Update')]
  [string]$Mode = 'Start',
  [string]$LockPath = '',
  [string]$HealthUrl = '',
  [int]$TimeoutSeconds = 120
)

$ErrorActionPreference = 'SilentlyContinue'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Split-Path -Parent $scriptDir
$iconPath = Join-Path $installDir 'resources\logo.ico'
if ([string]::IsNullOrWhiteSpace($HealthUrl)) {
  $HealthUrl = 'http://127.0.0.1:8002/api/health'
}

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$window = New-Object System.Windows.Window
$window.Title = if ($Mode -eq 'Update') { 'ERP-CNC Update' } else { 'START-CNC' }
$window.Width = 420
$window.Height = 230
$window.WindowStartupLocation = 'CenterScreen'
$window.ResizeMode = 'NoResize'
$window.Topmost = $true
$window.ShowInTaskbar = $true
$window.Background = [System.Windows.Media.Brushes]::White

if (Test-Path -LiteralPath $iconPath) {
  try { $window.Icon = [System.Windows.Media.Imaging.BitmapFrame]::Create([Uri]::new($iconPath)) } catch {}
}

$root = New-Object System.Windows.Controls.Grid
$root.Margin = New-Object System.Windows.Thickness(24)
$root.RowDefinitions.Add((New-Object System.Windows.Controls.RowDefinition))
$root.RowDefinitions.Add((New-Object System.Windows.Controls.RowDefinition))
$root.RowDefinitions.Add((New-Object System.Windows.Controls.RowDefinition))
$root.RowDefinitions[0].Height = [System.Windows.GridLength]::Auto
$root.RowDefinitions[1].Height = [System.Windows.GridLength]::Auto
$root.RowDefinitions[2].Height = [System.Windows.GridLength]::Auto

$header = New-Object System.Windows.Controls.StackPanel
$header.Orientation = 'Horizontal'
$header.HorizontalAlignment = 'Center'
$header.Margin = New-Object System.Windows.Thickness(0, 2, 0, 18)

if (Test-Path -LiteralPath $iconPath) {
  $image = New-Object System.Windows.Controls.Image
  $image.Width = 48
  $image.Height = 48
  $image.Margin = New-Object System.Windows.Thickness(0, 0, 14, 0)
  try { $image.Source = [System.Windows.Media.Imaging.BitmapImage]::new([Uri]::new($iconPath)) } catch {}
  $header.Children.Add($image) | Out-Null
}

$title = New-Object System.Windows.Controls.TextBlock
$title.Text = if ($Mode -eq 'Update') { 'ERP-CNC Update' } else { 'ERP-CNC' }
$title.FontSize = 22
$title.FontWeight = 'SemiBold'
$title.VerticalAlignment = 'Center'
$title.Foreground = [System.Windows.Media.Brushes]::Black
$header.Children.Add($title) | Out-Null
[System.Windows.Controls.Grid]::SetRow($header, 0)
$root.Children.Add($header) | Out-Null

$status = New-Object System.Windows.Controls.TextBlock
$status.Text = if ($Mode -eq 'Update') { 'Updating CNC adapter...' } else { 'Starting CNC adapter...' }
$status.FontSize = 15
$status.TextAlignment = 'Center'
$status.Margin = New-Object System.Windows.Thickness(0, 0, 0, 16)
$status.Foreground = [System.Windows.Media.Brushes]::Black
[System.Windows.Controls.Grid]::SetRow($status, 1)
$root.Children.Add($status) | Out-Null

$progress = New-Object System.Windows.Controls.ProgressBar
$progress.IsIndeterminate = $true
$progress.Height = 12
$progress.Minimum = 0
$progress.Maximum = 100
[System.Windows.Controls.Grid]::SetRow($progress, 2)
$root.Children.Add($progress) | Out-Null

$window.Content = $root
$startedAt = Get-Date
$readyCount = 0
$lockSeen = $false

function Complete-Splash([string]$message, [int]$delayMs) {
  $status.Text = $message
  $progress.IsIndeterminate = $false
  $progress.Value = 100
  $timer.Stop()
  $closeTimer = New-Object System.Windows.Threading.DispatcherTimer
  $closeTimer.Interval = [TimeSpan]::FromMilliseconds($delayMs)
  $closeTimer.Add_Tick({ $closeTimer.Stop(); $window.Close() })
  $closeTimer.Start()
}

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(800)
$timer.Add_Tick({
  $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds

  if ($Mode -eq 'Update') {
    if (-not [string]::IsNullOrWhiteSpace($LockPath) -and (Test-Path -LiteralPath $LockPath)) {
      $script:lockSeen = $true
      $status.Text = ('Updating CNC adapter... {0}s' -f $elapsed)
      return
    }

    if ($script:lockSeen) {
      try {
        $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
        if ($health) {
          Complete-Splash 'Update complete. Adapter is ready.' 1400
          return
        }
      } catch {}
      if ($elapsed -ge $TimeoutSeconds) {
        Complete-Splash 'Update finished, but adapter is not reachable. Check update log.' 8000
        return
      }
      $status.Text = 'Update applied. Waiting for adapter...'
      return
    }

    $status.Text = ('Preparing update... {0}s' -f $elapsed)
    if ($elapsed -ge $TimeoutSeconds) {
      Complete-Splash 'Update is taking longer than expected. Check update log.' 8000
    }
    return
  }

  try {
    $health = Invoke-RestMethod -Uri $HealthUrl -TimeoutSec 1
    if ($health.cnc.connected -eq $true) {
      $script:readyCount++
      if ($script:readyCount -ge 2) {
        Complete-Splash 'CNC adapter is ready.' 900
      }
      return
    }
  } catch {}

  $script:readyCount = 0
  if ($elapsed -ge $TimeoutSeconds) {
    Complete-Splash 'Still starting. Check START-CNC log if needed.' 8000
    return
  }

  $status.Text = ('Starting CNC adapter... {0}s' -f $elapsed)
})

$timer.Start()
$window.ShowDialog() | Out-Null
