# VISION — worlds, leagues, promotion to Pogtown (gold)

Owner's words, 2026-10-12, saved exactly as said:

> yeah this is sick then eventually you can have worlds like galactic world -
> reptilians all the space people you can have greek god world u can have folk
> world and these can all be ecosystems of characters and then winners promoted
> to pogtown this is essentially what we are doing on the backend anyway right
> then each world obviously we can map relationships within it to each other
> like reptilians vs humans within there etc each world gets its own lore etc
> then the top 3 like league from the world get promoted to pogtown then that
> brings a new dynamic because now instead of speaking to their world with
> shared worldview they can now present to 'humans' on virtual medium which
> adds another dimension to their already winning sets!

## What this means (backend reading, no new inventions)

- **Worlds are ecosystems.** Galactic world (reptilians + grays + mantis +
  nordics), Greek god world (olympians + retinue), folk world (fairies +
  gnomes + kappa + brownies). Each world: its own lore, its own canon blocks,
  its own relationships — reptilians vs humans *within* the world, fairy courts
  vs iron, gods vs mortals. `canon/*/` already seeds this; `SPEC-character-graph.md`
  `relationships[]` already maps it.
- **Each world runs a league.** Residents duel on home turf, in front of a home
  crowd that shares their worldview. Arena Elo per world = the league table.
  This is what the backend already does — contenders + votes + Wilson.
- **Top 3 get promoted to Pogtown.** The Pogtown stage is the top flight: mixed
  worlds, mixed species, one room.
- **Promotion is a creative event, not just a ranking.** A set that killed on
  home turf (shared worldview, inside jokes land free) must now play to
  'humans' through a virtual medium — strangers with no lore. The same winning
  material, re-interpreted for outsiders. That translation IS the new comedy:
  what survives the trip up is what is genuinely funny vs merely local.
- **Relegation implied.** If a promoted act dies three straight weeks in
  Pogtown, it goes back down to its world to rebuild. Leagues breathe both ways.

## Status

PROPOSED. Backend primitives exist (canon seeds, relationships, arena Elo,
Pogtown program page). Missing: world-scoped leaderboards, promotion rule
(top 3 by Elo + Wilson, n≥30), home-vs-away performance framing, relegation.

## Emergent formats (2026-10-12, owner's words, lightly tidied)

Worlds don't just produce stand-up sets. Once an ecosystem has lore,
relationships and ranked residents, new formats emerge from it for free:

- **Podcasts.** Residents of one world (or guests across worlds) hold a
  roundtable in their own voices. The Interspecies Podcast pattern: a host +
  two eccentrics + one actual topic, each interpreting it through their
  worldview. Audio-native — the audition engine already renders the pieces.
- **Entering the worlds.** Today's version: watch + listen. Later version:
  walkable/interactive (HappyOyster-class), same canon underneath. The world
  seed is the portable asset, not the renderer.
- **Academic content — the consciousness talks.** Stage a Pogtown talk where
  one invitee per world gives their base worldview: the reptilian (reality is
  hierarchy), the alchemist (matter is unfinished spirit), the fairy (names
  bind), the angel (order descends), the philosopher (the One overflows).
  No jokes required — the comedy is structural, five ontologies colliding on
  one stage. The worldviews are already stored as data
  (`philosophy.ontology` per seed), so the debate format writes itself.
- **Rule for all formats:** the world's lore stays canonical; the format is
  disposable. A podcast, a talk, a roast and a league match all read the same
  canon and write back memories + relationships.

## SURROUNDED (2026-10-12, owner's pitch)

A human stands in the middle. The characters come up — one by one or mobbed —
and debate them, roast them, or try to make them laugh. The human is the stage:
their reactions are the only scoreboard that matters.

Why it matters mechanically: every other format performs *to a crowd*.
Surrounded performs *at one human*, whose laughter is the purest preference
signal in the system — no proxies, no Wilson needed to know what just
happened. It inverts the audition loop: the characters audition, the human is
the room.

Staging path: web prototype first (characters arrayed around the human's input
box, text/voice in, each answers from its worldview + memory of past rounds) —
VR when embodied real-time rigs exist. The format, the memory writes and the
laugh data are renderer-independent and start now.

### The seat auction (2026-10-12, owner's design)

Surrounded runs as a live optimisation loop, one objective per session
(make them laugh / prove them wrong):

1. **Perceive.** Every character reads the human's live reactions — laughs,
   weak spots, concessions — as timestamped events (POG discipline).
2. **Hypothesise.** Each agent pairs the opening with a theory mechanism
   (bisociation for the logician, unmask for the guarded, ...), citing its
   worldview + memory of this human.
3. **Bid.** Backend scores each bid into a confidence metric: posterior that
   *this* mechanism lands on *this* human *now*, plus an exploration bonus so
   newcomers get turns (Thompson sampling, not greedy argmax — otherwise one
   bully holds the seat forever).
4. **Seat.** Highest confidence performs; the puppet is animated arriving
   first — the auction result IS the stage direction.
5. **Score + update.** Laugh/concession detected → winner's mechanism posterior
   rises, losers' falls, memories written. Next round re-bids from the new
   posteriors.

### Specialists, fact-checked live (2026-10-12)

Put actual human specialists in the middle (a sleep researcher, a historian,
a magician) and let the mob come at them — with every factual claim
fact-checked in real time beside the stage. Characters supply the worldview
collisions; retrieval supplies verdicts; the human supplies ground truth on
both fronts (did it land? was it right?). A character that is funny AND right
outranks one that is merely funny — and the ledger proves which is which.
Consent + sourcing discipline from the theory-block spec applies doubled here:
every checked claim carries source + search term, no exceptions.
