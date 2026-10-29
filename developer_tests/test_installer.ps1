# Optional developer regression checks. Uses temporary copies and a fake game;
# never installs into Steam or launches the game. No extra modules required.
[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0
$kit = Split-Path -Parent $PSScriptRoot
$setupSource = Join-Path $kit 'Setup.ps1'
$engine = Join-Path $PSHOME 'powershell.exe'
if ($PSVersionTable.PSVersion.Major -ge 6) {
    $engine = Join-Path $PSHOME 'pwsh.exe'
    if (-not (Test-Path -LiteralPath $engine)) { $engine = Join-Path $PSHOME 'pwsh' }
}
$tempRoot = Join-Path ([IO.Path]::GetTempPath()) ('stp_installer_test_' + [guid]::NewGuid().ToString('N'))
$Utf8 = New-Object System.Text.UTF8Encoding($false)

function Check([bool]$Condition, [string]$Message) {
    if (-not $Condition) { throw $Message }
}
function Assert-Released([string]$Path) {
    $probe = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::ReadWrite, [IO.FileShare]::None)
    $probe.Dispose()
}
function Invoke-Setup([string]$Mode, [int]$ExpectedExit) {
    $output = & $engine -NoProfile -ExecutionPolicy Bypass -File $setup -Mode $Mode -GamePath $gameRoot -NoOpen 2>&1 | Out-String
    Check ($LASTEXITCODE -eq $ExpectedExit) ('Unexpected installer result: ' + $output)
    return $output
}
function Get-TreeDigest([string]$Path) {
    $rows = @(Get-ChildItem -LiteralPath $Path -Recurse -File | Sort-Object FullName | ForEach-Object {
        $_.FullName.Substring($Path.Length) + ' ' + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash
    })
    return ($rows -join "`n")
}

