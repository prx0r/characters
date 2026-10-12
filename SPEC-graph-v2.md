# Character graph v2 — maximum granularity (2026-10-12)

v1 asked ~15 questions. v2 asks everything the engine can use. Every field
carries its own provenance: `measured` (arena/POG evidence), `authored`
(writer invention, reviewed), `derived` (computed from other fields),
`unknown` (explicitly missing — never silently defaulted).

## Identity (immutable without version bump)

- id, name, species, canon slug, version, seed_schema
- persona.deal/facts/interview_style/premise (v1, kept)
- physique {build, distinguishing, note} — body shapes psyche (Egri)
- situation {class, occupation, standing, note} — sociology shapes psyche
- self_concept {identity, desired_identity, feared_identity}
- awareness {unaware|aware|fluctuating} + note (Head: unaware failings =
  unearned-confidence comedy; aware = neurotic)

## Inner life (drives all comedy)

- dramatic_core {want, fear, need, self_model, blind_spots[]} (v1, kept)
- contradictions[] — pairs that coexist ( pompous + terrified). Engine fuel.
- philosophy {ontology, epistemology, axiology, causality, agency} (v1, kept)
- misinterpretation_rule (v1, kept) + fired_examples[] (timestamps where it
  demonstrably fired on stage — measured, not asserted)
- motivations {seeks[], avoids[]} (v1, kept)
- attention {notices_first[], ignores[], watched[]} — perception filter
- interpretation_biases[] — how new input gets misread, specifically
- expression {default_register, emotional_restraint, tells[]} (v1, kept)
- social_model {status_orientation, attitude_to_authority} (v1 where present)

## Craft (mutable strategy layer)

- modulator_range[] + per-modulator deltas (v1, kept)
- preferred_theories[], archetype, comedy.operator_priors{} (v1, kept)
- energy {baseline, decay, floor} — 0-80 scale shared with shikigami export
- threads[], memories[] (fictional events only), relationships[]
- repertoire[] (storytellers), artist facets (music/visual), rig id

## Evidence pointers (computed, never hand-edited)

- arena {elo, wins, bouts, wilson} — read live, not stored
- formulas — falsifiable claims + status
- voice refs (speech/singing), show pack ref, Tavern card ref

## World lore v2 (same discipline)

Every lore row: claim + source + status {canonical|paraphrase|measured|
inferred|raw} + confidence {A|B|C} + kind {entity|relationship|event|rule|
tension|news}. Style guide block per world: voice, tone, POV, pacing,
dialogue rules (stolen from Loreum, adapted). Inferred rows expire unless
re-evidenced; raw rows never feed generation.
