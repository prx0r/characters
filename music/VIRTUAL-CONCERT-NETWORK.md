# The Virtual Concert Network — one engine, unlimited music nights
Yes. We can turn the Atlas world into a reusable virtual music venue, with animated performers, musical performances, audience reactions, cinematic cameras and different genres.
The important discovery is that your existing Freaktown performance architecture is already pointed in this direction. Instead of building another animation platform, we'd extend the performance system to understand musical events as well as dialogue.
One concert hall could host Chopin tonight, a virtual jazz trio tomorrow, an original AI rock band on Friday, and an electronic ambient performance over the weekend.
1. The venue formats I'd build


Classical Nights
Chopin, Beethoven, Bach, Liszt and Debussy. Dramatic pianist entrances, introductions, proper performances, close-ups of the keyboard, applause and composer histories.
First launch. Public-domain compositions give us an especially useful starting repertoire.





Midnight Jazz Club
An AI pianist, double bassist and drummer. Recurring musicians, late-night sessions, original improvisations, solos, audience applause.
Potentially the strongest recurring series, because performers can develop recognisable styles and relationships.





Rock Nights
Original virtual bands with stage identities, albums, rivalries, evolving sound and a persistent fan base.
This connects directly to your /characters system.





TONE/02 — Live Worlds
Original electronic, ambient, experimental and AI-generated music, each performance taking place in a different Atlas environment.
Here the world itself can become part of the performance.



These needn't be four YouTube channels immediately. I'd start with one virtual music venue brand, where each series gets its own stage design, identity and recurring programming. Separate the channels later if audiences turn out to be substantially different.
2. Copyright: what we can actually use
I checked YouTube's official guidance and the US Copyright Office.
Format	Rights position	Practical decision
Beethoven/Chopin original compositions	Generally public domain, subject to territory and edition	Start here
Our own performances of public-domain music	Usually viable with cleared scores, sounds and assets	Ideal
Original AI-generated jazz/rock	Viable if model terms and other rights permit	Ideal
Modern pop hits arranged as classical music	Underlying compositions generally still protected	Permission or eligible revenue sharing
Existing famous recordings	Separate sound-recording copyright	Avoid without clearance
A public-domain composition does not mean that every recording, arrangement or score edition of it is free. The US Copyright Office distinguishes the underlying musical work from an individual sound recording. 


U.S. Copyright Office
+1



For modern-song covers, YouTube allows some eligible cover videos to share ad revenue with music publishers, but it depends on the rights holders and the video's eligibility. An original piano arrangement doesn't automatically make the use copyright-free. Video synchronization and arrangement rights also matter. 


YouTube Help
+1



So we can experiment with classical versions of popular songs, but I would not make copyrighted covers the foundation of the business.
YouTube also explicitly says original AI-assisted content can qualify for monetization, while mass-produced, repetitive content may not. Disclose qualifying synthetic music and realistic generated performances as required. 


YouTube Community
+1



3. The exact animation stack — we already have most of it
I checked the actual files in prx0r/freaktown, not just the README.
Concert Show Director
Host introduction · applause · performer entrance · performance · finale
World layer
Atlas → Gaussian splat → Spark / Three.js


Performer layer
GLB/VRM → animation rigs → instrument interactions


Music layer
MIDI / original audio → instrument sound → event timeline


Production layer
Freaktown cameras + audio + transport + FFmpeg



One finished concert
16:9 YouTube show · 9:16 highlights · future actual livestream

