#!/usr/bin/env bash
# Render SPEC.md -> SPEC.pdf using pandoc (pypandoc_binary wheel) + MathJax SVG + headless Chrome. Free tools only.
set -euo pipefail
cd "$(dirname "$0")"
PANDOC=${PANDOC:-pandoc}
cat > /tmp/spec_pdf.css <<'CSS'
body{font-family:"DejaVu Sans",sans-serif;font-size:10.5pt;margin:0 1.2cm;line-height:1.4}
table{border-collapse:collapse;font-size:9pt;margin:8px 0}th,td{border:1px solid #999;padding:3px 5px;vertical-align:top}
th{background:#eee}code,pre{font-size:8.5pt}pre{background:#f6f6f6;padding:6px;white-space:pre-wrap}
h1{font-size:15pt;border-bottom:1px solid #444;margin-top:18px}h2{font-size:12.5pt}
CSS
"$PANDOC" SPEC.md -s --mathjax=https://cdn.jsdelivr.net/npm/mathjax@3/es5/tex-svg-full.js --toc --toc-depth=2 \
  -c file:///tmp/spec_pdf.css -o /tmp/SPEC.html
google-chrome --headless=new --no-sandbox --disable-gpu --no-pdf-header-footer --virtual-time-budget=30000 \
  --print-to-pdf="$PWD/SPEC.pdf" file:///tmp/SPEC.html
