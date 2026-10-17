#!/bin/bash
# One-shot recovery: after the YouTube session cooldown, verify player access,
# then restart all harvesters + watchdog with throttled yt-dlp flags.
cd /root/patala-audition
export YTDLP_EXTRA="--remote-components ejs:github --sleep-requests 1 --min-sleep-interval 3 --max-sleep-interval 8"
L=/tmp/opencode/resume.log
say() { echo "$(date -Is) $*" >> "$L"; }

say "resume scheduled; initial 45min cooldown"
sleep 2700

for i in 1 2 3 4 5 6 7 8; do
  if timeout 90 yt-dlp --list-subs --cookies .env.cookies \
      $YTDLP_EXTRA "https://www.youtube.com/watch?v=nAuFGPa0qEE" \
      >/dev/null 2>&1; then
    say "youtube player access OK (attempt $i)"
    break
  fi
  say "still rate-limited (attempt $i); waiting 1800s"
  sleep 1800
done

start() {
  setsid nohup bash -c "$1" > "$2" 2>&1 < /dev/null &
  disown
}

start "cd /root/patala-audition && exec bash sources_watcher.sh" /tmp/opencode/watcher_resume.log
start "cd /root/patala-audition && exec python3 uk_shorts_discovery.py --max-names 1200" /tmp/opencode/longtail5.log
start "cd /root/patala-audition && exec python3 big_names_harvest.py" /tmp/opencode/big_names_run4.log
sleep 10
start "cd /root/patala-audition && exec bash watchdog.sh" /tmp/opencode/watchdog_launcher.log
say "harvesters + watchdog resumed"
