/**
 * Performance Mode — Full-screen immersive room
 * Minimal UI, only environmental feedback + subtitles
 */

import { AudioEngine } from '../engines/audio-engine.js';
import { GeminiLive } from '../engines/gemini-live.js';
import { EnergyEngine } from '../engines/energy-engine.js';
import { SfxEngine, SFX_CONFIG } from '../engines/sfx-engine.js';
import { SFX_TOOL } from '../config/personas.js';

export class PerformanceMode {
    constructor(container, sessionRecorder, debugPanel) {
        this.container = container;
        this.debugPanel = debugPanel || null;
        this.sessionRecorder = sessionRecorder;

        // Engines
        this.audioEngine = new AudioEngine();
        this.gemini = new GeminiLive();
        this.energyEngine = new EnergyEngine();
        this.sfxEngine = new SfxEngine();

        this.isLive = false;
        this.sfxAnimating = false;
        this.lastSfxType = null;
        this.apiKey = null;
        this.model = null;

        // DOM references
        this.recordBtn = container.querySelector('.record-btn');
        this.recordText = container.querySelector('.record-text');
        this.flashEl = container.querySelector('.sfx-flash');
        this.videoContainer = container.querySelector('.video-container');
        this.crowdVideo = container.querySelector('.crowd-video');
        this.videoOverlay = container.querySelector('.video-overlay');
        this.videoGlow = container.querySelector('.video-glow');
        this.energyBand = container.querySelector('.energy-band');

        // Bind
        if (this.recordBtn) {
            this.recordBtn.onclick = () => this.toggle();
        }
    }

    async init(apiKey, model) {
        this.apiKey = apiKey;
        this.model = model;
        await this.sfxEngine.init();

        // Autoplay video on load like analysis mode
        if (this.crowdVideo) {
            this.crowdVideo.play().catch(() => { });
        }

        // Energy → visuals
        this.energyEngine.onUpdate = (energy) => this.renderVisuals(energy);
        this.energyEngine.start();
    }

    async toggle() {
        if (this.isLive) {
            await this.stop();
        } else {
            await this.start();
        }
    }

    async start() {
        if (this.isLive) return;

        this.recordBtn.disabled = true;
        this.recordText.textContent = 'Connecting...';

        try {
            // Start video
            if (this.crowdVideo) {
                this.crowdVideo.play().catch(() => { });
            }

            // Start audio capture
            await this.audioEngine.start();

            // Connect Gemini
            await this.gemini.connect({
                apiKey: this.apiKey,
                model: this.model,
                voice: 'Puck',
                systemInstruction: `SYSTEM MODE: TOOL_USE_ONLY
ROLE: Crowd Reaction Bot.
INSTRUCTION: Listen to the audio stream. Trigger sound effects using the trigger_sfx tool.
WHEN TO TRIGGER:
- User says something funny → big_laugh, medium_laugh, or small_laugh (match intensity)
- User says something awkward/embarrassing → big_oof or small_oof
- User says something impressive/applause-worthy → clap
- User says something cute/sweet/touching → aww
- User explicitly says "This gets a [type]" before delivering a line → remember that reaction type and trigger it after the next spoken line finishes.
CONSTRAINTS:
- DO NOT SPEAK.
- DO NOT WRITE TEXT.
- YOU CAN ONLY CALL TOOLS.`,
                tools: [SFX_TOOL]
            });

            // Wire audio → gemini
            this.audioEngine.onAudioChunk = (base64) => {
                this.gemini.sendAudio(base64);
            };

            // Wire gemini → sfx
            this.gemini.onToolCall = (fc) => this.handleToolCall(fc);
            this.gemini.onTranscript = (text) => {
                this.energyEngine.markSpeech();
                if (this.sessionRecorder) {
                    this.sessionRecorder.recordEvent('transcript', { text });
                }
            };
            this.gemini.onClose = () => {
                if (this.isLive) this.stop();
            };

            // Reset session recorder
            if (this.sessionRecorder) {
                this.sessionRecorder.startSession('performance');
            }

            this.isLive = true;
            this.recordBtn.disabled = false;
            this.recordBtn.classList.add('active');
            this.recordText.textContent = 'Live';

            // Debug panel — send through Gemini with explicit type instruction
            if (this.debugPanel) {
                this.debugPanel.onLineSelected = (text, sfxType) => {
                    if (this.gemini.isReady) {
                        this.gemini.sendText(`This gets me a ${sfxType}. "${text}"`);
                        console.log(`[Debug] Sent via Gemini: this gets me a ${sfxType}`);
                    }
                };
            }

        } catch (e) {
            console.error('Performance start error:', e);
            this.recordText.textContent = 'Error';
            this.recordBtn.disabled = false;
        }
    }

