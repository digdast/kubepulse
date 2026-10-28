@echo off
title KubePulse — Remote K3s & Kubernetes Monitor
cd /d "%~dp0"

where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
    py -3.14 -c "import fastapi, uvicorn, paramiko" >nul 2>nul
    if %ERRORLEVEL% EQU 0 (
        echo Starting KubePulse with Python 3.14...
        py -3.14 run.py %*
        goto :eof
    )
)

echo Starting KubePulse with default Python...
python run.py %*
