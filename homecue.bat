@echo off
echo ================================================
echo   HomeCue Launcher
echo ================================================
echo.

:: Find the venv Python
set "SCRIPT_DIR=%~dp0"
set "PYTHON=%SCRIPT_DIR%venv\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo ERROR: Virtual environment not found at %PYTHON%
    echo Run setup.ps1 first.
    echo.
    pause
    exit /b 1
)

echo Using Python: %PYTHON%
echo.

:: Run HomeCue and keep window open no matter what
"%PYTHON%" -m homecue %*
echo.
echo ================================================
echo   HomeCue exited with code %ERRORLEVEL%
echo ================================================
echo.
pause
