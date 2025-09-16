#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Filtrage par zones d'intérêt (ROI) pour éliminer les faux positifs
Permet de définir des zones où ignorer les détections (arbres, etc.)
"""

import cv2
import numpy as np
from typing import List, Dict, Tuple, Optional
from loguru import logger
import json
from pathlib import Path

class ROIFilter:
    """Filtre les détections selon des zones d'intérêt définies"""

    def __init__(self, config: Dict):
        """
        Initialise le filtre ROI

        Args:
            config (dict): Configuration de l'application
        """
        self.config = config

        # Zones définies
        self.inclusion_zones = []  # Zones où ACCEPTER les détections
        self.exclusion_zones = []  # Zones où REJETER les détections (arbres)

        # État du filtre
        self.frame_width = 640
        self.frame_height = 480
        self.setup_mode = False

    def set_frame_dimensions(self, width: int, height: int):
        """Définit les dimensions de la frame"""
        self.frame_width = width
        self.frame_height = height
        logger.info(f"Dimensions ROI définies: {width}x{height}")

    def add_exclusion_zone(self, zone_name: str, polygon_points: List[Tuple[int, int]]):
        """
        Ajoute une zone d'exclusion (où ignorer les détections)

        Args:
            zone_name (str): Nom de la zone (ex: "arbre_gauche")
            polygon_points: Points du polygone définissant la zone
        """
        zone = {
            'name': zone_name,
            'type': 'exclusion',
            'polygon': polygon_points,
            'active': True
        }
        self.exclusion_zones.append(zone)
        logger.info(f"Zone d'exclusion ajoutée: {zone_name} avec {len(polygon_points)} points")

    def add_inclusion_zone(self, zone_name: str, polygon_points: List[Tuple[int, int]]):
        """
        Ajoute une zone d'inclusion (seule zone où accepter les détections)

        Args:
            zone_name (str): Nom de la zone (ex: "route_principale")
            polygon_points: Points du polygone définissant la zone
        """
        zone = {
            'name': zone_name,
            'type': 'inclusion',
            'polygon': polygon_points,
            'active': True
        }
        self.inclusion_zones.append(zone)
        logger.info(f"Zone d'inclusion ajoutée: {zone_name}")

    def add_predefined_road_zone(self):
        """Ajoute une zone de route typique (centre de l'image)"""
        # Zone rectangulaire au centre (typique pour route)
        road_zone = [
            (int(self.frame_width * 0.1), int(self.frame_height * 0.3)),   # Haut gauche
            (int(self.frame_width * 0.9), int(self.frame_height * 0.3)),   # Haut droite
            (int(self.frame_width * 0.9), int(self.frame_height * 0.8)),   # Bas droite
            (int(self.frame_width * 0.1), int(self.frame_height * 0.8))    # Bas gauche
        ]
        self.add_inclusion_zone("route_principale", road_zone)

    def add_predefined_tree_zones(self):
        """Ajoute des zones d'exclusion typiques pour arbres"""
        # Zone arbre gauche (exemple)
        tree_left = [
            (0, 0),
            (int(self.frame_width * 0.15), 0),
            (int(self.frame_width * 0.1), int(self.frame_height * 0.4)),
            (0, int(self.frame_height * 0.3))
        ]
        self.add_exclusion_zone("arbre_gauche", tree_left)

        # Zone arbre droite (exemple)
        tree_right = [
            (int(self.frame_width * 0.85), 0),
            (self.frame_width, 0),
            (self.frame_width, int(self.frame_height * 0.3)),
            (int(self.frame_width * 0.9), int(self.frame_height * 0.4))
        ]
        self.add_exclusion_zone("arbre_droite", tree_right)

    def filter_detections(self, detections: List[Dict]) -> List[Dict]:
        """
        Filtre les détections selon les zones définies

        Args:
            detections (List[Dict]): Détections brutes

        Returns:
            List[Dict]: Détections filtrées
        """
        if not self.inclusion_zones and not self.exclusion_zones:
            return detections

        filtered_detections = []

        for detection in detections:
            center = detection['center']
            detection_point = (int(center[0]), int(center[1]))

            # Vérifier les zones d'exclusion (arbres, etc.)
            is_excluded = False
            for zone in self.exclusion_zones:
                if zone['active'] and self._point_in_polygon(detection_point, zone['polygon']):
                    logger.debug(f"Détection exclue par zone: {zone['name']}")
                    is_excluded = True
                    break

            if is_excluded:
                continue

            # Vérifier les zones d'inclusion (si définies)
            if self.inclusion_zones:
                is_included = False
                for zone in self.inclusion_zones:
                    if zone['active'] and self._point_in_polygon(detection_point, zone['polygon']):
                        is_included = True
                        break

                if not is_included:
                    logger.debug("Détection hors zone d'inclusion")
                    continue

            # Ajouter métadonnées de filtrage
            detection['roi_filtered'] = True
            filtered_detections.append(detection)

        logger.debug(f"ROI: {len(detections)} → {len(filtered_detections)} détections")
        return filtered_detections

    def _point_in_polygon(self, point: Tuple[int, int], polygon: List[Tuple[int, int]]) -> bool:
        """
        Vérifie si un point est dans un polygone (algorithme ray casting)

        Args:
            point: Point à tester
            polygon: Points du polygone

        Returns:
            bool: True si le point est dans le polygone
        """
        x, y = point
        n = len(polygon)
        inside = False

        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y

        return inside

    def draw_zones(self, frame: np.ndarray) -> np.ndarray:
        """
        Dessine les zones ROI sur la frame

        Args:
            frame: Frame vidéo

        Returns:
            Frame avec zones dessinées
        """
        overlay = frame.copy()

        # Dessiner les zones d'exclusion en rouge
        for zone in self.exclusion_zones:
            if zone['active']:
                points = np.array(zone['polygon'], np.int32)
                cv2.fillPoly(overlay, [points], (0, 0, 255, 100))  # Rouge transparent
                cv2.polylines(frame, [points], True, (0, 0, 255), 2)

                # Label
                centroid = np.mean(points, axis=0).astype(int)
                cv2.putText(frame, f"EXCLUSION: {zone['name']}",
                           tuple(centroid), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 2)

        # Dessiner les zones d'inclusion en vert
        for zone in self.inclusion_zones:
            if zone['active']:
                points = np.array(zone['polygon'], np.int32)
                cv2.fillPoly(overlay, [points], (0, 255, 0, 50))   # Vert transparent
                cv2.polylines(frame, [points], True, (0, 255, 0), 2)

                # Label
                centroid = np.mean(points, axis=0).astype(int)
                cv2.putText(frame, f"INCLUSION: {zone['name']}",
                           tuple(centroid), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 2)

        # Mélanger l'overlay avec transparence
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

        return frame

    def save_zones(self, file_path: str):
        """Sauvegarde les zones dans un fichier JSON"""
        zones_data = {
            'frame_dimensions': [self.frame_width, self.frame_height],
            'inclusion_zones': self.inclusion_zones,
            'exclusion_zones': self.exclusion_zones
        }

        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(zones_data, f, indent=2)

        logger.info(f"Zones ROI sauvegardées: {file_path}")

    def load_zones(self, file_path: str):
        """Charge les zones depuis un fichier JSON"""
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                zones_data = json.load(f)

            self.frame_width, self.frame_height = zones_data['frame_dimensions']
            self.inclusion_zones = zones_data.get('inclusion_zones', [])
            self.exclusion_zones = zones_data.get('exclusion_zones', [])

            logger.info(f"Zones ROI chargées: {len(self.inclusion_zones)} inclusion, {len(self.exclusion_zones)} exclusion")

        except Exception as e:
            logger.error(f"Erreur chargement zones ROI: {e}")

    def get_statistics(self) -> Dict:
        """Retourne les statistiques des zones"""
        return {
            'inclusion_zones_count': len(self.inclusion_zones),
            'exclusion_zones_count': len(self.exclusion_zones),
            'active_inclusion_zones': len([z for z in self.inclusion_zones if z['active']]),
            'active_exclusion_zones': len([z for z in self.exclusion_zones if z['active']]),
            'frame_dimensions': [self.frame_width, self.frame_height]
        }

