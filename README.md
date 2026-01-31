# AutoPodcast

AutoPodcast est un outil Python destiné à préparer des podcasts et contenus audio
pour une lecture fiable sur autoradios USB.

Il répond à un problème simple et toujours actuel :  
de nombreux autoradios, anciens comme récents, gèrent très mal l’ordre de lecture,
les métadonnées et la reprise lorsqu’on utilise une clé USB.

AutoPodcast prépare les fichiers **en amont**, de manière déterministe.

---

## Objectif du projet

- Forcer un ordre de lecture clair et stable
- Générer des fichiers audio compatibles avec des autoradios simples
- Éviter les tris aléatoires et les reprises incohérentes
- Fonctionner sans dépendre d’une application mobile ou d’un réseau

Ce projet ne cherche pas à remplacer une application de podcast moderne,
mais à rendre **fiable** un environnement contraint.

---

## Fonctionnalités principales

- Interface graphique (Tkinter / ttk)
- Conversion et traitement audio via ffmpeg
- Écriture de métadonnées (ID3)
- Numérotation explicite des fichiers
- Thème de couleurs persistant
- Aide intégrée via un fichier Markdown

---

## Structure du projet

