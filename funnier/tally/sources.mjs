// Vote sources for the tally: AT Protocol records (Bluesky sign-in, read from each voter's PDS) + the Worker's public,
// anonymised D1 export (Google sign-in: GET <api>/export/votes and /export/events, voter = 'd1:<salted hash>').
// mergeVotes: one canonical voter per person, the latest vote per voter per pair. A person who used both sources is
// detected when a D1 vote is the same pick (pair, winner, createdAt to the ms) as one of their AT records (the client
// sends a vote to both when signed in to both): that D1 voter is aliased to the DID, so the copies collapse into one.
// Signed-out votes (GET <api>/export/anon, voter = 'dv:<salted hash of the device id>') join at reduced weight; a device
// whose pick matches a signed-in copy exactly (pair, winner, createdAt to the ms: the client re-sends its local picks after
// sign-in) is aliased to that person, so the copies collapse and its other picks count at full weight.
const pk = (a, b) => [a, b].sort().join('|')
export const ANON_W = 0.5 // a signed-out device counts half as much as a signed-in person
export const LOW_WATCH_W = 0.5 // picked before both clips were watched enough (client lowWatch / basis 'partial'): half weight
// tally weight of one merged vote; anon applies only while the voter is still an unlinked device
export function voteWeight(v) {
  let w = 1
  if (v && typeof v.did === 'string' && v.did.startsWith('dv:')) w *= ANON_W
  if (v && (v.basis === 'partial' || v.signals?.lowWatch === true)) w *= LOW_WATCH_W
  return w
}
const SRC_RANK = { atproto: 0, d1: 1, anon: 2 } // on an exact tie the more accountable copy is kept

export async function fetchExport(base, kind = 'votes', { since = '', maxPages = 200, fetchImpl = fetch } = {}) {
  const out = []
  let cursor = ''
  for (let i = 0; i < maxPages; i++) {
    const u = `${base.replace(/\/$/, '')}/export/${kind}?limit=1000${since ? '&since=' + encodeURIComponent(since) : ''}${cursor ? '&cursor=' + encodeURIComponent(cursor) : ''}`
    const r = await fetchImpl(u)
    if (!r.ok) throw new Error(`export ${kind} ${r.status}`)
    const j = await r.json()
    out.push(...(Array.isArray(j[kind]) ? j[kind] : []))
    if (!j.next) break
    cursor = j.next
  }
  return out
}

// atVotes: [{did, a, b, winner, createdAt, voter: 'human'|'agent', ...}]  d1Votes: export rows [{voter, a, b, winner, createdAt, ms, daily, signals}]
// byId: clip lookup (unknown clips dropped). Returns { votes, alias, d1Voters }
export function mergeVotes(atVotes, d1Votes, byId, { now = Date.now(), anonVotes = [] } = {}) {
  const atKey = new Map()
  for (const v of atVotes) atKey.set(pk(v.a, v.b) + '|' + v.winner + '|' + Date.parse(v.createdAt), v.did)
  const alias = {}
  const d1 = []
  for (const x of d1Votes || []) {
    if (!x || typeof x.voter !== 'string' || !/^d1:[0-9a-f]{8,64}$/.test(x.voter)) continue
    if (!byId[x.a] || !byId[x.b] || x.a === x.b || (x.winner !== x.a && x.winner !== x.b)) continue
    const t = Date.parse(x.createdAt); if (!t || t > now + 5 * 60e3) continue
    const did = atKey.get(pk(x.a, x.b) + '|' + x.winner + '|' + t)
    if (did) alias[x.voter] = did
    d1.push({ did: x.voter, voter: 'human', source: 'd1', a: x.a, b: x.b, winner: x.winner, createdAt: new Date(t).toISOString(),
      ...(Number.isInteger(x.ms) && x.ms >= 0 && x.ms <= 3600000 ? { ms: x.ms } : {}), ...(typeof x.daily === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x.daily) ? { daily: x.daily } : {}),
      ...(x.signals && typeof x.signals === 'object' ? { signals: x.signals } : {}) })
  }
  // signed-out device votes: same row checks; a device with any pick identical to a signed-in one is that person
  const d1Key = new Map()
  for (const v of d1) d1Key.set(pk(v.a, v.b) + '|' + v.winner + '|' + Date.parse(v.createdAt), alias[v.did] || v.did)
  const anon = []
  for (const x of anonVotes || []) {
    if (!x || typeof x.voter !== 'string' || !/^dv:[0-9a-f]{8,64}$/.test(x.voter)) continue
    if (!byId[x.a] || !byId[x.b] || x.a === x.b || (x.winner !== x.a && x.winner !== x.b)) continue
    const t = Date.parse(x.createdAt); if (!t || t > now + 5 * 60e3) continue
    const kk = pk(x.a, x.b) + '|' + x.winner + '|' + t, who = atKey.get(kk) || d1Key.get(kk)
    if (who) alias[x.voter] = who
    anon.push({ did: x.voter, voter: 'human', source: 'anon', a: x.a, b: x.b, winner: x.winner, createdAt: new Date(t).toISOString(),
      ...(x.basis === 'partial' ? { basis: 'partial' } : {}),
      ...(Number.isInteger(x.ms) && x.ms >= 0 && x.ms <= 3600000 ? { ms: x.ms } : {}), ...(typeof x.daily === 'string' && /^\d{4}-\d{2}-\d{2}$/.test(x.daily) ? { daily: x.daily } : {}),
      ...(x.signals && typeof x.signals === 'object' ? { signals: x.signals } : {}) })
  }
  const latest = new Map()
  for (const v of [...atVotes.map((v) => ({ ...v, source: v.source || 'atproto' })), ...d1, ...anon]) {
    const who = alias[v.did] || v.did, k = who + '|' + pk(v.a, v.b), prev = latest.get(k)
    // the latest pick wins; on an exact tie the AT record (public, signed) beats D1, which beats a signed-out copy
    if (!prev || Date.parse(v.createdAt) > Date.parse(prev.createdAt) || (Date.parse(v.createdAt) === Date.parse(prev.createdAt) && (SRC_RANK[v.source] ?? 0) < (SRC_RANK[prev.source] ?? 0))) latest.set(k, { ...v, did: who })
  }
  const votes = [...latest.values()]
  for (const v of votes) v.w = voteWeight(v)
  const d1Voters = {}, anonVoters = {}
  for (const v of votes) { const d = String(v.did); if (d.startsWith('dv:')) anonVoters[v.did] = (anonVoters[v.did] || 0) + 1; else if (d.startsWith('d1:')) d1Voters[v.did] = (d1Voters[v.did] || 0) + 1 }
  return { votes, alias, d1Voters, anonVoters }
}

// export events -> train-screening sessions input ({user, kind, a, b, at, signals}); aliased like the votes
export function eventsForTraining(d1Events, alias = {}) {
  return (d1Events || []).filter((e) => e && ['pass', 'skip'].includes(e.kind) && typeof e.voter === 'string' && e.a && e.b && Date.parse(e.createdAt))
    .map((e) => ({ user: alias[e.voter] || e.voter, kind: e.kind, a: e.a, b: e.b, at: e.createdAt, ...(typeof e.clip === 'string' ? { clip: e.clip } : {}), signals: e.signals && typeof e.signals === 'object' ? e.signals : {} }))
}
