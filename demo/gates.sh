#!/usr/bin/env bash
# gates.sh — Mechanical completion gates for Ralph Loop
# Run: cd demo && bash gates.sh
# Exit 0 = all gates pass. Non-zero = at least one gate failed.

set -uo pipefail

PASS=0
FAIL=0
TOTAL=0

run_gate() {
  local name="$1"; shift
  ((TOTAL++))
  local output
  if output=$("$@" 2>&1); then
    printf "  %-20s ok\n" "$name"
    ((PASS++))
  else
    printf "  %-20s FAIL\n" "$name"
    echo "    $output" | head -5
    ((FAIL++))
  fi
}

echo ""

# --- Frontend gates ---
run_gate "FE Install" npm --prefix frontend install --silent
run_gate "FE Lint" npm --prefix frontend run lint
run_gate "FE Typecheck" npm --prefix frontend run typecheck
run_gate "FE Tests" npm --prefix frontend run test -- --run
run_gate "FE Build" npm --prefix frontend run build

# --- Backend (Python) gates ---
run_gate "BE Install" pip install -q -r backend/requirements.txt
run_gate "BE Lint" python -m ruff check backend/
run_gate "BE Tests" python -m pytest backend/tests/ -q

# --- Simulator gates ---
run_gate "Sim Install" npm --prefix simulator install --silent
run_gate "Sim Lint" npm --prefix simulator run lint
run_gate "Sim Typecheck" npm --prefix simulator run typecheck
run_gate "Sim Tests" npm --prefix simulator run test -- --run

# --- Deployment build gate ---
run_gate "App Build" npm --prefix app run build

echo ""
echo "All $TOTAL gate(s): $PASS passed, $FAIL failed"
echo ""
[ "$FAIL" -eq 0 ]
