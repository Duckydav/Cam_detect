#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Classificateur avancé pour Cam_detect
Logique de classification spécialisée pour l'analyse de circulation
"""

import cv2
import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
from dataclasses import dataclass
from sklearn.cluster import DBSCAN
import math

@dataclass
class VehicleClassification:
    """Classification détaillée d'un véhicule"""
    base_class: str  # car, truck, bus
    size_category: str  # small, medium, large, extra_large
    estimated_length: float  # En mètres
    confidence: float
    special_attributes: List[str]  # trailer, emergency, etc.

@dataclass
class PersonClassification:
    """Classification détaillée d'une personne"""
    base_class: str = "person"
    has_companion: bool = False
    companion_type: Optional[str] = None  # dog, bicycle, stroller, etc.
    group_size: int = 1
    confidence: float = 0.0
    special_attributes: List[str] = None

    def __post_init__(self):
        if self.special_attributes is None:
            self.special_attributes = []

class AdvancedClassifier:
    """Classificateur avancé pour analyse de circulation détaillée"""

    # Tailles de véhicules en pixels (approximatives pour résolution 640px de largeur)
    VEHICLE_SIZE_THRESHOLDS = {
        'car': {'min_area': 800, 'max_area': 4000, 'aspect_ratio': (1.5, 3.0)},
        'truck': {'min_area': 2000, 'max_area': 8000, 'aspect_ratio': (1.2, 4.0)},
        'bus': {'min_area': 4000, 'max_area': 15000, 'aspect_ratio': (2.0, 5.0)}
    }

    # Seuils pour classification de taille
    SIZE_CATEGORIES = {
        'small': (0, 1500),
        'medium': (1500, 4000),
        'large': (4000, 8000),
        'extra_large': (8000, float('inf'))
    }

    def __init__(self, config: Dict):
        """
        Initialise le classificateur avancé

        Args:
            config (dict): Configuration de l'application
        """
        self.config = config
        self.frame_width = 640  # Largeur de référence
        self.frame_height = 480  # Hauteur de référence

        # Historique pour analyse temporelle
        self.detection_history = {}
        self.group_analyzer = PersonGroupAnalyzer()

    def classify_vehicle(self, detection: Dict, frame: np.ndarray = None) -> VehicleClassification:
        """
        Classification avancée d'un véhicule

        Args:
            detection (Dict): Détection de base YOLOv8
            frame (np.ndarray): Frame pour analyse visuelle (optionnel)

        Returns:
            VehicleClassification: Classification détaillée
        """
        base_class = detection['class_name']
        bbox = detection['bbox']
        confidence = detection['confidence']

        # Calculer les dimensions
        width = bbox[2] - bbox[0]
        height = bbox[3] - bbox[1]
        area = width * height
        aspect_ratio = width / height if height > 0 else 1.0

        # Classification de taille
        size_category = self._get_size_category(area)

        # Estimation de la longueur réelle (approximative)
        estimated_length = self._estimate_vehicle_length(base_class, area, aspect_ratio)

        # Détection d'attributs spéciaux
        special_attributes = []

        if frame is not None:
            special_attributes = self._detect_vehicle_attributes(detection, frame)

        # Affiner la classification selon les dimensions
        refined_class = self._refine_vehicle_class(base_class, area, aspect_ratio)

        return VehicleClassification(
            base_class=refined_class,
            size_category=size_category,
            estimated_length=estimated_length,
            confidence=confidence,
            special_attributes=special_attributes
        )

    def classify_person(self, detection: Dict, frame: np.ndarray = None,
                       all_detections: List[Dict] = None) -> PersonClassification:
        """
        Classification avancée d'une personne

        Args:
            detection (Dict): Détection de base YOLOv8
            frame (np.ndarray): Frame pour analyse visuelle
            all_detections (List[Dict]): Toutes les détections de la frame

        Returns:
            PersonClassification: Classification détaillée
        """
        confidence = detection['confidence']
        center = detection['center']
        bbox = detection['bbox']

        # Analyser les compagnons proches
        companion_info = self._detect_companions(detection, all_detections, frame)

        # Analyser les groupes de personnes
        group_info = self._analyze_person_groups(detection, all_detections)

        # Détection d'attributs spéciaux
        special_attributes = []
        if frame is not None:
            special_attributes = self._detect_person_attributes(detection, frame)

        return PersonClassification(
            base_class="person",
            has_companion=companion_info['has_companion'],
            companion_type=companion_info['type'],
            group_size=group_info['size'],
            confidence=confidence,
            special_attributes=special_attributes
        )

    def _get_size_category(self, area: float) -> str:
        """Détermine la catégorie de taille selon l'aire"""
        for category, (min_area, max_area) in self.SIZE_CATEGORIES.items():
            if min_area <= area < max_area:
                return category
        return 'unknown'

    def _estimate_vehicle_length(self, vehicle_class: str, area: float, aspect_ratio: float) -> float:
        """
        Estime la longueur réelle d'un véhicule

        Args:
            vehicle_class (str): Type de véhicule
            area (float): Aire en pixels
            aspect_ratio (float): Ratio largeur/hauteur

        Returns:
            float: Longueur estimée en mètres
        """
        # Approximations basées sur les tailles typiques et la perspective
        base_lengths = {
            'car': 4.5,      # Voiture moyenne: 4.5m
            'truck': 8.0,    # Camion: 8m
            'bus': 12.0      # Bus: 12m
        }

        base_length = base_lengths.get(vehicle_class, 5.0)

        # Facteur de correction selon l'aire (perspective)
        area_factor = min(area / 3000, 2.0)  # Normaliser par rapport à une aire de référence

        # Facteur de correction selon l'aspect ratio
        ratio_factor = min(aspect_ratio / 2.0, 1.5)

        estimated_length = base_length * area_factor * ratio_factor

        return round(estimated_length, 1)

    def _refine_vehicle_class(self, base_class: str, area: float, aspect_ratio: float) -> str:
        """
        Affine la classification de véhicule selon les dimensions

        Args:
            base_class (str): Classe de base
            area (float): Aire
            aspect_ratio (float): Ratio

        Returns:
            str: Classe affinée
        """
        # Si c'est classé comme voiture mais très grand, c'est probablement un truck
        if base_class == 'car' and area > 5000:
            return 'truck'

        # Si c'est classé comme truck mais très long, c'est probablement un bus
        if base_class == 'truck' and aspect_ratio > 3.5:
            return 'bus'

        # Si c'est classé comme bus mais petit, c'est probablement un truck
        if base_class == 'bus' and area < 3000:
            return 'truck'

        return base_class

    def _detect_vehicle_attributes(self, detection: Dict, frame: np.ndarray) -> List[str]:
        """
        Détecte les attributs spéciaux d'un véhicule

        Args:
            detection (Dict): Détection
            frame (np.ndarray): Frame

        Returns:
            List[str]: Liste d'attributs détectés
        """
        attributes = []
        bbox = detection['bbox']

        # Extraire la région du véhicule
        x1, y1, x2, y2 = map(int, bbox)
        vehicle_roi = frame[y1:y2, x1:x2]

        if vehicle_roi.size == 0:
            return attributes

        # Détection de remorque (par analyse de forme allongée)
        width = x2 - x1
        height = y2 - y1
        if width / height > 4.0:
            attributes.append('trailer')

        # Détection de couleurs dominantes (pour véhicules d'urgence)
        dominant_colors = self._get_dominant_colors(vehicle_roi)
        if any(color in ['red', 'blue', 'yellow'] for color in dominant_colors):
            attributes.append('emergency_colors')

        return attributes

    def _detect_companions(self, person_detection: Dict, all_detections: List[Dict],
                          frame: np.ndarray = None) -> Dict:
        """
        Détecte les compagnons proches d'une personne

        Args:
            person_detection (Dict): Détection de la personne
            all_detections (List[Dict]): Toutes les détections
            frame (np.ndarray): Frame pour analyse

        Returns:
            Dict: Informations sur les compagnons
        """
        if not all_detections:
            return {'has_companion': False, 'type': None}

        person_center = person_detection['center']
        companion_distance_threshold = 80  # pixels

        # Chercher des objets proches
        nearby_objects = []

        for detection in all_detections:
            if detection == person_detection:
                continue

            other_center = detection['center']
            distance = math.sqrt((person_center[0] - other_center[0])**2 +
                               (person_center[1] - other_center[1])**2)

            if distance < companion_distance_threshold:
                nearby_objects.append({
                    'detection': detection,
                    'distance': distance
                })

        # Analyser les objets proches
        companion_info = {'has_companion': False, 'type': None}

        for nearby in nearby_objects:
            obj_class = nearby['detection']['class_name']

            # Autre personne = groupe
            if obj_class == 'person':
                companion_info['has_companion'] = True
                companion_info['type'] = 'person'

            # Vélo proche = cycliste
            elif obj_class == 'bicycle':
                companion_info['has_companion'] = True
                companion_info['type'] = 'bicycle'

        # Détection de chien par analyse d'image (approximative)
        if frame is not None and not companion_info['has_companion']:
            has_dog = self._detect_dog_companion(person_detection, frame)
            if has_dog:
                companion_info['has_companion'] = True
                companion_info['type'] = 'dog'

        return companion_info

    def _detect_dog_companion(self, person_detection: Dict, frame: np.ndarray) -> bool:
        """
        Détection approximative d'un chien accompagnant une personne

        Args:
            person_detection (Dict): Détection de la personne
            frame (np.ndarray): Frame

        Returns:
            bool: True si chien détecté
        """
        # Cette méthode est approximative - dans une vraie implémentation,
        # on utiliserait un modèle spécialisé pour les animaux

        bbox = person_detection['bbox']
        x1, y1, x2, y2 = map(int, bbox)

        # Élargir la zone de recherche autour de la personne
        search_margin = 50
        search_x1 = max(0, x1 - search_margin)
        search_y1 = max(0, y1 - search_margin)
        search_x2 = min(frame.shape[1], x2 + search_margin)
        search_y2 = min(frame.shape[0], y2 + search_margin)

        search_area = frame[search_y1:search_y2, search_x1:search_x2]

        if search_area.size == 0:
            return False

        # Heuristique simple: chercher des formes sombres et basses près des pieds
        # Dans une vraie implémentation, on utiliserait un CNN spécialisé

        # Analyser la partie basse de la zone de recherche
        bottom_area = search_area[int(search_area.shape[0] * 0.7):, :]

        if bottom_area.size == 0:
            return False

        # Chercher des blobs sombres de taille appropriée
        gray = cv2.cvtColor(bottom_area, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 100, 255, cv2.THRESH_BINARY_INV)

        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

        for contour in contours:
            area = cv2.contourArea(contour)
            # Taille approximative d'un chien en pixels
            if 200 < area < 2000:
                # Vérifications supplémentaires possibles:
                # - Ratio d'aspect approprié
                # - Position par rapport à la personne
                # - Analyse de texture/couleur
                return True

        return False

    def _analyze_person_groups(self, person_detection: Dict, all_detections: List[Dict]) -> Dict:
        """
        Analyse les groupes de personnes

        Args:
            person_detection (Dict): Détection de la personne
            all_detections (List[Dict]): Toutes les détections

        Returns:
            Dict: Informations sur le groupe
        """
        if not all_detections:
            return {'size': 1, 'type': 'individual'}

        # Utiliser l'analyseur de groupes
        return self.group_analyzer.analyze_group(person_detection, all_detections)

    def _detect_person_attributes(self, detection: Dict, frame: np.ndarray) -> List[str]:
        """
        Détecte les attributs spéciaux d'une personne

        Args:
            detection (Dict): Détection
            frame (np.ndarray): Frame

        Returns:
            List[str]: Liste d'attributs
        """
        attributes = []
        bbox = detection['bbox']

        # Extraire la région de la personne
        x1, y1, x2, y2 = map(int, bbox)
        person_roi = frame[y1:y2, x1:x2]

        if person_roi.size == 0:
            return attributes

        # Analyse de couleurs pour vêtements haute visibilité
        dominant_colors = self._get_dominant_colors(person_roi)
        if any(color in ['yellow', 'orange', 'bright_green'] for color in dominant_colors):
            attributes.append('high_visibility')

        # Analyse de forme pour détection d'objets portés
        height = y2 - y1
        width = x2 - x1
        if width / height > 1.3:  # Personne très large = porte quelque chose
            attributes.append('carrying_object')

        return attributes

    def _get_dominant_colors(self, roi: np.ndarray) -> List[str]:
        """
        Extrait les couleurs dominantes d'une région

        Args:
            roi (np.ndarray): Région d'intérêt

        Returns:
            List[str]: Couleurs dominantes
        """
        if roi.size == 0:
            return []

        # Redimensionner pour accélérer le traitement
        roi_small = cv2.resize(roi, (50, 50))

        # Convertir en HSV pour meilleure analyse des couleurs
        hsv = cv2.cvtColor(roi_small, cv2.COLOR_BGR2HSV)

        # Analyser les plages de couleurs
        color_ranges = {
            'red': [(0, 50, 50), (10, 255, 255)],
            'blue': [(100, 50, 50), (130, 255, 255)],
            'green': [(40, 50, 50), (80, 255, 255)],
            'yellow': [(20, 50, 50), (40, 255, 255)],
            'orange': [(10, 50, 50), (20, 255, 255)]
        }

        dominant_colors = []

        for color_name, (lower, upper) in color_ranges.items():
            mask = cv2.inRange(hsv, np.array(lower), np.array(upper))
            if np.sum(mask) > roi_small.size * 0.1:  # Au moins 10% de la région
                dominant_colors.append(color_name)

        return dominant_colors

    def get_classification_summary(self, detections: List[Dict],
                                 frame: np.ndarray = None) -> Dict:
        """
        Génère un résumé des classifications pour une frame

        Args:
            detections (List[Dict]): Détections de la frame
            frame (np.ndarray): Frame pour analyse

        Returns:
            Dict: Résumé des classifications
        """
        summary = {
            'vehicles': {'total': 0, 'by_type': {}, 'by_size': {}},
            'persons': {'total': 0, 'with_companions': 0, 'in_groups': 0},
            'special_cases': []
        }

        for detection in detections:
            class_name = detection['class_name']

            if class_name in ['car', 'truck', 'bus']:
                vehicle_class = self.classify_vehicle(detection, frame)
                summary['vehicles']['total'] += 1

                # Par type
                if vehicle_class.base_class not in summary['vehicles']['by_type']:
                    summary['vehicles']['by_type'][vehicle_class.base_class] = 0
                summary['vehicles']['by_type'][vehicle_class.base_class] += 1

                # Par taille
                if vehicle_class.size_category not in summary['vehicles']['by_size']:
                    summary['vehicles']['by_size'][vehicle_class.size_category] = 0
                summary['vehicles']['by_size'][vehicle_class.size_category] += 1

            elif class_name == 'person':
                person_class = self.classify_person(detection, frame, detections)
                summary['persons']['total'] += 1

                if person_class.has_companion:
                    summary['persons']['with_companions'] += 1

                    # Cas spéciaux
                    if person_class.companion_type == 'dog':
                        summary['special_cases'].append({
                            'type': 'person_with_dog',
                            'confidence': person_class.confidence,
                            'position': detection['center']
                        })

                if person_class.group_size > 1:
                    summary['persons']['in_groups'] += 1

        return summary

