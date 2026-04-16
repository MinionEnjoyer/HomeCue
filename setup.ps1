# HomeCue Windows Setup Script
# Run with: powershell -ExecutionPolicy Bypass -File setup.ps1

$ErrorActionPreference = "Stop"

# --- Banner ---
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    HomeCue Setup" -ForegroundColor Cyan
Write-Host "    Corsair iCUE -> Home Assistant Bridge" -ForegroundColor Cyan
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""

# --- Check Python ---
Write-Host "[1/5] Checking Python installation..." -ForegroundColor Yellow

$pythonCmd = $null
foreach ($cmd in @("python", "python3", "py")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python (\d+)\.(\d+)") {
            $major = [int]$Matches[1]
            $minor = [int]$Matches[2]
            if ($major -ge 3 -and $minor -ge 9) {
                $pythonCmd = $cmd
                Write-Host "  Found $ver" -ForegroundColor Green
                break
            }
        }
    } catch {}
}

if (-not $pythonCmd) {
    Write-Host "  ERROR: Python 3.9+ is required but not found on PATH." -ForegroundColor Red
    Write-Host "  Download from: https://www.python.org/downloads/" -ForegroundColor Red
    Write-Host "  Make sure to check 'Add Python to PATH' during installation." -ForegroundColor Red
    exit 1
}

# --- Check iCUE ---
Write-Host ""
Write-Host "[2/5] Checking iCUE..." -ForegroundColor Yellow

$icueProcess = Get-Process -Name "iCUE" -ErrorAction SilentlyContinue
if ($icueProcess) {
    Write-Host "  iCUE is running" -ForegroundColor Green
} else {
    Write-Host "  WARNING: iCUE does not appear to be running." -ForegroundColor DarkYellow
    Write-Host "  HomeCue requires iCUE to be running with SDK enabled." -ForegroundColor DarkYellow
    Write-Host "  (iCUE > Settings > General > Enable SDK)" -ForegroundColor DarkYellow
    Write-Host ""
    $continue = Read-Host "  Continue anyway? [Y/n]"
    if ($continue -eq "n" -or $continue -eq "N") {
        exit 0
    }
}

# --- Create venv and install ---
Write-Host ""
Write-Host "[3/5] Setting up virtual environment and installing..." -ForegroundColor Yellow

$venvPath = Join-Path $PSScriptRoot "venv"
$venvPython = Join-Path $venvPath "Scripts\python.exe"
$recreateVenv = $false

if (Test-Path $venvPath) {
    # Check if venv is healthy by running its python.exe
    $venvOk = $false
    if (Test-Path $venvPython) {
        try {
            $result = & $venvPython --version 2>&1
            if ($LASTEXITCODE -eq 0) { $venvOk = $true }
        } catch {}
    }

    if ($venvOk) {
        Write-Host "  Virtual environment OK, reinstalling..." -ForegroundColor DarkYellow
    } else {
        Write-Host "  Virtual environment is broken (stale paths). Recreating..." -ForegroundColor DarkYellow
        Remove-Item -Recurse -Force $venvPath
        $recreateVenv = $true
    }
} else {
    $recreateVenv = $true
}

if ($recreateVenv) {
    Write-Host "  Creating virtual environment..."
    & $pythonCmd -m venv $venvPath
    if ($LASTEXITCODE -ne 0) {
        Write-Host "  ERROR: Failed to create virtual environment." -ForegroundColor Red
        exit 1
    }
}

$pipPath = Join-Path $venvPath "Scripts\pip.exe"
Write-Host "  Installing HomeCue and dependencies..."
& $pipPath install -e $PSScriptRoot --quiet
if ($LASTEXITCODE -ne 0) {
    Write-Host "  ERROR: Installation failed." -ForegroundColor Red
    exit 1
}
Write-Host "  Installed successfully" -ForegroundColor Green

# --- Configuration wizard ---
Write-Host ""
Write-Host "[4/5] Configuration" -ForegroundColor Yellow
Write-Host ""

$configPath = Join-Path $PSScriptRoot "config.yaml"

if (Test-Path $configPath) {
    Write-Host "  config.yaml already exists." -ForegroundColor DarkYellow
    $overwrite = Read-Host "  Overwrite? [y/N]"
    if ($overwrite -ne "y" -and $overwrite -ne "Y") {
        Write-Host "  Keeping existing config." -ForegroundColor Green
        $skipConfig = $true
    }
}

