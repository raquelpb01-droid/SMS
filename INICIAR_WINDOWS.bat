@echo off
setlocal
cd /d "%~dp0"
title Smart Bins - ESP32 e SAP simulados
 echo Preparando o Smart Bins. Na primeira vez, sera necessario acesso a internet.
where py >nul 2>&1
if errorlevel 1 (
    echo Python nao encontrado. Instale o Python 3.12 pelo site python.org.
    echo Na instalacao, marque Add python.exe to PATH e instale o Python Launcher.
    pause
    exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
    py -3 -m venv .venv
    if errorlevel 1 goto erro
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto erro
 echo O navegador abrira o aplicativo. Mantenha esta janela aberta durante o uso.
start "" "http://localhost:8501"
".venv\Scripts\python.exe" -m streamlit run app.py --server.headless true --browser.gatherUsageStats false
if errorlevel 1 goto erro
exit /b 0
:erro
 echo Nao foi possivel iniciar. Confira a mensagem acima e sua conexao com a internet.
pause
exit /b 1
