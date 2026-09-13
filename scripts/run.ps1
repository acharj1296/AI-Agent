# run.ps1 - Run the API with hot reload.
# Loads .env into the process environment (same as migrate.ps1).
param(
    [switch]$DepsUp = $true
)

$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "No .venv found. Run scripts/bootstrap.ps1 first."
    exit 1
}

if ($DepsUp) {
    Write-Host "Starting local MongoDB (Docker)..."
    docker compose -f deploy/environments/local/docker-compose.yaml up -d mongodb
    if ($LASTEXITCODE -ne 0) { throw "docker compose up failed - is Docker running?" }
}

if (Test-Path ".env") {
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
        }
    }
}

Write-Host "Starting API on http://127.0.0.1:8000 (docs: /docs)"
& .\.venv\Scripts\python.exe -m uvicorn aiagent.api.app:app --reload --host 127.0.0.1 --port 8000
exit $LASTEXITCODE