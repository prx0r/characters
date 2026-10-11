# Canonical Character Graph v1 — who × what × how

One schema for every comic mind: our inventions (Ralph, Nolan), Kill Tony
personas, and imported outsiders (Theroux, Norm). A laugh is always:

**WHO says it** (graph) × **WHAT mechanism** (theory/operator) × **HOW delivered** (modulator).

## Field map (where each layer lives)

| Layer | Question | Lives in | Example (Ralph) |
|---|---|---|---|
| WHO | stable identity, want/fear, blind spots, policy | this graph | compassionate conqueror who files cruelty as HR |
| WHAT | mechanism applied to a scenario | pogpet `theories.json` + `world_ops.py` | `rigidify` + `displacement` |
| HOW | pace, emphasis, pause, face, voice | freaktown delivery contract + audition takes | deadpan 0.55 energy, 1200ms punch hold |
| EVIDENCE | did it land | audition POGs / KT crowd / room read | pog_times_ms, roaring |

Lore (Clark, Steiner, Keel, Borges in `characters/theory/`) feeds WHO backstory.
It never decides WHAT or HOW. Mechanisms live only in pogpet's 25-theory registry.
Freaktown owns performance. No layer reaches into another's job.

## Schema (extends pogpet Nolan shape; all additions optional except id/name)

Required: `id, name, version, provenance[]`.
WHO: `traits[], humour, dramatic_core{want,fear,need,self_model,blind_spots[]}`,
  `status_model{desired,felt}`, `knowledge{knows,does_not_know}`,
  `perception{notices_first,ignores,watched}`, `action_policy{default_strategy}`,
  `misinterpretation_rule` (the joke-generating rule: what criticism becomes),
  `relationships[], threads[], memories[]` (fictional events only).
WHAT priors: `comedy{operator_priors{}}`, `preferred_theories[]`, `archetype`.
HOW defaults: `voice{cadence,tells[],voice_id}`, `delivery{energy,pace,punchline_hold_ms}`.
Provenance: every imported outsider carries `hypothesis_note` + `sets_observed`
  + `annotator`. Fictional characters carry `canon` (e.g. `reptilian`).

## Import rules (real performers)

1. Stage persona only. No biographical or psychological claims. Ever.
2. No verbatim lines stored. Fingerprints ≤7 words.
3. `blind_spots: ["unknown — …"]` unless ≥3 sets show the same collision.
4. `operator_priors` from observed frequencies, normalized per set.
5. One graph per performer; multi-set evidence strengthens, never concludes.

## Seeds vs instances (v1.1)

Two layers. Never one.

**Seed** = the general philosophy. Scenario-free. Orientation axes (what the
character believes the world IS), problem space (what situations count as
theirs), valid modulator ranges (which moods they can inhabit without
breaking). A seed generates no jokes. It defines the room jokes happen in.

**Instance** = a locked config: seed + scenario + modulator values + the
decision taken. One minute, one instance, immutable. `angry-Ralph-on-layoffs`
and `relaxed-Ralph-on-layoffs` are different instances of one seed — same
philosophy, different modulation, different minutes.

**Modulators** = named states with delivery deltas and policy tilts
(e.g. `angry`: pace +, emphasis +, patience −; `relaxed`: pause +, warmth +).
The decision model picks the instance config: given scenario + history, which
modulator + operator best serves the seed's philosophy. Feedback updates the
chooser, never the seed.

```
Seed (philosophy, timeless)
  └─ Instance (seed_id + scenario_id + modulators + decision, locked per set)
       └─ Performance (beats + audio + POGs)
```

New sets never edit the seed. A seed changes only by versioned authoring.

## The analysis this unlocks

Same scenario, different graphs: which `misinterpretation_rule` fires, which
operator lands, which delivery carries it. Compare Norm's shaggy-dog
`bogus_logic` against Nolan's `identity_contradiction` on one shared scenario
and you learn what transfers — the mechanism and the delivery, never the lines.

## v1.2 — character theory grounding (2026-10-11)
Three traditions converge on seed/instance, independently validating it:
- Egri (dramatic writing): physiology + sociology + psychology bone structure;
  psychology is the product of the other two. Seeds gain `physique` and
  `situation` (class/occupation/standing) blocks; psychology stays derived.
- Comedy craft (Head): goals at global/story/scene levels; aware failings =
  neurotic comedy, unaware = unearned confidence. Our `blind_spots` +
  per-instance `chosen_goal` cover this; Foil = the panel's job (reactor).
- Stanislavski: inner life flows outward into speech/body/tempo. Our WHO->HOW
  pipeline + tempo-rhythm modeling is this, computed.
- AI research: Dynamic Persona Coherence (ACL 2026) decouples Identity
  stability from Adaptive appropriateness (+26.8%) = seed/instance exactly;
  PersonaForge (Big Five + Vaillant defense mechanisms as constraints);
  ThinkPersona (persona graphs from interviews); QUIRKYMIND (preserve
  incongruity, don't average it out); TalkMatrix (character x situation
  matrix + minimax selection = our audition matrix + selection bottleneck).
  Defense mechanisms formalize `misinterpretation_rule`; L/M/S maps to
  seed/state stacking. No rebuild needed — these are validations plus two
  seed fields (physique, situation).

## v1.3 — Jev-compatible computational engine (2026-10-11)
Every decision point is a typed Jev question (`audition/jev_questions.py`):
choice over modulator range, choice over operators, appraisal nouls
(status_threatened, blind_spot_armed, play_frame, benign_ready), veto nouls
(swappable, generic, reframe_present). `seed_state()` compiles seed +
scenario + memories into one JSON state. One parallel call per instance
(`jev_decide.decide_instance`); conf>=0.6 adopts, else bandit; all
confidences stored on the instance. No key = same questions, heuristic
answers, comparable behavior. Jev never writes text.
