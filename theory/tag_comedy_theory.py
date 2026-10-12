"""Theory + emotion tagging via qwen-flash-character (works on this key).

Visual/omni models need Free Quota Only enabled in console.
Meanwhile: archive transcripts × MediaPipe numeric windows →
  comedy-theory tags + emotion read, aligned to body dials.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from openai import OpenAI

HERE = Path(__file__).parent
AUDITION = HERE.parent / "audition"
KT_DATA = Path("/home/box/repos/kill-tony-archive/data")


def _client() -> OpenAI:
    key = base = ""
    for line in (AUDITION / ".env").read_text().splitlines():
        if line.startswith("DASHSCOPE_API_KEY="):
            key = line.split("=", 1)[1].strip().strip("'\"")
        elif line.startswith("DASHSCOPE_BASE_URL="):
            base = line.split("=", 1)[1].strip().strip("'\"")
    return OpenAI(api_key=key, base_url=base or "https://dashscope-intl.aliyuncs.com/compatible-mode/v1")


def tag_transcript(model: str, transcript: str, meta: dict) -> dict:
    system = (
        "You are a comedy theory analyst for Kill Tony sets. "
        "You output STRICT JSON only. Never invent biographical facts about the comedian. "
        "Stage persona only."
    )
    user = f"""Comedian stage persona context (hypothesis only):
{json.dumps(meta.get('persona', {}), indent=2)[:1500]}

Transcript of one-minute set (segment boundaries by blank line / beat):
---
{transcript[:6000]}
---

