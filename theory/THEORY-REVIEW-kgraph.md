# Theory review — kgraph zero-cal test (uncle_lazer, 2026-10-15)

Test: rich text-only character graph -> emerge -> Jev -> MARY tempo ->
render (no clone, no fitted scale, never heard them) -> score vs GT.
Then: why does the ACTUAL delivery make more sense?

## Findings (ordered by theoretical weight)

1. **Persona text energy != delivery energy.** Graph v1 (rowdy want,
   sprint signature, vibe=manic) predicted manic everywhere; actual is
   dry-sarcastic-drawl. Lazer writes ABOUT being wild; delivers flat.
   Fix: `delivery_texture` field separates performative identity from
   voice behavior. Graph v2 overcorrected to deadpan — texture lexicon
   needs the sarcastic-drawl midpoint (dry wit, not flat).

2. **AM-laugh GT confounds the metric.** His GT labels are laugh-derived
   (laugh-near -> sarcastic/mock_indignant), so emotion-acc becomes
   laugh-position prediction — and punchline-from-text is 41% for humans
   (Punchlines-to-Predictions). Text cannot predict laugh positions
   reliably. Fair zero-cal emotion tests need GEMINI-style semantic-mood
   GT, not laugh-adjacency GT. Re-score on gemini-GT sets (pickles, ari,
   casey) for the real zero-cal number.

3. **Engine tempo floor ~0.74 effective.** Prompted tempo (whisper 0.80
   x calm 0.85 x clean-zone 0.92) bottoms out ~0.63-0.74 of base. His
   drawl needs ~0.4x. Very-slow delivery hits the floor; either stack
   two tone markers or document atempo as the <0.7 exception.

4. **Sprint-into-laugh re-confirmed** (lazer s2: actual accelerates near
   audience response — matches Casey corpus finding, third performer now).

5. **Rich graphs can be WORSE than thin ones** when affect is miscalibrated
   (0.00 vs 0.28) — granularity amplifies errors, it doesn't average them
   out. Graph iteration (run -> theory review -> revise texture) IS the
   calibration loop for new characters. v1->v2 moved predictions
   manic->deadpan; v3 (sarcastic-drawl midpoint) is next.
