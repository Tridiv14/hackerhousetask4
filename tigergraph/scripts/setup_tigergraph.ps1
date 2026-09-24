$ErrorActionPreference = "Stop"

Write-Host "Setting up TigerGraph Schema and Queries..."

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$PythonExe = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$SetupScript = Join-Path $PSScriptRoot "setup_tg.py"

if (-not (Test-Path $PythonExe)) {
    Write-Error "Python virtual environment not found at $PythonExe"
    exit 1
}

$env:PYTHONPATH = $ProjectRoot
& $PythonExe $SetupScript

if ($LASTEXITCODE -eq 0) {
    Write-Host "TigerGraph schema setup completed successfully."
} else {
    Write-Error "TigerGraph schema setup failed."
}

