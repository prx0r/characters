-- Signed-out votes: a pick made without a session is stored against the browser's random device id (localStorage
-- funnier.device, the same id anonymous laughs use). Kept apart from votes (user rows) so the tally can down-weight
-- them and dedupe a device that later signs in. Idempotent.
--   npx wrangler d1 execute funnier --remote --file migrations/0012_anon_votes.sql
-- ip: first 16 hex of SHA-256(SESSION_SECRET + client IP), used only for the per-IP rate limit; never exported.
-- created_at: the client's pick time (clamped to now); received_at: server epoch ms of the last write (rate limits).
CREATE TABLE IF NOT EXISTS anon_votes (
  device TEXT NOT NULL,
  ip TEXT,
  a TEXT NOT NULL,
  b TEXT NOT NULL,
  winner TEXT NOT NULL,
  ms INTEGER,
  daily TEXT,
  signals TEXT,
  created_at TEXT NOT NULL,
  received_at INTEGER NOT NULL,
  UNIQUE (device, a, b)
);
CREATE INDEX IF NOT EXISTS anon_votes_device_rx ON anon_votes (device, received_at);
CREATE INDEX IF NOT EXISTS anon_votes_ip_rx ON anon_votes (ip, received_at);
CREATE INDEX IF NOT EXISTS anon_votes_created ON anon_votes (created_at);