class PersonGroupAnalyzer:
    """Analyseur spécialisé pour les groupes de personnes"""

    def __init__(self, max_group_distance: float = 60):
        """
        Initialise l'analyseur de groupes

        Args:
            max_group_distance (float): Distance max entre membres d'un groupe
        """
        self.max_group_distance = max_group_distance

    def analyze_group(self, person_detection: Dict, all_detections: List[Dict]) -> Dict:
        """
        Analyse si une personne fait partie d'un groupe

        Args:
            person_detection (Dict): Détection de la personne
            all_detections (List[Dict]): Toutes les détections

        Returns:
            Dict: Informations sur le groupe
        """
        # Récupérer toutes les personnes
        persons = [d for d in all_detections if d['class_name'] == 'person']

        if len(persons) <= 1:
            return {'size': 1, 'type': 'individual'}

        # Créer une matrice de distances
        person_positions = [p['center'] for p in persons]

        # Utiliser DBSCAN pour identifier les clusters
        if len(person_positions) >= 2:
            clustering = DBSCAN(eps=self.max_group_distance, min_samples=2)
            person_array = np.array(person_positions)
            clusters = clustering.fit_predict(person_array)

            # Trouver le cluster de la personne actuelle
            person_idx = persons.index(person_detection)
            cluster_id = clusters[person_idx]

            if cluster_id != -1:  # Pas de bruit
                group_size = np.sum(clusters == cluster_id)
                group_type = self._classify_group_type(group_size)

                return {
                    'size': int(group_size),
                    'type': group_type,
                    'cluster_id': int(cluster_id)
                }

        return {'size': 1, 'type': 'individual'}

    def _classify_group_type(self, size: int) -> str:
        """
        Classifie le type de groupe selon la taille

        Args:
            size (int): Taille du groupe

        Returns:
            str: Type de groupe
        """
        if size == 1:
            return 'individual'
        elif size == 2:
            return 'pair'
        elif size <= 4:
            return 'small_group'
        elif size <= 8:
            return 'medium_group'
        else:
            return 'large_group'