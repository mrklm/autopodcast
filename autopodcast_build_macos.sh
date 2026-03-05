#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------
# Build macOS AutoPodcast: .app -> DMG + SHA256
# Sortie: ./releases/
#
# Usage:
#   ./build_macos_release.sh 1.1.1
#   ./build_macos_release.sh 1.1.1 macOS-x86_64
# ----------------------------------------------------

APP_NAME="AutoPodcast"
ENTRYPOINT="autopodcast.py"
ICON_PATH="assets/ar.icns"
REQUIREMENTS="requirements.txt"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version> [arch_tag]"
  exit 1
fi

# Arch tag (auto détecté si non fourni)
ARCH_TAG="${2:-}"
if [[ -z "$ARCH_TAG" ]]; then
  MACHINE="$(uname -m)"
  case "$MACHINE" in
    x86_64) ARCH_TAG="macOS-x86_64" ;;
    arm64)  ARCH_TAG="macOS-arm64" ;;
    *)      ARCH_TAG="macOS-$MACHINE" ;;
  esac
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASES_DIR="${ROOT_DIR}/releases"
DMG_STAGING_DIR="${ROOT_DIR}/dmg"

DMG_NAME="${APP_NAME}-v${VERSION}-${ARCH_TAG}.dmg"
DMG_PATH="${RELEASES_DIR}/${DMG_NAME}"
SHA_PATH="${DMG_PATH}.sha256"

# ---- sanity checks ---------------------------------
cd "$ROOT_DIR"

if [[ ! -f "$ENTRYPOINT" ]]; then
  echo "Erreur: entrée introuvable: ${ENTRYPOINT}"
  exit 1
fi

if [[ ! -f "$REQUIREMENTS" ]]; then
  echo "Erreur: requirements introuvable: ${REQUIREMENTS}"
  exit 1
fi

if [[ ! -f "$ICON_PATH" ]]; then
  echo "Erreur: icône introuvable: ${ICON_PATH}"
  exit 1
fi

# ---- venv ------------------------------------------
if [[ -d ".venv" ]]; then
  # shellcheck disable=SC1091
  source ".venv/bin/activate"
else
  echo "Erreur: venv .venv introuvable. Crée-le puis relance:"
  echo "  python3 -m venv .venv && source .venv/bin/activate && pip install -r requirements.txt"
  exit 1
fi

# ---- clean pre-build --------------------------------
rm -rf build dist "$DMG_STAGING_DIR" *.spec

# ---- deps -------------------------------------------
python -m pip install -U pip
python -m pip install -U pyinstaller
python -m pip install -r "$REQUIREMENTS"

# ---- tools executable bits (best-effort) ------------
if [[ -f "tools/macos-x86_64/ffmpeg" ]]; then
  chmod +x tools/macos-x86_64/ffmpeg tools/macos-x86_64/ffprobe 2>/dev/null || true
fi
if [[ -f "tools/macos-arm64/ffmpeg" ]]; then
  chmod +x tools/macos-arm64/ffmpeg tools/macos-arm64/ffprobe 2>/dev/null || true
fi

# ---- build .app -------------------------------------
pyinstaller \
  --windowed \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  "$ENTRYPOINT"

APP_BUNDLE="dist/${APP_NAME}.app"
if [[ ! -d "$APP_BUNDLE" ]]; then
  echo "Erreur: .app non générée: ${APP_BUNDLE}"
  exit 1
fi

# ---- releases dir -----------------------------------
mkdir -p "$RELEASES_DIR"

# ---- DMG staging ------------------------------------
mkdir -p "$DMG_STAGING_DIR"
cp -R "$APP_BUNDLE" "$DMG_STAGING_DIR/"
ln -s /Applications "$DMG_STAGING_DIR/Applications" || true

# ---- create DMG in releases/ ------------------------
hdiutil create \
  -volname "$APP_NAME" \
  -srcfolder "$DMG_STAGING_DIR" \
  -ov \
  -format UDZO \
  "$DMG_PATH"

# ---- SHA256 -----------------------------------------
shasum -a 256 "$DMG_PATH" > "$SHA_PATH"

echo "OK: ${DMG_PATH}"
echo "OK: ${SHA_PATH}"

# ---- clean post-build (keep only releases artifacts) -
rm -rf "$DMG_STAGING_DIR" build dist *.spec
