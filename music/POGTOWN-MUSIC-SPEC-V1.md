# POGTOWN MUSIC — Canonical Architecture Specification v1
**Date:** 2026-10-12  
**Status:** Proposed; not implemented  
**Scope:** Three editorial YouTube channels, one virtual-venue/performance engine, persistent AI musical artists, explainable composition, and a human-preference learning loop.

## 0. Product thesis

Build a fictional entertainment ecosystem whose artists persist beyond individual songs. Each musician has a canonical character identity and musical identity. Their songs are immutable experiments, their concerts are stage executions, and listener preference data informs a *versioned composition strategy*, not their immutable canon. Classical-music analysis is a research stream that produces explicitly sourced, inspectable musical technique blocks; those blocks can inspire new original compositions and can be assessed in controlled experiments.

This is **not** a farm of near-identical AI uploads, a generic avatar SDK, a general-purpose DAW, an autonomous rights-licensing platform, or an attempt to clone living musicians.

### Three canonical editorial channels

1. **Classical Nights** — high-quality performances of rights-cleared classical repertoire in reusable virtual venues. One familiar host, occasional knowledgeable discussion, multiple camera angles. A test bench for precise symbolic-to-instrument synchronization.
2. **Pogtown Records** — original fictional musicians and bands (Galactic world, folk world, etc.) with relationships, releases, live shows, experiments, competitions and collaborations. First proof: Ralph the Reptilian fronts a fictional original band.
3. **Inside the Music** — researched music explanations: harmony, counterpoint, rhythm, form and geometrical voice leading. A host plus demonstrations, score/sound visualizations, and later *fictional interview segments* in which artists describe logged choices behind their original songs.

**Do not create multiple additional channels or independent codebases for each genre.** Jazz Nights, Rock Nights, Electronic Sessions and Classical Nights are show-format configurations on one production engine. A band may later get an independent channel only after evidence warrants it.

## 1. Authority / repository map

This mirrors the repo boundaries reviewed on 2026-10-12.

| Authority | Existing repo | Owns | Must never own |
|---|---|---|---|
| Character / world canon | `prx0r/characters` | Character seed, world, relationships, band membership as a relationship, memories, voice **identity reference**, immutable versioned strategies and instances | Rendered media or YouTube upload state |
| Stage/performance truth | `prx0r/freaktown` | StageRuntime, Transport, camera/audio composition, rigged performers, performance manifests, synchronized instrument events and rendered-video receipts | Deciding artist identity or changing lore based on views |
| Distribution and public state | `prx0r/influence2` | Published catalog, channel entities, release schedules, posting approval, analytics snapshots, public memory, audience metrics | Changing the character or song's canon |
| Scientific experimentation | Portable module drawing on `prx0r/finalbuilds2` | Explicit hypotheses, forecasts, blinded tests, confidence/calibration, evidence IDs, experimental allocations | Treating raw YouTube views as proof of musical quality |
| Music knowledge and generation | New **narrow** `music-core` package (start within existing repo; extract only after successful P0) | Source-licensed scores, symbolic analysis, technique blocks, original composition programs, audio engine adapters, provenance | Generic creator platform or independent user-facing app |
| Asset/world provider | Atlas beta / World Labs + Three.js/Spark/GLB | World asset references, splat placements, static environment, riggable moving objects | Authoritative artist identity |

### Existing limitations to respect

- Freaktown `StageRuntime` currently centers on a **single VRM/avatar** and one principal audio transport. True ensembles require multiple performers plus sample-accurate stems/instrument timelines.
- The extracted stage-runtime package retains app/Zustand import debt; decouple with injected ClockSink/RoomStore before building broad reusable venue components.
- The `/characters` specs separate **seed → instance → performance → evidence**; maintain this. Git is authoritative for identity/strategy versions, SQLite/Postgres for append-only evaluation events and receipts.
- `/influence2` already describes approvals, publishing and 24-hour / 7-day measurement; reuse these, but verify OAuth scopes and actual channel upload permissions. An API key is insufficient for private authorized video uploads.
- Do not claim existing repos implement reliable band animation, piano fingering, music training or a finished preference optimizer; those are roadmap items.

