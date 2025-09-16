# Cam_detect - Analyse de Circulation Vidéo

## Vue d'ensemble
Application Windows 11 pour l'analyse automatique de circulation à partir de vidéos de surveillance. Détecte et classifie différents types de véhicules et piétons pour générer des statistiques de passage.

## Fonctionnalités
- **Détection multi-classes**: Voitures, camions, gros camions, piétons, piétons avec chiens
- **Analyse vidéo**: Traitement de fichiers MP4 de surveillance
- **Statistiques**: Comptage et analyse temporelle des passages
- **Interface GUI**: Interface moderne Windows 11 avec customtkinter
- **Performance**: YOLOv8 optimisé (95.5% mAP pour véhicules)

## Structure du Projet
```
Cam_detect/
├── src/
│   ├── core/           # Moteur de détection YOLOv8
│   ├── models/         # Classes d'objets détectés
│   ├── utils/          # Utilitaires et helpers
│   └── gui/            # Interface utilisateur
├── data/
│   ├── input/          # Vidéos à analyser
│   ├── output/         # Résultats et statistiques
│   └── cache/          # Cache temporaire
├── config/             # Fichiers de configuration
├── logs/               # Logs d'exécution
├── test_camera/        # Dataset vidéos existant (100+ fichiers)
└── requirements.txt    # Dépendances Python
```

## Installation

### Prérequis
- Python 3.8+
- Windows 11
- GPU NVIDIA recommandé (optionnel mais plus rapide)

### Configuration
1. Cloner ou télécharger le projet
2. Installer les dépendances:
```bash
pip install -r requirements.txt
```
3. Lancer l'application:
```bash
python src/main.py
```

## Classes Détectées
- **Voiture**: Véhicules légers
- **Camion**: Véhicules utilitaires moyens
- **Gros camion**: Poids lourds, semi-remorques
- **Piéton**: Personnes seules
- **Piéton avec chien**: Personnes accompagnées d'animaux

## Technologies Utilisées
- **YOLOv8**: Détection d'objets en temps réel (Ultralytics)
- **OpenCV**: Traitement vidéo
- **CustomTkinter**: Interface Windows 11
- **PyTorch**: Framework de deep learning
- **Pandas**: Analyse de données

## Données Test
Le dossier `test_camera/` contient 1 fichiers vidéo MP4 de surveillance réelle, parfait pour développer et tester le système d'analyse.

## Auteur
David François - Développement pour analyse de circulation urbaine
