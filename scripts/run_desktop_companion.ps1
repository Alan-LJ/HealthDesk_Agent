$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $projectRoot ".hdagent\Scripts\python.exe"

Set-Location $projectRoot

if (Test-Path $venvPython) {
    & $venvPython -m app.desktop_companion
} else {
    python -m app.desktop_companion
}
