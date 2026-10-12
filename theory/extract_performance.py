"""Granular performance extraction: acting video → Stage Lab performance.v1.

Pipeline:
  1. MediaPipe Face Mesh + Pose  → numeric time series (face + body dials)
  2. qwen3.8-omni-flash (audio)  → vocal delivery descriptor
  3. qwen3.8-omni-flash (frames+transcript) → comedy theory + emotion + body labels
  4. merge → performance.v1 timeline + granular_performance.json

Outputs land in theory/killtony-minutes/ (gitignored media stays outside).
Key: audition/.env DASHSCOPE_API_KEY only.
"""
from __future__ import annotations

import argparse
import base64
import json
import math
import os
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).parent
AUDITION = HERE.parent / "audition"
OUT_DIR = HERE.parent / "theory" / "killtony-minutes"
TMP = Path("/tmp/opencode/perf_extract")

# ---------------------------------------------------------------------------
# MediaPipe numeric extraction
# ---------------------------------------------------------------------------

# Face Mesh landmark indices (MediaPipe FaceMesh)
L_BROW_OUT, L_BROW_IN, L_BROW_TIP = 70, 63, 107
R_BROW_OUT, R_BROW_IN, R_BROW_TIP = 300, 296, 336
L_EYE_TOP, L_EYE_BOT, L_EYE_OUT, L_EYE_IN = 159, 145, 33, 133
R_EYE_TOP, R_EYE_BOT, R_EYE_OUT, R_EYE_IN = 386, 374, 362, 263
MOUTH_L, MOUTH_R = 61, 291
LIP_TOP, LIP_BOT = 13, 14
NOSE_TIP = 1
CHIN = 152
EAR_L, EAR_R = 234, 454

# Pose landmarks
L_SHOULDER, R_SHOULDER = 11, 12
L_ELBOW, R_ELBOW = 13, 14
L_WRIST, R_WRIST = 15, 16
L_HIP, R_HIP = 23, 24
L_EAR_POSE, R_EAR_POSE = 7, 8
NOSE_POSE = 0


def _dist(a, b) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def _norm(v) -> float:
    return float(np.linalg.norm(v))


MP_MODELS = Path("/tmp/opencode/mp_models")