The existing code we can reuse
Existing component	Concert adaptation
StageRuntime.ts	Load pianist, piano and venue
CameraDirector.ts	Keyboard overhead, pianist close-up, wide concert hall
AudioBus.ts	Music, host, audience applause, room ambience
Transport.ts	Shared clock for notes, animation and cameras
performance.v1	Extend with instrument and music events
/characters	Recurring musician identities and personality
Influence	Publishing, testing and audience analytics
I found that Freaktown already has VOICE, MUSIC, SFX and CROWD buses, and its CameraDirector already supports recorded camera cuts.
There is some integration debt: stage-runtime still imports app-specific Zustand state, and StageRuntime currently expects a single avatar/performance rather than a full band. Those are targeted extensions, not reasons to rebuild it.
Atlas is particularly suitable for this
World Labs provides an official world-generation and Three.js/Spark example.
We can generate an empty concert hall and place a separately rigged piano and performer on its stage. The environment is rendered as splats; the piano, hands, bodies, instruments and moving lights are ordinary animated 3D objects.
That separation is crucial. Don't bake the pianist or the piano into the generated world. They need to move and be replaceable.
World Labs explicitly supports exporting worlds as Gaussian splats for downstream use with Spark and Three.js. 


World Labs



4. The breakthrough: MIDI-controlled piano performance
I found three useful open-source projects, including one published just yesterday.
Hand-thesia 3D — MIDI to animated piano hands
Very relevant — Oct 11, 2026
Takes a MIDI file, creates planned finger motions, animates 3D hands and piano keys in Blender, renders piano audio with FluidSynth and exports video via FFmpeg.
It also includes a browser studio with camera and style controls.
Caveat: Early results have visible fingering and note-alignment problems, and full renders are computationally expensive. A reported 2.6-minute, 1080p/60fps example took roughly 6.5 hours on an RTX 4060. 


reddit.com






PianoMotion10M
This is the research-grade option: 116 hours of piano-playing video, roughly 10 million annotated hand poses, pretrained models and published code.
Particularly interesting for eventually producing realistic pianist motion from audio. The published experiments used an RTX 3090 Ti, so I wouldn't make this a prerequisite for the first show. 


GitHub





Blender MIDI Motion
A simpler addon that maps MIDI note events directly onto 3D objects and keyframes. Good for getting the correct piano keys moving immediately. It doesn't solve realistic hands. 


GitHub





What I'd implement first
Use a MIDI performance as the master musical event timeline.
For every note, we know its pitch, onset, release and velocity. That can control the corresponding piano key, drive the sound renderer and inform the pianist's hand animation.
The correct rendering priorities are:
1. Music sounds excellent, with expressive dynamics and phrasing.
2. All visible piano keys depress at the correct times.
3. Wrist and arm positions follow the musical register and phrasing.
4. Finger-to-key accuracy is added after the first three work.
That fourth step is genuinely hard. Music alone doesn't uniquely determine fingering, and a plausible animation can still be mechanically impossible.
For the first concert, I'd use a full-body pianist with mostly medium and wide shots, reserving keyboard close-ups for passages we've validated. We could later integrate the Hand-thesia finger planner into a GLB hand rig.
This gives us a deterministic music-performance engine, rather than hoping an image-to-video model guesses the correct piano notes.
For classical music I would also avoid generic low-quality synthesizer audio. The piano's tone, pedal, dynamics and reverb are central to the experience. Use a properly licensed quality piano sample library or instrument, render the performance, and synchronize the virtual player to that audio.
5. How we reuse the venue for other genres
The venue engine shouldn't care whether it's performing classical music, jazz or AI-generated rock. It should receive a performance score describing which musicians exist, what they play, how they move and what the cameras do.
Genre	Musical control	Animation approach
Classical piano	MIDI + expression/pedal	Exact keyboard + pianist rig
Jazz trio	Piano/bass/drum MIDI or aligned stems	Pianist, plucked bass, drum hits
Rock band	Original audio stems + beat/onset cues	Guitar strumming, drumming, singing
Electronic DJ	Audio + beat grid	Mixing controls, lighting, reactive environment
Ambient	Original audio + harmonic/energy analysis	Environment and lighting are the performer
Orchestra	Score/MIDI per instrument	Conducting and section-level motions first
Imagine the weekly programming
THE VIRTUAL MUSIC HALL
Example schedule

MON


Classical Nights
Bach — The Goldberg Variations


WED


Midnight Jazz
The house trio improvises


FRI


