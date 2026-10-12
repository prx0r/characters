"""Gemini performance.v1 → Stage Lab events + standalone Ralph player HTML.

Mapping:
  Gemini emotion     → Ralph expression (rig expressions table)
  body.lean forward  → lean_forward gesture
  body.arms open     → small_shrug
  body.head jut/tilt → head_tilt
  beat_type punchline→ hold 1200ms + eye_glitch
  anger present      → annoyed face boost
  vocal.energy > 0.7 → camera medium→closeup push

Output: standalone HTML (no server) + performance.v1 JSON.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
AUDITION = HERE.parent / "audition"
OUT = HERE / "killtony-minutes"
RIGS = AUDITION / "rigs"

# Gemini emotion → Ralph expression (from rigs/ralph.json)
EMOTION_MAP = {
    "neutral": "deadpan",
    "deadpan": "deadpan",
    "annoyed": "annoyed",
    "angry": "annoyed",
    "mock_indignant": "annoyed",
    "sarcastic": "suspicious",
    "suspicious": "suspicious",
    "defiant": "confident",
    "confident": "confident",
    "gleeful": "self_satisfied",
    "manic": "surprised",
    "embarrassed": "embarrassed",
    "surprised": "surprised",
}


def load_rig() -> dict:
    return json.loads((RIGS / "ralph.json").read_text())


def gemini_to_events(gem: dict, duration_ms: int, rig: dict) -> list[dict]:
    """Build performance.v1 events from Gemini segments."""
    exprs = set((rig.get("expressions") or {}).keys())
    gestures = set((rig.get("gestures") or {}).keys())
    hold_ms = int((rig.get("profile") or {}).get("punchline_hold_ms", 1200))

    events = [
        {"t": 0, "kind": "lights", "id": "house_up"},
        {"t": 400, "kind": "enter", "from": "stage_left"},
        {"t": 1200, "kind": "camera", "id": "medium"},
        {"t": 1200, "kind": "speak_start"},
    ]

    for seg in gem.get("segments") or []:
        t0 = int(float(seg.get("t0") or 0) * 1000)
        t1 = int(float(seg.get("t1") or (t0 / 1000 + 5)) * 1000)
        emotion = seg.get("emotion") or "neutral"
        expr = EMOTION_MAP.get(emotion, "deadpan")
        if expr not in exprs:
            expr = "deadpan"

        # expression at segment start
        events.append({"t": t0, "kind": "expression", "id": expr,
                       "source_emotion": emotion,
                       "intensity": seg.get("emotion_intensity")})

        body = seg.get("body") or {}
        comedy = seg.get("comedy") or {}
        vocal = seg.get("vocal") or {}
        btype = comedy.get("beat_type") or "setup"

        # gestures from body
        if body.get("lean") == "forward" and "lean_forward" in gestures:
            events.append({"t": t0 + 200, "kind": "gesture", "id": "lean_forward",
                           "intensity": min(1.0, float(body.get("lean_amount") or 0.3) * 2)})
        if body.get("arms") in ("open", "gesture_out") and "small_shrug" in gestures:
            events.append({"t": t0 + 400, "kind": "gesture", "id": "small_shrug",
                           "intensity": 0.5})
        if body.get("head") in ("jut", "tilt_left", "tilt_right") and "head_tilt" in gestures:
            events.append({"t": t0 + 300, "kind": "gesture", "id": "head_tilt",
                           "intensity": 0.6})

        # punchline: hold + eye glitch
        if btype == "punchline":
            events.append({"t": t1, "kind": "hold", "ms": hold_ms,
                           "note": "punchline stillness"})
            if "eye_glitch" in gestures:
                events.append({"t": t1 + 400, "kind": "gesture", "id": "eye_glitch",
                               "intensity": 1.0})
            events.append({"t": t1 + 800, "kind": "camera", "id": "closeup"})
            events.append({"t": t1 + hold_ms + 600, "kind": "camera", "id": "medium"})
        elif btype == "closer":
            if "warm_rock_lean" in gestures:
                events.append({"t": max(0, t0 - 500), "kind": "gesture",
                               "id": "warm_rock_lean", "intensity": 0.8})
            events.append({"t": t0, "kind": "camera", "id": "pushin"})
        elif btype == "tag":
            if "suit_adjust" in gestures:
                events.append({"t": t0 + 200, "kind": "gesture", "id": "suit_adjust",
                               "intensity": 0.5})

        # high energy → subtle camera
        if float(vocal.get("energy") or 0) > 0.85 and btype not in ("punchline", "closer"):
            events.append({"t": t0 + 100, "kind": "camera", "id": "medium"})

    events.append({"t": max(0, duration_ms - 400), "kind": "camera", "id": "wide"})
    events.append({"t": duration_ms, "kind": "exit", "to": "stage_left"})
    events.sort(key=lambda e: (e["t"], e.get("kind") or ""))
    return events


PUPPET_SVG = r'''<svg viewBox="0 0 220 300" style="background:transparent">
<defs><linearGradient id="spot" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#ffdf9e" stop-opacity=".28"/><stop offset="1" stop-color="#ffdf9e" stop-opacity="0"/></linearGradient></defs>
<rect x="0" y="0" width="26" height="300" fill="#5b1414"/><rect x="194" y="0" width="26" height="300" fill="#5b1414"/>
<rect x="22" y="0" width="6" height="300" fill="#3d0d0d"/><rect x="192" y="0" width="6" height="300" fill="#3d0d0d"/>
<polygon points="70,0 150,0 190,300 30,300" fill="url(#spot)"/>
<rect x="0" y="252" width="220" height="48" fill="#151020"/>
<ellipse cx="110" cy="278" rx="60" ry="10" fill="#000" opacity=".5"/>
<text class="CAMT" x="30" y="18" fill="#999" font-size="12">medium</text>
<g class="PB"><rect class="SUIT" x="60" y="170" width="100" height="100" rx="14" fill="#2b3440"/><rect x="100" y="170" width="20" height="100" fill="#e8e4d8"/><polygon points="110,185 118,205 110,235 102,205" fill="#7c1f1f"/></g>
<g class="PH"><ellipse class="SKIN" cx="110" cy="120" rx="52" ry="58" fill="#6b8f5e"/><ellipse cx="110" cy="120" rx="52" ry="58" fill="none" stroke="#2c3a26" stroke-width="3"/>
<rect class="BL" x="70" y="82" width="30" height="7" rx="3" fill="#2c3a26"/><rect class="BR" x="120" y="82" width="30" height="7" rx="3" fill="#2c3a26"/>
<ellipse cx="85" cy="112" rx="14" ry="16" fill="#f4f1e4"/><ellipse class="PL" cx="85" cy="113" rx="5" ry="9" fill="#111"/>
<ellipse cx="135" cy="112" rx="14" ry="16" fill="#f4f1e4"/><ellipse class="PR" cx="135" cy="113" rx="5" ry="9" fill="#111"/>
<ellipse class="MO" cx="110" cy="160" rx="16" ry="5" fill="#1a0f0f"/></g>
<g class="MIC"><rect x="107" y="205" width="6" height="75" rx="3" fill="#0c0c0c"/><ellipse cx="110" cy="282" rx="16" ry="4" fill="#0c0c0c"/><circle cx="110" cy="196" r="13" fill="#1f2937"/><circle cx="110" cy="196" r="13" fill="none" stroke="#4b5563" stroke-width="2"/></g>
<text class="EX" x="110" y="294" text-anchor="middle" fill="#facc15" font-size="14">deadpan</text></svg>'''


def make_player_html(gem: dict, events: list[dict], title: str, duration_ms: int,
                     video_url: str | None = None) -> str:
    """Standalone HTML player — timeline plays against Ralph puppet."""
    events_js = json.dumps(events)
    gem_js = json.dumps({
        "segments": [
            {"t0": s.get("t0"), "t1": s.get("t1"),
             "emotion": s.get("emotion"),
             "beat_type": (s.get("comedy") or {}).get("beat_type"),
             "text_hint": (s.get("vocal") or {}).get("note", "")[:80]}
            for s in gem.get("segments") or []
        ],
        "anger": gem.get("anger_analysis") or {},
        "overall": gem.get("overall") or {},
    })
    return f'''<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Ralph Stage Lab</title>
<style>
html,body{{margin:0;height:100%;background:#000;color:#eee;font-family:system-ui,sans-serif}}
#wrap{{display:flex;flex-direction:column;height:100vh}}
#stagebox{{flex:1;display:flex;align-items:center;justify-content:center;position:relative;overflow:hidden;
background:radial-gradient(circle at 50% 30%,#2b2010,#000 72%)}}
#stagebox svg{{width:min(70vh,90vw);max-height:90vh}}
#hud{{position:absolute;top:10px;left:12px;font-size:12px;color:#aaa;z-index:2}}
#seg{{position:absolute;top:10px;right:12px;font-size:12px;color:#facc15;text-align:right;max-width:45%}}
#emotion{{position:absolute;bottom:12px;left:12px;font-size:14px;color:#facc15}}
#beat{{position:absolute;bottom:12px;right:12px;font-size:12px;color:#888}}
#bar{{height:4px;background:#333;position:relative}}
#barfill{{height:100%;background:#facc15;width:0%}}
#ctrl{{padding:8px 12px;display:flex;gap:10px;align-items:center;background:#111}}
#ctrl button{{background:#222;color:#eee;border:1px solid #555;padding:6px 14px;border-radius:6px;cursor:pointer;font-size:14px}}
#ctrl button:hover{{background:#333}}
#ctrl input[type=range]{{flex:1}}
#meta{{font-size:11px;color:#666;padding:0 12px 8px}}
#anger{{color:#f87171;font-size:12px;padding:4px 12px;display:none}}
</style></head><body>
<div id="wrap">
<div id="stagebox">
<div id="hud">Stage Lab · Ralph</div>
<div id="seg"></div>
{PUPPET_SVG}
<div id="emotion">—</div>
<div id="beat">—</div>
</div>
<div id="bar"><div id="barfill"></div></div>
<div id="ctrl">
<button id="play">▶ Play</button>
<input type="range" id="scrub" min="0" max="{duration_ms}" value="0">
<span id="clock" style="font-size:12px;color:#aaa;min-width:70px">0:00 / {duration_ms//1000//60}:{duration_ms//1000%60:02d}</span>
</div>
<div id="anger"></div>
<div id="meta">{title} · {len(events)} events · {len((gem.get('segments') or []))} segments</div>
</div>
<script>
const EVENTS={events_js};
const GEM={gem_js};
const DUR={duration_ms};
let playing=false, t0=0, tpos=0, raf=null;

const q=s=>document.querySelector(s);
function apply(ev){{
  const kind=ev.kind, id=ev.id||'';
  if(kind==='expression'){{
    q('.EX').textContent=id;
    const mad=id==='annoyed';
    q('.BL').setAttribute('transform',mad?'rotate(-12 85 85)':'');
    q('.BR').setAttribute('transform',mad?'rotate(12 135 85)':'');
    const mo=q('.MO');
    if(id==='surprised'){{mo.setAttribute('ry','10');mo.setAttribute('cy','158');}}
    else if(id==='deadpan'){{mo.setAttribute('ry','4');mo.setAttribute('cy','160');}}
    else{{mo.setAttribute('ry','5');mo.setAttribute('cy','160');}}
  }}
  else if(kind==='camera'){{
    const t=q('.CAMT'); if(t)t.textContent=id;
    const sc={{wide:.85,medium:1,closeup:1.35,pushin:1.2}}[id]||1;
    q('.PH').setAttribute('transform',`translate(110 120) scale(${{sc}}) translate(-110 -120)`);
  }}
  else if(kind==='gesture'){{
    if(id==='eye_glitch'){{
      ['.PL','.PR'].forEach(s=>{{q(s).setAttribute('rx','2');q(s).setAttribute('fill','#b91c1c');}});
      q('.EX').textContent='SLIT.';
      setTimeout(()=>['.PL','.PR'].forEach(s=>{{q(s).setAttribute('rx','5');q(s).setAttribute('fill','#111');}}),900);
    }}
    if(id==='suit_adjust'){{
      q('.PB').setAttribute('transform','translate(-6 0)');
      setTimeout(()=>q('.PB').setAttribute('transform','translate(6 0)'),250);
      setTimeout(()=>q('.PB').setAttribute('transform',''),600);
    }}
    if(id==='warm_rock_lean'){{
      q('.PH').setAttribute('transform','translate(0 20)');
      setTimeout(()=>q('.PH').setAttribute('transform',''),1400);
    }}
    if(id==='head_tilt'){{
      q('.PH').setAttribute('transform','rotate(8 110 120)');
      setTimeout(()=>q('.PH').setAttribute('transform',''),700);
    }}
    if(id==='lean_forward'){{
      q('.PH').setAttribute('transform','translate(0 14)');
      setTimeout(()=>q('.PH').setAttribute('transform',''),900);
    }}
    if(id==='small_shrug'){{
      q('.PB').setAttribute('transform','translate(0 -8)');
      setTimeout(()=>q('.PB').setAttribute('transform',''),650);
    }}
  }}
  else if(kind==='hold'){{
    q('.EX').textContent='…';
  }}
  else if(kind==='speak_start'){{
    /* vocal info from segment */
  }}
}}

function segAt(ms){{
  return (GEM.segments||[]).find(s=>ms>=s.t0*1000 && ms<s.t1*1000);
}}

function tick(){{
  if(!playing)return;
  tpos = performance.now()-t0;
  if(tpos>=DUR){{tpos=DUR;stop();}}
  q('#barfill').style.width=(tpos/DUR*100)+'%';
  q('#scrub').value=tpos;
  const secs=Math.floor(tpos/1000);
  q('#clock').textContent=`${{Math.floor(secs/60)}}:${{String(secs%60).padStart(2,'0')}} / ${{Math.floor(DUR/60000)}}:${{String(Math.floor(DUR/1000)%60).padStart(2,'0')}}`;
  // fire events whose t <= tpos
  for(const ev of EVENTS){{
    if(ev._f)continue;
    if(ev.t<=tpos){{ev._f=1;apply(ev);}}
  }}
  // current segment HUD
  const seg=segAt(tpos);
  if(seg){{
    q('#emotion').textContent=seg.emotion||'—';
    q('#beat').textContent=seg.beat_type||'—';
    q('#seg').textContent=(seg.text_hint||'').slice(0,80);
  }}
  raf=requestAnimationFrame(tick);
}}
function play(){{
  playing=true;
  // reset one-shots
  EVENTS.forEach(e=>e._f=0);
  t0=performance.now()-tpos;
  q('#play').textContent='⏸ Pause';
  raf=requestAnimationFrame(tick);
}}
function stop(){{
  playing=false;cancelAnimationFrame(raf);
  q('#play').textContent='▶ Play';
}}
q('#play').onclick=()=>playing?stop():play();
q('#scrub').oninput=e=>{{
  tpos=+e.target.value;
  // reapply state up to tpos
  EVENTS.forEach(e=>e._f=0);
  for(const ev of EVENTS){{if(ev.t<=tpos){{ev._f=1;apply(ev);}}}}
  q('#barfill').style.width=(tpos/DUR*100)+'%';
}};
// anger banner
const ang=GEM.anger||{{}};
if(ang.present){{
  const el=q('#anger');
  el.style.display='block';
  el.textContent=`anger: ${{ang.type}} — ${{(ang.body_signature||[]).join('; ')}}`;
}}
</script></body></html>'''


def main():
    gem_path = Path(sys.argv[1]) if len(sys.argv) > 1 else \
        OUT / "kt704_ari_passport_gemini.gemini.json"
    if not gem_path.exists():
        print(f"missing {gem_path}")
        sys.exit(1)
    stem = gem_path.name.replace(".gemini.json", "")
    gem = json.loads(gem_path.read_text())
    rig = load_rig()
    duration_ms = int(float((gem.get("segments") or [{}])[-1].get("t1") or 60) * 1000)
    events = gemini_to_events(gem, duration_ms, rig)
    # write timeline
    tl = {"schema": "performance.v1", "source": stem,
          "method": "gemini→ralph_rig", "audio_duration_ms": duration_ms,
          "events": events, "n_events": len(events)}
    tl_path = OUT / f"{stem}.stage_timeline.json"
    tl_path.write_text(json.dumps(tl, indent=2))
    print(f"timeline: {tl_path.name} ({len(events)} events, {duration_ms}ms)")
    # write player
    title = stem.replace("_", " ").title()
    html = make_player_html(gem, events, title, duration_ms)
    html_path = OUT / f"{stem}_player.html"
    html_path.write_text(html)
    print(f"player:   {html_path}")
    print(f"open:     file://{html_path}")


if __name__ == "__main__":
    main()