def extract_mediapipe(video_path: Path, sample_every: int = 2) -> dict:
    """Sample face+body dials at ~15fps using MediaPipe Tasks API."""
    import mediapipe as mp
    from mediapipe.tasks.python import vision
    from mediapipe.tasks.python.core.base_options import BaseOptions

    face_opts = vision.FaceLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MP_MODELS / "face_landmarker.task")),
        running_mode=vision.RunningMode.VIDEO, num_faces=1, output_face_blendshapes=True,
        output_facial_transformation_matrixes=False,
        min_tracking_confidence=0.5)
    pose_opts = vision.PoseLandmarkerOptions(
        base_options=BaseOptions(model_asset_path=str(MP_MODELS / "pose_landmarker_lite.task")),
        running_mode=vision.RunningMode.VIDEO, num_poses=1,
        min_tracking_confidence=0.5)
    face_lm = vision.FaceLandmarker.create_from_options(face_opts)
    pose_lm = vision.PoseLandmarker.create_from_options(pose_opts)

    cap = cv2.VideoCapture(str(video_path))
    fps = cap.get(cv2.CAP_PROP_FPS) or 30.0
    frame_i = 0
    frames: list[dict] = []

    def mp_ts(frame_idx: int) -> int:
        return frame_idx * 1000000  # microseconds

    while True:
        ok, frame = cap.read()
        if not ok:
            break
        if frame_i % sample_every == 0:
            t = frame_i / fps
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            mp_img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
            ts = mp_ts(frame_i)
            row: dict = {"t": round(t, 3)}

            fm = face_lm.detect_for_video(mp_img, ts)
            if fm.face_landmarks:
                lm = fm.face_landmarks[0]
                h, w = frame.shape[:2]
                def pt(i):
                    p = lm[i]
                    return (p.x * w, p.y * h, getattr(p, "z", 0.0))
                face_w = _dist(pt(EAR_L)[:2], pt(EAR_R)[:2]) or 1.0
                eye_mid_y = (pt(L_EYE_TOP)[1] + pt(L_EYE_BOT)[1] + pt(R_EYE_TOP)[1] + pt(R_EYE_BOT)[1]) / 4
                face_d = {
                    "brow_left": round((eye_mid_y - pt(L_BROW_TIP)[1]) / face_w, 4),
                    "brow_right": round((eye_mid_y - pt(R_BROW_TIP)[1]) / face_w, 4),
                    "brow_asym": round((pt(L_BROW_TIP)[1] - pt(R_BROW_TIP)[1]) / face_w, 4),
                    "eye_open_left": round(_dist(pt(L_EYE_TOP)[:2], pt(L_EYE_BOT)[:2]) / face_w, 4),
                    "eye_open_right": round(_dist(pt(R_EYE_TOP)[:2], pt(R_EYE_BOT)[:2]) / face_w, 4),
                    "mouth_open": round(_dist(pt(LIP_TOP)[:2], pt(LIP_BOT)[:2]) / face_w, 4),
                    "mouth_wide": round(_dist(pt(MOUTH_L)[:2], pt(MOUTH_R)[:2]) / face_w, 4),
                    "head_yaw_proxy": round((pt(EAR_R)[0] - pt(EAR_L)[0]) / face_w, 4),
                    "head_pitch_proxy": round((pt(CHIN)[1] - pt(NOSE_TIP)[1]) / face_w, 4),
                    "nose_mouth": round(_dist(pt(NOSE_TIP)[:2], pt(LIP_TOP)[:2]) / face_w, 4),
                }
                # blendshapes if present (categories: browInnerUp, jawOpen, mouthSmile...)
                if fm.face_blendshapes:
                    bs = {c.category_name: round(c.score, 4) for c in fm.face_blendshapes[0]}
                    for k in ("browInnerUp", "browDownLeft", "browDownRight",
                              "jawOpen", "mouthSmileLeft", "mouthSmileRight",
                              "mouthFrownLeft", "mouthFrownRight",
                              "eyeBlinkLeft", "eyeBlinkRight",
                              "eyeSquintLeft", "eyeSquintRight",
                              "mouthPressLeft", "mouthPressRight",
                              "cheekPuff", "noseSneerLeft", "noseSneerRight"):
                        if k in bs:
                            face_d[f"bs_{k}"] = bs[k]
                row["face"] = face_d

            pr = pose_lm.detect_for_video(mp_img, ts)
            if pr.pose_world_landmarks or pr.pose_landmarks:
                pl = (pr.pose_world_landmarks or pr.pose_landmarks)[0]
                h, w = frame.shape[:2]
                def ppt(i):
                    p = pl[i]
                    # world landmarks are metric; use x,y scaled for proxies
                    return (p.x, p.y, getattr(p, "visibility", 1.0))
                sh_l, sh_r = ppt(L_SHOULDER), ppt(R_SHOULDER)
                hip_l, hip_r = ppt(L_HIP), ppt(R_HIP)
                torso = _dist(sh_l[:2], hip_l[:2]) or 1.0
                row["body"] = {
                    "shoulder_tilt": round((sh_l[1] - sh_r[1]) / torso, 4),
                    "lean_x": round(((sh_l[0] + sh_r[0]) / 2 - (hip_l[0] + hip_r[0]) / 2) / torso, 4),
                    "lean_y": round(((sh_l[1] + sh_r[1]) / 2 - (hip_l[1] + hip_r[1]) / 2) / torso, 4),
                    "arm_open": round(
                        (_dist(sh_l[:2], ppt(L_WRIST)[:2]) + _dist(sh_r[:2], ppt(R_WRIST)[:2])) / (2 * torso), 4),
                    "elbow_left": round(_dist(sh_l[:2], ppt(L_ELBOW)[:2]) / torso, 4),
                    "elbow_right": round(_dist(sh_r[:2], ppt(R_ELBOW)[:2]) / torso, 4),
                    "hand_face_left": round(_dist(ppt(L_WRIST)[:2], ppt(NOSE_POSE)[:2]) / torso, 4),
                    "hand_face_right": round(_dist(ppt(R_WRIST)[:2], ppt(NOSE_POSE)[:2]) / torso, 4),
                    "visibility": round(float(sh_l[2] + sh_r[2]) / 2, 3),
                }
            frames.append(row)
        frame_i += 1

    cap.release()
    face_lm.close()
    pose_lm.close()

    # derivative features (velocity of key dials)
    for i in range(1, len(frames)):
        dt = max(frames[i]["t"] - frames[i - 1]["t"], 1e-3)
        for section, keys in (("face", ("brow_left", "mouth_open", "mouth_wide")),
                              ("body", ("lean_x", "arm_open", "shoulder_tilt"))):
            if section in frames[i] and section in frames[i - 1]:
                for k in keys:
                    if k in frames[i][section] and k in frames[i - 1][section]:
                        frames[i][section][f"d_{k}"] = round(
                            (frames[i][section][k] - frames[i - 1][section][k]) / dt, 4)

    return {
        "fps_sampled": round(fps / sample_every, 2),
        "source_fps": fps,
        "n_frames": len(frames),
        "duration_s": round(frames[-1]["t"], 2) if frames else 0,
        "frames": frames,
    }


