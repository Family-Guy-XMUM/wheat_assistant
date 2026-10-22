@echo off
setlocal EnableExtensions DisableDelayedExpansion
set "PYTHONUTF8=1"
title MaiZi - Windows acceptance checks
pushd "%~dp0"
if errorlevel 1 goto folder_error
if not exist ".venv\Scripts\python.exe" goto setup_required
if not exist "frontend\dist\index.html" goto setup_required
".venv\Scripts\python.exe" scripts\validate_windows.py
set "MAIZI_VALIDATION_EXIT=%ERRORLEVEL%"
popd
if /i not "%~1"=="--no-pause" pause
exit /b %MAIZI_VALIDATION_EXIT%
:setup_required
echo Run Setup_Windows.bat first, then rerun this validator.
popd
if /i not "%~1"=="--no-pause" pause
exit /b 1
:folder_error
echo Extract the complete source folder before running this file.
if /i not "%~1"=="--no-pause" pause
exit /b 1
