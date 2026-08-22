#!/usr/bin/env bash
# สร้างไฟล์ standalone จากไฟล์ต้นฉบับ Artifact (ห่อ skeleton + โหลด Mermaid จาก CDN)
# ใช้: bash docs/build-standalone.sh
set -euo pipefail
cd "$(dirname "$0")"
SRC=room-booking-srs.html
OUT=room-booking-srs.standalone.html
TITLE=$(grep -o '<title>[^<]*</title>' "$SRC" | head -1)
{
  printf '<!doctype html>\n<html lang="th">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n%s\n' "$TITLE"
  sed '1d' "$SRC" | sed -n '1,/<\/style>/p'
  printf '</head>\n<body>\n'
  sed '1d' "$SRC" | sed '1,/<\/style>/d'
  cat <<'MERMAID'
<script type="module">
  import mermaid from "https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.esm.min.mjs";
  const dark = matchMedia("(prefers-color-scheme: dark)").matches;
  mermaid.initialize({ startOnLoad: true, theme: dark ? "dark" : "neutral", securityLevel: "strict" });
</script>
</body>
</html>
MERMAID
} > "$OUT"
echo "wrote $OUT ($(wc -c < "$OUT") bytes)"
