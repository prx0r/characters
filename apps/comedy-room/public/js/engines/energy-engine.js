/**
 * Energy Engine — Continuous 0–100 room energy state
 * Each instance is independent (used per-room in Compare Mode)
 */

export class EnergyEngine {
    constructor() {
        this.currentEnergy = 0;
        this.targetEnergy = 0;
        this.lastSpeechTime = performance.now();
        this.lastTick = performance.now();
        this.running = false;
        this.rafId = null;

        // Callback: called every frame with current energy (0–100)
        this.onUpdate = null;

        // History for Analysis Mode
        this.history = [];       // { time, energy }
        this.startTime = null;
    }

    start() {
        if (this.running) return;
        this.running = true;
        this.startTime = performance.now();
        this.lastTick = performance.now();
        this.loop(performance.now());
    }

    stop() {
        this.running = false;
        if (this.rafId) {
            cancelAnimationFrame(this.rafId);
            this.rafId = null;
        }
    }

    reset() {
        this.currentEnergy = 0;
        this.targetEnergy = 0;
        this.history = [];
        this.startTime = null;
    }

    addEnergy(amount) {
        this.targetEnergy = Math.min(100, this.targetEnergy + amount);
    }

    markSpeech() {
        this.lastSpeechTime = performance.now();
    }

    loop(now) {
        if (!this.running) return;

        const dt = (now - this.lastTick) / 1000;
        this.lastTick = now;

        if (dt > 0.5) {
            // Prevent huge jumps if tab was backgrounded
            this.rafId = requestAnimationFrame((t) => this.loop(t));
            return;
        }

        // Decay logic
        const timeSinceSpeech = now - this.lastSpeechTime;
        let decayRate = 5; // base

        if (timeSinceSpeech < 2000) {
            decayRate = 2;   // slow decay while speaking
        } else if (timeSinceSpeech > 5000) {
            decayRate = 12;  // fast decay during silence
        }

        if (this.targetEnergy > 0) {
            this.targetEnergy -= decayRate * dt;
            if (this.targetEnergy < 0) this.targetEnergy = 0;
        }

        // Smoothing: fast attack, slow release
        if (this.targetEnergy > this.currentEnergy) {
            this.currentEnergy += (this.targetEnergy - this.currentEnergy) * 5 * dt;
        } else {
            this.currentEnergy += (this.targetEnergy - this.currentEnergy) * 2 * dt;
        }

        // Record history (sample every ~250ms)
        if (this.startTime && this.history.length === 0 ||
            (this.history.length > 0 && now - this.history[this.history.length - 1]._raw > 250)) {
            this.history.push({
                time: (now - this.startTime) / 1000, // seconds since start
                energy: Math.round(this.currentEnergy * 10) / 10,
                _raw: now
            });
        }

        if (this.onUpdate) {
            this.onUpdate(this.currentEnergy);
        }

        this.rafId = requestAnimationFrame((t) => this.loop(t));
    }

    getHistory() {
        return this.history.map(h => ({ time: h.time, energy: h.energy }));
    }
}
