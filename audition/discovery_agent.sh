#!/bin/bash
# Overnight source-discovery: free-model agent web-searches for more UK comedy
# channels and appends them to sources_queue.json. Watcher harvests them.
cd /root/patala-audition
LOG=/tmp/opencode/agent.log
for i in 1 2 3 4 5 6 7 8 9 10 11 12; do
  before=$(wc -l < sources_queue.json 2>/dev/null || echo 0)
  timeout 900 /root/.opencode/bin/opencode run \
    --model opencode/deepseek-v4.1-flash-free "$(cat agent_prompt.md)" \
    >> "$LOG" 2>&1
  after=$(wc -l < sources_queue.json 2>/dev/null || echo 0)
  echo "agent round $i done: lines $before -> $after ($(date -Is))" >> "$LOG"
  python3 - <<'EOF' >> "$LOG" 2>&1
import boto3
s3 = boto3.client("s3",
    endpoint_url="https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com",
    aws_access_key_id="36c9d71d3defa6b43f53536bdc6f65f3",
    aws_secret_access_key="c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691",
    region_name="auto")
s3.put_object(Bucket="comedy-specials", Key="_coord/sources_queue.json",
              Body=open("sources_queue.json", "rb").read(),
              ContentType="application/json")
print("queue uploaded to R2")
EOF
  sleep 1800
done
echo "discovery agent: all rounds done" >> "$LOG"