## 2. Canonical data entities and relationships

Minimal typed domain:

`World` — `Character` — `Band` — `ArtistMusicalIdentity` — `StrategyVersion` — `Track` — `TrackTake` — `Performance` — `Venue` — `Release` — `AudienceObservation`.

Research side: `SourceWork` — `ScoreEdition` — `AnalyzedPassage` — `TechniqueBlock` — `TechniqueHypothesis` — `CompositionExperiment`.

Crosslink each TrackTake to its composer/artist strategy, adopted technique IDs, generator model/version, musical seed or MIDI, audio/stem asset hashes, exact usage rights, evaluation labels and render/publish receipts.

### `artist.music.v1` — authoritative musician facet

```json
{
  "schema": "pogtown.artist.music.v1",
  "character_id": "reptilian-ralph-middle-management",
  "artist_id": "ralph",
  "identity_version": 1,
  "world_id": "galactic",
  "roles": ["lead-vocalist", "songwriter"],
  "band_ids": ["galactic-compliance"],
  "speech_voice_ref": "voices/ralph-speech-v1",
  "singing_voice_ref": "voices/ralph-singing-v1",
  "voice_rights_ref": "licenses/voice-ralph-v1",
  "musical_seed": {
    "aesthetic": ["bureaucratic funk", "cosmic psychedelia"],
    "instrumentation": ["bass", "drums", "synth", "vocals"],
    "rhythmic_character": ["syncopated", "tight-pocket"],
    "harmonic_character": ["chromatic color", "clear hooks"],
    "expressive_constraints": ["remains in character", "no third-party voice imitation"]
  },
  "current_strategy_ref": "music-strategies/ralph/0003",
  "provenance": ["fictional-original"]
}
```

**Speech and singing voices are not interchangeable.** A TTS speaking voice does not guarantee consistent singing timbre. The singing pipeline must explicitly support stable consent-cleared voice identity or use an instrumental pilot.

### `music.technique.v1` — reusable knowledge, not copied music

```json
{
  "schema": "pogtown.music.technique.v1",
  "technique_id": "chromatic-mediant-color",
  "name": "Chromatic mediant harmonic move",
  "mechanism": "Root shifts by a third while retaining or recoloring common tones",
  "preconditions": ["harmonic center established"],
  "musical_effect_hypothesis": "Unfamiliar color while preserving perceivable coherence",
  "parameterization": {"root_motion": "third", "common_tone_bias": 0.6},
  "evidence": ["analysis/score-123/passage-5"],
  "verified_by": "human-review",
  "source_rights_ref": "rights/score-123",
  "examples_are_references_not_generation_targets": true
}
```

The `musical_effect_hypothesis` is an interpretation, **not** an objective discovered truth. It should have confidence, alternatives and falsifiable experiments.

### `music.track.v1` — sealed experiment

```json
{
  "schema": "pogtown.music.track.v1",
  "track_id": "galactic-compliance-single-001",
  "band_id": "galactic-compliance",
  "artist_strategy_versions": {"ralph": "0003", "bassist": "0002"},
  "technique_ids": ["chromatic-mediant-color", "syncopated-hook"],
  "generator": {"provider": "music-provider", "model": "model-version", "prompt_sha256": "...", "seed": 42},
  "assets": {"final_audio_sha256": "...", "stems": [], "midi_ref": null, "lyrics_ref": "..."},
  "rights": {"composition": "original", "recording": "cleared", "voice": "cleared", "samples": "cleared"},
  "state": "candidate",
  "parent_track_id": null,
  "created_at": "2026-10-12T00:00:00Z"
}
```

Track IDs/content hashes are immutable; revisions are child takes. Snapshot the entire generation configuration. Never overwrite an old strategy version or performance while retaining its ID.

## 3. Classical intelligence: what the system actually learns

