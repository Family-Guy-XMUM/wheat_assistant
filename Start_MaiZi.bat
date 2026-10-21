@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
title MaiZi - Local web app
pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist ".venv\Scripts\python.exe" goto setup_required
if not exist "frontend\dist\index.html" goto setup_required
if /i "%~1"=="--check" goto check_only

echo MaiZi is starting. Your browser will open automatically.
echo Keep this window open while using the app.
echo To stop: press Ctrl+C here. If prompted to terminate the batch, enter Y.
echo The usual address is http://127.0.0.1:8765
echo If that port is busy, use the address printed by the app below.
echo.
".venv\Scripts\python.exe" -m maizi.launcher %*
set "MAIZI_EXIT_CODE=%ERRORLEVEL%"
echo.
echo MaiZi stopped. Exit code: %MAIZI_EXIT_CODE%
popd
pause
exit /b %MAIZI_EXIT_CODE%

:check_only
".venv\Scripts\python.exe" -c "import maizi.launcher; import maizi.api; print('Windows source launch prerequisites: OK')"
set "MAIZI_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %MAIZI_EXIT_CODE%

:setup_required
echo [SETUP REQUIRED] Double-click Setup_Windows.bat first.
echo Then double-click Start_MaiZi.bat again.
popd
if /i not "%~1"=="--check" pause
exit /b 1

:folder_error
echo [ERROR] Cannot open the project folder. Extract the source folder first.
if /i not "%~1"=="--check" pause
exit /b 1
