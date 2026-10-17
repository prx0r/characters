/**
 * Room Sense Live — Server
 * Static files + Config API
 */

import 'dotenv/config';
import express from 'express';
import { createServer } from 'http';
import { fileURLToPath } from 'url';
import { dirname, join } from 'path';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

const PORT = process.env.PORT || 3000;
const GEMINI_API_KEY = process.env.GEMINI_API_KEY;

if (!GEMINI_API_KEY) {
    console.error('ERROR: GEMINI_API_KEY environment variable is required');
    process.exit(1);
}

const app = express();
app.use(express.json({ limit: '50kb' }));
app.use(express.static(join(__dirname, 'public')));

// Config endpoint
app.get('/api/config', (req, res) => {
    res.json({
        apiKey: GEMINI_API_KEY,
        model: 'gemini-2.5-flash-native-audio-preview-12-2025'
    });
});



const server = createServer(app);

server.listen(PORT, () => {
    console.log(`[Room Sense Live] Running at http://localhost:${PORT}`);
});
