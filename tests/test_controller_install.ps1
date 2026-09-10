param([string]$ScratchRoot = (Join-Path $PSScriptRoot '../test-results/controller-install'),
      [ValidateSet('fixed','default','unrelated','invalid')][string]$ListenerCase = 'fixed')
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
function Get-CimInstance {
    param($ClassName)
    $arguments = switch ($ListenerCase) { 'fixed' { '--port 43210' }; 'default' { '' }; 'unrelated' { '--port 43210' }; 'invalid' { '--port 99999' } }
    $script = if ($ListenerCase -eq 'unrelated') { Join-Path $fixture 'other-install/bridge.py' } else { Join-Path $destination 'bridge.py' }
    return @([pscustomobject]@{Name='python.exe'; ProcessId=987654321; CommandLine=('python.exe "' + $script + '" controller-serve ' + $arguments)})
}
function Stop-Process { param($Id,[switch]$Force) if ($Id -ne 987654321) { throw 'The fixture must not stop any real process.' } }
function Start-Process {
    param($FilePath,$ArgumentList,[switch]$PassThru,$WindowStyle)
    $global:NanoleafFixtureLaunches += [pscustomobject]@{FilePath=$FilePath; ArgumentList=$ArgumentList}
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
    if ($ListenerCase -eq 'invalid') {
        try {
            & (Join-Path $source 'install-modes.ps1') -SkipShortcuts -PythonRuntime $runtime
            throw 'Invalid port was accepted.'
        } catch {
            if ($_.Exception.Message -ne 'Invalid active controller port. Upgrade restart stopped.') { throw }
        }
        if ($global:NanoleafFixtureLaunches.Count -ne 1) { throw 'Invalid listener was restarted.' }
        Write-Output 'Invalid listener port rejected without a process restart.'
        return
    }
    & (Join-Path $source 'install-modes.ps1') -SkipShortcuts -PythonRuntime $runtime
    foreach ($name in @('controller_state.py','controller_contract.py','controller_server.py','requirements-controller.txt','bridge.py','wall.html','prism.js','prism-adapters.js','prism-labels.js')) {
        if (-not (Test-Path (Join-Path $destination $name))) { throw "Missing installed source asset $name" }
    }
    foreach ($name in @('wall.html','prism.js','prism-adapters.js','prism-labels.js')) {
        if ((Get-FileHash (Join-Path $source $name)).Hash -ne (Get-FileHash (Join-Path $destination $name)).Hash) { throw "Installed wall asset differs: $name" }
    }
    if (-not (Test-Path (Join-Path $destination 'vendor/device-contracts-1.0.0/package/manifest.json'))) { throw 'Missing verified artifact.' }
    if ((Get-Content -Raw (Join-Path $destination 'config.json')) -notmatch 'synthetic-private-token') { throw 'Private configuration changed.' }
    if ((Get-Content -Raw (Join-Path $destination 'scene-state.json')) -notmatch 'preserve-scene') { throw 'Scene state changed.' }
    $backup = @(Get-ChildItem -Directory $destination -Filter 'backup-wall-map-*')
    if ($backup.Count -ne 1 -or -not (Test-Path (Join-Path $backup[0].FullName 'config.json'))) { throw 'Private state backup missing.' }
    $expectedLaunches = if ($ListenerCase -eq 'unrelated') { 2 } else { 3 }
    if ($global:NanoleafFixtureLaunches.Count -ne $expectedLaunches) { throw 'Unexpected process launch request.' }
    $restart = @($global:NanoleafFixtureLaunches | Where-Object { $_.ArgumentList -match 'controller-serve' })
    if ($ListenerCase -eq 'unrelated') {
        if ($restart.Count -ne 0) { throw 'Another installation was restarted.' }
    } else {
        $expectedPort = if ($ListenerCase -eq 'fixed') { 43210 } else { 0 }
        if ($restart.Count -ne 1 -or $restart[0].ArgumentList -notmatch ('controller-serve --port ' + $expectedPort + '$')) { throw 'Active listener fixed port was not preserved.' }
    }
    Write-Output 'Controller source upgrade fixture passed; no personal installation or process launch occurred.'
} finally {
    $env:LOCALAPPDATA = $previousLocalAppData
    Remove-Item -Recurse -Force -LiteralPath $fixture
}
