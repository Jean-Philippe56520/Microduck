@echo off
setlocal
cd /d "%~dp0"
echo Kwipi - conseiller de sens, exploration et consequences possibles (v2 CANDIDAT)
echo Une photo approuvee, analyse locale par Qwen3.5 9B, aucun moteur ou souvenir.
powershell.exe -NoProfile -STA -ExecutionPolicy RemoteSigned -File "%~dp0scripts\kwipi-vision-test.ps1" -RolePreview -RoleV2
set "RESULT=%ERRORLEVEL%"
echo.
if not "%RESULT%"=="0" echo Essai incomplet/refuse, aucun effet robot ou memoire.
echo Cette fenetre peut etre fermee.
pause >nul
exit /b %RESULT%