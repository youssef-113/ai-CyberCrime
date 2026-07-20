#!/usr/bin/env bash
#
# ACEB Evaluation Pipeline Runner
# ================================
# Full evaluation lifecycle: start server, run tests, stop on failure, report.
#
# Usage:
#   ./scripts/run_eval.sh                    # uses defaults (localhost:8000)
#   ./scripts/run_eval.sh --url https://api.example.com
#   ./scripts/run_eval.sh --continue-on-error  # run all tests despite failures
#   ./scripts/run_eval.sh --register           # force-recreate evaluation user
#

set -euo pipefail

# ── Config ─────────────────────────────────────────────────────────────
BASE_URL="${EVAL_BASE_URL:-http://localhost:8000}"
EMAIL="${EVAL_EMAIL:-evaluation@aceb.test}"
PASSWORD="${EVAL_PASSWORD:-Eval@2026!!}"
OUTPUT_DIR="${EVAL_OUTPUT_DIR:-./outputs}"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"
OUTPUT_FILE="${OUTPUT_DIR}/evaluation_matrix_${TIMESTAMP}.json"
SUMMARY_FILE="${OUTPUT_DIR}/evaluation_summary_${TIMESTAMP}.md"

EXTRA_ARGS=()

# ── Parse CLI ──────────────────────────────────────────────────────────
while [[ $# -gt 0 ]]; do
  case "$1" in
    --url|--base-url)
      BASE_URL="$2"
      shift 2
      ;;
    --email)
      EMAIL="$2"
      shift 2
      ;;
    --password)
      PASSWORD="$2"
      shift 2
      ;;
    --output)
      OUTPUT_FILE="$2"
      shift 2
      ;;
    --continue-on-error)
      EXTRA_ARGS+=("--continue-on-error")
      shift
      ;;
    --register)
      EXTRA_ARGS+=("--register")
      shift
      ;;
    --help|-h)
      echo "ACEB Evaluation Pipeline Runner"
      echo ""
      echo "Usage: $0 [options]"
      echo ""
      echo "Options:"
      echo "  --url|--base-url <URL>       API base URL (default: $BASE_URL)"
      echo "  --email <EMAIL>              Eval user email (default: $EMAIL)"
      echo "  --password <PASSWORD>        Eval user password"
      echo "  --output <FILE>              Output JSON path"
      echo "  --continue-on-error          Run all tests despite failures"
      echo "  --register                   Force re-register user"
      echo "  --help|-h                    Show this help"
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

# ── Ensure output directory ───────────────────────────────────────────
mkdir -p "$OUTPUT_DIR"

# ── Header ─────────────────────────────────────────────────────────────
echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║       ACEB Evaluation Pipeline Runner                       ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "  Base URL:    $BASE_URL"
echo "  Email:       $EMAIL"
echo "  Output:      $OUTPUT_FILE"
echo "  Continue:    ${EXTRA_ARGS[*]:+(enabled)} ${EXTRA_ARGS[*]:-no (stop on fail)}"
echo ""

# ── Health check ─────────────────────────────────────────────────────
echo "── Phase 0: Health Check ──────────────────────────────────────"
echo "  Checking $BASE_URL/health ..."

if command -v curl &>/dev/null; then
    HEALTH=$(curl -s -o /dev/null -w "%{http_code}" --max-time 10 "$BASE_URL/health" 2>/dev/null || echo "000")
