# Changelog

Toutes les modifications notables du projet AutoPodcast sont documentées ici.

Le format s’inspire de *Keep a Changelog*  
et le versionnement suit le principe du *Semantic Versioning*.

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

---

## [À venir]

### Prévu
- Amélioration de la détection de ffmpeg
- Messages d’erreur plus explicites
- Gestion multi-plateforme affinée
- Améliorations ergonomiques de l’interface
