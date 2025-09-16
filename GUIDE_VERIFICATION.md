# 🔍 Guide de Vérification Rapide par Classe

Ce guide explique comment utiliser la fonctionnalité de **vérification rapide** pour examiner efficacement tous les bus, camions, voitures ou piétons détectés.

## 🚀 Comment utiliser la vérification

### 1. **Lancer l'analyse**
1. Sélectionnez une vidéo dans `test_camera/`
2. Ajustez les paramètres (confiance, classes)
3. Cliquez **"▶️ Analyser"**
4. Attendez la fin de l'analyse

### 2. **Ouvrir la vérification**
1. Cliquez **"🔍 Vérifier par classe"** (activé après analyse)
2. Une nouvelle fenêtre s'ouvre avec tous les objets détectés

## 🎯 Interface de vérification

### **Zone principale**
- **Image**: Frame vidéo avec détection mise en évidence
- **Zoom**: Molette de souris pour zoomer/dézoomer
- **Navigation**: Boutons ⬅️ ➡️ pour parcourir

### **Panneau d'informations**
- **Détails**: Classe, confiance, position, dimensions
- **Validation**:
  - ✅ **Valide** - Détection correcte
  - ❌ **Rejeter** - Fausse détection
  - ⏭️ **Passer** - Reporter la décision

### **Contrôles**
- **Classe**: Sélecteur pour bus, voitures, camions, piétons
- **Compteur**: Position actuelle (ex: 5/23)
- **Aller à**: Navigation rapide vers un numéro
- **Statistiques**: Total, validés, rejetés, en attente

## 📋 Workflow recommandé pour vérifier les bus

### **Méthode rapide** (5-10 minutes)
1. Sélectionner **"bus"** dans le menu déroulant
2. Parcourir rapidement avec ➡️
3. Valider ✅ ou rejeter ❌ chaque détection
4. Les cas douteux : utiliser ⏭️ **Passer**

### **Méthode détaillée** (15-30 minutes)
1. Examiner chaque bus individuellement
2. Vérifier la taille et forme (bus vs camion)
3. Zoomer avec la molette si nécessaire
4. Noter les erreurs de classification

## 🎨 Codes couleur des détections

- **🟢 Vert** : Voitures
- **🔴 Rouge** : Camions
- **🟠 Orange** : Bus/Gros camions
- **🟡 Jaune** : Piétons

## ⚡ Raccourcis clavier

- **Flèches** ⬅️➡️ : Navigation
- **Espace** : Valider (✅)
- **Suppr** : Rejeter (❌)
- **Tab** : Passer (⏭️)
- **1-4** : Changer de classe rapidement

## 📊 Statistiques en temps réel

La barre du haut affiche :
- **Total** : Nombre de détections
- **✅ Validés** : Détections confirmées
- **❌ Rejetés** : Fausses détections
- **⏳ En attente** : Non vérifiées

## 💾 Export des résultats

1. Cliquez **"💾 Exporter"**
2. Choisissez l'emplacement
3. Fichier JSON avec :
   - Résultats de vérification
   - Timestamps des détections
   - Statistiques de validation

## 🎯 Cas d'usage typiques

### **Vérifier tous les bus** (votre demande)
1. Sélectionner classe **"bus"**
2. Parcourir les 15-30 détections typiques
3. Identifier les erreurs (camions classés bus)
4. Valider les vrais bus
5. Export pour rapport final

### **Contrôle qualité complet**
1. Vérifier chaque classe une par une
2. Noter les patterns d'erreurs
3. Ajuster les seuils si nécessaire
4. Relancer l'analyse avec nouveaux paramètres

### **Vérification rapide**
- Juste les détections avec confiance < 0.7
- Focus sur les objets de grande taille
- Validation des cas ambigus uniquement

## 🔧 Conseils et astuces

### **Pour les bus spécifiquement :**
- Vérifier la longueur (bus = très allongés)
- Distinguer bus vs gros camions
- Attention aux remorques classées comme bus

### **Performance :**
- Utilisez le zoom pour les détections floues
- Navigation rapide avec "Aller à N°"
- Sauvegardez régulièrement (Ctrl+S)

### **Cas difficiles :**
- Véhicules partiellement visibles → souvent rejeter
- Objets très éloignés → confiance faible
- Véhicules superposés → vérifier manuellement

## 📈 Résultats attendus

**Temps typique :**
- 50 détections de bus : 10-15 minutes
- Vérification complète : 30-45 minutes
- Contrôle de qualité : 5 minutes

**Précision améliorée :**
- Avant vérification : ~85% précision
- Après vérification : ~95% précision
- Élimination des faux positifs

Cette fonctionnalité vous permet de **rapidement** examiner et valider chaque bus détecté, assurant une analyse de circulation de haute qualité ! 🚌✅