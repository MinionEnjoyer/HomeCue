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
)
echo.

echo [2] Checking homecue.exe...
if exist "%HOMECUE_EXE%" (
    echo     OK: %HOMECUE_EXE%
) else (
    echo     MISSING: %HOMECUE_EXE%
    echo     Run: .\venv\Scripts\pip.exe install -e .
)
echo.

echo [3] Reinstalling to regenerate homecue.exe...
"%SCRIPT_DIR%venv\Scripts\pip.exe" install -e "%SCRIPT_DIR%." 2>&1
echo     Exit code: %ERRORLEVEL%
echo.

echo [4] Testing homecue imports...
"%PYTHON%" -c "from homecue.__main__ import _entry; print('    OK: _entry found')" 2>&1
echo.

echo [5] Testing homecue.exe --version...
"%HOMECUE_EXE%" --version 2>&1
echo     Exit code: %ERRORLEVEL%
echo.

echo [6] Running homecue.exe (will connect to iCUE/MQTT)...
echo     Press Ctrl+C to stop once you see it working.
echo.
"%HOMECUE_EXE%" 2>&1
echo.
echo     Exit code: %ERRORLEVEL%
echo.

echo ================================================
echo   Done
echo ================================================
pause
