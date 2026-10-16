"""Laugh Timeline Generator: text in → laugh timeline out.

Pipeline:
  1. SMILE model (AUC 0.979) → P(laugh) per sentence
  2. Crowd physics (contagion AUC 0.623) → modulate by crowd state
  3. Output: laugh timeline with timing + intensity

Usage:
  python3 laugh_timeline.py <transcript.txt> [--room cauldron|medium|red_curtain]
  python3 laugh_timeline.py --demo  # test on KT set
"""
from __future__ import annotations
import json, re, pickle
import numpy as np
from pathlib import Path
from scipy.sparse import hstack, csr_matrix

HERE = Path(__file__).parent
LAB = HERE / "voicelab"

# ============================================================
# SMILE MODEL (AUC 0.979)
# ============================================================

def load_smile_model():
    bundle = pickle.loads((LAB / "unified_laugh_model.pkl").read_bytes())
    return bundle["model"], bundle["vectorizer"]

def lex_feat(text):
    words = text.split()
    return [len(text), len(words), int("?" in text), int("!" in text),
            int(bool(re.search(r"\b(not|no|never|don't|won't|can't)\b", text, re.I))),
            int(bool(re.search(r"\b(fuck|shit|damn|hell|bitch)\b", text, re.I))),
            len(re.findall(r"\b(i|me|my|im|i'm|i've)\b", text.lower())),
            text.lower().count("laugh"), text.lower().count("smile"),
            text.lower().count("face"), text.lower().count("voice")]

def smile_predict(model, vec, text):
    X_lex = np.array([lex_feat(text)])
    X_tfidf = vec.transform([text])
    X = hstack([csr_matrix(X_lex), X_tfidf])
    return float(model.predict_proba(X)[0, 1])

# ============================================================
# CROWD PHYSICS (contagion AUC 0.623)
# ============================================================

class CrowdState:
    def __init__(self, room_size=150):
        self.room_size = room_size
        self.heat = 0.0
        self.contagion = 0
        self.laugh_times = []
        self.decay = 0.88  # from CrowdPhysics engine
    
    def update(self, t, laughed):
        # Decay heat
        self.heat *= self.decay
        
        if laughed:
            self.heat = min(self.heat + 0.15, 1.0)
            self.contagion = min(self.contagion + 1, 5)
            self.laugh_times.append(t)
        else:
            self.contagion = max(0, self.contagion - 1)
    
    def modulate(self, base_p):
        """Apply crowd state to base prediction (contagion AUC 0.623)."""
        heat_boost = self.heat * 0.1
        contagion_boost = self.contagion * 0.05
        return min(base_p + heat_boost + contagion_boost, 1.0)

# ============================================================
# MAIN: text → laugh timeline
# ============================================================

def generate_laugh_timeline(text, room_size=150, threshold=0.5):
    """Generate laugh timeline from transcript text.
    
    Returns:
        timeline: [{t_start, t_end, p_laugh, p_final, laugh, intensity}]
        summary: {total_laughs, avg_p, crowd_heat_end}
    """
    model, vec = load_smile_model()
    
    # Split into sentences
    sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', text) if len(s.strip()) > 5]
    
    # Estimate timing (~2.5 words/sec)
    crowd = CrowdState(room_size)
    timeline = []
    t = 0.0
    
    for i, sent in enumerate(sents):
        words = len(sent.split())
        duration = words / 2.5
        t_start = t
        t_end = t + duration
        
        # Base prediction from SMILE
        p_base = smile_predict(model, vec, sent)
        
        # Crowd modulation
        p_final = crowd.modulate(p_base)
        
        # Laugh happens?
        laugh = p_final >= threshold
        
        # Intensity: based on p_final and crowd heat
        intensity = min(10, p_final * 10 * (1 + crowd.heat * 0.5))
        
        timeline.append({
            "t_start": round(t_start, 1),
            "t_end": round(t_end, 1),
            "text": sent[:80],
            "p_base": round(p_base, 3),
            "p_final": round(p_final, 3),
            "laugh": laugh,
            "intensity": round(intensity, 1),
            "crowd_heat": round(crowd.heat, 3),
        })
        
        crowd.update(t_end, laugh)
        t = t_end
    
    summary = {
        "total_sentences": len(sents),
        "total_laugh": sum(1 for e in timeline if e["laugh"]),
        "avg_p_base": round(np.mean([e["p_base"] for e in timeline]), 3),
        "avg_p_final": round(np.mean([e["p_final"] for e in timeline]), 3),
        "crowd_heat_end": round(crowd.heat, 3),
        "room_size": room_size,
    }
    
    return timeline, summary

if __name__ == "__main__":
    import sys
    
    if "--demo" in sys.argv:
        # Test on KT set
        kt = json.loads(open("/home/box/comedy-audio/kt_transcripts.json").read())
        text = kt["kam_ep716_roar"]
        print("DEMO: Kam Patterson ep716")
        print("="*60)
        timeline, summary = generate_laugh_timeline(text, room_size=150)
        
        for e in timeline:
            bar = "█" * int(e["p_final"] * 20)
            marker = " 😂" if e["laugh"] else ""
            print(f"  t={e['t_start']:5.1f}s P={e['p_final']:.3f} {bar:20s} heat={e['crowd_heat']:.2f}{marker} | {e['text'][:40]}")
        
        print(f"\nSummary: {summary}")
    else:
        # Read from file
        if len(sys.argv) < 2:
            print("Usage: python3 laugh_timeline.py <transcript.txt> [--room cauldron|medium|red_curtain]")
            sys.exit(1)
        
        text = open(sys.argv[1]).read()
        room = "medium"
        if "--room" in sys.argv:
            room = sys.argv[sys.argv.index("--room") + 1]
        
        room_sizes = {"cauldron": 30, "medium": 150, "red_curtain": 500}
        room_size = room_sizes.get(room, 150)
        
        timeline, summary = generate_laugh_timeline(text, room_size)
        
        for e in timeline:
            bar = "█" * int(e["p_final"] * 20)
            marker = " 😂" if e["laugh"] else ""
            print(f"  t={e['t_start']:5.1f}s P={e['p_final']:.3f} {bar:20s}{marker} | {e['text'][:50]}")
        
        print(f"\n{json.dumps(summary, indent=2)}")
