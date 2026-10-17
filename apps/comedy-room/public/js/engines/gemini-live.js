/**
 * Gemini Live Engine — WebSocket connection to Gemini Live API
 * Handles connect, setup, message routing, teardown
 */

const HOST = 'generativelanguage.googleapis.com';
const VERSION = 'v1beta';

export class GeminiLive {
    constructor(label) {
        this.label = label || 'agent';
        this.ws = null;
        this.connected = false;
        this.ready = false;

        // Callbacks
        this.onToolCall = null;      // (functionCall) => void
        this.onTranscript = null;    // (text) => void
        this.onModelText = null;     // (text) => void — model text output (TEXT modality)
        this.onAudioData = null;     // (base64) => void
        this.onTurnComplete = null;  // () => void
        this.onReady = null;         // () => void
        this.onClose = null;         // () => void
    }

    /**
     * Connect to Gemini Live API
     * @param {Object} opts
     * @param {string} opts.apiKey
     * @param {string} opts.model
     * @param {string} opts.systemInstruction
     * @param {Array} [opts.tools] - Tool declarations
     * @param {string} [opts.voice] - Voice name (default: Puck)
     * @param {string[]} [opts.responseModalities] - default ['AUDIO']
     */
    connect(opts) {
        return new Promise((resolve, reject) => {
            const url = `wss://${HOST}/ws/google.ai.generativelanguage.${VERSION}.GenerativeService.BidiGenerateContent?key=${opts.apiKey}`;

            // Timeout: reject if setup doesn't complete within 15s
            const timeout = setTimeout(() => {
                console.warn(`[GeminiLive:${this.label}] Connection timeout`);
                this.disconnect();
                reject(new Error(`Connection timeout (${this.label})`));
            }, 15000);

            this.ws = new WebSocket(url);

            this.ws.onopen = () => {
                this.connected = true;

                const modalities = opts.responseModalities || ['AUDIO'];
                const genConfig = { responseModalities: modalities };

                // Only include speechConfig when AUDIO is a response modality
                if (modalities.includes('AUDIO')) {
                    genConfig.speechConfig = {
                        voiceConfig: {
                            prebuiltVoiceConfig: {
                                voiceName: opts.voice || 'Puck'
                            }
                        }
                    };
                }

                const setupMsg = {
                    setup: {
                        model: `models/${opts.model}`,
                        generationConfig: genConfig,
                        systemInstruction: {
                            parts: [{ text: opts.systemInstruction }]
                        },
                        inputAudioTranscription: {},
                        outputAudioTranscription: {}
                    }
                };

                if (opts.tools) {
                    setupMsg.setup.tools = opts.tools;
                }

                this.ws.send(JSON.stringify(setupMsg));
            };

            this.ws.onmessage = async (event) => {
                let data;
                try {
                    const text = event.data instanceof Blob
                        ? await event.data.text()
                        : event.data;
                    data = JSON.parse(text);
                } catch (e) {
                    console.error('GeminiLive: Parse error:', e);
                    return;
                }

                // Setup complete
                if (data.setupComplete) {
                    clearTimeout(timeout);
                    this.ready = true;
                    console.log(`[GeminiLive:${this.label}] ✅ Connected and ready`);
                    if (this.onReady) this.onReady();
                    resolve();
                    return;
                }

                // Tool calls — top-level
                if (data.toolCall?.functionCalls) {
                    data.toolCall.functionCalls.forEach(fc => {
                        if (this.onToolCall) this.onToolCall(fc);
                    });
                }

                // Tool calls — nested in modelTurn
                const parts = data.serverContent?.modelTurn?.parts;
                if (parts) {
                    for (const part of parts) {
                        if (part.functionCall) {
                            if (this.onToolCall) this.onToolCall(part.functionCall);
                        }
                        if (part.text) {
                            if (this.onModelText) this.onModelText(part.text);
                        }
                        if (part.inlineData?.mimeType?.startsWith('audio/')) {
                            if (this.onAudioData) this.onAudioData(part.inlineData.data);
                        }
                    }
                }

                // Input transcription (user speech)
                if (data.serverContent?.inputTranscription?.text) {
                    if (this.onTranscript) this.onTranscript(data.serverContent.inputTranscription.text);
                }

                // Output transcription (model speech → text)
                if (data.serverContent?.outputTranscription?.text) {
                    if (this.onModelText) this.onModelText(data.serverContent.outputTranscription.text);
                }

                // Turn complete
                if (data.serverContent?.turnComplete) {
                    if (this.onTurnComplete) this.onTurnComplete();
                }
            };

            this.ws.onerror = (e) => {
                clearTimeout(timeout);
                console.error(`[GeminiLive:${this.label}] WS error:`, e);
                reject(e);
            };

            this.ws.onclose = (event) => {
                clearTimeout(timeout);
                console.log(`[GeminiLive:${this.label}] Connection closed (code: ${event.code})`);
                this.connected = false;
                this.ready = false;
                if (this.onClose) this.onClose();
            };
        });
    }

    sendAudio(base64) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        this.ws.send(JSON.stringify({
            realtimeInput: {
                mediaChunks: [{
                    mimeType: 'audio/pcm;rate=16000',
                    data: base64
                }]
            }
        }));
    }

    sendText(text) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        this.ws.send(JSON.stringify({
            clientContent: {
                turns: [{ role: 'user', parts: [{ text }] }],
                turnComplete: true
            }
        }));
    }

    sendToolResponse(id, name, result) {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;
        this.ws.send(JSON.stringify({
            toolResponse: {
                functionResponses: [{
                    id: id || 'unknown-id',
                    name,
                    response: { result }
                }]
            }
        }));
    }

    disconnect() {
        this.connected = false;
        this.ready = false;
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    get isReady() {
        return this.connected && this.ready && this.ws?.readyState === WebSocket.OPEN;
    }
}