class MovementCoherenceFilter:
    """Filtre basé sur la cohérence du mouvement"""

    def __init__(self, min_movement_pixels: int = 5, max_jitter_pixels: int = 50):
        """
        Initialise le filtre de cohérence de mouvement

        Args:
            min_movement_pixels: Mouvement minimum pour être considéré comme réel
            max_jitter_pixels: Mouvement maximum pour filtrer les tremblements
        """
        self.min_movement = min_movement_pixels
        self.max_jitter = max_jitter_pixels
        self.detection_history = {}  # Track ID -> historique positions

    def update_detection_movement(self, track_id: int, position: Tuple[int, int]) -> bool:
        """
        Met à jour l'historique de mouvement d'une détection

        Args:
            track_id: ID du track
            position: Position actuelle

        Returns:
            bool: True si le mouvement est cohérent
        """
        if track_id not in self.detection_history:
            self.detection_history[track_id] = []

        history = self.detection_history[track_id]
        history.append(position)

        # Garder seulement les 10 dernières positions
        if len(history) > 10:
            history.pop(0)

        # Analyser la cohérence si assez d'historique
        if len(history) >= 3:
            return self._analyze_movement_coherence(history)

        return True  # Accepter par défaut pour nouveaux tracks

    def _analyze_movement_coherence(self, positions: List[Tuple[int, int]]) -> bool:
        """
        Analyse la cohérence d'un mouvement

        Args:
            positions: Historique des positions

        Returns:
            bool: True si mouvement cohérent
        """
        if len(positions) < 3:
            return True

        # Calculer les mouvements entre frames
        movements = []
        for i in range(1, len(positions)):
            dx = positions[i][0] - positions[i-1][0]
            dy = positions[i][1] - positions[i-1][1]
            movement_magnitude = (dx**2 + dy**2)**0.5
            movements.append(movement_magnitude)

        # Vérifications de cohérence
        avg_movement = np.mean(movements)
        movement_variance = np.var(movements)

        # Filtrer si mouvement trop erratique (feuilles qui tremblent)
        if movement_variance > self.max_jitter**2:
            logger.debug("Mouvement trop erratique - probablement végétation")
            return False

        # Filtrer si mouvement trop faible (objet statique mal détecté)
        if avg_movement < self.min_movement:
            logger.debug("Mouvement insuffisant - probablement faux positif")
            return False

        return True

