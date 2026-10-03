

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
2. Choisir un profil MP3 et activer l'amélioration du volume si besoin.
3. Lancer le traitement.

Le programme :

- renomme les fichiers de manière ordonnée,
- applique des métadonnées propres,
- exporte les fichiers préparés directement dans `PODCASTS/` sur la clé USB.

Il suffit ensuite de brancher la clé dans l’autoradio.

### Vérifier et formater la clé USB

Sélectionnez la racine de la clé puis cliquez sur **Analyser la clé USB**.
Si son format n'est pas FAT, AutoPodcast propose un formatage en FAT32.
Le bouton **Formater la clé en FAT32…** permet aussi de le demander directement.
La compatibilité finale dépend de l'autoradio ; consultez sa notice.

**Le formatage efface tous les fichiers du volume sélectionné.** Sauvegardez-les
ailleurs avant de saisir **FORMATER** dans la confirmation. Le nom, le périphérique
et la capacité sont affichés pour vérifier la cible. Ne débranchez pas la clé
pendant l'opération. Une fois terminé, actualisez la liste, sélectionnez la clé
**PODCASTS** puis analysez-la avant de préparer les fichiers.

Le formatage intégré accepte les partitions USB physiques d'au moins 512 Mio,
sur une clé à une seule partition de données (une partition EFI est tolérée sous
macOS). Il ne repartitionne pas le disque et refuse les disques internes, les
dossiers ordinaires, ainsi que les volumes contenant l'application ou le profil
utilisateur. Une clé dont l'identité ne peut pas être vérifiée est refusée.

- **Linux** : nécessite UDisks2, dosfstools et gdbus (outils GLib). Une demande
  d'autorisation système peut apparaître.
- **Windows** : lancer AutoPodcast en tant qu'administrateur ; le formatage
  FAT32 intégré est limité aux volumes de 32 Gio maximum.
- **macOS** : utilise diskutil sur une partition USB externe. Les volumes
  virtuels APFS et les clés à plusieurs partitions de données sont refusés.

Après une erreur, vérifiez l'état de la clé avant de recommencer : le formatage
peut avoir commencé. AutoPodcast ne relance pas automatiquement le traitement audio.

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
4. Conversion via ffmpeg selon le profil choisi.
5. Amélioration dynamique du volume si l'option voiture est activée.
6. Écriture des tags ID3 (titre, piste, album, etc.).
7. Export dans un dossier de sortie déterministe.

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
