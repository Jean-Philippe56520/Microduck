@echo off
setlocal
cd /d "%~dp0"
echo Kwipi - verification du passage d'images a Qwen3.5 9B

echo Uniquement deux images synthetiques en memoire : rouge et bleu.
echo Aucune photo personnelle n'est ouverte ou enregistree.
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%~dp0scripts\kwipi-vision-test.ps1" -VisionCheck
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Diagnostic non concluant. Aucun changement moteur ni memoire.
echo Cette fenetre peut etre fermee. Aucun media n'est envoye a GitHub.
pause >nul
exit /b %RESULT%