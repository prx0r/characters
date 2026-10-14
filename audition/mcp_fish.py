"""Fish MCP client (direct JSON-RPC) — token auto-refresh from opencode store.

Usage: python3 mcp_fish.py call <tool> '<json-args>'
       python3 mcp_fish.py upload <local-file>
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

AUTH = Path("/root/.local/share/opencode/mcp-auth.json")
URL = "https://api.fish.audio/mcp"
SID = None


def _tok() -> str:
    d = json.loads(AUTH.read_text())
    fa = d["fish-audio"]
    t = fa["tokens"]
    if time.time() > t.get("expiresAt", 0) - 60:
        body = urllib.parse.urlencode({
            "grant_type": "refresh_token",
            "refresh_token": t["refreshToken"],
            "client_id": fa["clientInfo"]["clientId"]}).encode()
        req = urllib.request.Request("https://api.fish.audio/oauth/token", data=body,
                                     headers={"Content-Type": "application/x-www-form-urlencoded"})
        with urllib.request.urlopen(req, timeout=30) as r:
            nt = json.load(r)
        t["accessToken"] = nt["access_token"]
        t["expiresAt"] = time.time() + nt.get("expires_in", 3600)
        if "refresh_token" in nt:
            t["refreshToken"] = nt["refresh_token"]
        AUTH.write_text(json.dumps(d, indent=2))
    return t["accessToken"]


def _post(body: dict) -> list:
    global SID
    tok = _tok()
    h = {"Authorization": f"Bearer {tok}", "Content-Type": "application/json",
         "Accept": "application/json, text/event-stream"}
    if SID:
        h["mcp-session-id"] = SID
    req = urllib.request.Request(URL, data=json.dumps(body).encode(), headers=h)
    with urllib.request.urlopen(req, timeout=180) as r:
        SID = r.headers.get("mcp-session-id") or SID
        raw = r.read().decode()
    msgs = [json.loads(l[5:].strip()) for l in raw.splitlines() if l.startswith("data:")]
    if not msgs and raw.strip():
        msgs = [json.loads(raw)]
    return msgs


def rpc(method, params=None, mid=1):
    body = {"jsonrpc": "2.0", "id": mid, "method": method}
    if params is not None:
        body["params"] = params
    for m in _post(body):
        if m.get("id") == mid and ("result" in m or "error" in m):
            return m
    return {}


def ensure_session() -> None:
    rpc("initialize", {"protocolVersion": "2025-03-26", "capabilities": {},
                       "clientInfo": {"name": "patala-voice-engine", "version": "1"}}, mid=0)
    _post({"jsonrpc": "2.0", "method": "notifications/initialized"})


def tool(name: str, args: dict, mid: int = 1):
    r = rpc("tools/call", {"name": name, "arguments": args}, mid=mid)
    res = r.get("result") or r.get("error") or r
    if isinstance(res, dict) and res.get("content"):
        t = res["content"][0].get("text", "")
        try:
            return json.loads(t)
        except Exception:
            return t
    return res


def upload(local: str) -> dict:
    p = Path(local)
    name = p.name
    meta = tool("get_upload_url", {"filename": name, "contentType": "application/octet-stream"}, mid=10)
    # meta shapes vary: expect file_url / upload_url / url
    if isinstance(meta, str):
        try:
            meta = json.loads(meta)
        except Exception:
            return {"error": meta[:300]}
    put_url = meta.get("upload_url") or meta.get("url") or meta.get("signed_url")
    file_url = meta.get("file_url") or meta.get("url_for_downloads") or meta.get("download_url")
    if not put_url:
        return {"error": "no upload slot", "meta": meta}
    req = urllib.request.Request(put_url, data=p.read_bytes(), method="PUT",
                                 headers={"Content-Type": "application/octet-stream"})
    with urllib.request.urlopen(req, timeout=300) as r:
        status = r.status
    return {"upload_status": status, "file_url": file_url or meta.get("file_url"), "meta": meta}


if __name__ == "__main__":
    ensure_session()
    if sys.argv[1] == "call":
        out = tool(sys.argv[2], json.loads(sys.argv[3]), mid=99)
        print(json.dumps(out, indent=1))
    elif sys.argv[1] == "upload":
        out = upload(sys.argv[2])
        print(json.dumps(out, indent=1))
