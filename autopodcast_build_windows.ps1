# build_windows.ps1
Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

# ----------------------------------------------------
# Build Windows AutoPodcast (PyInstaller -> onedir + ZIP + SHA256)
# Sortie dans ./releases/
#
# Usage:
#   powershell -ExecutionPolicy Bypass -File .\build_windows.ps1
# ----------------------------------------------------

$APP_NAME   = "AutoPodcast"
$ENTRY_PY   = "autopodcast.py"
$ROOT_DIR   = (Get-Location).Path
$DIST_DIR   = Join-Path $ROOT_DIR "dist"
$BUILD_DIR  = Join-Path $ROOT_DIR "build"
$RELEASES   = Join-Path $ROOT_DIR "releases"
$VENV_DIR   = Join-Path $ROOT_DIR ".venv-build"

function Die($msg) { Write-Host "❌ $msg" -ForegroundColor Red; exit 1 }

if (!(Test-Path $ENTRY_PY)) { Die "Entrée introuvable: $ENTRY_PY" }

# Version depuis APP_VERSION
$pyText = Get-Content -Raw -Encoding UTF8 $ENTRY_PY
$m = [regex]::Match($pyText, 'APP_VERSION\s*=\s*"([^"]+)"')
if (!$m.Success) { Die "APP_VERSION introuvable dans $ENTRY_PY" }
$VERSION = $m.Groups[1].Value

# Arch Windows
$ARCH = if ([Environment]::Is64BitOperatingSystem) { "x86_64" } else { "x86" }

# Noms de sortie
$OUT_DIRNAME = "$APP_NAME-windows-$ARCH-v$VERSION"
$ZIP_OUT     = Join-Path $RELEASES ($OUT_DIRNAME + ".zip")
$SHA_OUT     = Join-Path $RELEASES ("SHA256SUMS-$APP_NAME-v$VERSION.txt")

Write-Host "=== Build $APP_NAME v$VERSION (Windows $ARCH) ==="

# Clean
if (Test-Path $BUILD_DIR) { Remove-Item -Recurse -Force $BUILD_DIR }
if (Test-Path $DIST_DIR)  { Remove-Item -Recurse -Force $DIST_DIR }
if (Test-Path $RELEASES)  { Remove-Item -Recurse -Force $RELEASES }
New-Item -ItemType Directory -Force -Path $RELEASES | Out-Null

# Venv build
if (Test-Path $VENV_DIR) { Remove-Item -Recurse -Force $VENV_DIR }
python -m venv $VENV_DIR
$PY = Join-Path $VENV_DIR "Scripts\python.exe"
$PIP = Join-Path $VENV_DIR "Scripts\pip.exe"

& $PY -m pip install --upgrade pip wheel setuptools | Out-Host

# Dépendances (adapte si tu as requirements.txt/build-requirements.txt)
if (Test-Path "requirements.txt") {
  & $PIP install -r "requirements.txt" | Out-Host
}
if (Test-Path "build-requirements.txt") {
  & $PIP install -r "build-requirements.txt" | Out-Host
} else {
  # Fallback minimal si tu n'as pas de build-requirements.txt
  & $PIP install pyinstaller pillow mutagen | Out-Host
}

# Sanity check ImageTk (évite de build un binaire cassé)
& $PY -c "from PIL import ImageTk; print('ImageTk OK')" | Out-Host

# PyInstaller
$SPEC = Join-Path $ROOT_DIR "$APP_NAME.spec"
if (Test-Path $SPEC) { Remove-Item -Force $SPEC }

# IMPORTANT: Windows --add-data utilise ; (pas :)
$addAssets = "assets;assets"
$addTools  = "tools;tools"

& $PY -m PyInstaller `
  --name $APP_NAME `
  --windowed `
  --onedir `
  --clean `
  --noconfirm `
  --icon "assets\ar.ico" `
  --add-data $addAssets `
  --add-data $addTools `
  --hidden-import "PIL._imagingtk" `
  --hidden-import "PIL._tkinter_finder" `
  --hidden-import "PIL.ImageTk" `
  $ENTRY_PY | Out-Host

# Préparer dossier release
$builtDir = Join-Path $DIST_DIR $APP_NAME
if (!(Test-Path $builtDir)) { Die "Sortie PyInstaller introuvable: $builtDir" }

$stageDir = Join-Path $RELEASES $OUT_DIRNAME
New-Item -ItemType Directory -Force -Path $stageDir | Out-Null

Copy-Item -Recurse -Force (Join-Path $builtDir "*") $stageDir

# ZIP
if (Test-Path $ZIP_OUT) { Remove-Item -Force $ZIP_OUT }
Compress-Archive -Path (Join-Path $stageDir "*") -DestinationPath $ZIP_OUT

# SHA256
$sha = (Get-FileHash -Algorithm SHA256 $ZIP_OUT).Hash.ToLower()
Set-Content -Encoding ASCII -Path $SHA_OUT -Value "$sha  $([IO.Path]::GetFileName($ZIP_OUT))"

Write-Host "✅ ZIP  : $ZIP_OUT"
Write-Host "✅ SHA  : $SHA_OUT"

# Clean build artifacts (optionnel)
if (Test-Path $BUILD_DIR) { Remove-Item -Recurse -Force $BUILD_DIR }
if (Test-Path $DIST_DIR)  { Remove-Item -Recurse -Force $DIST_DIR }
if (Test-Path $SPEC)      { Remove-Item -Force $SPEC }
if (Test-Path $VENV_DIR)  { Remove-Item -Recurse -Force $VENV_DIR }

Write-Host "=== OK ==="
