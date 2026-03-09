@echo off
setlocal
cd /d "%~dp0.."

docker compose down --remove-orphans
if errorlevel 1 exit /b %errorlevel%
