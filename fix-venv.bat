@echo off
echo ================================================
echo   HomeCue - Recreate Virtual Environment
echo ================================================
echo.
echo The venv has a stale Python path baked in.
echo This will delete and recreate it.
echo.

set "SCRIPT_DIR=%~dp0"

:: Find system Python
where python >nul 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: python not found on PATH.
    echo Install Python 3.9+ and ensure it is on your PATH.
    pause
    exit /b 1
)

:: Show what we're doing
for /f "delims=" %%i in ('where python') do set "SYS_PYTHON=%%i"
echo System Python: %SYS_PYTHON%

:: Check Python version
python --version 2>&1
echo.

:: Remove old venv
if exist "%SCRIPT_DIR%venv" (
    echo Removing old venv...
    rmdir /s /q "%SCRIPT_DIR%venv"
    echo     Done.
) else (
    echo No existing venv found.
)
echo.

:: Create new venv
echo Creating new virtual environment...
python -m venv "%SCRIPT_DIR%venv"
if %ERRORLEVEL% neq 0 (
    echo ERROR: Failed to create venv.
    pause
    exit /b 1
)
echo     Done.
echo.

:: Install HomeCue
echo Installing HomeCue and dependencies...
"%SCRIPT_DIR%venv\Scripts\pip.exe" install -e "%SCRIPT_DIR%."
if %ERRORLEVEL% neq 0 (
    echo ERROR: Installation failed.
    pause
    exit /b 1
)
echo.

:: Verify
echo Verifying homecue.exe...
"%SCRIPT_DIR%venv\Scripts\homecue.exe" --version 2>&1
if %ERRORLEVEL% neq 0 (
    echo ERROR: homecue.exe still broken.
    pause
    exit /b 1
)
echo.

echo ================================================
echo   Success! venv recreated.
echo   Run homecue.exe or homecue.bat to start.
echo ================================================
pause
