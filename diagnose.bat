@echo off
echo ================================================
echo   HomeCue Diagnostics
echo ================================================
echo.

set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"
set "HOMECUE_EXE=%SCRIPT_DIR%venv\Scripts\homecue.exe"

echo [1] Checking Python...
if exist "%PYTHON%" (
    echo     OK: %PYTHON%
    "%PYTHON%" --version
) else (
    echo     MISSING: %PYTHON%
    echo     Run setup.ps1 first.
    pause
    exit /b 1
)
echo.

echo [2] Checking homecue.exe...
if exist "%HOMECUE_EXE%" (
    echo     OK: %HOMECUE_EXE%
) else (
    echo     MISSING — will be created in step 4
)
echo.

echo [3] Checking dependencies...
"%PYTHON%" -c "import cuesdk; print('    cuesdk: OK')" 2>&1
"%PYTHON%" -c "import paho.mqtt; print('    paho-mqtt: OK')" 2>&1
"%PYTHON%" -c "import yaml; print('    pyyaml: OK')" 2>&1
"%PYTHON%" -c "import pystray; print('    pystray: OK')" 2>&1
"%PYTHON%" -c "import PIL; print('    Pillow: OK')" 2>&1
echo.

echo [4] Reinstalling HomeCue (regenerates homecue.exe)...
"%SCRIPT_DIR%venv\Scripts\pip.exe" install -e "%SCRIPT_DIR%." 2>&1
echo     Exit code: %ERRORLEVEL%
echo.

echo [5] Verifying entry point...
"%PYTHON%" -c "from homecue.__main__ import _entry; print('    OK: _entry found')" 2>&1
echo.

echo [6] Checking what homecue.exe points to...
"%PYTHON%" -c "import importlib.metadata; eps = importlib.metadata.entry_points(); console = [ep for ep in eps.get('console_scripts', eps) if hasattr(ep, 'name') and ep.name == 'homecue']; print('    Entry:', console[0].value if console else 'NOT FOUND')" 2>&1
echo.

echo [7] Testing homecue.exe --version...
"%HOMECUE_EXE%" --version 2>&1
echo     Exit code: %ERRORLEVEL%
echo.

echo [8] Checking working directory...
echo     diagnose.bat dir: %SCRIPT_DIR%
echo     Current dir: %CD%
echo.

echo [9] Running homecue.exe...
echo     Press Ctrl+C to stop once you see it working.
echo.
"%HOMECUE_EXE%" 2>&1
echo.
echo     homecue.exe exit code: %ERRORLEVEL%
echo.

echo ================================================
echo   Done — check output above for errors
echo ================================================
pause
