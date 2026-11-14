@echo off
rem =================================================================
rem  SentiTrade - export de l'historique MetaTrader 5 pour le backtest
rem  A lancer avec MetaTrader 5 OUVERT et CONNECTE au compte demo.
rem  Donnees : data\mt5\   Rapport detaille : logs\export_mt5_*.txt
rem  Journal des lancements : logs\export_donnees.log
rem  Options possibles, par exemple : EXPORTER_DONNEES.bat --symbole XAUUSD.p --annees 3
rem =================================================================
setlocal EnableExtensions
title SentiTrade - Export des donnees MetaTrader 5
cd /d "%~dp0"

set "VPY=%USERPROFILE%\.tradingbot\venv\Scripts\python.exe"
set "LOGDIR=%~dp0logs"
set "LOG=%~dp0logs\export_donnees.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
>>"%LOG%" echo.
>>"%LOG%" echo ===== Export lance le %date% %time% =====
if not exist "%VPY%" goto :pas_installe

echo ============================================================
echo    SentiTrade - export de l'historique MetaTrader 5
echo ============================================================
echo.
echo Laisse MetaTrader 5 ouvert et connecte pendant l'export.
echo La premiere fois, cela peut prendre plusieurs minutes :
echo MetaTrader 5 telecharge l'historique chez le broker.
echo.

"%VPY%" "%~dp0scripts\exporter_donnees_mt5.py" %*
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo Fin de l'export - code %RC%

echo.
echo ============================================================
if "%RC%"=="0" echo    EXPORT TERMINE - tout est OK.
if not "%RC%"=="0" echo    Export termine avec des points a regarder, ou interrompu.
if not "%RC%"=="0" echo    Pas d'inquietude : dis-le a Claude, il lira le rapport dans logs.
echo ============================================================
echo.
pause
exit /b %RC%

:pas_installe
>>"%LOG%" echo Environnement Python absent - INSTALLER.bat pas encore lance
echo L'environnement Python n'est pas encore installe : lance d'abord INSTALLER.bat
echo.
pause
exit /b 1
