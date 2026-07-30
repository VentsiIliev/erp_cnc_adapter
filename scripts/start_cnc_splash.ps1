$ErrorActionPreference = 'SilentlyContinue'

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$installDir = Split-Path -Parent $scriptDir
$iconPath = Join-Path $installDir 'resources\logo.ico'
$healthUrl = 'http://127.0.0.1:8002/api/health'
$timeoutSeconds = 120

Add-Type -AssemblyName PresentationFramework
Add-Type -AssemblyName PresentationCore
Add-Type -AssemblyName WindowsBase

$window = New-Object System.Windows.Window
$window.Title = 'START-CNC'
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
$title.Text = 'ERP-CNC'
$title.FontSize = 22
$title.FontWeight = 'SemiBold'
$title.VerticalAlignment = 'Center'
$title.Foreground = [System.Windows.Media.Brushes]::Black
$header.Children.Add($title) | Out-Null
[System.Windows.Controls.Grid]::SetRow($header, 0)
$root.Children.Add($header) | Out-Null

$status = New-Object System.Windows.Controls.TextBlock
$status.Text = 'Starting CNC adapter...'
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

$timer = New-Object System.Windows.Threading.DispatcherTimer
$timer.Interval = [TimeSpan]::FromMilliseconds(800)
$timer.Add_Tick({
  $elapsed = [int]((Get-Date) - $startedAt).TotalSeconds
  try {
    $health = Invoke-RestMethod -Uri $healthUrl -TimeoutSec 1
    if ($health.cnc.connected -eq $true) {
      $script:readyCount++
      $status.Text = 'CNC adapter is ready.'
      $progress.IsIndeterminate = $false
      $progress.Value = 100
      if ($script:readyCount -ge 2) {
        $timer.Stop()
        $closeTimer = New-Object System.Windows.Threading.DispatcherTimer
        $closeTimer.Interval = [TimeSpan]::FromMilliseconds(900)
        $closeTimer.Add_Tick({ $closeTimer.Stop(); $window.Close() })
        $closeTimer.Start()
      }
      return
    }
  } catch {}

  $script:readyCount = 0
  if ($elapsed -ge $timeoutSeconds) {
    $status.Text = 'Still starting. Check START-CNC log if needed.'
    $progress.IsIndeterminate = $false
    $progress.Value = 100
    $timer.Stop()
    $closeTimer = New-Object System.Windows.Threading.DispatcherTimer
    $closeTimer.Interval = [TimeSpan]::FromSeconds(8)
    $closeTimer.Add_Tick({ $closeTimer.Stop(); $window.Close() })
    $closeTimer.Start()
    return
  }

  $status.Text = ('Starting CNC adapter... {0}s' -f $elapsed)
})

$timer.Start()
$window.ShowDialog() | Out-Null
