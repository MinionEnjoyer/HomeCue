# HomeCue Update Script
# Run with: powershell -ExecutionPolicy Bypass -File update.ps1

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    HomeCue Updater" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# --- Pull latest ---
Write-Host "[1/2] Pulling latest version from GitHub..." -ForegroundColor Yellow

try {
    git -C $PSScriptRoot pull origin main
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: git pull failed." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Source updated" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: git is not installed or not on PATH." -ForegroundColor Red
    exit 1
}

# --- Reinstall ---
Write-Host ""
Write-Host "[2/2] Reinstalling dependencies..." -ForegroundColor Yellow

$pipPath = Join-Path $PSScriptRoot "venv\Scripts\pip.exe"

if (-not (Test-Path $pipPath)) {
    Write-Host "  ERROR: Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

& $pipPath install -e $PSScriptRoot --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Installation failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Dependencies updated" -ForegroundColor Green

# --- Done ---
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    Update complete!" -ForegroundColor Green
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Restart HomeCue to apply the update." -ForegroundColor White
Write-Host ""
