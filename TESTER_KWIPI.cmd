@echo off
setlocal
cd /d "%~dp0"
echo Kwipi - essai visuel local avec Qwen3.5 9B
echo.
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%~dp0scripts\kwipi-vision-test.ps1"
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo L'essai n'a pas ete valide. Consulter le message ci-dessus.
echo Cette fenetre peut etre fermee. Aucune image n'est envoyee a GitHub.
pause >nul
exit /b %RESULT%