@echo off
setlocal
cd /d "%~dp0.."

docker compose up --build -d
if errorlevel 1 exit /b %errorlevel%

echo Server running on http://127.0.0.1:8000
