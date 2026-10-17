export class AudioStreamer {
    constructor(sampleRate = 24000) {
        this.sampleRate = sampleRate;
        this.ctx = null;
        this.nextTime = 0;
        this.sources = [];
    }

    init() {
        if (!this.ctx) {
            this.ctx = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: this.sampleRate });
        }
    }

    addChunk(base64PCM) {
        if (!this.ctx) return;
        if (this.ctx.state === 'suspended') this.ctx.resume();

        const binaryStr = atob(base64PCM);
        const len = binaryStr.length;
        const bytes = new Uint8Array(len);
        for (let i = 0; i < len; i++) {
            bytes[i] = binaryStr.charCodeAt(i);
        }

        const data16 = new Int16Array(bytes.buffer);
        const audioBuffer = this.ctx.createBuffer(1, data16.length, this.sampleRate);
        const channelData = audioBuffer.getChannelData(0);
        for (let i = 0; i < data16.length; i++) {
            channelData[i] = data16[i] / 32768.0;
        }

        const source = this.ctx.createBufferSource();
        source.buffer = audioBuffer;
        source.connect(this.ctx.destination);

        const currentTime = this.ctx.currentTime;
        // Schedule audio carefully without stutter
        if (this.nextTime < currentTime) {
            this.nextTime = currentTime + 0.1; // Add small buffer if underrun
        }

        source.start(this.nextTime);
        this.nextTime += audioBuffer.duration;

        this.sources.push(source);
        source.onended = () => {
            const idx = this.sources.indexOf(source);
            if (idx > -1) this.sources.splice(idx, 1);
        };
    }

    stop() {
        this.sources.forEach(src => {
            try { src.stop(); } catch (e) { }
        });
        this.sources = [];
        this.nextTime = 0;
    }
}
