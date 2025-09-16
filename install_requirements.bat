@echo off
echo Installation des dependances pour Cam_detect...
echo.

REM Verifier si Python est installe
python --version >nul 2>&1
if errorlevel 1 (
    echo ERREUR: Python n'est pas installe ou n'est pas dans le PATH
    echo Veuillez installer Python 3.8+ depuis https://python.org
    pause
    exit /b 1
)

echo Python detecte. Installation des packages...
echo.

REM Mettre a jour pip
echo Mise a jour de pip...
python -m pip install --upgrade pip

REM Installer les dependances
echo Installation des dependances principales...
pip install -r requirements.txt

echo.
if errorlevel 1 (
    echo ERREUR: L'installation a echoue
    echo Verifiez votre connexion internet et reessayez
    pause
    exit /b 1
) else (
    echo Installation terminee avec succes!
    echo.
    echo Vous pouvez maintenant lancer l'application avec:
    echo python src/main.py
    echo.
)

pause