    handleToolCall(fc) {
        if (fc.name !== 'trigger_sfx') return;
        const type = fc.args?.type || 'small_laugh';
        const config = SFX_CONFIG[type];
        if (!config) return;

        console.log(`[Performance] SFX: ${type}`);

        // Play + visuals
        this.sfxEngine.trigger(type, {
            flash: this.flashEl,
            container: this.videoContainer,
            video: this.crowdVideo
        });

        this.lastSfxType = type;
        this.energyEngine.addEnergy(config.energy);

        // Record event
        if (this.sessionRecorder) {
            this.sessionRecorder.recordEvent('sfx', {
                type,
                energy: config.energy
            });
        }

        // Respond to Gemini
        this.gemini.sendToolResponse(fc.id, fc.name, 'ok');
    }


    renderVisuals(energy) {
        const e = energy / 100;

        // Video filters
        const brightness = 1.0 + (e * 0.4);
        const contrast = 1.0 + (e * 0.2);
        const sepia = e * 0.3;

        if (this.crowdVideo) {
            this.crowdVideo.style.filter = `brightness(${brightness}) contrast(${contrast}) sepia(${sepia})`;

            // Ambient shake + scale (only when not doing one-shot SFX anim)
            if (!this.sfxAnimating) {
                const scale = 1.0 + (e * 0.1);
                let shakeX = 0, shakeY = 0;
                if (e > 0.4) {
                    const intensity = (e - 0.4) * 2 * 3;
                    shakeX = (Math.random() - 0.5) * intensity;
                    shakeY = (Math.random() - 0.5) * intensity;
                }
                this.crowdVideo.style.transform = `scale(${scale}) translate(${shakeX}px, ${shakeY}px)`;
            }
        }

        // Vignette
        if (this.videoOverlay) {
            const stop = 40 - (e * 30);
            const alpha = 0.6 + (e * 0.3);
            this.videoOverlay.style.background = `radial-gradient(circle, rgba(0,0,0,0) ${stop}%, rgba(0,0,0,${alpha}) 100%)`;
        }

        // Warm glow
        if (this.videoGlow) {
            let glowOp = 0;
            if (e > 0.6) {
                glowOp = (e - 0.6) / 0.4;
                if (e > 0.8 && Math.random() > 0.5) glowOp *= 0.6;
            }
            this.videoGlow.style.opacity = glowOp;
        }

        // Energy band
        if (this.energyBand) {
            const cfg = this.lastSfxType ? SFX_CONFIG[this.lastSfxType] : null;
            const hue = cfg ? cfg.bandHue : 210;
            const lightness = 20 + (e * 35);
            const alpha = 0.3 + (e * 0.55);
            this.energyBand.style.background = `linear-gradient(to top, hsla(${hue}, 100%, ${lightness}%, ${alpha}) 0%, rgba(0,0,0,0) 100%)`;
        }
    }

    async stop() {
        this.isLive = false;

        this.gemini.disconnect();
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
        this.energyEngine.stop();
        this.sfxEngine.destroy();
    }
}