# ---------------------------------------------------------------------------
# Alibaba Omni (OpenAI-compatible)
# ---------------------------------------------------------------------------

def _load_env():
    key = os.getenv("DASHSCOPE_API_KEY", "").strip()
    base = os.getenv("DASHSCOPE_BASE_URL", "https://dashscope-intl.aliyuncs.com/compatible-mode/v1").strip()
    if not key:
        for line in (AUDITION / ".env").read_text().splitlines():
            if line.startswith("DASHSCOPE_API_KEY="):
                key = line.split("=", 1)[1].strip().strip("'\"")
            elif line.startswith("DASHSCOPE_BASE_URL="):
                base = line.split("=", 1)[1].strip().strip("'\"")
    return key, base


def _b64_data_uri(path: Path, mime: str) -> str:
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def omni_analyze_audio(audio_path: Path, prompt: str, model: str = "qwen3.8-omni-flash") -> dict:
    """Vocal delivery pass — audio only (small, reliable)."""
    from openai import OpenAI
    key, base = _load_env()
    if not key:
        return {"ok": False, "error": "no API key"}
    client = OpenAI(api_key=key, base_url=base)
    # compress to mp3 if huge
    mp3 = audio_path.with_suffix(".omni.mp3")
    if audio_path.suffix.lower() != ".mp3" or audio_path.stat().st_size > 8_000_000:
        subprocess.run(
            ["ffmpeg", "-y", "-i", str(audio_path), "-c:a", "libmp3lame", "-b:a", "64k", str(mp3)],
            capture_output=True, timeout=60)
        audio_path = mp3 if mp3.exists() else audio_path
    uri = _b64_data_uri(audio_path, "audio/mpeg" if audio_path.suffix == ".mp3" else "audio/wav")
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "input_audio", "input_audio": {"data": uri.split(",", 1)[1],
                                                            "format": "mp3" if audio_path.suffix == ".mp3" else "wav"}},
                ],
            }],
            temperature=0.2,
            extra_body={"response_format": {"type": "json_object"}},
        )
        text = r.choices[0].message.content or "{}"
        return {"ok": True, "raw": text, "parsed": _try_json(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:400]}


def omni_analyze_frames(image_paths: list[Path], prompt: str, model: str = "qwen3.8-omni-flash") -> dict:
    """Visual/theory pass — keyframes as images (no OSS needed)."""
    from openai import OpenAI
    key, base = _load_env()
    if not key:
        return {"ok": False, "error": "no API key"}
    client = OpenAI(api_key=key, base_url=base)
    content: list = [{"type": "text", "text": prompt}]
    for p in image_paths:
        uri = _b64_data_uri(p, "image/jpeg")
        content.append({"type": "image_url", "image_url": {"url": uri, "detail": "low"}})
    try:
        r = client.chat.completions.create(
            model=model,
            messages=[{"role": "user", "content": content}],
            temperature=0.2,
            extra_body={"response_format": {"type": "json_object"}},
        )
        text = r.choices[0].message.content or "{}"
        return {"ok": True, "raw": text, "parsed": _try_json(text)}
    except Exception as e:
        return {"ok": False, "error": str(e)[:400]}


