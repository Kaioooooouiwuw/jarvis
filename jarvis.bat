@echo off

title GUIDEON - Dev Mode

cd /d "%~dp0"

if not exist "venv_windows\Scripts\activate.bat" (
    echo ERRO: Ambiente virtual nao encontrado!
    pause
    exit
)

echo Ativando ambiente virtual...
call venv_windows\Scripts\activate

echo ================================
echo    GUIDEON - Iniciando Sistema
echo ================================
echo.

echo [1/2] Iniciando Monitor de Sistema...
start /b python monitor.py >nul 2>&1

echo [2/2] Iniciando Agente GUIDEON...
python agent.py dev

echo.
echo GUIDEON encerrado.
pause