### A. Score-to-knowledge pipeline

1. **Import legally usable MusicXML/MIDI** from a scored/licensed source, with source edition metadata and permitted commercial/training uses. Public-domain *composition* does not imply a public-domain modern recording or encoding. Sources include per-work Mutopia licenses, individually checked music21 corpus entries, and selectively verified public-domain datasets.
2. Parse notes, timing, measures, key signatures, parts, phrase marks and expressive markings.
3. Extract candidate features: harmonic function/Roman numerals, chord quality, inversions, harmonic rhythm, modulations, non-chord tones, cadence types, voice leading, counterpoint, rhythmic motifs, phrase structure, register and orchestration.
4. Inspect candidate passage as score + audio + annotations; expert/human spot-checks for difficult or ambiguous harmonic readings.
5. Package the useful generalizable principles into versioned technique blocks with supporting passage IDs and explicitly stated hypotheses.
6. Derive exploratory composition prompts / symbolic program transformations that express the principle **without copying a protected melody or arrangement**.
7. Compare original outputs in controlled arena trials and link observed response to a specific technique test.

### B. Three types of learning (do not collapse them)

- **Symbolic rule/retrieval:** immediately feasible. Use `music21`, `pretty_midi`, custom scripts and a retrieval layer. Requires no GPU training.
- **Preference / selection model:** after collecting meaningful blind human A/B ratings, learn which parameter combinations work for which audience and context. Use calibrated contextual bandits or Bradley–Terry models with uncertainty, cohort controls, and held-out tests.
- **Audio model fine-tuning:** *optional much later*, on clearly licensed **original audio**, after a distinct artist sound and sufficient owned material exist. ACE-Step 1.5 supports adapters, but do not equate an adaptation trained on a few tracks with a genuine long-term personality or a music-theory reasoning system.

### C. Tymoczko-inspired geometric visualization

Start with two visual levels:
1. Reliable 12-pitch-class circles, interval edges, chord inversions and voice-leading arrows.
2. Higher-dimensional chord-space/orbifold projections with mathematically justified distances and constraints. Explain the mapping and its limitations; do not claim a 2D pitch circle *is* full Tymoczko geometry.

Use music21 for score analysis, a typed `HarmonyGraph`/`VoiceLeadingEvent` feed, and Three.js for visuals. For a first video, show a specific resolved harmonic passage with score highlight, corresponding piano audio and moving lines between pitch classes.

### D. Video-format intelligence

For examples **we own or have authorization to analyze**, capture: transcript; hook structure; explanation beats; score/visual annotations; shot types and cuts; audio examples; segment timestamps; retention if owner-authorized. Store *abstract patterns* (e.g., 'hear once → pause → demonstrate the bass movement → rehear') rather than copied narration, shots, recordings or scripts. Public YouTube analytics for other channels is limited; do not claim their private retention curves or unobtainable A/B outcomes.

## 4. Autonomous bands: roles and state

### Formation

`World` residents may choose members based on canon relationships, instrumentation needs, stylistic compatibility, conflict opportunities and musical goals. `Band` is an explicit, versioned entity with memberships and history. A member can be in multiple projects; a band can add guests. Cross-world bands are possible when character canon and progression permit.

### Roles in one song creation round

- **Artist identity/policy:** stable goals, worldview, voice references, style seed.
- **Composer agent:** proposes melody/harmony/form or directs a music model with typed technique blocks.
- **Arranger:** assigns instruments/stems, register, dynamics, transitions.
- **Producer:** chooses sonic palette, mix/master and take selection.
- **Critical listener / quality gate:** screens technical faults, incoherence, rights issues, near-copying and severe model artifacts. Quality gate is not the final audience reward.
- **A&R / experimental director:** selects what to try next from uncertainty and past evidence, with exploration and cost controls.
- **Public interviewer/host:** presents *recorded decision logs and verified analysis*, framed as the fictional artist's explanation; never invent hidden cognition or present simulation as a human musician.

