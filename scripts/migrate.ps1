# migrate.ps1 - Initialize MongoDB: ensure MVP collections and indexes exist.
# Uses the same settings chain as the app (config + .env). Safe to run on every startup.
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Error "No .venv found. Run scripts/bootstrap.ps1 first."
    exit 1
}

if (Test-Path ".env") {
    # Load MONGODB_URI / MONGODB_DATABASE (and friends) from .env into the process environment.
    Get-Content ".env" | ForEach-Object {
        if ($_ -match '^\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$') {
            [System.Environment]::SetEnvironmentVariable($matches[1], $matches[2])
        }
    }
}

Write-Host "Initializing MongoDB collections and indexes..."
& .\.venv\Scripts\python.exe -m aiagent.db
if ($LASTEXITCODE -ne 0) { throw "aiagent.db initialization failed" }
Write-Host "MongoDB initialized."