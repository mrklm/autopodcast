#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Auto-Podcast — Préparation de clé USB "autoradio-safe" pour podcasts MP3

Fichiers :
- autopodcast.py   : application principale + onglet Général
- tab_options.py   : onglet Options
- tab_help.py      : onglet Aide (affiche AIDE.md)

Dépendances :
- Python 3.9+
- mutagen : pip install mutagen
- ffmpeg : embarqué dans tools/ffmpeg (ou tools/ffmpeg.exe sous Windows)

Arborescence suggérée :
autopodcast/
  autopodcast.py
  tab_options.py
  tab_help.py
  AIDE.md
  assets/
    ar.png
  tools/
    ffmpeg            (macOS/Linux)
    ffmpeg.exe        (Windows)
"""
import os
import re
import sys
import shutil
import queue
import threading
import subprocess
import platform
import json
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple, Dict

import tkinter as tk
from tkinter import ttk, filedialog, messagebox

from tab_options import OptionsTab, MP3_PROFILES, THEMES
from tab_help import HelpTab

from PIL import Image, ImageTk

def resource_path(*parts: str) -> Path:
    """
    Résout les ressources en mode source + PyInstaller (onedir/onefile).
    Gère le cas PyInstaller où sys._MEIPASS pointe sur .../_internal.
    """
    if getattr(sys, "frozen", False):
        candidates = []

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            candidates.append(mp)          # ex: .../_internal
            candidates.append(mp.parent)   # ex: .../ (où se trouvent souvent assets/)

        # Dossier de l'exécutable (très fiable en onedir)
        candidates.append(Path(sys.executable).resolve().parent)

        for base in candidates:
            p = base.joinpath(*parts)
            if p.exists():
                return p

        # Fallback (pour afficher un chemin quand même)
        return candidates[-1].joinpath(*parts)

    # Mode source
    return Path(__file__).resolve().parent.joinpath(*parts)



# Dépendance externe : mutagen
try:
    from mutagen.id3 import ID3, ID3NoHeaderError, TIT2
    from mutagen.mp3 import MP3
except Exception as e:
    ID3 = None  # type: ignore
    MP3 = None  # type: ignore
    MUTAGEN_IMPORT_ERROR = e
else:
    MUTAGEN_IMPORT_ERROR = None

APP_TITLE = "Auto-Podcast"
APP_VERSION = "1.1.7"


DEST_ROOT_DIRNAME = "PODCASTS"
DEST_SUBDIR = "INBOX"


# ----------------------------
# Utilitaires OS
# ----------------------------

def _is_windows() -> bool:
    return sys.platform.startswith("win")


def _is_macos() -> bool:
    return sys.platform == "darwin"


def _is_linux() -> bool:
    return sys.platform.startswith("linux")

def _default_config_path() -> Path:
    if _is_windows():
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "AutoPodcast" / "config.json"
        return Path.home() / "AppData" / "Roaming" / "AutoPodcast" / "config.json"

    if _is_macos():
        return Path.home() / "Library" / "Application Support" / "AutoPodcast" / "config.json"

    # Linux
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg) / "AutoPodcast" / "config.json"
    return Path.home() / ".config" / "AutoPodcast" / "config.json"

CONFIG_PATH = _default_config_path()
CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)

def detect_volumes() -> List[str]:
    """
    Retourne une liste de chemins de volumes candidats (best effort).
    - Windows : lettres de lecteurs amovibles (priorité), sinon lecteurs existants
    - macOS : /Volumes/<nom>
    - Linux : /media/<user>/<nom> et /run/media/<user>/<nom> (+ /media, /mnt)
    """
    vols: List[str] = []

    if _is_windows():
        try:
            import ctypes  # stdlib
            kernel32 = ctypes.windll.kernel32  # type: ignore
            drive_mask = kernel32.GetLogicalDrives()
            GetDriveTypeW = kernel32.GetDriveTypeW
            DRIVE_REMOVABLE = 2

            for i in range(26):
                if drive_mask & (1 << i):
                    letter = chr(ord("A") + i)
                    root = f"{letter}:\\"
                    dtype = GetDriveTypeW(ctypes.c_wchar_p(root))
                    if dtype == DRIVE_REMOVABLE and os.path.exists(root):
                        vols.append(root)

            # Fallback : tout ce qui existe
            if not vols:
                for i in range(26):
                    if drive_mask & (1 << i):
                        letter = chr(ord("A") + i)
                        root = f"{letter}:\\"
                        if os.path.exists(root):
                            vols.append(root)
        except Exception:
            for letter in "DEFGHIJKLMNOPQRSTUVWXYZ":
                root = f"{letter}:\\"
                if os.path.exists(root):
                    vols.append(root)

    elif _is_macos():
        base = Path("/Volumes")
        if base.exists():
            for p in base.iterdir():
                if p.is_dir():
                    vols.append(str(p))

    elif _is_linux():
        user = os.environ.get("USER") or os.environ.get("USERNAME") or ""
        candidates: List[Path] = []
        if user:
            candidates.extend([Path("/media") / user, Path("/run/media") / user])
        candidates.extend([Path("/media"), Path("/mnt")])

        seen = set()
        for base in candidates:
            if base.exists() and base.is_dir():
                for p in base.iterdir():
                    if p.is_dir():
                        s = str(p)
                        if s not in seen:
                            seen.add(s)
                            vols.append(s)

    return [v for v in vols if os.path.exists(v)]


def get_fs_type(volume_path: str) -> str:
    """Best effort : retourne FAT32 / FAT16 / exFAT / NTFS / UNKNOWN..."""
    try:
        if _is_windows():
            import ctypes
            kernel32 = ctypes.windll.kernel32  # type: ignore

            fs_name_buf = ctypes.create_unicode_buffer(255)
            vol_name_buf = ctypes.create_unicode_buffer(255)
            serial = ctypes.c_ulong()
            max_comp = ctypes.c_ulong()
            flags = ctypes.c_ulong()

            root = volume_path
            if not root.endswith("\\"):
                root += "\\"

            ok = kernel32.GetVolumeInformationW(
                ctypes.c_wchar_p(root),
                vol_name_buf,
                ctypes.sizeof(vol_name_buf),
                ctypes.byref(serial),
                ctypes.byref(max_comp),
                ctypes.byref(flags),
                fs_name_buf,
                ctypes.sizeof(fs_name_buf),
            )
            if ok:
                return fs_name_buf.value.upper()

        if _is_macos():
            p = subprocess.run(["diskutil", "info", volume_path], capture_output=True, text=True, check=False)
            out = (p.stdout or "") + "\n" + (p.stderr or "")
            m = re.search(r"File System Personality:\s*(.+)", out)
            if m:
                val = m.group(1).strip().upper()
                if "EXFAT" in val:
                    return "EXFAT"
                if "NTFS" in val:
                    return "NTFS"
                if "FAT_32" in val or "FAT32" in val or "MS-DOS" in val:
                    return "FAT32"
                if "FAT_16" in val or "FAT16" in val:
                    return "FAT16"
                return val

        if _is_linux():
            p = subprocess.run(["findmnt", "-no", "FSTYPE", "--target", volume_path], capture_output=True, text=True, check=False)
            fs = (p.stdout or "").strip().upper()
            if fs:
                return "VFAT" if fs == "VFAT" else fs

    except Exception:
        pass
    return "UNKNOWN"


def volume_stats(volume_path: str) -> Tuple[int, int]:
    """Retourne (total_bytes, free_bytes) best effort."""
    try:
        usage = shutil.disk_usage(volume_path)
        return usage.total, usage.free
    except Exception:
        return 0, 0


def human_bytes(n: int) -> str:
    if n <= 0:
        return "0 B"
    units = ["B", "KB", "MB", "GB", "TB"]
    f = float(n)
    i = 0
    while f >= 1024 and i < len(units) - 1:
        f /= 1024.0
        i += 1
    return f"{f:.2f} {units[i]}"


# ----------------------------
# Nettoyage titres / noms
# ----------------------------

def sanitize_title_for_filename(title: str, max_len: int = 15) -> str:
    """ASCII, sans emojis/caractères spéciaux, '_' à la place des espaces, longueur max."""
    if not title:
        title = "EPISODE"

    normalized = unicodedata.normalize("NFKD", title)
    ascii_only = normalized.encode("ascii", "ignore").decode("ascii")

    s = re.sub(r"[\s\-]+", "_", ascii_only)
    s = re.sub(r"[^A-Za-z0-9_]+", "", s)
    s = re.sub(r"_+", "_", s).strip("_")
    if not s:
        s = "EPISODE"
    return s[:max_len]


# ----------------------------
# MP3 tags
# ----------------------------

def read_mp3_title(path: Path) -> str:
    """Titre ID3 si possible, sinon nom de fichier."""
    if MUTAGEN_IMPORT_ERROR is not None or MP3 is None:
        return path.stem
    try:
        audio = MP3(str(path))
        tags = audio.tags
        if tags:
            tit2 = tags.get("TIT2")
            if tit2 and getattr(tit2, "text", None):
                t = str(tit2.text[0]).strip()
                if t:
                    return t
    except Exception:
        pass
    return path.stem

def reset_metadata_keep_title(path: Path, title: str) -> None:
    """Efface toutes les métadonnées et conserve uniquement TIT2. Écrit ID3v2.3."""
    if MUTAGEN_IMPORT_ERROR is not None or ID3 is None:
        return
    try:
        # 1) Tentative d'effacement générique (ID3, APEv2, etc.) si mutagen sait le faire
        try:
            from mutagen import File as MutagenFile  # type: ignore
            mf = MutagenFile(str(path))
            if mf is not None:
                try:
                    mf.delete()
                except Exception:
                    pass
        except Exception:
            pass

        # 2) Réécriture propre : ID3 minimal avec uniquement le titre
        try:
            tags = ID3(str(path))
        except ID3NoHeaderError:
            tags = ID3()

        tags.delete()
        tags.add(TIT2(encoding=1, text=title))
        tags.save(str(path), v2_version=3)
    except Exception:
        return

def _resource_base_dir() -> Path:
    """
    Répertoire de base pour les ressources.
    Gère PyInstaller onedir où sys._MEIPASS peut pointer sur .../_internal.
    """
    if getattr(sys, "frozen", False):
        candidates: List[Path] = []

        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            mp = Path(meipass)
            candidates.append(mp)        # .../_internal
            candidates.append(mp.parent) # .../

        candidates.append(Path(sys.executable).resolve().parent)  # dossier de l'exe

        for base in candidates:
            if base.exists():
                return base
        return candidates[-1]

    return Path(__file__).resolve().parent



def _macos_tools_subdir_names() -> List[str]:
    """
    Liste ordonnée des sous-dossiers possibles pour tools/ sur macOS.
    Supporte par exemple :
      - tools/macos/
      - tools/macos-x86_64/
      - tools/macos-arm64/
    """
    machine = platform.machine().lower()
    names: List[str] = []
    if machine in ("arm64", "aarch64"):
        names += ["macos-arm64", "macos-arm", "darwin-arm64"]
    else:
        names += ["macos-x86_64", "macos-x64", "darwin-x86_64"]
    names += ["macos", "darwin", "osx"]
    return names


def find_ffmpeg() -> Optional[Path]:
    """
    Cherche ffmpeg dans :
    - tools/… embarqué (source ou PyInstaller)
    - PATH (fallback)
    """
    base = _resource_base_dir()
    tools_root = base / "tools"

    candidates: List[Path] = []

    if _is_windows():
        # Structures possibles : tools/ffmpeg.exe ou tools/windows*/ffmpeg.exe
        candidates.extend([tools_root / "ffmpeg.exe", tools_root / "ffmpeg"])
        for sub in ("windows", "win", "win32", "win64", "windows-x86_64", "windows-amd64"):
            candidates.extend([tools_root / sub / "ffmpeg.exe", tools_root / sub / "ffmpeg"])
    elif _is_macos():
        # Structures possibles : tools/ffmpeg ou tools/macos-*/ffmpeg
        candidates.append(tools_root / "ffmpeg")
        for sub in _macos_tools_subdir_names():
            candidates.append(tools_root / sub / "ffmpeg")
    else:
        # Linux / autres : tools/ffmpeg ou tools/linux*/ffmpeg
        candidates.append(tools_root / "ffmpeg")
        for sub in ("linux", "linux-x86_64", "linux-x64", "linux-arm64", "linux-aarch64"):
            candidates.append(tools_root / sub / "ffmpeg")

    for c in candidates:
        try:
            if c.exists() and c.is_file():
                # Best-effort : s'assurer que ffmpeg est exécutable sur POSIX
                if not _is_windows():
                    try:
                        if not os.access(str(c), os.X_OK):
                            os.chmod(str(c), c.stat().st_mode | 0o111)
                    except Exception:
                        pass
                return c
        except Exception:
            continue

    which = shutil.which("ffmpeg")
    return Path(which) if which else None


def ffmpeg_convert_to_mp3(
    ffmpeg_path: Path,
    src: Path,
    dst: Path,
    bitrate: str,
    stop_event: threading.Event,
    proc_holder: Dict[str, Optional[subprocess.Popen]],
    strip_metadata: bool = False,
) -> None:

    """Convertit src -> dst en MP3 CBR 44.1 kHz Joint Stereo via ffmpeg."""
    dst.parent.mkdir(parents=True, exist_ok=True)

    cmd = [
        str(ffmpeg_path),
        "-y",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        str(src),
<<<<<<< HEAD
        # Si demandé : ne pas copier metadata/chapters depuis la source
        * (["-map_metadata", "-1", "-map_chapters", "-1"] if strip_metadata else []),
=======
    ]

    # Si demandé : ne pas copier metadata/chapters depuis la source
    if strip_metadata:
        cmd += ["-map_metadata", "-1", "-map_chapters", "-1"]

    cmd += [
>>>>>>> 217adb5880d4b66aaa2bb91ee047f8c566f6f5dd
        "-vn",
        "-ac",
        "2",
        "-ar",
        "44100",
        "-codec:a",
        "libmp3lame",
        "-b:a",
        bitrate,
        "-joint_stereo",
        "1",
    ]

    # Si demandé : sortie ID3 plus “autoradio-friendly”
    if strip_metadata:
        cmd += ["-write_id3v1", "0", "-id3v2_version", "3"]

    cmd += [str(dst)]

    if stop_event.is_set():
        raise RuntimeError("STOP_REQUESTED")

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    proc_holder["proc"] = proc
    try:
        while True:
            if stop_event.is_set():
                try:
                    proc.kill()
                except Exception:
                    pass
                raise RuntimeError("STOP_REQUESTED")

            ret = proc.poll()
            if ret is not None:
                if ret != 0:
                    err = (proc.stderr.read() if proc.stderr else "")[:1200]
                    raise RuntimeError(f"FFMPEG_ERROR: {err}")
                break
    finally:
        proc_holder["proc"] = None


# ----------------------------
# Analyse clé USB
# ----------------------------

@dataclass
class UsbAnalysis:
    volume: str
    fs_type: str
    total_bytes: int
    free_bytes: int
    file_count: int
    mp3_count: int
    other_count: int
    max_depth: int
    max_files_in_dir: int
    long_name_count: int
    non_ascii_name_count: int
    total_mp3_bytes: int
    verdict_ok: bool
    problems: List[str]


def scan_files_for_analysis(root: Path) -> Tuple[int, int, int, int, int, int, int, int]:
    """
    Retourne :
    (file_count, mp3_count, other_count, max_depth, max_files_in_dir,
     long_name_count, non_ascii_name_count, total_mp3_bytes)
    """
    file_count = 0
    mp3_count = 0
    other_count = 0
    max_depth = 0
    max_files_in_dir = 0
    long_name_count = 0
    non_ascii_name_count = 0
    total_mp3_bytes = 0

    for dirpath, _, filenames in os.walk(root):
        rel = Path(dirpath).relative_to(root)
        depth = len(rel.parts)
        max_depth = max(max_depth, depth)
        max_files_in_dir = max(max_files_in_dir, len(filenames))

        for fn in filenames:
            # ignore macOS parasites
            if fn.startswith("._") or fn.startswith(".") or fn.lower() == ".ds_store":
                continue

            file_count += 1
            p = Path(dirpath) / fn
            ext = p.suffix.lower()

            if ext == ".mp3":
                mp3_count += 1
                try:
                    total_mp3_bytes += p.stat().st_size
                except Exception:
                    pass
            else:
                other_count += 1

            if len(fn) > 64:
                long_name_count += 1

            try:
                fn.encode("ascii")
            except Exception:
                non_ascii_name_count += 1

    return (file_count, mp3_count, other_count, max_depth, max_files_in_dir, long_name_count, non_ascii_name_count, total_mp3_bytes)


def analyze_usb(volume_path: str) -> UsbAnalysis:
    fs = get_fs_type(volume_path)
    total, free = volume_stats(volume_path)

    root = Path(volume_path)
    file_count, mp3_count, other_count, max_depth, max_files_in_dir, long_name_count, non_ascii, total_mp3_bytes = scan_files_for_analysis(root)

    problems: List[str] = []
    if fs in ("EXFAT", "NTFS", "UNKNOWN"):
        problems.append(f"Système de fichiers détecté : {fs}. FAT32 (ou FAT16) est recommandé.")
    if fs == "VFAT":
        problems.append("Système de fichiers détecté : VFAT (FAT). FAT32 est recommandé si possible.")
    if max_depth > 2:
        problems.append(f"Arborescence profonde (profondeur max {max_depth}). Une arborescence simple est recommandée.")
    if max_files_in_dir > 200:
        problems.append(f"Trop de fichiers dans un même dossier (max {max_files_in_dir}). 50 à 100 est recommandé.")
    if file_count > 1500:
        problems.append(f"Beaucoup de fichiers ({file_count}). Certains autoradios limitent l'indexation.")
    if non_ascii > 0:
        problems.append(f"Noms de fichiers avec caractères non ASCII détectés ({non_ascii}). Cela peut poser problème.")
    if long_name_count > 0:
        problems.append(f"Noms de fichiers longs détectés ({long_name_count}). Des noms courts sont recommandés.")

    return UsbAnalysis(
        volume=volume_path,
        fs_type=fs,
        total_bytes=total,
        free_bytes=free,
        file_count=file_count,
        mp3_count=mp3_count,
        other_count=other_count,
        max_depth=max_depth,
        max_files_in_dir=max_files_in_dir,
        long_name_count=long_name_count,
        non_ascii_name_count=non_ascii,
        total_mp3_bytes=total_mp3_bytes,
        verdict_ok=(len(problems) == 0),
        problems=problems,
    )


def build_analysis_report(a: UsbAnalysis) -> str:
    lines: List[str] = []
    lines.append(f"=== Rapport d'analyse : {a.volume} ===")
    lines.append("")
    lines.append("Verdict : " + ("✅ Clé USB validée" if a.verdict_ok else "⚠️ Clé USB problématique"))
    lines.append("")
    if not a.verdict_ok:
        lines.append("Raisons possibles :")
        for p in a.problems:
            lines.append(f" - {p}")
        lines.append("")

    lines.append("Spécifications :")
    lines.append(f" - Système de fichiers : {a.fs_type}")
    lines.append(f" - Capacité totale : {human_bytes(a.total_bytes)}")
    lines.append(f" - Espace libre : {human_bytes(a.free_bytes)}")
    lines.append("")
    lines.append("Contenu :")
    lines.append(f" - Fichiers : {a.file_count}")
    lines.append(f" - MP3 : {a.mp3_count}")
    lines.append(f" - Autres : {a.other_count}")
    lines.append(f" - Profondeur max : {a.max_depth}")
    lines.append(f" - Max fichiers dans un dossier : {a.max_files_in_dir}")
    lines.append(f" - Noms longs (>64) : {a.long_name_count}")
    lines.append(f" - Noms non ASCII : {a.non_ascii_name_count}")
    lines.append(f" - Total MP3 : {human_bytes(a.total_mp3_bytes)}")
    lines.append("")
    lines.append("Recommandations autoradio :")
    lines.append(" - FAT32 recommandé")
    lines.append(" - 50 à 100 fichiers maximum par dossier")
    lines.append(" - Arborescence simple (2 niveaux)")
    lines.append(" - Noms de fichiers courts, ASCII")
    return "\n".join(lines)


# ----------------------------
# Config préparation
# ----------------------------

@dataclass
class PrepareConfig:
    volume: str
    source_mode: str
    selected_files: List[str]
    temp_dir: str


# ----------------------------
# Onglet Général
# ----------------------------

class GeneralTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook, app: "AutoPodcastApp") -> None:
        super().__init__(master)
        self.app = app
        self._img_ref = None  # garde référence PhotoImage

        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # Image centrée
        img_path = resource_path("assets", "ar.png")
        if img_path.exists():
            try:
                img = Image.open(str(img_path))
                MAX_SIZE = 210  # ← RÈGLE LA TAILLE ICI (en pixels)

                img.thumbnail((MAX_SIZE, MAX_SIZE), Image.LANCZOS)

                self._img_ref = ImageTk.PhotoImage(img)
                lbl_img = ttk.Label(root, image=self._img_ref)
                lbl_img.pack(anchor="center", pady=(0, 10))
            except Exception as e:
                ttk.Label(root, text=f"[Image ar.png non chargée] {type(e).__name__}: {e}").pack(anchor="center", pady=(0, 10))
        else:
            ttk.Label(root, text="[assets/ar.png manquant]").pack(anchor="center", pady=(0, 10))

        # Section clé USB (sans bouton analyse ici)
        vol_frame = ttk.LabelFrame(root, text="Clé USB", padding=10)
        vol_frame.pack(fill="x", pady=6)

        ttk.Label(vol_frame, text="Sélectionner la clé USB :").grid(row=0, column=0, sticky="w")
        self.var_volume = tk.StringVar(value="")
        self.cmb_volume = ttk.Combobox(vol_frame, textvariable=self.var_volume, values=[], state="readonly", width=45)
        self.cmb_volume.grid(row=0, column=1, sticky="we", padx=8)
        ttk.Button(vol_frame, text="Actualiser", command=self.app.refresh_volumes).grid(row=0, column=2, padx=6)
        ttk.Button(vol_frame, text="Parcourir…", command=self.app.browse_volume).grid(row=0, column=3)
        vol_frame.columnconfigure(1, weight=1)

        # Bouton analyser centré (en dessous du cadre)
        self.btn_analyze = ttk.Button(root, text="Analyser la clé USB", command=self.app.on_analyze)
        self.btn_analyze.pack(anchor="center", pady=(6, 10))

        # Section source
        src_frame = ttk.LabelFrame(root, text="Source", padding=10)
        src_frame.pack(fill="x", pady=6)

        self.var_source_mode = tk.StringVar(value="Sélectionner des fichiers")
        ttk.Label(src_frame, text="Source :").grid(row=0, column=0, sticky="w")
        self.cmb_source_mode = ttk.Combobox(
            src_frame,
            textvariable=self.var_source_mode,
            state="readonly",
            values=["Sélectionner des fichiers", "Utiliser les fichiers présents", "Fichiers présents + fichiers"],
            width=40,
        )
        self.cmb_source_mode.grid(row=0, column=1, sticky="w", padx=8)
        self.cmb_source_mode.bind("<<ComboboxSelected>>", lambda e: self._update_source_controls())

        ttk.Label(src_frame, text="Fichiers MP3 :").grid(row=1, column=0, sticky="w", pady=(10, 0))
        self.var_files = tk.StringVar(value="")
        self.ent_files = ttk.Entry(src_frame, textvariable=self.var_files)
        self.ent_files.grid(row=1, column=1, sticky="we", padx=8, pady=(10, 0))
        ttk.Button(src_frame, text="Sélectionner…", command=self.app.pick_files).grid(row=1, column=2, pady=(10, 0))

        src_frame.columnconfigure(1, weight=1)

        # Actions (centrées)
        act_frame = ttk.Frame(root)
        act_frame.pack(fill="x", pady=(10, 6))

        self.btn_prepare = ttk.Button(act_frame, text="Préparer la clé USB", command=self.app.on_prepare)
        self.btn_stop = ttk.Button(act_frame, text="Stop", command=self.app.on_stop, state="disabled")

        # Centrage via pack + expand
        self.btn_prepare.pack(side="left", expand=True)
        self.btn_stop.pack(side="left", expand=True)

        # Journal
        log_frame = ttk.LabelFrame(root, text="Journal", padding=10)
        log_frame.pack(fill="both", expand=True, pady=6)

        self.txt = tk.Text(
            log_frame,
            height=14,
            wrap="word",
            bg="black",
            fg="white",
            insertbackground="white",
            selectbackground="#444444",
            selectforeground="white",
        )
        self.txt.pack(fill="both", expand=True)
        self.txt.configure(state="disabled")

        self._update_source_controls()

    def _update_source_controls(self) -> None:
        mode = self.var_source_mode.get()
        self.ent_files.configure(state=("disabled" if mode == "Utiliser les fichiers présents" else "normal"))


# ----------------------------
# App principale
# ----------------------------

class AutoPodcastApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title(f"{APP_TITLE} v{APP_VERSION}")
        self.minsize(900, 680)

        self.stop_event = threading.Event()
        self.worker_thread: Optional[threading.Thread] = None
        self.msg_queue: "queue.Queue[Tuple[str, object]]" = queue.Queue()
        self.current_proc_holder: Dict[str, Optional[subprocess.Popen]] = {"proc": None}

        self.ffmpeg_path = find_ffmpeg()


        # Thème persistant
        self.config_data = self._load_config()
        default_theme = list(THEMES.keys())[0] if THEMES else ""
        self.current_theme_name = self.config_data.get("theme", default_theme) if default_theme else ""
        # Traitement du son (persistant)
        self.audio_norm_mode = self.config_data.get("audio_norm_mode", "Rapide (1 passe)")
        self.config_data["audio_norm_mode"] = self.audio_norm_mode

        # UI
        self._build_ui()
        
        # Appliquer le thème persistant après création de l'UI
        if self.current_theme_name:
            self.apply_theme(self.current_theme_name, save=False)
            try:
                self.tab_options.var_theme.set(self.current_theme_name)
            except Exception:
                pass

        # Volumes
        self.refresh_volumes()

        # Loop queue
        self.after(100, self._poll_queue)

        # Infos démarrage
        self._log_startup_info()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=8)
        root.pack(fill="both", expand=True)

        self.nb = ttk.Notebook(root)
        self.nb.pack(fill="both", expand=True)

        self.tab_general = GeneralTab(self.nb, self)
        self.tab_options = OptionsTab(self.nb, self)
        self.tab_help = HelpTab(self.nb, self)

        self.nb.add(self.tab_general, text="Général")
        self.nb.add(self.tab_options, text="Options")
        self.nb.add(self.tab_help, text="Aide")

        # Barre de progression bas de fenêtre (hors onglets)
        prog_frame = ttk.Frame(root)
        prog_frame.pack(fill="x", pady=(8, 0))

        self.var_status = tk.StringVar(value="Prêt.")
        ttk.Label(prog_frame, textvariable=self.var_status).pack(anchor="w")

        self.progress = ttk.Progressbar(prog_frame, orient="horizontal", mode="determinate")
        self.progress.pack(fill="x", pady=(4, 0))

    # ---------------- Journal UI ----------------

    def _log(self, msg: str) -> None:
        txt = self.tab_general.txt
        txt.configure(state="normal")
        txt.insert("end", msg + "\n")
        txt.see("end")
        txt.configure(state="disabled")

    def _set_status(self, msg: str) -> None:
        self.var_status.set(msg)

    def _set_progress(self, value: int, maximum: int) -> None:
        self.progress["maximum"] = max(1, maximum)
        self.progress["value"] = min(value, maximum)

    def _log_startup_info(self) -> None:
        self._log(f"Plateforme : {platform.system()} {platform.release()}")
        if MUTAGEN_IMPORT_ERROR is not None:
            self._log("⚠️ Dépendance manquante : mutagen n'est pas disponible.")
            self._log("   Installation : pip install mutagen")
        else:
            self._log("✅ Dépendance OK : mutagen")

        if self.ffmpeg_path is None:
            self._log("⚠️ ffmpeg non détecté. Veuillez placer ffmpeg dans tools/ ou l'ajouter au PATH.")
        else:
            self._log(f"✅ ffmpeg détecté : {self.ffmpeg_path}")

    # ---------------- Volumes / fichiers ----------------

        # ---------------- Thème (persistant) ----------------

    def _load_config(self) -> dict:
        if CONFIG_PATH.exists():
            try:
                return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
            except Exception:
                return {}
        return {}

    def _save_config(self) -> None:
        try:
            data = dict(getattr(self, "config_data", {}))
            data["theme"] = getattr(self, "current_theme_name", "")
            data["audio_norm_mode"] = getattr(self, "audio_norm_mode", "Rapide (1 passe)")
            CONFIG_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            return

    def apply_theme(self, theme_name: str, save: bool = True) -> None:
        theme = THEMES.get(theme_name)
        if not theme:
            return

        self.current_theme_name = theme_name
        if not hasattr(self, "config_data"):
            self.config_data = {}
        self.config_data["theme"] = theme_name
        if save:
            self._save_config()

        bg = theme["BG"]
        panel = theme["PANEL"]
        field = theme["FIELD"]
        fg = theme["FG"]
        field_fg = theme["FIELD_FG"]

        style = ttk.Style()

        # macOS : le thème natif "aqua" ignore la plupart des couleurs ttk.
        # Forcer un thème stylable (clam) quand disponible.
        try:
            if sys.platform == "darwin" and "clam" in style.theme_names():
                style.theme_use("clam")
            else:
                style.theme_use("default")
        except Exception:
            pass

        # Fenêtre
        try:
            self.configure(bg=bg)
        except Exception:
            pass

        # ttk de base
        style.configure("TFrame", background=bg)
        style.configure("TLabel", background=bg, foreground=fg)
        style.configure("TLabelframe", background=panel, foreground=fg)
        style.configure("TLabelframe.Label", background=panel, foreground=fg)

        # Notebook
        style.configure("TNotebook", background=bg, borderwidth=0)
        style.configure("TNotebook.Tab", background=panel, foreground=fg)
        style.map("TNotebook.Tab",
                  background=[("selected", field), ("active", panel)],
                  foreground=[("selected", fg), ("active", fg)])

        # Champs
        style.configure("TEntry", fieldbackground=field, foreground=field_fg)
        style.configure("TCombobox", fieldbackground=field, foreground=field_fg)
        style.map("TCombobox",
                  fieldbackground=[("readonly", field)],
                  foreground=[("readonly", field_fg)])

        # Widgets Tk (Text)
        self._apply_theme_to_tk_widgets(bg=bg, field=field, field_fg=field_fg)

    def _apply_theme_to_tk_widgets(self, bg: str, field: str, field_fg: str) -> None:
        def walk(widget):
            for child in widget.winfo_children():
                yield child
                yield from walk(child)

        for w in walk(self):
            if isinstance(w, tk.Text):
                try:
                    # Exception : le journal de l'onglet Général reste en blanc sur noir
                    if hasattr(self, "tab_general") and getattr(self.tab_general, "txt", None) is w:
                        w.configure(
                            background="black",
                            foreground="white",
                            insertbackground="white",
                            selectbackground="#444444",
                            selectforeground="white",
                        )

                    # Exception : l'onglet Aide reste en blanc sur noir + police 14
                    elif hasattr(self, "tab_help") and getattr(self.tab_help, "txt", None) is w:
                        w.configure(
                            background="black",
                            foreground="white",
                            insertbackground="white",
                            selectbackground="#444444",
                            selectforeground="white",
                            font=("Menlo", 14),
                        )

                    # Autres tk.Text : gérés par le thème
                    else:
                        w.configure(
                            background=field,
                            foreground=field_fg,
                            insertbackground=field_fg,
                        )
                except Exception:
                    pass


            elif isinstance(w, tk.Canvas):
                try:
                    w.configure(background=bg)
                except Exception:
                    pass

    # ---------------- Volumes / fichiers ----------------

    def refresh_volumes(self) -> None:
        """Rafraîchit la liste des volumes USB détectés et met à jour la ComboBox."""
        vols = detect_volumes()
        self.tab_general.cmb_volume["values"] = vols
        current = self.tab_general.var_volume.get()
        if vols and current not in vols:
            self.tab_general.var_volume.set(vols[0])

    def browse_volume(self) -> None:
        path = filedialog.askdirectory(title="Sélectionner la clé USB (répertoire racine du volume)")
        if path:
            self.tab_general.var_volume.set(path)

    def pick_files(self) -> None:
        files = filedialog.askopenfilenames(
            title="Sélectionner des fichiers MP3",
            filetypes=[("Fichiers MP3", "*.mp3"), ("Tous les fichiers", "*.*")],
        )
        if files:
            self.tab_general.var_files.set(";".join(files))

# ---------------- Queue poll ----------------

    def _poll_queue(self) -> None:
        try:
            while True:
                kind, payload = self.msg_queue.get_nowait()
                if kind == "log":
                    self._log(str(payload))
                elif kind == "status":
                    self._set_status(str(payload))
                elif kind == "progress":
                    v, m = payload  # type: ignore
                    self._set_progress(int(v), int(m))
                elif kind == "done":
                    self._on_worker_done(success=bool(payload))
        except queue.Empty:
            pass
        self.after(100, self._poll_queue)

    def _on_worker_done(self, success: bool) -> None:
        self.tab_general.btn_prepare.configure(state="normal")
        self.tab_general.btn_stop.configure(state="disabled")
        self.stop_event.clear()
        self.current_proc_holder["proc"] = None
        self._set_status("Terminé." if success else "Arrêté ou erreur.")

    # ---------------- Garde-fous ----------------

    def _is_probably_system_volume(self, vol: str) -> bool:
        try:
            p = Path(vol).resolve()
        except Exception:
            return False

        if _is_windows():
            sysdrive = os.environ.get("SystemDrive", "C:").upper()
            if str(p).upper() == (sysdrive + "\\"):
                return True
        else:
            if str(p) == "/":
                return True
        return False

    # ---------------- Actions : Analyse / Préparer / Stop ----------------

    def on_analyze(self) -> None:
        vol = self.tab_general.var_volume.get().strip()
        if not vol:
            messagebox.showwarning("Analyse", "Veuillez sélectionner une clé USB.")
            return
        if not os.path.exists(vol):
            messagebox.showerror("Analyse", "Le chemin sélectionné n'existe pas.")
            return
        if self._is_probably_system_volume(vol):
            messagebox.showerror("Analyse", "Le volume sélectionné semble être un disque système.")
            return

        self._set_status("Analyse en cours…")
        self._set_progress(0, 1)
        self._log("")
        try:
            a = analyze_usb(vol)
            self._log(build_analysis_report(a))
            self._set_status("Analyse terminée.")
        except Exception as e:
            self._log(f"❌ Erreur d'analyse : {e}")
            self._set_status("Erreur d'analyse.")

    def on_prepare(self) -> None:
        if MUTAGEN_IMPORT_ERROR is not None:
            messagebox.showerror("Préparation", "mutagen est requis.\nInstallez : pip install mutagen")
            return
        if self.ffmpeg_path is None or not self.ffmpeg_path.exists():
            messagebox.showerror("Préparation", "ffmpeg est requis.\nPlacez-le dans tools/ ou ajoutez-le au PATH.")
            return

        cfg = self._gather_config()
        if cfg is None:
            return

        # Analyse rapide + avertissements
        try:
            a = analyze_usb(cfg.volume)
        except Exception as e:
            messagebox.showerror("Préparation", f"Impossible d'analyser la clé : {e}")
            return

        warn_lines: List[str] = []
        fs_upper = a.fs_type.upper()
        if fs_upper in ("EXFAT", "NTFS", "UNKNOWN"):
            warn_lines.append("Le système de fichiers n'est pas FAT32/FAT16. Certains autoradios peuvent ignorer des fichiers.")
        if warn_lines:
            msg = "Avertissement :\n\n" + "\n".join(f"• {x}" for x in warn_lines) + "\n\nSouhaitez-vous continuer ?"
            if not messagebox.askyesno("Préparation", msg):
                return

        # Confirmation nettoyage /PODCASTS
        if self.tab_options.var_clean_dest.get():
            ok = messagebox.askyesno(
                "Confirmation",
                "Le dossier PODCASTS sur la clé USB sera vidé avant copie.\n"
                "Les autres fichiers de la clé ne seront pas touchés.\n\n"
                "Souhaitez-vous continuer ?"
            )
            if not ok:
                return

        self.stop_event.clear()
        self.tab_general.btn_prepare.configure(state="disabled")
        self.tab_general.btn_stop.configure(state="normal")
        self._set_progress(0, 1)
        self._set_status("Préparation en cours…")
        self._log("")
        self._log("=== Préparation : démarrage ===")

        self.worker_thread = threading.Thread(target=self._worker_prepare, args=(cfg,), daemon=True)
        self.worker_thread.start()

    def on_stop(self) -> None:
        if self.worker_thread and self.worker_thread.is_alive():
            self.stop_event.set()
            proc = self.current_proc_holder.get("proc")
            if proc is not None:
                try:
                    proc.kill()
                except Exception:
                    pass
            self.msg_queue.put(("log", "⛔ Arrêt demandé."))
            self.msg_queue.put(("status", "Arrêt en cours…"))

    # ---------------- Config et collecte ----------------

    def _gather_config(self) -> Optional[PrepareConfig]:
        vol = self.tab_general.var_volume.get().strip()
        if not vol:
            messagebox.showwarning("Préparation", "Veuillez sélectionner une clé USB.")
            return None
        if not os.path.exists(vol):
            messagebox.showerror("Préparation", "Le chemin sélectionné n'existe pas.")
            return None
        if self._is_probably_system_volume(vol):
            messagebox.showerror("Préparation", "Le volume sélectionné semble être un disque système.")
            return None

        # Temp par défaut : valeur dans onglet Options
        temp_dir = self.tab_options.var_temp.get().strip()
        if not temp_dir:
            messagebox.showerror("Préparation", "Veuillez sélectionner un répertoire temporaire (Options).")
            return None
        if not os.path.exists(temp_dir):
            messagebox.showerror("Préparation", "Le répertoire temporaire n'existe pas.")
            return None

        mode = self.tab_general.var_source_mode.get()
        selected_files: List[str] = []
        if mode in ("Sélectionner des fichiers", "Fichiers présents + fichiers"):
            raw = self.tab_general.var_files.get().strip()
            if raw:
                selected_files = [x for x in raw.split(";") if x.strip()]
            if not selected_files and mode == "Sélectionner des fichiers":
                messagebox.showwarning("Préparation", "Veuillez sélectionner des fichiers MP3.")
                return None

        return PrepareConfig(volume=vol, source_mode=mode, selected_files=selected_files, temp_dir=temp_dir)

    def _collect_sources(self, cfg: PrepareConfig) -> List[str]:
        sources: List[str] = []
        src_set = set()

        def add_mp3(p: Path) -> None:
            name = p.name
            if name.startswith("._") or name.startswith(".") or name.lower() == ".ds_store":
                return
            if p.is_file() and p.suffix.lower() == ".mp3":
                s = str(p)
                if s not in src_set:
                    src_set.add(s)
                    sources.append(s)

        # Fichiers sélectionnés
        if cfg.source_mode in ("Sélectionner des fichiers", "Fichiers présents + fichiers"):
            for f in cfg.selected_files:
                add_mp3(Path(f))

        # Fichiers présents sur la clé
        if cfg.source_mode in ("Utiliser les fichiers présents", "Fichiers présents + fichiers"):
            vol = Path(cfg.volume)
            for dirpath, _, filenames in os.walk(vol):
                for fn in filenames:
                    if fn.startswith("._") or fn.startswith(".") or fn.lower() == ".ds_store":
                        continue
                    if fn.lower().endswith(".mp3"):
                        add_mp3(Path(dirpath) / fn)

        return sources

    # ---------------- Worker préparation ----------------

    def _worker_prepare(self, cfg: PrepareConfig) -> None:
        success = False
        try:
            self.msg_queue.put(("status", "Collecte des fichiers source…"))
            sources = self._collect_sources(cfg)
            if not sources:
                self.msg_queue.put(("log", "⚠️ Aucun fichier MP3 à traiter."))
                self.msg_queue.put(("done", False))
                return

            temp_root = Path(cfg.temp_dir) / "AutoPodcast_tmp"
            temp_root.mkdir(parents=True, exist_ok=True)

            dest_root = Path(cfg.volume) / DEST_ROOT_DIRNAME
            dest_inbox = dest_root / DEST_SUBDIR

            # Nettoyage destination /PODCASTS
            if self.tab_options.var_clean_dest.get():
                self.msg_queue.put(("status", "Nettoyage du dossier PODCASTS sur la clé USB…"))
                if dest_root.exists():
                    shutil.rmtree(dest_root)
                dest_inbox.mkdir(parents=True, exist_ok=True)
            else:
                dest_inbox.mkdir(parents=True, exist_ok=True)

            # Profil bitrate
            profile_key = self.tab_options.var_profile.get()
            bitrate = MP3_PROFILES.get(profile_key, MP3_PROFILES["MP3 - Standard - CBR 128 kb/s - 44.1 kHz - Joint Stéréo"])["bitrate"]

            total = len(sources)
            self.msg_queue.put(("progress", (0, total)))
            self.msg_queue.put(("log", f"Fichiers à traiter : {total}"))

            for i, src_str in enumerate(sources, start=1):
                if self.stop_event.is_set():
                    raise RuntimeError("STOP_REQUESTED")

                src = Path(src_str)
                self.msg_queue.put(("status", f"Traitement {i}/{total} : {src.name}"))
                self.msg_queue.put(("progress", (i - 1, total)))

                title = read_mp3_title(src)

                # Nom de fichier final : 3 chiffres + 15 caractères
                if self.tab_options.var_format_title.get():
                    short = sanitize_title_for_filename(title, max_len=15)
                else:
                    short = sanitize_title_for_filename(title, max_len=60)
                out_name = f"{i:03d}_{short}.mp3"

                tmp_out = temp_root / out_name
                ffmpeg_convert_to_mp3(
                    ffmpeg_path=self.ffmpeg_path,  # type: ignore[arg-type]
                    src=src,
                    dst=tmp_out,
                    bitrate=bitrate,
                    stop_event=self.stop_event,
                    proc_holder=self.current_proc_holder,
                    strip_metadata=bool(self.tab_options.var_reset_meta.get()),
                )


                if bool(self.tab_options.var_reset_meta.get()):
                    reset_metadata_keep_title(tmp_out, title)


                # Copie vers clé
                dest_file = dest_inbox / out_name
                shutil.copy2(tmp_out, dest_file)

                self.msg_queue.put(("log", f"✅ {out_name}"))

            self.msg_queue.put(("progress", (total, total)))
            self.msg_queue.put(("status", "Finalisation…"))

            if self.tab_options.var_clean_temp.get():
                try:
                    shutil.rmtree(temp_root)
                    self.msg_queue.put(("log", "🧹 Fichiers temporaires supprimés."))
                except Exception as e:
                    self.msg_queue.put(("log", f"⚠️ Impossible de supprimer les temporaires : {e}"))

            self.msg_queue.put(("log", "=== Préparation : terminée ==="))
            success = True

        except RuntimeError as e:
            if str(e) == "STOP_REQUESTED":
                self.msg_queue.put(("log", "⛔ Préparation interrompue par l'utilisateur."))
            else:
                self.msg_queue.put(("log", f"❌ Erreur : {e}"))
        except Exception as e:
            self.msg_queue.put(("log", f"❌ Erreur inattendue : {e}"))
        finally:
            self.msg_queue.put(("done", success))


def main() -> None:
    app = AutoPodcastApp()
    app.mainloop()


if __name__ == "__main__":
    main()
