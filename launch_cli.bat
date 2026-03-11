@echo off
setlocal EnableExtensions DisableDelayedExpansion

REM ==================================================
REM gf-audit/launch_cli.bat
REM Windows launcher for the Python CLI entrypoint.
REM
REM Resolution order for Python:
REM   1) GF_AUDIT_PYTHON environment variable
REM   2) .venv\Scripts\python.exe
REM   3) py -3
REM   4) python on PATH
REM ==================================================

for %%I in ("%~dp0.") do set "REPO_ROOT=%%~fI"

set "APP_MAIN_PY=%REPO_ROOT%\app\main_cli.py"
set "APP_INIT_PY=%REPO_ROOT%\app\__init__.py"
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%APP_MAIN_PY%" (
  echo ERROR: CLI entrypoint not found:
  echo   %APP_MAIN_PY%
  exit /b 2
)

if not exist "%APP_INIT_PY%" (
  echo ERROR: Python package marker not found:
  echo   %APP_INIT_PY%
  exit /b 2
)

call :resolve_python
if errorlevel 1 exit /b %ERRORLEVEL%

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"
set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"

pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Cannot change directory to repo root:
  echo   %REPO_ROOT%
  exit /b 2
)

if /I "%USE_PY_LAUNCHER%"=="1" (
  py -3 -X utf8 -m app.main_cli %*
) else (
  "%PYTHON_EXE%" -X utf8 -m app.main_cli %*
)

set "RC=%ERRORLEVEL%"
popd >nul 2>&1
exit /b %RC%

:resolve_python
set "USE_PY_LAUNCHER=0"
set "PYTHON_EXE="

if defined GF_AUDIT_PYTHON (
  if exist "%GF_AUDIT_PYTHON%" (
    set "PYTHON_EXE=%GF_AUDIT_PYTHON%"
    goto :resolve_python_ok
  ) else (
    echo ERROR: GF_AUDIT_PYTHON is set but the file does not exist:
    echo   %GF_AUDIT_PYTHON%
    exit /b 2
  )
)

if exist "%VENV_PYTHON%" (
  set "PYTHON_EXE=%VENV_PYTHON%"
  goto :resolve_python_ok
)

where py >nul 2>&1
if not errorlevel 1 (
  set "USE_PY_LAUNCHER=1"
  goto :resolve_python_ok
)

for /f "delims=" %%I in ('where python 2^>nul') do (
  set "PYTHON_EXE=%%I"
  goto :resolve_python_ok
)

echo ERROR: No Python runtime found.
echo.
echo Expected one of:
echo   - GF_AUDIT_PYTHON environment variable
echo   - %VENV_PYTHON%
echo   - py launcher on PATH
echo   - python on PATH
exit /b 2

:resolve_python_ok
exit /b 0