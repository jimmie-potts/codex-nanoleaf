param([switch]$SkipShortcuts)
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
$python = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$copy = Start-Process -FilePath $python -ArgumentList ('"' + (Join-Path $PSScriptRoot 'backup_install.py') + '" "' + $destination + '" "' + $backup + '"') -PassThru -WindowStyle Hidden
$copy.WaitForExit()
if ($copy.ExitCode -ne 0) { throw 'Could not back up the bridge state. Upgrade stopped.' }
# Copy dependencies first so a hook arriving during the upgrade can import them.
foreach ($name in @('tray-icon.ico', 'tray-icon.ps1', 'project_map.py', 'wall_server.py', 'wall.html', 'bridge.py', 'tray.ps1', 'remove-modes.ps1', 'backup_install.py', 'install-modes.ps1', 'README.md')) {
    if (Test-Path (Join-Path $destination $name)) { Copy-Item (Join-Path $destination $name) $backup }
    Copy-Item (Join-Path $PSScriptRoot $name) (Join-Path $destination ($name + '.new'))
    Move-Item -Force (Join-Path $destination ($name + '.new')) (Join-Path $destination $name)
}
# Restart only this installation's worker, map server, and tray.
$bridge = Join-Path $destination 'bridge.py'
$tray = Join-Path $destination 'tray.ps1'
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match ([regex]::Escape($bridge) + '"?\s+(?:worker|serve)(?:\s|$)')) -or
    ($_.Name -eq 'powershell.exe' -and $_.CommandLine -match ([regex]::Escape($tray) + '(?:"|$)'))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
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
