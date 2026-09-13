# bootstrap.ps1 - Create venv, install dev deps, copy .env.example
$ErrorActionPreference = "Stop"
Set-Location (Split-Path $PSScriptRoot)

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Error "uv is required. Install from https://docs.astral.sh/uv/ and re-run."
    exit 1
}

Write-Host "Creating Python 3.12 virtual environment..."
uv venv --python 3.12 .venv
if ($LASTEXITCODE -ne 0) { throw "uv venv failed" }

Write-Host "Installing package in editable mode with dev dependencies..."
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
if ($LASTEXITCODE -ne 0) { throw "uv pip install failed" }

if (-not (Test-Path ".env")) {
    Copy-Item ".env.example" ".env"
    Write-Host "Created .env from .env.example - review MONGODB_URI and other settings."
}

Write-Host "`nSetup complete. Activate the environment with:" -ForegroundColor Green
Write-Host "  .\.venv\Scripts\Activate.ps1" -ForegroundColor Cyan