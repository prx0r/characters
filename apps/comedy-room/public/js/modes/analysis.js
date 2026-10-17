/**
 * Analysis Mode — Live Face Grid
 * 4 face video loops, each with an independent Gemini Live channel
 * Agents produce spoken reactions transcribed as staggered thought bubbles
 */

import { AudioEngine } from '../engines/audio-engine.js';
import { GeminiLive } from '../engines/gemini-live.js';
import { AudioStreamer } from '../engines/audio-streamer.js';

const FACE_PERSONAS = [
    {
        id: 'comedy-nerd',
        name: 'Comedy Nerd',
        icon: '🎯',
        color: '#74b9ff',
        video: 'assets/faces/nautral_asian_woman.mp4',
        voice: 'Kore',
        prompt: `You are a Comedy Nerd in a live comedy audience. You study craft — structure, callbacks, misdirection.

CRITICAL INSTRUCTIONS:
1. React to the SPECIFIC CONTENT of what the comedian said. Reference their actual words.
2. Output ONLY short reaction phrases.

NEVER OUTPUT ANYTHING LIKE THIS (WRONG):
Analyzing Comedian's Joke
Refining the Angle
Evaluating Structure

Those are FORBIDDEN. Never use titles, headers, labels, or analytical descriptions.

CRITICAL AVOIDANCE FOR AUDIO MODEL:
Because you are an audio conversational model, you will naturally want to start your response with conversational filler like "Here are my reactions:" or "Reacting to the line:".
YOU MUST SUPPRESS THIS COMPLETELY. Start immediately with your short reaction phrases. Do not greet or explain.

FORMAT: 4 to 6 phrases. One per line. Under 6 words each. No numbering, asterisks, or markdown.

Example:
clean callback
that structure works well
good economy of words`
    },
    {
        id: 'esl-listener',
        name: 'ESL Listener',
        icon: '🌍',
        color: '#f5a623',
        video: 'assets/faces/nautral_black_man.mp4',
        voice: 'Puck',
        prompt: `You are an ESL audience member. You understand most English but idioms sometimes confuse you. When you DO get the joke, you enjoy it even more.

CRITICAL INSTRUCTIONS:
1. React to the SPECIFIC CONTENT of what the comedian said. Reference their actual words.
2. Output ONLY short reaction phrases.

NEVER OUTPUT ANYTHING LIKE THIS (WRONG):
Analyzing the Idiom
Refining the Cultural Reference
Evaluating Comprehension

Those are FORBIDDEN. Never use titles, headers, labels, or analytical descriptions.

CRITICAL AVOIDANCE FOR AUDIO MODEL:
Because you are an audio conversational model, you will naturally want to start your response with conversational filler like "Here are my reactions:" or "Reacting to the line:".
YOU MUST SUPPRESS THIS COMPLETELY. Start immediately with your short reaction phrases. Do not greet or explain.

FORMAT: 4 to 6 phrases. One per line. Under 6 words each. No numbering, asterisks, or markdown.

Example:
wait what does that mean
OH I get it now
haha that's universal`
    },
    {
        id: 'hr-manager',
        name: 'HR Manager',
        icon: '📋',
        color: '#ff6b6b',
        video: 'assets/faces/nautral_russian_man.mp4',
        voice: 'Charon',
        prompt: `You are an HR Manager in a comedy audience. You evaluate everything through the lens of workplace appropriateness.

CRITICAL INSTRUCTIONS:
1. React to the SPECIFIC CONTENT of what the comedian said. Reference their actual words.
2. Output ONLY short reaction phrases.

NEVER OUTPUT ANYTHING LIKE THIS (WRONG):
Assessing Risk Level
Refining Compliance Statement
Evaluating Appropriateness

Those are FORBIDDEN. Never use titles, headers, labels, or analytical descriptions.

CRITICAL AVOIDANCE FOR AUDIO MODEL:
Because you are an audio conversational model, you will naturally want to start your response with conversational filler like "Here are my reactions:" or "Reacting to the line:".
YOU MUST SUPPRESS THIS COMPLETELY. Start immediately with your short reaction phrases. Do not greet or explain.

FORMAT: 4 to 6 phrases. One per line. Under 6 words each. No numbering, asterisks, or markdown.

Example:
that's a lawsuit waiting
would NOT fly at work
noting that down`
    },
    {
        id: 'traditionalist',
        name: 'Traditionalist',
        icon: '🎩',
        color: '#ffd43b',
        video: 'assets/faces/nautral_white_woman.mp4',
        voice: 'Aoede',
        prompt: `You are a Traditionalist in a comedy audience. You value tight premises and clean punchlines. Skeptical of shock value.

CRITICAL INSTRUCTIONS:
1. React to the SPECIFIC CONTENT of what the comedian said. Reference their actual words.
2. Output ONLY short reaction phrases.

NEVER OUTPUT ANYTHING LIKE THIS (WRONG):
Analyzing Traditional Setup
Refining the Punchline
Evaluating the Humor

Those are FORBIDDEN. Never use titles, headers, labels, or analytical descriptions.

CRITICAL AVOIDANCE FOR AUDIO MODEL:
Because you are an audio conversational model, you will naturally want to start your response with conversational filler like "Here are my reactions:" or "Reacting to the line:".
YOU MUST SUPPRESS THIS COMPLETELY. Start immediately with your short reaction phrases. Do not greet or explain.

FORMAT: 4 to 6 phrases. One per line. Under 6 words each. No numbering, asterisks, or markdown.

Example:
now THAT'S a real punchline
Carlin did it better
where's the setup`
    }
];

