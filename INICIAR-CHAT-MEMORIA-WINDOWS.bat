@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Chat e memoria episodica experimental
echo.
echo BRAIN-SSD - Experimento de memoria episodica
echo As notas so serao salvas se voce usar "Guardar uma lembranca".
echo Arquivo privado: %%LOCALAPPDATA%%\BrainSSD\episodic-notes.sqlite3
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tools\run_chat.py" --profile economia --episodic-memory
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 "tools\run_chat.py" --profile economia --episodic-memory
  ) else (
    python "tools\run_chat.py" --profile economia --episodic-memory
  )
)
if errorlevel 1 (
  echo.
  echo Nao foi possivel iniciar. Leia docs\CHAT_WINDOWS.md.
  pause
)
endlocal
