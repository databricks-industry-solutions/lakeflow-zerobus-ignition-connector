#!/usr/bin/env bash
# gates.sh - Mechanical completion gates for bug-hunt PRD
# Run: bash gates.sh
# Exit 0 = all gates pass. Non-zero = at least one gate failed.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

passed=0
failed=0
total=0

run_gate() {
  local name="$1"; shift
  ((total++))
  if "$@" > /dev/null 2>&1; then
    printf "  %-24s ok\n" "$name"
    ((passed++))
  else
    printf "  %-24s FAIL\n" "$name"
    ((failed++))
  fi
}

echo ""
run_gate "Frontend tests"      bash -c "cd demo/app && npm test -- --run"
run_gate "Frontend typecheck"  bash -c "cd demo/app && npm run typecheck"
run_gate "Backend tests"       bash -c "cd demo/app && uv run --extra test pytest backend/tests/ -m 'not integration' -x -q"
run_gate "Pipeline tests"      bash -c "cd pipelines/sdp && uv run pytest -x -q"
run_gate "Pipeline lint"       bash -c "cd pipelines/sdp && uv run ruff check src/ tests/"
run_gate "Simulator tests"     bash -c "cd demo/simulator && npm test -- --run"
run_gate "Simulator lint"      bash -c "cd demo/simulator && npm run lint"
run_gate "Simulator typecheck" bash -c "cd demo/simulator && npx tsc --noEmit"

echo ""
if [ "$failed" -eq 0 ]; then
  echo "All $total gate(s) passed"
  exit 0
else
  echo "$failed of $total gate(s) failed"
  exit 1
fi
