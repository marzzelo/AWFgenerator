@echo off
setlocal
cd /d "%~dp0"
if exist "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" (
  "%LOCALAPPDATA%\Programs\Python\Python312\python.exe" editor.py
) else (
  python editor.py
)
if errorlevel 1 pause