def _try_json(s: str):
    s = s.strip()
    if s.startswith("```"):
        s = s.split("```", 2)[1] if s.count("```") >= 2 else s
        if s.startswith("json"):
            s = s[4:]
    try:
        return json.loads(s)
    except Exception:
        # find first { ... }
        a, b = s.find("{"), s.rfind("}")
        if a >= 0 and b > a:
            try:
                return json.loads(s[a:b + 1])
            except Exception:
                pass
    return {"_unparsed": s[:2000]}


def extract_keyframes(video_path: Path, times_s: list[float], out_dir: Path) -> list[Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = []
    for i, t in enumerate(times_s):
        p = out_dir / f"kf_{i:02d}_{t:.1f}s.jpg"
        subprocess.run(
            ["ffmpeg", "-y", "-ss", str(t), "-i", str(video_path),
             "-frames:v", "1", "-q:v", "4", "-vf", "scale=480:-2", str(p)],
            capture_output=True, timeout=30)
        if p.exists() and p.stat().st_size > 1000:
            paths.append(p)
    return paths


# ---------------------------------------------------------------------------
# Prompts — maximum granularity on anger / body / voice
# ---------------------------------------------------------------------------

VOCAL_PROMPT = """You are a comedy performance analyst. Listen to this stand-up audio clip.
Return STRICT JSON only. Analyze VOCAL DELIVERY only (not jokes).

{
  "speaker": str,
  "accent_notes": str,
  "baseline_pitch": "low|mid|high",
  "pitch_range": "narrow|mid|wide",
  "pace_wpm_est": number,
  "energy_curve": [{"t": number, "energy": number}],   // 0-1, ~8 points
  "volume_curve": [{"t": number, "loudness": number}], // 0-1, ~8 points
  "segments": [
    {
      "t0": number, "t1": number,
      "emotion": "neutral|angry|defiant|gleeful|manic|deadpan|embarrassed|mock_angry|sarcastic",
      "emotion_intensity": number,
      "vocal_actions": ["quiet","build","shout","whisper","laugh_through","spit_out","drawl","rapid_fire","held_silence"],
      "pitch_shift": "flat|rise|fall|spike|drop",
      "emphasis_words": [str],
      "breath_pattern": "steady|held|panting|sigh",
      "note": str  // one line on HOW the voice carries the emotion
    }
  ],
  "anger_specific": {
    // only fill if anger or mock-anger appears; else null
    "present": bool,
    "type": "hot_yelling|cold_flat|mock_indignant|controlled_seethe|fake_rage_for_joke",
    "markers": [str],   // e.g. "volume spike on target word", "sudden quiet after loud"
    "target": str,      // who/what the anger is directed at
    "release_or_withhold": "releases_into_laugh|withholds_stays_angry|switches_to_deadpan"
  }
}"""

FRAME_PROMPT = """You are a comedy performance analyst. These are sequential keyframes from a stand-up set (vertical video, comedian on stage).
Also given: approximate timestamps for each frame.

Return STRICT JSON only.

{
  "overall_body_style": str,
  "stage_presence": "still_dominant|pacing|gestural|expansive|contained",
  "segments": [
    {
      "frame_indices": [int],
      "t_guess": number,
      "body_language": {
        "lean": "back|neutral|forward",
        "lean_amount": number,
        "head_tilt": "none|left|right|down_challenge|up_dismiss",
        "arm_state": "sides|open|crossed|mic_point|hand_to_face|gesture_out|hands_together",
        "shoulder_shrug": number,
        "facial_expression": "neutral|annoyed|surprised|deadpan|smirk|grimace|wide_eyes|sneer|mock_horror",
        "brow": "neutral|raised|furrowed|one_raised|flat_angry",
        "eye_contact": "audience|floor|side|mic|camera",
        "micro_gesture": str  // e.g. "micro-shrug on punch", "chin tuck"
      },
      "comedy_theory": {
        "beat_type": "setup|premise|escalation|punchline|tag|callback|closer|button",
        "gtvh_operators": ["literalise","double_meaning","topic_wipeout","self_deprecation","status_manipulation","other"],
        "bergson": "mechanicity|repetition|elasticity|none",
        "benign_violation_tension": number,
        "status_move": "down|up|flat|reversal",
        "note": str
      },
      "emotion_read": {
        "primary": str,
        "arousal": number,
        "valence": number,
        "dominance": number,
        "is_performed_vs_genuine": "performed|genuine|ambiguous",
        "anger_flavor": null | "hot|cold|mock|contained"
      }
    }
  ],
  "gesture_library_candidates": [
    // discrete reusable gestures you can name for a motion library
    {"name": str, "t_guess": number, "duration_est_s": number,
     "body_params": {"lean": number, "head_deg": number, "arm_open": number, "brow": number}}
  ],
  "what_angry_looks_like_here": {
    // fill from any anger/mock-anger frames; else null
    "present": bool,
    "body_signature": [str],   // e.g. "chin jut", "micro point with mic hand", "freeze then snap"
    "face_signature": [str],
    "contrast_before_after": str // how non-anger frames differ
  }
}"""


# ---------------------------------------------------------------------------
# Merge → performance.v1 + granular
# ---------------------------------------------------------------------------

def numeric_aggregates(mp_data: dict, win_s: float = 1.0) -> list[dict]:
    """Windowed stats of MediaPipe dials for theory correlation."""
    frames = mp_data["frames"]
    if not frames:
        return []
    t0, t1 = frames[0]["t"], frames[-1]["t"]
    out = []
    t = t0
    while t < t1:
        chunk = [f for f in frames if t <= f["t"] < t + win_s]
        if not chunk:
            t += win_s
            continue
        def col(section, key):
            vals = [f[section][key] for f in chunk if section in f and key in f[section]]
            if not vals:
                return None
            return {"mean": round(float(np.mean(vals)), 4),
                    "max": round(float(np.max(vals)), 4),
                    "min": round(float(np.min(vals)), 4),
                    "range": round(float(np.ptp(vals)), 4)}
        out.append({
            "t0": round(t, 2), "t1": round(t + win_s, 2),
            "brow_mean": (col("face", "brow_left") or {}).get("mean"),
            "brow_range": (col("face", "brow_left") or {}).get("range"),
            "mouth_open_mean": (col("face", "mouth_open") or {}).get("mean"),
            "mouth_open_max": (col("face", "mouth_open") or {}).get("max"),
            "mouth_wide_max": (col("face", "mouth_wide") or {}).get("max"),
            "eye_open_mean": (lambda c: (c["mean"] if c else None))(
                col("face", "eye_open_left")),
            "lean_x_mean": (col("body", "lean_x") or {}).get("mean"),
            "lean_x_range": (col("body", "lean_x") or {}).get("range"),
            "arm_open_mean": (col("body", "arm_open") or {}).get("mean"),
            "shoulder_tilt_abs": abs((col("body", "shoulder_tilt") or {}).get("mean") or 0),
            "hand_face_right_min": (col("body", "hand_face_right") or {}).get("min"),
        })
        t += win_s
    return out


def build_performance_v1(granular: dict, source_id: str) -> dict:
    """Map granular segments → Stage Lab performance.v1 events."""
    events = []
    segs = (granular.get("frames_pass", {}) or {}).get("segments") or []
    for i, seg in enumerate(segs):
        bl = seg.get("body_language") or {}
        ct = seg.get("comedy_theory") or {}
        er = seg.get("emotion_read") or {}
        t0 = float(seg.get("t_guess") or i)
        # expression
        expr = bl.get("facial_expression") or "neutral"
        if expr in ("neutral", "deadpan"):
            expr = "deadpan" if expr == "deadpan" else "neutral"
        events.append({"t": round(t0, 2), "kind": "expression", "value": expr,
                       "intensity": er.get("arousal")})
        # gesture
        lean = bl.get("lean") or "neutral"
        arm = bl.get("arm_state") or "sides"
        gesture = "hold still"
        if lean == "forward":
            gesture = "lean in"
        elif arm in ("open", "gesture_out"):
            gesture = "small gesture"
        elif bl.get("shoulder_shrug", 0) and bl.get("shoulder_shrug", 0) > 0.3:
            gesture = "shrug"
        events.append({"t": round(t0, 2), "kind": "gesture", "value": gesture})
        # look
        look = (bl.get("eye_contact") or "audience").replace("_", " ")
        events.append({"t": round(t0, 2), "kind": "look", "value": look})
        # hold on punchline (stillness rule from Stage Lab)
        if ct.get("beat_type") == "punchline":
            events.append({"t": round(t0, 2) + 0.05, "kind": "hold", "ms": 1200})

    # speech markers from vocal pass
    for seg in (granular.get("audio_pass", {}) or {}).get("segments") or []:
        events.append({
            "t": round(float(seg.get("t0", 0)), 2),
            "kind": "speak_start",
            "value": {
                "emotion": seg.get("emotion"),
                "intensity": seg.get("emotion_intensity"),
                "actions": seg.get("vocal_actions"),
                "pitch_shift": seg.get("pitch_shift"),
            },
        })

    events.sort(key=lambda e: e["t"])
    return {
        "version": "performance.v1",
        "source": source_id,
        "duration_s": granular.get("mediapipe", {}).get("duration_s"),
        "events": events,
        "n_events": len(events),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video", type=Path)
    ap.add_argument("--id", default=None, help="output stem")
    ap.add_argument("--skip-omni", action="store_true")
    ap.add_argument("--sample-every", type=int, default=2)
    args = ap.parse_args()

    vid = args.video.resolve()
    stem = args.id or vid.stem
    TMP.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[1/4] MediaPipe {vid.name} ...", flush=True)
    mp_data = extract_mediapipe(vid, sample_every=args.sample_every)
    print(f"      {mp_data['n_frames']} samples, {mp_data['duration_s']}s")

    print("[2/4] numeric windows ...", flush=True)
    windows = numeric_aggregates(mp_data)

    audio_pass = {}
    frames_pass = {}
    if not args.skip_omni:
        # keyframes every ~N seconds across clip
        dur = mp_data["duration_s"] or 60
        n_kf = min(8, max(4, int(dur // 8)))
        times = [round(dur * (i + 0.5) / n_kf, 2) for i in range(n_kf)]
        print(f"[3/4] Omni keyframes @ {times} ...", flush=True)
        kfs = extract_keyframes(vid, times, TMP / f"kf_{stem}")
        # annotate times into prompt
        fp = FRAME_PROMPT + "\n\nFrame timestamps (seconds): " + json.dumps(times)
        frames_pass = omni_analyze_frames(kfs, fp)
        if frames_pass.get("ok"):
            frames_pass = frames_pass.get("parsed") or frames_pass
            print(f"      frames ok, {len(frames_pass.get('segments') or [])} segments")
        else:
            print(f"      frames FAIL: {frames_pass.get('error')}")

        # audio
        wav = TMP / f"{stem}_audio.wav"
        subprocess.run(["ffmpeg", "-y", "-i", str(vid), "-vn", str(wav)],
                       capture_output=True, timeout=60)
        if wav.exists():
            print("[4/4] Omni vocal pass ...", flush=True)
            audio_pass = omni_analyze_audio(wav, VOCAL_PROMPT)
            if audio_pass.get("ok"):
                audio_pass = audio_pass.get("parsed") or audio_pass
                print(f"      audio ok, {len(audio_pass.get('segments') or [])} segments")
            else:
                print(f"      audio FAIL: {audio_pass.get('error')}")
        else:
            print("[4/4] no audio extracted, skip vocal")
    else:
        print("[3-4/4] skip omni")

    granular = {
        "id": stem,
        "video": str(vid),
        "extracted_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "mediapipe": {k: v for k, v in mp_data.items() if k != "frames"},
        "numeric_windows": windows,
        "audio_pass": audio_pass if isinstance(audio_pass, dict) else {},
        "frames_pass": frames_pass if isinstance(frames_pass, dict) else {},
        "anger_focus": _extract_anger(mp_data, windows, audio_pass, frames_pass),
    }

    # full face/body frames optional (heavy) — keep windows only in main file
    granular_path = OUT_DIR / f"{stem}.granular.json"
    granular_path.write_text(json.dumps(granular, indent=2))
    print(f"wrote {granular_path}")

    perf = build_performance_v1(granular, stem)
    perf_path = OUT_DIR / f"{stem}.performance.v1.json"
    perf_path.write_text(json.dumps(perf, indent=2))
    print(f"wrote {perf_path}  ({perf['n_events']} events)")

    # anger drill-down report
    anger_path = OUT_DIR / f"{stem}.anger_report.md"
    anger_path.write_text(render_anger_report(stem, granular))
    print(f"wrote {anger_path}")


def _extract_anger(mp_data, windows, audio_pass, frames_pass) -> dict:
    """Isolate numeric signature of anger segments vs baseline."""
    anger_segs = []
    if isinstance(audio_pass, dict):
        for s in audio_pass.get("segments") or []:
            emo = (s.get("emotion") or "").lower()
            if "angry" in emo or "defiant" in emo or "manic" in emo:
                anger_segs.append({"source": "audio", **s})
    if isinstance(frames_pass, dict):
        for s in frames_pass.get("segments") or []:
            er = s.get("emotion_read") or {}
            emo = (er.get("primary") or "").lower()
            anger_flavor = er.get("anger_flavor")
            if "angry" in emo or anger_flavor:
                anger_segs.append({"source": "visual", "t_guess": s.get("t_guess"),
                                   "emotion": emo, "anger_flavor": anger_flavor,
                                   "body": s.get("body_language")})

    # baseline = windows where no anger seg overlaps
    def in_anger(t0):
        for a in anger_segs:
            a0 = a.get("t0", a.get("t_guess", 0))
            a1 = a.get("t1", (a0 or 0) + 2)
            if a0 is not None and a0 <= t0 + 0.5 <= (a1 or a0 + 2):
                return True
        return False

    ang_w = [w for w in windows if in_anger(w["t0"])]
    base_w = [w for w in windows if not in_anger(w["t0"])]

    def avg(ws, k):
        vals = [w[k] for w in ws if w.get(k) is not None]
        return round(float(np.mean(vals)), 4) if vals else None

    keys = ["brow_mean", "brow_range", "mouth_open_max", "mouth_wide_max",
            "lean_x_mean", "lean_x_range", "arm_open_mean", "shoulder_tilt_abs",
            "hand_face_right_min"]
    return {
        "n_anger_windows": len(ang_w),
        "n_baseline_windows": len(base_w),
        "anger_segments": anger_segs,
        "anger_vs_baseline": {
            k: {"anger": avg(ang_w, k), "baseline": avg(base_w, k),
                "delta": round((avg(ang_w, k) or 0) - (avg(base_w, k) or 0), 4)
                        if avg(ang_w, k) is not None and avg(base_w, k) is not None else None}
            for k in keys
        },
        "visual_signature": (frames_pass or {}).get("what_angry_looks_like_here")
            if isinstance(frames_pass, dict) else None,
    }


def render_anger_report(stem: str, g: dict) -> str:
    a = g.get("anger_focus") or {}
    lines = [
        f"# Anger / body / voice report — `{stem}`",
        "",
        f"- anger windows: **{a.get('n_anger_windows')}** / baseline: **{a.get('n_baseline_windows')}**",
        "",
        "## Numeric delta (anger − baseline)",
        "",
        "| dial | anger | baseline | delta |",
        "|------|------:|---------:|------:|",
    ]
    for k, v in (a.get("anger_vs_baseline") or {}).items():
        lines.append(f"| {k} | {v.get('anger')} | {v.get('baseline')} | {v.get('delta')} |")
    lines += ["", "## Visual signature", "```json",
              json.dumps(a.get("visual_signature"), indent=2), "```"]
    ang = (g.get("audio_pass") or {}).get("anger_specific")
    lines += ["", "## Vocal anger_specific", "```json", json.dumps(ang, indent=2), "```"]
    lines += ["", "## Modulator cross-ref",
              "Map deltas onto audition/modulators.json `angry.performative`:",
              "- `emphasis_delta` ← mouth_wide_max / brow_range spikes",
              "- `gestures: sharp` ← lean_x_range + arm_open velocity",
              "- `pace_delta` ← vocal pace_wpm_est vs baseline",
              "- `pause_mult` ← held_silence / breath_pattern markers",
              ""]
    return "\n".join(lines)


if __name__ == "__main__":
    main()
