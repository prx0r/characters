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
  sleep 1800
done
echo "discovery agent: all rounds done" >> "$LOG"
