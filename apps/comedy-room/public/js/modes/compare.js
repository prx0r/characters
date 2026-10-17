/**
 * Compare Mode — Side-by-side persona rooms
 * Same mic feed, each room has an independent Gemini Live channel
 * that produces spoken reactions shown as scattered text bubbles
 */

import { AudioEngine } from '../engines/audio-engine.js';
import { GeminiLive } from '../engines/gemini-live.js';
import { PERSONAS, PERSONA_IDS } from '../config/personas.js';

const BUBBLE_SLOTS = 8;

export class CompareMode {
    constructor(container, sessionRecorder, debugPanel) {
        this.container = container;
        this.sessionRecorder = sessionRecorder;
        this.isLive = false;
        this.debugPanel = debugPanel || null;
        this.apiKey = null;
        this.model = null;

        this.audioEngine = new AudioEngine();
        this.rooms = {};

        this.recordBtn = container.querySelector('.record-btn');
        this.recordText = container.querySelector('.record-text');

        if (this.recordBtn) {
            this.recordBtn.onclick = () => this.toggle();
        }
    }

    async init(apiKey, model) {
        this.apiKey = apiKey;
        this.model = model;

        PERSONA_IDS.forEach(id => {
            const roomEl = this.container.querySelector(`[data-persona="${id}"]`);
            if (!roomEl) return;

            // Create bubble slots
            const bubbleEls = [];
            for (let i = 0; i < BUBBLE_SLOTS; i++) {
                const el = document.createElement('div');
                el.className = `room-bubble slot-${i}`;
                roomEl.appendChild(el);
                bubbleEls.push(el);
            }

            this.rooms[id] = {
                id,
                persona: PERSONAS[id],
                element: roomEl,
                // Each room gets its own labeled GeminiLive instance
                gemini: new GeminiLive(`compare:${id}`),
                video: roomEl.querySelector('.crowd-video'),
                bubbleEls,
                nextSlot: 0,
                // Text buffer + debounce
                turnBuffer: '',
                debounceTimer: null,
                displayTimers: [],
            };
        });

        // Autoplay all videos on load like analysis mode
        Object.values(this.rooms).forEach(room => {
            if (room.video) room.video.play().catch(() => { });
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

            Object.values(this.rooms).forEach(room => {
                if (room.video) room.video.play().catch(() => { });
            });

            // Connect each room independently — don't let one failure kill all
            const results = await Promise.allSettled(
                Object.values(this.rooms).map(room => this.connectRoom(room))
            );

            // Log connection results
            results.forEach((r, i) => {
                const id = Object.keys(this.rooms)[i];
                if (r.status === 'fulfilled') {
                    console.log(`[Compare] ✅ ${id} channel ready`);
                } else {
                    console.error(`[Compare] ❌ ${id} channel failed:`, r.reason);
                }
            });

            // Check at least one connected
            const anyConnected = Object.values(this.rooms).some(r => r.gemini.isReady);
            if (!anyConnected) throw new Error('No channels connected');

            // Wire audio → all connected rooms
            this.audioEngine.onAudioChunk = (base64) => {
                Object.values(this.rooms).forEach(room => {
                    if (room.gemini.isReady) {
                        room.gemini.sendAudio(base64);
                    }
                });
            };

            if (this.sessionRecorder) {
                this.sessionRecorder.startSession('compare');
            }

            this.isLive = true;
            this.recordBtn.disabled = false;
            this.recordBtn.classList.add('active');
            this.recordText.textContent = 'Live';

            // Debug panel — wire callback
            if (this.debugPanel) {
                this.debugPanel.onLineSelected = (text, sfxType) => {
                    const framedText = `The comedian just said on stage: "${text}"`;
                    Object.values(this.rooms).forEach(room => {
                        if (room.gemini.isReady) {
                            room.gemini.sendText(framedText);
                        }
                    });
                    console.log(`[Debug] Sent to all rooms: "${framedText}"`);
                };
            }

        } catch (e) {
            console.error('Compare start error:', e);
            this.recordText.textContent = 'Error';
            this.recordBtn.disabled = false;
        }
    }

    async connectRoom(room) {
        // NOTE: Do NOT use responseModalities: ['TEXT'] here.
        // It breaks the Gemini Live WebSocket connection (stuck on "Connecting...").
        // Gemini Live API requires AUDIO modality for streaming sessions.
        // Text reactions are captured via outputAudioTranscription instead.
        await room.gemini.connect({
            apiKey: this.apiKey,
            model: this.model,
            voice: room.persona.voice,
            systemInstruction: room.persona.comparePrompt
        });

        // Buffer text and use debounce to process — don't rely on turnComplete alone
        room.gemini.onModelText = (text) => {
            room.turnBuffer += text;
            // Reset debounce timer — process 1.5s after last text fragment
            if (room.debounceTimer) clearTimeout(room.debounceTimer);
            room.debounceTimer = setTimeout(() => {
                this.flushBuffer(room);
            }, 1500);
        };

        // Also flush on turnComplete as a secondary trigger
        room.gemini.onTurnComplete = () => {
            if (room.turnBuffer.trim()) {
                if (room.debounceTimer) clearTimeout(room.debounceTimer);
                this.flushBuffer(room);
            }
        };

        room.gemini.onClose = () => {
            console.warn(`[Compare] Channel ${room.id} closed`);
        };
    }

    flushBuffer(room) {
        const text = room.turnBuffer.trim();
        room.turnBuffer = '';
        room.debounceTimer = null;
        if (text) {
            this.displayScattered(room, text);
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

    displayScattered(room, fullText) {
        // Don't clear previous — let them overlap for density
        const phrases = fullText
            .split(/[\n]+/)
            .map(s => this.cleanPhrase(s))
            .filter(s => s.length > 0 && s.length < 60);

        if (phrases.length === 0) return;

        console.log(`[Compare:${room.id}] Showing ${phrases.length} reactions`);

        const staggerDelay = 800;
        const displayDuration = 5000;

        phrases.forEach((phrase, i) => {
            const slotIndex = (room.nextSlot + i) % BUBBLE_SLOTS;
            const bubbleEl = room.bubbleEls[slotIndex];

            const showTimer = setTimeout(() => {
                if (!bubbleEl) return;
                bubbleEl.textContent = phrase;
                bubbleEl.classList.add('visible');
            }, i * staggerDelay);

            const hideTimer = setTimeout(() => {
                if (!bubbleEl) return;
                bubbleEl.classList.remove('visible');
            }, i * staggerDelay + displayDuration);

            room.displayTimers.push(showTimer, hideTimer);
        });

        room.nextSlot = (room.nextSlot + phrases.length) % BUBBLE_SLOTS;
    }

    async stop() {
        this.isLive = false;

        Object.values(this.rooms).forEach(room => {
            room.gemini.disconnect();
            if (room.debounceTimer) clearTimeout(room.debounceTimer);
            room.displayTimers.forEach(t => clearTimeout(t));
            room.displayTimers = [];
            room.turnBuffer = '';
            room.bubbleEls.forEach(el => el.classList.remove('visible'));
        });

        await this.audioEngine.stop();

        this.recordBtn.disabled = false;
        this.recordBtn.classList.remove('active');
        this.recordText.textContent = 'Off Air';

        if (this.debugPanel) {
            this.debugPanel.onLineSelected = null;
        }

        if (this.sessionRecorder) {
            this.sessionRecorder.endSession();
        }
    }

    destroy() {
        this.stop();
    }
}
