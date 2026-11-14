@echo off
rem =================================================================
rem  TradingBot - relance la verification de l'environnement.
rem  Le rapport est enregistre dans logs\ pour que Claude puisse le lire.
rem =================================================================
setlocal EnableExtensions
title TradingBot - Verification
cd /d "%~dp0"

set "VPY=%USERPROFILE%\.tradingbot\venv\Scripts\python.exe"
if not exist "%VPY%" goto :pas_installe

"%VPY%" "%~dp0scripts\check_env.py"
echo.
pause
exit /b 0

:pas_installe
echo L'environnement n'est pas encore installe : lance d'abord INSTALLER.bat
echo.
pause
exit /b 1
