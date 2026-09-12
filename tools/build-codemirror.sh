#!/usr/bin/env bash
# Regenera o bundle vendorizado do CodeMirror 6 usado pelo editor de templates.
#
# O artefato (core/static/vendor/codemirror/codemirror6.bundle.js) é commitado,
# então node/npm NÃO são necessários em runtime — só para regerar este bundle
# quando quisermos atualizar a versão do editor.
#
# Uso: tools/build-codemirror.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="$REPO_ROOT/src/omacrm/core/static/vendor/codemirror"
ENTRY="$REPO_ROOT/tools/codemirror-entry.mjs"

# Versões pinadas: mudar aqui (e só aqui) ao atualizar.
CM_CODEMIRROR="6.0.2"
CM_VIEW="6.43.11"
CM_STATE="6.7.4"
CM_LINT="6.9.7"
CM_AUTOCOMPLETE="6.20.3"
CM_COMMANDS="6.11.0"
CM_LANG_XML="6.1.0"
CM_THEME_ONE_DARK="6.1.3"

WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
cd "$WORK"

npm init -y >/dev/null 2>&1
npm i --silent \
  "codemirror@$CM_CODEMIRROR" \
  "@codemirror/view@$CM_VIEW" \
  "@codemirror/state@$CM_STATE" \
  "@codemirror/lint@$CM_LINT" \
  "@codemirror/autocomplete@$CM_AUTOCOMPLETE" \
  "@codemirror/commands@$CM_COMMANDS" \
  "@codemirror/lang-xml@$CM_LANG_XML" \
  "@codemirror/theme-one-dark@$CM_THEME_ONE_DARK"

cp "$ENTRY" entry.mjs
npx --yes esbuild entry.mjs \
  --bundle --minify --format=iife --target=es2020 --legal-comments=none \
  --outfile=codemirror6.bundle.js

mkdir -p "$OUT_DIR"
cp codemirror6.bundle.js "$OUT_DIR/codemirror6.bundle.js"
{
  echo "CodeMirror 6 — MIT License"
  echo
  cat node_modules/codemirror/LICENSE
} > "$OUT_DIR/LICENSE-codemirror.txt"

echo "bundle gerado:"
ls -la "$OUT_DIR/codemirror6.bundle.js"
echo "gzip: $(gzip -c "$OUT_DIR/codemirror6.bundle.js" | wc -c) bytes"
