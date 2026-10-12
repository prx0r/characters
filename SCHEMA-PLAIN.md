# Character profile, in plain words

Every performer in `freaks/<slug>/character.json` answers the same questions.
If a file can't answer one, that answer is missing — never guessed.

## The person (who they are)

- **name** — stage name. **species** — what kind of being (folklore type ok).
- **persona.deal** — one sentence: who they are and what they do.
- **persona.facts** — 4-6 concrete, checkable things about them.
- **persona.interview_style** — how they talk when questioned.
- **premise** — the act in one line. **profile** — energy, pace, gesture
  frequency, eye contact, how long they hold after a punchline (ms).
- **voice.voice_id** — TTS voice. **voice.eleven_voice_id** — showcase voice
  (only if cast and approved; empty otherwise).

## The inner life (why they're funny)

- **dramatic_core.want / fear / need / self_model** — what they chase, dread,
  require, and believe about themselves.
- **dramatic_core.blind_spots** — 1-3 things everyone sees but them. This is
  the comedy engine room: jokes are built by aiming situations at blind spots.
  `unknown — ...` is allowed ONLY with zero observed sets; authors fill it
  for originals, evidence fills it for imports.
- **philosophy** (ontology/epistemology/axiology/causality/agency) — what the
  world IS according to them, in their own logic. Five sentences, no jargon.
- **misinterpretation_rule** — the one-sentence engine: what does criticism
  turn into in their hands? (Ralph: workflow tickets. Kyle: cucumber debts.)
- **motivations.seeks / avoids** — three each.
- **expression** — default register + emotional restraint (high/medium/low).

## The craft (how they perform)

- **modulator_range** — moods they can inhabit without breaking (angry,
  smug, paranoid...). The director picks; the seed never changes mid-set.
- **preferred_theories + comedy.operator_priors** — which joke mechanisms
  they lean on, with weights. Learned from duels, seeded by author.
- **archetype** — their home mechanism (bisociation, rigidity...).
- **threads** — running gags and open loops. **actions** — named gestures
  with triggers (rigs map these to motion).
- **canon** — which `canon/<slug>` they descend from (lineage, required).

## The paperwork (trust)

- **version** — `seed-v1`, plus `+backfill` if upgraded later. Backfills carry
  `provenance: {seed, status: needs-review}` until a human signs off.
- **No verbatim lines** from anyone's copyrighted act. **No biography** of
  real people. Fingerprints ≤7 words. Stage persona only, always.

## Status right now

25 packs, all complete (14 backfilled 2026-10-12, flagged needs-review).
3 stubs (`bobgob`, `bucky`, `sesh`: audio only, no character yet — write or
delete). Canon missing in `egyptian-death`, `proclus`, `synergetics`.
