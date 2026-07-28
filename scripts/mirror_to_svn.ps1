param(
    [string]$Version = "",

    [string]$GitRepo = (Resolve-Path (Join-Path $PSScriptRoot "..")).Path,
    [string]$SvnWorkingCopy = (Join-Path $env:USERPROFILE "Desktop\erp_cnc_adapter_svn"),
    [string]$SvnRoot = "https://192.168.2.101:8443/svn/2245_RouterRetrofit",
    [switch]$SkipTag,
    [Alias("h")]
    [switch]$Help
)

$ErrorActionPreference = "Stop"

function Show-Help {
    $scriptName = Split-Path -Leaf $PSCommandPath
    Write-Host ""
    Write-Host "Mirror ERP-CNC Adapter from Git to the company SVN repository."
    Write-Host ""
    Write-Host "Usage:"
    Write-Host "  .\scripts\$scriptName -Version v1.0.1"
    Write-Host "  .\scripts\$scriptName -Version v1.0.1 -SkipTag"
    Write-Host "  .\scripts\$scriptName --help"
    Write-Host ""
    Write-Host "Options:"
    Write-Host "  -Version <version>       Release/version label used for SVN commit and tag, for example v1.0.1. Required unless -Help is used."
    Write-Host "  -GitRepo <path>          Source Git working copy. Defaults to the repo root above this script."
    Write-Host "  -SvnWorkingCopy <path>   Local SVN trunk checkout to mirror into. Defaults to %USERPROFILE%\Desktop\erp_cnc_adapter_svn."
    Write-Host "  -SvnRoot <url>           SVN project root containing trunk/ and tags/. Defaults to the 2245_RouterRetrofit repo."
    Write-Host "  -SkipTag                 Commit SVN trunk only; do not create /tags/<version>. Use this for non-release mirrors."
    Write-Host "  -Help, -h, --help        Show this help and exit without copying, committing, or tagging."
    Write-Host ""
    Write-Host "Behavior:"
    Write-Host "  The file list is computed by Git each run using .gitignore rules. Ignored files such as logs, .venv, dist, build, config.json, and IDE files are not mirrored."
    Write-Host "  The script clears the SVN working copy except .svn, copies the Git-selected files, runs svn add/delete, commits trunk, then optionally creates an SVN tag."
    Write-Host ""
    Write-Host "Examples:"
    Write-Host "  .\scripts\$scriptName -Version v1.0.1"
    Write-Host "  .\scripts\$scriptName -Version v1.0.1 -SkipTag"
    Write-Host "  .\scripts\$scriptName -Version v1.0.1 -SvnWorkingCopy 'C:\Users\Notebook 1\Desktop\erp_cnc_adapter_svn'"
    Write-Host ""
}

if ($Help -or $Version -eq "--help" -or $Version -eq "-h" -or $Version -eq "/?") {
    Show-Help
    exit 0
}

if ([string]::IsNullOrWhiteSpace($Version)) {
    Show-Help
    throw "-Version is required unless -Help/--help is used."
}

function Invoke-Checked($Command, [string[]]$Arguments) {
    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Get-RelativePath([string]$BasePath, [string]$Path) {
    $baseUri = [Uri]((Resolve-Path $BasePath).Path.TrimEnd('\') + '\')
    $pathUri = [Uri]((Resolve-Path $Path).Path)
    return [Uri]::UnescapeDataString($baseUri.MakeRelativeUri($pathUri).ToString()).Replace('/', '\')
}

function Remove-DirectoryContentsExceptSvn([string]$Path) {
    Get-ChildItem -LiteralPath $Path -Force | Where-Object { $_.Name -ne ".svn" } | ForEach-Object {
        Remove-Item -LiteralPath $_.FullName -Recurse -Force
    }
}

if (-not (Test-Path -LiteralPath (Join-Path $GitRepo ".git"))) {
    throw "Git repo not found: $GitRepo"
}
if (-not (Test-Path -LiteralPath (Join-Path $SvnWorkingCopy ".svn"))) {
    throw "SVN working copy not found: $SvnWorkingCopy"
}

Write-Host "Collecting files from Git repo using .gitignore rules..."
Push-Location $GitRepo
try {
    $raw = git ls-files -z --cached --others --exclude-standard
    if ($LASTEXITCODE -ne 0) {
        throw "git ls-files failed with exit code $LASTEXITCODE"
    }

    $files = @()
    foreach ($file in ($raw -split "`0")) {
        if (-not $file) { continue }

        # --no-index makes Git apply ignore rules even if a file was accidentally tracked.
        git check-ignore --no-index -q -- $file
        if ($LASTEXITCODE -eq 0) { continue }
        if ($LASTEXITCODE -ne 1) {
            throw "git check-ignore failed for $file with exit code $LASTEXITCODE"
        }

        $fullPath = Join-Path $GitRepo $file
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $files += $file
        }
    }
}
finally {
    Pop-Location
}

Write-Host ("Copying {0} files to SVN working copy..." -f $files.Count)
Remove-DirectoryContentsExceptSvn $SvnWorkingCopy

foreach ($file in $files) {
    $source = Join-Path $GitRepo $file
    $dest = Join-Path $SvnWorkingCopy $file
    $destDir = Split-Path -Parent $dest
    if (-not (Test-Path -LiteralPath $destDir)) {
        New-Item -ItemType Directory -Path $destDir -Force | Out-Null
    }
    Copy-Item -LiteralPath $source -Destination $dest -Force
}

Push-Location $SvnWorkingCopy
try {
    Write-Host "Adding new SVN files..."
    svn add --force . --depth infinity | Out-Host

    Write-Host "Scheduling removed SVN files..."
    $statusLines = svn status
    foreach ($line in $statusLines) {
        if ($line.StartsWith("!")) {
            $path = $line.Substring(8).Trim()
            if ($path) {
                svn delete --force -- $path | Out-Host
            }
        }
    }

    $statusLines = svn status
    if ($statusLines) {
        Write-Host "Committing SVN trunk..."
        svn commit -m "Mirror ERP-CNC Adapter $Version"
    } else {
        Write-Host "No SVN trunk changes to commit."
    }

    if (-not $SkipTag) {
        $tagUrl = "$SvnRoot/tags/$Version"
        Write-Host "Creating SVN tag $tagUrl ..."
        svn copy "$SvnRoot/trunk" $tagUrl -m "Tag $Version"
    }

    Write-Host "SVN mirror complete: $Version"
}
finally {
    Pop-Location
}