class ContextualValidator:
    """Validateur contextuel pour éliminer les faux positifs"""

    def __init__(self):
        """Initialise le validateur contextuel"""
        self.ground_level_ratio = 0.7  # Ratio de hauteur pour le "sol"
        self.size_coherence_factor = 2.0  # Facteur de cohérence de taille

    def validate_detection(self, detection: Dict, frame_dimensions: Tuple[int, int]) -> bool:
        """
        Valide une détection selon le contexte

        Args:
            detection: Détection à valider
            frame_dimensions: Dimensions de la frame

        Returns:
            bool: True si détection valide
        """
        width, height = frame_dimensions
        bbox = detection['bbox']
        center = detection['center']
        class_name = detection['class_name']

        # Vérifications selon la classe
        if class_name in ['car', 'truck', 'bus']:
            return self._validate_vehicle(detection, frame_dimensions)
        elif class_name == 'person':
            return self._validate_person(detection, frame_dimensions)

        return True

    def _validate_vehicle(self, detection: Dict, frame_dimensions: Tuple[int, int]) -> bool:
        """Valide une détection de véhicule"""
        width, height = frame_dimensions
        bbox = detection['bbox']
        center = detection['center']

        # Les véhicules doivent être près du sol (partie basse de l'image)
        if center[1] < height * 0.4:  # Trop haut dans l'image
            logger.debug("Véhicule trop haut - probablement végétation")
            return False

        # Vérifier la taille cohérente
        obj_width = bbox[2] - bbox[0]
        obj_height = bbox[3] - bbox[1]

        # Ratio largeur/hauteur cohérent pour véhicules
        aspect_ratio = obj_width / obj_height if obj_height > 0 else 0
        if aspect_ratio < 0.8 or aspect_ratio > 4.0:  # Trop vertical ou horizontal
            logger.debug(f"Ratio d'aspect incohérent pour véhicule: {aspect_ratio}")
            return False

        return True

    def _validate_person(self, detection: Dict, frame_dimensions: Tuple[int, int]) -> bool:
        """Valide une détection de personne"""
        width, height = frame_dimensions
        bbox = detection['bbox']
        center = detection['center']

        # Les piétons doivent avoir un ratio hauteur/largeur cohérent
        obj_width = bbox[2] - bbox[0]
        obj_height = bbox[3] - bbox[1]

        aspect_ratio = obj_height / obj_width if obj_width > 0 else 0
        if aspect_ratio < 1.2 or aspect_ratio > 4.0:  # Pas assez vertical
            logger.debug(f"Ratio d'aspect incohérent pour personne: {aspect_ratio}")
            return False

        return True