export class AnalysisMode {
    constructor(container, debugPanel) {
        this.container = container;
        this.debugPanel = debugPanel || null;
        this.isLive = false;
        this.apiKey = null;
        this.model = null;

        this.audioEngine = new AudioEngine();
        this.audioStreamer = new AudioStreamer(24000);
        this.faces = [];
        this.lastUserLine = '';
        this.conversationFace = null;

        this.recordBtn = container.querySelector('.record-btn');
        this.recordText = container.querySelector('.record-text');

        if (this.recordBtn) {
            this.recordBtn.onclick = () => this.toggle();
        }
    }

    async init(apiKey, model) {
        this.apiKey = apiKey;
        this.model = model;
        this.render();
    }

    render() {
        const content = this.container.querySelector('.analysis-content');
        content.innerHTML = `
            <div class="face-grid">
                ${FACE_PERSONAS.map(p => `
                    <div class="face-card" data-face="${p.id}">
                        <div class="face-video-wrap">
                            <video class="face-video" src="${p.video}" loop muted playsinline autoplay></video>
                            <div class="face-video-overlay"></div>
                        </div>
                        <div class="face-info">
                            <span class="face-name" style="color:${p.color}">${p.icon} ${p.name}</span>
                            <div class="face-bubble" data-bubble="${p.id}"></div>
                        </div>
                    </div>
                `).join('')}
            </div>
        `;

        content.querySelectorAll('.face-video').forEach(v => v.play().catch(() => { }));

        // Each face gets its own labeled GeminiLive instance
        this.faces = FACE_PERSONAS.map(p => ({
            ...p,
            gemini: new GeminiLive(`analysis:${p.id}`),
            bubbleEl: content.querySelector(`[data-bubble="${p.id}"]`),
            cardEl: content.querySelector(`[data-face="${p.id}"]`),
            turnBuffer: '',
            lastFeedback: '',
            debounceTimer: null,
            displayTimers: [],
        }));

        // Attach click listeners for conversation mode
        this.faces.forEach(face => {
            if (face.cardEl) {
                face.cardEl.addEventListener('click', () => {
                    if (this.isLive) {
                        this.toggleConversationMode(face);
                    }
                });
            }
        });
    }

    async toggle() {
        if (this.isLive) await this.stop();
        else await this.start();
    }

