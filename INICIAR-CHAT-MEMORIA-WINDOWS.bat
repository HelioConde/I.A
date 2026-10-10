@echo off
setlocal
cd /d "%~dp0"
if not exist "tools\doctor_chat.py" (
  echo.
  echo ERRO: este atalho precisa estar na raiz do projeto Brain-SSD.
  echo Pasta atual: %CD%
  echo Extraia o projeto inteiro, sem mover somente o arquivo .bat.
  echo.
  pause
  exit /b 2
)
set "PYTHON_CMD="
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (
      set "PYTHON_CMD=py -3.11"
    ) else (
      set "PYTHON_CMD=py -3"
    )
  ) else (
    set "PYTHON_CMD=python"
  )
)
echo Pasta do Brain-SSD: %CD%
echo Interpretador selecionado:
%PYTHON_CMD% --version
if errorlevel 1 (
  echo Python nao encontrado. Instale Python 3.11 e tente novamente.
  pause
  exit /b 3
)
title Brain-SSD - Chat com memoria
echo.
echo BRAIN-SSD - Experimento de memoria episodica
echo As notas so serao salvas se voce usar "Guardar uma lembranca".
echo Arquivo privado: %%LOCALAPPDATA%%\BrainSSD\episodic-notes.sqlite3
echo.
echo [1/2] Verificando GGUF e llama.cpp. Sem carregar o modelo...
%PYTHON_CMD% "tools\doctor_chat.py" --profile economia --probe
if errorlevel 1 goto :not_ready
echo.
echo [2/2] Iniciando chat com memoria opt-in...
%PYTHON_CMD% "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow
if errorlevel 1 goto :not_ready
goto :end
:not_ready
echo.
echo Nao foi possivel preparar a IA local.
echo Veja os avisos do diagnostico acima.
echo Execute DIAGNOSTICAR-CHAT-WINDOWS.bat para detalhes.
echo O historico e as memorias locais nao foram apagados.
pause
:end
endlocal
