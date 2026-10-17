"""Minimal status page for the overnight pipeline. Serves on 0.0.0.0:3781.

Usage: python3 status_server.py [--port 3781]
"""
from __future__ import annotations
import argparse, html, json, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

HERE = Path(__file__).parent
LOGS = [("/tmp/opencode/overnight.log", 40),
        ("/tmp/opencode/bbc2.log", 12),
        ("/tmp/opencode/status_harvest.log", 12)]
STATE = HERE / "index" / "shorts_discovery_state.json"
SUMMARY = HERE / "index" / "uk_comedy_summary.json"


def tail(path: str, n: int) -> str:
    p = Path(path)
    if not p.exists():
        return "(no log yet)"
    lines = p.read_text(errors="replace").splitlines()[-n:]
    return "\n".join(lines)


def build() -> str:
    parts = [f"<h2>Overnight pipeline status</h2><p>page built: {time.strftime('%F %T')}</p>"]
    if SUMMARY.exists():
        s = json.loads(SUMMARY.read_text())
        parts.append(f"<p><b>R2 index:</b> {json.dumps(s)[:400]}</p>")
    if STATE.exists():
        st = json.loads(STATE.read_text())
        by = {}
        harvested = 0
        for v in st.values():
            by[v["status"]] = by.get(v["status"], 0) + 1
            harvested += v.get("harvested", 0)
        parts.append(f"<p><b>discovery:</b> {len(st)} names checked, "
                     f"clips harvested {harvested}, {json.dumps(by)}</p>")
    for path, n in LOGS:
        parts.append(f"<h3>{path} (last {n})</h3><pre>{html.escape(tail(path, n))}</pre>")
    return ("<!doctype html><html><head><meta charset=utf-8>"
            "<meta http-equiv=refresh content=120>"
            "<style>body{font-family:monospace;background:#111;color:#ddd;padding:1em}"
            "pre{background:#222;padding:.6em;overflow-x:auto}</style></head>"
            "<body>" + "\n".join(parts) + "</body></html>")


class H(BaseHTTPRequestHandler):
    def do_GET(self):
        body = build().encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=3781)
    a = ap.parse_args()
    print(f"status on http://0.0.0.0:{a.port}/", flush=True)
    ThreadingHTTPServer(("0.0.0.0", a.port), H).serve_forever()
