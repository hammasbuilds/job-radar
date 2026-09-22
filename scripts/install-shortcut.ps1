# Create Desktop and Start-menu shortcuts for job-radar, and try to pin.
#
# Windows 11 removed the "Pin to taskbar" shell verb and blocks the registry
# route that worked on Windows 10, so a script cannot reliably pin. This
# attempts the verb where it still exists and reports honestly when it does
# not, rather than claiming success — a shortcut that silently did not pin is
# worse than being told to right-click once.

$ErrorActionPreference = 'Stop'

$root     = Split-Path -Parent $PSScriptRoot
$target   = Join-Path $root 'run-job-radar.bat'
$icon     = Join-Path $root 'assets\job-radar.ico'

if (-not (Test-Path $target)) { throw "missing $target" }

function New-Shortcut([string]$linkPath) {
    $shell = New-Object -ComObject WScript.Shell
    $link  = $shell.CreateShortcut($linkPath)
    $link.TargetPath       = $target
    $link.WorkingDirectory = $root
    $link.Description      = 'job-radar - European AI roles, filtered'
    if (Test-Path $icon) { $link.IconLocation = $icon }
    $link.Save()
    Write-Host "  created $linkPath"
}

$desktop = [Environment]::GetFolderPath('Desktop')
New-Shortcut (Join-Path $desktop 'job-radar.lnk')

$startMenu = Join-Path ([Environment]::GetFolderPath('ApplicationData')) `
                       'Microsoft\Windows\Start Menu\Programs'
New-Item -ItemType Directory -Force -Path $startMenu | Out-Null
$startLink = Join-Path $startMenu 'job-radar.lnk'
New-Shortcut $startLink

# Try the shell verb. Present on Windows 10, removed on most Windows 11 builds.
$pinned = $false
try {
    $shellApp = New-Object -ComObject Shell.Application
    $folder   = $shellApp.Namespace((Split-Path $startLink))
    $item     = $folder.ParseName((Split-Path $startLink -Leaf))
    $verb     = $item.Verbs() | Where-Object { $_.Name -replace '&','' -match 'Pin to taskbar' }
    if ($verb) { $verb.DoIt(); $pinned = $true }
} catch {
    $pinned = $false
}

if ($pinned) {
    Write-Host "  pinned to the taskbar"
} else {
    Write-Host "  could not pin automatically (Windows 11 blocks this)."
    Write-Host "  Start -> type 'job-radar' -> right-click -> Pin to taskbar"
}
