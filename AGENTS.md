# AGENTS.md — operating memory for prx0r/characters

Read this first. It exists because a full session of visions nearly evaporated.
Details live in linked docs; this file holds rules that must survive turnover.

## What this repo is

Character foundry + audition engine + arena leagues + worlds, for fictional
comedy (now expanding to music/art). Canon immutable, strategies evolve,
evidence decides. Site live at https://auditions.pogtown.com/

## Lanes (two agents work here)

- **Audition/engine/site** (`audition/*`, pages): primary lane A.
- **Theory/extraction** (`theory/*`, world seed data): primary lane B.
- **Shared** (`app.py`, `generate.py`, `store.py`, site JS): heads-up in chat
  before touching. Small diffs. Tests before push.

## Merge protocol (learned from three near-misses)

1. Commit first. 2. Fetch + `git log`/`show --stat` their commits.
3. Check overlapping paths explicitly. 4. Merge, never rebase/force on master.
5. Tests green, then push. Parallel branches showing your files as "deleted"
   usually just predate them — verify before panicking.

## Money & secrets (violations happened; rules are absolute)

- ASK before any spend of any amount (API credits, quotas, rentals, top-ups).
- Free voices do narration/baseline; paid voices ONLY for what free can't do
  (character voices, whispers, expressive delivery).
- Keys live in `audition/.env` only (gitignored, 600). Never committed,
  never printed, never in code. Audit with `git grep -c`, counts only.
- Template is the honest fallback, never the product pose. Labels must name
  the true author (mimo/template/edge). No fabrication, ever.

## Evidence discipline

- Wilson before crowns: nothing "funniest" under n≥30, CI excluding 0.5.
- Human votes dispose; model scores propose. Never inverted.
- Strategies die, characters don't. No verbatim copyrighted material.
- POG timestamps > votes > retention. Keep sources separate.

## Backends (current)

- LLM: OpenCode Go `mimo-v2.6-flash` → `mimo-v2.5` fallback → template.
  Gateway flaky: 2×15s tries. Never OpenAI models.
- TTS: edge-tts (free); ElevenLabs v4 for showcase (owner-approved only).
- Portraits: DiceBear seeds (placeholders, honestly labeled).
- No GPU workloads locally. No torch installs. Disk floor: 4G free.

## Docs (read, don't duplicate)

- `VISION.md` — visions + owner's verbatim messages (do not edit words).
- `MAP.md` — worlds × formats × channels with live status (keep current).
- `SESSION-2026-10-12.md` — full session record (shipped/decided/blocked).
- `SPEC-character-graph.md` — character schema (dense; needs plain version).
- `dev.md` — peer review + P0 history.
- `potentialplan.md`, `music/` — briefs and specs, verbatim.

## Commands

- Tests: `python3 -m pytest audition/test_audition.py -q` (slow box, ~2-3 min).
- App: `python3 audition/app.py` (:8807). Never `pkill -f` with a pattern
  matching your own shell — use `pgrep -f "[a]udition/app\.py"`.
- DB is gitignored; back up before migrations. Renders/MP4s live in /tmp.

## Open threads (see SESSION doc §18 for detail)

Rudy needs an audition · #728 timestamp TBD · KT transcripts blocked on
YouTube access · Go quota watch · decoder noise uncommitted · 13 thin
character packs await backfill · Rive RML rig · OpenSkill promotion ·
InnerTube port · Cynics/Stoics canons.
