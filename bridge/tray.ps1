param([switch]$Check)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
. (Join-Path $PSScriptRoot 'tray-icon.ps1')
if ($Check) {
    $checkIcon = New-NanoleafTrayIcon
    $checkIcon.Dispose()
    Write-Output 'Windows tray components and icon loading available.'
    exit 0
}
$mutex = [Threading.Mutex]::new($false, 'Local\CodexNanoleafTray')
if (-not $mutex.WaitOne(0, $false)) { $mutex.Dispose(); exit 0 }
$python = Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'
$bridge = Join-Path $PSScriptRoot 'bridge.py'
$icon = [Windows.Forms.NotifyIcon]::new()
$menu = [Windows.Forms.ContextMenuStrip]::new()
$trayArtwork = New-NanoleafTrayIcon
$icon.Icon = $trayArtwork
$icon.Text = 'Nanoleaf: loading status'
$icon.ContextMenuStrip = $menu
$script:poll = $null
$script:commands = [Collections.Generic.List[Diagnostics.Process]]::new()
$script:items = @{}
function Start-Bridge([string]$Arguments) {
    $info = [Diagnostics.ProcessStartInfo]::new()
    $info.FileName = $python
    $info.Arguments = '"' + $bridge + '" ' + $Arguments
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    return [Diagnostics.Process]::Start($info)
}
$stateLabel = $menu.Items.Add('Reading status...')
$stateLabel.Enabled = $false
[void]$menu.Items.Add([Windows.Forms.ToolStripSeparator]::new())
foreach ($mode in @('work', 'free', 'quiet')) {
    $item = $menu.Items.Add((Get-Culture).TextInfo.ToTitleCase($mode))
    $item.Tag = $mode
    $item.Add_Click({
        try {
            $script:commands.Add((Start-Bridge ('mode ' + $this.Tag)))
            $stateLabel.Text = 'Switch requested...'
        } catch { $stateLabel.Text = 'Could not start bridge command.' }
    })
    $script:items[$mode] = $item
}
[void]$menu.Items.Add([Windows.Forms.ToolStripSeparator]::new())
$mapItem = $menu.Items.Add('Open wall map')
$mapItem.Add_Click({ $script:commands.Add((Start-Bridge 'map')) })
$layoutMenu = [Windows.Forms.ToolStripMenuItem]::new('Layout')
foreach ($style in @('classic', 'project')) {
    $entry = $layoutMenu.DropDownItems.Add((Get-Culture).TextInfo.ToTitleCase($style))
    $entry.Tag = $style
    $entry.Add_Click({ $script:commands.Add((Start-Bridge ('style ' + $this.Tag))) })
}
[void]$menu.Items.Add($layoutMenu)
[void]$menu.Items.Add([Windows.Forms.ToolStripSeparator]::new())
$exitItem = $menu.Items.Add('Exit tray only')
$exitItem.Add_Click({ [Windows.Forms.Application]::ExitThread() })
$timer = [Windows.Forms.Timer]::new()
$timer.Interval = 2000
$timer.Add_Tick({
    try {
        foreach ($command in @($script:commands.ToArray())) {
            if ($command.HasExited) {
                if ($command.ExitCode -ne 0) { $stateLabel.Text = 'Command failed; check connection.' }
                [void]$script:commands.Remove($command)
                $command.Dispose()
            }
        }
        if ($null -ne $script:poll -and $script:poll.HasExited) {
            $state = $script:poll.StandardOutput.ReadToEnd() | ConvertFrom-Json
            $script:poll.Dispose()
            $script:poll = $null
            foreach ($entry in $script:items.GetEnumerator()) { $entry.Value.Checked = ($entry.Key -eq $state.mode) }
            foreach ($entry in $layoutMenu.DropDownItems) { $entry.Checked = ($entry.Tag -eq $state.style) }
            if ($state.error) { $detail = $state.error }
            elseif ($state.map_pending) { $detail = 'Layout change pending' }
            elseif ($state.pending) { $detail = 'Switch pending' }
            elseif ($state.mode -eq 'free') { $detail = 'Lights released' }
            else { $detail = 'Last light update succeeded' }
            $stateLabel.Text = [string]$state.mode + ': ' + $detail
            $icon.Text = ('Nanoleaf ' + $stateLabel.Text).Substring(0, [Math]::Min(63, ('Nanoleaf ' + $stateLabel.Text).Length))
        }
        if ($null -eq $script:poll) { $script:poll = Start-Bridge 'map-status' }
    } catch {
        $stateLabel.Text = 'Local status unavailable.'
        if ($null -ne $script:poll) { $script:poll.Dispose(); $script:poll = $null }
    }
})
try {
    # Resume the saved mode without clearing tasks or changing mode selection.
    $script:commands.Add((Start-Bridge 'setup --refresh'))
    $script:poll = Start-Bridge 'map-status'
    $icon.Visible = $true
    $timer.Start()
    [Windows.Forms.Application]::Run()
} finally {
    $timer.Stop()
    $timer.Dispose()
    $icon.Visible = $false
    $icon.Dispose()
    $trayArtwork.Dispose()
    $menu.Dispose()
    if ($null -ne $script:poll) { $script:poll.Dispose() }
    foreach ($command in $script:commands) { $command.Dispose() }
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
