@echo off
setlocal EnableExtensions DisableDelayedExpansion

for %%I in ("%~dp0.") do set "REPO_ROOT=%%~fI"
set "APP_MAIN_PY=%REPO_ROOT%\app\main_cli.py"
set "APP_INIT_PY=%REPO_ROOT%\app\__init__.py"
set "VENV_PYTHON=%REPO_ROOT%\.venv\Scripts\python.exe"

if not exist "%APP_MAIN_PY%" (
  echo ERROR: CLI entrypoint not found:
  echo   %APP_MAIN_PY%
  pause
  exit /b 2
)

if not exist "%APP_INIT_PY%" (
  echo ERROR: Python package marker not found:
  echo   %APP_INIT_PY%
  pause
  exit /b 2
)

call :resolve_runtime
if errorlevel 1 (
  pause
  exit /b %ERRORLEVEL%
)

set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONDONTWRITEBYTECODE=1"

if defined PYTHONPATH (
  set "PYTHONPATH=%REPO_ROOT%;%PYTHONPATH%"
) else (
  set "PYTHONPATH=%REPO_ROOT%"
)

pushd "%REPO_ROOT%" >nul 2>&1
if errorlevel 1 (
  echo ERROR: Cannot change directory to repo root:
  echo   %REPO_ROOT%
  pause
  exit /b 2
)

if "%~1"=="" (
  echo No CLI arguments were provided.
  echo.
  echo Required:
  echo   --project-root
  echo   --rgl-root
  echo   --gf-exe
  echo   --out-root
  echo.
  if /I "%USE_UV%"=="1" (
    uv run --directory "%REPO_ROOT%" gf-audit-cli --help
  ) else if /I "%USE_PY_LAUNCHER%"=="1" (
    py -3 -X utf8 -m app.main_cli --help
  ) else (
    "%PYTHON_EXE%" -X utf8 -m app.main_cli --help
  )
  echo.
  pause
  popd >nul 2>&1
  exit /b 0
)

if /I "%USE_UV%"=="1" (
  uv run --directory "%REPO_ROOT%" gf-audit-cli %*
) else if /I "%USE_PY_LAUNCHER%"=="1" (
  py -3 -X utf8 -m app.main_cli %*
) else (
  "%PYTHON_EXE%" -X utf8 -m app.main_cli %*
)

set "RC=%ERRORLEVEL%"
if not "%RC%"=="0" (
  echo.
  echo CLI exited with code %RC%.
  pause
)

popd >nul 2>&1
exit /b %RC%

:resolve_runtime
set "USE_UV=0"
set "USE_PY_LAUNCHER=0"
set "PYTHON_EXE="

if defined GF_AUDIT_PYTHON (
  if exist "%GF_AUDIT_PYTHON%" (
    set "PYTHON_EXE=%GF_AUDIT_PYTHON%"
    goto :resolve_runtime_ok
  ) else (
    echo ERROR: GF_AUDIT_PYTHON is set but the file does not exist:
    echo   %GF_AUDIT_PYTHON%
    exit /b 2
  )
)

if exist "%VENV_PYTHON%" (
  set "PYTHON_EXE=%VENV_PYTHON%"
  goto :resolve_runtime_ok
)

where uv >nul 2>&1
if not errorlevel 1 (
  set "USE_UV=1"
  goto :resolve_runtime_ok
)

where py >nul 2>&1
if not errorlevel 1 (
  set "USE_PY_LAUNCHER=1"
  goto :resolve_runtime_ok
)

for /f "delims=" %%I in ('where python 2^>nul') do (
  set "PYTHON_EXE=%%I"
  goto :resolve_runtime_ok
)

echo ERROR: No Python runtime found.
echo.
echo Expected one of:
echo   - GF_AUDIT_PYTHON environment variable
echo   - %VENV_PYTHON%
echo   - uv on PATH
echo   - py launcher on PATH
echo   - python on PATH
exit /b 2

:resolve_runtime_ok
exit /b 0