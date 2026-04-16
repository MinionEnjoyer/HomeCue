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
Write-Host "[2/3] Checking virtual environment..." -ForegroundColor Yellow

$venvPath = Join-Path $scriptDir "venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$pipPath = Join-Path $venvPath "Scripts\pip.exe"

if (-not (Test-Path $venvPath)) {
    Write-Host "  ERROR: Virtual environment not found. Run setup.ps1 first." -ForegroundColor Red
    exit 1
}

# Check if venv is healthy (exe launchers have hardcoded paths that break on folder moves)
$venvOk = $false
if (Test-Path $venvPython) {
    try {
        $null = & $venvPython --version 2>&1
        if ($LASTEXITCODE -eq 0) { $venvOk = $true }
    } catch {}
}

if (-not $venvOk) {
    Write-Host "  Virtual environment has stale paths. Recreating..." -ForegroundColor DarkYellow

    Remove-Item -Recurse -Force $venvPath

    # Find system Python
    $pythonCmd = $null
    foreach ($cmd in @("python", "python3", "py")) {
        try {
            $null = & $cmd --version 2>&1
            if ($LASTEXITCODE -eq 0) { $pythonCmd = $cmd; break }
        } catch {}
    }
    if (-not $pythonCmd) {
        Write-Host "  ERROR: Python not found on PATH. Cannot recreate venv." -ForegroundColor Red
        exit 1
    }

    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
    Write-Host "  Recreated virtual environment" -ForegroundColor Green
} else {
    Write-Host "  Virtual environment OK" -ForegroundColor Green
}

Write-Host ""
Write-Host "[3/3] Reinstalling dependencies..." -ForegroundColor Yellow

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