try {
    New-Item -ItemType Directory -Path $tempRoot | Out-Null
    $tokens = $null
    $parseErrors = $null
    $ast = [Management.Automation.Language.Parser]::ParseFile($setupSource, [ref]$tokens, [ref]$parseErrors)
    Check ($parseErrors.Count -eq 0) 'Setup.ps1 has syntax errors.'
    # Load only pure helper functions, never the installer's main body.
    foreach ($name in @('Get-UniquePaths','Test-Marker','Assert-FilesAvailable','Restore-ChangedFiles')) {
        $node = $ast.Find({ param($item) $item -is [Management.Automation.Language.FunctionDefinitionAst] -and $item.Name -eq $name }, $false)
        Check ($null -ne $node) ('Missing function: ' + $name)
        . ([scriptblock]::Create($node.Extent.Text))
    }

    $marker = Join-Path $tempRoot 'marker [literal].rpy'
    [IO.File]::WriteAllText($marker, "# STP Achievement Guide scanner -- owned file, version 0.1.0`nsecond line`n")
    for ($i = 0; $i -lt 20; $i++) {
        Check (Test-Marker $marker '# STP Achievement Guide scanner -- owned file,*') 'Marker was not recognized.'
        Assert-Released $marker
    }
    Check (-not (Test-Marker $marker 'unrelated')) 'Wrong marker was accepted.'
    Assert-Released $marker
    [IO.File]::WriteAllText($marker, '')
    Check (-not (Test-Marker $marker '*')) 'Empty marker was accepted.'
    Assert-Released $marker
    Remove-Item -LiteralPath $marker
    Check (-not (Test-Marker $marker '*')) 'Missing marker was accepted.'
    Write-Host 'PASS: marker reads release handles immediately (matching, nonmatching, empty, missing).'

    $first = Join-Path $tempRoot 'Steam/steamapps/common/Slay the Princess'
    $different = Join-Path $tempRoot 'OtherSteam/steamapps/common/Slay the Princess'
    $paths = @(Get-UniquePaths @($first, $first.ToUpperInvariant(), ($first + '/'), ($first + '/.'), $first.Replace('/', '\'), $different))
    Check ($paths.Count -eq 2) 'Case/separator/trailing-slash variants were not deduplicated.'
    Check ($paths[0] -eq [IO.Path]::GetFullPath($first)) 'Discovery order changed.'
    Check (@(Get-UniquePaths @()).Count -eq 0) 'Empty path list is not empty.'
    $rootPath = [IO.Path]::GetPathRoot([IO.Path]::GetFullPath($first))
    Check ((@(Get-UniquePaths @($rootPath)))[0] -eq $rootPath) 'Drive root was damaged.'
    Write-Host 'PASS: Windows-style path deduplication preserves distinct installations and drive roots.'

    $testKit = Join-Path $tempRoot 'kit'
    New-Item -ItemType Directory -Path $testKit | Out-Null
    Copy-Item -LiteralPath $setupSource -Destination $testKit
    Copy-Item -LiteralPath (Join-Path $kit 'mod') -Destination $testKit -Recurse
    $setup = Join-Path $testKit 'Setup.ps1'
    $gameRoot = Join-Path $tempRoot 'fake game'
    $game = Join-Path $gameRoot 'game'
    New-Item -ItemType Directory -Path (Join-Path $game 'saves') -Force | Out-Null
    [IO.File]::WriteAllText((Join-Path $gameRoot 'SlaythePrincess.exe'), 'Fake test fixture. Never launched.')
    [IO.File]::WriteAllText((Join-Path $game 'original.rpy'), 'original preserved')
    [IO.File]::WriteAllText((Join-Path $game 'saves/test.save'), 'save preserved')
    $scan = Join-Path $game 'zz_stp_achievement_scan.rpy'
    $scanText = "# STP Achievement Guide scanner -- owned file, version 0.1.0`nsecond line`n"
    [IO.File]::WriteAllText($scan, $scanText)
    [IO.File]::WriteAllText(($scan + 'c'), 'old compiled scanner')
    [IO.File]::WriteAllText((Join-Path $game 'stp_guide_scan_settings.json'), '{"product":"stp-achievement-guide-scan"}')

    $before = Get-TreeDigest $gameRoot
    $held = [IO.File]::Open($scan, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        $failed = $false
        try { Assert-FilesAvailable @($scan) } catch { $failed = $_.Exception.Message -like '*No installation files have been changed yet*' }
        Check $failed 'An external read lock was not detected.'
        $output = Invoke-Setup 'Install' 1
        Check ($output -like '*No installation files have been changed yet*') 'Locked install did not stop before modification.'
        Check ((Get-TreeDigest $gameRoot) -eq $before) 'Locked install changed game files.'
        Check (-not (Test-Path -LiteralPath (Join-Path $testKit 'Backups'))) 'Locked install reached the modification stage.'
    } finally { $held.Dispose() }
    Assert-FilesAvailable @($game)
    Assert-Released $scan
    Write-Host 'PASS: locked files stop installation before changes; lock probes release their handles.'

    $null = Invoke-Setup 'Install' 0
    Check (-not (Test-Path -LiteralPath $scan)) 'Scanner was not removed.'
    Check (-not (Test-Path -LiteralPath ($scan + 'c'))) 'Compiled scanner was not removed.'
    $controller = Join-Path $game 'python-packages/stp_guide/controller.py'
    Check (Test-Path -LiteralPath $controller) 'Guide package missing.'
    $receiptPath = Join-Path $testKit 'installation.json'
    $receipt = Get-Content -LiteralPath $receiptPath -Raw | ConvertFrom-Json
    Check ($receipt.version -eq '0.2.3') 'Wrong installer version in receipt.'
    Check ([IO.File]::ReadAllText((Join-Path $receipt.backup (Split-Path -Leaf $scan))) -eq $scanText) 'Scanner backup does not match.'
    $null = Invoke-Setup 'Install' 0
    Write-Host 'PASS: scanner migration, backups and repeat installation.'

    # Fail the final write after both guide replacement and scanner removal.
    # All original bytes must come back, including the installation receipt.
    [IO.File]::WriteAllText($scan, $scanText)
    [IO.File]::WriteAllText(($scan + 'c'), 'compiled scanner before failed upgrade')
    $before = Get-TreeDigest $gameRoot
    $receiptBefore = [IO.File]::ReadAllText($receiptPath)
    $cleanSetup = [IO.File]::ReadAllText($setup)
    $needle = 'function Write-Atomic([string]$Path, [string]$Text) {'
    $fault = $needle + "`n" + '    if ((Split-Path -Leaf $Path) -eq "installation.json") { throw "INJECTED FINAL WRITE FAILURE" }'
    Check ($cleanSetup.Contains($needle)) 'Fault-injection location missing.'
    [IO.File]::WriteAllText($setup, $cleanSetup.Replace($needle, $fault), $Utf8)
    $output = Invoke-Setup 'Install' 1
    Check ($output -like '*INJECTED FINAL WRITE FAILURE*') 'Injected failure was not reported.'
    Check ($output -like '*restored to their previous state*') 'Recovery was not reported.'
    Check ((Get-TreeDigest $gameRoot) -eq $before) 'Failed upgrade did not restore the previous game files.'
    Check ([IO.File]::ReadAllText($receiptPath) -eq $receiptBefore) 'Failed upgrade changed the receipt.'
    [IO.File]::WriteAllText($setup, $cleanSetup, $Utf8)
    $null = Invoke-Setup 'Install' 0
    Write-Host 'PASS: a failure after scanner removal restores prior guide/scanner files and receipt; retry succeeds.'

    [IO.File]::WriteAllText((Join-Path $gameRoot 'log.txt'), "Game test log`npassword=should-be-redacted")
    [IO.File]::WriteAllText((Join-Path $gameRoot 'stp_guide_diagnostics.json'), '{"product":"stp-achievement-guide","version":"0.2.3","events":[{"event":"menu","location":{"file":"scripts/ch_1/script.rpy","line":1498,"compiled":true}}]}')
    $null = Invoke-Setup 'Troubleshoot' 0
    $archives = @(Get-ChildItem -LiteralPath (Join-Path $testKit 'Output') -Filter '*.zip')
    Check ($archives.Count -eq 1) 'Troubleshooting ZIP missing.'
    $logs = Join-Path $tempRoot 'logs'
    Expand-Archive -LiteralPath $archives[0].FullName -DestinationPath $logs
    Check ([IO.File]::ReadAllText((Join-Path $logs 'log.txt')) -notlike '*should-be-redacted*') 'Sensitive log line was not removed.'
    $runtimeReport = Get-Content -LiteralPath (Join-Path $logs 'stp_guide_diagnostics.json') -Raw | ConvertFrom-Json
    Check ($runtimeReport.events[0].location.compiled -eq $true) 'Runtime location diagnostics were not collected.'
    $null = Invoke-Setup 'Uninstall' 0
    Check (-not (Test-Path -LiteralPath $controller)) 'Guide package was not removed.'
    $guideSource = Join-Path $game 'zz_stp_achievement_guide.rpy'
    Check (-not (Test-Path -LiteralPath $guideSource)) 'Guide source was not removed.'
    Check ([IO.File]::ReadAllText((Join-Path $game 'original.rpy')) -eq 'original preserved') 'Original story file changed.'
    Check ([IO.File]::ReadAllText((Join-Path $game 'saves/test.save')) -eq 'save preserved') 'Save fixture changed.'
    [IO.File]::WriteAllText($guideSource, 'UNRELATED')
    $null = Invoke-Setup 'Install' 1
    Check ([IO.File]::ReadAllText($guideSource) -eq 'UNRELATED') 'Unrelated collision file changed.'
    Write-Host 'PASS: diagnostics, log redaction, uninstall, original/save preservation and collision refusal.'
    Write-Host 'All installer regression checks passed.' -ForegroundColor Green
} finally {
    if (Test-Path -LiteralPath $tempRoot) { Remove-Item -LiteralPath $tempRoot -Recurse -Force }
}
