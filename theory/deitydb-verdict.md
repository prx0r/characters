# DEITYDB — depth verdict (honest)

Clone: `/root/deitydb` (219MB total; data itself = 3.3MB SQL + CSV seeds; bulk is .git + scripts). Tables: entities 1,067 / relationships 1,027 / names 479 / aliases 181 / functions 292 / sources 67 / relationship_types 67. NO RECLONE NEEDED — shallow clone holds all data files.

## What it IS good for (verified by query)
- Roster at scale: 1,067 typed entities across 137 traditions (Greek 599 deep; Egyptian, Mesopotamian, Norse, Gnostic, Hermetic, Islamic...).
- Typed relationships (67 types: parent_of, guides, etc.) with per-row notes, e.g. Hermes Chthonios guides Charon ("Shared psychopompic function."). 2,910 cross-tradition per README.
- Reception chains: same figure renamed across traditions (e.g. Hermanubis fusion row) — the syncretism map.
- Function index (292 single-word functions: abyss, psychopomp...) for grouping blocks by job.
- Source pointers with URLs (Theoi Project etc.) — follow these for depth.

## What it is NOT (verified: note fields are tag-lists, not prose)
- Personalities: Hermes row = "travel; commerce; herds; psychopomp". No character.
- Histories: no narratives, no myths retold, no views on humans/existence.
- Example ceilings: Yaldabaoth row gives roles (lion-serpent, demiurge) but no story; Jinn rows give tiers, no lore.

## Verdict for block work
DeityDB = index + relationship graph + source router. It tells you WHO exists, who connects to whom, and where to read deeper (its 67 sources). Personalities/histories/views must come from the primaries it points at (Theoi, PGM, hymns, Clark cases). Use it to enumerate, never to characterize.

## Queries banked
- Offline sqlite mirror: `/tmp/r2check/deity.db` (entities, relationships, names, aliases, functions, sources). Rebuild: parse script in session history (regex INSERT splitter).
- Proven pulls: archon-7 set, Hekate retinue (Mormolykeia/Empousa/Enodia/Trivia), Hermanubis, jinn tiers (Ifrit/Marid), Charon, Ereshkigal, Bes, Ptah-Seker-Osiris, Serapis.