These are **logical roles**, not necessarily six always-running LLM agents. P0 compiles them into one orchestrator with typed passes.

### Event-driven artist development

`band.formed`, `composition.proposed`, `track.generated`, `quality.passed`, `arena.paired`, `listener.preferred`, `strategy.proposed`, `strategy.approved`, `performance.booked`, `release.published`, `show.interviewed`, `band.relationship_changed`.

Fictional memory and canonical relationships should change through explicitly accepted world events. Strategy evidence by itself must **not** automatically rewrite character identity.

### Concrete first band: Galactic Compliance

Ralph the Reptilian is a fictional lead vocalist whose songs translate corporate bureaucracy into cosmic funk. The bassist is a different Galactic-world character who favors ornate jazz substitutions; the drummer prefers rigid, almost machine-perfect pocket. Their disagreement about musical complexity becomes part of their relationship graph and stage interviews. An early experiment can compare a tight repetitive chorus against a harmonically unusual chorus while keeping mastering, loudness, length and presentation matched.

## 5. Performance engine: one venue, multiple musical kinds

Define `show.music.v1` as a typed extension of existing Freaktown `performance.v1` (do not overwrite old contracts). References: venue environment, anchor positions, cast + rigs, instrument models, track/stems, event stream, camera directions, host speech, applause, controls and render settings.

### Timeline events

```
show.open
host.speak
crowd.applause
performer.enter
instrument.note_on / instrument.note_off
pedal.down / pedal.up
song.section_start / song.section_end
singer.phrase_start / singer.phrase_end
camera.cut
light.cue
performer.bow
show.close
```

A single master **audio transport** is authoritative. Stage visuals read the clock, not their own unrelated timers. Capture timing offsets against audio; measured drift should be bounded and covered in tests. Keep music audio independent of voice-lipsync analyser; use instrument/stem-specific analyzers and exact MIDI where available.

### Animation by difficulty

1. Piano first: MIDI controls exact piano-key depression; separate physical fingering/IK layer; medium and wide shots until finger accuracy is verified.
2. Jazz band: MIDI piano, bass pluck events, drum kit hit events, section-level body animation and camera cuts.
3. Rock band: ideally separate licensed source stems / symbolic music events. Beat-driven arm strums alone are an approximation, not accurate fret/finger work.
4. Vocal performers: stable approved fictional vocal timbre + phoneme/viseme mapping from aligned **actual song audio**; do not animate arbitrary speech mouths over sung vocals.
5. Atlas environment: immutable environment asset/splat + separate skeletal performers/instruments/props/lights and occlusion anchors; never rely on a static splat to articulate hands or keys.

### Media deliverables

Each sealed performance produces: `show.json`, WAV/FLAC master, optional stems/MIDI, MP4 16:9, 9:16 excerpts, thumbnail candidates, shot-list/camera log, rights manifest, hashes, sync QC report, publishing metadata and analytics joins.

## 6. Musical arena, experiments and genuine learning

### Two distinct data channels

**Controlled arena (causal-ish):** play two loudness-normalized, same-length candidate clips blind; randomize A/B positions; hide artist identity/thumbnail; ask a concise preference question plus optional tags ('memorable melody', 'better groove', 'too repetitive', 'novel', 'would replay'). Collect human listeners separately from agent judges. Agents are useful as cheap *screeners*, not a substitute for human music preferences.

**Public platform (observational):** track clicks, first-30s retention, average view duration, returning viewers, audience cohort and format. Understand that thumbnails, promotion, seasonality, host personality, scene design and upload timing affect these numbers independently of composition. Model those factors or do not attribute outcomes to harmony.

### Rewards (multi-objective; avoid optimizing one click metric)

Store a vector:

- musical coherence / basic quality;
- distinctive identity consistency;
- originality / non-plagiarism;
- blind human preference;
- memorability and replay intent;
- real-world audience retention (with caveats);
- cost/latency and rights/safety gates.

