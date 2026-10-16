"""Laugh Track Generator: text/audio → calibrated laugh track.

Uses SMILE model (AUC 0.979) as base predictor, modulated by crowd physics.
Outputs per-beat: timestamp, P(laugh), intensity, selected laugh clip.

Usage:
  python3 laugh_track.py <transcript.txt> [--room cauldron|medium|red_curtain] [--comedian "Name"]
  python3 laugh_track.py --demo  # test on KT set
"""
from __future__ import annotations
import json, re, pickle, subprocess, tempfile
import numpy as np
from pathlib import Path
from scipy.sparse import hstack, csr_matrix

HERE = Path(__file__).parent
LAB = HERE / "voicelab"

# ============================================================
# SMILE MODEL (AUC 0.979)
# ============================================================

def load_smile():
    bundle = pickle.loads((LAB / "unified_laugh_model.pkl").read_bytes())
    return bundle["model"], bundle["vectorizer"]

def smile_predict(model, vec, text):
    def lex_feat(text):
        words = text.split()
        return [len(text), len(words), int("?" in text), int("!" in text),
                int(bool(re.search(r"\b(not|no|never|don't|won't|can't)\b", text, re.I))),
                int(bool(re.search(r"\b(fuck|shit|damn|hell|bitch)\b", text, re.I))),
                len(re.findall(r"\b(i|me|my|im|i'm|i've)\b", text.lower())),
                text.lower().count("laugh"), text.lower().count("smile"),
                text.lower().count("face"), text.lower().count("voice")]
    X_lex = np.array([lex_feat(text)])
    X_tfidf = vec.transform([text])
    X = hstack([csr_matrix(X_lex), X_tfidf])
    return float(model.predict_proba(X)[0, 1])

# ============================================================
# CROWD PHYSICS
# ============================================================

class CrowdState:
    def __init__(self, room_size=150):
        self.heat = 0.0
        self.contagion = 0
        self.decay = 0.88
    
    def update(self, laughed):
        if laughed:
            self.heat = min(self.heat + 0.15, 1.0)
            self.contagion = min(self.contagion + 1, 5)
        else:
            self.heat *= self.decay
            self.contagion = max(0, self.contagion - 1)
    
    def modulate(self, p):
        return min(p + self.heat * 0.1 + self.contagion * 0.05, 1.0)

# ============================================================
# LAUGH LIBRARY
# ============================================================

def select_laugh_clip(intensity):
    """Select laugh clip based on intensity (0-1)."""
    clips = [
        (0.0, "audience_laugh22"),   # light
        (0.5, "audience_laugh51"),   # medium
        (0.7, "crowd_bar_chile"),    # big
        (0.9, "crowd_laugh_clap"),   # huge
    ]
    for threshold, clip in reversed(clips):
        if intensity >= threshold:
            return clip
    return "audience_laugh22"

# ============================================================
# MAIN: text → laugh track
# ============================================================

def generate_laugh_track(text, room_size=150, comedian=None):
    model, vec = load_smile()
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 5]
    crowd = CrowdState(room_size)
    
    # Per-comedian calibration thresholds (from real KT data)
    comedian_thresholds = {
        "Kam Patterson": 0.534, "Hans Kim": 0.540, "David Lucas": 0.514,
        "Pat O'Neill": 0.526, "William Montgomery": 0.530, "Ari Matti": 0.520,
    }
    threshold = comedian_thresholds.get(comedian, 0.55)  # default 0.55
    
    track = []
    t = 0.0
    
    for sent in sents:
        p_base = smile_predict(model, vec, sent)
        # Threshold on BASE prediction (before crowd modulation)
        laugh = p_base >= threshold
        # Apply crowd modulation for intensity display
        p_final = crowd.modulate(p_base)
        
        intensity = p_final
        duration = 0.5 + intensity * 2.0
        clip = select_laugh_clip(intensity) if laugh else None
        
        track.append({
            "t_start": round(t, 1),
            "t_end": round(t + len(sent.split())/2.5, 1),
            "text": sent[:80],
            "p_base": round(p_base, 3),
            "p_final": round(p_final, 3),
            "laugh": laugh,
            "intensity": round(intensity, 3),
            "duration_s": round(duration, 1),
            "clip": clip,
            "crowd_heat": round(crowd.heat, 3),
        })
        
        crowd.update(laugh)
        t += len(sent.split()) / 2.5
    
    summary = {
        "total_sentences": len(sents),
        "total_laugh": sum(1 for e in track if e["laugh"]),
        "laugh_rate": round(sum(1 for e in track if e["laugh"]) / max(len(sents), 1), 3),
        "avg_intensity": round(np.mean([e["intensity"] for e in track if e["laugh"]]), 3) if any(e["laugh"] for e in track) else 0,
        "room_size": room_size,
    }
    
    return track, summary

if __name__ == "__main__":
    import sys
    
    if "--demo" in sys.argv:
        kt = json.loads(open("/home/box/comedy-audio/kt_transcripts.json").read())
        text = kt.get("kam_ep716_roar", "")
        print("DEMO: Kam Patterson ep716")
        print("="*70)
        track, summary = generate_laugh_track(text, room_size=150)
        
        for e in track:
            bar = "█" * int(e["p_final"] * 20)
            clip = f" [{e['clip']}]" if e["clip"] else ""
            marker = " 😂" if e["laugh"] else ""
            print(f"  t={e['t_start']:5.1f}s P={e['p_final']:.3f} {bar:20s} int={e['intensity']:.2f}{clip}{marker} | {e['text'][:35]}")
        
        print(f"\n{json.dumps(summary, indent=2)}")
    else:
        if len(sys.argv) < 2:
            print("Usage: python3 laugh_track.py <transcript.txt> [--room cauldron|medium|red_curtain]")
            sys.exit(1)
        
        text = open(sys.argv[1]).read()
        room = "medium"
        if "--room" in sys.argv:
            room = sys.argv[sys.argv.index("--room") + 1]
        
        room_sizes = {"cauldron": 30, "medium": 150, "red_curtain": 500}
        track, summary = generate_laugh_track(text, room_sizes.get(room, 150))
        
        for e in track:
            bar = "█" * int(e["p_final"] * 20)
            clip = f" [{e['clip']}]" if e["clip"] else ""
            marker = " 😂" if e["laugh"] else ""
            print(f"  t={e['t_start']:5.1f}s P={e['p_final']:.3f} {bar:20s}{clip}{marker} | {e['text'][:50]}")
        
        print(f"\n{json.dumps(summary, indent=2)}")
