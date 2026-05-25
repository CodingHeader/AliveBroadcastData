@echo off
chcp 65001 >nul 2>&1
echo === AliveBroadcastData Starting ===

REM Read port from config.py (default 12306)
set PORT=12306
for /f "tokens=2 delims==" %%a in ('findstr /R "^PORT = " config.py 2^>nul') do set PORT=%%a
set PORT=%PORT: =%

REM Check port in use
netstat -ano | findstr ":%PORT% " >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port %PORT% is in use
    echo Close the process or change PORT in server\config.py
    pause
    exit /b 1
)

cd /d %~dp0\server

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.x
    pause
    exit /b 1
)

REM Check requirements.txt
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found
    pause
    exit /b 1
)

if not exist "venv" ( echo Creating venv... & python -m venv venv )
call venv\Scripts\activate
pip install -r requirements.txt -q

echo Server starting at http://127.0.0.1:%PORT%
python main.py
pause
