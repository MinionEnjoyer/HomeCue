# HomeCue Update Script
# Run with: powershell -ExecutionPolicy Bypass -File update.ps1

Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    HomeCue Updater" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# Resolve script directory (handles both direct and Bypass invocations)
$scriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent (Resolve-Path $MyInvocation.MyCommand.Path) }

# --- Pull latest ---
Write-Host "[1/2] Pulling latest version from GitHub..." -ForegroundColor Yellow

Push-Location $scriptDir
try {
    # Check that this is a git repo
    if (-not (Test-Path ".git")) {
        Write-Host "  ERROR: Not a git repository. Did you clone with git?" -ForegroundColor Red
        Write-Host "  Run: git clone https://github.com/MinionEnjoyer/HomeCue.git" -ForegroundColor Gray
        Pop-Location
        exit 1
    }

    # Run git pull — capture output so stderr doesn't trigger errors
    $output = git pull origin main 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: git pull failed:" -ForegroundColor Red
        Write-Host "  $output" -ForegroundColor Gray
        Pop-Location
        exit 1
    }
    Write-Host "  $output" -ForegroundColor Green
} catch {
    Write-Host "  ERROR: git is not installed or not on PATH." -ForegroundColor Red
    Write-Host "  $_" -ForegroundColor Gray
    Pop-Location
    exit 1
}
Pop-Location

# --- Reinstall ---
Write-Host ""
Write-Host "[2/2] Reinstalling dependencies..." -ForegroundColor Yellow

$pipPath = Join-Path $scriptDir "venv\Scripts\pip.exe"

if (-not (Test-Path $pipPath)) {
    Write-Host "  ERROR: Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

$output = & $pipPath install -e $scriptDir --quiet 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Installation failed:" -ForegroundColor Red
    Write-Host "  $output" -ForegroundColor Gray
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