**Never normalize every goal to one undifferentiated 'viral score'.** Maintain Pareto candidates and an experimental novelty track. Explicitly record whether a result is a synthetic judge prediction, user preference, or live YouTube metric.

### Learning algorithm, phased

1. **P0 (<50 trustworthy human matchups):** aggregate pairwise wins, confidence intervals, listen-through and qualitative notes. Human selection. Random exploration across predefined axes.
2. **P1 (50–500):** Bradley–Terry or hierarchical pairwise model with uncertainty, balanced assignments and held-out judges; consider contextual Thompson allocation only with enough matched evidence.
3. **P2 (500+ diverse matched votes):** lightweight learned preference model for **ranking and selection**, tested on held-out composers/artists and independent listeners. Keep score features as interpretable inputs.
4. **P3:** optional reinforcement/fine-tuning over own licensed tracks. Define explicit training budgets, safeguards against homogenization and recurring human reviews.

The number thresholds are proposed engineering gates, not scientific validity guarantees. Version criteria before changing them. For hypothesis policy, prefer `/finalbuilds2/docs/HYPOTHESIS-EVOLUTION-POLICY.md` over naive Beta-success scoring: use out-of-sample predictive skill, calibration and evidence breadth.

### Arena visual contract

`comparison_id`, `anonymous_a`, `anonymous_b`, `clip_duration_ms`, `matched_loudness_lufs`, `randomized_side`, `cohort`, `judge_type`, `preference`, `reason_tags`, `timestamp`, `experiment_id`, `feature_differences`, `rights_refs`.

No treating skipped/abandoned trials as direct dislikes unless explicitly modeled. No training from fake simulated ratings.

### League architecture

- World-scoped first leagues: Galactic jazz vs Galactic rock, etc.
- Per-artist skill/response in genres; bands can have their own ratings.
- Promotion to cross-world headline show based on sustained performance with minimum independent judgments, not simply most uploads.
- Novelty festivals and surprise collaborations keep exploration alive.
- Rankings are contextual (audience, genre, format) rather than universal declarations of objective artistic quality.

## 7. Interview / explanation format

**Classical:** real score → human-verified harmonic insight → performance excerpt → rendered geometry → transformed replay.

**Original AI artist:** original track → logged generation decisions (techniques, arrangement, iterations) → artist-character interprets these choices in-character → reproducible A/B demonstration → questions answered from evidence.

The artist's dialogue is a **fictional presentation of documented production decisions**, not independent proof the model introspected its own mental process. The host can genuinely query the database and challenge claimed choices. In later editions, invite real musicians/composers to challenge the work, with consent and explicit distinctions between human and synthetic speakers.

Possible episode structure, 5–8 minutes:
- 0:00 cold-open passage
- 0:15 hook and thesis
- 0:45 first playback
- 1:15 expose the bass line / harmony / rhythm
- 2:30 geometrical or score-space visualization
- 3:30 artist or host explains the choice
- 4:45 compare alternate arrangements
- 6:00 full passage replay and synthesis

This is an editorial template with genuine content variation, not a mass-produced script shell. Prioritize correctness and listener understanding.

## 8. Provider-neutral tooling

| Need | P0 | Later |
|---|---|---|
| Scores and harmonic features | `music21`, `pretty_midi` / `partitura`, MusicXML | specialized geometric chord-space modules |
| Audio structure | `librosa` onset/beat/chroma; aligned MIDI if known | robust stem/score alignment |
| Symbolic note playback | licensed piano sound bank, FluidSynth for prototype | high-quality paid/licensed piano VST rendering |
| Generative originals | licensed generation provider; evaluate ACE-Step 1.5 | per-artist adapter trained solely on rights-cleared owned audio |
| Voices | rights-cleared character TTS for speech; separate licensed singing voice | stable controllable singing engine, validation and alignment |
| Environment | existing Atlas beta world + Three.js/Spark | new venue assets, audience interaction |
| Characters/stage | `prx0r/freaktown` GLB/VRM/Three.js | multiple rigs, IK, facial and instrument tracks |
| Encoding | FFmpeg, cached assets | distributed render workers only when needed |
| Distribution | `prx0r/influence2` approval + YouTube APIs | scheduled channel programming |
| Graph & strategy | `prx0r/characters` canon + immutable strategy version | richer compositions/relationship graph |

