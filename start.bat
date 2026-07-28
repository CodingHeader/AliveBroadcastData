@echo off
setlocal enabledelayedexpansion
chcp 65001 >nul 2>&1
echo === AliveBroadcastData Starting ===

REM Load .env if present
if exist ".env" (
    for /f "usebackq delims=" %%l in (".env") do (
        set "line=%%l"
        if not "!line:~0,1!"=="#" if not "!line!"=="" call :parseenv "!line!"
    )
)

if not defined SECRET_KEY (
    echo [ERROR] 未找到 SECRET_KEY，请先在项目根目录创建 .env
    endlocal
    pause
    exit /b 1
)

REM Read port from config.py (default 12306)
set PORT=12306
for /f "tokens=2 delims==" %%a in ('findstr /R "^PORT = " config.py 2^>nul') do set PORT=%%a
set PORT=%PORT: =%

REM Check port in use
netstat -ano | findstr ":%PORT% " >nul 2>&1
if not errorlevel 1 (
    echo [WARN] Port %PORT% is in use
    echo Close the process or change PORT in server\config.py
    endlocal
    pause
    exit /b 1
)

cd /d %~dp0\server

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERROR] Python not found, please install Python 3.x
    endlocal
    pause
    exit /b 1
)

REM Check requirements.txt
if not exist "requirements.txt" (
    echo [ERROR] requirements.txt not found
    endlocal
    pause
    exit /b 1
)

if not exist "venv" ( echo Creating venv... & python -m venv venv )
call venv\Scripts\activate
pip install -r requirements.txt -q

echo Server starting at http://127.0.0.1:%PORT%
python main.py
endlocal

pause
exit /b 0

:parseenv
set "raw=%~1"
set "key="
set "value="
for /f "tokens=1* delims==" %%i in ("!raw!") do (
    set "key=%%i"
    set "value=%%j"
)
if "!key!"=="" goto :eof
set "key=!key: =!"
if defined value (
    set "value=!value:"=!"
    set "value=!value:'=!"
    set "!key!=!value!"
)
goto :eof