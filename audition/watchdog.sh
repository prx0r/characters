#!/bin/bash
# Watchdog: keeps the debz overnight pipeline alive until it finishes.
# Restarts any dead component; logs every action. Safe: all components are
# idempotent (exists-checks + markers), so restarts never double-write.
cd /root/patala-audition
export YTDLP_EXTRA="--remote-components ejs:github --sleep-requests 1 --min-sleep-interval 3 --max-sleep-interval 8"
LOG=/tmp/opencode/watchdog.log
say() { echo "$(date -Is) $*" >> "$LOG"; }

ensure() {
  local name="$1" pat="$2" cmd="$3"
  if ! pgrep -f "$pat" >/dev/null 2>&1; then
    say "restarting $name"
    setsid nohup bash -c "$cmd" > "/tmp/opencode/${name}_restart.log" 2>&1 < /dev/null &
    disown
  fi
}

while true; do
  ensure status_server "status_server.py --port 3781" \
      "cd /root/patala-audition && exec python3 status_server.py --port 3781"
  ensure runner "runner_agent[.]py" \
      "cd /root/patala-audition && exec bash overnight_shorts.sh"

  if ! grep -q "all rounds done" /tmp/opencode/agent.log 2>/dev/null; then
    ensure agent "discovery_agent.sh" \
        "cd /root/patala-audition && exec bash discovery_agent.sh"
  fi
  if [ ! -f /root/patala-audition/index/.finalized ]; then
    ensure finalize "finalize.sh" \
        "cd /root/patala-audition && exec bash finalize.sh"
  fi

  if ! docker inspect -f '{{.State.Running}}' bgutil-provider 2>/dev/null \
      | grep -q true; then
    say "starting bgutil-provider container"
    docker start bgutil-provider >> "$LOG" 2>&1
  fi

  sleep 300
done
