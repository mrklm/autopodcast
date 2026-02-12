# Changelog

Toutes les modifications notables du projet AutoPodcast sont documentées ici.

Le format s’inspire de *Keep a Changelog*  
et le versionnement suit le principe du *Semantic Versioning*.


---

## [1.1.5] — 2026-02-12

### Modifié

 - Problème d'affichage de l'image du programme sous linux

---

## [1.1.4] — 2026-02-12

### Modifié

 - Problème d'affichage de l'image du programme sous linux

---

## [1.1.3] — 2026-02-12

### Modifié

 - Nettoyage d'incohérences dans le script en rapport avec les commandes pour éffacer 
   les métadonnées

---

## [1.1.2] — 2026-02-12

### Modifié

 - Efface réelement les métadonnées (case cochée par défaut dans options)

---

## [1.1.1] — 2026-02-01

### Ajouté

 - Section aide en lettres blanches sur fond noir
 - Taille police aide = 14

---

## [1.1] — 2026-02-01

### Ajouté

 - Journal onglet général lettres blanches sur fond noir

---

## [1.0] — 2026-02-01

### Ajouté

 - Options de normalisation (simple ou double passe)

### Technique

- Nomralisation via ffmpeg --> dynaudnorm / loudnorm

  mode 1 passe: (dynaudnorm)
  ffmpeg -i input.mp3 -af dynaudnorm=f=150:g=15 output.mp3

  mode 2 passe: (loudnorm)
  ffmpeg -i input.mp3 -af loudnorm=I=-16:LRA=11:TP=-1.5:print_format=json -f null -
  ffmpeg -i input.mp3 -af loudnorm=I=-16:LRA=11:TP=-1.5:measured_I=...:measured_LRA=...:measured_TP=...:measured_thresh=...:offset=...:linear=true:print_format=summary output.mp3

---

## [0.1.1] — 2026-01-31

### Corrigé

- Chargement des assets (image, aide) en mode application macOS (.app)
- Chemins de ressources compatibles PyInstaller

### Technique

- Ajout de la fonction resource_path()
- Correction de la persistance de la configuration utilisateur

---

## [0.1.0] — 2026-01-31

### Ajouté

- Application AutoPodcast (structure initiale)
- Interface graphique Tkinter avec onglets
- Onglet Options
- Onglet Aide avec chargement du fichier `assets/AIDE.md`
- Gestion persistante du thème (via `config.json`)
- Affichage de l’image d’accueil redimensionnée proprement
- Fichier README.md
- Fichier CHANGELOG.md
- Fichier `.gitignore` adapté au projet

### Technique

- Définition centralisée de la version (`APP_VERSION`)
- Utilisation de Pillow pour le redimensionnement d’image
- Gestion des chemins via `pathlib`
- Dépendances listées dans `requirements.txt`

