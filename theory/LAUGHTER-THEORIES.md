# Unified Theories of Laughter — reference + operational mapping

*All frameworks in one place, mapped to computable features we extract.*
*Every theory → what it predicts → which feature tests it.*

## The three classical theories (incongruity, superiority, relief)

These aren't competing — they're layers of the same phenomenon.

### Incongruity (Kant, Schopenhauer, Morreall, Attardo)
Laughter arises when perception violates expectation. Setup builds a frame;
punchline forces re-framing. Morreall: humor = pleasant psychological shift
from incongruity to resolution.

**Computable as:**
- `punchline_surprisal`: -log P(punchline | setup) from any LM (ACL 2021)
- `setup_uncertainty`: LM entropy while generating setup (multiple readings?)
- `semantic_distance`: 1 - cosine(setup_embed, punchline_embed)
- `garden_path_score`: does the setup build one reading then force another?

**Our Jev nouls that capture this:** garden_path, displacement, escalation

### Superiority (Hobbes, Plato, Gruner)
Laughter at others' misfortune — their loss is our gain. Schadenfreude
requires perceived safety (we're not the target).

**Computable as:**
- `status_delta`: status_before - status_after for the target
- `target_is_performer`: is the comedian laughing at self or others?
- `benign_distance`: is the misfortune distant enough to feel safe?

**Our Jev nouls:** status_reversal, identity_contradiction, expose_self_blindness

### Relief/Release (Freud, Spencer, Bergson)
Laughter discharges nervous energy. Bergson: "the mechanical encrusted on
the living" — rigid systems colliding with organic life. Freud: joke as
pressure valve for repressed impulse.

**Computable as:**
- `tension_buildup`: speech_rate decrease + pause increase before punchline
- `release_energy`: laugh magnitude after punchline
- `rigidity_collision`: rule-following after reality made it absurd (our rigidify operator)

**Our Jev nouls:** rigidity, benign_violation (the "safe discharge" version)

## Predictive processing / free energy (the modern synthesis)

The dpv framework (2026, 828 Chinese stand-up sets) unifies the classical
theories under predictive processing:

**Core claim:** humor arises from COORDINATED violations of temporal AND
semantic predictions. The setup establishes BOTH:
- Temporal expectations: regular pause rhythm (~0.6s), speech rate
- Semantic expectations: topic frame, word associations, narrative trajectory

The punchline violates BOTH simultaneously:
- Extended pause (1.5s) disrupts established rhythm
- Semantically distant content deviates from contextual predictions

This creates "efficient prediction error resolution" — the brain resolves
the double violation quickly and the resolution itself is pleasurable.

**Key empirical findings:**
1. Temporal features OUTWEIGHT semantic features in predicting appreciation
2. Pauses systematically lengthen before high-surprise punchlines
3. Successful performers escalate unpredictability over time (distance_shift r=0.09, p<0.01)
4. Rushed pacing undermines comedic impact (insufficient prediction window)

**Computable as:**
- `setup_rhythm`: mean pause in setup (baseline ~0.6s)
- `pause_escalation`: do pauses lengthen toward punchline?
- `pre_punchline_pause`: pause in [punchline-2s, punchline)
- `pause_variability`: std of pauses (deviation from rhythm)
- `distance_shift`: slope of semantic distance over time
- `speech_rate`: syllables/sec (slower = more prediction window)

## Valence / arousal (Russell circumplex, Mehrabian)

Every emotional state maps to valence (unpleasant→pleasant) and arousal
(calm→excited). Laughter spans the space:
- Roaring laugh: high arousal, positive valence
- Nervous titter: high arousal, negative valence
- Warm chuckle: low arousal, positive valence
- Mocking laugh: high arousal, negative valence (target-directed)

**SMILE findings:** happy laughter vs mocking laughter differ acoustically:
- Mocking: higher F0, higher center of gravity, higher peak frequencies
- Happy: lower F0, broader spectral distribution

**Computable as:**
- `valence`: from laugh type + target (self vs other)
- `arousal`: from laugh intensity + F0 of laughter
- `valence_shift`: does the set move from negative to positive setup→punchline?

**Our emotion labels (kt_emotion.py):** already capture valence/arousal
per set: valence score (hostile→loving), arousal score (lethargic→manic)

## Rasa theory (Abhinavagupta, 10th-11th c. Kashmir)

The aesthetic framework. Nine rasas (flavors/emotional essences):
1. Shringara (love/beauty)
2. Hasya (humor/laughter) ← our target
3. Karuna (compassion)
4. Raudra (anger/fury)
5. Veera (heroism)
6. Bhayanaka (terror)
7. Bibhatsa (disgust)
8. Adbhuta (wonder)
9. Shanta (peace)

Hasya (humor) has two sub-types:
- **Audhasmya** (spontaneous, involuntary laughter) — sudden, surprise-based
- **Ragasya** (deliberate, cultivated humor) — structured, narrative-based

The rasa theory predicts: humor requires **distance** (the aesthetic frame
"this is表演, not real") AND **rasa-samkar** (blending of flavors — hasya
mixed with bhayanaka = dark comedy, hasya with shringara = romantic comedy).

**Computable as:**
- `rasa_blend`: which other emotions co-occur with hasya in this set?
  (our emotion labels + mechanism tags capture this)
- `aesthetic_distance`: is the frame clearly performative? (comedy club vs
  real conflict)
- `spontaneous_vs_cultivated`: sudden surprise (audhasmya) vs structured
  buildup (ragasya) — maps to garden_path vs escalation

## Provine's laughter research (2000, 1992)

Laughter is 30x more likely in social contexts than alone. It's a social
signal, not a cognitive response to incongruity per se.

**Key findings:**
- Contagion: laughter begets laughter (AUROC 0.643 in TIC-TALK)
- 0.2s reaction lag (Provine's "click response")
- "Ha ha" is not random — it's rhythmic, syllabic, 5Hz oscillation
- Laughter高峰期 in conversation follows turn-taking (speaker change)

**Computable as:**
- `contagion_lift`: p(laugh_t | laugh_history) / p(laugh_t | no_history)
- `reaction_lag`: time from punchline to laugh onset (~0.2s baseline)
- `laugh_rhythm`: syllable rate of laughter itself (~5Hz)
- `turn_alignment`: does laugh onset align with speaker change?

## Semantic Script Theory (Raskin) / GTVH (Attardo & Raskin)

Humor requires two overlapping scripts with opposite meanings on the
"script opposition" axis. The joke triggers the shift from Script1 to
Script 2. GTVH formalizes this with six knowledge resources:
1. Script opposition (SOP)
2. Logical mechanism (LM)
3. Situation (SI)
4. Narrative strategy (NA)
5. Target (TA)
6. Language (LI)

**Computable as:**
- `script_opposition`: semantic distance between the two readings
- `logical_mechanism`: our Jev operator (rigidify, status_invert, etc.)
- `target_present`: is there a clear target? (self vs other vs abstract)

**Our GTVH implementation:** audition/gtvh.py already encodes this

## Internal comedy theory (from our repo)

### Jev mechanism nouls (10 categories, 276 sets tagged)
- rigidity: rule-following after reality made it absurd
- status_reversal: powerful diminished, control inverted
- displacement: taboo answered sideways through bland language
- identity_contradiction: claimed self conflicts with shown self
- self_awareness: knowingly exploiting own absurdity
- specificity: concrete details carry the joke
- escalation: stepwise build to something bigger
- garden_path: setup builds one reading, forces re-reading
- benign_violation: wrong/taboo made safe enough to laugh at
- audience_alliance: audience let in on what someone lacks

### Comedy operators (from kt_decode, learned priors)
- rigidify: apply rule mechanically after reality broke it
- repeat_variation: same structure, escalating instances
- status_invert: flip who controls whom
- identity_contradict: expose gap between claim and reality
- expose_self_blindness: show what the character can't see
- unmask: reveal the hidden truth
- literalize: take figurative language literally
- double_interpret: force re-reading with new frame

### Sincerity doctrine (our invention)
Characters never know it's comedy. The wink veto: no character can break
the fourth wall. This creates the aesthetic distance rasa theory requires —
the audience knows it's表演, the character doesn't.

### Misinterpretation rule (our invention)
The one-sentence engine: what does criticism turn into in this character's
hands? Ralph: workflow tickets. Kyle: cucumber debts. This is the
character-specific rigidity mechanism — their blind spot transforms
criticism into comedy.

## How the theories compose (the unified model)

```
SETUP (dpv temporal + semantic baseline)
  ↓ establishes rhythm + expectations
PUNCHLINE (coordinated violation)
  ↓ double violation: temporal + semantic
RESOLUTION (prediction error discharged)
  ↓ free energy minimization
LAUGHTER (social signal + affective response)
  ↓ contagion spreads through crowd
CROWD STATE (heat increases, lowers threshold for next laugh)
  ↓ Provine loop
NEXT JOKE (escalating unpredictability, dpv distance_shift)
```

Each theory captures a different layer:
- Incongruity: the semantic violation (what the punchline does)
- Superiority: the social direction (who laughs at whom)
- Relief: the affective discharge (why it feels good)
- Predictive processing: the temporal mechanism (when and how)
- Rasa: the aesthetic frame (why distance enables humor)
- Provine: the social dynamics (how laughter spreads)
- GTVH: the formal structure (how scripts overlap)
- Our nouls: the operational taxonomy (what mechanism fired)

## Operational summary: feature → theory → prediction

| Feature | Theory | Prediction |
|---|---|---|
| punchline_surprisal | Incongruity | Higher = bigger laugh |
| setup_uncertainty | Incongruity | Higher = bigger laugh (more readings to resolve) |
| pre_punchline_pause | Predictive processing | Longer = bigger laugh (prediction window) |
| pause_variability | Predictive processing | Lower baseline + sudden spike = bigger laugh |
| distance_shift | Predictive processing | Rising = bigger laugh (escalation) |
| status_delta | Superiority | Bigger flip = bigger laugh (if safe) |
| tension_buildup | Relief | Longer buildup = bigger release |
| kinetic_energy_dip | TIC-TALK | Deeper stillness = bigger laugh |
| laugh_history | Provine | Recent laughs = higher probability (contagion) |
| valence | Valence/arousal | Positive = warmer laugh; negative = sharper |
| mechanism_noul | Our taxonomy | garden_path → explosive; benign_violation → wheeze |
| target_self | Superiority/self | Self-deprecation = safer, warmer |

## Sources

- dpv framework: arXiv 2605.00143 (2026)
- TIC-TALK: arXiv 2603.21803 / CHum 2026
- Uncertainty & Surprisal: ACL 2021 (Xie et al.)
- SMILE: NAACL 2024 (Hyun et al.)
- StandUp4AI: EMNLP 2025 Findings (Barriere et al.)
- "So You Think You're Funny": EMNLP 2021
- Provine 1992, 2000: laughter contagion research
- Raskin 1985: Semantic Script Theory of Humor
- Attardo & Raskin 1991: General Theory of Verbal Humor
- Abhinavagupta ~1000 CE: Dhvanyaloka commentary (rasa theory)
- Bergson 1900: Laughter (mechanical encrusted on living)
- Freud 1905: Jokes and Their Relation to the Unconscious
- Morreall 1983: Taking Laughter Seriously
- McGraw & Warren 2010: Benign Violation Theory
- Our repo: kt_decode.py, kt_jev_annotate.py, gtvh.py, killtony-priors.json
