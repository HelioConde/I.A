@echo off
setlocal
cd /d "%~dp0"
title Brain-SSD - Testes e pacote de diagnostico
echo.
echo BRAIN-SSD - Logs e testes locais (sem upload automatico)
echo Nao salvamos perguntas, respostas nem conteudo da memoria nos logs.
echo.
if exist ".venv\Scripts\python.exe" (
  ".venv\Scripts\python.exe" "tools\run_diagnostics.py"
) else (
  where py >nul 2>nul
  if not errorlevel 1 (
    py -3 "tools\run_diagnostics.py"
  ) else (
    python "tools\run_diagnostics.py"
  )
)
echo.
echo Abra o caminho do ZIP exibido acima e anexe o pacote a conversa.
echo Voce pode repetir os testes e guardar um historico local rotativo.
pause
endlocal
