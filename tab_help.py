# -*- coding: utf-8 -*-
"""
Onglet Aide — Auto-Podcast
Affiche le contenu du fichier AIDE.md (UTF-8).
"""

from pathlib import Path
import tkinter as tk
from tkinter import ttk


class HelpTab(ttk.Frame):
    def __init__(self, master: ttk.Notebook, app) -> None:
        super().__init__(master)
        self.app = app
        self._build_ui()
        self._load_help()

    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        info = ttk.Label(root, text="AIDE.md", font=("TkDefaultFont", 12, "bold"))
        info.pack(anchor="w", pady=(0, 8))

        frame = ttk.Frame(root)
        frame.pack(fill="both", expand=True)

        self.txt = tk.Text(frame, wrap="word")
        self.txt.pack(side="left", fill="both", expand=True)

        sb = ttk.Scrollbar(frame, orient="vertical", command=self.txt.yview)
        sb.pack(side="right", fill="y")
        self.txt.configure(yscrollcommand=sb.set)

        self.txt.configure(state="disabled")

        btn = ttk.Button(root, text="Recharger", command=self._load_help)
        btn.pack(anchor="e", pady=(8, 0))

    def _load_help(self) -> None:
        help_path = Path(__file__).resolve().parent / "assets" / "AIDE.md"
        if help_path.exists():
            try:
                content = help_path.read_text(encoding="utf-8")
            except Exception as e:
                content = f"Impossible de lire AIDE.md : {e}"
        else:
            content = "Fichier AIDE.md introuvable.\n\nPlacez un fichier AIDE.md dans le dossier assets/."

        self.txt.configure(state="normal")
        self.txt.delete("1.0", "end")
        self.txt.insert("1.0", content)
        self.txt.configure(state="disabled")
