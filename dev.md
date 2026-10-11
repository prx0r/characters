# Peer review: `prx0r/characters`

Repository: [prx0r/characters](https://github.com/prx0r/characters) · Source-level review of the current GitHub tree

## Executive verdict

Keep this repository. It is considerably closer to the Freaktown MVP than our earlier discussions suggested. But the central weakness is that it records performances more effectively than it learns from them.

You already have a functioning-looking audition architecture, a character seed/instance distinction, a Jev decision layer, POG capture, multiple performance candidates, human audio takes, and substantial Kill Tony research data.

The next priority should not be another dataset, facial animation stack, or new agent framework.

It should be making the following loop genuinely work:

Generate a character-consistent minute → listen → POG → critique → retrieve meaningful history → make an evidence-informed creative decision → produce a better new minute.

Architectural direction

Keep

The separation of canon, character graph, theory mechanisms, delivery modulation and auditions is sound.

Learning and continuity

Needs work

Current learning is largely weighted operator counts, recent comments and short text memories rather than evidence-linked comedic development.

Review limitation

I inspected the repository tree and selected source files, but have not executed its runtime or test suite in a cloned local working tree. Findings below distinguish confirmed code issues from engineering risks that need testing.

## 1. What is already implemented

The repository currently contains 817 tree entries and several substantial subsystems.

| Area                  | Verified implementation                                                         | Assessment                                             |
| --------------------- | ------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Character definitions | `SPEC-character-graph.md`, canon blocks, character formulas and performer packs | Strong foundation                                      |
| Audition UI/API       | `audition/app.py`, HTML frontend                                                | Existing implementation, needs end-to-end verification |
| Comedy generation     | `audition/generate.py`, prompt compiler, theory/operator selection              | Useful, but weak quality safeguards                    |
| Jev                   | `jev_decide.py`, `jev_questions.py`, `slop_jev.py`                              | Good experimental layer                                |
| POG                   | Timestamped events, beat attribution, playback events                           | Valuable foundation                                    |
| Learning              | Strategies table, ratings, operator success/failure counts                      | Too simplistic                                         |
| Memory                | Character-linked text memories                                                  | Insufficient for persistent callbacks                  |
| Human performance     | Upload and selection of recorded audio takes                                    | Good start                                             |
| Research              | Kill Tony decoding, persona generation and stored theory features               | Substantial work already done                          |
| Tests                 | `test_audition.py` covering storage, generation, API and human takes            | Positive, but limited                                  |

This changes my recommendation from the earlier discussions: don't migrate to Pi immediately. Repair the existing audition engine first, then add Pi where it creates measurable value.

## 2. Critical findings

### P0 — Scenario and script can become inconsistent

Confirmed in `audition/app.py`, approximately lines 86–90.

After `generate_minute()` has produced the complete minute, the app checks whether its scenario was recently used. If so, it can replace `gen["scenario"]` with a different scenario.

But it does not regenerate the script, decisions or beat content.

That means the database could say:

Scenario: AI policing

while the actual audio is about something else.

This compromises source attribution, theory analysis and future learning.

Fix: choose and lock the scenario before generation. If a collision requires replacing it, regenerate the complete performance and its associated decision record. Never mutate the scenario metadata on a finished result.

### P0 — Beat timestamps are not verified against speech

Confirmed in `audition/app.py`, approximately lines 103–110.

The app estimates beat timings, synthesizes the full script as one audio file, and then proportionally stretches the estimated beats across the real audio duration.

This makes the total duration fit, but it does not establish where individual punchlines or pauses actually occur.

A POG attributed to beat 3 may belong to beat 2 or 4.

This directly underminuses your most important learning signal.

Fix: use word boundaries supplied by the TTS provider, forced alignment where appropriate, or synthesize independently timed beats with controlled silence. Mark the source of alignment and preserve uncertainty.

Do not treat proportionally stretched timing as ground truth.

### P0 — Strategy updates reward entire minutes, not individual jokes

Confirmed in `generate.py`, approximately lines 404–438.

The current `summarize_strategy()` treats an audition as successful when:

- Rating is at least `funny`; or
- The audition has at least two POGs.

It then increments success counts for all selected operators and modulators.

This is a credit-assignment problem.

If Nolan performs six beats using several techniques, and only one punchline is funny, the system can reward the entire creative configuration.

A weak 60-second set with two good moments may receive the same success classification as a consistently excellent performance.

Fix: preserve separate outcomes for the entire set, individual beats, delivery and audience engagement. Attach POGs to candidate beats probabilistically where timing is uncertain. Record which creative choices apply to each beat.

### P0 — Strategy history is overwritten

Confirmed in `audition/store.py`, approximately lines 53–59 and 209–219.

The `strategies` table has `character_id` as its primary key and uses an upsert to replace the existing version.

The version number changes, but older strategy contents are not retained in that table.

This means the repository cannot reliably reconstruct the strategy used for an older audition from its stored `strategy_version` alone.

Fix: make strategy versions immutable records with stable hashes, parent IDs, supporting evidence and approval status. Maintain a separate pointer to the current accepted strategy.

This is exactly where the concepts from `prx0r/cg` become useful.

## 3. The architecture you should converge on

The existing graph specification already distinguishes seeds, instances and performances. Preserve that. The main redesign is of the learning and evidence layer, not the character ontology.

Versioned Character Seed

General philosophy and enduring identity

Situated Character Instance

Scenario + emotional state + relevant memory + selected response

Comedic Decision and Performance

Theory operations + beat structure + delivery + audio

Observed Evidence

POGs + critique + validated alignment + later YouTube analytics

Memory and Strategy Revision

Callback opportunities + competing hypotheses + selected experiments

### The key: separate the actor from the comedy director

You want a character whose behaviour is internally consistent, but whose material selection improves over time.

Those are different decision problems.

|            | Actor policy                                             | Comedy director policy                                          |
| ---------- | -------------------------------------------------------- | --------------------------------------------------------------- |
| Objective  | Remain coherent as a character                           | Produce entertaining performances                               |
| Input      | Philosophy, emotional state, fictional history, scenario | Character, source material, comedy mechanisms, POGs and novelty |
| Output     | Appraisal, motivation, action, interpretation            | Which reactions and material to develop                         |
| Changes    | Slowly, through fictional experience                     | After performance evidence                                      |
| Evaluation | Character consistency                                    | Human laughter, overall quality, later retention                |

I would not build two separate agents yet. Make these two typed stages within the same generation pipeline.

The director proposes promising scenarios and experiments; the actor responds through its philosophy; the writer constructs the minute; delivery renders it.

This means the director can discover that self-deceptive rationalisation consistently works for Nolan without teaching Nolan that he is deliberately using self-deceptive rationalisation to make audiences laugh.

That distinction is essential for persistent character comedy.

## 4. Additional engineering concerns

These are worth addressing, but shouldn't distract from the core learning loop.

| Priority | Issue                                                                                                             | Recommendation                                                                                                  |
| -------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------- |
| High     | `/root/pogpet`, `/root/characters` and other absolute paths are embedded in generation/research code              | Resolve paths from configuration or repository roots; test in a fresh checkout                                  |
| High     | Background generation jobs live in the global `JOBS` dictionary and daemon threads                                | Persist job status and errors; restarting the server must not leave jobs permanently unresolved                 |
| High     | The offline generation fallback produces template material, while the real model path depends on `OPENAI_API_KEY` | Make provider and mode explicit; don't present placeholder material as model-generated comedy                   |
| High     | LLM beats are sliced to seven items and text is capped per beat                                                   | Validate complete structured output; reject invalid or truncated performances instead of quietly modifying them |
| Medium   | The current success heuristic mixes ratings and raw POG counts                                                    | Track exposures, playback iterations and confirmed reactions separately                                         |
| Medium   | `short_views` records private simulated short-form viewing behaviour                                              | Keep those events distinct from actual YouTube Analytics API data                                               |
| Medium   | Jev confidence thresholds decide some operators and modulators                                                    | Calibrate on reviewed labels; confidence isn't proof of comic quality                                           |
| Medium   | Human audio takes are stored, but speech-to-speech and facial retargeting aren't shown as completed integrations  | Keep them behind feature flags, after P0                                                                        |
| Medium   | The repository contains many generated performer packs with identically sized `set.wav` files                     | Audit these assets for placeholders before treating them as real rendered performances                          |
| Medium   | Runtime and tests assume specific neighbouring repositories                                                       | Add dependency checks, setup instructions and isolated fixtures                                                 |

One more issue in the existing prompt compiler: `build_context()` limits remembered material to three memories, truncates contextual fields and includes a direct audience critique. That can make recent feedback dominate the character's more enduring comedic history.

I'd replace this with a deliberate context retrieval policy: a compact recent summary, relevant older events, one or two promising strategy hypotheses, and a diversity/novelty constraint.

## 5. The Kill Tony research layer needs careful calibration

Your research output is already substantial. The repository contains a large `killtony-features.jsonl`, generated comedian profiles and individual minute files.

But the source code reveals some important limitations.

`research/kt_decode.py` uses deterministic text heuristics. For instance, it looks at punctuation, words like but, actually and because, and topic/authority vocabulary to infer mechanisms.

These can be useful candidate features, but they cannot reliably distinguish a true punchline from an ordinary explanatory sentence.

Similarly, `research/kt_personas.py` assigns broad persona attributes using aggregate operator and topic frequencies. It constructs descriptions such as a performer tending toward their most frequent mechanism.

That is not yet a reliable philosophical character model.

The research system needs three confidence levels:

- Observed: exact source, topic, performance, recorded audience reaction.
- Annotated: model- or rule-inferred mechanism, situation, delivery and persona.
- Validated: claims that survive human review or independent prediction tests.

Make sure `prx0r/characters` never promotes a low-confidence Kill Tony inference directly into the canonical identity of a performer or fictional character.

The scientifically interesting experiment is still worthwhile: multiple performers confronting comparable scenarios, producing distinct interpretations and receiving different responses.

But it needs stronger semantic annotation and controlled comparisons before the results should steer the generator.

## 6. What I'd retain, change and defer

| Component                                        | Decision                                                   |
| ------------------------------------------------ | ---------------------------------------------------------- |
| Existing Flask audition app                      | Retain                                                     |
| Existing POG UI and SQLite database              | Retain and strengthen                                      |
| Seed/instance/modulator architecture             | Retain                                                     |
| Theory registry shared with Pogpet               | Retain                                                     |
| Jev typed decision questions                     | Retain experimentally                                      |
| Current keyword-based Kill Tony prior weights    | Demote to weak priors                                      |
| Current feedback-to-strategy summarizer          | Replace                                                    |
| Three-latest-memory retrieval                    | Replace                                                    |
| Existing candidate battle generator              | Keep, then improve comparison protocol                     |
| CG content-addressed receipts and decision forks | Adapt minimal pieces                                       |
| MW observation/outcome separation                | Borrow schema principle                                    |
| Pi SDK integration                               | Defer until the POG feedback loop is reliably demonstrated |
| GEPA, LoRA, decision-model fine-tuning           | Defer                                                      |
| Atlas studio, Mixamo, facial capture             | Defer                                                      |

The battle generator deserves particular attention: you already have code for generating three candidates and choosing one through a model scoring process. That can be a useful experimental mechanism, but it must not become a self-confirming loop where the same LLM produces material, judges it, and then declares improvement.

Ideally you occasionally listen to blind A/B versions, with candidate identity hidden until after your preference is recorded.

# Full development instruction for the coding agent

This is the brief I'd give to the agent working inside `prx0r/characters`. It is intentionally ordered so that the first milestone is usable, rather than another comprehensive but unfinished framework.

# FREAKTOWN CHARACTERS — COMPREHENSIVE PEER REVIEW AND IMPLEMENTATION

Repository: `prx0r/characters`

## Mission

Turn the current audition prototype into a reliable, persistent, character-first comedy learning system.

Each character must:

1. Have a stable, general philosophical identity.
2. Interpret new situations through that identity.
3. Generate an original 45–60-second comedy performance.
4. Submit it for real human evaluation.
5. Receive timestamped POGs, ratings and critique.
6. Interpret the feedback without confusing correlations with proven causes.
7. Remember fictional events, recurring jokes, relationships and unresolved situations.
8. Make evidence-informed creative decisions about its next minute.
9. Retain its identity while improving its material.
10. Eventually consume published YouTube results without corrupting its private audition feedback.

Do not rewrite the application. Extend the current implementation incrementally.

## 0. First: audit the actual working tree

Inspect and run:

- `audition/app.py`
- `audition/generate.py`
- `audition/store.py`
- `audition/prompt.py`
- `audition/battle.py`
- `audition/jev_decide.py`
- `audition/jev_questions.py`
- `audition/tts_provider.py`
- `audition/test_audition.py`
- `research/kt_decode.py`
- `research/kt_personas.py`
- `SPEC-character-graph.md`

Inspect the relevant Pogpet/Freaktown source contracts and CG's receipt mechanism.

Run the existing tests before modifying code. Report actual results, failures and broken dependencies.

Verify the POG player works with a real generated audio file, not a silent placeholder.

Do not replace the current Flask frontend merely to standardise the stack.

## 1. Fix correctness bugs before adding features

### 1A. Scenario consistency

Currently, `app.py` may replace `gen["scenario"]` after generating the script.

Remove that behaviour.

A generation result must be internally consistent across:

- Scenario
- Source material
- Character interpretation
- Selected operator
- Beats
- Full script
- Audio
- Instance metadata

If a scenario must change, regenerate the entire instance.

Add regression tests verifying that scenario replacement cannot leave a mismatched script or decision.

### 1B. Audio and POG alignment

Do not pretend proportional beat scaling yields precise punchline timestamps.

Prefer actual TTS word boundaries or provider-supported timing metadata.

Where timing is unavailable, retain estimated timestamps and mark attribution uncertain.

Keep original POG timestamps as the source of truth.

Distinguish:

- Exact human click position
- Audio playback iteration
- Audio source/take
- Estimated associated beat
- Alignment confidence

Test POG attribution near beat boundaries, after seeking, and across repeated playbacks.

### 1C. Model output validation

Create a strict, versioned schema for generated minute output.

Validate:

- Nonempty meaningful beats
- Valid beat types
- Correct character and scenario IDs
- Duration expectations
- Reasonable text length
- Selected theory/operator references
- Required decision fields

Never silently truncate important text to obtain a superficially valid object.

Use bounded retries for invalid model output and report provider errors clearly.

### 1D. Job durability

Persist generation job states.

On restart, detect interrupted jobs and make them retryable.

Avoid relying solely on global process memory for job lifecycle.

## 2. Canonical character philosophy

Preserve the existing Seed → Instance → Performance architecture.

Create a validated, versioned character seed interface supporting:

- Ontology
- Epistemology
- Values and preferences
- Causal assumptions
- Agency model
- Self-concept
- Status and social orientation
- General motivations and fears
- Character contradictions
- Attention and interpretation biases
- Expression and emotional restraint
- Identity constraints
- Provenance

Do not require every character to populate every philosophical dimension.

The seed must be scenario-independent.

Do not hardcode a character's favourite jokes or specific source situations into its foundational philosophy.

Preserve existing Nolan, Ralph and Rudy data through compatible adapters.

Remove generic fallback motivations that silently make different characters alike. Missing values should be identified as unknown or supplied through explicit authoring.

Record seed content hashes in every completed audition.

Allow character changes only through versioned, reviewed revisions.

## 3. Make performances immutable experiments

Adapt the minimal useful design from `prx0r/cg`.

Every performance should pin:

- Unique performance ID
- Character and seed version/hash
- Current fictional state version
- Scenario and source IDs
- Creative strategy version/hash
- Decision policy version
- Selected theory IDs
- Operator IDs
- Modulator and delivery parameters
- Model/provider identifiers
- Prompt/compiler version
- Generation settings and seed
- Script and structured beats
- Audio asset hash
- Timing provenance
- Generation timestamp

Create a content-addressed manifest or equivalent receipt.

Do not require deterministic output from external LLMs.

Historical performances must remain intact even if the character, prompt or strategy evolves.

Maintain separate current-version pointers.

## 4. Replace strategy overwriting with version history

Current `strategies` upserts replace the previous strategy.

Migrate to append-only strategy versions.

Each version must record:

- Parent strategy version
- Evidence audition IDs
- Hypotheses being proposed
- Changes from previous strategy
- Selection preferences
- Known uncertainties
- Approval status
- Creation timestamp and content hash

Do not create separate repositories per character.

## 5. Build proper character memory

Implement structured memory records that distinguish:

### Canonical fictional events

Things established as having occurred in the character's fictional world.

### Proposed events

Possible fictional history produced during an audition, not yet approved as canon.

### Relationships

Other fictional entities, previous interactions and evolving tensions.

### Running gags

Recurring behavioural patterns or comedic misunderstandings.

### Callback opportunities

Prior events whose unresolved consequences could generate fresh material.

### Material history

Previously attempted jokes, premises, topics and mechanisms.

Each memory should contain:

- ID
- Character ID
- Type
- Description
- Source audition IDs
- First and last occurrence
- Canonical/proposed/rejected status
- Relevant entities
- Related scenario/theory IDs
- Callback attempts
- Evidence links

Preserve the full history. Do not only retrieve the last three text notes.

Create a retrieval function that can combine:

- Semantic relevance
- Shared entities
- Current scenario
- Unresolved consequences
- Character relationships
- Recency
- Novelty
- Callback freshness

Use SQLite FTS initially if appropriate.

Maintain separate current-version pointers.

Support:

- Accept
- Reject
- Revert
- Compare to baseline

Use Git for canonical seed and approved strategy files if useful, but keep high-volume observations and analytics in SQLite.

Do not create separate repositories per character.

## 6. Implement callback generation

A callback is not merely a repeated joke.

Require a callback candidate to contain:

1. Original fictional event or established running pattern.
2. Its original character interpretation.
3. The audience-facing contradiction.
4. The new scenario in which it becomes relevant.
5. The new consequence or reinterpretation.
6. Prior usage and freshness.
7. Proposed comic mechanism.

Create `propose_callbacks(character_id, scenario_id)`.

Return candidate callbacks and evidence, not an automatically inserted punchline.

Make the generator decide whether to use one.

Log actual callback use per performance.

Add a regression fixture containing 30 Nolan auditions.

Verify audition 31 can retrieve a relevant event from audition 4, use it in a new context, avoid the original punchline, and preserve continuity.

## 7. Separate actor decisions from director decisions

Implement two typed decision stages within the current generator.

### Actor decision

Given:

- Character philosophy
- Current fictional state
- New scenario
- Relevant memories

Produce:

- Interpretation
- Appraisal
- Perceived stakes
- Motivation
- Intended action
- Emotional state or shift
- Relevant identity contradiction

This must remain coherent with the character.

### Comedy director decision

Given:

- Character interpretation
- Scenario
- Prior audience evidence
- Comedy theory registry
- Callback candidates
- Freshness constraints

Produce:

- Candidate comic mechanisms
- Material-development objectives
- Candidate beat structures
- Creative experiment hypothesis
- Modulator/delivery proposal

The actor must not automatically become self-aware of the mechanism the director is exploiting.

Keep Jev's typed appraisal/choice machinery where it is useful. Jev is a classifier and chooser, not a substitute for actual audience results.

Do not train a separate decision model yet.

## 8. Improve performance evaluation

Replace binary `good`/`failed` operator counts with evidence-linked observations.

Separate:

- Overall human rating
- Raw POG count
- Distinct listening sessions
- Repeated playback reactions
- Validated beat-level POG attribution
- Textual critique
- Blind pairwise preference
- Candidate-generation history
- Script-level technique
- Delivery-level technique

Preserve each observation independently.

Do not automatically credit every operator in a minute for one successful punchline.

Provide concise character performance summaries with sample counts and uncertainties.

Use a simple contextual selection policy initially:

- Character
- Scenario family
- Modulator
- Operator
- Callback status
- Observed feedback

Log all candidate options and the selection probabilities when using randomised decisions, so future off-policy evaluation remains possible.

Do not report causal improvement from uncontrolled trials.

## 9. Make strategy reflection useful

After a user submits feedback:

1. Retrieve the completed performance and actual observations.
2. Identify potentially successful and unsuccessful beats.
3. Compare the results with the previous strategy's predictions.
4. Update the evidence record.
5. Identify unresolved uncertainty.
6. Propose a small strategy revision.
7. Record one controlled experiment for a future minute.

The character must distinguish:

- "The user laughed at this point"
- "The user said this joke was strong"
- "I hypothesise this mechanism caused the laugh"

These are not interchangeable statements.

Maintain character continuity separately from strategy optimisation.

Do not automatically modify the character seed.

## 10. Improve battle mode

Keep the existing candidate generation.

But do not equate an LLM-selected winner with genuine comedy improvement.

Store all proposed candidates and scores, including rejected ones.

Support blind human A/B listening.

Prefer comparisons where only one important creative factor changes.

Maintain a fixed baseline and occasionally test the adapted strategy against it using new scenarios.

Keep unsuccessful experiments as useful evidence.

## 11. Pi harness integration — only after the core loop works

Evaluate Pi as the orchestration shell for persistent character work.

Do not install a second full agent platform.

The character-specific information should remain in external, versioned files and database records.

The common agent rules should remain stable.

Expose tools such as:

- `read_character_seed`
- `read_current_state`
- `get_performance_brief`
- `search_character_memory`
- `propose_callbacks`
- `read_comedy_theory`
- `submit_minute`
- `get_feedback`
- `propose_strategy_revision`

Use a separate session per character as needed.

Do not rely on raw conversation history as canonical memory.

Do not rewrite the system prompt after every audition.

## 12. Research integration

Preserve the existing Kill Tony analyses.

Improve their provenance and confidence tracking.

Separate observed facts, heuristic classifications, model predictions and independently validated conclusions.

Do not derive permanent philosophical traits from one performance or a weak keyword match.

Add a small manually reviewed benchmark of sets representing several performers, scenarios and reaction levels.

Measure agreement and document uncertain classifications.

Use research outputs as weak creative priors, not guaranteed truths.

## 13. Prepare YouTube learning without building publishing

Define a `PublishedPerformanceMetrics` interface.

Link metrics to a completed performance, platform upload and collection timestamp.

Preserve separate:

- Internal POG events
- Private audition ratings
- YouTube retention
- YouTube engagement
- Comments and sentiment analysis
- Model-derived predictions

Do not merge all these into one synthetic laughter score.

Integration should eventually occur through `prx0r/influence`.

No social publishing automation in this phase.

## 14. Operational hygiene

- Remove hardcoded `/root/...` dependencies.
- Add reproducible environment setup.
- Keep credentials server-side.
- Validate file uploads and paths.
- Bound subprocess execution times.
- Avoid unbounded background thread growth.
- Use SQLite migrations with transactional safeguards.
- Enforce character ID isolation.
- Handle concurrent strategy changes safely.
- Preserve error details in logs without leaking credentials.
- Add unit, integration and end-to-end tests.

Do not delete existing research, canon or asset files.

## 15. Delivery milestones

### Milestone A — Reliable P0

Fix generation consistency, schema validation, audio alignment handling and runtime persistence.

Demonstrate one real minute, POG capture, critique and a subsequent minute.

### Milestone B — Thirty-performance memory

Use a realistic 30-audition fixture to demonstrate durable character memories, callback retrieval, strategy versioning and evidence-based decision selection.

### Milestone C — Human-tested improvement

Generate baseline and adapted material. Let a human blindly compare them. Record the results without fabricating progress.

### Milestone D — External analytics readiness

Expose read-only interfaces and schemas for eventual Influence/YouTube integration.

## Non-goals

Do not build:

- A new agent framework
- A graph database
- A generic RL training platform
- New character rendering infrastructure
- Atlas or Mixamo integration
- Autonomous publishing
- A social network
- A new standalone analytics dashboard

## Final acceptance criteria

Demonstrate Nolan performing 30 recorded audition trials and creating a 31st minute.

For audition 31, verify that the system:

- Loads the same canonical philosophy.
- Retrieves meaningful long-term history.
- Considers at least one valid callback.
- Chooses a new character-consistent interpretation.
- Generates fresh, coherent material.
- Records its creative decision and strategy version.
- Produces actual playable audio.
- Accepts a valid POG and human critique.
- Saves an evidence-linked strategy proposal.
- Can reproduce the historical performance record after restart.
- Does not claim improved humour without independent evidence.

Show the actual tests, outputs and runtime commands.

Do not mark the task complete when only the schemas, stubs or unit-test fixtures exist.

## Final recommendation

I would use the current `prx0r/characters` app as your primary audition engine rather than starting again.

The single most valuable feature to implement is not persistent chat, Git branches or automatic learning prompts. It is a searchable, evidence-linked history of character decisions and their comedic consequences.

Once that works, Pi becomes useful because the character can actively investigate its own past. CG becomes useful because you can compare exact strategy revisions. Jev becomes useful because you can classify decisions consistently. YouTube becomes useful because external audience reactions can inform which experiments the character tries next.

Without that foundation, all four just provide more elaborate ways of generating fresh jokes without learning.

Immediate engineering order: fix scenario integrity → preserve immutable strategy versions → improve timestamp alignment → build callback memory → demonstrate a real 30-to-31 performance progression.
