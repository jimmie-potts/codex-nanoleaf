$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class NanoleafIconTestNative {
    [DllImport("user32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    public static extern IntPtr LoadImage(IntPtr instance, string name, uint type, int width, int height, uint flags);
    [DllImport("user32.dll")]
    public static extern bool DestroyIcon(IntPtr icon);
}
'@
$root = Split-Path $PSScriptRoot -Parent
. (Join-Path $root 'bridge/tray-icon.ps1')
$path = Join-Path $root 'bridge/tray-icon.ico'
$bytes = [IO.File]::ReadAllBytes($path)
if ([BitConverter]::ToUInt16($bytes, 2) -ne 1) { throw 'Not a Windows icon.' }
$count = [BitConverter]::ToUInt16($bytes, 4)
$sizes = @(16, 20, 24, 32, 48, 256)
if ($count -ne $sizes.Count) { throw 'Unexpected frame count.' }
foreach ($index in 0..($count - 1)) {
    $size = $sizes[$index]
    $encoded = if ($size -eq 256) { 0 } else { $size }
    if ($bytes[6 + 16 * $index] -ne $encoded -or $bytes[7 + 16 * $index] -ne $encoded) {
        throw "Missing square $size px frame."
    }
    # LoadImage also supports the 256 px shell frame, which .NET Framework's
    # multi-frame Icon constructor treats as a zero-size directory entry.
    $handle = [NanoleafIconTestNative]::LoadImage([IntPtr]::Zero, $path, 1, $size, $size, 0x10)
    if ($handle -eq [IntPtr]::Zero) { throw "Windows cannot load $size px frame." }
    $frame = [Drawing.Icon]::FromHandle($handle)
    try {
        if ($frame.Width -ne $size -or $frame.Height -ne $size) { throw "Cannot load $size px frame." }
        $bitmap = $frame.ToBitmap()
        try {
            if ($bitmap.GetPixel(0, 0).A -ne 0) { throw "Opaque background in $size px frame." }
            $blue = 0; $green = 0
            for ($y = 0; $y -lt $size; $y++) {
                for ($x = 0; $x -lt $size; $x++) {
                    $pixel = $bitmap.GetPixel($x, $y)
                    if ($pixel.A -gt 80 -and $pixel.B -gt $pixel.G * 1.3) { $blue++ }
                    if ($pixel.A -gt 80 -and $pixel.G -gt $pixel.B * 1.3) { $green++ }
                }
            }
            if ($blue -eq 0 -or $green -eq 0) { throw "Blue Lines or green status node missing at $size px." }
        } finally { $bitmap.Dispose() }
    } finally { $frame.Dispose(); [void][NanoleafIconTestNative]::DestroyIcon($handle) }
}
$icon = New-NanoleafTrayIcon -Path $path
try {
    if ($icon.Size -ne [Windows.Forms.SystemInformation]::SmallIconSize) { throw 'Wrong tray icon size.' }
    $bitmap = $icon.ToBitmap()
    try {
        if ($bitmap.GetPixel(0, 0).A -ne 0) { throw 'The tray loader did not preserve transparency.' }
    } finally { $bitmap.Dispose() }
} finally { $icon.Dispose() }
$temporary = Join-Path ([IO.Path]::GetTempPath()) ('nanoleaf-icon-test-' + [guid]::NewGuid())
[void][IO.Directory]::CreateDirectory($temporary)
try {
    $corrupt = Join-Path $temporary 'corrupt.ico'
    [IO.File]::WriteAllText($corrupt, 'invalid icon')
    foreach ($candidate in @((Join-Path $temporary 'missing.ico'), $corrupt)) {
        $fallback = New-NanoleafTrayIcon -Path $candidate
        try {
            if ($fallback.Size -ne [Drawing.SystemIcons]::Information.Size) { throw 'Fallback icon unavailable.' }
            if ([object]::ReferenceEquals($fallback, [Drawing.SystemIcons]::Information)) { throw 'Fallback is not independently owned.' }
        } finally { $fallback.Dispose() }
    }
} finally { Remove-Item -LiteralPath $temporary -Recurse -Force }
Write-Output 'PASS: six Windows icon sizes, transparent backgrounds, blue/green artwork, tray sizing, missing/corrupt fallback.'
