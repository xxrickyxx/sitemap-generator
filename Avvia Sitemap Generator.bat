@echo off
chcp 65001 > nul
title Sitemap Generator Pro - miamai.it
color 0B

echo.
echo  ================================================
echo    Sitemap Generator Pro - miamai.it
echo  ================================================
echo.

REM Cambia nella cartella dove si trova questo .bat
cd /d "%~dp0"

echo  [*] Chiudo eventuali processi Python precedenti su porta 8000...
for /f "tokens=5" %%a in ('netstat -ano 2^>nul ^| findstr ":8000 "') do (
    if not "%%a"=="0" (
        taskkill /PID %%a /F >nul 2>&1
    )
)

echo  [*] Attendo liberazione porta...
timeout /t 2 /nobreak >nul

echo  [*] Avvio il server...
echo.
echo  Il browser si aprira' su http://localhost:8000
echo.
echo  NON chiudere questa finestra mentre usi il programma.
echo  Per uscire: CTRL+C oppure chiudi questa finestra.
echo.
echo  ------------------------------------------------
echo.

python "%~dp0sitemap_generator.py"

echo.
echo  ================================================
echo  Server arrestato.
echo  ================================================
echo.
pause
