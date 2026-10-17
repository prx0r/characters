/**
 * Audio Engine — Mic capture via AudioWorklet
 * Shared across Performance and Compare modes
 */

const SAMPLE_RATE = 16000;

export class AudioEngine {
    constructor() {
        this.context = null;
        this.mediaStream = null;
        this.worklet = null;
        this.onAudioChunk = null; // callback(base64)
        this.running = false;
    }

    async start() {
        if (this.running) return;

        this.mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: SAMPLE_RATE,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true,
                autoGainControl: true
            }
        });

        this.context = new AudioContext({ sampleRate: SAMPLE_RATE });
        await this.context.audioWorklet.addModule('audio-processor.js');

        const source = this.context.createMediaStreamSource(this.mediaStream);
        this.worklet = new AudioWorkletNode(this.context, 'audio-processor');

        this.worklet.port.onmessage = (e) => {
            if (!this.running || !this.onAudioChunk) return;
            const pcm = this.floatToInt16(e.data);
            const base64 = this.toBase64(pcm.buffer);
            this.onAudioChunk(base64);
        };

        source.connect(this.worklet);
        this.running = true;
    }

    async stop() {
        this.running = false;

        if (this.mediaStream) {
            this.mediaStream.getTracks().forEach(t => t.stop());
            this.mediaStream = null;
        }

        if (this.context) {
            await this.context.close();
            this.context = null;
        }

        this.worklet = null;
    }

    floatToInt16(f32) {
        const i16 = new Int16Array(f32.length);
        for (let i = 0; i < f32.length; i++) {
            const s = Math.max(-1, Math.min(1, f32[i]));
            i16[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
        }
        return i16;
    }

    toBase64(buf) {
        const bytes = new Uint8Array(buf);
        let str = '';
        for (let i = 0; i < bytes.length; i++) str += String.fromCharCode(bytes[i]);
        return btoa(str);
    }
}
