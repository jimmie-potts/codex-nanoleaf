param([switch]$SkipShortcuts, [string]$PythonRuntime = (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'))
# Upgrade the existing installation without resetting tasks or rewriting hooks.
$ErrorActionPreference = 'Stop'
$destination = Join-Path $env:LOCALAPPDATA 'CodexNanoleaf'
if (-not (Test-Path (Join-Path $destination 'config.json'))) {
    throw 'Set up the Nanoleaf bridge before installing mode controls.'
}
foreach ($asset in @('tray-icon.ico', 'tray-icon.ps1')) {
    if (-not (Test-Path -LiteralPath (Join-Path $PSScriptRoot $asset) -PathType Leaf)) {
        throw ('Missing tray asset: ' + $asset)
    }
}
$backup = Join-Path $destination ('backup-wall-map-' + (Get-Date -Format 'yyyyMMdd-HHmmss'))
New-Item -ItemType Directory -Path $backup | Out-Null
$python = $PythonRuntime
$copy = Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $PSScriptRoot 'backup_install.py') + '" "' + $destination + '" "' + $backup + '"') -PassThru -WindowStyle Hidden
$copy.WaitForExit()
if ($copy.ExitCode -ne 0) { throw 'Could not back up the bridge state. Upgrade stopped.' }
# Copy the verified optional controller artifact before code imports it.
$vendor = Join-Path $PSScriptRoot 'vendor'
if (-not (Test-Path $vendor)) { throw 'Missing controller contract artifact.' }
& $python (Join-Path $PSScriptRoot 'controller_contract.py')
if ($LASTEXITCODE -ne 0) { throw 'Controller contract verification failed.' }
if (Test-Path (Join-Path $destination 'vendor')) { Copy-Item -Recurse (Join-Path $destination 'vendor') (Join-Path $backup 'vendor') }
Copy-Item -Recurse -Force $vendor $destination
# Copy dependencies first so a hook arriving during the upgrade can import them.
foreach ($name in @('tray-icon.ico', 'tray-icon.ps1', 'controller_state.py', 'controller_contract.py', 'controller_server.py', 'requirements-controller.txt', 'project_map.py', 'shared_input.py', 'wall_server.py', 'wall.html', 'prism.js', 'prism-adapters.js', 'prism-labels.js', 'bridge.py', 'tray.ps1', 'remove-modes.ps1', 'backup_install.py', 'install-modes.ps1', 'README.md')) {
    if (Test-Path (Join-Path $destination $name)) { Copy-Item (Join-Path $destination $name) $backup }
    Copy-Item (Join-Path $PSScriptRoot $name) (Join-Path $destination ($name + '.new'))
    Move-Item -Force (Join-Path $destination ($name + '.new')) (Join-Path $destination $name)
}
# Restart only this installation's worker, map server, and tray.
$bridge = Join-Path $destination 'bridge.py'
$tray = Join-Path $destination 'tray.ps1'
$controllerProcesses = @(Get-CimInstance Win32_Process | Where-Object { $_.Name -in @('python.exe','pythonw.exe') -and $_.CommandLine -match ('(?:^|["\s])' + [regex]::Escape($bridge) + '"?\s+controller-serve(?:\s|$)') })
$controllerPort = 0
foreach ($process in $controllerProcesses) {
    # Rebuild the allowed arguments. Never replay arbitrary process arguments.
    $configuration = [regex]::Match($process.CommandLine, ('(?:^|["\s])' + [regex]::Escape($bridge) + '"?\s+controller-serve(?:\s+--port(?:\s+|=)"?([0-9]{1,5})"?)?\s*$'))
    if (-not $configuration.Success) { throw 'Cannot safely preserve active controller arguments. Upgrade restart stopped.' }
    $port = if ($configuration.Groups[1].Success) { [int]$configuration.Groups[1].Value } else { 0 }
    if ($port -gt 65535) { throw 'Invalid active controller port. Upgrade restart stopped.' }
    $controllerPort = $port
}
$controllerRunning = $controllerProcesses.Count -gt 0
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match ([regex]::Escape($bridge) + '"?\s+(?:worker|serve|controller-serve)(?:\s|$)')) -or
    ($_.Name -eq 'powershell.exe' -and $_.CommandLine -match ([regex]::Escape($tray) + '(?:"|$)'))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
if ($controllerRunning) { Start-Process -FilePath $python -WindowStyle Hidden -ArgumentList ('"' + $bridge + '" controller-serve --port ' + $controllerPort) }
if (-not $SkipShortcuts) {
    $shell = New-Object -ComObject WScript.Shell
    foreach ($folder in @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Programs'))) {
        $shortcut = $shell.CreateShortcut((Join-Path $folder 'Codex Nanoleaf.lnk'))
        $shortcut.TargetPath = Join-Path $env:WINDIR 'System32\WindowsPowerShell\v1.0\powershell.exe'
        $shortcut.Arguments = '-NoProfile -STA -WindowStyle Hidden -File "' + $tray + '"'
        $shortcut.WorkingDirectory = $destination
        $shortcut.WindowStyle = 7
        $shortcut.IconLocation = (Join-Path $destination 'tray-icon.ico') + ',0'
        $shortcut.Description = 'Open the Nanoleaf wall map and switch layouts or modes'
        $shortcut.Save()
    }
}
Start-Process powershell.exe -WindowStyle Hidden -ArgumentList ('-NoProfile -STA -WindowStyle Hidden -File "' + $tray + '"')
Write-Output ('Wall map and tray controls installed. Previous program files: ' + $backup)
