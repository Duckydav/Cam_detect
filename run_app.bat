@echo off
echo Lancement de Cam_detect...
echo.

REM Changer vers le repertoire du script
cd /d "%~dp0"

REM Verifier si Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou n'est pas dans le PATH
    echo Veuillez installer Python 3.8+ depuis https://python.org
    pause
    exit /b 1
)

REM Verifier si les dependances sont installees
python -c "import ultralytics, cv2, customtkinter" >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Les dependances ne sont pas installees
    echo Veuillez executer install_requirements.bat d'abord
    pause
    exit /b 1
)

REM Lancer l'application
echo Demarrage de l'application...
echo.
python src/main.py

if errorlevel 1 (
    echo.
    echo L'application s'est fermee avec une erreur
    pause
)