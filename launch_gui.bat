@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ==================================================
REM gf-audit GUI launcher
REM
REM Optional environment variables:
REM   GF_AUDIT_DEBUG_CONSOLE=1   -> force python.exe instead of pythonw.exe
REM   GF_AUDIT_PYTHON=<path>     -> explicit Python interpreter
REM ==================================================

for %%I in ("%~dp0.") do set "APP_ROOT=%%~fI"
set "APP_MAIN=%APP_ROOT%\app\main_gui.py"
set "VENV_DIR=%APP_ROOT%\.venv"

set "PYTHONUTF8=1"
if defined PYTHONPATH (
  set "PYTHONPATH=%APP_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%APP_ROOT%"
)

if not exist "%APP_MAIN%" (
  echo ERROR: GUI entry point not found:
  echo   %APP_MAIN%
  pause
  exit /b 2
)

set "PY_CMD="
set "PY_ARGS="
set "LAUNCH_MODE=windowed"

REM ---- explicit override ----
if defined GF_AUDIT_PYTHON (
  if exist "%GF_AUDIT_PYTHON%" (
    set "PY_CMD=%GF_AUDIT_PYTHON%"
    goto launch
  ) else (
    echo ERROR: GF_AUDIT_PYTHON points to a missing file:
    echo   %GF_AUDIT_PYTHON%
    pause
    exit /b 2
  )
)

REM ---- debug mode keeps console visible ----
if /I "%GF_AUDIT_DEBUG_CONSOLE%"=="1" (
  set "LAUNCH_MODE=console"
  goto resolve_console_python
)

REM ---- prefer venv pythonw for GUI ----
if exist "%VENV_DIR%\Scripts\pythonw.exe" (
  set "PY_CMD=%VENV_DIR%\Scripts\pythonw.exe"
  goto launch
)

REM ---- fallback to launcher pyw on PATH ----
where pyw >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=pyw"
  set "PY_ARGS=-3"
  goto launch
)

REM ---- fallback to pythonw on PATH ----
where pythonw >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=pythonw"
  goto launch
)

REM ---- last resort: console Python ----
set "LAUNCH_MODE=console"

:resolve_console_python
if exist "%VENV_DIR%\Scripts\python.exe" (
  set "PY_CMD=%VENV_DIR%\Scripts\python.exe"
  goto launch
)

where py >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=py"
  set "PY_ARGS=-3"
  goto launch
)

where python >nul 2>&1
if not errorlevel 1 (
  set "PY_CMD=python"
  goto launch
)

echo ERROR: No suitable Python interpreter found.
echo Install Python 3 or create a local .venv in:
echo   %VENV_DIR%
pause
exit /b 2

:launch
if /I "%LAUNCH_MODE%"=="console" (
  "%PY_CMD%" %PY_ARGS% "%APP_MAIN%"
  set "RC=%ERRORLEVEL%"
  if not "%RC%"=="0" (
    echo.
    echo GUI exited with code %RC%.
    pause
  )
  exit /b %RC%
) else (
  "%PY_CMD%" %PY_ARGS% "%APP_MAIN%"
  exit /b %ERRORLEVEL%
)