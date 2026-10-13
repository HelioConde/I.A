@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"
title Luna - Qwen3-4B Q8_0 ja instalado

if not exist "tools\usar_qwen4b_luna.py" (
  echo ERRO: Atualize a branch do Brain-SSD. Faltou tools\usar_qwen4b_luna.py.
  pause
  endlocal & exit /b 2
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
      py -3 --version >nul 2>nul
      if not errorlevel 1 set "PYTHON_CMD=py -3"
    )
  )
)
if not defined PYTHON_CMD set "PYTHON_CMD=python"
%PYTHON_CMD% --version
if errorlevel 1 (
  echo ERRO: Python 3.11 ou superior nao encontrado.
  pause
  endlocal & exit /b 3
)
echo.
echo ===================================================
echo LUNA - USAR QWEN3-4B Q8_0 JA INSTALADO
echo ===================================================
echo Sem download. Modelo verificado por GGUF e SHA-256.
echo Os modelos antigos e suas permissoes serao preservados.
echo Feche qualquer sessao anterior da Luna antes de iniciar.
echo.
%PYTHON_CMD% "tools\usar_qwen4b_luna.py" --activate
if errorlevel 1 (
  echo.
  echo O modelo 4B Q8_0 nao foi ativado.
  echo Se ainda nao instalou, execute INSTALAR-QWEN4B-LUNA.bat.
  echo Para conferir: py -3 tools\usar_qwen4b_luna.py --status
  pause
  endlocal & exit /b 2
)
echo.
echo Modelo verificado e selecionado. Iniciando Luna...
call "%~dp0INICIAR-COPILOTO-WINDOWS.bat"
set "RESULT=%ERRORLEVEL%"
endlocal & exit /b %RESULT%
