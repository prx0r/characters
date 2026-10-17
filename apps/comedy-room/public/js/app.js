/**
 * Room Sense Live — App Shell
 * Mode routing, session recording, bootstrap
 */

import { PerformanceMode } from './modes/performance.js';
import { CompareMode } from './modes/compare.js';
import { AnalysisMode } from './modes/analysis.js';
import { DebugPanel, isDebugMode } from './debug-panel.js';

/**
 * Session Recorder — Captures events during live sessions
 * Provides data to Analysis Mode
 */
class SessionRecorder {
    constructor() {
        this.reset();
    }

    reset() {
        this.mode = null;
        this.events = [];
        this.startTime = null;
        this.duration = 0;
        this.energyHistory = [];
        this.personaHistories = {};
        this.active = false;
    }

    startSession(mode) {
        this.reset();
        this.mode = mode;
        this.startTime = performance.now();
        this.active = true;
    }

    recordEvent(type, data) {
        if (!this.active) return;
        this.events.push({
            type,
            data,
            timestamp: (performance.now() - this.startTime) / 1000
        });
    }

    setEnergyHistory(history) {
        this.energyHistory = history;
    }

    setPersonaHistory(personaId, history) {
        this.personaHistories[personaId] = history;
    }

    endSession() {
        if (!this.active) return;
        this.duration = (performance.now() - this.startTime) / 1000;
        this.active = false;
    }

    getData() {
        return {
            mode: this.mode,
            events: this.events,
            duration: this.duration,
            energyHistory: this.energyHistory,
            personaHistories: this.personaHistories
        };
    }

    hasData() {
        return this.events.length > 0;
    }
}

/**
 * App Shell
 */
class App {
    constructor() {
        this.currentMode = null;
        this.apiKey = null;
        this.model = null;

        this.sessionRecorder = new SessionRecorder();
        this.debugPanel = isDebugMode() ? new DebugPanel() : null;

        // Mode instances
        this.modes = {};

        // Mode nav
        this.modeButtons = document.querySelectorAll('.mode-btn');
        this.modeContainers = {
            performance: document.getElementById('performance-mode'),
            compare: document.getElementById('compare-mode'),
            analysis: document.getElementById('analysis-mode')
        };

        // Bind mode switching
        this.modeButtons.forEach(btn => {
            btn.addEventListener('click', () => {
                const mode = btn.dataset.mode;
                this.switchMode(mode);
            });
        });

        this.boot();
    }

    async boot() {
        try {
            const res = await fetch('/api/config');
            const data = await res.json();
            this.apiKey = data.apiKey;
            this.model = data.model;

            await this.initModes();
            this.switchMode('performance');
        } catch (e) {
            console.error('Boot failed:', e);
        }
    }

    async initModes() {
        // Performance Mode
        const perfContainer = this.modeContainers.performance;
        if (perfContainer) {
            this.modes.performance = new PerformanceMode(perfContainer, this.sessionRecorder, this.debugPanel);
            await this.modes.performance.init(this.apiKey, this.model);
        }

        // Compare Mode
        const compContainer = this.modeContainers.compare;
        if (compContainer) {
            this.modes.compare = new CompareMode(compContainer, this.sessionRecorder, this.debugPanel);
            await this.modes.compare.init(this.apiKey, this.model);
        }

        // Analysis Mode
        const analysisContainer = this.modeContainers.analysis;
        if (analysisContainer) {
            this.modes.analysis = new AnalysisMode(analysisContainer, this.debugPanel);
            await this.modes.analysis.init(this.apiKey, this.model);
        }
    }

    switchMode(mode) {
        if (this.currentMode === mode) return;

        // Stop any active session in the mode we're leaving
        if (this.currentMode && this.modes[this.currentMode]) {
            const leaving = this.modes[this.currentMode];
            if (leaving.isLive) {
                leaving.stop();
            }
        }

        // Hide all containers
        Object.entries(this.modeContainers).forEach(([key, el]) => {
            if (el) el.classList.toggle('active', key === mode);
        });

        // Update nav
        this.modeButtons.forEach(btn => {
            btn.classList.toggle('active', btn.dataset.mode === mode);
        });

        this.currentMode = mode;
    }
}

// Boot
new App();

