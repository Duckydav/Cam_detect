#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Processeur vidéo pour Cam_detect
Gestion du traitement de flux vidéo avec détection YOLOv8
"""

import cv2
import numpy as np
from pathlib import Path
from typing import Dict, List, Callable, Optional, Tuple
from loguru import logger
import threading
import time
from datetime import datetime, timedelta

from .detector import TrafficDetector

class VideoProcessor:
    """Processeur vidéo avec détection d'objets temps réel"""

    def __init__(self, config: Dict):
        """
        Initialise le processeur vidéo

        Args:
            config (dict): Configuration de l'application
        """
        self.config = config
        self.detector = TrafficDetector(config)

        # État du processeur
        self.is_processing = False
        self.is_paused = False
        self.current_frame = None
        self.frame_count = 0
        self.total_frames = 0

        # Paramètres vidéo
        self.video_path = None
        self.video_cap = None
        self.fps = 30.0
        self.frame_width = 0
        self.frame_height = 0

        # Callbacks pour l'interface
        self.frame_callback = None
        self.progress_callback = None
        self.stats_callback = None
        self.completion_callback = None
        self.error_callback = None

        # Configuration du traitement
        self.fps_analysis = config.get('video.fps_analysis', 5)
        self.resize_width = config.get('video.resize_width', 640)
        self.skip_frames = config.get('video.skip_frames', 0)
        self.max_frames = config.get('video.max_frames', 0)

        # Historique des détections
        self.detection_history = []
        self.timeline_stats = {}

    def set_callbacks(self,
                     frame_callback: Callable = None,
                     progress_callback: Callable = None,
                     stats_callback: Callable = None,
                     completion_callback: Callable = None,
                     error_callback: Callable = None):
        """
        Configure les callbacks pour l'interface utilisateur

        Args:
            frame_callback: Appelé avec chaque frame traitée
            progress_callback: Appelé pour mettre à jour la progression
            stats_callback: Appelé avec les statistiques mises à jour
            completion_callback: Appelé quand le traitement est terminé
            error_callback: Appelé en cas d'erreur
        """
        self.frame_callback = frame_callback
        self.progress_callback = progress_callback
        self.stats_callback = stats_callback
        self.completion_callback = completion_callback
        self.error_callback = error_callback

    def load_video(self, video_path: str) -> bool:
        """
        Charge une vidéo pour traitement

        Args:
            video_path (str): Chemin vers le fichier vidéo

        Returns:
            bool: True si le chargement réussit
        """
        try:
            self.video_path = Path(video_path)

            if not self.video_path.exists():
                raise FileNotFoundError(f"Fichier vidéo non trouvé: {video_path}")

            # Ouvrir la vidéo avec OpenCV
            self.video_cap = cv2.VideoCapture(str(video_path))

            if not self.video_cap.isOpened():
                raise RuntimeError("Impossible d'ouvrir la vidéo")

            # Récupérer les propriétés de la vidéo
            self.total_frames = int(self.video_cap.get(cv2.CAP_PROP_FRAME_COUNT))
            self.fps = self.video_cap.get(cv2.CAP_PROP_FPS)
            self.frame_width = int(self.video_cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            self.frame_height = int(self.video_cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

            logger.info(f"Vidéo chargée: {self.video_path.name}")
            logger.info(f"Résolution: {self.frame_width}x{self.frame_height}")
            logger.info(f"FPS: {self.fps:.2f}, Frames: {self.total_frames}")
            logger.info(f"Durée: {self.total_frames/self.fps:.1f} secondes")

            # Réinitialiser les statistiques
            self.detector.reset_statistics()
            self.detection_history.clear()
            self.timeline_stats.clear()
            self.frame_count = 0

            return True

        except Exception as e:
            logger.error(f"Erreur lors du chargement de la vidéo: {e}")
            if self.error_callback:
                self.error_callback(f"Erreur de chargement: {e}")
            return False

    def start_processing(self,
                        confidence: float = 0.5,
                        class_selection: Dict[str, bool] = None):
        """
        Démarre le traitement vidéo

        Args:
            confidence (float): Seuil de confiance pour la détection
            class_selection (Dict[str, bool]): Classes sélectionnées
        """
        if not self.video_cap or not self.video_cap.isOpened():
            logger.error("Aucune vidéo chargée")
            return

        if self.is_processing:
            logger.warning("Traitement déjà en cours")
            return

        # Configurer le détecteur
        if class_selection:
            self.detector.set_enabled_classes(class_selection)

        self.is_processing = True
        self.is_paused = False

        # Lancer le traitement dans un thread
        processing_thread = threading.Thread(
            target=self._process_video_thread,
            args=(confidence,)
        )
        processing_thread.daemon = True
        processing_thread.start()

        logger.info("Traitement vidéo démarré")

    def _process_video_thread(self, confidence: float):
        """
        Thread principal de traitement vidéo

        Args:
            confidence (float): Seuil de confiance
        """
        try:
            # Aller au début ou à la frame de démarrage
            if self.skip_frames > 0:
                self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, self.skip_frames)
                self.frame_count = self.skip_frames

            start_time = time.time()
            frames_processed = 0

            while self.is_processing and self.video_cap.isOpened():
                # Gestion de la pause
                while self.is_paused and self.is_processing:
                    time.sleep(0.1)
                    continue

                if not self.is_processing:
                    break

                # Lire la frame suivante
                ret, frame = self.video_cap.read()
                if not ret:
                    logger.info("Fin de la vidéo atteinte")
                    break

                self.frame_count += 1

                # Arrêter si limite de frames atteinte
                if self.max_frames > 0 and self.frame_count >= self.max_frames:
                    logger.info(f"Limite de frames atteinte: {self.max_frames}")
                    break

                # Traiter seulement certaines frames pour optimiser
                if self.frame_count % self.fps_analysis == 0:
                    processed_frame = self._process_single_frame(frame, confidence)
                    frames_processed += 1

                    # Callback avec la frame traitée
                    if self.frame_callback and processed_frame is not None:
                        self.frame_callback(processed_frame)

                # Mettre à jour la progression
                if self.frame_count % 30 == 0:  # Toutes les 30 frames
                    progress = self.frame_count / self.total_frames
                    if self.progress_callback:
                        self.progress_callback(progress)

                    # Statistiques en temps réel
                    if self.stats_callback:
                        stats = self._get_current_stats()
                        self.stats_callback(stats)

            # Traitement terminé
            processing_time = time.time() - start_time
            avg_fps = frames_processed / processing_time if processing_time > 0 else 0

            logger.info(f"Traitement terminé en {processing_time:.1f}s")
            logger.info(f"FPS moyen de traitement: {avg_fps:.2f}")

            if self.completion_callback and self.is_processing:
                final_stats = self._get_final_stats()
                self.completion_callback(final_stats)

        except Exception as e:
            logger.error(f"Erreur pendant le traitement: {e}")
            if self.error_callback:
                self.error_callback(f"Erreur de traitement: {e}")

        finally:
            self.is_processing = False

    def _process_single_frame(self, frame: np.ndarray, confidence: float) -> Optional[np.ndarray]:
        """
        Traite une frame individuelle

        Args:
            frame (np.ndarray): Frame à traiter
            confidence (float): Seuil de confiance

        Returns:
            Optional[np.ndarray]: Frame avec détections ou None
        """
        try:
            # Redimensionner la frame si nécessaire
            if self.resize_width > 0:
                aspect_ratio = frame.shape[0] / frame.shape[1]
                new_height = int(self.resize_width * aspect_ratio)
                frame = cv2.resize(frame, (self.resize_width, new_height))

            # Détection des objets
            detections = self.detector.detect_objects(frame, confidence)

            # Analyse avancée pour piétons avec chiens
            enriched_detections = self.detector.detect_persons_with_dogs(detections)

            # Sauvegarder dans l'historique
            frame_data = {
                'frame_number': self.frame_count,
                'timestamp': self.frame_count / self.fps,
                'detections': enriched_detections,
                'detection_count': len(enriched_detections)
            }
            self.detection_history.append(frame_data)

            # Mettre à jour les stats timeline
            self._update_timeline_stats(frame_data)

            # Dessiner les détections
            processed_frame = self.detector.draw_detections(frame, enriched_detections)

            self.current_frame = processed_frame
            return processed_frame

        except Exception as e:
            logger.error(f"Erreur traitement frame {self.frame_count}: {e}")
            return None

    def _update_timeline_stats(self, frame_data: Dict):
        """
        Met à jour les statistiques temporelles

        Args:
            frame_data (Dict): Données de la frame
        """
        timestamp = frame_data['timestamp']
        minute_mark = int(timestamp // 60)  # Grouper par minutes

        if minute_mark not in self.timeline_stats:
            self.timeline_stats[minute_mark] = {
                'cars': 0,
                'trucks': 0,
                'buses': 0,
                'persons': 0,
                'total': 0,
                'frames': 0
            }

        stats = self.timeline_stats[minute_mark]
        stats['frames'] += 1

        for detection in frame_data['detections']:
            class_name = detection['class_name']
            if class_name == 'car':
                stats['cars'] += 1
            elif class_name == 'truck':
                stats['trucks'] += 1
            elif class_name == 'bus':
                stats['buses'] += 1
            elif class_name == 'person':
                stats['persons'] += 1

            stats['total'] += 1

    def _get_current_stats(self) -> Dict:
        """
        Récupère les statistiques actuelles

        Returns:
            Dict: Statistiques de traitement
        """
        base_stats = self.detector.get_statistics()

        current_stats = {
            **base_stats,
            'current_frame': self.frame_count,
            'total_frames': self.total_frames,
            'progress_percent': (self.frame_count / self.total_frames) * 100 if self.total_frames > 0 else 0,
            'video_timestamp': self.frame_count / self.fps if self.fps > 0 else 0,
            'detections_last_minute': self._get_recent_detection_count(60)
        }

        return current_stats

    def _get_recent_detection_count(self, seconds: int) -> int:
        """
        Compte les détections dans les X dernières secondes

        Args:
            seconds (int): Période en secondes

        Returns:
            int: Nombre de détections récentes
        """
        current_time = self.frame_count / self.fps
        cutoff_time = current_time - seconds

        recent_count = 0
        for frame_data in reversed(self.detection_history):
            if frame_data['timestamp'] >= cutoff_time:
                recent_count += frame_data['detection_count']
            else:
                break

        return recent_count

    def _get_final_stats(self) -> Dict:
        """
        Génère les statistiques finales de traitement

        Returns:
            Dict: Statistiques complètes
        """
        base_stats = self._get_current_stats()

        # Statistiques temporelles
        timeline_summary = {}
        for minute, stats in self.timeline_stats.items():
            timeline_summary[f"minute_{minute}"] = stats

        # Moyennes et totaux
        video_duration = self.total_frames / self.fps if self.fps > 0 else 0

        final_stats = {
            **base_stats,
            'video_path': str(self.video_path),
            'video_duration_seconds': video_duration,
            'total_detections': sum(frame['detection_count'] for frame in self.detection_history),
            'avg_detections_per_minute': len(self.detection_history) / (video_duration / 60) if video_duration > 0 else 0,
            'timeline_stats': timeline_summary,
            'processing_completed': True,
            'completion_timestamp': datetime.now().isoformat()
        }

        return final_stats

    def pause_processing(self):
        """Met en pause le traitement"""
        self.is_paused = True
        logger.info("Traitement mis en pause")

    def resume_processing(self):
        """Reprend le traitement"""
        self.is_paused = False
        logger.info("Traitement repris")

    def stop_processing(self):
        """Arrête le traitement"""
        self.is_processing = False
        self.is_paused = False
        logger.info("Traitement arrêté")

    def save_results(self, output_path: str = None) -> bool:
        """
        Sauvegarde les résultats d'analyse

        Args:
            output_path (str): Chemin de sauvegarde (optionnel)

        Returns:
            bool: True si la sauvegarde réussit
        """
        try:
            if not output_path:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"analysis_{self.video_path.stem}_{timestamp}.json"
                project_root = Path(__file__).parent.parent.parent
                output_path = project_root / "data" / "output" / filename

            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Préparer les données à sauvegarder
            results = {
                'video_info': {
                    'path': str(self.video_path),
                    'duration': self.total_frames / self.fps,
                    'fps': self.fps,
                    'total_frames': self.total_frames,
                    'resolution': [self.frame_width, self.frame_height]
                },
                'detection_summary': self.detector.get_statistics(),
                'timeline_stats': self.timeline_stats,
                'detection_history': self.detection_history,
                'processing_info': {
                    'confidence_threshold': 0.5,  # TODO: récupérer la valeur réelle
                    'fps_analysis': self.fps_analysis,
                    'processed_frames': len(self.detection_history)
                }
            }

            import json
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2, ensure_ascii=False)

            logger.info(f"Résultats sauvegardés: {output_path}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            return False

    def get_current_frame(self) -> Optional[np.ndarray]:
        """
        Retourne la frame actuellement traitée

        Returns:
            Optional[np.ndarray]: Frame actuelle ou None
        """
        return self.current_frame

    def seek_to_frame(self, frame_number: int) -> bool:
        """
        Se déplace à une frame spécifique

        Args:
            frame_number (int): Numéro de frame cible

        Returns:
            bool: True si le déplacement réussit
        """
        if not self.video_cap or not self.video_cap.isOpened():
            return False

        try:
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            self.frame_count = frame_number
            logger.debug(f"Déplacement à la frame: {frame_number}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors du déplacement: {e}")
            return False

    def __del__(self):
        """Nettoyage lors de la destruction"""
        if hasattr(self, 'video_cap') and self.video_cap:
            self.video_cap.release()
        self.stop_processing()
        logger.debug("Processeur vidéo nettoyé")