#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Script de test pour vérifier l'installation de Cam_detect
Teste tous les modules et dépendances principales
"""

import sys
import os
from pathlib import Path

def test_python_version():
    """Test de la version Python"""
    print("🐍 Test de Python...")
    version = sys.version_info
    if version.major >= 3 and version.minor >= 8:
        print(f"   ✅ Python {version.major}.{version.minor} - OK")
        return True
    else:
        print(f"   ❌ Python {version.major}.{version.minor} - Version trop ancienne (requis: 3.8+)")
        return False

def test_dependencies():
    """Test des dépendances principales"""
    print("\n📦 Test des dépendances...")

    dependencies = [
        ('ultralytics', 'YOLOv8'),
        ('cv2', 'OpenCV'),
        ('customtkinter', 'CustomTkinter'),
        ('torch', 'PyTorch'),
        ('numpy', 'NumPy'),
        ('PIL', 'Pillow'),
        ('pandas', 'Pandas'),
        ('yaml', 'PyYAML'),
        ('loguru', 'Loguru'),
        ('sklearn', 'Scikit-learn')
    ]

    failed_imports = []

    for module, name in dependencies:
        try:
            __import__(module)
            print(f"   ✅ {name} - OK")
        except ImportError:
            print(f"   ❌ {name} - MANQUANT")
            failed_imports.append(name)

    return len(failed_imports) == 0, failed_imports

def test_project_structure():
    """Test de la structure du projet"""
    print("\n📁 Test de la structure du projet...")

    required_paths = [
        'src/main.py',
        'src/core/__init__.py',
        'src/core/detector.py',
        'src/core/video_processor.py',
        'src/core/tracker.py',
        'src/gui/__init__.py',
        'src/gui/main_window.py',
        'src/models/__init__.py',
        'src/models/advanced_classifier.py',
        'src/utils/__init__.py',
        'src/utils/logger.py',
        'src/utils/config_manager.py',
        'config/config.yaml',
        'requirements.txt',
        'README.md'
    ]

    project_root = Path(__file__).parent
    missing_files = []

    for path in required_paths:
        file_path = project_root / path
        if file_path.exists():
            print(f"   ✅ {path} - OK")
        else:
            print(f"   ❌ {path} - MANQUANT")
            missing_files.append(path)

    return len(missing_files) == 0, missing_files

def test_video_files():
    """Test de la présence de fichiers vidéo de test"""
    print("\n🎥 Test des fichiers vidéo de test...")

    test_dir = Path(__file__).parent / "test_camera"

    if not test_dir.exists():
        print("   ❌ Répertoire test_camera non trouvé")
        return False

    video_files = list(test_dir.glob("*.mp4"))

    if len(video_files) > 0:
        print(f"   ✅ {len(video_files)} fichiers vidéo trouvés")
        print(f"   📄 Premier fichier: {video_files[0].name}")
        return True
    else:
        print("   ⚠️  Aucun fichier vidéo MP4 trouvé dans test_camera/")
        return False

def test_yolo_model():
    """Test de chargement du modèle YOLOv8"""
    print("\n🤖 Test du modèle YOLOv8...")

    try:
        from ultralytics import YOLO

        # Tenter de charger un modèle nano (le plus léger)
        model = YOLO('yolov8n.pt')
        print("   ✅ Modèle YOLOv8 chargé avec succès")

        # Tester une inférence simple
        import numpy as np
        dummy_image = np.zeros((640, 640, 3), dtype=np.uint8)
        results = model(dummy_image, verbose=False)
        print("   ✅ Inférence de test réussie")

        return True

    except Exception as e:
        print(f"   ❌ Erreur avec YOLOv8: {e}")
        return False

def test_gui_import():
    """Test d'import de l'interface graphique"""
    print("\n🖥️  Test de l'interface graphique...")

    try:
        # Ajouter src au path
        sys.path.insert(0, str(Path(__file__).parent / "src"))

        from utils.config_manager import ConfigManager
        from utils.logger import setup_logger
        print("   ✅ Modules utilitaires - OK")

        from core.detector import TrafficDetector
        from core.video_processor import VideoProcessor
        from core.tracker import MultiObjectTracker
        print("   ✅ Modules core - OK")

        from models.advanced_classifier import AdvancedClassifier
        print("   ✅ Modules models - OK")

        from gui.main_window import MainWindow
        print("   ✅ Interface graphique - OK")

        return True

    except Exception as e:
        print(f"   ❌ Erreur d'import: {e}")
        return False

def main():
    """Test principal"""
    print("🔍 CAM_DETECT - TEST D'INSTALLATION")
    print("=" * 50)

    tests = [
        ("Version Python", test_python_version),
        ("Dépendances", lambda: test_dependencies()[0]),
        ("Structure projet", lambda: test_project_structure()[0]),
        ("Fichiers vidéo", test_video_files),
        ("Modèle YOLOv8", test_yolo_model),
        ("Interface graphique", test_gui_import)
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"   ❌ Erreur inattendue: {e}")
            results.append((test_name, False))

    # Résumé
    print("\n" + "=" * 50)
    print("📋 RÉSUMÉ DES TESTS")
    print("=" * 50)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ RÉUSSI" if result else "❌ ÉCHEC"
        print(f"{test_name:<20} : {status}")
        if result:
            passed += 1

    print("-" * 50)
    print(f"Tests réussis: {passed}/{total}")

    if passed == total:
        print("\n🎉 INSTALLATION COMPLÈTE ET FONCTIONNELLE!")
        print("Vous pouvez lancer l'application avec: python src/main.py")
        return 0
    else:
        print(f"\n⚠️  PROBLÈMES DÉTECTÉS ({total - passed} échecs)")
        print("Consultez les messages d'erreur ci-dessus pour résoudre les problèmes.")
        return 1

if __name__ == "__main__":
    exit_code = main()

    print(f"\nAppuyez sur Entrée pour fermer...")
    input()
    sys.exit(exit_code)