#!/bin/bash
# Overnight UK comedy shorts pipeline (runs on debz, survives laptop shutdown).
# Chain: BBC CF re-ASR retries -> club shorts harvest -> long-tail discovery
#        -> roster/index/funnygraph sync. Idempotent; safe to re-run.
set -u
cd "$(dirname "$0")"
mkdir -p /tmp/opencode
LOG=/tmp/opencode/overnight.log
echo "=== overnight start $(date -Is)" >> "$LOG"

PY=python3

# debz IP is bot-flagged: bgutil POT provider (docker, port 4416) + ejs solver
export YTDLP_EXTRA="--remote-components ejs:github"

# 0. roster (Wikipedia + local index)
$PY uk_roster.py >> "$LOG" 2>&1

# 1. BBC ep3/ep4: replace tiny transcripts with CF when rate limit clears
export CF_ASR_NO_FALLBACK=1
for i in 1 2 3 4 5 6 7 8; do
  echo "--- bbc CF attempt $i $(date -Is)" >> "$LOG"
  $PY bbc_fringe_batch.py --force --ids "john meagher,vittorio angelone" \
      >> /tmp/opencode/bbc2.log 2>&1
  if grep -q 'DONE: {"done": 2' /tmp/opencode/bbc2.log; then
    echo "--- bbc CF ok on attempt $i" >> "$LOG"
    break
  fi
  sleep 1500
done
unset CF_ASR_NO_FALLBACK

# 2. club shorts harvest (Angel Comedy + any discovered channels)
$PY shorts_harvest.py --channel @angelcomedyclub --source-group angel-shorts --max 250 \
    >> /tmp/opencode/status_harvest.log 2>&1
if [ -f sources_queue.json ]; then
  while IFS= read -r line; do
    handle=$(echo "$line" | $PY -c "import sys,json;print(json.loads(sys.stdin.read()).get('handle',''))" 2>/dev/null)
    if [ -n "$handle" ]; then
      echo "--- harvest $handle" >> "$LOG"
      $PY shorts_harvest.py --channel "$handle" --source-group web-discovered --max 120 \
          >> /tmp/opencode/status_harvest.log 2>&1
    fi
  done < sources_queue.json
fi

# 3. long-tail: UK comics with no long-form material -> shorts only
$PY uk_shorts_discovery.py --max-names 300 >> "$LOG" 2>&1

# 4. final metadata pass + funnygraph contribution branch
$PY r2_cleanup.py >> "$LOG" 2>&1
$PY r2_index.py >> "$LOG" 2>&1
if [ -d "${FUNNYGRAPH_DIR:-/tmp/funnygraph}" ]; then
  $PY funnygraph_sync.py --push >> "$LOG" 2>&1
fi

echo "=== overnight done $(date -Is)" >> "$LOG"
