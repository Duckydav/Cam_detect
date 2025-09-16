#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Logger configuré pour Cam_detect
Utilise loguru pour logging avancé avec rotation de fichiers
"""

import sys
from pathlib import Path
from loguru import logger

def setup_logger(log_level="INFO", log_file=None):
    """
    Configure le système de logging pour l'application

    Args:
        log_level (str): Niveau de log (DEBUG, INFO, WARNING, ERROR)
        log_file (str): Chemin vers le fichier de log (optionnel)

    Returns:
        logger: Instance configurée de loguru
    """
    # Supprimer la configuration par défaut
    logger.remove()

    # Configuration pour la console
    logger.add(
        sys.stdout,
        level=log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>",
        colorize=True
    )

    # Configuration pour le fichier si spécifié
    if log_file is None:
        # Chemin par défaut
        project_root = Path(__file__).parent.parent.parent
        log_dir = project_root / "logs"
        log_dir.mkdir(exist_ok=True)
        log_file = log_dir / "cam_detect.log"

    logger.add(
        str(log_file),
        level=log_level,
        format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
        rotation="10 MB",  # Rotation à 10MB
        retention="1 week", # Conserver 1 semaine
        compression="zip"   # Compression des anciens logs
    )

    logger.info(f"Logger initialisé - Niveau: {log_level}")
    logger.info(f"Fichier de log: {log_file}")

    return logger