

# AutoPodcast — Aide

## Pourquoi ce programme ?

AutoPodcast est né d’un constat simple :  
beaucoup d’autoradios (anciens & récents) gèrent très mal les podcasts via USB.

Problèmes fréquents :

- ordre de lecture incohérent,
- reprise de lecture inexistante ou aléatoire,
- tri alphabétique approximatif,
- métadonnées partiellement ignorées.

AutoPodcast prépare les fichiers en amont pour que l’autoradio n’ait plus à “réfléchir”.  
Le but n’est pas d’être intelligent, mais d’être prévisible.

---

## Comment utiliser ce programme ?

1. Sélectionner un dossier contenant des fichiers audio (podcasts, émissions, conférences…).
2. Choisir un profil MP3 (bitrate, mono/stéréo, normalisation si activée).
3. Lancer le traitement.

Le programme :

- renomme les fichiers de manière ordonnée,
- applique des métadonnées propres,
- exporte un dossier prêt à être copié sur une clé USB.

Il suffit ensuite de brancher la clé dans l’autoradio.

---

## Comment fonctionne ce programme ? (niveau technique)

### Architecture générale

- Interface : **Tkinter / ttk**
- Traitement audio : **ffmpeg**
- Métadonnées : **mutagen**
- Configuration persistante : **JSON local (`config.json`)**

### Pipeline de traitement

1. Lecture du dossier source.
2. Analyse des fichiers audio.
3. Génération d’un ordre explicite (numérotation).
4. Conversion / normalisation via ffmpeg selon le profil choisi.
5. Écriture des tags ID3 (titre, piste, album, etc.).
6. Export dans un dossier de sortie déterministe.

### Pourquoi ça marche avec des autoradios “simples”

Les autoradios USB lisent généralement :

- par **nom de fichier**,
- parfois par **ordre de copie**,
- rarement par métadonnées complètes.

AutoPodcast force donc :

- un nommage strict (`01 - …`, `02 - …`),
- des fichiers compatibles,
- un ordre qui ne dépend pas de l’indexation interne de l’autoradio.

### Thème et persistance

- Le thème actif est stocké dans `config.json`.
- Il est relu au démarrage et réappliqué automatiquement.
- Aucun état n’est stocké ailleurs que dans le dossier du programme.

---

## Philosophie

AutoPodcast ne cherche pas à remplacer une application de podcast moderne.  
Il cherche à rendre fiable un environnement qui ne l’est pas.

Moins d’intelligence embarquée,   

plus d'autoradios qui lisent les fichiers presents sur la clé USB.
