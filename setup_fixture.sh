#!/bin/bash
# Builds the benchmark workspace fixture: pinned shallow clone + a deterministic 5 MB file.
set -euo pipefail
DEST="${1:?usage: setup_fixture.sh <dest-dir> [bigrepo-dir]}"
COMMIT=65c1c44800eeac6fb065a54823ee5ae62c79540a   # microsoft/vscode-extension-samples HEAD on 2026-10-17
if [ ! -d "$DEST/.git" ]; then
  mkdir -p "$DEST" && cd "$DEST"
  git init -q && git remote add origin https://github.com/microsoft/vscode-extension-samples.git
  git fetch -q --depth 1 origin "$COMMIT" && git -c advice.detachedHead=false checkout -q FETCH_HEAD
fi
cd "$DEST"
test "$(git rev-parse HEAD)" = "$COMMIT"
# 5 MB plain-text file (.txt so no language server parses it): tracked .ts sources concatenated in sorted order, repeated, cut at exactly 5 MiB.
if [ ! -f big-5mb.txt ]; then
  : > big-5mb.txt
  tmp=$(mktemp)
  trap 'rm -f "$tmp"' EXIT
  git ls-files '*.ts' | LC_ALL=C sort | xargs cat > "$tmp"
  while [ "$(wc -c < big-5mb.txt)" -lt 5242880 ]; do cat "$tmp" >> big-5mb.txt; done
  head -c 5242880 big-5mb.txt > big.tmp && mv big.tmp big-5mb.txt
fi
echo "fixture ok: $(git ls-files | wc -l | tr -d ' ') tracked files, $(du -sh . | cut -f1)"

# Large-repo scenario (optional 2nd arg): microsoft/TypeScript v5.6.3, shallow, ~70k files.
BIGREPO="${2:-}"
if [ -n "$BIGREPO" ] && [ ! -d "$BIGREPO/.git" ]; then
  TS_COMMIT=d48a5cf89a62a62d6c6ed53ffa18f070d9458b85   # tag v5.6.3
  mkdir -p "$BIGREPO" && cd "$BIGREPO"
  git init -q && git remote add origin https://github.com/microsoft/TypeScript.git
  git fetch -q --depth 1 origin "$TS_COMMIT" && git -c advice.detachedHead=false checkout -q FETCH_HEAD
  test "$(git rev-parse HEAD)" = "$TS_COMMIT"
  echo "bigrepo ok: $(git ls-files | wc -l | tr -d ' ') tracked files, $(du -sh . | cut -f1)"
fi
