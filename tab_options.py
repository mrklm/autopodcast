# -*- coding: utf-8 -*-
"""
Onglet Options — Auto-Podcast
Contient les options (profil MP3, nettoyage tags, formatage titre, nettoyage destination, temporaires).
"""
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog


# ===== Bibliothèque de thèmes pour le sélecteur =====
THEMES = {
    # ===== Thèmes sombres (sobres / quotidiens) =====
    "[Sombre] Midnight Garage": dict(
        BG="#151515", PANEL="#1F1F1F", FIELD="#2A2A2A",
        FG="#EAEAEA", FIELD_FG="#F0F0F0", ACCENT="#FF9800"
    ),
    "[Sombre] AIR-KLM Night flight": dict(
        BG="#0B1E2D", PANEL="#102A3D", FIELD="#16384F",
        FG="#EAF6FF", FIELD_FG="#FFFFFF", ACCENT="#00A1DE"
    ),
    "[Sombre] Café Serré": dict(
        BG="#1B120C", PANEL="#2A1C14", FIELD="#3A281D",
        FG="#F2E6D8", FIELD_FG="#FFF4E6", ACCENT="#C28E5C"
    ),
    "[Sombre] Matrix Déjà Vu": dict(
        BG="#000A00", PANEL="#001F00", FIELD="#003300",
        FG="#00FF66", FIELD_FG="#66FF99", ACCENT="#00FF00"
    ),
    "[Sombre] Miami Vice 1987": dict(
        BG="#14002E", PANEL="#2B0057", FIELD="#004D4D",
        FG="#FFF0FF", FIELD_FG="#FFFFFF", ACCENT="#00FFD5"
    ),
    "[Sombre] Cyber Licorne": dict(
        BG="#1A0026", PANEL="#2E004F", FIELD="#3D0066",
        FG="#F6E7FF", FIELD_FG="#FFFFFF", ACCENT="#FF2CF7"
    ),

    # ===== Thèmes clairs =====
    "[Clair] AIR-KLM Day flight": dict(
        BG="#EAF6FF", PANEL="#D6EEF9", FIELD="#FFFFFF",
        FG="#0B2A3F", FIELD_FG="#0B2A3F", ACCENT="#00A1DE"
    ),
    "[Clair] Matin Brumeux": dict(
        BG="#E6E7E8", PANEL="#D4D7DB", FIELD="#FFFFFF",
        FG="#1E1F22", FIELD_FG="#1E1F22", ACCENT="#6B7C93"
    ),
    "[Clair] Latte Vanille": dict(
        BG="#FAF6F1", PANEL="#EFE6DC", FIELD="#FFFFFF",
        FG="#3D2E22", FIELD_FG="#3D2E22", ACCENT="#D8B892"
    ),
    "[Clair] Miellerie La Divette": dict(
        BG="#E6B65C", PANEL="#F5E6CC", FIELD="#FFFFFF",
        FG="#50371A", FIELD_FG="#50371A", ACCENT="#F2B705"
    ),

    # ===== Thèmes Pouêt-Pouêt (mais distincts) =====
    "[Pouêt] Chewing-gum Océan": dict(
        BG="#00A6C8", PANEL="#0083A1", FIELD="#00C7B7",
        FG="#082026", FIELD_FG="#082026", ACCENT="#FF4FD8"
    ),
    "[Pouêt] Pamplemousse": dict(
        BG="#FF4A1C", PANEL="#E63B10", FIELD="#FF7A00",
        FG="#1A0B00", FIELD_FG="#1A0B00", ACCENT="#00E5FF"
    ),
    "[Pouêt] Raisin Toxique": dict(
        BG="#7A00FF", PANEL="#5B00C9", FIELD="#B000FF",
        FG="#0F001A", FIELD_FG="#0F001A", ACCENT="#39FF14"
    ),
    "[Pouêt] Citron qui pique": dict(
        BG="#FFF200", PANEL="#E6D800", FIELD="#FFF7A6",
        FG="#1A1A00", FIELD_FG="#1A1A00", ACCENT="#0066FF"
    ),
    "[Pouêt] Barbie Apocalypse": dict(
        BG="#FF1493", PANEL="#004D40", FIELD="#1B5E20",
        FG="#E8FFF8", FIELD_FG="#FFFFFF", ACCENT="#FFEB3B"
    ),
    "[Pouêt] Compagnie Créole": dict(
        BG="#8B3A1A", PANEL="#F2C94C", FIELD="#FFFFFF",
        FG="#5A2E0C", FIELD_FG="#5A2E0C", ACCENT="#8B3A1A"
    ),
}

