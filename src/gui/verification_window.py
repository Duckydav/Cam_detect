#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fenêtre de vérification rapide par classe pour Cam_detect
Permet de parcourir et valider rapidement les détections par type
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox
from PIL import Image, ImageTk
import cv2
import numpy as np
from typing import Dict, List, Optional, Tuple
from loguru import logger
from pathlib import Path
import json
from datetime import datetime

class DetectionVerificationWindow:
    """Fenêtre de vérification des détections par classe"""

    def __init__(self, parent, detections_data: Dict, video_path: str):
        """
        Initialise la fenêtre de vérification

        Args:
            parent: Fenêtre parent
            detections_data (Dict): Données des détections
            video_path (str): Chemin vers la vidéo
        """
        self.parent = parent
        self.detections_data = detections_data
        self.video_path = video_path
        self.video_cap = None

        # État de vérification
        self.current_class = "bus"
        self.current_detection_index = 0
        self.detections_by_class = {}
        self.verification_results = {}

        # Interface
        self.window = None
        self.image_label = None
        self.info_frame = None
        self.navigation_frame = None
        self.class_selector = None

        # Variables d'affichage
        self.current_image = None
        self.zoom_factor = 1.0

        self._prepare_detections_data()
        self._setup_window()
        self._create_widgets()
        self._load_first_detection()

    def _prepare_detections_data(self):
        """Prépare les données de détections par classe"""
        logger.info("Préparation des données de détections par classe")

        # Grouper les détections par classe
        for frame_data in self.detections_data.get('detection_history', []):
            frame_number = frame_data['frame_number']
            timestamp = frame_data['timestamp']

            for detection in frame_data['detections']:
                class_name = detection['class_name']

                if class_name not in self.detections_by_class:
                    self.detections_by_class[class_name] = []

                # Ajouter info de frame pour navigation
                detection_with_frame = detection.copy()
                detection_with_frame.update({
                    'frame_number': frame_number,
                    'timestamp': timestamp,
                    'video_time': f"{int(timestamp // 60):02d}:{int(timestamp % 60):02d}"
                })

                self.detections_by_class[class_name].append(detection_with_frame)

        # Trier par frame
        for class_name in self.detections_by_class:
            self.detections_by_class[class_name].sort(key=lambda x: x['frame_number'])

        # Initialiser les résultats de vérification
        for class_name, detections in self.detections_by_class.items():
            self.verification_results[class_name] = {
                'verified': [],
                'rejected': [],
                'pending': list(range(len(detections)))
            }

        logger.info(f"Classes trouvées: {list(self.detections_by_class.keys())}")
        for class_name, detections in self.detections_by_class.items():
            logger.info(f"  {class_name}: {len(detections)} détections")

    def _setup_window(self):
        """Configure la fenêtre de vérification"""
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("Vérification des Détections - Cam_detect")
        self.window.geometry("1000x700")

        # Centrer la fenêtre
        self.window.transient(self.parent)
        self.window.grab_set()

        # Configuration grille
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_columnconfigure(1, weight=1)

    def _create_widgets(self):
        """Crée l'interface de vérification"""

        # Barre d'outils du haut
        self._create_toolbar()

        # Zone d'image principale
        self._create_image_area()

        # Panneau d'informations
        self._create_info_panel()

        # Contrôles de navigation
        self._create_navigation_controls()

    def _create_toolbar(self):
        """Crée la barre d'outils"""
        toolbar = ctk.CTkFrame(self.window, height=60)
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        toolbar.grid_columnconfigure(2, weight=1)

        # Sélecteur de classe
        ctk.CTkLabel(toolbar, text="Classe:").grid(row=0, column=0, padx=10, pady=15)

        available_classes = list(self.detections_by_class.keys())
        if not available_classes:
            available_classes = ["Aucune détection"]

        self.class_selector = ctk.CTkComboBox(
            toolbar,
            values=available_classes,
            command=self._on_class_changed,
            width=150
        )
        self.class_selector.grid(row=0, column=1, padx=10, pady=15)

        if available_classes and available_classes[0] != "Aucune détection":
            self.class_selector.set(available_classes[0])
            self.current_class = available_classes[0]

        # Statistiques
        self.stats_label = ctk.CTkLabel(toolbar, text="", font=ctk.CTkFont(size=12))
        self.stats_label.grid(row=0, column=2, padx=20, pady=15)

        # Boutons d'action
        self.export_btn = ctk.CTkButton(
            toolbar,
            text="💾 Exporter",
            command=self._export_results,
            width=100
        )
        self.export_btn.grid(row=0, column=3, padx=5, pady=15)

        close_btn = ctk.CTkButton(
            toolbar,
            text="❌ Fermer",
            command=self.window.destroy,
            width=100
        )
        close_btn.grid(row=0, column=4, padx=5, pady=15)

    def _create_image_area(self):
        """Crée la zone d'affichage d'image"""
        image_frame = ctk.CTkFrame(self.window)
        image_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

        # Canvas pour l'image
        self.image_canvas = tk.Canvas(
            image_frame,
            bg="black",
            width=600,
            height=400
        )
        self.image_canvas.pack(expand=True, fill="both", padx=10, pady=10)

        # Bind pour zoom
        self.image_canvas.bind("<MouseWheel>", self._on_mouse_wheel)
        self.image_canvas.bind("<Button-1>", self._on_canvas_click)

    def _create_info_panel(self):
        """Crée le panneau d'informations"""
        self.info_frame = ctk.CTkFrame(self.window, width=250)
        self.info_frame.grid(row=1, column=2, sticky="nsew", padx=(0, 10), pady=5)

        # Titre
        ctk.CTkLabel(
            self.info_frame,
            text="📋 Informations",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)

        # Zone de texte pour les détails
        self.info_text = ctk.CTkTextbox(self.info_frame, height=200)
        self.info_text.pack(fill="both", expand=True, padx=10, pady=10)

        # Boutons de validation
        validation_frame = ctk.CTkFrame(self.info_frame)
        validation_frame.pack(fill="x", padx=10, pady=10)

        self.accept_btn = ctk.CTkButton(
            validation_frame,
            text="✅ Valide",
            command=self._accept_detection,
            fg_color="green",
            hover_color="darkgreen",
            height=40
        )
        self.accept_btn.pack(fill="x", pady=2)

        self.reject_btn = ctk.CTkButton(
            validation_frame,
            text="❌ Rejeter",
            command=self._reject_detection,
            fg_color="red",
            hover_color="darkred",
            height=40
        )
        self.reject_btn.pack(fill="x", pady=2)

        self.skip_btn = ctk.CTkButton(
            validation_frame,
            text="⏭️ Passer",
            command=self._skip_detection,
            fg_color="orange",
            hover_color="darkorange",
            height=40
        )
        self.skip_btn.pack(fill="x", pady=2)

    def _create_navigation_controls(self):
        """Crée les contrôles de navigation"""
        nav_frame = ctk.CTkFrame(self.window, height=80)
        nav_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        nav_frame.grid_columnconfigure(3, weight=1)

        # Boutons de navigation
        self.prev_btn = ctk.CTkButton(
            nav_frame,
            text="⬅️ Précédent",
            command=self._previous_detection,
            width=120
        )
        self.prev_btn.grid(row=0, column=0, padx=10, pady=20)

        self.next_btn = ctk.CTkButton(
            nav_frame,
            text="➡️ Suivant",
            command=self._next_detection,
            width=120
        )
        self.next_btn.grid(row=0, column=1, padx=10, pady=20)

        # Compteur
        self.counter_label = ctk.CTkLabel(
            nav_frame,
            text="0 / 0",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        self.counter_label.grid(row=0, column=2, padx=20, pady=20)

        # Barre de progression
        self.progress_bar = ctk.CTkProgressBar(nav_frame, width=200)
        self.progress_bar.grid(row=0, column=3, padx=20, pady=20, sticky="e")

        # Navigation rapide
        rapid_frame = ctk.CTkFrame(nav_frame)
        rapid_frame.grid(row=0, column=4, padx=10, pady=20)

        ctk.CTkLabel(rapid_frame, text="Aller à:").pack(side="left", padx=5)

        self.goto_entry = ctk.CTkEntry(rapid_frame, width=60, placeholder_text="N°")
        self.goto_entry.pack(side="left", padx=5)
        self.goto_entry.bind("<Return>", self._goto_detection)

        goto_btn = ctk.CTkButton(
            rapid_frame,
            text="▶️",
            command=self._goto_detection,
            width=40
        )
        goto_btn.pack(side="left", padx=5)

    def _on_class_changed(self, class_name: str):
        """Callback quand la classe sélectionnée change"""
        if class_name == "Aucune détection":
            return

        self.current_class = class_name
        self.current_detection_index = 0
        self._update_display()
        logger.info(f"Classe changée vers: {class_name}")

    def _load_first_detection(self):
        """Charge la première détection"""
        if self.detections_by_class:
            self._open_video()
            self._update_display()

    def _open_video(self):
        """Ouvre la vidéo pour extraction de frames"""
        try:
            self.video_cap = cv2.VideoCapture(self.video_path)
            if not self.video_cap.isOpened():
                raise RuntimeError("Impossible d'ouvrir la vidéo")
            logger.info("Vidéo ouverte pour vérification")
        except Exception as e:
            logger.error(f"Erreur ouverture vidéo: {e}")
            messagebox.showerror("Erreur", f"Impossible d'ouvrir la vidéo: {e}")

    def _update_display(self):
        """Met à jour l'affichage avec la détection courante"""
        if not self.detections_by_class or self.current_class not in self.detections_by_class:
            self._show_no_detection()
            return

        detections = self.detections_by_class[self.current_class]
        if not detections or self.current_detection_index >= len(detections):
            self._show_no_detection()
            return

        current_detection = detections[self.current_detection_index]

        # Extraire et afficher la frame
        self._display_detection_frame(current_detection)

        # Mettre à jour les informations
        self._update_info_panel(current_detection)

        # Mettre à jour la navigation
        self._update_navigation()

        # Mettre à jour les statistiques
        self._update_statistics()

    def _display_detection_frame(self, detection: Dict):
        """Affiche la frame avec la détection mise en évidence"""
        if not self.video_cap:
            return

        try:
            # Aller à la frame spécifique
            frame_number = detection['frame_number']
            self.video_cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)

            ret, frame = self.video_cap.read()
            if not ret:
                logger.error(f"Impossible de lire la frame {frame_number}")
                return

            # Dessiner la détection
            annotated_frame = self._annotate_frame(frame, detection)

            # Convertir pour affichage
            self._display_frame_on_canvas(annotated_frame)

        except Exception as e:
            logger.error(f"Erreur affichage frame: {e}")

    def _annotate_frame(self, frame: np.ndarray, detection: Dict) -> np.ndarray:
        """Annote la frame avec la détection"""
        annotated = frame.copy()
        bbox = detection['bbox']
        class_name = detection['class_name']
        confidence = detection['confidence']

        # Coordonnées
        x1, y1, x2, y2 = map(int, bbox)

        # Couleur selon la classe
        colors = {
            'car': (0, 255, 0),
            'truck': (255, 0, 0),
            'bus': (255, 165, 0),
            'person': (255, 255, 0)
        }
        color = colors.get(class_name, (128, 128, 128))

        # Dessiner le rectangle principal (plus épais)
        cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 3)

        # Dessiner un rectangle de focus élargi
        margin = 20
        focus_x1 = max(0, x1 - margin)
        focus_y1 = max(0, y1 - margin)
        focus_x2 = min(frame.shape[1], x2 + margin)
        focus_y2 = min(frame.shape[0], y2 + margin)

        cv2.rectangle(annotated, (focus_x1, focus_y1), (focus_x2, focus_y2), (255, 255, 255), 1)

        # Label détaillé
        label = f"{class_name.upper()}: {confidence:.2f}"
        label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.8, 2)[0]

        # Fond du label
        cv2.rectangle(
            annotated,
            (x1, y1 - label_size[1] - 15),
            (x1 + label_size[0] + 10, y1),
            color,
            -1
        )

        # Texte du label
        cv2.putText(
            annotated,
            label,
            (x1 + 5, y1 - 8),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.8,
            (255, 255, 255),
            2
        )

        # Ajouter des informations sur la frame
        frame_info = f"Frame: {detection['frame_number']} | Temps: {detection['video_time']}"
        cv2.putText(
            annotated,
            frame_info,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2
        )

        return annotated

    def _display_frame_on_canvas(self, frame: np.ndarray):
        """Affiche la frame sur le canvas"""
        # Convertir BGR to RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Redimensionner pour le canvas
        canvas_width = self.image_canvas.winfo_width()
        canvas_height = self.image_canvas.winfo_height()

        if canvas_width > 1 and canvas_height > 1:
            # Maintenir le ratio d'aspect
            h, w = frame_rgb.shape[:2]
            scale = min(canvas_width / w, canvas_height / h) * self.zoom_factor

            new_w = int(w * scale)
            new_h = int(h * scale)

            if new_w > 0 and new_h > 0:
                frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

                # Convertir en image PIL
                image = Image.fromarray(frame_resized)
                photo = ImageTk.PhotoImage(image)

                # Afficher sur le canvas
                self.image_canvas.delete("all")
                self.image_canvas.create_image(
                    canvas_width // 2,
                    canvas_height // 2,
                    anchor=tk.CENTER,
                    image=photo
                )

                # Garder une référence
                self.current_image = photo

    def _update_info_panel(self, detection: Dict):
        """Met à jour le panneau d'informations"""
        info_text = f"""DÉTECTION ACTUELLE
{"=" * 30}

🎯 Classe: {detection['class_name'].upper()}
📊 Confiance: {detection['confidence']:.3f}
🎥 Frame: {detection['frame_number']}
⏰ Temps: {detection['video_time']}
📍 Position: ({detection['center'][0]:.0f}, {detection['center'][1]:.0f})

📏 DIMENSIONS
Largeur: {detection['bbox'][2] - detection['bbox'][0]:.0f}px
Hauteur: {detection['bbox'][3] - detection['bbox'][1]:.0f}px
Aire: {(detection['bbox'][2] - detection['bbox'][0]) * (detection['bbox'][3] - detection['bbox'][1]):.0f}px²

🎲 COORDONNÉES BBOX
x1: {detection['bbox'][0]:.0f}
y1: {detection['bbox'][1]:.0f}
x2: {detection['bbox'][2]:.0f}
y2: {detection['bbox'][3]:.0f}
"""

        self.info_text.delete("0.0", "end")
        self.info_text.insert("0.0", info_text)

    def _update_navigation(self):
        """Met à jour les contrôles de navigation"""
        if not self.detections_by_class or self.current_class not in self.detections_by_class:
            return

        detections = self.detections_by_class[self.current_class]
        total = len(detections)
        current = self.current_detection_index + 1

        # Compteur
        self.counter_label.configure(text=f"{current} / {total}")

        # Barre de progression
        if total > 0:
            self.progress_bar.set(current / total)
        else:
            self.progress_bar.set(0)

        # État des boutons
        self.prev_btn.configure(state="normal" if current > 1 else "disabled")
        self.next_btn.configure(state="normal" if current < total else "disabled")

    def _update_statistics(self):
        """Met à jour les statistiques dans la toolbar"""
        if not self.current_class or self.current_class not in self.verification_results:
            return

        results = self.verification_results[self.current_class]
        total = len(self.detections_by_class.get(self.current_class, []))
        verified = len(results['verified'])
        rejected = len(results['rejected'])
        pending = len(results['pending'])

        stats_text = f"Total: {total} | ✅ {verified} | ❌ {rejected} | ⏳ {pending}"
        self.stats_label.configure(text=stats_text)

    def _show_no_detection(self):
        """Affiche un message quand aucune détection"""
        self.image_canvas.delete("all")
        self.image_canvas.create_text(
            300, 200,
            text="Aucune détection à afficher",
            fill="white",
            font=("Arial", 16)
        )

        self.info_text.delete("0.0", "end")
        self.info_text.insert("0.0", "Aucune détection sélectionnée")

    # Méthodes de navigation
    def _previous_detection(self):
        """Va à la détection précédente"""
        if self.current_detection_index > 0:
            self.current_detection_index -= 1
            self._update_display()

    def _next_detection(self):
        """Va à la détection suivante"""
        if (self.current_class in self.detections_by_class and
            self.current_detection_index < len(self.detections_by_class[self.current_class]) - 1):
            self.current_detection_index += 1
            self._update_display()

    def _goto_detection(self, event=None):
        """Va à une détection spécifique"""
        try:
            target = int(self.goto_entry.get()) - 1  # Index 0-based
            if (self.current_class in self.detections_by_class and
                0 <= target < len(self.detections_by_class[self.current_class])):
                self.current_detection_index = target
                self._update_display()
                self.goto_entry.delete(0, 'end')
            else:
                messagebox.showwarning("Navigation", "Numéro de détection invalide")
        except ValueError:
            messagebox.showwarning("Navigation", "Veuillez entrer un numéro valide")

    # Méthodes de validation
    def _accept_detection(self):
        """Valide la détection courante"""
        self._mark_detection('verified')
        self._next_detection()

    def _reject_detection(self):
        """Rejette la détection courante"""
        self._mark_detection('rejected')
        self._next_detection()

    def _skip_detection(self):
        """Passe la détection courante"""
        self._next_detection()

    def _mark_detection(self, status: str):
        """Marque une détection avec un statut"""
        if (self.current_class not in self.verification_results or
            self.current_detection_index >= len(self.detections_by_class.get(self.current_class, []))):
            return

        results = self.verification_results[self.current_class]
        index = self.current_detection_index

        # Retirer de tous les statuts
        for status_list in results.values():
            if index in status_list:
                status_list.remove(index)

        # Ajouter au nouveau statut
        results[status].append(index)

        logger.info(f"Détection {index} marquée comme {status}")

    # Méthodes d'événements
    def _on_mouse_wheel(self, event):
        """Gestion du zoom avec la molette"""
        if event.delta > 0:
            self.zoom_factor = min(3.0, self.zoom_factor * 1.1)
        else:
            self.zoom_factor = max(0.5, self.zoom_factor * 0.9)

        self._update_display()

    def _on_canvas_click(self, event):
        """Gestion du clic sur le canvas"""
        # Possibilité d'ajouter des fonctionnalités de clic
        pass

    # Méthodes d'export
    def _export_results(self):
        """Exporte les résultats de vérification"""
        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            video_name = Path(self.video_path).stem
            filename = f"verification_{video_name}_{timestamp}.json"

            project_root = Path(__file__).parent.parent.parent
            output_path = project_root / "data" / "output" / filename
            output_path.parent.mkdir(parents=True, exist_ok=True)

            export_data = {
                'video_path': self.video_path,
                'verification_timestamp': datetime.now().isoformat(),
                'verification_results': self.verification_results,
                'statistics': self._get_verification_statistics()
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(export_data, f, indent=2, ensure_ascii=False)

            messagebox.showinfo("Export", f"Résultats exportés vers:\n{output_path}")
            logger.info(f"Résultats de vérification exportés: {output_path}")

        except Exception as e:
            logger.error(f"Erreur export: {e}")
            messagebox.showerror("Erreur", f"Erreur lors de l'export: {e}")

    def _get_verification_statistics(self) -> Dict:
        """Génère les statistiques de vérification"""
        stats = {}

        for class_name, results in self.verification_results.items():
            total = len(self.detections_by_class.get(class_name, []))
            verified = len(results['verified'])
            rejected = len(results['rejected'])
            pending = len(results['pending'])

            stats[class_name] = {
                'total': total,
                'verified': verified,
                'rejected': rejected,
                'pending': pending,
                'verification_rate': (verified + rejected) / total if total > 0 else 0
            }

        return stats

    def __del__(self):
        """Nettoyage lors de la fermeture"""
        if hasattr(self, 'video_cap') and self.video_cap:
            self.video_cap.release()