else
    HEALTH=$(python3 -c "
import httpx, sys
try:
    r = httpx.get('$BASE_URL/health', timeout=10)
    print(r.status_code)
except Exception:
    print('000')
" 2>/dev/null)
fi

if [ "$HEALTH" = "000" ] || [ "$HEALTH" = "" ]; then
    echo "  ✗ Cannot reach $BASE_URL"
    echo ""
    echo "  Make sure the backend is running:"
    echo "    cd backend && python main.py"
    echo "  Or use Docker:"
    echo "    docker-compose up -d"
    echo ""
    exit 1
fi
echo "  ✓ Server is up (HTTP $HEALTH)"
echo ""

# ── Run evaluation ───────────────────────────────────────────────────
echo "── Phase 1-4: Full Evaluation ──────────────────────────────────"

python3 scripts/evaluation_matrix.py \
    --base-url "$BASE_URL" \
    --email "$EMAIL" \
    --password "$PASSWORD" \
    --output "$OUTPUT_FILE" \
    "${EXTRA_ARGS[@]}"

EXIT_CODE=$?

# ── Generate summary markdown (if JSON exists) ──────────────────────
if [ -f "$OUTPUT_FILE" ] && command -v python3 &>/dev/null; then
    echo ""
    echo "── Phase 5: Generate Summary Report ─────────────────────────"
    python3 -c "
import json, sys
from pathlib import Path

with open('$OUTPUT_FILE', 'r', encoding='utf-8') as f:
    data = json.load(f)

summary = data['summary']
results = data['results']
total = summary['total']
passed = summary['passed']
failed = summary['failed']

# Per-type stats
from collections import defaultdict
by_type = defaultdict(lambda: {'total': 0, 'passed': 0, 'failed': 0})
for r in results:
    tc = r['test_case']
    ct = tc.get('expected_output', {}).get('crime_type', tc['crime_type'])
    by_type[ct]['total'] += 1
    if r['overall_passed']:
        by_type[ct]['passed'] += 1
    else:
        by_type[ct]['failed'] += 1

lines = []
lines.append('# ACEB Evaluation Matrix Report')
lines.append('')
lines.append(f'- **Date:** {summary[\"start_time\"][:10] if summary[\"start_time\"] else \"N/A\"}')
lines.append(f'- **Base URL:** {summary[\"base_url\"]}')
lines.append(f'- **Total Cases:** {total}')
lines.append(f'- **Passed:** {passed}')
lines.append(f'- **Failed:** {failed}')
lines.append(f'- **Pass Rate:** {passed/total*100:.1f}%' if total else 'N/A')
lines.append('')

# Matrix table
lines.append('## Evaluation Matrix')
lines.append('')
lines.append('| Case ID | Type | Difficulty | Classify | RAG | Verify | Status |')
lines.append('|---------|------|------------|----------|-----|--------|--------|')
for r in results:
    tc = r['test_case']
    ct = tc.get('expected_output', {}).get('crime_type', tc['crime_type'])
    diff = tc.get('difficulty', '?')
    cls = r['stages'].get('classification', {}).get('passed', False)
    rag = r['stages'].get('rag_retrieval', {}).get('passed', False)
    ver = r['stages'].get('verification', {}).get('passed', False)
    status = '✅ PASS' if r['overall_passed'] else '❌ FAIL'
    lines.append(f'| {r[\"case_id\"]} | {ct} | {diff} | {\"✅\" if cls else \"❌\"} | {\"✅\" if rag else \"❌\"} | {\"✅\" if ver else \"❌\"} | {status} |')

lines.append('')
lines.append('## Per-Crime-Type Breakdown')
lines.append('')
lines.append('| Crime Type | Total | Passed | Failed | Rate |')
lines.append('|------------|-------|--------|--------|------|')
for ct, counts in sorted(by_type.items()):
    rate = counts['passed'] / counts['total'] * 100 if counts['total'] else 0
    lines.append(f'| {ct} | {counts[\"total\"]} | {counts[\"passed\"]} | {counts[\"failed\"]} | {rate:.0f}% |')

lines.append('')
lines.append('## Failed Cases')
lines.append('')
failed_results = [r for r in results if not r['overall_passed']]
if failed_results:
    for r in failed_results:
        lines.append(f'### {r[\"case_id\"]}')
        for sname, s in r['stages'].items():
            if not s['passed']:
                lines.append(f'- **{sname}**: {s[\"error\"]}')
        lines.append('')
else:
    lines.append('None — all cases passed!')

Path('$SUMMARY_FILE').write_text('\n'.join(lines), encoding='utf-8')
print(f'  ✓ Summary saved to: $SUMMARY_FILE')
"
fi

echo ""
echo "── Done ─────────────────────────────────────────────────────────"
if [ $EXIT_CODE -eq 0 ]; then
    echo "  ✓ All evaluations passed!"
else
    echo "  ✗ Some evaluations failed. Check the report above."
    echo "  Fix the code and re-run to verify fixes."
fi
echo "  Results: $OUTPUT_FILE"
echo ""

exit $EXIT_CODE
