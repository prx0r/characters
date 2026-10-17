# P0: Granular A/B Testing — How a Joke Lands

**The endgame metric is "how a joke lands."** It depends on:
- **Audience state** (heat, momentum, valence — the "killed" physics)
- **The joke itself** (mechanism, incongruity, resolvable prediction error)
- **Delivery** (timing, pace, energy, pauses)
- **Character profile** (who's telling it, their persona)

## The Core Insight

The audience is a **state machine**. Like Guitar Hero combo:
- Once "killed" (heat > 0.7), easier to stay killed
- Laughs reduce resistance, bombs increase it
- Crowd remembers — recovery is faster after prior heat

**Granular A/B testing:** Same joke + different delivery/room state = different landing.

## Theoretical Foundation (Verified)

### Free Energy Principle × Comedy
From *A Complexity Science Account of Humor* (PMC9955919):
- Setup establishes attractor V0 (audience expectation)
- Punchline forces phase transition to V1 (new interpretation)
- **Resolvable incongruity (V0 - V1) predicts funniness**
- Faster resolution = funnier
- Free energy released during transition = laughter

The audience maintains a **generative model** of what's coming based on:
- Character profile (who is this comedian?)
- Prior material (what have they said so far?)
- Crowd state (how hot are we?)

When the punchline violates that prediction → prediction error → free energy → laughter.

### Audience Contagion (SIR Model)
From *Dynamics of Audience Applause* (PMC4043176):
- SIR model: Susceptible → Infected (laughing) → Recovered
- Contagion rate proportional to number already laughing
- Linear contagion (not quadratic)
- Individual variation in start/stop thresholds

### Provine's Contagion
- Laughter itself evokes laughter (laughter-specific auditory detector)
- 30x more laughter in social settings
- Social context > joke content for raw laughter frequency

## What We're Building

### P0: Validated Laugh Track + Ensemble
1. Multiple competing models (ensemble) for laugh prediction
2. Each model trained on different features/datasets
3. Validate against real laugh events (AM specials + hand-labeled)
4. Output: calibrated P(laugh) per beat with uncertainty

### P1: Granular Payload Review
After each set, output:
- Per-beat: P(laugh), predicted type, actual (if known)
- Crowd state timeline: heat, momentum, valence
- Mechanism breakdown: what worked, what didn't
- Delivery analysis: timing, pace, energy

### P2: A/B Testing Framework
**Same joke + different conditions = different landing:**
- Warm room (heat=0.8) vs cold room (heat=0.0)
- Louis formula (2.1s pause) vs rushed (0.5s pause)
- Character A vs Character B telling the same joke

### P3: Predictive Processing Engine
Audience maintains expectations. Model updates:
- Prior: character profile + crowd state + prior material
- Likelihood: joke mechanism + delivery
- Posterior: P(laugh | joke, delivery, audience state)

## Test Data: Louis CK Bits

Use Louis CK specials for validation:
- 13 decomposed clips with technique labels
- Measured delivery: 1.67s pauses, 163 wpm, 19.6 dB dynamics
- Word-level timing from scribe
- AM laugh events from specials

## Key Files

| File | What |
|---|---|
| `audition/crowd_state.py` | Audience state machine (heat/momentum/valence) |
| `audition/delivery_engine.py` | Set → directed Fish TTS |
| `audition/delivery_laugh.py` | Delivery-aware laugh prediction |
| `audition/realtime_laughter.py` | Realtime audio → laugh events |
| `audition/laugh_api.py` | Standalone API |
| `theory/LOUIS-FORMULA.md` | Measured Louis delivery |
| `theory/datasets/` | prosody200, ali-wong, smile, standup4ai |
| `/home/box/comedy-audio/am_events/` | 5 specials with laugh events |
