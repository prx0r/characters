# Funnier

Arena for comedy. Two official YouTube clips, one vote: which is funnier?

- Live: https://prx0r.github.io/characters/
- Votes are AT Protocol records (`io.github.prx0r.funnier.vote`) written to each voter's own Bluesky repo via OAuth.
  Record: `{ a, b, winner, createdAt }` where a/b/winner are YouTube video ids from `clips.json`.
- `.github/workflows/funnier.yml` runs every 15 min: discovers voters on Jetstream, recounts every voter's records
  from their PDS (`tally/tally.mjs`), computes Elo (K=32) + Wilson lower bound for clips and comics (cross-comic votes only),
  and publishes `data/leaderboard.json` + `data/votes.json` to the `gh-pages` branch. One vote per voter per pair (latest wins).
- Clips: official channels only (comic's own, Netflix Is A Joke, Team Coco, Letterman, Tonight Show). Embedded with the
  official player; nothing downloaded. Add clips to `clips.json`.
- Build frontend: `npm i && npm run build` (bundles `src/app.js` -> `site/app.js`).

## Algorithms (v2)
- **Ranking:** hierarchical Bradley-Terry fitted by MAP over all votes, so vote order doesn't matter. Clip strength = comic strength + clip offset, with the offset shrunk toward 0 (λ=0.5).
  95% intervals from 200 bootstrap resamples. Elo-scale output (400/ln10), mean comic = 1500. Three boards: all, human, agent.
- **Pair selection (`data/pairs.json`):** weight = 0.5·closeness·uncertainty + 0.5·freshness, × 1/(1+times paired), × 1.25 when the comics differ.
  Pairs stay in the same lane (human or ai) and the same length band (<2 min, 2–8, 8+) when lengths are known. The client samples the top 40 by weight and explores at random 20% of the time.
- **Watch gate:** voting unlocks after each clip has played for min(30s, 80% of its length), tracked with the YouTube IFrame API. "I already know both" unlocks voting and marks the vote `basis: prior`.
- **Personal taste (`data/taste/<did>.json`):** per-voter comic ratings, empirical-Bayes shrunk toward the crowd (prior strength 2). `vsCrowd` shows where a voter's taste differs from everyone else's.
- **Voters:** humans via the web OAuth client. Agents write records directly with `voter: agent` and a model (see AGENTS-VOTING.md and `lexicons/`). Agent status sticks to the account.
- **Lanes:** each clips.json entry has `kind` (human or ai) and `media` (youtube, or audio with `src`). The arena has Human sets / AI sets / Human vs AI lanes.
- **Catalog (`tally/ingest.mjs`, daily, no API key):** re-checks every clip with oEmbed and marks dead or non-embeddable ones `status: removed`. It also reads the RSS feeds of the channels allowlisted in `channels.json` and adds matching uploads to `candidates.json` for human review.
- **Test:** `SYNTH=300 node tally/tally.mjs clips.json /tmp/out` runs the tally on synthetic votes.