Return STRICT JSON with this schema:
{{
  "overall": {{
    "archetype": "bisociation|superiority|relief|incongruity|benign_violation",
    "primary_operators": ["double_interpret","literalize","repeat_variation","garden_path","status_reversal","self_deprecation","other"],
    "energy_arc": "flat_build|spike_hold|wave|cold_then_hot|manic",
    "dominant_emotion": "neutral|angry|defiant|gleeful|manic|deadpan|embarrassed|mock_indignant",
    "dominant_emotion_intensity": 0.0
  }},
  "beats": [
    {{
      "text_excerpt": "first ~12 words",
      "beat_type": "setup|escalation|punchline|tag|callback|closer",
      "operators": ["..."],
      "emotion": "neutral|angry|defiant|gleeful|manic|deadpan|embarrassed|mock_indignant",
      "emotion_intensity": 0.0,
      "anger_flavor": null | "hot|cold|mock|contained",
      "anger_target": null | str,
      "status_move": "down|up|flat|reversal",
      "body_hypothesis": "what body language would serve this beat (one line)",
      "vocal_hypothesis": "what vocal delivery would serve this beat (one line)"
    }}
  ],
  "anger_manual": {{
    "present": bool,
    "if_present": {{
      "type": "hot_yelling|cold_flat|mock_indignant|controlled_seethe|fake_rage_for_joke",
      "body_signature_hypotheses": [str],
      "vocal_signature_hypotheses": [str],
      "contrast_note": str
    }}
  }},
  "notes": str
}}
Keep beats to the actual set (~6-12). Be specific and falsifiable."""
    c = _client()
    r = c.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        temperature=0.3,
        extra_body={"response_format": {"type": "json_object"}},
    )
    raw = r.choices[0].message.content or "{}"
    try:
        return json.loads(raw)
    except Exception:
        a, b = raw.find("{"), raw.rfind("}")
        return json.loads(raw[a:b + 1]) if a >= 0 and b > a else {"_raw": raw[:2000]}


def load_set_transcript(ep: int, set_number: int) -> dict | None:
    f = next(KT_DATA.glob(f"reprocess_ep{ep}_pass2.json"), None)
    if not f:
        return None
    d = json.loads(f.read_text())
    for s in d.get("sets", []):
        if s.get("set_number") == set_number and "ari" in (s.get("comedian_name") or "").lower():
            return s
    return None


# map archive set → local short file (best effort)
SET_MAP = [
    {"ep": 704, "set": 1, "short": "/home/box/ari_matti_sets/shorts/kt704_passport_short.mp4",
     "granular": HERE / "killtony-minutes" / "kt704_ari_passport.granular.json"},
    {"ep": 715, "set": 2, "short": "/home/box/ari_matti_sets/shorts/kt715_walking_short.mp4",
     "granular": None},
    {"ep": 728, "set": 3, "short": "/home/box/ari_matti_sets/shorts/kt728_jamesbond_short.mp4",
     "granular": None},
]


def correlate_anger_to_numeric(theory: dict, granular: dict | None) -> dict:
    """Attach MediaPipe numeric windows near theory beat times where emotion is anger-ish."""
    if not granular:
        return {"note": "no granular yet"}
    windows = granular.get("numeric_windows") or []
    anger_beats = [
        b for b in (theory.get("beats") or [])
        if "angry" in (b.get("emotion") or "") or b.get("anger_flavor")
    ]
    # crude time alignment: distribute beats evenly across duration (no word timings yet)
    dur = granular.get("mediapipe", {}).get("duration_s") or 60
    n = max(len(theory.get("beats") or []), 1)
    out = []
    for i, b in enumerate(theory.get("beats") or []):
        t = dur * (i + 0.5) / n
        near = [w for w in windows if abs((w["t0"] + w["t1"]) / 2 - t) < 1.5]
        if not near:
            continue
        def mean(k):
            vals = [w.get(k) for w in near if w.get(k) is not None]
            return sum(vals) / len(vals) if vals else None
        out.append({
            "t_guess": round(t, 2),
            "emotion": b.get("emotion"),
            "anger_flavor": b.get("anger_flavor"),
            "beat_type": b.get("beat_type"),
            "numeric": {
                "brow_mean": mean("brow_mean"),
                "mouth_open_max": mean("mouth_open_max"),
                "mouth_wide_max": mean("mouth_wide_max"),
                "lean_x_range": mean("lean_x_range"),
                "arm_open_mean": mean("arm_open_mean"),
                "hand_face_right_min": mean("hand_face_right_min"),
            },
            "body_hypothesis": b.get("body_hypothesis"),
            "vocal_hypothesis": b.get("vocal_hypothesis"),
        })
    return {"aligned_beats": out}


def main():
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen-flash-character"
    c = _client()
    # list models the key can see (best effort)
    out_dir = HERE / "killtony-minutes"
    out_dir.mkdir(exist_ok=True)

    persona_f = HERE / "killtony-personas" / "ari_matti.json"
    persona = json.loads(persona_f.read_text()) if persona_f.exists() else {}

    for entry in SET_MAP:
        s = load_set_transcript(entry["ep"], entry["set"])
        if not s:
            print(f"skip ep{entry['ep']} set{entry['set']}: no archive transcript")
            continue
        transcript = s.get("set_transcript") or ""
        print(f"tag ep{entry['ep']} set{entry['set']} ({len(transcript)} chars) ...", flush=True)
        theory = tag_transcript(model, transcript, {"persona": persona})
        granular = None
        if entry["granular"] and Path(entry["granular"]).exists():
            granular = json.loads(Path(entry["granular"]).read_text())
        elif Path(entry["short"]).exists():
            # lazy: only if extract already ran; else leave None
            gpath = out_dir / f"kt{entry['ep']}_ari_set{entry['set']}.granular.json"
            if gpath.exists():
                granular = json.loads(gpath.read_text())

        corr = correlate_anger_to_numeric(theory, granular)
        stem = f"kt{entry['ep']}_ari_set{entry['set']}"
        path = out_dir / f"{stem}.theory.json"
        path.write_text(json.dumps({
            "id": stem,
            "model": model,
            "episode": entry["ep"],
            "set_number": entry["set"],
            "source_transcript_chars": len(transcript),
            "theory": theory,
            "anger_body_correlation": corr,
            "short": entry["short"],
        }, indent=2))
        print(f"  -> {path}")
        n_beats = len((theory.get("beats") or []))
        print(f"  beats={n_beats} anger_present={theory.get('anger_manual',{}).get('present')}")


if __name__ == "__main__":
    main()
