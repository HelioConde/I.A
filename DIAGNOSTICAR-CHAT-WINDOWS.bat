@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Diagnostico de instalacao
echo.
echo  BRAIN-SSD - Verificar requisitos do chat Windows
echo.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" "tools\doctor_chat.py" --profile economia --probe
) else (
    where py >nul 2>nul
    if not errorlevel 1 (
        py -3 "tools\doctor_chat.py" --profile economia --probe
    ) else (
        python "tools\doctor_chat.py" --profile economia --probe
    )
)
echo.
echo  Se algum requisito estiver faltando, consulte docs\CHAT_WINDOWS.md.
pause
endlocal
