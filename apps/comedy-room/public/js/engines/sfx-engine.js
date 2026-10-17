/**
 * SFX Engine — Sound effect playback + one-shot visual triggers
 * Scoped to target DOM elements so multiple rooms can trigger independently
 */

// Type → audio file mapping
export const SFX_MAP = {
    big_laugh: 'assets/sfx/laugh_01.mp3',
    medium_laugh: 'assets/sfx/laugh_02.mp3',
    small_laugh: 'assets/sfx/laugh_03.mp3',
    big_oof: 'assets/sfx/oof_01.mp3',
    small_oof: 'assets/sfx/oof_02.mp3',
    clap: 'assets/sfx/clap_01.mp3',
    aww: 'assets/sfx/aww_01.mp3'
};

// Per-type visual + energy config
export const SFX_CONFIG = {
    small_laugh: { energy: 20, flash: 'flash-small_laugh', shake: null, zoom: 'zoom-small_laugh', bandHue: 210, duration: 400 },
    medium_laugh: { energy: 40, flash: 'flash-medium_laugh', shake: 'shake-medium_laugh', zoom: 'zoom-medium_laugh', bandHue: 35, duration: 600 },
    big_laugh: { energy: 70, flash: 'flash-big_laugh', shake: 'shake-big_laugh', zoom: 'zoom-big_laugh', bandHue: 320, duration: 800 },
    big_oof: { energy: 50, flash: 'flash-big_oof', shake: 'shake-big_oof', zoom: 'zoom-big_oof', bandHue: 15, duration: 550 },
    small_oof: { energy: 25, flash: 'flash-small_oof', shake: 'shake-small_oof', zoom: 'zoom-small_oof', bandHue: 25, duration: 450 },
    clap: { energy: 35, flash: 'flash-clap', shake: null, zoom: 'zoom-clap', bandHue: 50, duration: 400 },
    aww: { energy: 25, flash: 'flash-aww', shake: null, zoom: 'zoom-aww', bandHue: 330, duration: 800 }
};

export const SFX_TYPES = Object.keys(SFX_CONFIG);

export class SfxEngine {
    constructor() {
        this.audioContext = null;
        this.audioBuffers = {};
        this.loaded = false;
    }

    async init() {
        this.audioContext = new AudioContext({ sampleRate: 24000 });
        await this.preload();
    }

    async preload() {
        const entries = Object.entries(SFX_MAP);
        await Promise.all(entries.map(async ([type, file]) => {
            const resp = await fetch(file);
            const arrayBuf = await resp.arrayBuffer();
            this.audioBuffers[type] = await this.audioContext.decodeAudioData(arrayBuf);
        }));
        this.loaded = true;
    }

    /**
     * Trigger a sound effect + one-shot visual on target elements
     * @param {string} type - SFX type (e.g. 'big_laugh')
     * @param {Object} [targets] - DOM elements for visual effects
     * @param {HTMLElement} [targets.flash] - Flash overlay element
     * @param {HTMLElement} [targets.container] - Video container (shake)
     * @param {HTMLElement} [targets.video] - Video element (zoom)
     */
    trigger(type, targets = {}) {
        const config = SFX_CONFIG[type];
        if (!config) {
            console.warn(`SfxEngine: Unknown type: ${type}`);
            return;
        }

        this.playSound(type);

        if (targets.flash || targets.container || targets.video) {
            this.triggerVisual(type, config, targets);
        }

        return config;
    }

    playSound(type) {
        const buffer = this.audioBuffers[type];
        if (!buffer || !this.audioContext) return;

        const source = this.audioContext.createBufferSource();
        source.buffer = buffer;
        source.connect(this.audioContext.destination);
        source.start(0);
    }

    triggerVisual(type, config, { flash, container, video }) {
        const removeAfter = (el, cls, fallbackMs) => {
            const handler = () => {
                el.classList.remove(cls);
                el.removeEventListener('animationend', handler);
            };
            el.addEventListener('animationend', handler);
            setTimeout(() => el.classList.remove(cls), fallbackMs);
        };

        // Clear in-progress animations
        if (flash) {
            flash.className = 'sfx-flash';
            void flash.offsetWidth; // force reflow
            flash.classList.add(config.flash);
            removeAfter(flash, config.flash, config.duration + 50);
        }

        if (container && config.shake) {
            // Remove all shake classes first
            Object.values(SFX_CONFIG).forEach(c => {
                if (c.shake) container.classList.remove(c.shake);
            });
            void container.offsetWidth;
            container.classList.add(config.shake);
            removeAfter(container, config.shake, config.duration);
        }

        if (video && config.zoom) {
            Object.values(SFX_CONFIG).forEach(c => {
                if (c.zoom) video.classList.remove(c.zoom);
            });
            void video.offsetWidth;
            video.classList.add(config.zoom);
            removeAfter(video, config.zoom, config.duration);
        }
    }

    destroy() {
        if (this.audioContext) {
            this.audioContext.close();
            this.audioContext = null;
        }
        this.audioBuffers = {};
        this.loaded = false;
    }
}
