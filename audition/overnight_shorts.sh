#!/bin/bash
# "Overnight Shorts" pipeline launcher.
#
# Runs the yt-dlp harvest fleet (club-channel watcher + UK roster long-tail +
# big-names shorts) under runner_agent.py, which rotates the active role
# between the local box and debz through R2 (_coord/rotation.json) whenever
# one side's YouTube session gets rate-limited.
#
# Usage (on either box):
#   setsid nohup bash overnight_shorts.sh >/tmp/opencode/overnight_shorts.log 2>&1 </dev/null & disown
cd "$(dirname "$(readlink -f "$0")")"

if [ -d /root/patala-audition ]; then
  export WORKER_NAME=debz
  export YTDLP_EXTRA="--remote-components ejs:github --sleep-requests 1 --min-sleep-interval 3 --max-sleep-interval 8"
else
  export WORKER_NAME=local
  export YTDLP_EXTRA="--sleep-requests 1 --min-sleep-interval 3 --max-sleep-interval 8"
fi

exec python3 runner_agent.py
