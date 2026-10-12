# HANDOVER — prx0r/characters (2026-10-12, end of marathon session)

For the next agent. Read AGENTS.md first (rules), MAP.md (live status),
this file second (state + traps).

## Live right now

- Site: https://auditions.pogtown.com/ (/, /duel, /arena, /watch, /shorts,
  /pogtown, /mp4, /pilots). App: `python3 audition/app.py` (:8807) behind
  the `audition-room` Cloudflare tunnel (token in ~/.cloudflared/).
- DB (gitignored): 5 worlds, 29 residents, 16 relationships, 92 lore rows,
  6 arena contenders, 2 votes, 10 auditions.
- Tests: 12/12 green but SLOW (~2-6 min; gateway timeouts burn time).
- Keys: all in audition/.env only (gitignored). OpenCode Go oc_sk_ works
  (mimo-v2.6-flash → v2.5 fallback → template). DashScope key: text/character
  models only (omni/vision/ASR-upload paywalled). ElevenLabs: STARTER tier,
  pilots spent ~3k/40k chars — ASK BEFORE ANY SPEND (owner rule, violated
  once already).

## What each system is (don't re-derive)

- Character packs: 25 complete (14 backfilled, needs-review flags), 3 stubs
  (bobgob/bucky/sesh: audio only). Loader: any freak dir loads; unknowns
  fall back to Nolan. DO NOT invent characters (owner rule) — except
  Diogenes (real, PD). Vex/Nip/Strophe/Pippa packs DELETED this session.
- Worlds: galactic (full graph worlds/galactic.json + encyclopedia), folk
  (+34 fable collections indexed + storytellers w/ repertoires), greek
  (Zeus/Hera + 7 curated edges), earth (away-turf concept), philosophers
  (Diogenes only; needs Cynics/Stoics).
- Formats: standup/duel/battle/watch/MP4 live; react/podcast/shanty/
  surrounded/telling built (surrounded + telling proven, rest need audio
  runs); roast/sketch/talks/songs specced.
- Tavern V2 round-trip proven. Bluesky import live. DiceBear placeholders.
- Rive CLI 1.5.1 in ~/.rive (64MB). Vosk model in ~/.cache/vosk.

## Other agent (theory lane) — coordinate, don't duplicate

- Owns theory/* extraction (Ari/MediaPipe/Gemini/scribe/prosody). Good work.
- Merge protocol: commit first, fetch, `git log/show --stat`, check overlap,
  merge never rebase/force, tests, push. Their branches often predate yours
  (parallel-branch "deletions" are usually just missing-your-work — verify).
- Shared files need chat heads-up. They use librosa (installed here).

## Traps (each cost us real time)

1. Same-box checks lie; verify from outside (webfetch) + edge logs.
2. Cloudflare remote config rules: token tunnels obey dashboard only.
3. `pkill -f` matching your own shell (twice!). Use `pgrep -f "[a]udition/app\.py"`.
4. pogpet/backend/render.py shadows audition/render.py — file-location import.
5. Gateway flaky (2.8s ↔ hangs); retries + honest template fallback.
6. Labels must name the true author (see gpt-4o-mini incident, session doc).
7. Gutenberg front matter leaks into TTS (cleaner exists, verify heads).
8. Tests import real DB path; don't run concurrent servers on :8807.
9. Killtony-minutes decoder noise (266 files) uncommitted — owner call.
10. Rudy has no ready audition. #728 Ari timestamp TBD.

## Open threads (priority order)

InnerTube port (transcripts) · podcast/shanty audio runs · OpenSkill
promotion · world league UI · Cynics/Stoics · Rive RML rig · DragonBones
eval · card marketplace · payouts/KYC (lawyer) · Go quota watch.
