#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Gestionnaire de configuration pour Cam_detect
Charge et valide les fichiers de configuration YAML
"""

import yaml
from pathlib import Path
from loguru import logger

class ConfigManager:
    """Gestionnaire de configuration centralisé"""

    def __init__(self, config_file=None):
        """
        Initialise le gestionnaire de configuration

        Args:
            config_file (str): Chemin vers le fichier de configuration
        """
        if config_file is None:
            project_root = Path(__file__).parent.parent.parent
            self.config_file = project_root / "config" / "config.yaml"
        else:
            self.config_file = Path(config_file)

        self.config = None

    def load_config(self):
        """
        Charge la configuration depuis le fichier YAML

        Returns:
            dict: Configuration chargée
        """
        try:
            if not self.config_file.exists():
                logger.warning(f"Fichier de configuration non trouvé: {self.config_file}")
                return self._get_default_config()

            with open(self.config_file, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)

            logger.info(f"Configuration chargée depuis: {self.config_file}")
            self._validate_config()
            return self.config

        except yaml.YAMLError as e:
            logger.error(f"Erreur de parsing YAML: {e}")
            return self._get_default_config()
        except Exception as e:
            logger.error(f"Erreur lors du chargement de la configuration: {e}")
            return self._get_default_config()

    def _validate_config(self):
        """Valide la configuration chargée"""
        required_sections = ['model', 'detection_classes', 'video', 'gui']

        for section in required_sections:
            if section not in self.config:
                logger.warning(f"Section manquante dans la configuration: {section}")

        # Validation des chemins
        project_root = Path(__file__).parent.parent.parent

        if 'video' in self.config:
            for path_key in ['input_dir', 'output_dir', 'cache_dir']:
                if path_key in self.config['video']:
                    path = project_root / self.config['video'][path_key]
                    path.mkdir(parents=True, exist_ok=True)

    def _get_default_config(self):
        """
        Retourne une configuration par défaut

        Returns:
            dict: Configuration par défaut
        """
        logger.info("Utilisation de la configuration par défaut")

        return {
            'model': {
                'name': 'yolov8n.pt',
                'confidence': 0.5,
                'iou_threshold': 0.45,
                'device': 'auto'
            },
            'detection_classes': {
                'car': [2],
                'truck': [7],
                'bus': [5],
                'person': [0]
            },
            'video': {
                'input_dir': 'test_camera',
                'output_dir': 'data/output',
                'cache_dir': 'data/cache',
                'fps_analysis': 5,
                'resize_width': 640
            },
            'gui': {
                'theme': 'dark',
                'window_size': [1200, 800],
                'preview_size': [640, 480]
            },
            'logging': {
                'level': 'INFO',
                'file': 'logs/cam_detect.log'
            },
            'tracking': {
                'enabled': True,
                'method': 'bytetrack'
            }
        }

    def get(self, key_path, default=None):
        """
        Récupère une valeur de configuration par chemin de clés

        Args:
            key_path (str): Chemin vers la clé (ex: 'model.confidence')
            default: Valeur par défaut si la clé n'existe pas

        Returns:
            Valeur de configuration ou valeur par défaut
        """
        if self.config is None:
            self.load_config()

        keys = key_path.split('.')
        value = self.config

        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            logger.warning(f"Clé de configuration non trouvée: {key_path}")
            return default

    def update(self, key_path, value):
        """
        Met à jour une valeur de configuration

        Args:
            key_path (str): Chemin vers la clé
            value: Nouvelle valeur
        """
        if self.config is None:
            self.load_config()

        keys = key_path.split('.')
        config_ref = self.config

        # Naviguer jusqu'à l'avant-dernière clé
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]

        # Mettre à jour la valeur finale
        config_ref[keys[-1]] = value
        logger.info(f"Configuration mise à jour: {key_path} = {value}")

    def save_config(self, file_path=None):
        """
        Sauvegarde la configuration actuelle

        Args:
            file_path (str): Chemin de sauvegarde (optionnel)
        """
        if file_path is None:
            file_path = self.config_file

        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.config, f, default_flow_style=False, allow_unicode=True)
            logger.info(f"Configuration sauvegardée: {file_path}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")