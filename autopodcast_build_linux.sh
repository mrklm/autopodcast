#!/usr/bin/env bash
set -euo pipefail

# ------------------------------------------------------------
# Build Linux AutoPodcast
# Sortie : ./releases/
# Génère :
#  - AppImage + SHA256
#  - tar.gz   + SHA256
#
# Usage :
#   ./build_linux.sh              # utilise la version dans autopodcast.py
#   ./build_linux.sh 1.1.3        # force la version
# ------------------------------------------------------------

APP_NAME="AutoPodcast"
ENTRY_PY="autopodcast.py"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASES_DIR="${ROOT_DIR}/releases"
BUILD_DIR="${ROOT_DIR}/build"
DIST_DIR="${ROOT_DIR}/dist"
APPDIR="${ROOT_DIR}/AppDir"
VENV_DIR="${ROOT_DIR}/.venv-build"

# AppImage tooling
APPIMAGETOOL_BIN="${ROOT_DIR}/appimagetool-x86_64.AppImage"
APPIMAGETOOL_URL="https://github.com/AppImage/appimagetool/releases/download/continuous/appimagetool-x86_64.AppImage"

die() { echo "❌ $*" >&2; exit 1; }

require_file() { [[ -f "$1" ]] || die "Fichier manquant : $1"; }
require_dir()  { [[ -d "$1" ]] || die "Dossier manquant : $1"; }

# -----------------------------
# Détection arch + tools/ffmpeg
# -----------------------------
ARCH_RAW="$(uname -m)"
case "$ARCH_RAW" in
  x86_64|amd64) ARCH_TAG="x86_64"; TOOLS_SUBDIR="linux-x86_64" ;;
  aarch64|arm64) ARCH_TAG="arm64"; TOOLS_SUBDIR="linux-arm64" ;;
  *) ARCH_TAG="$ARCH_RAW"; TOOLS_SUBDIR="linux-$ARCH_RAW" ;;
esac

TOOLS_FFMPEG="${ROOT_DIR}/tools/${TOOLS_SUBDIR}/ffmpeg"
TOOLS_FFMPEG_FALLBACK="${ROOT_DIR}/tools/ffmpeg"

# -----------------------------
# Version : argument ou lecture dans autopodcast.py
# -----------------------------
extract_version_from_py() {
  python3 - <<'PY'
import re, pathlib, sys
p = pathlib.Path("autopodcast.py")
s = p.read_text(encoding="utf-8", errors="ignore")
m = re.search(r'^\s*APP_VERSION\s*=\s*"([^"]+)"\s*$', s, re.M)
if not m:
    sys.exit(2)
print(m.group(1))
PY
}

VERSION="${1:-}"
if [[ -z "${VERSION}" ]]; then
  VERSION="$(extract_version_from_py || true)"
  [[ -n "${VERSION}" ]] || die "Impossible de lire APP_VERSION dans ${ENTRY_PY}. Passez une version en argument."
fi

APPIMAGE_OUT="${APP_NAME}-linux-${ARCH_TAG}-v${VERSION}.AppImage"
TAR_DIR="${APP_NAME}-${VERSION}-linux-${ARCH_TAG}"
TAR_OUT="${TAR_DIR}.tar.gz"
SHA_OUT="SHA256SUMS-${APP_NAME}-v${VERSION}.txt"

# -----------------------------
# Pré-check projet
# -----------------------------
cd "${ROOT_DIR}"
require_file "${ROOT_DIR}/${ENTRY_PY}"
require_file "${ROOT_DIR}/tab_options.py"
require_file "${ROOT_DIR}/tab_help.py"
require_dir  "${ROOT_DIR}/assets"
require_file "${ROOT_DIR}/assets/AIDE.md"
require_dir  "${ROOT_DIR}/tools"

# Vérifier ffmpeg (embarqué)
if [[ -f "${TOOLS_FFMPEG}" ]]; then
  chmod +x "${TOOLS_FFMPEG}" || true
elif [[ -f "${TOOLS_FFMPEG_FALLBACK}" ]]; then
  chmod +x "${TOOLS_FFMPEG_FALLBACK}" || true
else
  echo "⚠️ ffmpeg embarqué non trouvé."
  echo "   Attendu : ${TOOLS_FFMPEG} (recommandé) ou ${TOOLS_FFMPEG_FALLBACK}"
  echo "   Le programme peut fonctionner si ffmpeg est dans le PATH, mais l’objectif est l’embarqué."
fi

# -----------------------------
# Nettoyage début
# -----------------------------
rm -rf "${BUILD_DIR}" "${DIST_DIR}" "${APPDIR}" "${RELEASES_DIR}" "${VENV_DIR}"
rm -f "${ROOT_DIR}/"*.spec 2>/dev/null || true
mkdir -p "${RELEASES_DIR}"

# -----------------------------
# venv build
# -----------------------------
python3 -m venv "${VENV_DIR}"
# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"
python -m pip install -U pip wheel setuptools >/dev/null
python -m pip install -U pyinstaller pillow mutagen >/dev/null

# Sanity checks
python -c "from PIL import ImageTk; print('✅ Pillow ImageTk OK')" >/dev/null
python -c "import mutagen; print('✅ Mutagen OK')" >/dev/null

