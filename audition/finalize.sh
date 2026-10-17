#!/bin/bash
# Finalizer: waits until all harvest tracks settle, then runs
# r2_cleanup -> r2_index -> funnygraph_sync --push.
# Idempotent: exits immediately once index/.finalized exists.
cd /root/patala-audition
export YTDLP_EXTRA="--remote-components ejs:github"
LOG=/tmp/opencode/finalize.log
say() { echo "$(date -Is) $*" >> "$LOG"; }

[ -f index/.finalized ] && exit 0
say "finalizer started; waiting for tracks"

while true; do
  bn=$(grep -c '"__complete__": true' index/big_names_state.json 2>/dev/null)
  queued=$(grep -c . sources_queue.json 2>/dev/null)
  done_=$(grep -c . .sources_done 2>/dev/null)
  if [ "${bn:-0}" -ge 1 ] \
     && ! pgrep -f "uk_shorts_discovery[.]py" >/dev/null \
     && ! pgrep -f "discovery_agent[.]sh" >/dev/null \
     && [ "${done_:-0}" -ge "${queued:-1}" ]; then
    say "tracks settled (big_names=$bn queue=$queued done=$done_); 30min drain buffer"
    sleep 1800
    break
  fi
  sleep 600
done

say "running r2_cleanup"
python3 r2_cleanup.py >> "$LOG" 2>&1
say "running r2_index"
python3 r2_index.py >> "$LOG" 2>&1
say "running funnygraph_sync --push"
python3 funnygraph_sync.py --push >> "$LOG" 2>&1

touch index/.finalized
say "=== finalize done"
