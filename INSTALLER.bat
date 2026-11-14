@echo off
rem =================================================================
rem  TradingBot - installation de l'environnement Python (Windows)
rem  Idempotent : peut etre relance sans risque, met a jour les librairies.
rem  Journal : logs\installation.log et logs\pip.log
rem =================================================================
setlocal EnableExtensions
title TradingBot - Installation
cd /d "%~dp0"

set "HOMEBOT=%USERPROFILE%\.tradingbot"
set "VENV=%HOMEBOT%\venv"
set "VPY=%VENV%\Scripts\python.exe"
set "LOGDIR=%~dp0logs"
set "LOG=%~dp0logs\installation.log"
set "PYEXE="
set "PYARGS="

if not exist "%LOGDIR%" mkdir "%LOGDIR%"
>>"%LOG%" echo.
>>"%LOG%" echo ===== Installation lancee le %date% %time% =====

echo ============================================================
echo    TradingBot - installation de l'environnement Python
echo ============================================================

rem -----------------------------------------------------------------
rem 1. Trouver un Python 64 bits compatible, 3.12 de preference
rem    a. emplacements standard  b. lanceur py  c. python du PATH
rem -----------------------------------------------------------------
call :etape "Recherche de Python"
for %%V in (12 11 13 10) do (
    if not defined PYEXE if exist "%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe" set "PYEXE=%LOCALAPPDATA%\Programs\Python\Python3%%V\python.exe"
    if not defined PYEXE if exist "%ProgramFiles%\Python3%%V\python.exe" set "PYEXE=%ProgramFiles%\Python3%%V\python.exe"
    if not defined PYEXE if exist "%LOCALAPPDATA%\Python\pythoncore-3.%%V-64\python.exe" set "PYEXE=%LOCALAPPDATA%\Python\pythoncore-3.%%V-64\python.exe"
)
if defined PYEXE goto :verifier_python

for %%V in (12 11 13 10) do if not defined PYEXE call :essayer_py 3.%%V
if defined PYEXE goto :verifier_python

python -c "import sys" <nul >nul 2>&1
if errorlevel 1 goto :installer_python
set "PYEXE=python"

:verifier_python
"%PYEXE%" %PYARGS% -c "import sys; sys.exit(0 if (3, 10) <= sys.version_info[:2] <= (3, 13) and sys.maxsize > 2**32 else 1)" <nul >nul 2>&1
if errorlevel 1 goto :installer_python
echo Python retenu :
"%PYEXE%" %PYARGS% -c "import sys, platform; print('   ', platform.python_version(), '-', sys.executable)"
>>"%LOG%" echo Python retenu : %PYEXE% %PYARGS%

rem -----------------------------------------------------------------
rem 2. Environnement virtuel dans %USERPROFILE%\.tradingbot\venv
rem -----------------------------------------------------------------
if not exist "%HOMEBOT%" mkdir "%HOMEBOT%"
if not exist "%VPY%" goto :creer_venv
"%VPY%" -c "import sys" <nul >nul 2>&1
if not errorlevel 1 goto :venv_pret
call :etape "Environnement existant endommage : suppression puis recreation"
rmdir /s /q "%VENV%"

:creer_venv
call :etape "Creation de l'environnement virtuel dans %VENV%"
"%PYEXE%" %PYARGS% -m venv "%VENV%"
if errorlevel 1 goto :erreur

:venv_pret

rem -----------------------------------------------------------------
rem 3. Librairies
rem -----------------------------------------------------------------
call :etape "Mise a jour de pip"
"%VPY%" -m pip install --upgrade pip --disable-pip-version-check --log "%LOGDIR%\pip.log"
if errorlevel 1 echo Mise a jour de pip impossible - on continue avec la version actuelle.

call :etape "Installation des librairies - quelques minutes la premiere fois"
"%VPY%" -m pip install -r "%~dp0requirements.txt" --disable-pip-version-check --log "%LOGDIR%\pip.log"
if errorlevel 1 goto :erreur
"%VPY%" -m pip freeze --disable-pip-version-check > "%LOGDIR%\requirements.lock.txt"

rem -----------------------------------------------------------------
rem 4. Modele de fichier secret et raccourci sur le Bureau
rem -----------------------------------------------------------------
if not exist "%HOMEBOT%\.env" copy /y "%~dp0.env.example" "%HOMEBOT%\.env" >nul
powershell -NoProfile -ExecutionPolicy Bypass -Command "$s = (New-Object -ComObject WScript.Shell).CreateShortcut([IO.Path]::Combine([Environment]::GetFolderPath('Desktop'), 'TradingBot.lnk')); $s.TargetPath = '%~dp0'; $s.Save()" >nul 2>&1
if not errorlevel 1 echo Raccourci TradingBot cree sur le Bureau.

rem -----------------------------------------------------------------
rem 5. Verification complete
rem -----------------------------------------------------------------
call :etape "Verification complete de l'installation"
"%VPY%" "%~dp0scripts\check_env.py"
set "RC=%ERRORLEVEL%"
>>"%LOG%" echo Fin de l'installation - code de verification %RC%
echo.
echo ============================================================
if "%RC%"=="0" echo    INSTALLATION TERMINEE - tout est OK.
if not "%RC%"=="0" echo    Installation terminee, avec des points a regarder.
if not "%RC%"=="0" echo    Pas d'inquietude : dis-le a Claude, il lira le rapport.
echo ============================================================
echo.
pause
exit /b %RC%


rem =================================================================
rem  Sous-programmes
rem =================================================================
:etape
echo.
echo --- %~1
>>"%LOG%" echo [%time%] %~1
exit /b 0

:essayer_py
rem Teste "py -3.X". L'entree vient de nul : aucune question ne peut bloquer.
py -%1 -c "import sys" <nul >nul 2>&1
if errorlevel 1 exit /b 1
set "PYEXE=py"
set "PYARGS=-%1"
exit /b 0

:erreur
>>"%LOG%" echo ERREUR - l'etape precedente a echoue
echo.
echo [ERREUR] L'installation s'est arretee.
echo          Dis-le a Claude : il lira logs\installation.log et logs\pip.log.
echo.
pause
exit /b 1

:installer_python
>>"%LOG%" echo Aucun Python compatible trouve
echo.
echo [!!] Aucun Python 64 bits compatible - version 3.10 a 3.13 - n'a ete trouve.
where winget >nul 2>&1
if errorlevel 1 goto :python_manuel
echo.
choice /c ON /m "Installer Python 3.12 automatiquement maintenant"
if errorlevel 2 goto :python_manuel
winget install --exact --id Python.Python.3.12 --accept-package-agreements --accept-source-agreements
if errorlevel 1 goto :python_manuel
>>"%LOG%" echo Python 3.12 installe via winget
echo.
echo Python 3.12 est installe.
echo FERME cette fenetre, puis relance INSTALLER.bat pour continuer.
echo.
pause
exit /b 0

:python_manuel
>>"%LOG%" echo Installation manuelle de Python demandee
echo.
echo Installe Python 3.12 - 64 bits - depuis https://www.python.org/downloads/windows/
echo Pendant l'installation, coche la case "Add python.exe to PATH".
echo Puis relance INSTALLER.bat.
echo.
pause
exit /b 1
