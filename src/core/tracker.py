#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Système de tracking multi-objets pour Cam_detect
Suivi des véhicules et piétons à travers les frames vidéo
"""

import numpy as np
from typing import Dict, List, Tuple, Optional
from loguru import logger
import cv2
from dataclasses import dataclass, field
from collections import deque
import math
import time

@dataclass
class TrackedObject:
    """Classe représentant un objet suivi"""
    track_id: int
    class_name: str
    class_id: int
    confidence: float
    bbox: List[float]  # [x1, y1, x2, y2]
    center: List[float]  # [x, y]

    # Historique de tracking
    positions: deque = field(default_factory=lambda: deque(maxlen=30))
    confidences: deque = field(default_factory=lambda: deque(maxlen=30))
    frame_history: deque = field(default_factory=lambda: deque(maxlen=30))

    # Métadonnées de tracking
    first_seen_frame: int = 0
    last_seen_frame: int = 0
    frames_tracked: int = 0
    frames_lost: int = 0
    max_frames_lost: int = 10

    # Propriétés calculées
    velocity: Tuple[float, float] = (0.0, 0.0)
    direction: float = 0.0  # En degrés

    # États spéciaux
    is_active: bool = True
    has_crossed_line: bool = False
    entry_point: Optional[str] = None
    exit_point: Optional[str] = None

class MultiObjectTracker:
    """Tracker multi-objets pour analyse de circulation"""

    def __init__(self, config: Dict):
        """
        Initialise le tracker

        Args:
            config (dict): Configuration du tracking
        """
        self.config = config

        # Paramètres de tracking
        self.max_distance = 100.0  # Distance max pour association
        self.min_track_length = 5   # Minimum de frames pour valider un track
        self.max_frames_lost = 10   # Maximum de frames perdues avant suppression

        # État du tracker
        self.tracked_objects: Dict[int, TrackedObject] = {}
        self.next_track_id = 1
        self.frame_count = 0

        # Statistiques de tracking
        self.total_tracks_created = 0
        self.total_tracks_completed = 0
        self.crossing_counts = {'north': 0, 'south': 0, 'east': 0, 'west': 0}

        # Zone de détection et lignes de comptage
        self.detection_zone = None
        self.counting_lines = []

        self._setup_tracking_zones()

    def _setup_tracking_zones(self):
        """Configure les zones de tracking et lignes de comptage"""
        zone_config = self.config.get('detection_zone', {})

        if zone_config.get('enabled', False):
            self.detection_zone = {
                'x1': zone_config.get('x1', 0),
                'y1': zone_config.get('y1', 0),
                'x2': zone_config.get('x2', 1920),
                'y2': zone_config.get('y2', 1080)
            }

        # Lignes de comptage par défaut (au centre de l'écran)
        width = zone_config.get('x2', 1920) - zone_config.get('x1', 0)
        height = zone_config.get('y2', 1080) - zone_config.get('y1', 0)
        center_x = width // 2
        center_y = height // 2

        self.counting_lines = [
            {
                'name': 'horizontal',
                'line': [(0, center_y), (width, center_y)],
                'direction': 'vertical'  # Détecte mouvement vertical
            },
            {
                'name': 'vertical',
                'line': [(center_x, 0), (center_x, height)],
                'direction': 'horizontal'  # Détecte mouvement horizontal
            }
        ]

    def update(self, detections: List[Dict], frame_number: int) -> List[TrackedObject]:
        """
        Met à jour le tracker avec de nouvelles détections

        Args:
            detections (List[Dict]): Détections de la frame courante
            frame_number (int): Numéro de la frame

        Returns:
            List[TrackedObject]: Objets actuellement trackés
        """
        self.frame_count = frame_number

        # Associer les détections aux tracks existants
        associations, unmatched_detections, unmatched_tracks = self._associate_detections(detections)

        # Mettre à jour les tracks associés
        for track_id, detection in associations.items():
            self._update_track(track_id, detection, frame_number)

        # Créer de nouveaux tracks pour les détections non associées
        for detection in unmatched_detections:
            self._create_new_track(detection, frame_number)

        # Gérer les tracks perdus
        for track_id in unmatched_tracks:
            self._handle_lost_track(track_id, frame_number)

        # Nettoyer les tracks inactifs
        self._cleanup_inactive_tracks()

        # Retourner les tracks actifs
        active_tracks = [track for track in self.tracked_objects.values() if track.is_active]

        logger.debug(f"Frame {frame_number}: {len(active_tracks)} tracks actifs")
        return active_tracks

    def _associate_detections(self, detections: List[Dict]) -> Tuple[Dict, List[Dict], List[int]]:
        """
        Associe les détections aux tracks existants

        Args:
            detections (List[Dict]): Nouvelles détections

        Returns:
            Tuple: (associations, détections_non_associées, tracks_non_associés)
        """
        if not self.tracked_objects:
            return {}, detections, []

        active_tracks = {tid: track for tid, track in self.tracked_objects.items() if track.is_active}

        if not active_tracks:
            return {}, detections, []

        # Calculer la matrice de coûts (distances)
        track_ids = list(active_tracks.keys())
        cost_matrix = np.full((len(track_ids), len(detections)), float('inf'))

        for i, track_id in enumerate(track_ids):
            track = active_tracks[track_id]
            for j, detection in enumerate(detections):
                # Filtrer par classe
                if track.class_id == detection['class_id']:
                    distance = self._calculate_distance(track.center, detection['center'])
                    if distance < self.max_distance:
                        cost_matrix[i, j] = distance

        # Association par algorithme hongrois simplifié
        associations = {}
        unmatched_detections = detections.copy()
        unmatched_tracks = track_ids.copy()

        # Trouver les meilleures associations (greedy approach)
        for _ in range(min(len(track_ids), len(detections))):
            if cost_matrix.size == 0:
                break

            min_cost_idx = np.unravel_index(np.argmin(cost_matrix), cost_matrix.shape)

            if cost_matrix[min_cost_idx] == float('inf'):
                break

            track_idx, det_idx = min_cost_idx
            track_id = track_ids[track_idx]
            detection = detections[det_idx]

            associations[track_id] = detection

            # Retirer de la matrice
            cost_matrix[track_idx, :] = float('inf')
            cost_matrix[:, det_idx] = float('inf')

            # Retirer des listes non associées
            if detection in unmatched_detections:
                unmatched_detections.remove(detection)
            if track_id in unmatched_tracks:
                unmatched_tracks.remove(track_id)

        return associations, unmatched_detections, unmatched_tracks

    def _calculate_distance(self, center1: List[float], center2: List[float]) -> float:
        """
        Calcule la distance euclidienne entre deux centres

        Args:
            center1, center2: Coordonnées des centres

        Returns:
            float: Distance euclidienne
        """
        return math.sqrt((center1[0] - center2[0])**2 + (center1[1] - center2[1])**2)

    def _update_track(self, track_id: int, detection: Dict, frame_number: int):
        """
        Met à jour un track existant

        Args:
            track_id (int): ID du track
            detection (Dict): Nouvelle détection
            frame_number (int): Numéro de frame
        """
        track = self.tracked_objects[track_id]

        # Mettre à jour les propriétés de base
        track.bbox = detection['bbox']
        track.confidence = detection['confidence']

        # Calculer le nouveau centre
        old_center = track.center.copy()
        track.center = detection['center']

        # Ajouter à l'historique
        track.positions.append(track.center.copy())
        track.confidences.append(track.confidence)
        track.frame_history.append(frame_number)

        # Calculer la vélocité
        if len(track.positions) >= 2:
            track.velocity = (
                track.center[0] - old_center[0],
                track.center[1] - old_center[1]
            )

            # Calculer la direction
            if abs(track.velocity[0]) > 0.1 or abs(track.velocity[1]) > 0.1:
                track.direction = math.degrees(math.atan2(track.velocity[1], track.velocity[0]))

        # Mettre à jour les métadonnées
        track.last_seen_frame = frame_number
        track.frames_tracked += 1
        track.frames_lost = 0

        # Vérifier les croisements de lignes
        self._check_line_crossings(track, old_center)

    def _create_new_track(self, detection: Dict, frame_number: int):
        """
        Crée un nouveau track

        Args:
            detection (Dict): Détection initiale
            frame_number (int): Numéro de frame
        """
        track_id = self.next_track_id
        self.next_track_id += 1

        new_track = TrackedObject(
            track_id=track_id,
            class_name=detection['class_name'],
            class_id=detection['class_id'],
            confidence=detection['confidence'],
            bbox=detection['bbox'],
            center=detection['center'],
            first_seen_frame=frame_number,
            last_seen_frame=frame_number,
            frames_tracked=1
        )

        # Initialiser l'historique
        new_track.positions.append(new_track.center.copy())
        new_track.confidences.append(new_track.confidence)
        new_track.frame_history.append(frame_number)

        # Déterminer le point d'entrée
        new_track.entry_point = self._get_entry_point(new_track.center)

        self.tracked_objects[track_id] = new_track
        self.total_tracks_created += 1

        logger.debug(f"Nouveau track créé: {track_id} ({detection['class_name']})")

    def _handle_lost_track(self, track_id: int, frame_number: int):
        """
        Gère un track perdu

        Args:
            track_id (int): ID du track
            frame_number (int): Numéro de frame
        """
        if track_id not in self.tracked_objects:
            return

        track = self.tracked_objects[track_id]
        track.frames_lost += 1

        if track.frames_lost >= self.max_frames_lost:
            track.is_active = False
            track.exit_point = self._get_exit_point(track.center)

            # Marquer comme terminé si assez long
            if track.frames_tracked >= self.min_track_length:
                self.total_tracks_completed += 1

            logger.debug(f"Track {track_id} marqué inactif après {track.frames_lost} frames perdues")

    def _cleanup_inactive_tracks(self):
        """Nettoie les tracks inactifs anciens"""
        tracks_to_remove = []

        for track_id, track in self.tracked_objects.items():
            if not track.is_active and (self.frame_count - track.last_seen_frame) > 100:
                tracks_to_remove.append(track_id)

        for track_id in tracks_to_remove:
            del self.tracked_objects[track_id]
            logger.debug(f"Track {track_id} supprimé du cache")

    def _check_line_crossings(self, track: TrackedObject, old_center: List[float]):
        """
        Vérifie si un track a croisé une ligne de comptage

        Args:
            track (TrackedObject): Track à vérifier
            old_center (List[float]): Position précédente
        """
        new_center = track.center

        for line_info in self.counting_lines:
            line_start, line_end = line_info['line']

            if self._line_intersection(old_center, new_center, line_start, line_end):
                direction = self._get_crossing_direction(old_center, new_center, line_info)

                if direction and not track.has_crossed_line:
                    track.has_crossed_line = True
                    self.crossing_counts[direction] += 1

                    logger.info(f"Track {track.track_id} ({track.class_name}) a traversé vers {direction}")

    def _line_intersection(self, p1: List[float], p2: List[float],
                          p3: List[float], p4: List[float]) -> bool:
        """
        Vérifie si deux segments se croisent

        Args:
            p1, p2: Points du premier segment
            p3, p4: Points du deuxième segment

        Returns:
            bool: True si intersection
        """
        def ccw(A, B, C):
            return (C[1] - A[1]) * (B[0] - A[0]) > (B[1] - A[1]) * (C[0] - A[0])

        return ccw(p1, p3, p4) != ccw(p2, p3, p4) and ccw(p1, p2, p3) != ccw(p1, p2, p4)

    def _get_crossing_direction(self, old_pos: List[float], new_pos: List[float],
                               line_info: Dict) -> Optional[str]:
        """
        Détermine la direction du croisement

        Args:
            old_pos, new_pos: Positions avant/après
            line_info: Information de la ligne

        Returns:
            Optional[str]: Direction du croisement
        """
        if line_info['direction'] == 'vertical':
            if new_pos[1] < old_pos[1]:
                return 'north'
            else:
                return 'south'
        else:  # horizontal
            if new_pos[0] > old_pos[0]:
                return 'east'
            else:
                return 'west'

    def _get_entry_point(self, center: List[float]) -> str:
        """
        Détermine le point d'entrée d'un objet

        Args:
            center: Position du centre

        Returns:
            str: Point d'entrée (north, south, east, west)
        """
        if not self.detection_zone:
            width, height = 1920, 1080  # Valeurs par défaut
        else:
            width = self.detection_zone['x2'] - self.detection_zone['x1']
            height = self.detection_zone['y2'] - self.detection_zone['y1']

        x, y = center

        # Déterminer le bord le plus proche
        distances = {
            'north': y,
            'south': height - y,
            'west': x,
            'east': width - x
        }

        return min(distances, key=distances.get)

    def _get_exit_point(self, center: List[float]) -> str:
        """Détermine le point de sortie d'un objet"""
        return self._get_entry_point(center)  # Même logique

    def draw_tracks(self, frame: np.ndarray) -> np.ndarray:
        """
        Dessine les tracks sur la frame

        Args:
            frame (np.ndarray): Frame vidéo

        Returns:
            np.ndarray: Frame avec tracks dessinés
        """
        frame_copy = frame.copy()

        # Couleurs pour les tracks
        colors = {
            'car': (0, 255, 0),
            'truck': (255, 0, 0),
            'bus': (255, 165, 0),
            'person': (255, 255, 0)
        }

        for track in self.tracked_objects.values():
            if not track.is_active or len(track.positions) < 2:
                continue

            color = colors.get(track.class_name, (128, 128, 128))

            # Dessiner la trajectoire
            points = np.array(track.positions, dtype=np.int32)
            if len(points) > 1:
                cv2.polylines(frame_copy, [points], isClosed=False, color=color, thickness=2)

            # Dessiner le point actuel
            center = tuple(map(int, track.center))
            cv2.circle(frame_copy, center, 5, color, -1)

            # Dessiner l'ID du track
            cv2.putText(
                frame_copy,
                f"ID:{track.track_id}",
                (center[0] + 10, center[1] - 10),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                color,
                2
            )

            # Dessiner la flèche de direction si en mouvement
            if abs(track.velocity[0]) > 1 or abs(track.velocity[1]) > 1:
                end_point = (
                    int(center[0] + track.velocity[0] * 3),
                    int(center[1] + track.velocity[1] * 3)
                )
                cv2.arrowedLine(frame_copy, center, end_point, color, 2, tipLength=0.3)

        # Dessiner les lignes de comptage
        self._draw_counting_lines(frame_copy)

        # Dessiner les statistiques
        self._draw_statistics(frame_copy)

        return frame_copy

    def _draw_counting_lines(self, frame: np.ndarray):
        """Dessine les lignes de comptage"""
        for i, line_info in enumerate(self.counting_lines):
            start, end = line_info['line']
            color = (0, 255, 255) if i == 0 else (255, 0, 255)
            cv2.line(frame, start, end, color, 2)

    def _draw_statistics(self, frame: np.ndarray):
        """Dessine les statistiques de tracking sur la frame"""
        active_count = len([t for t in self.tracked_objects.values() if t.is_active])

        stats_text = [
            f"Tracks actifs: {active_count}",
            f"Total créés: {self.total_tracks_created}",
            f"Terminés: {self.total_tracks_completed}",
            f"Croisements: N:{self.crossing_counts['north']} S:{self.crossing_counts['south']}"
        ]

        for i, text in enumerate(stats_text):
            cv2.putText(
                frame,
                text,
                (10, 30 + i * 25),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.6,
                (255, 255, 255),
                2
            )

    def get_tracking_statistics(self) -> Dict:
        """
        Retourne les statistiques de tracking

        Returns:
            Dict: Statistiques complètes
        """
        active_tracks = [t for t in self.tracked_objects.values() if t.is_active]
        completed_tracks = [t for t in self.tracked_objects.values() if not t.is_active and t.frames_tracked >= self.min_track_length]

        # Statistiques par classe
        class_stats = {}
        for track in active_tracks + completed_tracks:
            class_name = track.class_name
            if class_name not in class_stats:
                class_stats[class_name] = {'active': 0, 'completed': 0, 'total': 0}

            if track.is_active:
                class_stats[class_name]['active'] += 1
            else:
                class_stats[class_name]['completed'] += 1
            class_stats[class_name]['total'] += 1

        return {
            'active_tracks': len(active_tracks),
            'completed_tracks': len(completed_tracks),
            'total_tracks_created': self.total_tracks_created,
            'crossing_counts': self.crossing_counts.copy(),
            'class_statistics': class_stats,
            'average_track_length': np.mean([t.frames_tracked for t in completed_tracks]) if completed_tracks else 0
        }

    def reset(self):
        """Remet à zéro le tracker"""
        self.tracked_objects.clear()
        self.next_track_id = 1
        self.frame_count = 0
        self.total_tracks_created = 0
        self.total_tracks_completed = 0
        self.crossing_counts = {'north': 0, 'south': 0, 'east': 0, 'west': 0}
        logger.info("Tracker remis à zéro")