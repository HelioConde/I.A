@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Preparacao verificada do Windows
if not exist "tools\install_windows_chat.py" (
  echo ERRO: o arquivo de instalacao nao foi encontrado.
  echo Atualize o repositorio completo em %CD%.
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
echo.
echo PREPARAR BRAIN-SSD: Windows x64, CPU-only.
echo Modelo oficial Qwen (~639 MB) + runtime llama.cpp oficial.
echo Os downloads so iniciarao com sua confirmacao.
echo O programa verifica o SHA-256 e preserva seu historico e memorias.
echo.
echo Versao do Python:
%PYTHON_CMD% --version
if errorlevel 1 goto :python_error
echo.
set /p "CONFIRMAR=Deseja baixar/instalar os componentes oficiais? [S/N]: "
if /I not "%CONFIRMAR%"=="S" (
  echo Cancelado. Nenhum download foi iniciado.
  goto :end
)
%PYTHON_CMD% "tools\install_windows_chat.py" --all
if errorlevel 1 (
  echo.
  echo Preparacao incompleta. Nenhum arquivo privado foi apagado.
  echo Consulte o aviso acima e tente novamente.
  goto :end
)
echo.
echo Validando os requisitos (nao gera resposta neste passo)...
%PYTHON_CMD% "tools\doctor_chat.py" --profile economia --probe
if errorlevel 1 (
  echo Requisitos ainda pendentes. A instalacao nao foi declarada como funcional.
  goto :end
)
echo.
echo Pre-requisitos prontos para teste real.
echo Execute INICIAR-CHAT-MEMORIA-WINDOWS.bat para iniciar o chat.
goto :end
:python_error
echo Python 3.11 ou mais novo nao encontrado.
:end
pause
endlocal
