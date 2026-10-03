#!/usr/bin/env bash
set -euo pipefail

# ----------------------------------------------------
# Build macOS High Sierra AutoPodcast: .app -> DMG + SHA256
# Sortie: ./releases/
#
# Usage:
#   ./autopodcast_build_high_sierra.sh 1.1.12
#
# Cible:
#   - macOS 10.13.6 High Sierra
#   - Intel x86_64
#   - Python 3.10.11 dans .venv-high-sierra
#   - PyInstaller 6.22.3
#   - ffmpeg/ffprobe embarques dans tools/macos-x86_64/
#
# Ce script est separe du build macOS generique pour garder un chemin
# reproductible et stable pour High Sierra. Il ne met volontairement pas a jour
# pip, PyInstaller ou les dependances pendant le build.
# ----------------------------------------------------

APP_NAME="AutoPodcast"
ENTRYPOINT="autopodcast.py"
ICON_PATH="assets/ar.icns"
REQUIREMENTS="requirements.txt"
VENV_DIR=".venv-high-sierra"
TOOLS_DIR="tools/macos-x86_64"
TOOLS_FFMPEG="${TOOLS_DIR}/ffmpeg"
TOOLS_FFPROBE="${TOOLS_DIR}/ffprobe"
ARCH_TAG="macOS-High-Sierra-x86_64"

VERSION="${1:-}"
if [[ -z "$VERSION" ]]; then
  echo "Usage: $0 <version>"
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RELEASES_DIR="${ROOT_DIR}/releases"
DMG_STAGING_DIR="${ROOT_DIR}/dmg"
DMG_NAME="${APP_NAME}-v${VERSION}-${ARCH_TAG}.dmg"
DMG_PATH="${RELEASES_DIR}/${DMG_NAME}"
SHA_PATH="${DMG_PATH}.sha256"

cd "$ROOT_DIR"

die() {
  echo "Erreur: $*" >&2
  exit 1
}

require_file() {
  local path="$1"
  [[ -f "$path" ]] || die "fichier introuvable: $path"
}

require_dir() {
  local path="$1"
  [[ -d "$path" ]] || die "dossier introuvable: $path"
}

echo "=== AutoPodcast build High Sierra ${VERSION} ==="

# ---- sanity checks ---------------------------------
require_file "$ENTRYPOINT"
require_file "$REQUIREMENTS"
require_file "$ICON_PATH"
require_file "$TOOLS_FFMPEG"
require_file "$TOOLS_FFPROBE"
require_dir "$VENV_DIR"

MACHINE="$(uname -m)"
echo "Architecture machine: ${MACHINE}"
[[ "$MACHINE" == "x86_64" ]] || die "ce build High Sierra doit etre lance sur une machine x86_64"

PYTHON_BIN="${VENV_DIR}/bin/python"
require_file "$PYTHON_BIN"

PYTHON_VERSION="$("$PYTHON_BIN" -c 'import platform; print(platform.python_version())')"
echo "Python: ${PYTHON_VERSION}"
[[ "$PYTHON_VERSION" == "3.10.11" ]] || die "Python 3.10.11 est requis pour ce build"

PYINSTALLER_VERSION="$("$PYTHON_BIN" -m PyInstaller --version)"
echo "PyInstaller: ${PYINSTALLER_VERSION}"
[[ "$PYINSTALLER_VERSION" == "6.22.3" ]] || die "PyInstaller 6.22.3 est requis pour ce build"

chmod +x "$TOOLS_FFMPEG" "$TOOLS_FFPROBE"
[[ -x "$TOOLS_FFMPEG" ]] || die "ffmpeg n'est pas executable: $TOOLS_FFMPEG"
[[ -x "$TOOLS_FFPROBE" ]] || die "ffprobe n'est pas executable: $TOOLS_FFPROBE"
echo "ffmpeg embarque: ${TOOLS_FFMPEG}"
echo "ffprobe embarque: ${TOOLS_FFPROBE}"

# ---- PyInstaller High Sierra patch -----------------
# PyInstaller 6.22.3 appelle codesign --remove sur des binaires intermediaires.
# Sous macOS 10.13, cette suppression de signature peut corrompre le binaire et
# declencher ensuite:
#   AssertionError: Executable contains code signature!
#
# Le bootloader compile localement sur High Sierra ne contient pas de signature
# LC_CODE_SIGNATURE au depart. Le contournement valide consiste donc uniquement
# sous macOS 10.13 a ne pas lancer codesign --remove.
#
# On modifie seulement le PyInstaller de .venv-high-sierra, avec sauvegarde, et
# seulement si le bloc attendu est trouve exactement. On ne supprime pas
# l'assertion dans fix_exe_for_code_signing().

