[CmdletBinding()]
param(
    [switch]$Start,
    [switch]$ResetDemo,
    [switch]$E2E,
    [string]$ApiBaseUrl = "http://127.0.0.1:8000",
    [string]$FrontendBaseUrl = "http://127.0.0.1:5173"
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$backend = Join-Path $root "SRC\Backend"
$frontend = Join-Path $root "SRC\Frontend"

function Wait-ForApi([string]$Url) {
    $deadline = (Get-Date).AddSeconds(90)
    do {
        try {
            $response = Invoke-RestMethod -Uri "$Url/api/health" -TimeoutSec 3
            if ($response.status -eq "ok") { return }
        } catch { }
        Start-Sleep -Seconds 2
    } while ((Get-Date) -lt $deadline)
    throw "TransitOps API did not become healthy at $Url/api/health."
}

Push-Location $root
try {
    if ($ResetDemo) {
        Write-Warning "Resetting the local Docker demo database and uploaded receipts. Do not use this switch with shared data."
        docker compose down -v
        if ($LASTEXITCODE -ne 0) { throw "Docker could not reset the TransitOps demo environment." }
        $Start = $true
    }

    if ($Start) {
        Write-Host "Starting TransitOps Docker services..."
        docker compose up --build -d
        if ($LASTEXITCODE -ne 0) { throw "Docker could not start the TransitOps services." }
    }

    Write-Host "Waiting for the TransitOps API..."
    Wait-ForApi $ApiBaseUrl
    Write-Host "API health check passed."

    Push-Location $backend
    try {
        if (-not (Test-Path ".\.venv\Scripts\python.exe")) {
            throw "Backend virtual environment is missing. Follow the Backend setup in README.md first."
        }
        Write-Host "Running backend business-rule and API tests..."
        & ".\.venv\Scripts\python.exe" -m pytest
        if ($LASTEXITCODE -ne 0) {
            throw "Backend tests failed. Use -ResetDemo only for disposable local demo data, then rerun the workflow."
        }
    } finally { Pop-Location }

    Push-Location $frontend
    try {
        Write-Host "Running frontend lint and production build..."
        npm run lint
        if ($LASTEXITCODE -ne 0) { throw "Frontend lint failed." }
        npm run build
        if ($LASTEXITCODE -ne 0) { throw "Frontend production build failed." }
        if ($E2E) {
            $previousBaseUrl = $env:PLAYWRIGHT_BASE_URL
            $env:PLAYWRIGHT_BASE_URL = $FrontendBaseUrl
            Write-Host "Running desktop and mobile end-to-end role journeys..."
            npm run test:e2e
            if ($LASTEXITCODE -ne 0) { throw "Frontend end-to-end tests failed." }
            $env:PLAYWRIGHT_BASE_URL = $previousBaseUrl
        }
    } finally { Pop-Location }

    Write-Host "TransitOps workflow verification completed successfully."
} finally {
    Pop-Location
}
