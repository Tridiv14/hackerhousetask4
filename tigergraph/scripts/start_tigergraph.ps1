$ErrorActionPreference = "Stop"

# Navigate to the docker directory relative to this script
$DockerDir = Join-Path $PSScriptRoot "..\docker"
Set-Location $DockerDir

Write-Host "Verifying Docker is running..."
docker info > $null
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker is not running. Please start Docker Desktop."
    exit 1
}

Write-Host "Starting TigerGraph container..."
docker compose up -d

Write-Host "TigerGraph is starting... This can take a few minutes."
Write-Host "Waiting for container to become healthy..."

# Wait up to 60 seconds for port 9000 to be available
$timeout = 60
$timer = 0
while ($timer -lt $timeout) {
    try {
        $response = Invoke-WebRequest -Uri "http://localhost:9000/echo" -UseBasicParsing -ErrorAction SilentlyContinue
        if ($response.StatusCode -eq 200) {
            Write-Host "TigerGraph is reachable on port 9000!"
            break
        }
    } catch {
        # ignore
    }
    Start-Sleep -Seconds 5
    $timer += 5
}

if ($timer -ge $timeout) {
    Write-Host "TigerGraph might still be initializing. Use 'docker logs -f tigergraph' to monitor."
}
