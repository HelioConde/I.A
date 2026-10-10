@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Chat local Windows
echo.
echo  BRAIN-SSD - Chat visual no Windows
echo  CPU-only, sem API externa. O navegador abrira automaticamente.
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tools\run_chat.py"
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 "tools\run_chat.py"
    ) else (
        python "tools\run_chat.py"
    )
)
if errorlevel 1 (
    echo.
    echo Falha ao iniciar. Verifique Python 3.11+ e o ambiente do projeto.
    pause
)
endlocal
