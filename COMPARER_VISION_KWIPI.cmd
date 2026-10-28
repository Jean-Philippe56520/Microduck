@echo off
setlocal
cd /d "%~dp0"
echo Kwipi - comparaison de deux consignes visuelles pour Qwen3.5 9B
echo La meme photo consentie sera analysee DEUX FOIS sur Ollama local uniquement.
echo Aucune photo ni sortie modele brute ne sera envoyee a GitHub.
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%~dp0scripts\kwipi-vision-test.ps1" -ComparePrompts
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Essai incomplet ou refuse; aucune memoire ni moteur.
echo Cette fenetre peut etre fermee.
pause >nul
exit /b %RESULT%