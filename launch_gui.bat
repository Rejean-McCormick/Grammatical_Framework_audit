@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ==================================================
REM gf-audit GUI launcher
REM
REM Optional environment variables:
REM   GF_AUDIT_DEBUG_CONSOLE=1   -> force console mode
REM   GF_AUDIT_PYTHON=<path>     -> explicit Python interpreter
REM
REM Resolution order:
REM   1) GF_AUDIT_PYTHON environment variable
REM   2) .venv\Scripts\pythonw.exe / python.exe
REM   3) uv run against this project
REM   4) pyw / pythonw on PATH
REM   5) py / python on PATH
REM ==================================================

for %%I in ("%~dp0.") do set "APP_ROOT=%%~fI"
set "APP_MAIN=%APP_ROOT%\app\main_gui.py"
set "VENV_DIR=%APP_ROOT%\.venv"
set "VENV_PYTHONW=%VENV_DIR%\Scripts\pythonw.exe"
set "VENV_PYTHON=%VENV_DIR%\Scripts\python.exe"

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
set "USE_UV=0"

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
  goto resolve_console_runtime
)

REM ---- prefer repo-local venv pythonw for GUI ----
if exist "%VENV_PYTHONW%" (
  set "PY_CMD=%VENV_PYTHONW%"
  goto launch
)

REM ---- uv project launcher before global Python ----
where uv >nul 2>&1
if not errorlevel 1 (
  set "USE_UV=1"
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

:resolve_console_runtime
if exist "%VENV_PYTHON%" (
  set "PY_CMD=%VENV_PYTHON%"
  goto launch
)

where uv >nul 2>&1
if not errorlevel 1 (
  set "USE_UV=1"
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
echo.
echo Expected one of:
echo   - GF_AUDIT_PYTHON environment variable
echo   - %VENV_PYTHONW% or %VENV_PYTHON%
echo   - uv on PATH
echo   - pyw / pythonw on PATH
echo   - py / python on PATH
pause
exit /b 2

:launch
if /I "%USE_UV%"=="1" (
  if /I "%LAUNCH_MODE%"=="console" (
    uv run --directory "%APP_ROOT%" python -X utf8 -m app.main_gui %*
    set "RC=%ERRORLEVEL%"
    if not "%RC%"=="0" (
      echo.
      echo GUI exited with code %RC%.
      pause
    )
    exit /b %RC%
  ) else (
    uv run --directory "%APP_ROOT%" pythonw.exe -X utf8 -m app.main_gui %*
    exit /b %ERRORLEVEL%
  )
)

if /I "%LAUNCH_MODE%"=="console" (
  "%PY_CMD%" %PY_ARGS% "%APP_MAIN%" %*
  set "RC=%ERRORLEVEL%"
  if not "%RC%"=="0" (
    echo.
    echo GUI exited with code %RC%.
    pause
  )
  exit /b %RC%
) else (
  "%PY_CMD%" %PY_ARGS% "%APP_MAIN%" %*
  exit /b %ERRORLEVEL%
)