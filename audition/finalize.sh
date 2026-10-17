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
DEADLINE=$(( $(date +%s) + 39600 ))   # hard stop: 11h from start

both_done() {
  python3 - <<'EOF'
import boto3
s3 = boto3.client("s3",
    endpoint_url="https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com",
    aws_access_key_id="36c9d71d3defa6b43f53536bdc6f65f3",
    aws_secret_access_key="c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691",
    region_name="auto")
ok = True
for k in ("_coord/done_local.json", "_coord/done_debz.json"):
    try:
        s3.head_object(Bucket="comedy-specials", Key=k)
    except Exception:
        ok = False
print("1" if ok else "0")
EOF
}

while true; do
  if [ "$(both_done)" = "1" ]; then
    say "both boxes report sweeps done; 30min drain buffer"
    sleep 1800
    break
  fi
  if [ "$(date +%s)" -ge "$DEADLINE" ]; then
    say "deadline reached; proceeding regardless"
    break
  fi
  sleep 600
done

say "running fix_attribution"
python3 fix_attribution.py >> "$LOG" 2>&1
say "running r2_cleanup"
python3 r2_cleanup.py >> "$LOG" 2>&1
say "running discovery_top"
python3 discovery_top.py >> "$LOG" 2>&1
say "running r2_index"
python3 r2_index.py >> "$LOG" 2>&1
say "running funnygraph_sync --push"
python3 funnygraph_sync.py --push >> "$LOG" 2>&1

touch index/.finalized
say "=== finalize done"
