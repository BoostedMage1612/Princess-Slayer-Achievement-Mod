# Slay the Princess Achievement Guide v0.2.3
# Installs only owned guide files. Original scripts and saves are never modified.
[CmdletBinding()]
param(
    [ValidateSet('Install','Uninstall','Troubleshoot')][string]$Mode = 'Install',
    [string]$GamePath = '',
    [switch]$NoOpen
)
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$Product = 'stp-achievement-guide'
$Root = $PSScriptRoot
$SourceName = 'zz_stp_achievement_guide.rpy'
$DataName = 'stp_guide_data.json'
$ReceiptPath = Join-Path $Root 'installation.json'
$Output = Join-Path $Root 'Output'
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Get-UniquePaths([string[]]$Paths) {
    # Windows paths are case-insensitive. Normalize separators and trailing slashes
    # before comparing registry, environment and Steam-library discoveries.
    $seen = New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    foreach ($path in $Paths) {
        if ([string]::IsNullOrWhiteSpace($path)) { continue }
        $normalized = [IO.Path]::GetFullPath($path.Trim().Trim('"').Replace([char]'\', [IO.Path]::DirectorySeparatorChar))
        $rootLength = [IO.Path]::GetPathRoot($normalized).Length
        while ($normalized.Length -gt $rootLength -and $normalized.EndsWith([string][IO.Path]::DirectorySeparatorChar)) {
            $normalized = $normalized.Substring(0, $normalized.Length - 1)
        }
        if ($seen.Add($normalized)) { $normalized }
    }
}

function Get-GameRoot([string]$Path) {
    if ([string]::IsNullOrWhiteSpace($Path)) { return $null }
    $Path = $Path.Trim().Trim('"')
    if (Test-Path -LiteralPath $Path -PathType Leaf) { $Path = Split-Path -Parent $Path }
    if ((Split-Path -Leaf $Path) -eq 'game') { $Path = Split-Path -Parent $Path }
    if (-not (Test-Path -LiteralPath (Join-Path $Path 'game') -PathType Container)) { return $null }
    $executables = @(Get-ChildItem -LiteralPath $Path -Filter '*.exe' -File -ErrorAction SilentlyContinue |
        Where-Object { $_.BaseName -match '(?i)slay.*princess' })
    if ($executables.Count -eq 0) { return $null }
    return (Get-Item -LiteralPath $Path).FullName
}

function Find-Game {
    if ($GamePath) {
        $chosen = Get-GameRoot $GamePath
        if (-not $chosen) { throw 'The selected folder must contain SlaythePrincess.exe and its game folder.' }
        return $chosen
    }
    if (Test-Path -LiteralPath $ReceiptPath) {
        try {
            $receipt = Get-Content -LiteralPath $ReceiptPath -Raw | ConvertFrom-Json
            if ($receipt.product -eq $Product) {
                $old = Get-GameRoot $receipt.game_root
                if ($old) { return $old }
            }
        } catch { }
    }
    $steamRoots = New-Object 'System.Collections.Generic.List[string]'
    foreach ($spec in @(@('HKCU:\Software\Valve\Steam','SteamPath'),
                         @('HKLM:\SOFTWARE\WOW6432Node\Valve\Steam','InstallPath'),
                         @('HKLM:\SOFTWARE\Valve\Steam','InstallPath'))) {
        try {
            $key = Get-ItemProperty -LiteralPath $spec[0] -ErrorAction Stop
            $value = $key.($spec[1])
            if ($value) { $steamRoots.Add([string]$value) }
        } catch { }
    }
    foreach ($base in @(${env:ProgramFiles(x86)}, $env:ProgramFiles)) {
        if ($base) { $steamRoots.Add((Join-Path $base 'Steam')) }
    }
    $libraries = New-Object 'System.Collections.Generic.List[string]'
    foreach ($steam in (Get-UniquePaths $steamRoots)) {
        $libraries.Add($steam)
        $vdf = Join-Path $steam 'steamapps/libraryfolders.vdf'
        if (Test-Path -LiteralPath $vdf) {
            $body = Get-Content -LiteralPath $vdf -Raw
            foreach ($match in [regex]::Matches($body, '"path"\s+"([^"]+)"')) {
                $libraries.Add($match.Groups[1].Value.Replace('\\','\'))
            }
            foreach ($match in [regex]::Matches($body, '"\d+"\s+"([A-Za-z]:[^\r\n"]+)"')) {
                $libraries.Add($match.Groups[1].Value.Replace('\\','\'))
            }
        }
    }
    $candidates = @()
    foreach ($library in (Get-UniquePaths $libraries)) {
        $manifest = Join-Path $library 'steamapps/appmanifest_1989270.acf'
        if (Test-Path -LiteralPath $manifest) {
            $content = Get-Content -LiteralPath $manifest -Raw
            $match = [regex]::Match($content, '"installdir"\s+"([^"]+)"')
            if ($match.Success) {
                $dir = $match.Groups[1].Value
                if ($dir -notmatch '[/\\]' -and $dir -ne '..') {
                    $candidate = Get-GameRoot (Join-Path (Join-Path $library 'steamapps/common') $dir)
                    if ($candidate) { $candidates += $candidate }
                }
            }
        }
    }
    $candidates = @(Get-UniquePaths $candidates)
    if ($candidates.Count -eq 1) { return $candidates[0] }
    if ($candidates.Count -gt 1) {
        Write-Host 'More than one installation was found:'
        for ($i=0; $i -lt $candidates.Count; $i++) { Write-Host ('{0}. {1}' -f ($i+1),$candidates[$i]) }
        $number = 0
        if ([int]::TryParse((Read-Host 'Choose installation number'), [ref]$number) -and $number -ge 1 -and $number -le $candidates.Count) {
            return $candidates[$number-1]
        }
        throw 'No installation was selected.'
    }
    Add-Type -AssemblyName System.Windows.Forms
    $dialog = New-Object System.Windows.Forms.FolderBrowserDialog
    $dialog.Description = 'Choose the Slay the Princess folder containing SlaythePrincess.exe. In Steam: Manage > Browse local files.'
    $dialog.ShowNewFolderButton = $false
    try {
        if ($dialog.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { throw 'No game folder selected.' }
        $chosen = Get-GameRoot $dialog.SelectedPath
    } finally { $dialog.Dispose() }
    if (-not $chosen) { throw 'That folder is not a Slay the Princess installation.' }
    return $chosen
}

function Assert-Closed([string]$GameRoot) {
    foreach ($process in @(Get-Process -ErrorAction SilentlyContinue)) {
        if ($process.ProcessName -match '(?i)slay.*princess') {
            throw 'Close Slay the Princess completely before installing or removing this guide mod.'
        }
        try { $path = $process.Path } catch { $path = $null }
        if ($path -and $path.StartsWith($GameRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
            throw 'A process is running from the game folder. Close the game, then retry.'
        }
    }
}

function Write-Atomic([string]$Path, [string]$Text) {
    $temp = $Path + '.' + [guid]::NewGuid().ToString('N') + '.tmp'
    try {
        [IO.File]::WriteAllText($temp, $Text, $Utf8)
        Move-Item -LiteralPath $temp -Destination $Path -Force
    } finally { if (Test-Path -LiteralPath $temp) { Remove-Item -LiteralPath $temp -Force } }
}

function Test-Marker([string]$Path, [string]$Pattern) {
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) { return $false }
    # ReadLines + Select-Object -First can leave the lazy reader open. On Windows
    # that prevents this installer from removing the very file it just checked.
    $reader = [IO.File]::OpenText($Path)
    try {
        $line = $reader.ReadLine()
        return ($null -ne $line -and $line -like $Pattern)
    } finally { $reader.Dispose() }
}
function Assert-FilesAvailable([string[]]$Paths) {
    # Detect a remaining lock before modifying any owned files. Close every
    # probe immediately; never hold handles across a replacement or removal.
    foreach ($path in $Paths) {
        if (-not (Test-Path -LiteralPath $path)) { continue }
        if (Test-Path -LiteralPath $path -PathType Container) {
            $files = @(Get-ChildItem -LiteralPath $path -Recurse -File -Force)
        } else { $files = @(Get-Item -LiteralPath $path) }
        foreach ($file in $files) {
            $stream = $null
            try {
                $stream = [IO.File]::Open($file.FullName, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::None)
            } catch {
                throw ('Cannot access guide file: ' + $file.FullName + "`nClose the game and other installer windows, then retry. No installation files have been changed yet.`n" + $_.Exception.Message)
            } finally { if ($null -ne $stream) { $stream.Dispose() } }
        }
    }
}
function Restore-ChangedFiles([string[]]$Changed, [string[]]$Existing, [string]$Backup) {
    $failures = New-Object 'System.Collections.Generic.List[string]'
    # Only restore paths whose modification was attempted. In particular, do not
    # delete an untouched, locked scanner while recovering an earlier operation.
    for ($index = $Changed.Count - 1; $index -ge 0; $index--) {
        $path = $Changed[$index]
        try {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
            if ($Existing -contains $path) {
                Copy-Item -LiteralPath (Join-Path $Backup (Split-Path -Leaf $path)) -Destination $path -Recurse
            }
        } catch { $failures.Add($path + ': ' + $_.Exception.Message) }
    }
    return $failures.ToArray()
}
function Assert-JsonOwner([string]$Path, [string]$Owner) {
    if (Test-Path -LiteralPath $Path) {
        $data = Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json
        if ($data.product -ne $Owner) { throw ('Unrecognized file left untouched: ' + $Path) }
    }
}
function Assert-PackageOwner([string]$Path) {
    if (Test-Path -LiteralPath $Path) {
        if (((Get-Item -LiteralPath $Path).Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'The guide package path is a link. It has been left untouched.'
        }
        if (-not (Test-Marker (Join-Path $Path 'OWNED_BY_STP_GUIDE.txt') 'stp-achievement-guide')) {
            throw 'An unrelated Python package uses the guide name. It has been left untouched.'
        }
    }
}
try {
    Write-Host 'Slay the Princess - Achievement Guide v0.2.3' -ForegroundColor Cyan
    $gameRoot = Find-Game
    $gameDir = Join-Path $gameRoot 'game'
    $installed = Join-Path $gameDir $SourceName
    $compiled = $installed + 'c'
    $dataFile = Join-Path $gameDir $DataName
    $packageParent = Join-Path $gameDir 'python-packages'
    $package = Join-Path $packageParent 'stp_guide'
    $scanSource = Join-Path $gameDir 'zz_stp_achievement_scan.rpy'
    $scanCompiled = $scanSource + 'c'
    $scanSettings = Join-Path $gameDir 'stp_guide_scan_settings.json'
    Write-Host ('Game: ' + $gameRoot)

    if ($Mode -eq 'Troubleshoot') {
        New-Item -ItemType Directory -Path $Output -Force | Out-Null
        $stamp = [DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_ffff')
        $stage = Join-Path $Output ('troubleshooting_' + $stamp)
        New-Item -ItemType Directory -Path $stage | Out-Null
        try {
            $summary = @('STP Achievement Guide v0.2.3',
                ('Guide source: ' + (Test-Path -LiteralPath $installed)),
                ('Guide compiled: ' + (Test-Path -LiteralPath $compiled)),
                ('Route database: ' + (Test-Path -LiteralPath $dataFile)),
                ('Guide package: ' + (Test-Path -LiteralPath $package)),
                ('Runtime diagnostics: ' + (Test-Path -LiteralPath (Join-Path $gameRoot 'stp_guide_diagnostics.json'))),
                ('PowerShell: ' + $PSVersionTable.PSVersion.ToString()))
            [IO.File]::WriteAllLines((Join-Path $stage 'summary.txt'),$summary,$Utf8)
            foreach ($name in @('traceback.txt','errors.txt','log.txt','stp_guide_diagnostics.json')) {
                $path = Join-Path $gameRoot $name
                if ((Test-Path -LiteralPath $path) -and (Get-Item -LiteralPath $path).Length -le 8MB) {
                    if ($name -eq 'stp_guide_diagnostics.json') {
                        try {
                            if ((Get-Item -LiteralPath $path).Length -gt 256KB) { continue }
                            $diagnosticHeader = Get-Content -LiteralPath $path -Raw | ConvertFrom-Json
                            if ($diagnosticHeader.product -ne $Product) { continue }
                        } catch { continue }
                    }
                    $body = [IO.File]::ReadAllText($path).Replace($gameRoot,'<GAME>')
                    if ($env:USERPROFILE) { $body = $body.Replace($env:USERPROFILE,'<USER>') }
                    $body = [regex]::Replace($body,'(?im)^.*(?:access[_ -]?token|auth(?:orization)?|password|steam[_ ]?id|account[_ ]?id).*$','<REDACTED LINE>')
                    [IO.File]::WriteAllText((Join-Path $stage $name),$body,$Utf8)
                }
            }
            $zip = Join-Path $Output ('UPLOAD_THIS_STP_Troubleshooting_' + $stamp + '.zip')
            Compress-Archive -Path (Join-Path $stage '*') -DestinationPath $zip
            Write-Host ('Upload this ZIP: ' + $zip) -ForegroundColor Green
            if (-not $NoOpen) { Start-Process explorer.exe -ArgumentList ('"' + $Output + '"') }
        } finally { Remove-Item -LiteralPath $stage -Recurse -Force }
        exit 0
    }

    Assert-Closed $gameRoot
    if ((Test-Path -LiteralPath $installed) -and -not (Test-Marker $installed '# STP Achievement Guide -- owned file,*')) {
        throw 'An unrelated file uses the guide filename. It has been left untouched.'
    }
    if ((Test-Path -LiteralPath $compiled) -and -not (Test-Marker $installed '# STP Achievement Guide -- owned file,*')) {
        throw 'An unrecognized compiled guide exists. It has been left untouched.'
    }
    Assert-JsonOwner $dataFile $Product
    Assert-PackageOwner $package
    if ($Mode -eq 'Uninstall') {
        Assert-FilesAvailable @($installed,$compiled,$dataFile,$package)
        foreach ($path in @($installed,$compiled,$dataFile,$package)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path -Recurse -Force }
        }
        Write-Host 'Guide removed. Original game files, achievements and saves were preserved.' -ForegroundColor Green
        exit 0
    }

    $source = Join-Path (Join-Path $Root 'mod') $SourceName
    $sourceData = Join-Path (Join-Path $Root 'mod') $DataName
    $sourcePackage = Join-Path (Join-Path (Join-Path $Root 'mod') 'python-packages') 'stp_guide'
    if (-not (Test-Marker $source '# STP Achievement Guide -- owned file,*')) { throw 'Extract the entire ZIP before running 1_Install_Guide.cmd.' }
    if (-not (Test-Path -LiteralPath $sourceData -PathType Leaf)) { throw 'The route database is missing. Extract the entire ZIP again.' }
    Assert-JsonOwner $sourceData $Product
    if (-not (Test-Path -LiteralPath $sourcePackage -PathType Container)) { throw 'The guide Python package is missing. Extract the entire ZIP again.' }
    Assert-PackageOwner $sourcePackage
    if ((Test-Path -LiteralPath $scanSource) -and -not (Test-Marker $scanSource '# STP Achievement Guide scanner -- owned file,*')) {
        throw 'An unrecognized scanner file exists. It has been left untouched.'
    }
    if ((Test-Path -LiteralPath $scanCompiled) -and -not (Test-Marker $scanSource '# STP Achievement Guide scanner -- owned file,*')) {
        throw 'An unrecognized compiled scanner exists. It has been left untouched.'
    }
    Assert-JsonOwner $scanSettings 'stp-achievement-guide-scan'
    Assert-JsonOwner $ReceiptPath $Product
    $targets = @($installed,$compiled,$dataFile,$package,$scanSource,$scanCompiled,$scanSettings,$ReceiptPath)
    Assert-FilesAvailable $targets
    $backup = Join-Path $Root ('Backups/' + [DateTime]::UtcNow.ToString('yyyyMMdd_HHmmss_ffff'))
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    $existing = @($targets | Where-Object { Test-Path -LiteralPath $_ })
    foreach ($path in $existing) { Copy-Item -LiteralPath $path -Destination $backup -Recurse }
    $changed = New-Object 'System.Collections.Generic.List[string]'
    try {
        New-Item -ItemType Directory -Path $packageParent -Force | Out-Null
        $changed.Add($dataFile)
        Write-Atomic $dataFile ([IO.File]::ReadAllText($sourceData))
        # A directory copy or removal can partially succeed before failing.
        $changed.Add($package)
        if (Test-Path -LiteralPath $package) { Remove-Item -LiteralPath $package -Recurse -Force }
        Copy-Item -LiteralPath $sourcePackage -Destination $package -Recurse
        $changed.Add($installed)
        Write-Atomic $installed ([IO.File]::ReadAllText($source))
        foreach ($path in @($compiled,$scanSource,$scanCompiled,$scanSettings)) {
            if (Test-Path -LiteralPath $path) {
                Remove-Item -LiteralPath $path -Force
                $changed.Add($path)
            }
        }
        $changed.Add($ReceiptPath)
        Write-Atomic $ReceiptPath (@{product=$Product;version='0.2.3';game_root=$gameRoot;backup=$backup} | ConvertTo-Json)
    } catch {
        $originalError = $_
        $recoveryFailures = @(Restore-ChangedFiles $changed $existing $backup)
        if ($recoveryFailures.Count -gt 0) {
            throw ('Installation failed: ' + $originalError.Exception.Message + "`nSome guide files could not be restored. Their backups are in: " + $backup + "`n" + ($recoveryFailures -join "`n"))
        }
        throw ('Installation failed: ' + $originalError.Exception.Message + "`nChanged guide files were restored to their previous state. Backup: " + $backup)
    }
    Write-Host ''
    Write-Host 'Installed. The old scan mod was replaced with the guide.' -ForegroundColor Green
    Write-Host '1. Launch Slay the Princess through Steam.'
    Write-Host '2. Press F8. Choose a recommended run, then Start this guided run.'
    Write-Host '3. Advance dialogue normally. Click the gold-highlighted choices yourself.'
    Write-Host 'F8 opens the guide; F9 hides or shows the small guide panel.'
    Write-Host 'No Python installation or administrator mode is normally needed.'
    exit 0
} catch {
    Write-Host ''
    Write-Host ('ERROR: ' + $_.Exception.Message) -ForegroundColor Red
    Write-Host 'Original story files and save files were not edited.'
    exit 1
}