OSX_PY="$("$PYTHON_BIN" - <<'PY'
from pathlib import Path
import PyInstaller.utils.osx as osx

print(Path(osx.__file__).resolve())
PY
)"

echo "PyInstaller osx.py: ${OSX_PY}"

"$PYTHON_BIN" - "$OSX_PY" <<'PY'
from pathlib import Path
import shutil
import sys

path = Path(sys.argv[1])
text = path.read_text(encoding="utf-8")

marker = 'Skipping signature removal on macOS High Sierra'
if marker in text:
    print("Patch High Sierra PyInstaller deja present.")
    sys.exit(0)

expected = '''def remove_signature_from_binary(filename):
    """
    Remove the signature from all architecture slices of the given binary file using the codesign utility.
    """
    logger.debug("Removing signature from file %r", filename)
    cmd_args = ['/usr/bin/codesign', '--remove', '--all-architectures', filename]
    p = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
    if p.returncode:
        raise SystemError(f"codesign command ({cmd_args}) failed with error code {p.returncode}!\\noutput: {p.stdout}")
'''

replacement = '''def remove_signature_from_binary(filename):
    """
    Remove the signature from all architecture slices of the given binary file using the codesign utility.
    """
    import platform

    if platform.mac_ver()[0].startswith("10.13"):
        logger.info("Skipping signature removal on macOS High Sierra")
        return

    logger.debug("Removing signature from file %r", filename)
    cmd_args = ['/usr/bin/codesign', '--remove', '--all-architectures', filename]
    p = subprocess.run(cmd_args, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, encoding='utf-8')
    if p.returncode:
        raise SystemError(f"codesign command ({cmd_args}) failed with error code {p.returncode}!\\noutput: {p.stdout}")
'''

if expected not in text:
    raise SystemExit(
        "Bloc PyInstaller attendu introuvable exactement. "
        "Patch refuse pour eviter une modification approximative."
    )

backup = path.with_suffix(path.suffix + ".autopodcast-high-sierra.bak")
if not backup.exists():
    shutil.copy2(path, backup)
    print(f"Sauvegarde creee: {backup}")
else:
    print(f"Sauvegarde deja presente: {backup}")

path.write_text(text.replace(expected, replacement, 1), encoding="utf-8")
print("Patch High Sierra PyInstaller applique.")
PY

# ---- clean pre-build --------------------------------
rm -rf build dist "$DMG_STAGING_DIR" *.spec

# ---- build .app -------------------------------------
export MACOSX_DEPLOYMENT_TARGET=10.13
echo "MACOSX_DEPLOYMENT_TARGET=${MACOSX_DEPLOYMENT_TARGET}"

"$PYTHON_BIN" -m PyInstaller \
  --windowed \
  --target-architecture x86_64 \
  --name "$APP_NAME" \
  --icon "$ICON_PATH" \
  --add-data "assets:assets" \
  --add-data "tools:tools" \
  "$ENTRYPOINT"

APP_BUNDLE="dist/${APP_NAME}.app"
APP_EXECUTABLE="${APP_BUNDLE}/Contents/MacOS/${APP_NAME}"
require_dir "$APP_BUNDLE"
require_file "$APP_EXECUTABLE"

echo "Architecture du binaire principal:"
file "$APP_EXECUTABLE"

# Ne pas supposer le chemin final exact dans le bundle. PyInstaller peut placer
# les donnees dans Contents/Resources, Contents/Frameworks/_internal, etc.
FFMPEG_IN_APP="$(find "$APP_BUNDLE" -type f -name ffmpeg -print | head -n 1 || true)"
FFPROBE_IN_APP="$(find "$APP_BUNDLE" -type f -name ffprobe -print | head -n 1 || true)"

[[ -n "$FFMPEG_IN_APP" ]] || die "ffmpeg introuvable dans ${APP_BUNDLE}"
[[ -n "$FFPROBE_IN_APP" ]] || die "ffprobe introuvable dans ${APP_BUNDLE}"
[[ -x "$FFMPEG_IN_APP" ]] || die "ffmpeg trouve mais non executable dans le bundle: $FFMPEG_IN_APP"
[[ -x "$FFPROBE_IN_APP" ]] || die "ffprobe trouve mais non executable dans le bundle: $FFPROBE_IN_APP"

echo "ffmpeg dans le bundle: ${FFMPEG_IN_APP}"
echo "ffprobe dans le bundle: ${FFPROBE_IN_APP}"

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

# ---- clean post-build (keep release artifacts) -------
rm -rf "$DMG_STAGING_DIR" build dist *.spec

echo "=== Build High Sierra termine ==="