# Profils MP3 partagés avec l'app
MP3_PROFILES = {
    "MP3 - Éco - CBR 96 kb/s - 44.1 kHz - Joint Stéréo": {"bitrate": "96k"},
    "MP3 - Standard - CBR 128 kb/s - 44.1 kHz - Joint Stéréo": {"bitrate": "128k"},
    "MP3 - Qualité - CBR 192 kb/s - 44.1 kHz - Joint Stéréo": {"bitrate": "192k"},
}


class OptionsTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook, app) -> None:
        super().__init__(master)
        self.app = app

        # Variables (accessibles depuis autopodcast.py)
        desktop = str(Path.home() / "Desktop")
        if not Path(desktop).exists():
            desktop = str(Path.home())

        self.var_temp = tk.StringVar(value=desktop)

        self.var_fs_target = tk.StringVar(value="FAT32")
        self.var_profile = tk.StringVar(value="MP3 - Standard - CBR 128 kb/s - 44.1 kHz - Joint Stéréo")

        self.var_reset_meta = tk.BooleanVar(value=True)
        self.var_format_title = tk.BooleanVar(value=True)
        self.var_clean_temp = tk.BooleanVar(value=True)
        self.var_clean_dest = tk.BooleanVar(value=True)

        self.var_theme = tk.StringVar(value=getattr(self.app, "current_theme_name", ""))
        self._build_ui()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)


        # Thème
        theme_frame = ttk.LabelFrame(root, text="Thème", padding=10)
        theme_frame.pack(fill="x", pady=6)

        ttk.Label(theme_frame, text="Thèmes :").grid(row=0, column=0, sticky="w")
        cmb_theme = ttk.Combobox(
            theme_frame,
            textvariable=self.var_theme,
            values=list(THEMES.keys()),
            state="readonly",
            width=40
        )
        cmb_theme.grid(row=0, column=1, sticky="w", padx=8)
        cmb_theme.bind("<<ComboboxSelected>>", self._on_theme_change)
        theme_frame.columnconfigure(1, weight=1)

        # Temp
        tmp_frame = ttk.LabelFrame(root, text="Répertoire temporaire", padding=10)
        tmp_frame.pack(fill="x", pady=6)

        ttk.Label(tmp_frame, text="Répertoire :").grid(row=0, column=0, sticky="w")
        ttk.Entry(tmp_frame, textvariable=self.var_temp).grid(row=0, column=1, sticky="we", padx=8)
        ttk.Button(tmp_frame, text="Parcourir…", command=self._pick_temp_dir).grid(row=0, column=2)
        tmp_frame.columnconfigure(1, weight=1)

        # Options
        opt_frame = ttk.LabelFrame(root, text="Options", padding=10)
        opt_frame.pack(fill="x", pady=6)

        ttk.Label(opt_frame, text="Type de formatage (indicatif) :").grid(row=0, column=0, sticky="w")
        ttk.Combobox(opt_frame, textvariable=self.var_fs_target, values=["FAT32", "FAT16"], state="readonly", width=12).grid(
            row=0, column=1, sticky="w", padx=8
        )

        ttk.Label(opt_frame, text="Profil MP3 :").grid(row=1, column=0, sticky="w", pady=(10, 0))
        ttk.Combobox(opt_frame, textvariable=self.var_profile, values=list(MP3_PROFILES.keys()), state="readonly", width=52).grid(
            row=1, column=1, sticky="w", padx=8, pady=(10, 0)
        )

        ttk.Checkbutton(
            opt_frame,
            text="Réinitialiser les métadonnées (conserver uniquement le titre)",
            variable=self.var_reset_meta
        ).grid(row=2, column=0, columnspan=3, sticky="w", pady=(12, 0))

        ttk.Checkbutton(
            opt_frame,
            text="Formatage du titre : noms courts (3 chiffres + 15 caractères), suppression des caractères spéciaux",
            variable=self.var_format_title
        ).grid(row=3, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            opt_frame,
            text="Vider le dossier PODCASTS sur la clé USB avant copie (les autres fichiers ne sont pas touchés)",
            variable=self.var_clean_dest
        ).grid(row=4, column=0, columnspan=3, sticky="w", pady=(6, 0))

        ttk.Checkbutton(
            opt_frame,
            text="Effacer les fichiers temporaires à la fin",
            variable=self.var_clean_temp
        ).grid(row=5, column=0, columnspan=3, sticky="w", pady=(6, 0))

    def _pick_temp_dir(self) -> None:
        path = filedialog.askdirectory(title="Sélectionner un répertoire temporaire")
        if path:
            self.var_temp.set(path)


    def _on_theme_change(self, event=None) -> None:
        theme_name = self.var_theme.get().strip()
        if theme_name and hasattr(self.app, "apply_theme"):
            self.app.apply_theme(theme_name)
