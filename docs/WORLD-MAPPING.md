# WORLD-MAPPING — same delivery, different world (spec v1)

The architecture: a minute is FUNNY because of the collision between a
character's delivery engine and THEIR world's social assumptions. Extract
that collision, keep the delivery word-for-word-timed, swap the world.

## The mapping (per minute)

1. **Extract the earth-world collision:** what social assumption does the
   bit violate? (Norm's moth: "asking a podiatrist for emotional help" —
   wrong-expert assumption. Kyle: "politeness is transactional".)
2. **Find the galactic/folklore equivalent:** same collision shape, new lore.
   Wrong-expert -> "asking the wrong alien department"; transactional
   politeness -> "cucumber tribute is intergalactic currency".
3. **Keep the delivery arc IDENTICAL:** same emotions, same recipes, same
   timing. Only the material words change. The collision SHAPE transfers.

## Collision shapes (from our corpus)

| shape | earth example | galactic example | folk example |
|---|---|---|---|
| wrong_expert | moth->podiatrist | bureaucrat->war-room | witch->cucumber doctor |
| wrong_scale | personal grief in professional setting | galaxy-ending event filed as paperwork | world-ending curse over missing hat |
| literalize_metaphor | "heartbroken" -> actual cardiac | "bloodline" -> literal blood bank | "iron burns" -> literal burn ward |
| status_reversal | customer demands manager, IS manager | alien demands Earth leader, IS Earth | fairy demands tribute from king |
| deadpan_absurd | flat affect + wild content | flat affect + cosmic content | flat affect + magical content |

## Process

1. Read the real minute's delivery arc (stencil)
2. Identify its collision shape + social assumption
3. Write NEW material: same collision, target world's lore
4. Render with SAME recipes + target world's voice card
5. Verify + score with SAME rubric
6. A/B: does it land the same? (score delta = transfer quality)

## Files

- `voicelab/worlds.json` — collision shapes + world lore tokens
- `swap_world.py` — the mapper (stencil + collision + world -> material)