# -----------------------------
# PyInstaller (onedir)
# -----------------------------
pyinstaller \
  --name "${APP_NAME}" \
  --windowed \
  --onedir \
  --clean \
  --noconfirm \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  "${ENTRY_PY}"

# -----------------------------
# AppDir layout
# -----------------------------
mkdir -p "${APPDIR}/usr/bin" \
         "${APPDIR}/usr/share/applications" \
         "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

# Binaire + libs PyInstaller
cp -r "${DIST_DIR}/${APP_NAME}/"* "${APPDIR}/usr/bin/"

# Desktop entry
cat > "${APPDIR}/usr/share/applications/autopodcast.desktop" <<'DESKTOP'
[Desktop Entry]
Name=AutoPodcast
Exec=AutoPodcast
Icon=autopodcast
Type=Application
Categories=Audio;
DESKTOP

# Icône AppImage
mkdir -p "${APPDIR}/usr/share/icons/hicolor/256x256/apps"

cp assets/ar.png \
   "${APPDIR}/usr/share/icons/hicolor/256x256/apps/autopodcast.png"

# Important pour appimagetool
cp "${APPDIR}/usr/share/icons/hicolor/256x256/apps/autopodcast.png" \
   "${APPDIR}/.DirIcon"


# appimagetool attend un .desktop à la racine de l'AppDir
cp "${APPDIR}/usr/share/applications/autopodcast.desktop" "${APPDIR}/autopodcast.desktop"


# Icône : assets/ar.png -> autopodcast.png
if [[ -f "${ROOT_DIR}/assets/ar.png" ]]; then
    cp "${ROOT_DIR}/assets/ar.png" "${APPDIR}/usr/share/icons/hicolor/256x256/apps/autopodcast.png"
    cp "${APPDIR}/usr/share/icons/hicolor/256x256/apps/autopodcast.png" "${APPDIR}/autopodcast.png"

else
  echo "⚠️ Icône non trouvée : assets/ar.png (AppImage ok, mais icône absente)."
fi

# AppRun (lance le binaire)
cat > "${APPDIR}/AppRun" <<'APPRUN'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/AutoPodcast" "$@"
APPRUN
chmod +x "${APPDIR}/AppRun"

# -----------------------------
# appimagetool
# -----------------------------

# Si un vieux appimagetool invalide traîne (ex: "Not Found"), on le supprime
if [[ -f "${APPIMAGETOOL_BIN}" ]]; then
  if ! head -c 4 "${APPIMAGETOOL_BIN}" | grep -q $'\x7fELF'; then
    echo "⚠️ appimagetool existant invalide (pas un ELF) : suppression et re-téléchargement."
    rm -f "${APPIMAGETOOL_BIN}"
    sync
  fi
fi

if [[ ! -f "${APPIMAGETOOL_BIN}" ]]; then
  echo "⬇️ Téléchargement appimagetool…"
  if command -v curl >/dev/null 2>&1; then
    curl -L "${APPIMAGETOOL_URL}" -o "${APPIMAGETOOL_BIN}"
  elif command -v wget >/dev/null 2>&1; then
    wget -O "${APPIMAGETOOL_BIN}" "${APPIMAGETOOL_URL}"
  else
    die "Ni curl ni wget n'est disponible pour télécharger appimagetool."
  fi

  # Vérification : fichier non vide
  if [[ ! -s "${APPIMAGETOOL_BIN}" ]]; then
    die "Téléchargement appimagetool vide."
  fi

  # Vérification : signature ELF (évite 404 HTML)
  if ! head -c 4 "${APPIMAGETOOL_BIN}" | grep -q $'\x7fELF'; then
    echo "Contenu téléchargé invalide :"
    head -n 3 "${APPIMAGETOOL_BIN}" || true
    die "appimagetool invalide (probable 404 ou page HTML)."
  fi

  chmod +x "${APPIMAGETOOL_BIN}"
fi


# -----------------------------
# Build AppImage
# -----------------------------
"${APPIMAGETOOL_BIN}" "${APPDIR}" "${RELEASES_DIR}/${APPIMAGE_OUT}"

# -----------------------------
# Build tar.gz (depuis dist/AutoPodcast)
# -----------------------------
tar -czf "${RELEASES_DIR}/${TAR_OUT}" -C "${DIST_DIR}" "${APP_NAME}"

# -----------------------------
# SHA256 (fichiers .sha256 séparés)
# -----------------------------
(
  cd "${RELEASES_DIR}"
  sha256sum "${APPIMAGE_OUT}" > "${APPIMAGE_OUT}.sha256"
  sha256sum "${TAR_OUT}" > "${TAR_OUT}.sha256"
)

# -----------------------------
# Clean fin (repo clean)
# -----------------------------
deactivate || true
rm -rf "${BUILD_DIR}" "${DIST_DIR}" "${APPDIR}" "${VENV_DIR}"
rm -f "${ROOT_DIR}/"*.spec 2>/dev/null || true

echo "✅ Build terminé"
echo "📦 Sortie : ${RELEASES_DIR}"
ls -lh "${RELEASES_DIR}"
