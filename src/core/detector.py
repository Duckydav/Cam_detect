#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Moteur de détection YOLOv8 pour Cam_detect
Détection d'objets optimisée pour l'analyse de circulation
"""

import cv2
import numpy as np
from pathlib import Path
from loguru import logger
from ultralytics import YOLO
import torch
from typing import Dict, List, Tuple, Optional

class TrafficDetector:
    """Détecteur YOLOv8 spécialisé pour l'analyse de circulation"""

    # Mapping des classes COCO vers nos catégories de trafic
    COCO_CLASSES = {
        'car': [2],           # car
        'truck': [7],         # truck
        'bus': [5],           # bus
        'person': [0],        # person
        'bicycle': [1],       # bicycle (optionnel)
        'motorcycle': [3]     # motorcycle (optionnel)
    }

    def __init__(self, config: Dict):
        """
        Initialise le détecteur YOLOv8

        Args:
            config (dict): Configuration du modèle
        """
        self.config = config
        self.model = None
        self.device = None
        self.class_names = []
        self.enabled_classes = set()

        # Statistiques de détection
        self.detection_stats = {
            'cars': 0,
            'trucks': 0,
            'buses': 0,
            'persons': 0,
            'total_frames': 0
        }

        self._setup_device()
        self._load_model()
        self._setup_classes()

    def _setup_device(self):
        """Configure le device (CPU/GPU) pour l'inférence"""
        device_config = self.config.get('model.device', 'auto')

        if device_config == 'auto':
            if torch.cuda.is_available():
                self.device = 'cuda:0'
                logger.info(f"GPU détecté: {torch.cuda.get_device_name(0)}")
            else:
                self.device = 'cpu'
                logger.info("GPU non disponible, utilisation du CPU")
        else:
            self.device = device_config

        logger.info(f"Device configuré: {self.device}")

    def _load_model(self):
        """Charge le modèle YOLOv8"""
        model_name = self.config.get('model.name', 'yolov8n.pt')

        try:
            logger.info(f"Chargement du modèle: {model_name}")
            self.model = YOLO(model_name)

            # Configurer le device
            if hasattr(self.model, 'to'):
                self.model.to(self.device)

            logger.info("Modèle YOLOv8 chargé avec succès")

        except Exception as e:
            logger.error(f"Erreur lors du chargement du modèle: {e}")
            raise RuntimeError(f"Impossible de charger le modèle YOLOv8: {e}")

    def _setup_classes(self):
        """Configure les classes à détecter"""
        detection_classes = self.config.get('detection_classes', {})

        for class_name, coco_ids in detection_classes.items():
            self.enabled_classes.update(coco_ids)
            logger.debug(f"Classe activée: {class_name} -> {coco_ids}")

        logger.info(f"Classes de détection configurées: {len(self.enabled_classes)} classes")

    def detect_objects(self, frame: np.ndarray, confidence: float = 0.5) -> List[Dict]:
        """
        Détecte les objets dans une frame

        Args:
            frame (np.ndarray): Frame vidéo à analyser
            confidence (float): Seuil de confiance minimum

        Returns:
            List[Dict]: Liste des détections avec coordonnées et classes
        """
        if self.model is None:
            logger.error("Modèle non chargé")
            return []

        try:
            # Configuration de l'inférence
            conf_threshold = confidence
            iou_threshold = self.config.get('model.iou_threshold', 0.45)

            # Inférence YOLOv8
            results = self.model(
                frame,
                conf=conf_threshold,
                iou=iou_threshold,
                device=self.device,
                verbose=False
            )

            detections = []

            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Extraire les données de détection
                        coords = box.xyxy[0].cpu().numpy()  # x1, y1, x2, y2
                        conf = float(box.conf[0].cpu().numpy())
                        class_id = int(box.cls[0].cpu().numpy())

                        # Filtrer par classes activées
                        if class_id in self.enabled_classes:
                            detection = {
                                'bbox': coords.tolist(),  # [x1, y1, x2, y2]
                                'confidence': conf,
                                'class_id': class_id,
                                'class_name': self._get_class_name(class_id),
                                'center': [
                                    (coords[0] + coords[2]) / 2,
                                    (coords[1] + coords[3]) / 2
                                ]
                            }
                            detections.append(detection)

            # Mettre à jour les statistiques
            self._update_stats(detections)

            logger.debug(f"Détections: {len(detections)} objets trouvés")
            return detections

        except Exception as e:
            logger.error(f"Erreur lors de la détection: {e}")
            return []

    def _get_class_name(self, class_id: int) -> str:
        """
        Convertit un ID de classe COCO en nom de catégorie trafic

        Args:
            class_id (int): ID de la classe COCO

        Returns:
            str: Nom de la catégorie de trafic
        """
        class_mapping = {
            0: 'person',      # Piéton
            1: 'bicycle',     # Vélo
            2: 'car',         # Voiture
            3: 'motorcycle',  # Moto
            5: 'bus',         # Bus/Gros camion
            7: 'truck'        # Camion
        }

        return class_mapping.get(class_id, f'class_{class_id}')

    def _update_stats(self, detections: List[Dict]):
        """Met à jour les statistiques de détection"""
        self.detection_stats['total_frames'] += 1

        for detection in detections:
            class_name = detection['class_name']
            if class_name == 'car':
                self.detection_stats['cars'] += 1
            elif class_name == 'truck':
                self.detection_stats['trucks'] += 1
            elif class_name == 'bus':
                self.detection_stats['buses'] += 1
            elif class_name == 'person':
                self.detection_stats['persons'] += 1

    def detect_persons_with_dogs(self, detections: List[Dict]) -> List[Dict]:
        """
        Analyse avancée pour détecter les piétons avec chiens

        Args:
            detections (List[Dict]): Détections de base

        Returns:
            List[Dict]: Détections enrichies avec classification piéton/chien
        """
        persons_with_dogs = []

        # Rechercher les paires personne-chien proches
        persons = [d for d in detections if d['class_name'] == 'person']

        # TODO: Implémenter détection de chiens (classe non standard COCO)
        # Logique possible:
        # 1. Utiliser un modèle spécialisé pour animaux
        # 2. Analyser les objets proches des piétons
        # 3. Utiliser l'analyse de forme/mouvement

        for person in persons:
            # Analyse simplifiée - dans une vraie implémentation,
            # on utiliserait un modèle séparé ou des heuristiques avancées
            person_copy = person.copy()
            person_copy['has_dog'] = False  # Placeholder
            persons_with_dogs.append(person_copy)

        return persons_with_dogs

    def draw_detections(self, frame: np.ndarray, detections: List[Dict]) -> np.ndarray:
        """
        Dessine les détections sur la frame

        Args:
            frame (np.ndarray): Frame vidéo
            detections (List[Dict]): Liste des détections

        Returns:
            np.ndarray: Frame avec détections dessinées
        """
        frame_copy = frame.copy()

        # Couleurs par classe
        colors = {
            'car': (0, 255, 0),        # Vert
            'truck': (255, 0, 0),      # Rouge
            'bus': (255, 165, 0),      # Orange
            'person': (255, 255, 0),   # Jaune
            'bicycle': (0, 255, 255),  # Cyan
            'motorcycle': (255, 0, 255) # Magenta
        }

        for detection in detections:
            bbox = detection['bbox']
            class_name = detection['class_name']
            confidence = detection['confidence']

            # Coordonnées du rectangle
            x1, y1, x2, y2 = map(int, bbox)

            # Couleur selon la classe
            color = colors.get(class_name, (128, 128, 128))

            # Dessiner le rectangle
            cv2.rectangle(frame_copy, (x1, y1), (x2, y2), color, 2)

            # Label avec classe et confiance
            label = f"{class_name}: {confidence:.2f}"
            label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]

            # Fond du label
            cv2.rectangle(
                frame_copy,
                (x1, y1 - label_size[1] - 10),
                (x1 + label_size[0], y1),
                color,
                -1
            )

            # Texte du label
            cv2.putText(
                frame_copy,
                label,
                (x1, y1 - 5),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

        return frame_copy

    def get_statistics(self) -> Dict:
        """
        Retourne les statistiques de détection

        Returns:
            Dict: Statistiques complètes
        """
        stats = self.detection_stats.copy()

        if stats['total_frames'] > 0:
            stats['cars_per_frame'] = stats['cars'] / stats['total_frames']
            stats['trucks_per_frame'] = stats['trucks'] / stats['total_frames']
            stats['buses_per_frame'] = stats['buses'] / stats['total_frames']
            stats['persons_per_frame'] = stats['persons'] / stats['total_frames']
        else:
            stats.update({
                'cars_per_frame': 0,
                'trucks_per_frame': 0,
                'buses_per_frame': 0,
                'persons_per_frame': 0
            })

        return stats

    def reset_statistics(self):
        """Remet à zéro les statistiques"""
        self.detection_stats = {
            'cars': 0,
            'trucks': 0,
            'buses': 0,
            'persons': 0,
            'total_frames': 0
        }
        logger.info("Statistiques remises à zéro")

    def set_enabled_classes(self, class_selection: Dict[str, bool]):
        """
        Configure les classes actives selon la sélection utilisateur

        Args:
            class_selection (Dict[str, bool]): Classes sélectionnées dans l'UI
        """
        self.enabled_classes.clear()

        class_mapping = {
            'Voitures': self.COCO_CLASSES['car'],
            'Camions': self.COCO_CLASSES['truck'],
            'Bus/Gros camions': self.COCO_CLASSES['bus'],
            'Piétons': self.COCO_CLASSES['person']
        }

        for ui_name, enabled in class_selection.items():
            if enabled and ui_name in class_mapping:
                self.enabled_classes.update(class_mapping[ui_name])

        logger.info(f"Classes actives: {self.enabled_classes}")

    def __del__(self):
        """Nettoyage lors de la destruction"""
        if hasattr(self, 'model') and self.model:
            del self.model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
        logger.debug("Détecteur nettoyé")