@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
title wheat_assistant - Local web app
pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist ".venv\Scripts\python.exe" goto setup_required
if not exist "frontend\dist\index.html" goto setup_required
if /i "%~1"=="--check" goto check_only

echo wheat_assistant is starting. Your browser will open automatically.
echo Keep this window open while using the app.
echo To stop: press Ctrl+C here. If prompted to terminate the batch, enter Y.
echo The usual address is http://127.0.0.1:8765
echo If that port is busy, use the address printed by the app below.
echo.
".venv\Scripts\python.exe" -m wheat_assistant.launcher %*
set "WHEAT_ASSISTANT_EXIT_CODE=%ERRORLEVEL%"
echo.
echo wheat_assistant stopped. Exit code: %WHEAT_ASSISTANT_EXIT_CODE%
popd
pause
exit /b %WHEAT_ASSISTANT_EXIT_CODE%

:check_only
".venv\Scripts\python.exe" -c "import wheat_assistant.launcher; import wheat_assistant.api; print('Windows source launch prerequisites: OK')"
set "WHEAT_ASSISTANT_EXIT_CODE=%ERRORLEVEL%"
popd
exit /b %WHEAT_ASSISTANT_EXIT_CODE%

:setup_required
echo [SETUP REQUIRED] Double-click Setup_Windows.bat first.
echo Then double-click Start_wheat_assistant.bat again.
popd
if /i not "%~1"=="--check" pause
exit /b 1

:folder_error
echo [ERROR] Cannot open the project folder. Extract the source folder first.
if /i not "%~1"=="--check" pause
exit /b 1
