# Return an owned icon so callers can dispose it, including the fallback.
function New-NanoleafTrayIcon {
    param([string]$Path = (Join-Path $PSScriptRoot 'tray-icon.ico'))
    try {
        return [Drawing.Icon]::new($Path, [Windows.Forms.SystemInformation]::SmallIconSize)
    } catch {
        return [Drawing.SystemIcons]::Information.Clone()
    }
}
