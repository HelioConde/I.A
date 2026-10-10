@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Verificacao e chat local
echo.
echo BRAIN-SSD - Experimento de memoria episodica
echo As notas so serao salvas se voce usar "Guardar uma lembranca".
echo Arquivo privado: %%LOCALAPPDATA%%\BrainSSD\episodic-notes.sqlite3
echo.
echo [1/2] Verificando GGUF e llama.cpp. Sem carregar o modelo...
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tools\doctor_chat.py" --profile economia --probe
  if errorlevel 1 goto :not_ready
  ".venv\Scripts\python.exe" "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 "tools\doctor_chat.py" --profile economia --probe
    if errorlevel 1 goto :not_ready
    py -3 "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow
  ) else (
    python "tools\doctor_chat.py" --profile economia --probe
    if errorlevel 1 goto :not_ready
    python "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow
  )
)
if errorlevel 1 goto :not_ready
goto :end
:not_ready
echo.
echo Nao foi possivel preparar a IA local.
echo Verifique os itens marcados como FALTA ou avisos do diagnostico acima.
echo Execute DIAGNOSTICAR-CHAT-WINDOWS.bat para detalhes.
echo O historico e as suas memorias locais nao foram apagados.
pause
:end
endlocal
