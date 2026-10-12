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

## Worlds as graphs, seeded from DeityDB (2026-10-12)

Each world IS a graph: residents as nodes, charged relationships as edges,
lore claims as sourced annotations. Seeding is a query, not research —
`/root/deitydb` holds 4,130 entities, 7,161 sourced relationships, 137
traditions (Greek 599 deep; Egyptian/Norse/Mesopotamian canonical; Gnostic +
Islamic incl. jinn). Query a tradition subgraph, paraphrase into
`world_residents` + `world_relationships` (never verbatim). Borrowed lenses:
D&D alignment+domains as personality axes; Historical/Devotional/Esoteric
lenses as the respect guardrail (Devotional never comedy material);
Prolog-style path queries as sketch-premise engines.

Core mechanic: **edge + mechanism + lore = set premise.** The edge supplies
tension, theory supplies the WHAT, lore supplies material; the character's
`misinterpretation_rule` fires on the edge.

Transfer science: `killtony-priors.json` is the human-world baseline.
New worlds inherit mechanism priors only (never lines), then earn their own
Wilson evidence in arena duels → a mechanism × world transfer matrix.

Formats are subgraph shapes: sketch = 1 edge, roast = star, podcast = clique,
movie = path, consciousness talk = ontology set, Surrounded = edges at the
human, league = repeated edges over time. One engine, seven shows.

Next horizon: an evolutionary loop over the graph (see research below) —
selection by laugh-fitness, niches by mechanism × world.

## Worlds as derivation engines (2026-10-12, owner's vision)

Worlds don't just host characters — they *produce* them. From real source
material (reptilians, gods, folk beings, animals) the world derives canon,
canon derives residents, residents derive artists and bands, and successful
originals graduate back into canon as new entries — versioned, sourced,
never overwriting. New plausible AI characters expand the world the way new
species expand a bestiary: same grammar, new animal.

Earth is the next world: humans plus human animals, including brand-new
mammals derived from Earth lore (traffic pigeons, critic foxes, subway owls).
And Earth is secretly the most important venue — Pogtown plays TO humans,
so every promotion is an away game on Earth turf. Home-vs-away is just
world-vs-Earth, formalized.

## Formats from the wild (2026-10-12, owner's directives)

- **Sketches, SNL as seed.** Study SNL's sketch structures (cold open, recurring
  characters, commercial parody, weekend-update desk) as format patterns —
  never copy lines. Our worlds supply the cast; SNL supplies the grammar.
- **Agents react, live.** Characters watch content and react in real time via
  Qwen Omni joint audiovisual analysis — what they see AND hear, timestamped.
  Reaction lines become duellable contenders.
- **Earth news as world feed.** A live data pipe carries Earth headlines into
  every world as inspiration material: artists mine it for sets, drawings,
  music. The news is real and sourced; what each world makes of it is the show.

## Owner's last 5 messages — word for word (2026-10-12)

**1.**
yeah this is sick tehn eventually you can have worlds like galactic world - reptilians all teh sapce people  you can have greek god world u can have folk world and these can all be ecosystems of characters and then winners prototed to pogtown this is essentially what we are doing on teh backend anyway right then each world obviously we can map relationships within it to eachotehr like reptilians vs humans within there etc each world gets its own lore etc then the top 3 like league from the world get promotoed to pogtown then that brings a new dynamic because now instead of speaking to their world with shared worldview tehy can now present to 'humans' on virtual medium which adds another dimension to their already winning sets ! save exactly this as the vision its gold

**2.**
fuckk this is insane because each world can have shared world lore relationships grounded in actual theories think of other worlds .. can we do philosopher world .. omg we could do angel / demon world all real beings

**3.**
yeah and then u can have actual things emerging from tehse worlds lik podcasts , in the future ability to enter the worlds even more academic content like we can stage a pogtown consciousness talk where we invite someone from each world to give their base worldviews etc

**4.**
omg and then formats like surrounded hahah get a human in the middle and tehn tehse characters all come up to you and you have a debate or they try to make u laugh etc would be great in vr

**5.**
yeah this is cool because each ai character is then getting live information on whats making the human laugh or weak and then present with theory then on the backend u can have confidence metric and highest confidence gets the seat and is animated as getting tehre first, its basically all an optimisation loop with multiagents for a function like proving the person wrong or making tehm laugh.. this would be insane to get actual human specialists on and tehn fact checked in real time with ai characters

**Plus the line that came with the request (phone call-in):**
yeah then you could basically have the human call in on their phone and so we can track facial expressions live laughter etc