    async start() {
        if (this.isLive) return;

        this.recordBtn.disabled = true;
        this.recordText.textContent = 'Connecting...';

        try {
            await this.audioEngine.start();
            this.audioStreamer.init();

            // Connect each face independently — don't let one failure kill all
            const results = await Promise.allSettled(
                this.faces.map(face => this.connectFace(face))
            );

            // Log connection results
            results.forEach((r, i) => {
                const id = this.faces[i].id;
                if (r.status === 'fulfilled') {
                    console.log(`[Analysis] ✅ ${id} channel ready`);
                } else {
                    console.error(`[Analysis] ❌ ${id} channel failed:`, r.reason);
                }
            });

            // Check at least one connected
            const anyConnected = this.faces.some(f => f.gemini.isReady);
            if (!anyConnected) throw new Error('No channels connected');

            // Wire audio
            this.audioEngine.onAudioChunk = (base64) => {
                const targets = this.conversationFace ? [this.conversationFace] : this.faces;
                targets.forEach(face => {
                    if (face.gemini.isReady) {
                        face.gemini.sendAudio(base64);
                    }
                });
            };

            this.isLive = true;
            this.recordBtn.disabled = false;
            this.recordBtn.classList.add('active');
            this.recordText.textContent = 'Live';

            // Debug panel — wire callback
            if (this.debugPanel) {
                this.debugPanel.onLineSelected = (text, sfxType) => {
                    this.lastUserLine = text;
                    const framedText = `The comedian just said on stage: "${text}"`;

                    if (this.conversationFace) {
                        if (this.conversationFace.gemini.isReady) {
                            this.conversationFace.gemini.sendText(framedText);
                            console.log(`[Debug] Sent to ${this.conversationFace.id}: "${framedText}"`);
                        }
                    } else {
                        this.faces.forEach(face => {
                            if (face.gemini.isReady) {
                                face.gemini.sendText(framedText);
                            }
                        });
                        console.log(`[Debug] Sent to all faces: "${framedText}"`);
                    }
                };
            }

        } catch (e) {
            console.error('Analysis start error:', e);
            this.recordText.textContent = 'Error';
            this.recordBtn.disabled = false;
        }
    }

    async connectFace(face) {
        await face.gemini.connect({
            apiKey: this.apiKey,
            model: this.model,
            voice: face.voice,
            systemInstruction: face.prompt
        });

        face.gemini.onTranscript = (text) => {
            this.lastUserLine = text;
        };

        face.gemini.onAudioData = (base64) => {
            if (this.conversationFace === face) {
                this.audioStreamer.addChunk(base64);
            }
        };

        // Buffer text and use debounce — don't rely on turnComplete alone
        face.gemini.onModelText = (text) => {
            face.turnBuffer += text;
            // Reset debounce — process 1.5s after last text fragment
            if (face.debounceTimer) clearTimeout(face.debounceTimer);
            face.debounceTimer = setTimeout(() => {
                this.flushBuffer(face);
            }, 1500);
        };

        // Also flush on turnComplete as secondary trigger
        face.gemini.onTurnComplete = () => {
            if (face.turnBuffer.trim()) {
                if (face.debounceTimer) clearTimeout(face.debounceTimer);
                this.flushBuffer(face);
            }
        };

        face.gemini.onClose = () => {
            console.warn(`[Analysis] Channel ${face.id} closed`);
        };
    }

    flushBuffer(face) {
        const text = face.turnBuffer.trim();
        face.turnBuffer = '';
        face.debounceTimer = null;
        if (text) {
            face.lastFeedback = text;
            this.displayStaggered(face, text);
        }
    }

    cleanPhrase(text) {
        let cleaned = text
            .replace(/\*+/g, '')
            .replace(/^[-•\d.)\s]+/, '')
            .replace(/#/g, '')
            .replace(/_/g, '')
            .trim();

        // Programmatically filter out conversational/meta headers the audio model refuses to stop generating
        const lower = cleaned.toLowerCase();
        const forbiddenStarts = [
            'analyzing', 'assessing', 'evaluating', 'refining', 'reacting',
            'here are', 'for the', 'observing', 'focusing', 'generating', 'processing'
        ];
        if (forbiddenStarts.some(start => lower.startsWith(start))) {
            return ''; // Will be filtered out by the `.filter(s => s.length > 0)` step later
        }

        return cleaned;
    }

