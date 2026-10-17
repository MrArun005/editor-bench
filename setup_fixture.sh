#!/bin/bash
# Builds the benchmark workspace fixture: pinned shallow clone + a deterministic 5 MB file.
set -euo pipefail
DEST="${1:?usage: setup_fixture.sh <dest-dir>}"
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
  git ls-files '*.ts' | LC_ALL=C sort | xargs cat > /tmp/editor-bench-src.$$
  while [ "$(wc -c < big-5mb.txt)" -lt 5242880 ]; do cat /tmp/editor-bench-src.$$ >> big-5mb.txt; done
  head -c 5242880 big-5mb.txt > big.tmp && mv big.tmp big-5mb.txt && rm -f /tmp/editor-bench-src.$$
fi
echo "fixture ok: $(git ls-files | wc -l | tr -d ' ') tracked files, $(du -sh . | cut -f1)"
