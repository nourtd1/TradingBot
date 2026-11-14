@echo off
rem =================================================================
rem  Recherche multi-marches - export de l'univers MetaTrader 5
rem  (forex, metaux, indices, energies, crypto : voir docs\RECHERCHE_PLAN.md
rem   et docs\RECHERCHE_PLAN_CYCLE2.md section 5)
rem  A lancer avec MetaTrader 5 OUVERT et CONNECTE au compte demo.
rem  Donnees : data\univers\ (ou le dossier donne par --dossier)
rem  Rapport detaille : logs\export_univers_*.txt
rem  Journal des lancements : logs\export_univers.log
rem  Options possibles, par exemple :
rem    EXPORTER_UNIVERS.bat --lister                 (liste les symboles du broker)
rem    EXPORTER_UNIVERS.bat --symboles EURUSD,US500  (seulement ces symboles)
rem    EXPORTER_UNIVERS.bat --annees 20 --annees-m15 6
rem    EXPORTER_UNIVERS.bat --dossier data\univers_monbroker   (un dossier par broker)
rem  Noms imposes : config\univers_symboles.json, section "forcer".
rem =================================================================
setlocal EnableExtensions
title Recherche multi-marches - Export de l'univers MetaTrader 5
cd /d "%~dp0"

set "VPY=%USERPROFILE%\.tradingbot\venv\Scripts\python.exe"
set "LOGDIR=%~dp0logs"
set "LOG=%~dp0logs\export_univers.log"

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
>>"%LOG%" echo.
>>"%LOG%" echo ===== Export de l'univers lance le %date% %time% =====
if not exist "%VPY%" goto :pas_installe

echo ============================================================
echo    Recherche multi-marches - export de l'univers MetaTrader 5
echo ============================================================
echo.
echo Laisse MetaTrader 5 ouvert et connecte pendant l'export.
echo Il y a jusqu'a une trentaine de marches, jusqu'a 20 ans d'historique :
echo la premiere fois, cela peut prendre de longues minutes,
echo car MetaTrader 5 telecharge l'historique chez le broker.
echo.

"%VPY%" "%~dp0scripts\exporter_univers_mt5.py" %*
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo Fin de l'export de l'univers - code %RC%

echo.
echo ============================================================
if "%RC%"=="0" echo    EXPORT TERMINE - au moins un marche par famille.
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
