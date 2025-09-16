#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cam_detect - Application principale d'analyse de circulation vidéo
Auteur: David François
Version: 1.0
"""

import sys
import os
import tkinter as tk
from pathlib import Path

# Ajouter le répertoire src au path Python
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root / "src"))

try:
    import customtkinter as ctk
    from gui.main_window import MainWindow
    from utils.logger import setup_logger
    from utils.config_manager import ConfigManager
except ImportError as e:
    print(f"Erreur d'import: {e}")
    print("Veuillez installer les dépendances avec: pip install -r requirements.txt")
    sys.exit(1)

# Configuration de l'application
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

def main():
    """Point d'entrée principal de l'application"""
    try:
        # Initialisation du logger
        logger = setup_logger()
        logger.info("Démarrage de Cam_detect")

        # Chargement de la configuration
        config_manager = ConfigManager()
        config = config_manager.load_config()

        # Création de l'application
        app = MainWindow(config)

        # Démarrage de l'interface
        logger.info("Lancement de l'interface utilisateur")
        app.run()

    except Exception as e:
        print(f"Erreur fatale: {e}")
        if 'logger' in locals():
            logger.error(f"Erreur fatale: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()