#!/usr/bin/env bash
# Runs token-bench on a PRIVATE repo, on your own machine only. Nothing it writes goes into this
# (public) repo: the config is gitignored, results and checkouts go to ~/token-bench-private.
#
#   cp repos/private.example.json repos/private.local.json   # fill in the <...> values once
#   ./run-private-local.sh                                  # estimate, confirm, run, report
#
# Env: ARMS, REPS, TOKEN_BENCH_OUT, FRIEDLIVER_SRC (a FriedLiver-Code checkout, for the IDE-side
# index measure), FRIEDLIVER_INDEX_MCP (JSON list of ACP mcpServers for the FriedLiver arms).
# Keys: ANTHROPIC_API_KEY, OPENAI_API_KEY, GEMINI_API_KEY, CURSOR_API_KEY; `agy` must be logged in.
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
CONFIG="${1:-$HERE/repos/private.local.json}"
OUT="${TOKEN_BENCH_OUT:-$HOME/token-bench-private/$(date +%Y%m%d-%H%M%S)}"
ARMS="${ARMS:-claude,friedliver-claude,cursor,codex,friedliver-codex,gemini,friedliver-gemini,antigravity}"
REPS="${REPS:-3}"

[ -f "$CONFIG" ] || { echo "No config. Copy repos/private.example.json to $CONFIG and fill it in."; exit 1; }
if grep -q '<[A-Z]' "$CONFIG"; then echo "$CONFIG still has <PLACEHOLDERS>."; exit 1; fi
git -C "$HERE" check-ignore -q "$CONFIG" 2>/dev/null || case "$CONFIG" in "$HERE"/*) echo "$CONFIG is inside the repo but not gitignored."; exit 1;; esac
unset GITHUB_ACTIONS CI

cd "$HERE"
python3 bench.py estimate --config "$CONFIG" --arms "$ARMS" --reps "$REPS"
read -r -p "List-price estimate above. Run it? [y/N] " ok
[ "$ok" = y ] || exit 0
python3 bench.py run --config "$CONFIG" --out "$OUT" --arms "$ARMS" --reps "$REPS" --skip-missing-keys
if [ -n "${FRIEDLIVER_SRC:-}" ]; then
  for d in "$OUT"/work/*/; do python3 bench.py context-replay --config "$CONFIG" --repo-dir "$d" --out "$OUT"; break; done
fi
python3 report.py "$OUT"
echo "Manual Antigravity IDE rows: fill a CSV like fixtures/manual-antigravity-ide.sample.csv, then"
echo "  python3 bench.py import-manual --config $CONFIG --csv YOUR.csv --out $OUT && python3 report.py $OUT"
echo "The checkout is a git worktree of your repo; remove it with: git worktree remove --force $OUT/work/<name>"
open "$OUT/report.html" 2>/dev/null || true
