"""Multimodal Jev (TypeSafe blog 2026-10-14): images in state via
TypeSafe-Danger-Zone-Images header. Works on OpenRouter decisions endpoint.

Use cases for the engine:
- frame-judge: puppet/avatar frames -> typed QC (shot type, mouth open,
  character visible) for the video lane
- reaction lane: live frame -> what's happening (choice) -> character responds
- box type (jev-1.14, preview): bounding box -> crude performer tracking
  (TIC-TALK kinetic proxy without YOLO)

Usage: python3 multimodal_jev.py judge --image frame.png [--question "..."]
"""
from __future__ import annotations
import argparse, base64, json
from pathlib import Path
import urllib.request, urllib.error

HERE = Path(__file__).parent


def _key() -> str:
    for line in (HERE / ".env").read_text().splitlines():
        if line.startswith("OPENROUTER_API_KEY="):
            return line.split("=", 1)[1].strip()
    return ""


def ask(state: dict, questions: dict, model: str = "typesafe/jev-1.13") -> dict:
    body = {"model": model, "state": state, "questions": questions}
    req = urllib.request.Request(
        "https://openrouter.ai/api/alpha/decisions",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {_key()}",
                 "Content-Type": "application/json",
                 "TypeSafe-Danger-Zone-Images": "true"})
    with urllib.request.urlopen(req, timeout=90) as r:
        return json.load(r)


def image_state(image_path: str, context: str = "") -> dict:
    b64 = base64.b64encode(Path(image_path).read_bytes()).decode()
    state = {"frame": f"data:image/png;base64,{b64}"}
    if context:
        state["context"] = context
    return state


def frame_judge(image_path: str, context: str = "a comedy stage frame") -> dict:
    state = image_state(image_path, context)
    qs = {
        "shot": {"type": "choice",
                 "instructions": "What shot type is this frame?",
                 "criteria": {"closeup": "face fills frame", "medium": "waist up",
                              "full": "full body visible", "wide": "stage or audience"}},
        "has_subject": {"type": "noul",
                        "instructions": "Is there a clear performer/subject in frame?",
                        "criteria": {"true": "subject visible", "false": "empty or unclear"}},
    }
    return ask(state, qs)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    j = sub.add_parser("judge")
    j.add_argument("--image", required=True)
    j.add_argument("--context", default="a comedy stage frame")
    args = ap.parse_args()
    res = frame_judge(args.image, args.context)
    print(json.dumps(res.get("answers", res), indent=1)[:400])
