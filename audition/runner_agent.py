#!/usr/bin/env python3
"""Rotate the yt-dlp harvest fleet between local box and debz.

One box is ACTIVE (runs watcher + long-tail + big-names); the other is STANDBY.
Health probe every 10 min; two consecutive failures => hand off to the peer.
Standby reclaims when: no active owner, owner heartbeat is stale, or the owner
has been flagged limited for >30 min. Coordination object:
s3://comedy-specials/_coord/rotation.json

Run with: WORKER_NAME=debz|local python3 runner_agent.py
"""
from __future__ import annotations
import datetime, json, os, subprocess, time
from pathlib import Path

import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from uk_shorts_discovery import R2_ENDPOINT, R2_KEY, R2_SECRET, R2_BUCKET  # noqa: E402

import boto3  # noqa: E402

HERE = Path(__file__).parent
WORKER = os.environ.get("WORKER_NAME") or "local"
PEER = "local" if WORKER == "debz" else "debz"
SKIP = {s.strip() for s in os.environ.get("SKIP_TASKS", "").split(",") if s.strip()}
KEY = "_coord/rotation.json"
PROBE_VID = "nAuFGPa0qEE"
LOG = Path("/tmp/opencode/rotation.log")
STALE_S = 1800

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")

TASKS = [
    {"name": "watcher", "pat": "sources_watcher[.]sh",
     "cmd": "exec bash sources_watcher.sh",
     "done": None},
    {"name": "longtail", "pat": "uk_shorts_discovery[.]py",
     "cmd": "exec python3 uk_shorts_discovery.py --max-names 1200",
     "done": HERE / "index" / ".shorts_done"},
    {"name": "bignames", "pat": "big_names_harvest[.]py",
     "cmd": "exec python3 big_names_harvest.py",
     "done": None},  # checked via state file below
]


def now() -> str:
    return datetime.datetime.utcnow().isoformat(timespec="seconds") + "Z"


def age_s(ts: str | None) -> float:
    if not ts:
        return 1e9
    try:
        t = datetime.datetime.fromisoformat(ts.replace("Z", ""))
        return (datetime.datetime.utcnow() - t).total_seconds()
    except Exception:
        return 1e9


def say(msg: str):
    line = f"{now()} [{WORKER}] {msg}"
    print(line, flush=True)
    try:
        with LOG.open("a") as f:
            f.write(line + "\n")
    except Exception:
        pass


def read_rot() -> dict:
    try:
        b = s3.get_object(Bucket=R2_BUCKET, Key=KEY)["Body"].read()
        return json.loads(b)
    except Exception:
        return {}


def write_rot(d: dict):
    try:
        s3.put_object(Bucket=R2_BUCKET, Key=KEY,
                      Body=json.dumps(d).encode(),
                      ContentType="application/json")
    except Exception as e:
        say(f"rotation write failed: {str(e)[:80]}")


def running(pat: str) -> bool:
    return subprocess.run(["pgrep", "-f", pat],
                          capture_output=True).returncode == 0


def task_done(t: dict) -> bool:
    if t["name"] in SKIP:
        return True
    if t["name"] == "bignames":
        try:
            s = json.loads((HERE / "index" / "big_names_state.json").read_text())
            return bool(s.get("__complete__"))
        except Exception:
            return False
    return t["done"] is not None and Path(t["done"]).exists()


def all_sweeps_done() -> bool:
    return all(task_done(t) for t in TASKS if t["name"] != "watcher")


def write_done_marker():
    try:
        s3.put_object(Bucket=R2_BUCKET, Key=f"_coord/done_{WORKER}.json",
                      Body=json.dumps({"worker": WORKER, "ts": now()}).encode(),
                      ContentType="application/json")
        say("wrote done marker to R2")
    except Exception as e:
        say(f"done marker write failed: {str(e)[:80]}")


def ensure_workers():
    for t in TASKS:
        if t["name"] in SKIP or task_done(t):
            continue
        if not running(t["pat"]):
            say(f"starting {t['name']}")
            logf = open(f"/tmp/opencode/{t['name']}.log", "ab")
            subprocess.Popen(
                ["bash", "-c", f"cd {HERE} && {t['cmd']}"],
                stdout=logf, stderr=logf, stdin=subprocess.DEVNULL,
                start_new_session=True)


def stop_workers():
    for t in TASKS:
        if t["name"] in SKIP:
            continue
        if running(t["pat"]):
            say(f"stopping {t['name']}")
            subprocess.run(["pkill", "-f", t["pat"]], capture_output=True)


def probe() -> bool:
    yt = os.environ.get("YTDLP_EXTRA", "")
    cookies = str(HERE / ".env.cookies")
    if not Path(cookies).exists():
        cookies = "/home/box/Downloads/cookies.txt"
    cmd = ["yt-dlp", "--list-subs", "--cookies", cookies] + yt.split() + \
        [f"https://www.youtube.com/watch?v={PROBE_VID}"]
    try:
        r = subprocess.run(cmd, capture_output=True, timeout=120)
        if r.returncode == 0:
            return True
        err = (r.stderr or b"").decode(errors="ignore")
        if "rate-limited" in err or "not available" in err or \
           "Sign in" in err or "unavailable" in err:
            return False
        # other errors (e.g. geo) shouldn't count as rate limiting
        return True
    except subprocess.TimeoutExpired:
        return False


def main():
    fails, last_beat, last_probe = 0, 0.0, 0.0
    marked = False
    say("runner starting")
    while True:
        if not marked and all_sweeps_done():
            write_done_marker()
            marked = True
        rot = read_rot()
        active = rot.get("active")
        owner_stale = age_s(rot.get("beat")) > STALE_S
        limited_by = rot.get("limited")
        limited_old = age_s(rot.get("limited_at")) > STALE_S

        if active == WORKER:
            ensure_workers()
            if time.time() - last_beat > 90:
                write_rot({"active": WORKER, "beat": now(),
                           "limited": "", "limited_at": ""})
                last_beat = time.time()
            if time.time() - last_probe > 600:
                last_probe = time.time()
                ok = probe()
                fails = 0 if ok else fails + 1
                say(f"probe: {'ok' if ok else f'FAIL {fails}'}")
                if fails >= 2:
                    stop_workers()
                    write_rot({"active": PEER, "beat": now(),
                               "limited": WORKER, "limited_at": now()})
                    say(f"rate-limited -> handing off to {PEER}")
                    fails = 0
                    last_beat = time.time()
        else:
            stop_workers()
            if time.time() - last_probe > 600:
                last_probe = time.time()
                ok = probe()
                say(f"standby probe: {'ok' if ok else 'limited'}")
                if ok and (active is None or owner_stale or
                           (limited_by == PEER and limited_old)):
                    write_rot({"active": WORKER, "beat": now(),
                               "limited": "", "limited_at": ""})
                    say(f"claiming active role (was {active})")
                    last_beat = time.time()
        time.sleep(30)


if __name__ == "__main__":
    main()