Critical licensing example: Meta AudioCraft MusicGen weights are CC-BY-NC, even though the code is MIT. Do not use those weights in commercial channel operations without rights. Verify every generator/provider license and model version. ACE-Step 1.5 claims MIT licensing and LoRA support but verify exact repo/checkpoint/terms before release.

## 9. Copyright, transparency and quality gates

- Rights database for each composition, score encoding, sample, instrument preset, recording, vocal identity, cover arrangement, model output, environment texture and GLB.
- Public-domain composition ≠ rights to a recent performer recording or edited score. Per-work rights and territory matter.
- Modern pop-cover composition/arrangement/synchronization issues require clearance or supported YouTube rights process; publisher Content ID participation and optional revenue sharing are not universal guarantees.
- Never clone real celebrities' or musicians' voices without authorization. Fictional artists may share permitted synthetic speech/singing references with their character identity, with documented provider terms and consent where relevant.
- Mark realistic synthetic scenes and AI-generated music according to YouTube's altered/synthetic disclosure rules. Don't imply prerecorded shows are live or pretend human performers performed AI-generated takes.
- YouTube's inauthentic/mass-produced content policies are a business risk; ensure substantive differentiated artistry, sound quality, commentary and educational content.
- Prevent automatic publishing if rights missing, audio clipping, note-sync failure, incoherent hands, visual clipping, unverifiable music-analysis statements or low-confidence interviewer claims.

## 9A. The same grammar for autonomous visual artists (future, not P0)

A persistent creator is **not** restricted to music. Add a media-specific `artist.visual.v1` facet to a character with authored visual principles (composition, palette, form, materials, motif vocabulary, spatial arrangement, movement, favored techniques), a style seed, versioned strategies, and provenance. The character identity remains shared; visual/music practice and learning remain distinct. A band can collaborate with a fictional visual artist on album covers, stage design, music videos, live lighting and eventually interactive environments.

For research, an art-explanation series extracts **abstract** visual techniques from rights-cleared images or images used within lawful commentary; it does not train on unknown third-party imagery or copy a living artist's recognizable compositions. The visual arena measures blinded preference on pairs at matched resolution and image size, then gathers originality/legibility/composition-specific tags. Do not combine music and image preferences into one single creativity score.

Practical example: Ralph's band writes a new song; a Galactic-world visual artist proposes three stage designs with different geometries and lighting rules; the musician and artist negotiate in-character; human listeners judge the audio blind, and viewers separately judge the art blind. We can then test whether particular audiovisual pairings improve viewing **without** misattributing the improvement to the song itself.