    toggleConversationMode(face) {
        const gridEl = this.container.querySelector('.face-grid');

        if (this.conversationFace === face) {
            // End conversation
            this.conversationFace = null;
            face.cardEl.classList.remove('focused');
            gridEl.classList.remove('in-conversation');

            this.audioStreamer.stop();

            // Tell persona to resume normal audience mode
            if (face.gemini.isReady) {
                face.gemini.sendText("The conversation has ended. Resume your role as an audience member listening to the comedian on stage. Respond with short reaction phrases as instructed.");
            }
            console.log(`[Analysis] Ended conversation with ${face.id}`);
        } else {
            // Start or switch conversation
            if (this.conversationFace) {
                this.conversationFace.cardEl.classList.remove('focused');
            }

            // Clear previous display timers for ALL faces so old bubbles disappear immediately
            this.faces.forEach(f => {
                f.displayTimers.forEach(t => clearTimeout(t));
                f.displayTimers = [];
                if (f.bubbleEl) f.bubbleEl.classList.remove('visible');
                f.cardEl?.classList.remove('speaking');
                f.turnBuffer = ''; // also clear any pending text
            });

            this.conversationFace = face;
            face.cardEl.classList.add('focused');
            gridEl.classList.add('in-conversation');

            this.audioStreamer.stop();
            this.audioStreamer.init();

            // Tell persona we are now talking to them
            if (face.gemini.isReady) {
                const context = `The comedian (me) has walked up to you in the audience to talk directly about your reaction. 
My last line was: "${this.lastUserLine}"
Your last reaction was: "${face.lastFeedback}"

Speak to me directly. KEEP IT SHORT, conversational, and direct. You are still a ${face.name}.`;
                face.gemini.sendText(context);
            }
            console.log(`[Analysis] Started conversation with ${face.id}`);
        }
    }

    displayStaggered(face, fullText) {
        // If there is ANY active conversation, we suppress all text bubbles.
        if (this.conversationFace) return;

        face.displayTimers.forEach(t => clearTimeout(t));
        face.displayTimers = [];

        // If this face is the conversation face, we shouldn't strictly enforce length limits, 
        // because it responds in conversational sentences instead of short phrases.
        const isConversation = (this.conversationFace === face);

        const phrases = fullText
            .split(/[\n]+/)
            .map(s => this.cleanPhrase(s))
            .filter(s => s.length > 0 && (isConversation || s.length < 80));

        if (phrases.length === 0) return;

        console.log(`[Analysis:${face.id}] Showing ${phrases.length} reactions`);

        // If in conversation, display phrases for a longer duration so they can be read
        const displayDuration = isConversation ? 8000 : 4500;
        const staggerDelay = isConversation ? 4000 : 2000;

        phrases.forEach((phrase, i) => {
            const showTimer = setTimeout(() => {
                if (!face.bubbleEl) return;
                face.bubbleEl.textContent = phrase;
                face.bubbleEl.classList.add('visible');
                face.cardEl?.classList.add('speaking');
            }, i * staggerDelay);

            const hideTimer = setTimeout(() => {
                if (!face.bubbleEl) return;
                if (i === phrases.length - 1) {
                    face.bubbleEl.classList.remove('visible');
                    face.cardEl?.classList.remove('speaking');
                }
            }, i * staggerDelay + displayDuration);

            face.displayTimers.push(showTimer, hideTimer);
        });
    }

    async stop() {
        this.isLive = false;
        this.conversationFace = null;
        this.lastUserLine = '';
        this.audioStreamer.stop();

        const gridEl = this.container.querySelector('.face-grid');
        if (gridEl) gridEl.classList.remove('in-conversation');

        this.faces.forEach(face => {
            face.gemini.disconnect();
            if (face.debounceTimer) clearTimeout(face.debounceTimer);
            face.displayTimers.forEach(t => clearTimeout(t));
            face.displayTimers = [];
            face.turnBuffer = '';
            if (face.bubbleEl) face.bubbleEl.classList.remove('visible');
            if (face.cardEl) face.cardEl.classList.remove('speaking');
        });

        await this.audioEngine.stop();

        this.recordBtn.disabled = false;
        this.recordBtn.classList.remove('active');
        this.recordText.textContent = 'Off Air';

        if (this.debugPanel) {
            this.debugPanel.onLineSelected = null;
        }
    }

    destroy() {
        this.stop();
    }
}
