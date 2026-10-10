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
title Brain-SSD - Diagnostico de instalacao
echo.
echo BRAIN-SSD - Verificar requisitos do chat Windows
echo Este atalho funciona mesmo quando aberto a partir de Documents/Downloads.
echo.
%PYTHON_CMD% "tools\doctor_chat.py" --profile economia --probe
set "EXIT_CODE=%ERRORLEVEL%"
echo.
echo Se houver requisitos FALTA, consulte docs\CHAT_WINDOWS.md.
echo O teste nao apaga memorias e nao executa inferencia do Qwen.
pause
endlocal & exit /b %EXIT_CODE%
