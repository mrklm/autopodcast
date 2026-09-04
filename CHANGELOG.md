# Changelog

Toutes les modifications notables du projet AutoPodcast sont documentées ici.

Le format s’inspire de *Keep a Changelog*  
et le versionnement suit le principe du *Semantic Versioning*.


---

## [1.1.11] — 2026-09-04

### Modifié

- Remplacement des modes de normalisation par une seule option
  `Améliorer le volume pour écoute voiture`.
- Application effective du filtre ffmpeg `dynaudnorm=f=150:g=15` lorsque cette option
  est activée.

---

## [1.1.10] — 2026-09-04

### Modifié

- Le thème est maintenant tiré au sort à chaque démarrage de l'application.

---

## [1.1.9] — 2026-09-04

### Modifié

- Suppression du sous-dossier `INBOX` : les fichiers préparés sont maintenant copiés
  directement dans `PODCASTS/` pour simplifier l'arborescence USB.

---

## [1.1.8] — 2026-09-04

### Corrigé

- Reconstruction prévue depuis le code corrigé pour éviter l'erreur
  `ffmpeg_convert_to_mp3() got an unexpected keyword argument 'strip_metadata'`
  présente dans d'anciens paquets macOS.
- Nettoyage des marqueurs de conflit restés dans le changelog.

---

## [1.1.7] — 2026-02-12

### Modifié

 - Icône prise en compte pour le build windows

## [1.1.6] — 2026-02-12

### Modifié

 - Adaptation du script autopodcast.py pour windows (chemins d'outils et image)

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

### Corrigé

- Ajout du paramètre `strip_metadata` à `ffmpeg_convert_to_mp3()`.
- Nettoyage d'incohérences dans le script en rapport avec les commandes pour effacer
  les métadonnées.

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
