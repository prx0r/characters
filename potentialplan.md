# Pogtown Character Lab — full development instructions

I've inspected the latest `prx0r/characters` source, including its October 11 commits, audition engine, voice provider, character schemas, performance beats and existing human-recording workflow.

The big architectural decision: make characters persistent 2D puppets, with agent-directed acting, rather than generating a new 3D mesh or video for each set.

Your current repository already has most of the creative intelligence. For example, Reptilian Ralph has defined gestures such as `eye_glitch`, `suit_adjust` and `warm_rock_lean`, plus specific performance instructions attached to his 11 delivery beats. Those can become real animation commands.

The components are now sufficiently concrete to experiment with:

- [VoxCPM2](https://github.com/OpenBMB/VoxCPM): actual prompt-to-voice generation with reproducible seeds and controllable cloning.
- [Rive CLI](https://github.com/rive-app/rive-docs/blob/main/cli/agents.mdx): official agent-readable animation authoring, compilation, inspection and screenshots.
- [Agent Theater](https://github.com/needle-tools/agent-theater): an MIT-licensed stage with structured casting, scene and performance controls.
- [OpenMontage](https://github.com/calesthio/OpenMontage): a substantial production framework that already has a beta local character-animation pipeline.

One important discovery: Agent Theater's own third-party documentation says its built-in speech generation is currently disabled. It makes even more sense to use VoxCPM2 as the voice engine and Agent Theater as the stage-direction reference, rather than depending on its internal audio.

The brief below is designed for your coding agent to execute directly in `prx0r/characters`, preserving the existing work and producing demonstrable experiments before committing to a production stack.

# AGENT MASTER BRIEF: Character Lab v1 — Autonomous Voice, Puppets & Stage Performances

**Repository:** https://github.com/prx0r/characters
**Mission:** Transform our existing Character Foundry and Audition system into an experimental studio where persistent fictional characters can acquire original voices, expressive 2D bodies, reusable gestures, stage direction and complete audiovisual performances.

**Priority:** Get one genuinely expressive character performing a convincing, funny 60-second set. Do not spend weeks creating generic infrastructure.

**Operating principle:** Clone, install, inspect, run and compare existing technologies before building equivalents.

## 0. Read our repository before coding

First inspect the current repository and recent commits. Do not assume the older README or previous reviews describe the latest state.

Read these files:

- `README.md`
- `dev.md`
- `SPEC-character-graph.md`
- `SPEC-theory-blocks.md`
- `audition/app.py`
- `audition/generate.py`
- `audition/tts_provider.py`
- `audition/store.py`
- `audition/battle.py`
- `audition/prompt.py`
- `audition/gates.py`
- `audition/test_audition.py`
- `audition/static/index.html`
- `research/export_shikigami.py`
- `freaks/reptilian-ralph-middle-management/character.json`
- `freaks/reptilian-ralph-middle-management/delivery.json`

Inspect the neighboring `prx0r/freaktown`, `prx0r/pogpet` and `prx0r/influence2` projects where available. Establish ownership boundaries before creating shared interfaces.

### Preserve what already works

Our Character Foundry already defines:

- Canonical identity and psychological philosophy.
- Character-specific blind spots and misunderstandings.
- Comedy mechanisms and scenario generation.
- Structured delivery beats.
- Emotional modulators.
- Character-specific gesture descriptions.
- Auditions, POG reactions and feedback.
- Human audio-take uploads.
- Performance histories and versioned strategies.

**These are inputs to the new animation system, not features to rebuild.**

The core relationship remains:

`WHO (character identity) × WHAT (comic mechanism) × HOW (performance) → AUDIENCE EVIDENCE`

Do not corrupt the underlying character identity merely because a performance is rated badly.

The existing `delivery.json` format is our starting contract. Add backward-compatible adapters rather than replacing it.

---

# PHASE 1 — Clone and benchmark the technology

## 1.1 Create an isolated experimental workspace

Create a local directory adjacent to the repository, for example:

`../character-lab-vendors/`

Keep third-party source repositories, virtual environments, model weights, cached outputs and temporary render files outside our Git history.

Create a tracked experiment manifest inside `characters/experiments/` recording:

- Project name and original GitHub URL.
- Exact commit SHA or release tag.
- License and model-weight license.
- Installation requirements.
- Whether installation succeeded.
- Actual functionality tested.
- CPU/GPU requirements.
- Render or generation times.
- Known limitations and crashes.
- Final adoption decision.

Never claim a repository works merely because it cloned successfully.

### Primary projects to evaluate

| Project          | URL                                              | Experiment                        |
| ---------------- | ------------------------------------------------ | --------------------------------- |
| VoxCPM2          | https://github.com/OpenBMB/VoxCPM                | Prompt-to-voice                   |
| VoiceStudio      | https://github.com/debpalash/VoiceStudio         | Voice design and audio workstation|
| Seed-VC          | https://github.com/Plachtaa/seed-vc              | Preserve human performances through voice conversion |
| Agent Theater    | https://github.com/needle-tools/agent-theater    | Agent-driven stage control        |
| OpenMontage      | https://github.com/calesthio/OpenMontage         | Complete video production         |
| Rive CLI         | https://rive.app/docs/cli/overview               | Agent-generated 2D rigs           |
| rive-mcp         | https://github.com/ODU33104/rive-mcp             | Experimental Rive creation and inspection |
| Rhubarb Lip Sync | https://github.com/DanielSWolf/rhubarb-lip-sync  | Audio-to-mouth cues               |
| ManimGX          | https://github.com/academa-labs/manimgx          | Programmable visual explanations  |

Also investigate Rive's official editor MCP integration before relying on third-party tools.

Use shallow clones where appropriate. Pin revisions. Read each project's install guide before executing setup commands.

Rive CLI is installed from Rive's official distribution; it is not simply another GitHub repository to clone.

### Installation and licensing rules

- Agent Theater is MIT, but review its `THIRD-PARTY.md` before reusing bundled art, music or fonts.
- OpenMontage and VoiceStudio are AGPL-3.0; do not copy their implementation directly into proprietary shared modules without a licensing review.
- `rive-mcp` is freeware with a restrictive license. It allows use but prohibits unauthorized modifications and redistribution. Treat it as a standalone evaluation.
- VoxCPM2 is Apache 2.0. Verify the exact model and dependency licenses.
- Rive CLI and hosted Rive services have separate commercial publishing and watermark requirements. Verify these.
- Do not automatically download large model weights, start paid GPU instances or invoke paid APIs without reporting costs and obtaining approval.
- Never clone an identifiable person's voice without permission.

**Do not install every dependency in one environment.** Isolate Node, Python audio, GPU and rendering dependencies.

## 1.2 Create a capability report

Write:

`experiments/2026-10-character-lab/CAPABILITY_REPORT.md`

For every tool, record one of:

- Working: executed successfully, with a saved artifact.
- Partial: installed but output or functionality incomplete.
- Blocked: exact error and required resolution.
- Not tested: explicitly state why.
- Rejected: clear technical, licensing or cost reason.

Include actual commands, logs and output artifact locations.

---

# PHASE 2 — Prompt-to-voice laboratory

**This is the first priority and should be demonstrable independently of any animation work.**

## 2.1 Install and run VoxCPM2

Use a dedicated Python environment and the official project instructions.

The reference installation is:

`pip install voxcpm`

First check Python, PyTorch, CUDA, available memory and model-download requirements.

Test the project's native command-line interface, including this supported pattern:

`voxcpm design --text "Good evening. Management assures me the situation is completely under control." --control "A restrained, dry, middle-aged male corporate executive; precise diction, low-mid pitch, quietly condescending, with a barely concealed reptilian hiss" --seed 42 --output ralph_voice_42.wav`

Read the installed CLI help before relying on specific optional flags.

The Python API also supports embedding a voice description in parentheses at the beginning of the text.

**Do not confuse a natural-language voice description with a persistent voice ID.** The ability to recreate exactly the same voice across independent generations needs to be tested.

## 2.2 Design a voice audition matrix

Begin with three fictional characters.

### Reptilian Ralph

Design goal: an exhausted alien middle manager desperately maintaining corporate professionalism.

Voice prompts to test:

1. Male, 45, American corporate executive, low-pitched, slow, clipped diction, deadpan authority.
2. Male, 50, smooth and friendly corporate trainer with an unsettling undertone of superiority.
3. Male, 40, slightly nasal, very restrained, subtly reptilian vocal texture, impatient with incompetence.
4. Male, 55, deep resonant boardroom voice, formal, exhausted, dryly annoyed.

### No-Nose Nolan

Design goal: a police detective who is convinced of his own competence despite obvious limitations.

Voice prompts:

1. Male, 35, overconfident New York police detective, punchy rhythm, slightly gravelly.
2. Male, 40, exhausted American noir detective, low register, suspicious, dry understatement.
3. Male, 30, animated and defensive, rapid speech whenever challenged.
4. Male, 45, solemn investigative narrator with hilariously misplaced certainty.

### Experimental giraffe

Design goal: a gentle, overthinking intellectual whose unusual perspective makes ordinary events bizarre.

Voice prompts:

1. Male, 35, thoughtful British academic, warm baritone, deliberate pauses, gentle curiosity.
2. Male, 30, soft American philosopher, slightly breathy, earnest and analytical.
3. Female, 40, dry public-radio presenter, intelligent, precise, deeply curious.
4. Male, 45, relaxed East African English speaker, reflective and understated, with a natural conversational rhythm.

Accents must be evaluated for authenticity rather than caricature.

For each prompt, generate at least three seeded candidates using the same short test script.

That gives **36 initial candidate recordings**.

Store each candidate's prompt, model, generation settings, seed, duration and output hash.

## 2.3 Build the Voice Lab UI

Add a **Voice Lab** section to the existing audition interface rather than creating a completely separate application.

Required controls:

- Select an existing character.
- Enter or edit a natural-language voice description.
- Choose a model/provider.
- Generate multiple seeded candidates.
- Play audio candidates side by side.
- Rate voice identity, expressiveness, naturalness and suitability.
- Mark a candidate as a favorite.
- Save a named voice profile to the character.
- Reuse that profile in future auditions.
- Compare how the same voice performs emotionally different lines.

Show a clear status for each generation: pending, running, completed, failed.

Do not silently substitute a different TTS model and label its output VoxCPM2.

## 2.4 Test voice persistence

This is critical for recurring characters.

For each winning voice candidate:

1. Generate a canonical reference passage.
2. Preserve the actual generated WAV.
3. Generate five unrelated new lines using the same voice-design prompt.
4. Generate the lines using the saved reference WAV through VoxCPM2's cloning mode.
5. Compare speaker similarity, timbre consistency, naturalness and emotional expression.
6. Blind-rate samples so judgments aren't biased by model labels.

The winning character voice is a **versioned profile plus an actual reference artifact**, not merely a text description.

Proposed additional configuration, separate from the existing `voice` fields:

- `voice_profile_id`
- `provider`
- `model_revision`
- `design_prompt`
- `reference_audio_path`
- `reference_audio_sha256`
- `generation_defaults`
- `consent_provenance`
- `status`

The generated reference recording should remain available even when the model is upgraded.

## 2.5 Add multiple delivery modes

Introduce a provider interface with four performance sources:

**A. Prompt-to-voice** — Natural-language voice design with no reference recording.
**B. Reference-based TTS** — Generate speech using the character's approved reference voice.
**C. Human performance** — Use the raw audio uploaded through the existing audition interface.
**D. Voice-converted performance** — Take an authorized human recording and convert its timbre to the fictional character voice.

Evaluate Seed-VC for mode D.

Always preserve the original human take and store the conversion as a derived artifact.

Do not assume Seed-VC supports arbitrary text descriptions as its target voice; it normally uses a reference speaker recording. The designed VoxCPM voice can potentially supply that reference, but test compatibility and output quality.

The objective is to determine whether **human-acted timing + converted fictional voice** delivers better comedy than fresh TTS.

## 2.6 Benchmark audio quality and costs

Compare:

- Existing Edge TTS baseline.
- VoxCPM2 prompt-designed voice.
- VoxCPM2 reference-cloned voice.
- Original human performance.
- Seed-VC transformed human performance.

Evaluate with identical text whenever possible.

Record speed, GPU utilization, peak memory, intelligibility, artifacts, expressive fidelity, generation consistency, and actual cost.

No provider is declared the winner before listening tests.

---

# PHASE 3 — Build the Rive Puppet Laboratory

## 3.1 Use Rive instead of the mesh-first rendering path

For the first generation of Pogtown characters, prioritize original layered 2D artwork and puppets.

The objective is not merely a talking PNG. Each character must be capable of **acting**.

Install the official Rive CLI following its documentation:

https://rive.app/docs/cli/getting-started

Useful documented commands include:

- `rive doctor`
- `rive create <project-name>`
- `rive <project-name>`
- `rive --verify`
- `rive inspect --summary`

Use the generated `AGENTS.md` and CLI reference to confirm exact command invocation and project-specific options.

Experiment with Rive Markup Language, runtime state machines, bones, meshes and parameterized animation.

Use the official CLI first, then evaluate `rive-mcp` in an isolated workspace.

## 3.2 Create the first puppet: Reptilian Ralph

The first rig should be a readable, attractive, stylized 2D interpretation of the existing character.

Keep his canonical identity:

- Seven-foot reptilian pretending to be a human executive.
- Badly fitting human suit.
- Eyelids that occasionally reveal reptilian eyes.
- Restrained and condescending demeanor.
- Discomfort with cold environments.
- Almost obsessive corporate professionalism.

Create original layered artwork with separately animatable parts:

- Head and jaw.
- Eyes, pupils and eyelids.
- Eyebrows or equivalent eye-expression shapes.
- Mouth and multiple phoneme shapes.
- Neck and torso.
- Shoulders and arms.
- Hands.
- Suit and tie.
- Optional tongue, eyelid or suit-glitch elements.

Use artwork suitable for clean cutout motion and deformation. Avoid asking an image generator to create a different full-character image for each emotion.

Do not embed final production decisions into opaque image-generation prompts. Keep editable assets, geometry and controls.

## 3.3 Implement a minimum expressive rig

Create named states and parameters:

**Expressions** — neutral, deadpan, confident, confused, suspicious, annoyed, embarrassed, surprised, self-satisfied

**Gestures** — idle, blink, look_audience, look_away, small_shrug, suit_adjust, lean_forward, recoil, head_tilt, eye_glitch, warm_rock_lean

**Mouth** — closed, rest, AI, E, O, U, FV, L, MBP, open

Use only the mouth shapes required by the selected lip-sync system; map additional ones when useful.

The art should also support blended intensity, such as a small or large head tilt, without needing a separate animation for every value.

## 3.4 Add physically convincing motion rules

Avoid the current generative-animation failure mode: movement everywhere, constantly.

Use:

- Anticipation before an expressive action.
- Small secondary movement.
- Different transition durations for different emotions.
- Eye movements that precede some head turns.
- Pauses and complete stillness.
- Slight breathing and idle movement.
- Character-specific movement limits.
- Deliberate post-punchline holds.
- Natural settling after gestures.

Ralph should move less than Nolan. His movements should feel controlled until his emotional mask slips. That contrast is part of the joke.

Create at least three distinct idle or listening states so the character doesn't mechanically loop the same motion every few seconds.

## 3.5 Export and validate

Required artifacts:

- Editable Rive source.
- Compiled `.riv` file.
- A visual sheet showing every expression.
- A short animation testing all supported gestures.
- An animation demonstrating mouth movement.
- State-machine/input documentation.
- Automated screenshots captured at known states.
- A compatibility report for the chosen Rive browser runtime.

Verify that the compiled artifact loads successfully in the official runtime.

Remember: a `.riv` animation and an MP4 performance are different deliverables. Build a render/export adapter rather than assuming Rive's normal interactive asset output is already a finished video.

---

# PHASE 4 — Adopt Agent Theater's stage-directing philosophy

**Important: we want Agent Theater's expressive staging system, not an exact dependency on its browser application.**

Clone and run: https://github.com/needle-tools/agent-theater

Study the following conceptual interfaces:

- `theater_start`
- `stage_create`
- `stage_cast`
- `stage_script`
- `show_play`
- `piece_*`

Inspect the actual source, underlying scene data, stage schema, timing and playback implementation.

Also test a real scene in its browser application.

Agent Theater uses browser WebMCP and has browser support restrictions. Do not require WebMCP to be available on every viewer's device.

## 4.1 Build a simple Pogtown stage

Create one reusable stage: **Pogtown Comedy Club**

Visual requirements:

- Dark theatrical background.
- Warm spotlight.
- Microphone and stand.
- Minimal floor shadows.
- Stage-left and stage-right positions.
- Camera framing suitable for vertical shorts.
- One dominant character at a time.
- Optional shadow audience, not detailed crowd animation.

The stage must be reusable across different performers without redesign.

Add a stage manifest containing asset references, positions, lighting choices, camera presets and sound cues.

## 4.2 Define a stage-director protocol

The stage director must be able to express actions like:

- Enter from stage left.
- Walk to the microphone.
- Face audience.
- Start speaking.
- Look at the audience.
- Pause.
- Tilt head.
- React to an imagined interruption.
- Change facial expression.
- Hold still after a joke.
- Exit.

Create typed, validated commands rather than asking the animation engine to interpret arbitrary language at runtime.

The director chooses actions. The renderer executes them.

Do not allow unvalidated generated code to manipulate the browser or files directly.

## 4.3 Build a performance timeline

Our existing `delivery.json` already includes beat IDs, type, text, pause duration, expression, gesture, look direction, pace and emphasis. Use this as the initial input.

Add an optional `performance.v1` artifact with character ID + version, audition ID + delivery hash, audio ref + duration, word/beat alignments, stage manifest ID, puppet/rig version, ordered timestamped events, gesture intensities, camera events, sound effects, runtime/renderer version.

All times illustrative. A production event must be validated against the final audio duration. Don't overwrite the original delivery structure with renderer-specific data.

## 4.4 Make theatrical timing genuinely intelligent

Create a simple Stage Director module. It receives approved script + beat roles, character psychology + habits, final audio + timing, stage capabilities, action vocabulary. It outputs event proposals.

Rules:

1. Character motivation determines reactions.
2. Movement should emphasize a line, not distract from it.
3. Punchlines often deserve stillness.
4. A character can misunderstand its own situation.
5. The stage director can know the joke; the character must not become self-aware of it.
6. Physical gags must be deliberately motivated.
7. Different characters must have different movement styles.
8. Do not generate a gesture for every sentence.
9. Do not insert canned audience laughter and treat it as genuine audience feedback.
10. Permit manual edits to every proposed event.

Create reusable directional primitives, not a full autonomous film director.

## 4.5 Add camera direction

Start with four presets: full-stage shot, medium character shot, face close-up, slight dramatic push-in. Camera movement should be sparse and meaningful. For the MVP, support fixed shots and a small number of transitions.

---

# PHASE 5 — Accurate lip sync and delivery timing

The current audition engine scales approximate beat durations to the synthesized audio length. That is insufficient for frame-accurate animation and reliable punchline attribution.

Implement a dedicated alignment stage.

## 5.1 Test Rhubarb Lip Sync

Repository: https://github.com/DanielSWolf/rhubarb-lip-sync

Take the final WAV and generate timed mouth cues. Map detected mouth cues to the Rive puppet's supported mouth-shape states. Store the timing output as a versioned artifact.

Rhubarb is a starting point, not guaranteed perfect phonetic alignment. For detailed word timing, also evaluate a maintained forced-alignment implementation or timestamps from a compatible speech pipeline.

## 5.2 Make final audio the timing source

Production order:

1. Script approved.
2. Voice/performance generated or recorded.
3. Final audio chosen.
4. Audio normalized.
5. Actual audio duration measured.
6. Speech alignment generated.
7. Mouth cues generated.
8. Stage and gesture events resolved.
9. Animation rendered.
10. Composite and QA.

Do not render against estimated text timings and then stretch the result afterward. Preserve timing provenance and alignment uncertainty. If audio changes, invalidate and regenerate dependent alignment and render artifacts.

## 5.3 Preserve human comedy timing

Do not automatically eliminate silence or normalize every pause. A pause may be an intentional joke mechanism. Distinguish speech / dramatic silence / breath / laughter / environmental sound / technical dead air. A pause should be removable only when identified as accidental or deliberately edited.

---

# PHASE 6 — Integration into the current audition system

Do not create an unrelated second app. Extend the existing Flask/SQLite audition system behind feature flags.

## 6.1 Add optional adapters

Suggested modules:

- `audition/audio_providers/base.py`
- `audition/audio_providers/voxcpm.py`
- `audition/audio_providers/seed_vc.py`
- `audition/audio_providers/voicestudio.py`
- `audition/performance/timeline.py`
- `audition/performance/alignment.py`
- `audition/performance/stage_director.py`
- `audition/performance/rig_adapter.py`
- `audition/performance/render.py`

Treat these as a suggested layout, not an obligation to split every operation into a large abstraction hierarchy.

Existing Edge TTS must remain available as a baseline and fallback. A failed local VoxCPM installation must not break ordinary auditions.

## 6.2 Add an experimental UI

Add two tabs or sections: **Voice Lab** (create, play, compare, approve and version character voices) and **Stage Lab** (select audition, choose take/rig/stage, generate direction events, preview, edit, render, watch, save/reject). The user should be able to compare multiple render versions without regenerating the script.

## 6.3 Keep production experiments immutable

Introduce additive database tables or equivalent persistent records for voice profiles, audio candidates, approved references, rig versions, stage manifests, performance timelines, render jobs, rendered artifacts, human quality evaluations, experiment comparisons. A run should always be traceable to its script, character, voice, rig, renderer and model version. Do not modify previous audition evidence when rerendering the same script.

## 6.4 Keep feedback disentangled

Separate assessments of material / delivery / voice / animation / production. A polished animation does not prove the joke was better. Avoid feeding video-production ratings directly into the character's comedy strategy without appropriate attribution.

---

# PHASE 7 — OpenMontage integration

Treat OpenMontage as an experimental production backend. Clone it separately and inspect `AGENT_GUIDE.md`, `PROJECT_CONTEXT.md`, `pipeline_defs/character-animation.yaml`, `skills/pipelines/character-animation/`, `ink-theater/`, `remotion-composer/`, existing quality-review tools. Run its existing sample pipeline before modifying anything. Evaluate whether its local SVG/GSAP animation and composition pipeline is sufficient to render our first puppet. It may be sensible to use the existing SVG rigging system initially while comparing it with Rive, rather than spending substantial time on both integrations.

### Preferred integration design

Our repository produces a validated performance package (rig, stage spec, final audio, timed mouth cues, gesture/expression events, camera instructions). OpenMontage handles composition, output formats and production QA where it demonstrably offers value. If integrating OpenMontage takes longer than implementing a small Remotion/FFmpeg exporter, use the smaller exporter for the first MVP.

**Do not block the first complete show on adopting OpenMontage.** Document the AGPL implications before shipping a commercial hosted integration.

---

# PHASE 8 — Three controlled experiments

Every experiment must produce a real artifact, not just an implementation plan.

## Experiment A: Which voice is the character?

**Character:** Reptilian Ralph. Generate and compare at least twelve prompt-to-voice candidates. Use consistent material and independent ratings. Then select two or three finalists and generate longer audio samples. Produce a voice comparison page, listening matrix, recommended canonical voice reference, config file, hardware/cost record. Success means the user can actually hear, compare and select voices.

## Experiment B: Can the character act?

Take one approved 10–15-second Ralph audio recording. Produce three animation variants (mouth-only / mouth+eyes+body / full stage direction). Use the same script and audio for all three. Compare blind. Measure expression, distraction, sync, overall quality. Produce playable videos + comparison screen. Success means the differences are visible and reproducible.

## Experiment C: One complete minute

Generate or select a full 60-second Ralph set using our existing comedy pipeline. Use saved voice profile, final audio, accurate alignment, reusable puppet, Pogtown Comedy Club stage, stage-director events, camera + facial direction, final rendered video. Produce at least `final_vertical.mp4` (1080×1920), `final_landscape.mp4` (1920×1080), timeline, manifests, contact sheet, QA report, human review record. Render low-res previews first. Do not report success until a real video can be opened and watched.

---

# PHASE 9 — Quality gates

Implement automated checks for valid IDs/versions, existing nonempty audio, valid sample rates/durations, no corrupt WAV/MP3, no clipping, ordered events within audio duration, supported mouth shapes/actions, valid Rive compile+load, no crashes, no missing assets, exact duration/fps, correct aspect ratio, no silent/black/frozen sections, artifact hashes + provenance.

Add a visual review loop: render selected frames, inspect, record failures, modify only relevant parameters, rerender. Require human approval for final design and performance. Do not use an uncalibrated AI aesthetic score as sole approval gate.

### Testing

Existing audition tests must continue to pass. Add new tests with synthetic/fixture audio so CI does not require GPU or model download. Keep expensive integration tests opt-in. Document external dependencies and make repository paths configurable rather than assuming `/root/characters` and `/root/pogpet` exist on every machine.

---

# PHASE 10 — The longer-term autonomous character system

Do not build this until experiments A, B and C work. Once a character reliably performs, preserve separate decision layers: Actor / Comedy director / Stage director / Production director / Critic. These can initially be typed steps in one coding-agent workflow. We do not need five separate continuously running autonomous agents. The long-term learning system should compare multiple deliveries of the same script, identify which choices helped, and update versioned policies. Investigate the Harness Learning paper (https://arxiv.org/abs/2609.35738) as a research direction. Do not introduce RL infrastructure before we have valid evaluations.

---

# Final execution order

1. Inspect the existing repo and get tests running.
2. Create the external experiment workspace and technology manifest.
3. Install/benchmark VoxCPM2.
4. Produce the prompt-to-voice audition board.
5. Save a persistent Ralph voice.
6. Install and validate Rive CLI.
7. Create Ralph's editable expressive 2D rig.
8. Inspect and run Agent Theater.
9. Build a minimal typed stage-direction adapter.
10. Connect final audio to timed mouth cues.
11. Render and compare three 10–15-second performance variants.
12. Test OpenMontage against the simpler export path.
13. Produce one complete 60-second set.
14. Extend the existing audition UI with voice and stage previews.
15. Record costs, limitations and next experiments.

**Do not** replace the existing character ontology, generate a new video appearance for every joke, require 3D meshes, rebuild the comedy engine, deploy unfinished systems, or spend a week on architecture without a playable artifact.

## Required final report

Return: exact revision/branch, all third-party projects + revisions + licenses, working/blocked features with logs, voice comparison results + audio artifacts, Rive rig preview + gesture demo, stage-director timeline example, rendered comparison videos, final 60-second performance if achieved, total cost/resources, source changes/tests/commits/PRs, architectural recommendations.

If a dependency cannot run, produce a reproducible failure report and continue with the next reasonable independent experiment.

**Final success criterion:** I can open our existing Character Audition app, select Reptilian Ralph, audition several voices designed from text, select one, watch him perform with expressive eyes, mouth, head and body, see the agent's stage directions translated into movement, and produce a complete shareable stand-up video.

**Our aim is not to build another animation framework. It is to give our fictional characters expressive, reusable bodies and voices so they can actually perform.**

The first demonstration is twelve different Ralph voices from text prompts, followed by a single 15-second performance in Rive.
