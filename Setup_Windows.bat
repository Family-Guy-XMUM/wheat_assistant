@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
title wheat_assistant - First-time Windows setup
pushd "%~dp0"
if errorlevel 1 goto folder_error

where uv.exe >nul 2>nul
if errorlevel 1 goto missing_uv
where node.exe >nul 2>nul
if errorlevel 1 goto missing_node
where npm.cmd >nul 2>nul
if errorlevel 1 goto missing_node
node -e "if (Number(process.versions.node.split('.')[0]) < 22) process.exit(1)"
if errorlevel 1 goto old_node

echo [1/3] Preparing Python 3.12 and locked dependencies...
echo uv may download Python when it is not already available.
uv sync --frozen --python 3.12
if errorlevel 1 goto setup_failed

echo [2/3] Installing locked frontend dependencies...
call npm.cmd --prefix frontend ci
if errorlevel 1 goto setup_failed

echo [3/3] Building the local web interface...
call npm.cmd --prefix frontend run build
if errorlevel 1 goto setup_failed

if exist ".env" goto setup_ready
copy ".env.example" ".env" >nul
if errorlevel 1 goto setup_failed

:setup_ready
echo.
echo Setup complete. Double-click Start_wheat_assistant.bat to launch.
echo Optional live AI: configure your own .env locally. Never share that file.
echo Existing .env files are preserved. Editable rules and demos work without a key.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 0

:missing_uv
echo [MISSING TOOL] Install uv, then open a new terminal or rerun this file.
echo Official instructions: https://docs.astral.sh/uv/getting-started/installation/
goto setup_failed

:missing_node
echo [MISSING TOOL] Install Node.js 22 or newer, including npm.
echo Official download: https://nodejs.org/en/download
goto setup_failed

:old_node
echo [UNSUPPORTED VERSION] Node.js 22 or newer is required.
goto setup_failed

:setup_failed
echo.
echo Setup did not finish. Review the error above, fix it, then rerun this file.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1

:folder_error
echo [ERROR] Cannot open the project folder. Extract the source folder first.
if /i not "%~1"=="--no-pause" pause
exit /b 1
