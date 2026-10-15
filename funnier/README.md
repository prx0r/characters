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