New Music Friday
Debut virtual artists and bands


SAT


Galactic Sessions
Electronic live sets in other worlds


SUN


The Music Explained
Harmony, geometry and composition



And the virtual artists could become a fascinating extension of your character system.
Instead of a character existing purely to perform jokes, an artist could have a persistent musical identity: favourite harmonic language, influences, instrument, recurring motifs, stage persona, previous releases and audience reception.
An AI jazz pianist develops a recognizable improvisational vocabulary. A rock band's sound changes over its albums. A virtual composer experiments with unfamiliar scales and tunings.
Those artists can even appear on Pogtown for interviews, arguments, collaborations or comedy.
The common denominator is an evolving performer, not a generated MP3.
6. The classical music analysis channel may be just as valuable
Your Dmitri Tymoczko idea is particularly strong here.
A visual example of voice leading

C majorA minor

Illustrative 12-tone pitch-class circle, not Tymoczko's full chord-space orbifold. Toggle between chords: two notes are shared while G moves to A.

The full system would be much richer:
- music21 parses scores, analyses chords, keys and Roman-numeral functions. 
  
  
  music21 Documentation
- Tymoczko's geometry represents relationships among chords, including voice-leading paths through higher-dimensional spaces. His software page includes a chord-graph explorer.
- Three.js renders interactive geometric visualisations synced to the musical score.
- An explanatory agent creates drafts of musical analysis, which we validate before publishing.
For a video titled Why Chopin's Harmony Feels Like Longing.
First, we hear the passage performed in our virtual concert hall. Then the scene transitions into a geometric representation of the chords: common tones remain in place, other voices move, harmonic tension builds and the music resolves.
Then we hear the same passage again, understanding something new.
This could become a standalone educational channel, but it also gives the concerts an optional Explain This Passage feature.
7. Recorded concerts first, actual live performances later
There's an important production distinction.
Phase 1 — Cinematic concerts
Fully pre-rendered and quality checked, then published as normal videos or YouTube Premieres. The concert looks like a live performance, but we clearly describe it as a virtual production.
Best for complex piano movement and excellent audio.



Phase 2 — Genuine live broadcasts
Freaktown's runtime plays the world and characters in real time. OBS streams the rendered stage to YouTube. Music events, camera changes and host interaction can be controlled live.
Live viewers might eventually influence the encore or request an improvisation.



Phase 3 — Interactive venue
Visitors enter the world as an audience, walk from different seats, talk to artists, experience spatial audio and interact with shows.
This connects to your longer-term Pogtown shared-world architecture.



8. What I would tell the coding agent to build now
Classical Nights P0
First milestone

One beautiful, five-minute virtual piano recital.
Suggested first piece: Bach's Prelude in C Major, BWV 846, using a checked public-domain source and a properly licensed sound library.

0 of 8 tasks complete
Reset


[ ] Create one Atlas concert hall with an unobstructed performance area and camera anchors.

[ ] Load a separately rigged GLB grand piano and pianist into the existing Three.js stage.

[ ] Import public-domain MIDI; render expressive, high-quality piano audio.

[ ] Make piano keys respond accurately to MIDI note-on and note-off events.

[ ] Animate seated posture, wrists, arms, pedal and basic finger positions.

[ ] Add Freaktown host introduction, musician entrance, applause and ending.

[ ] Extend CameraDirector for stage wide, side, keyboard overhead and pianist close-up.

[ ] Render one 16:9 concert and two 9:16 highlights; manually review all musical synchronisation.

 Copy developer brief
For repertoire, Mutopia is an especially useful source because it provides score files and MIDI with per-work licensing information. 


mutopiaproject.org



The long-term opportunity is to turn the venue into a virtual record label and performance studio. Musicians—human, AI-generated or hybrid—could acquire their own identities, release music, collaborate and perform in different Atlas worlds.
But the right first proof is simply watching a convincing pianist perform one beautiful piece, with properly synchronized music and cameras, in a venue we can reuse hundreds of times.