A promising *research direction* beyond diatonic jazz is continuous/microtonal harmonic geometry (e.g., the October 2026 Harmonic Eigenspace preprint, https://arxiv.org/abs/2610.03398). Treat it as an experimental compositional instrument and hypothesis source, not an established predictor of public taste.

## 10. Milestones and non-goals

### P0 — One end-to-end three-format showcase (1–3 weeks, scope not calendar promise)

1. **Classical Nights:** 2–4-minute rights-cleared piano recital. MIDI/event-to-key sync, seated performer, three stable camera presets, host+applause, 16:9 final.
2. **Pogtown Records:** Ralph's 45–90-second *original* performance, initially spoken intro + instrumental if consistent fictional sung voice not available. Stable artist identity fields and versioned track pack; credible stage presence.
3. **Inside the Music:** 90–180-second Bach harmonic demonstration using a checked MusicXML score, audio excerpts and visualized notes/voice leading; one manually approved TechniqueBlock.
4. **Arena:** one A/B blind matched comparison with persistent votes, JSONL/SQLite receipts and charts, clearly separating human and agent assessments.
5. **Distribution:** drafts for each channel, thumbnail/rights/QC review, human publishing approval. No auto-posting by default.

**P0 acceptance:** all three are rendered using the same stage/timeline and asset registry (not three bespoke renderers); works have proven license chain; note animation is auditably synchronized; one technique block demonstrably causes a variation in an original composition; anonymous A/B votes can be traced to sealed takes and versions.

### P1 — Musician ecosystem (weeks 4–8, contingent on P0)

- Found at least one recurring 3-member fictional band with different musical roles, stable voice/style references and canon-preserving disputes.
- Release two music pieces + one behind-the-composition episode.
- Build an initial 20–50 human A/B tests across well-defined musical variants (not necessarily YouTube traffic).
- Add scores/technique browser and per-artist strategy revision history.

### P2 — Genre night expansion

- Jazz trio with section-level performance, sax/horn or bass/drum events, 1–2 additional venues; rock night after credible singing/guitar animation.
- Cross-world battle / collaboration, audience requests and recurring host interviews.
- Compare predictions to held-out audience data before using auto-exploration allocation.

### P3 — Real-time & personalized

- True live stage performance/stream, audience interaction, responsive improvisation and eventually AR/VR. These depend on lower-latency generator/instrument timing than P0 and are **not** production assumptions.

### Non-goals until P0 passes

No generic online DAW; no full-body finger-perfect guitar rig; no fully autonomous YouTube channel farm; no unsupervised LoRA training on found music; no auto-published deepfake performances of real musicians; no new game engine; no bespoke big graph database before SQLite queries become inadequate.

## 11. Engineering test plan

1. **Authority tests:** Influence cannot write canon; renderer cannot update artist strategy; strategy updates always have a parent, version and evidence refs.
2. **Timeline tests:** paused/seeked/restarted performances keep synchronized note, camera and audio events; re-renders preserve cue order and report measured max drift.
3. **Rights tests:** missing/restricted license blocks public publishing; rights manifest derived transitively from track, samples, score and voice.
4. **Performance QC:** automated note-on/key motion audit for piano; clipping/loudness checks; no silent unplayed note unless explicitly omitted in arrangement; invalid rig camera failures prevent publish.
5. **Arena integrity:** randomization, no double votes by session, provenance, blind identity, versioned question phrasing, separate human vs synthetic judge results.
6. **Learning science:** held-out comparison, baseline, confidence intervals, diversity/novelty measure, no early reinforcement from uncalibrated guesses.
7. **Explanatory accuracy:** each factual musicological claim linked to a scored passage and reviewer; AI-fabricated analysis remains draft.
8. **Release:** publishing starts as draft, explicit human approval, channel identity pinned, receipt/analytics joins checked.

## 12. Immediate developer work-order

**Work in existing repos. Start with `freaktown` and `characters`. Do not scaffold a new website or 3 new channel stacks.**

- Inspect latest `StageRuntime.ts`, `Transport.ts`, `AudioBus.ts`, `CameraDirector.ts` and `performance.v1.schema.json`. Implement a backward-compatible `show.music.v1` fixture and tests for instrument events.
- Build a minimal MIDI event importer and add a GLB piano with per-key animation into a seeded concert hall. Keep the environment separate from movable assets.
- Add artist musical-facet schema and band-membership relationship into `/characters`, pinning both identity and mutable strategy versions without overwriting history.
- Implement `TechniqueBlock` extraction + one verified Bach passage using `music21`, not a foundation-model training run.
- Build one truly original Ralph track/take with legally clear assets, sync its stage cues, and preserve exact production receipts.
- Build one blind paired listening flow reusing character audition interfaces, label judge source, and store selections append-only.
- Add one `Inside the Music` visual sequence that reads the *same passage and technique data* as the composition experiment.
- Wire publication as approved drafts through Influence; retain all rights, QC, identity and analytics joins.

**Ship the three samples, then decide whether to extract `music-core` into its own package/repository.**
