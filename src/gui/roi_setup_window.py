#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Fenêtre de configuration des zones ROI pour éliminer les faux positifs
Interface graphique pour définir les zones d'arbres et de route
"""

import tkinter as tk
import customtkinter as ctk
from tkinter import messagebox, filedialog
from PIL import Image, ImageTk
import cv2
import numpy as np
from typing import List, Tuple, Optional
from loguru import logger
from pathlib import Path
import json

class ROISetupWindow:
    """Interface de configuration des zones ROI"""

    def __init__(self, parent, video_path: str, callback=None):
        """
        Initialise la fenêtre de configuration ROI

        Args:
            parent: Fenêtre parent
            video_path: Chemin vers la vidéo
            callback: Fonction appelée avec les zones configurées
        """
        self.parent = parent
        self.video_path = video_path
        self.callback = callback

        # État de l'interface
        self.video_cap = None
        self.current_frame = None
        self.canvas_image = None

        # Zones en cours de définition
        self.current_zone_points = []
        self.current_zone_type = "exclusion"  # exclusion ou inclusion
        self.current_zone_name = ""

        # Zones finalisées
        self.exclusion_zones = []
        self.inclusion_zones = []

        # Interface
        self.window = None
        self.canvas = None
        self.canvas_width = 800
        self.canvas_height = 600

        self._setup_window()
        self._create_widgets()
        self._load_first_frame()

    def _setup_window(self):
        """Configure la fenêtre principale"""
        self.window = ctk.CTkToplevel(self.parent)
        self.window.title("Configuration des Zones ROI - Éliminer les Faux Positifs")
        self.window.geometry("1200x800")

        # Centrer et rendre modale
        self.window.transient(self.parent)
        self.window.grab_set()

        # Configuration grille
        self.window.grid_rowconfigure(1, weight=1)
        self.window.grid_columnconfigure(1, weight=1)

    def _create_widgets(self):
        """Crée l'interface utilisateur"""
        # Barre d'outils
        self._create_toolbar()

        # Zone de canvas principal
        self._create_canvas_area()

        # Panneau de contrôle
        self._create_control_panel()

        # Barre de statut
        self._create_status_bar()

    def _create_toolbar(self):
        """Crée la barre d'outils du haut"""
        toolbar = ctk.CTkFrame(self.window, height=60)
        toolbar.grid(row=0, column=0, columnspan=3, sticky="ew", padx=10, pady=5)
        toolbar.grid_columnconfigure(4, weight=1)

        # Instructions
        instructions = ctk.CTkLabel(
            toolbar,
            text="💡 Cliquez pour définir les zones où IGNORER les détections (arbres, etc.)",
            font=ctk.CTkFont(size=14, weight="bold")
        )
        instructions.grid(row=0, column=0, columnspan=5, pady=10)

        # Mode de zone
        ctk.CTkLabel(toolbar, text="Type de zone:").grid(row=1, column=0, padx=10, pady=5)

        self.zone_type_var = tk.StringVar(value="exclusion")
        zone_type_menu = ctk.CTkOptionMenu(
            toolbar,
            values=["exclusion", "inclusion"],
            variable=self.zone_type_var,
            command=self._on_zone_type_changed
        )
        zone_type_menu.grid(row=1, column=1, padx=10, pady=5)

        # Nom de zone
        ctk.CTkLabel(toolbar, text="Nom:").grid(row=1, column=2, padx=10, pady=5)

        self.zone_name_entry = ctk.CTkEntry(toolbar, placeholder_text="ex: arbre_gauche")
        self.zone_name_entry.grid(row=1, column=3, padx=10, pady=5)

        # Boutons d'action
        action_frame = ctk.CTkFrame(toolbar)
        action_frame.grid(row=1, column=4, padx=10, pady=5, sticky="e")

        self.finish_zone_btn = ctk.CTkButton(
            action_frame,
            text="✅ Terminer zone",
            command=self._finish_current_zone,
            state="disabled"
        )
        self.finish_zone_btn.pack(side="left", padx=5)

        self.clear_btn = ctk.CTkButton(
            action_frame,
            text="🗑️ Effacer",
            command=self._clear_current_zone
        )
        self.clear_btn.pack(side="left", padx=5)

    def _create_canvas_area(self):
        """Crée la zone de canvas pour l'image"""
        canvas_frame = ctk.CTkFrame(self.window)
        canvas_frame.grid(row=1, column=0, columnspan=2, sticky="nsew", padx=10, pady=5)

        # Canvas pour l'image
        self.canvas = tk.Canvas(
            canvas_frame,
            bg="black",
            width=self.canvas_width,
            height=self.canvas_height,
            cursor="crosshair"
        )
        self.canvas.pack(expand=True, fill="both", padx=10, pady=10)

        # Bind des événements
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Motion>", self._on_canvas_motion)
        self.canvas.bind("<Button-3>", self._on_canvas_right_click)  # Clic droit pour annuler

    def _create_control_panel(self):
        """Crée le panneau de contrôle latéral"""
        control_frame = ctk.CTkFrame(self.window, width=300)
        control_frame.grid(row=1, column=2, sticky="nsew", padx=(0, 10), pady=5)

        # Titre
        ctk.CTkLabel(
            control_frame,
            text="🎛️ Contrôles",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(pady=10)

        # Zone actuelle
        current_zone_frame = ctk.CTkFrame(control_frame)
        current_zone_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(current_zone_frame, text="Zone en cours:", font=ctk.CTkFont(weight="bold")).pack(pady=5)

        self.current_zone_info = ctk.CTkTextbox(current_zone_frame, height=80)
        self.current_zone_info.pack(fill="x", padx=10, pady=5)

        # Zones définies
        zones_frame = ctk.CTkFrame(control_frame)
        zones_frame.pack(fill="both", expand=True, padx=10, pady=10)

        ctk.CTkLabel(zones_frame, text="Zones définies:", font=ctk.CTkFont(weight="bold")).pack(pady=5)

        self.zones_list = ctk.CTkTextbox(zones_frame, height=200)
        self.zones_list.pack(fill="both", expand=True, padx=10, pady=5)

        # Zones prédéfinies
        preset_frame = ctk.CTkFrame(control_frame)
        preset_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(preset_frame, text="Zones prédéfinies:", font=ctk.CTkFont(weight="bold")).pack(pady=5)

        preset_road_btn = ctk.CTkButton(
            preset_frame,
            text="🛣️ Zone route (centre)",
            command=self._add_preset_road,
            height=30
        )
        preset_road_btn.pack(fill="x", padx=10, pady=2)

        preset_trees_btn = ctk.CTkButton(
            preset_frame,
            text="🌳 Zones arbres (côtés)",
            command=self._add_preset_trees,
            height=30
        )
        preset_trees_btn.pack(fill="x", padx=10, pady=2)

        # Actions finales
        final_frame = ctk.CTkFrame(control_frame)
        final_frame.pack(fill="x", padx=10, pady=5)

        save_btn = ctk.CTkButton(
            final_frame,
            text="💾 Sauvegarder",
            command=self._save_configuration,
            height=40,
            fg_color="green",
            hover_color="darkgreen"
        )
        save_btn.pack(fill="x", padx=10, pady=5)

        load_btn = ctk.CTkButton(
            final_frame,
            text="📂 Charger",
            command=self._load_configuration,
            height=30
        )
        load_btn.pack(fill="x", padx=10, pady=2)

        apply_btn = ctk.CTkButton(
            final_frame,
            text="✅ Appliquer et fermer",
            command=self._apply_and_close,
            height=40,
            fg_color="blue",
            hover_color="darkblue"
        )
        apply_btn.pack(fill="x", padx=10, pady=5)

    def _create_status_bar(self):
        """Crée la barre de statut"""
        status_frame = ctk.CTkFrame(self.window, height=40)
        status_frame.grid(row=2, column=0, columnspan=3, sticky="ew", padx=10, pady=5)

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Prêt - Cliquez sur l'image pour commencer à définir une zone"
        )
        self.status_label.pack(pady=10)

    def _load_first_frame(self):
        """Charge la première frame de la vidéo"""
        try:
            self.video_cap = cv2.VideoCapture(self.video_path)
            if not self.video_cap.isOpened():
                raise RuntimeError("Impossible d'ouvrir la vidéo")

            # Lire la première frame
            ret, frame = self.video_cap.read()
            if ret:
                self.current_frame = frame
                self._display_frame()
            else:
                raise RuntimeError("Impossible de lire la première frame")

        except Exception as e:
            logger.error(f"Erreur chargement vidéo: {e}")
            messagebox.showerror("Erreur", f"Impossible de charger la vidéo: {e}")

    def _display_frame(self):
        """Affiche la frame sur le canvas"""
        if self.current_frame is None:
            return

        # Redimensionner la frame pour le canvas
        frame_rgb = cv2.cvtColor(self.current_frame, cv2.COLOR_BGR2RGB)
        h, w = frame_rgb.shape[:2]

        # Calculer le scaling pour maintenir le ratio
        scale = min(self.canvas_width / w, self.canvas_height / h)
        new_w = int(w * scale)
        new_h = int(h * scale)

        if new_w > 0 and new_h > 0:
            frame_resized = cv2.resize(frame_rgb, (new_w, new_h))

            # Dessiner les zones existantes
            frame_with_zones = self._draw_zones_on_frame(frame_resized)

            # Convertir pour tkinter
            image = Image.fromarray(frame_with_zones)
            self.canvas_image = ImageTk.PhotoImage(image)

            # Afficher sur le canvas
            self.canvas.delete("all")
            self.canvas.create_image(
                self.canvas_width // 2,
                self.canvas_height // 2,
                anchor=tk.CENTER,
                image=self.canvas_image
            )

            # Dessiner la zone en cours
            self._draw_current_zone()

    def _draw_zones_on_frame(self, frame: np.ndarray) -> np.ndarray:
        """Dessine les zones définies sur la frame"""
        overlay = frame.copy()

        # Dessiner zones d'exclusion (rouge)
        for zone in self.exclusion_zones:
            if len(zone['polygon']) >= 3:
                points = np.array(self._scale_points_to_canvas(zone['polygon']), np.int32)
                cv2.fillPoly(overlay, [points], (255, 0, 0, 100))
                cv2.polylines(frame, [points], True, (255, 0, 0), 2)

        # Dessiner zones d'inclusion (vert)
        for zone in self.inclusion_zones:
            if len(zone['polygon']) >= 3:
                points = np.array(self._scale_points_to_canvas(zone['polygon']), np.int32)
                cv2.fillPoly(overlay, [points], (0, 255, 0, 50))
                cv2.polylines(frame, [points], True, (0, 255, 0), 2)

        # Mélanger avec transparence
        cv2.addWeighted(overlay, 0.3, frame, 0.7, 0, frame)

        return frame

    def _draw_current_zone(self):
        """Dessine la zone en cours de définition"""
        if len(self.current_zone_points) < 2:
            return

        # Convertir les points à l'échelle du canvas
        canvas_points = self._scale_points_to_canvas(self.current_zone_points)

        # Dessiner les lignes
        color = "red" if self.current_zone_type == "exclusion" else "green"
        for i in range(len(canvas_points) - 1):
            self.canvas.create_line(
                canvas_points[i][0], canvas_points[i][1],
                canvas_points[i+1][0], canvas_points[i+1][1],
                fill=color, width=2, tags="current_zone"
            )

        # Dessiner les points
        for point in canvas_points:
            self.canvas.create_oval(
                point[0]-3, point[1]-3, point[0]+3, point[1]+3,
                fill=color, outline="white", tags="current_zone"
            )

    def _scale_points_to_canvas(self, points: List[Tuple[int, int]]) -> List[Tuple[int, int]]:
        """Convertit les points de l'image vers les coordonnées du canvas"""
        if not points or self.current_frame is None:
            return []

        h, w = self.current_frame.shape[:2]
        scale = min(self.canvas_width / w, self.canvas_height / h)

        offset_x = (self.canvas_width - w * scale) // 2
        offset_y = (self.canvas_height - h * scale) // 2

        scaled_points = []
        for x, y in points:
            canvas_x = int(x * scale + offset_x)
            canvas_y = int(y * scale + offset_y)
            scaled_points.append((canvas_x, canvas_y))

        return scaled_points

    def _scale_point_to_image(self, canvas_point: Tuple[int, int]) -> Tuple[int, int]:
        """Convertit un point du canvas vers les coordonnées de l'image"""
        if self.current_frame is None:
            return canvas_point

        h, w = self.current_frame.shape[:2]
        scale = min(self.canvas_width / w, self.canvas_height / h)

        offset_x = (self.canvas_width - w * scale) // 2
        offset_y = (self.canvas_height - h * scale) // 2

        image_x = int((canvas_point[0] - offset_x) / scale)
        image_y = int((canvas_point[1] - offset_y) / scale)

        return (image_x, image_y)

    def _on_canvas_click(self, event):
        """Gestion du clic sur le canvas"""
        # Convertir le point cliqué vers les coordonnées image
        image_point = self._scale_point_to_image((event.x, event.y))
        self.current_zone_points.append(image_point)

        # Mettre à jour l'affichage
        self._update_current_zone_info()
        self._display_frame()

        # Activer le bouton de finalisation si assez de points
        if len(self.current_zone_points) >= 3:
            self.finish_zone_btn.configure(state="normal")

        self.status_label.configure(
            text=f"Point {len(self.current_zone_points)} ajouté - Clic droit pour terminer"
        )

    def _on_canvas_motion(self, event):
        """Gestion du mouvement de souris"""
        if len(self.current_zone_points) > 0:
            # Afficher une ligne de prévisualisation
            last_point = self._scale_points_to_canvas([self.current_zone_points[-1]])[0]
            self.canvas.delete("preview_line")
            self.canvas.create_line(
                last_point[0], last_point[1], event.x, event.y,
                fill="yellow", width=1, dash=(5, 5), tags="preview_line"
            )

    def _on_canvas_right_click(self, event):
        """Gestion du clic droit (terminer zone)"""
        if len(self.current_zone_points) >= 3:
            self._finish_current_zone()

    def _on_zone_type_changed(self, value):
        """Callback quand le type de zone change"""
        self.current_zone_type = value
        self._display_frame()

    def _update_current_zone_info(self):
        """Met à jour l'info de la zone courante"""
        info = f"Type: {self.current_zone_type}\n"
        info += f"Points: {len(self.current_zone_points)}\n"
        if len(self.current_zone_points) >= 3:
            info += "✅ Prêt à finaliser"
        else:
            info += f"❌ Besoin de {3 - len(self.current_zone_points)} points"

        self.current_zone_info.delete("0.0", "end")
        self.current_zone_info.insert("0.0", info)

    def _clear_current_zone(self):
        """Efface la zone en cours"""
        self.current_zone_points.clear()
        self.finish_zone_btn.configure(state="disabled")
        self.canvas.delete("current_zone")
        self.canvas.delete("preview_line")
        self._update_current_zone_info()
        self.status_label.configure(text="Zone effacée - Recommencez")

    def _finish_current_zone(self):
        """Finalise la zone courante"""
        if len(self.current_zone_points) < 3:
            messagebox.showwarning("Attention", "Une zone doit avoir au moins 3 points")
            return

        zone_name = self.zone_name_entry.get().strip()
        if not zone_name:
            zone_name = f"{self.current_zone_type}_{len(self.exclusion_zones + self.inclusion_zones) + 1}"

        zone_data = {
            'name': zone_name,
            'type': self.current_zone_type,
            'polygon': self.current_zone_points.copy(),
            'active': True
        }

        if self.current_zone_type == "exclusion":
            self.exclusion_zones.append(zone_data)
        else:
            self.inclusion_zones.append(zone_data)

        # Réinitialiser
        self.current_zone_points.clear()
        self.zone_name_entry.delete(0, 'end')
        self.finish_zone_btn.configure(state="disabled")
        self.canvas.delete("current_zone")
        self.canvas.delete("preview_line")

        # Mettre à jour l'affichage
        self._update_zones_list()
        self._update_current_zone_info()
        self._display_frame()

        self.status_label.configure(text=f"Zone '{zone_name}' ajoutée ✅")
        logger.info(f"Zone {self.current_zone_type} ajoutée: {zone_name}")

    def _update_zones_list(self):
        """Met à jour la liste des zones définies"""
        zones_text = ""

        if self.exclusion_zones:
            zones_text += "🚫 ZONES D'EXCLUSION:\n"
            for zone in self.exclusion_zones:
                zones_text += f"  • {zone['name']} ({len(zone['polygon'])} points)\n"
            zones_text += "\n"

        if self.inclusion_zones:
            zones_text += "✅ ZONES D'INCLUSION:\n"
            for zone in self.inclusion_zones:
                zones_text += f"  • {zone['name']} ({len(zone['polygon'])} points)\n"

        if not zones_text:
            zones_text = "Aucune zone définie"

        self.zones_list.delete("0.0", "end")
        self.zones_list.insert("0.0", zones_text)

    def _add_preset_road(self):
        """Ajoute une zone de route prédéfinie"""
        if self.current_frame is None:
            return

        h, w = self.current_frame.shape[:2]
        road_zone = [
            (int(w * 0.1), int(h * 0.4)),   # Haut gauche
            (int(w * 0.9), int(h * 0.4)),   # Haut droite
            (int(w * 0.9), int(h * 0.9)),   # Bas droite
            (int(w * 0.1), int(h * 0.9))    # Bas gauche
        ]

        zone_data = {
            'name': 'route_principale',
            'type': 'inclusion',
            'polygon': road_zone,
            'active': True
        }

        self.inclusion_zones.append(zone_data)
        self._update_zones_list()
        self._display_frame()

        messagebox.showinfo("Zone ajoutée", "Zone de route prédéfinie ajoutée")

    def _add_preset_trees(self):
        """Ajoute des zones d'arbres prédéfinies"""
        if self.current_frame is None:
            return

        h, w = self.current_frame.shape[:2]

        # Zone arbre gauche
        tree_left = [
            (0, 0),
            (int(w * 0.15), 0),
            (int(w * 0.1), int(h * 0.5)),
            (0, int(h * 0.4))
        ]

        # Zone arbre droite
        tree_right = [
            (int(w * 0.85), 0),
            (w, 0),
            (w, int(h * 0.4)),
            (int(w * 0.9), int(h * 0.5))
        ]

        zones = [
            {'name': 'arbre_gauche', 'polygon': tree_left},
            {'name': 'arbre_droite', 'polygon': tree_right}
        ]

        for zone_info in zones:
            zone_data = {
                'name': zone_info['name'],
                'type': 'exclusion',
                'polygon': zone_info['polygon'],
                'active': True
            }
            self.exclusion_zones.append(zone_data)

        self._update_zones_list()
        self._display_frame()

        messagebox.showinfo("Zones ajoutées", "Zones d'arbres prédéfinies ajoutées")

    def _save_configuration(self):
        """Sauvegarde la configuration ROI"""
        if not self.exclusion_zones and not self.inclusion_zones:
            messagebox.showwarning("Attention", "Aucune zone à sauvegarder")
            return

        file_path = filedialog.asksaveasfilename(
            title="Sauvegarder configuration ROI",
            defaultextension=".json",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                h, w = self.current_frame.shape[:2] if self.current_frame is not None else (480, 640)

                config_data = {
                    'video_path': self.video_path,
                    'frame_dimensions': [w, h],
                    'exclusion_zones': self.exclusion_zones,
                    'inclusion_zones': self.inclusion_zones
                }

                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config_data, f, indent=2)

                messagebox.showinfo("Succès", f"Configuration sauvegardée:\n{file_path}")
                logger.info(f"Configuration ROI sauvegardée: {file_path}")

            except Exception as e:
                logger.error(f"Erreur sauvegarde: {e}")
                messagebox.showerror("Erreur", f"Erreur lors de la sauvegarde: {e}")

    def _load_configuration(self):
        """Charge une configuration ROI"""
        file_path = filedialog.askopenfilename(
            title="Charger configuration ROI",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    config_data = json.load(f)

                self.exclusion_zones = config_data.get('exclusion_zones', [])
                self.inclusion_zones = config_data.get('inclusion_zones', [])

                self._update_zones_list()
                self._display_frame()

                messagebox.showinfo("Succès", f"Configuration chargée:\n{file_path}")
                logger.info(f"Configuration ROI chargée: {file_path}")

            except Exception as e:
                logger.error(f"Erreur chargement: {e}")
                messagebox.showerror("Erreur", f"Erreur lors du chargement: {e}")

    def _apply_and_close(self):
        """Applique la configuration et ferme la fenêtre"""
        if not self.exclusion_zones and not self.inclusion_zones:
            result = messagebox.askquestion(
                "Aucune zone",
                "Aucune zone définie. Voulez-vous continuer sans filtrage ?"
            )
            if result != 'yes':
                return

        # Préparer les données pour le callback
        roi_config = {
            'exclusion_zones': self.exclusion_zones,
            'inclusion_zones': self.inclusion_zones,
            'frame_dimensions': self.current_frame.shape[:2][::-1] if self.current_frame is not None else (640, 480)
        }

        # Appeler le callback si fourni
        if self.callback:
            self.callback(roi_config)

        self.window.destroy()
        logger.info("Configuration ROI appliquée et fenêtre fermée")

    def __del__(self):
        """Nettoyage lors de la fermeture"""
        if hasattr(self, 'video_cap') and self.video_cap:
            self.video_cap.release()