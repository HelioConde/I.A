@echo off
setlocal EnableExtensions
cd /d "%~dp0"
title Brain-SSD - Copiloto Windows experimental
if not exist "tools\run_chat.py" (
  echo ERRO: execute este arquivo na raiz do projeto I.A.
  pause
  exit /b 2
)
set "PYTHON_CMD=python"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=".venv\Scripts\python.exe""
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3.11 --version >nul 2>nul
    if not errorlevel 1 (set "PYTHON_CMD=py -3.11") else (set "PYTHON_CMD=py -3")
  )
)
%PYTHON_CMD% --version
if errorlevel 1 (
  echo Python 3.11+ nao encontrado.
  pause
  exit /b 3
)
echo.
echo O COPILOTO NAO abre arquivos nem grava a tela automaticamente.
echo Primeiro, escolha quais permissoes dar nesta sessao.
echo.
set "COPILOT_ROOT="
choice /c SN /n /m "Autorizar leitura de UMA pasta e suas subpastas? [S/N] "
if errorlevel 2 goto :ask_screen
set "COPILOT_ROOT=%USERPROFILE%\Documents"
echo Pasta padrao: %COPILOT_ROOT%
set /p "COPILOT_ROOT=Digite outra pasta autorizada (Enter = Documents): "
if not defined COPILOT_ROOT set "COPILOT_ROOT=%USERPROFILE%\Documents"
if not exist "%COPILOT_ROOT%\" (
  echo Pasta inexistente. Nenhuma pasta foi autorizada.
  set "COPILOT_ROOT="
)
set "COPILOT_ROOT_ARG=%COPILOT_ROOT%"
if defined COPILOT_ROOT (
  rem O Windows interpreta "C:\\" como argumento com aspa escapada.
  rem Acrescente ponto apenas no argumento de caminhos que terminam em barra.
  if "%COPILOT_ROOT:~-1%"=="\" set "COPILOT_ROOT_ARG=%COPILOT_ROOT%."
)
:ask_screen
set "COPILOT_SCREEN="
choice /c SN /n /m "Permitir capturas da tela SOMENTE quando solicitadas na interface? [S/N] "
if errorlevel 2 goto :ask_apps
set "COPILOT_SCREEN=--copilot-screen"
:ask_apps
set "COPILOT_APPS="
choice /c SN /n /m "Permitir consultar nomes dos programas instalados e processos ativos? [S/N] "
if errorlevel 2 goto :ask_launch
set "COPILOT_APPS=--copilot-apps"
:ask_launch
set "COPILOT_LAUNCH="
echo Abrir programas exige outro clique de confirmacao no chat.
choice /c SN /n /m "Permitir ABERTURA confirmada do Bloco de Notas e Calculadora? [S/N] "
if errorlevel 2 goto :ask_edit
set "COPILOT_LAUNCH=--copilot-launch"
:ask_edit
set "COPILOT_EDIT="
if not defined COPILOT_ROOT goto :start
echo Edicao apenas de codigo em pasta autorizada, com diff e backup.
choice /c SN /n /m "Permitir editar CODIGO apos confirmacao manual de cada mudanca? [S/N] "
if errorlevel 2 goto :start
set "COPILOT_EDIT=--copilot-edit"
:start
echo.
echo Verificando requisitos do modelo...
%PYTHON_CMD% "tools\doctor_chat.py" --profile economia --probe
if errorlevel 1 (
  echo.
  echo Modelo ou runtime ausente. Prepare pelo instalador principal.
  echo Depois execute novamente INICIAR-COPILOTO-WINDOWS.bat.
  call "%~dp0INICIAR-BRAIN-SSD.bat"
  goto :end
)
echo.
echo Iniciando chat e copiloto local. A pesquisa web continua opt-in.
if defined COPILOT_ROOT (
  %PYTHON_CMD% "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow --web-search --web-provider auto --copilot-root "%COPILOT_ROOT_ARG%" %COPILOT_SCREEN% %COPILOT_APPS% %COPILOT_LAUNCH% %COPILOT_EDIT%
) else (
  %PYTHON_CMD% "tools\run_chat.py" --profile economia --episodic-memory --cognitive-shadow --web-search --web-provider auto %COPILOT_SCREEN% %COPILOT_APPS% %COPILOT_LAUNCH% %COPILOT_EDIT%
)
if errorlevel 1 (
  echo.
  echo Copiloto nao iniciou; consulte os erros anteriores.
  pause
)
:end
endlocal
