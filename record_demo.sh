#!/usr/bin/env bash
# Record a demo GIF of Pip running.
# Output: marketing/assets/demo.gif

set -e
cd "$(dirname "$0")"

OUTDIR="marketing/assets"
RAW="$OUTDIR/demo_raw.mp4"
GIF="$OUTDIR/demo.gif"
PAL="$OUTDIR/demo_palette.png"

DURATION=22
FPS=12
CAP_W=320
CAP_H=280

echo "==> Launching Pip..."
DISPLAY=:0.0 python3 main.py &
PIP_PID=$!
echo "    PID=$PIP_PID"

echo "==> Waiting 6s for window to fully appear..."
sleep 6

# Find the largest window owned by this PID (skips tiny helper windows)
find_main_window() {
  local best_id="" best_area=0
  for wid in $(xdotool search --pid "$PIP_PID" 2>/dev/null); do
    geom=$(xdotool getwindowgeometry "$wid" 2>/dev/null) || continue
    w=$(echo "$geom" | grep Geometry | awk '{print $2}' | cut -d'x' -f1)
    h=$(echo "$geom" | grep Geometry | awk '{print $2}' | cut -d'x' -f2)
    [ -z "$w" ] || [ -z "$h" ] && continue
    area=$(( w * h ))
    if [ "$area" -gt "$best_area" ]; then
      best_area=$area
      best_id=$wid
    fi
  done
  echo "$best_id"
}

WIN_ID=$(find_main_window)

if [ -n "$WIN_ID" ]; then
  GEOM=$(xdotool getwindowgeometry "$WIN_ID" 2>/dev/null)
  echo "    Window $WIN_ID: $GEOM"
  WIN_X=$(echo "$GEOM" | grep Position | awk '{print $2}' | cut -d',' -f1)
  WIN_Y=$(echo "$GEOM" | grep Position | awk '{print $2}' | cut -d',' -f2)
  WIN_W=$(echo "$GEOM" | grep Geometry | awk '{print $2}' | cut -d'x' -f1)
  WIN_H=$(echo "$GEOM" | grep Geometry | awk '{print $2}' | cut -d'x' -f2)
  echo "    Pip at ${WIN_X},${WIN_Y} size ${WIN_W}x${WIN_H}"
  # Speech bubbles appear above/left — give 200px left clearance, hug right edge of monitor 1
  CX_RIGHT=$(( WIN_X + WIN_W + 20 ))
  [ "$CX_RIGHT" -gt 1919 ] && CX_RIGHT=1919
  CX=$(( CX_RIGHT - CAP_W ))
  [ "$CX" -lt 0 ] && CX=0
  CY=$(( WIN_Y - 150 ))
else
  echo "    No window found — computing default position via Python..."
  POS=$(python3 -c "
from PyQt6.QtWidgets import QApplication
import sys
app = QApplication(sys.argv)
s = app.primaryScreen().geometry()
# Pip defaults: bottom-right with 40/60 margin
print(f'{s.width() - 112 - 40 - 260},{s.height() - 104 - 60 - 210}')
" 2>/dev/null)
  CX=$(echo "$POS" | cut -d',' -f1)
  CY=$(echo "$POS" | cut -d',' -f2)
fi

# Clamp within monitor 1 only (Pip lives on primary)
SCR_W=1919
SCR_H=1080
[ "${CX:-0}" -lt 0 ] && CX=0
[ "${CY:-0}" -lt 0 ] && CY=0
[ "$(( CX + CAP_W ))" -gt "$SCR_W" ] && CX=$(( SCR_W - CAP_W ))
[ "$(( CY + CAP_H ))" -gt "$SCR_H" ] && CY=$(( SCR_H - CAP_H ))

echo "    Capture region: ${CAP_W}x${CAP_H} at ${CX},${CY}"

echo "==> Recording ${DURATION}s at ${FPS}fps..."
ffmpeg -y \
  -f x11grab \
  -framerate "$FPS" \
  -video_size "${CAP_W}x${CAP_H}" \
  -i ":0.0+${CX},${CY}" \
  -t "$DURATION" \
  -c:v libx264 -preset ultrafast -crf 18 \
  "$RAW" 2>/dev/null
echo "    Saved raw: $RAW"

echo "==> Converting to GIF (palette pass 1)..."
ffmpeg -y -i "$RAW" \
  -vf "fps=$FPS,scale=320:-1:flags=lanczos,palettegen=stats_mode=diff" \
  "$PAL" 2>/dev/null

echo "==> Converting to GIF (palette pass 2)..."
ffmpeg -y -i "$RAW" -i "$PAL" \
  -lavfi "fps=$FPS,scale=320:-1:flags=lanczos [x]; [x][1:v] paletteuse=dither=bayer:bayer_scale=5:diff_mode=rectangle" \
  "$GIF" 2>/dev/null

SIZE=$(du -sh "$GIF" | cut -f1)
echo "==> Done! $GIF ($SIZE)"

echo "==> Stopping Pip..."
kill "$PIP_PID" 2>/dev/null || true
wait "$PIP_PID" 2>/dev/null || true

rm -f "$RAW" "$PAL"
echo "==> Cleaned up temp files."
