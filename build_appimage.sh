#!/usr/bin/env bash
# Build Pip-Companion-x86_64.AppImage
# Usage: cd companion/ && bash build_appimage.sh
#
# Requirements:
#   pip install pyinstaller --break-system-packages
#   appimagetool must be on PATH or one directory up (../appimagetool)
#
# Outputs: ../Pip-Companion-x86_64.AppImage

set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
cd "$SCRIPT_DIR"

echo "==> Cleaning previous build..."
rm -rf build dist AppDir

echo "==> Running PyInstaller..."
pyinstaller pip_companion.spec --noconfirm

echo "==> Creating AppDir structure..."
mkdir -p AppDir/usr/bin AppDir/usr/share/applications
mkdir -p AppDir/usr/share/icons/hicolor/256x256/apps
cp -r dist/pip-companion/* AppDir/usr/bin/

echo "==> Writing AppDir metadata..."
cat > AppDir/pip-companion.desktop << 'DESKTOP'
[Desktop Entry]
Name=Pip Companion
Comment=Pixel-art desktop companion powered by Claude
Exec=pip-companion
Icon=pip-companion
Type=Application
Categories=Utility;
Terminal=false
StartupNotify=false
DESKTOP

cat > AppDir/AppRun << 'APPRUN'
#!/bin/bash
SELF="$(readlink -f "$0")"
HERE="${SELF%/*}"
export LD_LIBRARY_PATH="${HERE}/usr/bin/_internal:${LD_LIBRARY_PATH}"
exec "${HERE}/usr/bin/pip-companion" "$@"
APPRUN
chmod +x AppDir/AppRun

echo "==> Generating icon..."
python3 - << 'PYICON'
import sys
from PyQt6.QtWidgets import QApplication
from PyQt6.QtGui import QPixmap, QPainter, QColor
from PyQt6.QtCore import Qt
app = QApplication(sys.argv)
img = QPixmap(256, 256)
img.fill(Qt.GlobalColor.transparent)
p = QPainter(img)
p.setRenderHint(QPainter.RenderHint.Antialiasing)
p.setBrush(QColor(110, 95, 210)); p.setPen(Qt.PenStyle.NoPen)
p.drawEllipse(8, 8, 240, 240)
p.setBrush(QColor(255, 255, 255))
p.drawEllipse(64, 90, 48, 52); p.drawEllipse(144, 90, 48, 52)
p.setBrush(QColor(20, 15, 40))
p.drawEllipse(78, 104, 24, 26); p.drawEllipse(158, 104, 24, 26)
p.setBrush(QColor(55, 35, 90))
p.drawChord(80, 148, 96, 60, 200*16, -200*16)
p.setBrush(QColor(255, 160, 180, 160))
p.drawEllipse(42, 138, 40, 24); p.drawEllipse(174, 138, 40, 24)
p.end()
img.save('AppDir/pip-companion.png')
import shutil
shutil.copy('AppDir/pip-companion.png',
            'AppDir/usr/share/icons/hicolor/256x256/apps/pip-companion.png')
PYICON

echo "==> Building AppImage..."
APPIMAGETOOL="$(command -v appimagetool 2>/dev/null || echo '../appimagetool')"
ARCH=x86_64 "$APPIMAGETOOL" --appimage-extract-and-run AppDir/ ../Pip-Companion-x86_64.AppImage

echo ""
echo "Done! Output: $(ls -lh ../Pip-Companion-x86_64.AppImage)"
echo ""
echo "NOTE: The 'claude' CLI must be installed on the target machine."
echo "      xdotool must also be installed for window-watcher features."
