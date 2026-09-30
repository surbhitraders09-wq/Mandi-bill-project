@echo off
setlocal
rem =====================================================================
rem  Mandi-API auto-start (called by Startup VBS at each logon).
rem  Self-contained: derives every path from this file's own location.
rem  Idempotent: skips if :8000 is already being served, so it can never
rem  double-bind or shadow an existing instance.
rem =====================================================================

set "ROOT=%~dp0"
set "BACKEND=%ROOT%backend"
set "VENV_PY=%BACKEND%\venv\Scripts\python.exe"
set "LOG_DIR=%BACKEND%logs"
set "LOG=%LOG_DIR%\api.log"
set "ERR_LOG=%LOG_DIR%\api-error.log"

rem ---- use venv python if present, else fall back to `python` ----
if not exist "%VENV_PY%" set "VENV_PY=python"

rem ---- ensure log dir exists ----
if not exist "%LOG_DIR%" mkdir "%LOG_DIR%" 2>nul

rem ---- bail if something already serves :8000 (idempotent) ----
netstat -ano | findstr /C:":8000" | findstr /C:"LISTENING" >nul 2>&1
if not errorlevel 1 (
    echo %date% %time%  WARN  :8000 already in use - skipping>>"%LOG%"
    exit /b 0
)

rem ---- start uvicorn detached (so uvicorn outlives this bat) ----
cd /d "%BACKEND%"
echo %date% %time%  START uvicorn app.main:app host=0.0.0.0 port=8000>>"%LOG%"
start "" /min "%VENV_PY%" -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --no-access-log >>"%LOG%" 2>>"%ERR_LOG%"
exit /b 0
