#!/usr/bin/env bash
# ScapeBusters smoke check (ATK-05). Usage: bash scripts/smoke.sh   (make smoke)
# Prints PASS/FAIL per check; exits non-zero if any check fails.
set -u
cd "$(dirname "$0")/.."

EDGE="${SB_EDGE_URL:-http://127.0.0.1:8000}"
ORIGIN="${UPSTREAM_ORIGIN:-${SB_ORIGIN_URL:-https://campuscart-c73de.web.app}}"
case "$ORIGIN" in
  *campuscart-c73de.web.app*) BRAND="<title>campuscart</title>"; PAGE="/events" ;;
  *) BRAND="ExampleCorp Nimbus Platform"; PAGE="/docs/" ;;
esac
INTERSTITIAL="Checking your browser"
# A browser-shaped request so Layer 1 escalates (interstitial) instead of throttling curl's UA.
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/140.0.0.0 Safari/537.36"
LOG="$(mktemp)"
trap 'rm -f "$LOG"' EXIT
fails=0

report() {  # report <name> <ok:0|1> <detail>
  if [ "$2" -eq 0 ]; then echo "PASS  $1"; else echo "FAIL  $1 — $3"; fails=$((fails + 1)); fi
}

# 1. backend health (INT-05 Control API)
code=$(curl -s -o "$LOG" -w "%{http_code}" --max-time 10 "$EDGE/api/v1/health")
[ "$code" = "200" ]; report "backend $EDGE/api/v1/health -> 200" $? "HTTP ${code:-000} $(head -c 200 "$LOG")"

# 2. one page through the edge -> 200 with interstitial or origin content
code=$(curl -s -o "$LOG" -w "%{http_code}" --max-time 10 \
  -H "User-Agent: $UA" \
  -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8" \
  -H "Accept-Language: en-US,en;q=0.9" \
  -H "Sec-Fetch-Mode: navigate" -H "Sec-Fetch-Dest: document" -H "Sec-Fetch-Site: none" \
  "$EDGE$PAGE")
ok=1
if [ "$code" = "200" ] && { grep -q "$INTERSTITIAL" "$LOG" || grep -q "$BRAND" "$LOG"; }; then ok=0; fi
report "edge GET $PAGE -> 200 (interstitial or content)" $ok "HTTP ${code:-000}"

# 3. dashboard production build
if [ ! -f dashboard/package.json ]; then
  report "npm --prefix dashboard run build" 1 "dashboard/package.json missing (DSH-01, Harsh)"
elif npm --prefix dashboard run build >"$LOG" 2>&1; then
  report "npm --prefix dashboard run build" 0 ""
else
  report "npm --prefix dashboard run build" 1 "$(tail -n 5 "$LOG" | tr '\n' ' ')"
fi

if [ "$fails" -eq 0 ]; then echo "SMOKE PASS"; else echo "SMOKE FAIL ($fails)"; fi
exit "$fails"
