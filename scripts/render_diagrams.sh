#!/usr/bin/env bash
set -euo pipefail

# Render Mermaid diagrams to PNGs using npx mermaid-cli
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
DIAGRAM_DIR="$ROOT_DIR/docs/diagrams"
OUT_DIR="$DIAGRAM_DIR/images"
mkdir -p "$OUT_DIR"

# Chrome can't use its sandbox on CI runners; mermaid-cli needs these flags.
# Generated at runtime so the repo doesn't carry a root-level puppeteer config.
PUPPETEER_CONFIG="$(mktemp)"
trap 'rm -f "$PUPPETEER_CONFIG"' EXIT
printf '{ "args": ["--no-sandbox", "--disable-setuid-sandbox"] }' > "$PUPPETEER_CONFIG"

echo "Rendering Mermaid diagrams to $OUT_DIR"

# Render ER diagram
npx --yes @mermaid-js/mermaid-cli -i "$DIAGRAM_DIR/ER_diagram.mmd" -o "$OUT_DIR/ER_diagram.png" -p "$PUPPETEER_CONFIG"

# Render class diagram
npx --yes @mermaid-js/mermaid-cli -i "$DIAGRAM_DIR/class_diagram.mmd" -o "$OUT_DIR/class_diagram.png" -p "$PUPPETEER_CONFIG"

echo "Rendering complete."