if (-not $skipConfig) {
    Write-Host "  Enter your MQTT broker details (press Enter for defaults):" -ForegroundColor Cyan
    Write-Host ""

    $mqttHost = Read-Host "  MQTT broker IP/hostname [192.168.1.100]"
    if ([string]::IsNullOrWhiteSpace($mqttHost)) { $mqttHost = "192.168.1.100" }

    $mqttPort = Read-Host "  MQTT port [1883]"
    if ([string]::IsNullOrWhiteSpace($mqttPort)) { $mqttPort = "1883" }

    $mqttUser = Read-Host "  MQTT username (leave blank for none)"
    $mqttPass = ""
    if (-not [string]::IsNullOrWhiteSpace($mqttUser)) {
        $mqttPass = Read-Host "  MQTT password"
    }

    Write-Host ""
    Write-Host "  Exclusive access takes full control of lighting from iCUE." -ForegroundColor DarkYellow
    Write-Host "  If disabled (default), iCUE profiles still show unless HomeCue actively sets colors." -ForegroundColor DarkYellow
    $exclusive = Read-Host "  Enable exclusive access? [y/N]"
    $exclusiveVal = "false"
    if ($exclusive -eq "y" -or $exclusive -eq "Y") { $exclusiveVal = "true" }

    # Build config YAML
    $configContent = @"
# HomeCue Configuration
# Generated by setup.ps1

mqtt:
  host: "$mqttHost"
  port: $mqttPort
"@

    if (-not [string]::IsNullOrWhiteSpace($mqttUser)) {
        $configContent += "`n  username: `"$mqttUser`""
        $configContent += "`n  password: `"$mqttPass`""
    }

    # Ask about profile switching
    Write-Host ""
    Write-Host "  Profile switching lets you switch iCUE lighting profiles from Home Assistant." -ForegroundColor Cyan
    Write-Host "  You export profiles from iCUE and HomeCue exposes them as a dropdown in HA." -ForegroundColor Cyan
    $enableProfiles = Read-Host "  Enable profile switching? [y/N]"
    $profilesPathVal = ""
    if ($enableProfiles -eq "y" -or $enableProfiles -eq "Y") {
        $profilesDir = "C:\ProgramData\Corsair\CUE5\GameSdkEffects\HomeCue"
        $profilesPathVal = $profilesDir

        if (-not (Test-Path $profilesDir)) {
            New-Item -ItemType Directory -Path $profilesDir -Force | Out-Null
            Write-Host "  Created profiles directory: $profilesDir" -ForegroundColor Green
        } else {
            Write-Host "  Profiles directory already exists: $profilesDir" -ForegroundColor Green
        }

        Write-Host ""
        Write-Host "  To add profiles:" -ForegroundColor DarkYellow
        Write-Host "    1. Open iCUE and create a lighting profile" -ForegroundColor DarkYellow
        Write-Host "    2. Right-click the profile > Export" -ForegroundColor DarkYellow
        Write-Host "    3. Select 'Lighting Effects' only" -ForegroundColor DarkYellow
        Write-Host "    4. Save the .cueprofile file to:" -ForegroundColor DarkYellow
        Write-Host "       $profilesDir" -ForegroundColor Cyan
        Write-Host "    5. Use only letters, numbers, and underscores in filenames" -ForegroundColor DarkYellow
    }

    $configContent += @"

  discovery_prefix: "homeassistant"
  client_id: "homecue"

poll_interval: 5.0
effects_fps: 30
exclusive_access: $exclusiveVal
log_level: "INFO"

# Override device names as they appear in Home Assistant.
# device_names:
#   "CORSAIR iCUE LINK QX RGB Fan": "Top Case Fan"
"@

    if (-not [string]::IsNullOrWhiteSpace($profilesPathVal)) {
        $escapedPath = $profilesPathVal -replace '\\', '\\'
        $configContent += @"


profiles_path: "$escapedPath"
"@
    }

    # Write as UTF-8 without BOM (PyYAML cannot parse BOM)
    [System.IO.File]::WriteAllText($configPath, $configContent, [System.Text.UTF8Encoding]::new($false))
    Write-Host ""
    Write-Host "  Config written to config.yaml" -ForegroundColor Green
}

# --- Startup task ---
Write-Host ""
Write-Host "[5/5] Startup configuration" -ForegroundColor Yellow
Write-Host ""

$homecueExe = Join-Path $venvPath "Scripts\homecue.exe"

$addStartup = Read-Host "  Run HomeCue automatically at Windows login? [y/N]"
if ($addStartup -eq "y" -or $addStartup -eq "Y") {
    $taskName = "HomeCue"

    # Remove existing task if present (ignore errors if it doesn't exist)
    try {
        $null = schtasks /Query /TN $taskName 2>&1
        if ($LASTEXITCODE -eq 0) {
            $null = schtasks /Delete /TN $taskName /F 2>&1
        }
    } catch {
        # Task doesn't exist yet, that's fine
    }

    schtasks /Create `
        /TN $taskName `
        /TR "`"$homecueExe`" --config `"$configPath`" --tray" `
        /SC ONLOGON `
        /RL HIGHEST `
        /F | Out-Null

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Startup task created: '$taskName'" -ForegroundColor Green
        Write-Host "  HomeCue will start automatically when you log in." -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Could not create startup task." -ForegroundColor DarkYellow
        Write-Host "  You may need to run this script as Administrator." -ForegroundColor DarkYellow
    }
} else {
    Write-Host "  Skipped. You can run HomeCue manually anytime." -ForegroundColor DarkYellow
}

# --- Summary ---
Write-Host ""
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host "    Setup complete!" -ForegroundColor Green
Write-Host "  ================================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "  To run HomeCue now:" -ForegroundColor White
Write-Host "    .\venv\Scripts\homecue.exe" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Or activate the venv first:" -ForegroundColor White
Write-Host "    .\venv\Scripts\Activate.ps1" -ForegroundColor Cyan
Write-Host "    homecue" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Your Corsair devices will appear in Home Assistant" -ForegroundColor White
Write-Host "  automatically as light entities once HomeCue connects." -ForegroundColor White
Write-Host ""
Write-Host "  Make sure iCUE is running with SDK enabled:" -ForegroundColor DarkYellow
Write-Host "    iCUE > Settings > General > Enable SDK" -ForegroundColor DarkYellow
Write-Host ""
