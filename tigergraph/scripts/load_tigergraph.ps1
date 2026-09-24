$ErrorActionPreference = "Stop"

Write-Host "Loading data into TigerGraph..."

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$LoadScript = Join-Path $PSScriptRoot "load_tg.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python virtual environment not found at $PythonExe"
    exit 1
}

$env:PYTHONPATH = $ProjectRoot
& $PythonExe $LoadScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "TigerGraph load completed successfully."
} else {
    Write-Error "TigerGraph load failed."
}
