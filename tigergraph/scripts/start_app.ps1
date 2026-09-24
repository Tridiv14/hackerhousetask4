$ErrorActionPreference = "Stop"

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$env:PYTHONPATH = $ProjectRoot

Set-Location $ProjectRoot
Write-Host "Starting Autonomous Fraud Investigation API..."
.venv\Scripts\uvicorn.exe backend.app:app --host 0.0.0.0 --port 8000 --reload
