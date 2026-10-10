# characters — Freaktown Character Foundry

Bulk-generated, theoretically-accurate character packs in standardised
Freaktown Character Pack v1 format (`docs/CHARACTER_PACK.md` in freaktown).

Layout mirrors `freaktown/freaks/<slug>/` so packs drop straight into the show:

```text
canon/<slug>/
  canon.json       # reference block: traits, lore, variants, mesh guide, verify_against
freaks/<slug>/
  character.json   # identity, persona, voice, profile, actions + canon:<slug> (name REQUIRED)
  delivery.json    # freaktown.delivery.v1 beats[] — the jokeblocks
  set.wav          # composed clip (placeholder silence until TTS render)
  meta.json        # status + sha256 hashes; lineage.root = canon slug (tool-maintained)
```

Rule: mine `canon/`, cast `freaks/`. One canon (e.g. `reptilian`)
feeds many interpretations (Ralph the manager, Rudy the technician...).
A performer is proven when every canon physical + behavioral trait
shows up at least once in its 11 beats.

## Canon blocks (v1)

* `canon/reptilian/` — conspiracy archetype: slit-eye glitch, itchy suit,
  bloodlines, warm rocks, Dulce denial. Proved by Ralph.
* `canon/gnome/` — Paracelsian earth elemental: freeze-when-watched,
  red hat, porridge bribes, flamingo war. Proved by Gnorma.
* `canon/fairy/` — old-rules gig fairy: iron burns, names bind,
  literal wishes, milk debt. Proved by Fay.
* `canon/kappa/` — river imp: head-dish, cucumber ledger, bow reflex,
  sumo law. Proved by Kyle.

## Performers (all validated OK)

* `freaks/kappa-kyle-cucumber-debt/` (144 words)
* `freaks/reptilian-ralph-middle-management/` (145)
* `freaks/gnorma-the-hoa-gnome/` (148)
* `freaks/fay-marrow-the-gig-fairy/` (147)
* `freaks/channel-charlie-indigo-host/` (141, dual-voice, no canon — original)
* `freaks/buddha-ultimate-deadpan/` (140, historical PD — no canon yet)

## v1 — Kappa Kyle (review me!)

* `freaks/kappa-kyle-cucumber-debt/` — PD Japanese folklore kappa as
  cucumber-debt collector. Full stage-ready pack: 11 beats, 138 words,
  closer <8 words, Kill-Tony timing (setup 300ms / punch 1500ms / tag 500ms).

Validate with freaktown's own validator:

```bash
python3 /root/freaktown/scripts/validate_pack.py /root/characters/freaks/kappa-kyle-cucumber-debt
```

Recompose real audio:

```bash
python show.py --no-tts --comedian kappa-kyle-cucumber-debt
```

## Copyright rule

Only public-domain folklore / ancient myth here (kappa, jinn-archetype,
anunnaki-archetype, fairies, olympic spirits, heptameron angels).
No channeled names (Ramtha™, Bashar©, Seth©, Ra©), no Cannon text,
no Clark text — paraphrased lore only, original sets only.
