@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" (
  set "PYTHON_CMD=.venv\Scripts\python.exe"
) else (
  set "PYTHON_CMD=py -3"
)
echo Avaliacao Luna: servidor esperado em http://127.0.0.1:8766
echo A pesquisa externa fica desativada. Para autoriza-la nesta execucao, use:
echo   %PYTHON_CMD% tools\run_luna_evaluation.py --allow-web
%PYTHON_CMD% tools\run_luna_evaluation.py
if errorlevel 1 (
  echo.
  echo O teste nao foi concluido. Veja a mensagem acima; nenhuma resposta foi simulada.
)
pause
endlocal
