$ErrorActionPreference = 'Stop'
$tray = Join-Path $PSScriptRoot 'tray.ps1'
$bridge = Join-Path $PSScriptRoot 'bridge.py'
Get-CimInstance Win32_Process | Where-Object {
    ($_.Name -eq 'powershell.exe' -and $_.CommandLine -match ([regex]::Escape($tray) + '(?:"|$)')) -or
    ($_.Name -in @('python.exe', 'pythonw.exe') -and $_.CommandLine -match ([regex]::Escape($bridge) + '"?\s+serve(?:\s|$)'))
} | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
foreach ($folder in @([Environment]::GetFolderPath('Startup'), [Environment]::GetFolderPath('Programs'))) {
    $link = Join-Path $folder 'Codex Nanoleaf.lnk'
    if (Test-Path $link) { Remove-Item $link }
}
