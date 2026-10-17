#!/bin/bash
# Watches sources_queue.json for new @handles and harvests their shorts.
# Idempotent (R2 exists-checks + .sources_done marker).
cd "$(dirname "$(readlink -f "$0")")"
LOG=/tmp/opencode/harvest_web.log
while true; do
  if [ -f sources_queue.json ]; then
    while IFS= read -r line; do
      h=$(printf '%s' "$line" | python3 -c \
        "import sys,json
try: print(json.loads(sys.stdin.read()).get('handle','') or '')
except Exception: print('')" 2>/dev/null)
      case "$h" in
        @*) ;;
        *) continue ;;
      esac
      grep -qF -- "$h" .sources_done 2>/dev/null && continue
      echo "$h" >> .sources_done
      echo "--- harvesting $h $(date -Is)" >> "$LOG"
      python3 shorts_harvest.py --channel "$h" --source-group web-discovered \
        --max 120 >> "$LOG" 2>&1
    done < sources_queue.json
  fi
  sleep 900
done
