param(
    [Parameter(Mandatory=$true)]
    [string]$Version,

    [string[]]$Notes = @(),
    [string]$NotesFile = "",
    [string]$GitRemote = "origin",
    [string]$GitBranch = "main",
    [string]$SvnWorkingCopy = (Join-Path $env:USERPROFILE "Desktop\erp_cnc_adapter_svn"),
    [string]$SvnRoot = "https://192.168.2.101:8443/svn/2245_RouterRetrofit",
    [switch]$SkipBuild,
    [switch]$SkipGitPush,
    [switch]$SkipSvn,
    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path

function Show-Help {
    $scriptName = Split-Path -Leaf $PSCommandPath
    Write-Host ""
    Write-Host "Create and publish an ERP-CNC Adapter release."
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\util_scripts\$scriptName -Version 1.0.5 -Notes 'Added dashboard SVN credential settings'"
    Write-Host "  .\util_scripts\$scriptName -Version 1.0.5 -NotesFile .\release-notes.txt"
    Write-Host "  .\util_scripts\$scriptName -Version 1.0.5 -SkipSvn"
    Write-Host ""
    Write-Host "Behavior:"
    Write-Host "  1. Prompts for notes when -Notes/-NotesFile are omitted."
    Write-Host "  2. Updates version.py and prepends CHANGELOG.md."
    Write-Host "  3. Runs util_scripts\build.bat unless -SkipBuild is used."
    Write-Host "  4. Commits, tags, and pushes Git."
    Write-Host "  5. Mirrors Git HEAD to SVN trunk, updates trunk/release/latest.json, creates the SVN tag, and imports the ZIP/manifest."
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Version <x.y.z>          Release version, with or without leading v. Required."
    Write-Host "  -Notes <items>            One or more changelog bullets."
    Write-Host "  -NotesFile <path>         Text file with one release-note bullet per line."
    Write-Host "  -GitRemote <name>         Git remote. Default: origin."
    Write-Host "  -GitBranch <name>         Git branch to push. Default: main."
    Write-Host "  -SvnWorkingCopy <path>    Local SVN trunk checkout. Default: %USERPROFILE%\Desktop\erp_cnc_adapter_svn."
    Write-Host "  -SvnRoot <url>            SVN project root containing trunk/ and tags/."
    Write-Host "  -SkipBuild                Do not run the build script. Requires existing dist\dist_v<version>."
    Write-Host "  -SkipGitPush              Commit/tag locally but do not push Git."
    Write-Host "  -SkipSvn                  Do not mirror or publish SVN."
    Write-Host "  -Help, -h, --help         Show this help."
    Write-Host ""
}

if ($Help -or $Version -eq "--help" -or $Version -eq "-h" -or $Version -eq "/?") {
    Show-Help
    exit 0
}

function Invoke-Checked([string]$Command, [string[]]$Arguments, [string]$WorkingDirectory = $RepoRoot) {
    Push-Location $WorkingDirectory
    try {
        & $Command @Arguments
        if ($LASTEXITCODE -ne 0) {
            throw "$Command failed with exit code $LASTEXITCODE"
        }
    }
    finally {
        Pop-Location
    }
}

function Get-ReleaseNotes {
    if ($NotesFile) {
        return @(Get-Content -LiteralPath $NotesFile | Where-Object { -not [string]::IsNullOrWhiteSpace($_) })
    }
    if ($Notes.Count -gt 0) {
        return $Notes
    }

    Write-Host "Enter release notes, one per line. Submit an empty line when finished."
    $items = @()
    while ($true) {
        $line = Read-Host "Change"
        if ([string]::IsNullOrWhiteSpace($line)) { break }
        $items += $line.Trim()
    }
    if ($items.Count -eq 0) {
        throw "At least one release note is required."
    }
    return $items
}

function Set-VersionFile([string]$CleanVersion) {
    $versionPath = Join-Path $RepoRoot "version.py"
    $today = (Get-Date).ToString("yyyy-MM-dd")
    $text = Get-Content -LiteralPath $versionPath -Raw
    $text = [regex]::Replace($text, 'VERSION\s*=\s*"[^"]+"', "VERSION = `"$CleanVersion`"")
    $text = [regex]::Replace($text, 'BUILD_DATE\s*=\s*"[^"]+"', "BUILD_DATE = `"$today`"")
    Set-Content -LiteralPath $versionPath -Value $text -Encoding UTF8
}

function Update-Changelog([string]$TagVersion, [string[]]$ReleaseNotes) {
    $path = Join-Path $RepoRoot "CHANGELOG.md"
    $date = (Get-Date).ToString("yyyy-MM-dd")
    $body = "## $TagVersion - $date`r`n`r`n"
    foreach ($note in $ReleaseNotes) {
        $clean = $note.Trim().TrimStart("-", " ")
        $body += "- $clean`r`n"
    }
    $body += "`r`n"

    $existing = Get-Content -LiteralPath $path -Raw
    $marker = "All notable changes to ERP-CNC Adapter are documented here.`r`n`r`n"
    if ($existing.Contains($marker)) {
        $updated = $existing.Replace($marker, $marker + $body)
    } else {
        $updated = $body + $existing
    }
    Set-Content -LiteralPath $path -Value $updated -Encoding UTF8
}

function Mirror-ToSvnTrunk([string]$TagVersion) {
    if (-not (Test-Path -LiteralPath (Join-Path $SvnWorkingCopy ".svn"))) {
        throw "SVN working copy not found: $SvnWorkingCopy"
    }

    Invoke-Checked "svn" @("update", $SvnWorkingCopy)

    $archive = Join-Path $env:TEMP "erp-cnc-$TagVersion-git-head.zip"
    $exportDir = Join-Path $env:TEMP "erp-cnc-$TagVersion-git-head-export"
    Remove-Item -LiteralPath $archive -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $exportDir -Recurse -Force -ErrorAction SilentlyContinue
    Invoke-Checked "git" @("archive", "--format=zip", "--output=$archive", "HEAD")
    New-Item -ItemType Directory -Force $exportDir | Out-Null
    Expand-Archive -LiteralPath $archive -DestinationPath $exportDir -Force

    & robocopy $exportDir $SvnWorkingCopy /MIR /XD .svn /R:2 /W:1 | Out-Host
    if ($LASTEXITCODE -gt 7) {
        throw "robocopy failed with exit code $LASTEXITCODE"
    }

    $releaseDir = Join-Path $SvnWorkingCopy "release"
    New-Item -ItemType Directory -Force $releaseDir | Out-Null
    $latest = @{
        version = $TagVersion.TrimStart("v")
        package_url = "$SvnRoot/tags/$TagVersion/release/erp-cnc-adapter-update-$TagVersion.zip"
        manifest_url = "$SvnRoot/tags/$TagVersion/release/manifest.json"
    }
    $json = $latest | ConvertTo-Json -Depth 5
    [System.IO.File]::WriteAllText((Join-Path $releaseDir "latest.json"), $json + "`n", [System.Text.UTF8Encoding]::new($false))

    Push-Location $SvnWorkingCopy
    try {
        svn add --force . --depth infinity | Out-Host
        $statusLines = svn status
        foreach ($line in $statusLines) {
            if ($line.StartsWith("!")) {
                $missing = $line.Substring(8).Trim()
                if ($missing) { svn delete --force -- $missing | Out-Host }
            }
        }
        $statusLines = svn status | Where-Object { -not $_.Contains(".claude") -and -not $_.Contains("adapter.pid") }
        if ($statusLines) {
            svn commit -m "Mirror ERP-CNC Adapter $TagVersion"
            if ($LASTEXITCODE -ne 0) { throw "svn commit failed with exit code $LASTEXITCODE" }
        } else {
            Write-Host "No SVN trunk changes to commit."
        }
    }
    finally {
        Pop-Location
    }
}

function Publish-SvnRelease([string]$TagVersion) {
    $tagUrl = "$SvnRoot/tags/$TagVersion"
    svn copy "$SvnRoot/trunk" $tagUrl -m "Tag ERP-CNC Adapter $TagVersion"
    if ($LASTEXITCODE -ne 0) { throw "svn copy tag failed with exit code $LASTEXITCODE" }

    $distDir = Join-Path $RepoRoot "dist\dist_$TagVersion"
    $manifest = Join-Path $distDir "manifest.json"
    $zip = Join-Path $distDir "erp-cnc-adapter-update-$TagVersion.zip"
    if (-not (Test-Path -LiteralPath $manifest)) { throw "Missing release manifest: $manifest" }
    if (-not (Test-Path -LiteralPath $zip)) { throw "Missing release ZIP: $zip" }

    svn import $manifest "$tagUrl/release/manifest.json" -m "Add $TagVersion update manifest"
    if ($LASTEXITCODE -ne 0) { throw "svn import manifest failed with exit code $LASTEXITCODE" }
    svn import $zip "$tagUrl/release/erp-cnc-adapter-update-$TagVersion.zip" -m "Add $TagVersion update package ZIP"
    if ($LASTEXITCODE -ne 0) { throw "svn import ZIP failed with exit code $LASTEXITCODE" }
}

$cleanVersion = $Version.Trim().TrimStart("v")
$tagVersion = "v$cleanVersion"
$releaseNotes = Get-ReleaseNotes

if (-not (Test-Path -LiteralPath (Join-Path $RepoRoot ".git"))) {
    throw "Git repo not found: $RepoRoot"
}

Write-Host "Preparing release $tagVersion..."
Set-VersionFile $cleanVersion
Update-Changelog $tagVersion $releaseNotes

if (-not $SkipBuild) {
    $env:BUILD_NO_PAUSE = "1"
    Invoke-Checked (Join-Path $RepoRoot "util_scripts\build.bat") @()
}

$distDir = Join-Path $RepoRoot "dist\dist_$tagVersion"
if (-not (Test-Path -LiteralPath (Join-Path $distDir "erp-cnc-adapter-update-$tagVersion.zip"))) {
    throw "Release ZIP not found after build: $distDir"
}
if (-not (Test-Path -LiteralPath (Join-Path $distDir "manifest.json"))) {
    throw "Manifest not found after build: $distDir"
}

Invoke-Checked "git" @("add", "-A")
& git reset -- adapter.pid config.json | Out-Null
$staged = git diff --cached --name-only
if (-not $staged) {
    throw "No Git changes staged for release."
}
Invoke-Checked "git" @("commit", "-m", "Release $tagVersion")
Invoke-Checked "git" @("tag", $tagVersion)

if (-not $SkipGitPush) {
    Invoke-Checked "git" @("push", $GitRemote, $GitBranch)
    Invoke-Checked "git" @("push", $GitRemote, $tagVersion)
}

if (-not $SkipSvn) {
    Mirror-ToSvnTrunk $tagVersion
    Publish-SvnRelease $tagVersion
}

Write-Host "Release complete: $tagVersion"
Write-Host "Package: $distDir"
