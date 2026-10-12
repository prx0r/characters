"""Casey Rocket character player — maps Gemini emotions + blendshapes to animated SVG.

Character design: kinetic receiver with scanning eyes, subtle smirk, raised brows.
Different from Ralph — Casey is perception-heavy, not expression-heavy.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
OUT = HERE / "killtony-minutes"

# Casey-specific SVG — wiry kinetic figure with big scanning eyes
CASEY_SVG = r'''<svg viewBox="0 0 220 300" style="background:transparent">
<defs>
  <linearGradient id="spot" x1="0" y1="0" x2="0" y2="1">
    <stop offset="0" stop-color="#ffdf9e" stop-opacity=".25"/>
    <stop offset="1" stop-color="#ffdf9e" stop-opacity="0"/>
  </linearGradient>
  <radialGradient id="eye_glow" cx="50%" cy="50%" r="50%">
    <stop offset="0%" stop-color="#88ccff" stop-opacity=".15"/>
    <stop offset="100%" stop-color="#88ccff" stop-opacity="0"/>
  </radialGradient>
</defs>
<!-- stage -->
<rect x="0" y="0" width="22" height="300" fill="#1a1a2e"/>
<rect x="198" y="0" width="22" height="300" fill="#1a1a2e"/>
<polygon points="70,0 150,0 190,300 30,300" fill="url(#spot)"/>
<rect x="0" y="252" width="220" height="48" fill="#0f0f1a"/>
<ellipse cx="110" cy="278" rx="55" ry="8" fill="#000" opacity=".5"/>
<text class="CAMT" x="30" y="18" fill="#666" font-size="11" font-family="monospace">medium</text>

<!-- body — wiry, kinetic -->
<g class="PB">
  <rect class="SUIT" x="72" y="165" width="76" height="95" rx="8" fill="#2d2d3a"/>
  <rect x="105" y="165" width="10" height="95" fill="#4a4a5a"/>
  <!-- nervous energy lines -->
  <line class="ENERGY1" x1="78" y1="180" x2="82" y2="185" stroke="#555" stroke-width="1" opacity=".5"/>
  <line class="ENERGY2" x1="140" y1="200" x2="144" y2="205" stroke="#555" stroke-width="1" opacity=".5"/>
</g>

<!-- head — slightly too big, kinetic -->
<g class="PH">
  <ellipse class="SKIN" cx="110" cy="115" rx="48" ry="54" fill="#d4a574"/>
  <ellipse cx="110" cy="115" rx="48" ry="54" fill="none" stroke="#a07850" stroke-width="2"/>

  <!-- brows — raised by default (receiving) -->
  <rect class="BL" x="72" y="74" width="32" height="6" rx="3" fill="#6b4226" transform="rotate(-8 88 77)"/>
  <rect class="BR" x="118" y="74" width="32" height="6" rx="3" fill="#6b4226" transform="rotate(8 134 77)"/>

  <!-- eyes — LARGE scanning eyes -->
  <ellipse cx="88" cy="108" rx="16" ry="18" fill="#f5f0e8"/>
  <ellipse cx="132" cy="108" rx="16" ry="18" fill="#f5f0e8"/>
  <!-- iris — moves with eyeLook -->
  <circle class="PL" cx="88" cy="110" r="7" fill="#2a5f8f"/>
  <circle class="PR" cx="132" cy="110" r="7" fill="#2a5f8f"/>
  <!-- pupil -->
  <circle class="PUP_L" cx="88" cy="110" r="3.5" fill="#0a0a0a"/>
  <circle class="PUP_R" cx="132" cy="110" r="3.5" fill="#0a0a0a"/>
  <!-- eye glow (receiving signal) -->
  <ellipse cx="88" cy="108" rx="22" ry="24" fill="url(#eye_glow)" class="EYE_GLOW_L" opacity="0"/>
  <ellipse cx="132" cy="108" rx="22" ry="24" fill="url(#eye_glow)" class="EYE_GLOW_R" opacity="0"/>

  <!-- mouth — subtle, not exaggerated -->
  <ellipse class="MO" cx="110" cy="155" rx="14" ry="4" fill="#8b4513"/>
</g>

<!-- mic -->
<g class="MIC">
  <rect x="107" y="200" width="6" height="70" rx="3" fill="#333"/>
  <ellipse cx="110" cy="272" rx="14" ry="4" fill="#222"/>
  <circle cx="110" cy="192" r="11" fill="#1a1a1a"/>
  <circle cx="110" cy="192" r="11" fill="none" stroke="#444" stroke-width="1.5"/>
</g>

<!-- status text -->
<text class="EX" x="110" y="292" text-anchor="middle" fill="#facc15" font-size="13" font-family="monospace">receiving</text>
</svg>'''

# Emotion → facial expression mapping (Casey-specific)
EMOTION_FACES = {
    "gleeful":    {"brow": "raised", "mouth_ry": 5, "mouth_cy": 155, "eye_rx": 7, "glow": 0.3},
    "manic":      {"brow": "raised", "mouth_ry": 8, "mouth_cy": 153, "eye_rx": 8, "glow": 0.7},
    "deadpan":    {"brow": "neutral", "mouth_ry": 3, "mouth_cy": 156, "eye_rx": 6, "glow": 0},
    "sarcastic":  {"brow": "one_raised", "mouth_ry": 4, "mouth_cy": 155, "eye_rx": 5, "glow": 0.1},
    "surprised":  {"brow": "raised", "mouth_ry": 10, "mouth_cy": 152, "eye_rx": 9, "glow": 0.5},
}

# Blendshape → micro-expression mapping
def blendshape_to_svg(bs: dict) -> dict:
    """Map ARKit blendshapes to SVG parameters."""
    return {
        "brow_left_rot": -8 - (bs.get("browInnerUp", 0) * 15),  # raised = more rotation
        "brow_right_rot": 8 + (bs.get("browInnerUp", 0) * 15),
        "brow_furrow": bs.get("browDownLeft", 0) + bs.get("browDownRight", 0),
        "eye_squint_l": bs.get("eyeSquintLeft", 0),
        "eye_squint_r": bs.get("eyeSquintRight", 0),
        "eye_open_l": 1 - bs.get("eyeBlinkLeft", 0),
        "eye_open_r": 1 - bs.get("eyeBlinkRight", 0),
        "mouth_open": bs.get("jawOpen", 0),
        "mouth_wide": bs.get("mouthSmileLeft", 0) + bs.get("mouthSmileRight", 0),
        "mouth_pucker": bs.get("mouthPucker", 0),
        "eye_look_x": bs.get("eyeLookInRight", 0) - bs.get("eyeLookOutLeft", 0),
        "eye_look_y": bs.get("eyeLookDownLeft", 0) - bs.get("eyeLookUpLeft", 0),
    }


def make_casey_player(gem: dict, events: list, visemes: list, title: str, duration_ms: int) -> str:
    events_js = json.dumps(events)
    vis_js = json.dumps(visemes or [])
    gem_js = json.dumps({
        "segments": [
            {"t0": s.get("t0"), "t1": s.get("t1"),
             "emotion": s.get("emotion"),
             "face": (s.get("body") or {}).get("face"),
             "brow": (s.get("body") or {}).get("brow"),
             "beat_type": (s.get("comedy") or {}).get("beat_type"),
             "vocal_energy": (s.get("vocal") or {}).get("energy")}
            for s in gem.get("segments") or []
        ],
        "anger": gem.get("anger_analysis") or {},
        "overall": gem.get("overall") or {},
    })
    faces_js = json.dumps(EMOTION_FACES)

    return f'''<!doctype html>
<html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title} — Casey Rocket Stage Lab</title>
<style>
*{{margin:0;padding:0;box-sizing:border-box}}
html,body{{height:100%;background:#000;color:#eee;font-family:system-ui,sans-serif;overflow:hidden}}
#wrap{{display:flex;flex-direction:column;height:100vh}}
#stagebox{{flex:1;display:flex;align-items:center;justify-content:center;position:relative;
  background:radial-gradient(ellipse at 50% 40%,#1a1520 0%,#000 70%)}}
#stagebox svg{{width:min(70vh,85vw);max-height:90vh}}
#hud{{position:absolute;top:10px;left:12px;font-size:11px;color:#888;font-family:monospace}}
#seg{{position:absolute;top:10px;right:12px;font-size:11px;color:#facc15;text-align:right;max-width:50%}}
#emotion{{position:absolute;bottom:14px;left:14px;font-size:16px;color:#facc15;font-weight:bold}}
#beat{{position:absolute;bottom:14px;right:14px;font-size:12px;color:#888}}
#bar{{height:3px;background:#222}}
#barfill{{height:100%;background:#facc15;width:0%}}
#ctrl{{padding:6px 12px;display:flex;gap:10px;align-items:center;background:#0a0a0a}}
#ctrl button{{background:#1a1a1a;color:#eee;border:1px solid #444;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:13px}}
#ctrl input[type=range]{{flex:1}}
#meta{{font-size:10px;color:#555;padding:2px 12px 4px}}
#anger{{color:#f87171;font-size:11px;padding:2px 12px;display:none}}
</style></head><body>
<div id="wrap">
<div id="stagebox">
<div id="hud">CASEY ROCKET · receiving</div>
<div id="seg"></div>
{CASEY_SVG}
<div id="emotion">receiving…</div>
<div id="beat">—</div>
</div>
<div id="bar"><div id="barfill"></div></div>
<div id="ctrl">
<button id="play">▶</button>
<input type="range" id="scrub" min="0" max="{duration_ms}" value="0">
<span id="clock" style="font-size:11px;color:#888">0:00</span>
</div>
<div id="anger"></div>
<div id="meta">{title} · {len(events)} events · {len((gem.get('segments') or []))} segments</div>
</div>
<script>
const EVENTS={events_js};
const VISEMES={vis_js};
const GEM={gem_js};
const FACES={faces_js};
const DUR={duration_ms};
let playing=false,tpos=0,raf=null,visIdx=0;

const q=s=>document.querySelector(s);

// mouth shapes for visemes
const MOUTH={{closed:[3,14,155],rest:[4,15,155],AI:[10,17,153],E:[7,16,154],
  O:[8,11,154],U:[6,9,155],FV:[3,14,155],L:[6,15,154],MBP:[2,12,155],open:[12,18,152]}};

function applyViseme(ms){{
  if(!VISEMES.length)return;
  let lo=0,hi=VISEMES.length-1,cur=VISEMES[0];
  while(lo<=hi){{const mid=(lo+hi)>>1;if(VISEMES[mid].t<=ms){{cur=VISEMES[mid];lo=mid+1;}}else hi=mid-1;}}
  const p=MOUTH[cur.shape]||MOUTH.rest;
  const mo=q('.MO');if(mo){{mo.setAttribute('ry',p[0]);mo.setAttribute('rx',p[1]);mo.setAttribute('cy',p[2]);}}
}}

function applyEmotion(emotion){{
  const f=FACES[emotion]||FACES.deadpan;
  // brows
  const bl=q('.BL'),br=q('.BR');
  if(bl)bl.setAttribute('transform',`rotate(${{f.brow==='raised'?-14:f.brow==='one_raised'?-14:0}} 88 77)`);
  if(br)br.setAttribute('transform',`rotate(${{f.brow==='raised'?14:8}} 134 77)`);
  // mouth
  const mo=q('.MO');
  if(mo){{mo.setAttribute('ry',f.mouth_ry);mo.setAttribute('cy',f.mouth_cy);}}
  // eye glow (receiving signal intensity)
  const gl=q('.EYE_GLOW_L'),gr=q('.EYE_GLOW_R');
  if(gl)gl.setAttribute('opacity',f.glow);
  if(gr)gr.setAttribute('opacity',f.glow);
  // eye iris size (manic = bigger)
  const pl=q('.PL'),pr=q('.PR');
  if(pl)pl.setAttribute('r',f.eye_rx);
  if(pr)pr.setAttribute('r',f.eye_rx);
  q('.EX').textContent=emotion;
}}

function applyBlendshapes(ms){{
  // sample nearest viseme for micro mouth movement
  if(!VISEMES.length)return;
  let lo=0,hi=VISEMES.length-1,cur=VISEMES[0];
  while(lo<=hi){{const mid=(lo+hi)>>1;if(VISEMES[mid].t<=ms){{cur=VISEMES[mid];lo=mid+1;}}else hi=mid-1;}}
  // eye iris position from time (simulated scan)
  const scan_x=Math.sin(ms/800)*4;
  const scan_y=Math.cos(ms/1200)*3;
  ['.PUP_L','.PUP_R'].forEach(s=>{{
    const el=q(s);if(el){{
      const base=s==='.PUP_L'?88:132;
      el.setAttribute('cx',base+scan_x);
      el.setAttribute('cy',110+scan_y);
    }}
  }});
}}

function apply(ev){{
  const kind=ev.kind,id=ev.id||'';
  if(kind==='expression'){{applyEmotion(id);}}
  else if(kind==='camera'){{
    const t=q('.CAMT');if(t)t.textContent=id;
    const sc={{wide:.85,medium:1,closeup:1.3,pushin:1.15}}[id]||1;
    q('.PH').setAttribute('transform',`translate(110 115) scale(${{sc}}) translate(-110 -115)`);
  }}
  else if(kind==='gesture'){{
    if(id==='lean_forward'){{q('.PH').setAttribute('transform','translate(0 12)');setTimeout(()=>q('.PH').setAttribute('transform',''),800);}}
    if(id==='head_tilt'){{q('.PH').setAttribute('transform','rotate(6 110 115)');setTimeout(()=>q('.PH').setAttribute('transform',''),600);}}
    if(id==='small_shrug'){{q('.PB').setAttribute('transform','translate(0 -6)');setTimeout(()=>q('.PB').setAttribute('transform',''),500);}}
  }}
  else if(kind==='hold'){{q('.EX').textContent='…';}}
}}

function segAt(ms){{
  return (GEM.segments||[]).find(s=>ms>=s.t0*1000&&ms<s.t1*1000);
}}

function tick(){{
  if(!playing)return;
  tpos=performance.now()-tpos;
  if(tpos>=DUR){{tpos=DUR;stop();}}
  q('#barfill').style.width=(tpos/DUR*100)+'%';
  q('#scrub').value=tpos;
  const s=Math.floor(tpos/1000);
  q('#clock').textContent=`${{Math.floor(s/60)}}:${{String(s%60).padStart(2,'0')}}`;
  for(const ev of EVENTS){{if(!ev._f&&ev.t<=tpos){{ev._f=1;apply(ev);}}}}
  applyViseme(tpos);
  applyBlendshapes(tpos);
  const seg=segAt(tpos);
  if(seg){{
    q('#emotion').textContent=seg.emotion||'receiving…';
    q('#beat').textContent=seg.beat_type||'—';
    q('#seg').textContent=(seg.face||'')+(seg.brow?' · '+seg.brow:'');
  }}
  raf=requestAnimationFrame(tick);
}}
function play(){{playing=true;EVENTS.forEach(e=>e._f=0);tpos=performance.now()-tpos;q('#play').textContent='⏸';raf=requestAnimationFrame(tick);}}
function stop(){{playing=false;cancelAnimationFrame(raf);q('#play').textContent='▶';}}
q('#play').onclick=()=>playing?stop():play();
q('#scrub').oninput=e=>{{tpos=+e.target.value;EVENTS.forEach(e=>e._f=0);for(const ev of EVENTS)if(ev.t<=tpos){{ev._f=1;apply(ev);}}applyViseme(tpos);}};
const ang=GEM.anger||{{}};
if(ang.present){{const el=q('#anger');el.style.display='block';el.textContent=`anger: ${{ang.type}}`;}}
</script></body></html>'''


def main():
    stem = sys.argv[1] if len(sys.argv) > 1 else "casey_rocket_2_gemini_video"
    gem_path = OUT / f"{stem}.gemini.json"
    tl_path = OUT / f"{stem}.stage_timeline.json"
    
    gem = json.loads(gem_path.read_text())
    tl = json.loads(tl_path.read_text()) if tl_path.exists() else {"events": []}
    
    # load visemes if they exist
    aud_id = stem.replace("_gemini_video", "").replace("_gemini", "")
    vis_path = Path(f"audition/audio/{aud_id}.visemes.json")
    visemes = json.loads(vis_path.read_text()) if vis_path.exists() else []
    
    duration_ms = int(float((gem.get("segments") or [{}])[-1].get("t1") or 44) * 1000)
    title = stem.replace("_", " ").title()
    
    html = make_casey_player(gem, tl.get("events", []), visemes, title, duration_ms)
    out = OUT / f"{stem}_casey_player.html"
    out.write_text(html)
    print(f"wrote {out}")
    print(f"  events: {len(tl.get('events',[]))}")
    print(f"  visemes: {len(visemes)}")
    print(f"  duration: {duration_ms}ms")
    print(f"  open: file://{out}")


if __name__ == "__main__":
    main()
