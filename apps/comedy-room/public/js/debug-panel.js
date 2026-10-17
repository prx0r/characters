/**
 * Debug Panel — Predefined lines for testing reactions without a microphone
 * Enabled via ?debug=1 URL parameter
 */

const DEBUG_LINES = [
    { label: 'Clap', sfxType: 'clap', text: "Let's give it up for that." },
    { label: 'Aww', sfxType: 'aww', text: "I adopted the dog nobody else wanted." },
    { label: 'Big laugh', sfxType: 'big_laugh', text: "I paid for therapy just to complain about paying for therapy." },
    { label: 'Medium laugh', sfxType: 'medium_laugh', text: "I started meal prepping and now I just have five identical regrets in my fridge." },
    { label: 'Small laugh', sfxType: 'small_laugh', text: "I call it cardio, but it's mostly emotional." },
    { label: 'Big oof', sfxType: 'big_oof', text: "I texted 'love you' to my boss." },
    { label: 'Small oof', sfxType: 'small_oof', text: "I waved back at someone who wasn't waving at me." },
];

export function isDebugMode() {
    const params = new URLSearchParams(window.location.search);
    return params.get('debug') === '1';
}

export class DebugPanel {
    constructor() {
        this.onLineSelected = null; // (text, sfxType) => void
        this.panelOpen = false;

        // Badge
        this.badge = document.createElement('div');
        this.badge.className = 'debug-badge';
        this.badge.textContent = '🐛 DEBUG';
        document.body.appendChild(this.badge);

        // Lines button
        this.linesBtn = document.createElement('button');
        this.linesBtn.className = 'debug-lines-btn';
        this.linesBtn.textContent = 'Lines';
        this.linesBtn.onclick = () => this.togglePanel();
        document.body.appendChild(this.linesBtn);

        // Panel
        this.panel = document.createElement('div');
        this.panel.className = 'debug-panel';

        const heading = document.createElement('div');
        heading.className = 'debug-panel-heading';
        heading.textContent = 'Test Lines';
        this.panel.appendChild(heading);

        DEBUG_LINES.forEach(({ label, text, sfxType }) => {
            const item = document.createElement('button');
            item.className = 'debug-line-item';
            item.innerHTML = `<span class="debug-line-label">${label}</span><span class="debug-line-text">"${text}"</span>`;
            item.onclick = () => {
                if (this.onLineSelected) this.onLineSelected(text, sfxType);
                // Brief flash feedback
                item.classList.add('sent');
                setTimeout(() => item.classList.remove('sent'), 600);
            };
            this.panel.appendChild(item);
        });

        document.body.appendChild(this.panel);
    }

    togglePanel() {
        this.panelOpen = !this.panelOpen;
        this.panel.classList.toggle('open', this.panelOpen);
        this.linesBtn.classList.toggle('active', this.panelOpen);
    }

    show() {
        this.linesBtn.style.display = '';
        this.badge.style.display = '';
    }

    hide() {
        this.linesBtn.style.display = 'none';
        this.badge.style.display = 'none';
        this.panelOpen = false;
        this.panel.classList.remove('open');
        this.linesBtn.classList.remove('active');
    }

    destroy() {
        this.badge.remove();
        this.linesBtn.remove();
        this.panel.remove();
    }
}
