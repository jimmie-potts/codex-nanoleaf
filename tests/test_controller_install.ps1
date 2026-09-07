param([string]$ScratchRoot = (Join-Path $PSScriptRoot '../test-results/controller-install'))
# Exercise upgrade copying against temporary Windows state. Process launch is replaced.
$ErrorActionPreference = 'Stop'
$source = (Resolve-Path (Join-Path $PSScriptRoot '../bridge')).Path
New-Item -ItemType Directory -Force -Path $ScratchRoot | Out-Null
$fixture = Join-Path (Resolve-Path $ScratchRoot).Path ([guid]::NewGuid().ToString('N'))
$destination = Join-Path $fixture 'CodexNanoleaf'
New-Item -ItemType Directory -Path $destination | Out-Null
Set-Content -LiteralPath (Join-Path $destination 'config.json') -Value '{"token":"synthetic-private-token"}'
Set-Content -LiteralPath (Join-Path $destination 'scene-state.json') -Value '{"fixture":"preserve-scene"}'
# Replace child Python with a fixture runtime. Python behavior has its own tests.
$runtime = Join-Path $fixture 'fixture-python.ps1'
@'
param([string]$Script, [string]$Source, [string]$Destination)
if ($Script -like '*backup_install.py') {
    foreach ($name in @('config.json','scene-state.json')) { Copy-Item (Join-Path $Source $name) $Destination }
} elseif ($Script -like '*controller_contract.py') {
    $root = Join-Path (Split-Path $Script) 'vendor/device-contracts-1.0.0'
    $archive = Join-Path $root 'jimmie-potts-device-contracts-1.0.0.tgz'
    if ((Get-FileHash $archive -Algorithm SHA256).Hash.ToLower() -ne '5e0b30ac92e6e8e1e38d8249b740b565de66e3cc810a04bc6fac23e182e84e87') { throw 'Fixture artifact verification failed.' }
} else { throw 'Unexpected fixture Python invocation.' }
$global:LASTEXITCODE = 0
'@ | Set-Content -LiteralPath $runtime
$previousLocalAppData = $env:LOCALAPPDATA
$global:NanoleafFixtureLaunches = @()
function Get-CimInstance { param($ClassName) return @() }
function Stop-Process { throw 'The fixture must not stop any real process.' }
function Start-Process {
    param($FilePath,$ArgumentList,[switch]$PassThru,$WindowStyle)
    $global:NanoleafFixtureLaunches += [string]$FilePath
    $exitCode = 0
    if ($ArgumentList -match 'backup_install.py') {
        $arguments = @([regex]::Matches($ArgumentList, '"([^"]*)"') | ForEach-Object { $_.Groups[1].Value })
        & $FilePath @arguments
        $exitCode = if ($null -eq $LASTEXITCODE) { 0 } else { $LASTEXITCODE }
    }
    $process = [pscustomobject]@{ExitCode=$exitCode}
    Add-Member -InputObject $process -MemberType ScriptMethod -Name WaitForExit -Value {}
    if ($PassThru) { return $process }
}
try {
    $env:LOCALAPPDATA = $fixture
    & (Join-Path $source 'install-modes.ps1') -SkipShortcuts -PythonRuntime $runtime
    foreach ($name in @('controller_state.py','controller_contract.py','controller_server.py','requirements-controller.txt','bridge.py')) {
        if (-not (Test-Path (Join-Path $destination $name))) { throw "Missing installed source asset $name" }
    }
    if (-not (Test-Path (Join-Path $destination 'vendor/device-contracts-1.0.0/package/manifest.json'))) { throw 'Missing verified artifact.' }
    if ((Get-Content -Raw (Join-Path $destination 'config.json')) -notmatch 'synthetic-private-token') { throw 'Private configuration changed.' }
    if ((Get-Content -Raw (Join-Path $destination 'scene-state.json')) -notmatch 'preserve-scene') { throw 'Scene state changed.' }
    $backup = @(Get-ChildItem -Directory $destination -Filter 'backup-wall-map-*')
    if ($backup.Count -ne 1 -or -not (Test-Path (Join-Path $backup[0].FullName 'config.json'))) { throw 'Private state backup missing.' }
    if ($global:NanoleafFixtureLaunches.Count -ne 2) { throw 'Unexpected process launch request.' }
    Write-Output 'Controller source upgrade fixture passed; no personal installation or process launch occurred.'
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
    Remove-Item -Recurse -Force -LiteralPath $fixture
}
