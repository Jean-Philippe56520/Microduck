@echo off
setlocal
cd /d "%~dp0"
echo Kwipi - simulation du ROLE de production candidat avec Qwen3.5 9B
echo Une photo volontairement autorisee. Aucun robot ni souvenir modifie.
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%~dp0scripts\kwipi-vision-test.ps1" -RolePreview
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Essai non concluant : aucun effet robot ou memoire.
echo Cette fenetre peut etre fermee.
pause >nul
exit /b %RESULT%