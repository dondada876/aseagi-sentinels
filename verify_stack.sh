#!/usr/bin/env bash
# PROJ344 — verify & authenticate the sentinel stack BEFORE deploy or merge.
# Runs every engine's dummy test + a full WARDEN integration pass. Exits non-zero on ANY failure,
# so it can gate a deploy, a merge, or a PR check. Read-only, no droplet, no live corpus needed.
#
#   bash infra/verify_stack.sh
#
# Non-destructive: touches only each engine's own gitignored run outputs.
set -uo pipefail
cd "$(dirname "$0")"                       # -> infra/
pass=0; fail=0
step(){ printf '\n=== %s ===\n' "$1"; }
ck(){ if "$@"; then echo "  [PASS]"; pass=$((pass+1)); else echo "  [FAIL] ($*)"; fail=$((fail+1)); fi; }

echo "PROJ344 stack verification — $(date -u +%FT%TZ)"

step "REGISTRY — registry.json true to the filesystem (verify/check-on-update/deprecate)"
ck python3 registry_check.py

step "TETHER — statement re-anchoring (dummy test)"
ck python3 tether/tests/dummy_reanchor_test.py

step "DOWSER — corroboration gap sentinel (dummy test)"
ck python3 dowser/tests/dummy_sentinel_test.py

step "PLUMB — citation-integrity engine (smoke: produces a report)"
ck bash -c 'python3 plumb/link_verify.py >/dev/null && test -f plumb/dashboard_data.json'

step "WARDEN — orchestrator integration (runs all three, writes the board)"
ck bash -c 'python3 warden/orchestrate.py >/dev/null && test -f warden/combined_board.json'

step "WARDEN board sanity (three lanes present, deploy target = .91)"
ck python3 - <<'PY'
import json,sys
b=json.load(open("warden/combined_board.json"))
ok = set(b["lanes"])=={"MEASURE","MATCH","HUNT"} and b.get("deploy_target")=="137.184.1.91"
sys.exit(0 if ok else 1)
PY

echo
echo "----------------------------------------"
echo "VERIFY: $pass passed, $fail failed"
if [ "$fail" -ne 0 ]; then
  echo "STACK NOT AUTHENTICATED — do not deploy or merge."; exit 1
fi
echo "STACK AUTHENTICATED — safe to deploy (.91) / merge."
