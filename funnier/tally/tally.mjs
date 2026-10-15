// Funnier tally: discover voters via Jetstream, recount every vote from each voter's own PDS,
// compute Elo + Wilson for clips and comics. Node 22+ (global fetch + WebSocket). No deps.
// Usage: node tally.mjs <clips.json> <outdir>
import fs from 'node:fs'
import path from 'node:path'

const COLLECTION = 'io.github.prx0r.funnier.vote'
const [, , CLIPS_PATH, OUT] = process.argv
const DATA = path.join(OUT, 'data')
fs.mkdirSync(DATA, { recursive: true })
const clips = JSON.parse(fs.readFileSync(CLIPS_PATH, 'utf8'))
const byId = Object.fromEntries(clips.map((c) => [c.id, c]))
const statePath = path.join(DATA, 'state.json')
const state = fs.existsSync(statePath) ? JSON.parse(fs.readFileSync(statePath, 'utf8')) : { cursor: null, dids: [] }
const dids = new Set(state.dids)
for (const d of (process.env.EXTRA_DIDS || '').split(',').filter(Boolean)) dids.add(d.trim())

// 1. discover new voters from Jetstream (replay since last cursor)
async function discover() {
  const now = Date.now() * 1000
  const cursor = state.cursor || now - 72 * 3600 * 1e6
  const hosts = ['jetstream2.us-east.bsky.network', 'jetstream1.us-east.bsky.network', 'jetstream1.us-west.bsky.network']
  for (const h of hosts) {
    try {
      const last = await new Promise((resolve, reject) => {
        const ws = new WebSocket(`wss://${h}/subscribe?wantedCollections=${COLLECTION}&cursor=${cursor}`)
        let lastT = cursor, opened = false
        const done = () => { try { ws.close() } catch {} resolve(lastT) }
        const timer = setTimeout(done, 45000)
        ws.onopen = () => { opened = true }
        ws.onmessage = (m) => {
          const e = JSON.parse(typeof m.data === 'string' ? m.data : Buffer.from(m.data).toString())
          if (e.time_us) lastT = e.time_us
          if (e.kind === 'commit' && e.commit?.collection === COLLECTION) dids.add(e.did)
          if (e.time_us && e.time_us >= now) { clearTimeout(timer); done() }
        }
        ws.onerror = (err) => { clearTimeout(timer); opened ? done() : reject(err) }
      })
      // if we saw nothing, Jetstream sends nothing for a filtered collection: advance to "now" minus a safety margin
      state.cursor = Math.max(last, now - 10 * 60 * 1e6)
      console.log('jetstream ok', h, 'dids', dids.size)
      return
    } catch (e) { console.warn('jetstream fail', h, e?.message || e) }
  }
}

// 2. recount from each voter's PDS
async function pdsFor(did) {
  let doc
  if (did.startsWith('did:plc:')) doc = await (await fetch('https://plc.directory/' + did)).json()
  else if (did.startsWith('did:web:')) doc = await (await fetch(`https://${did.slice(8)}/.well-known/did.json`)).json()
  const svc = (doc?.service || []).find((s) => s.id === '#atproto_pds' || s.type === 'AtprotoPersonalDataServer')
  const handle = (doc?.alsoKnownAs || []).find((a) => a.startsWith('at://'))?.slice(5)
  return { pds: svc?.serviceEndpoint, handle }
}

async function recordsFor(did) {
  const { pds, handle } = await pdsFor(did)
  if (!pds) return { handle, recs: [] }
  const recs = []
  let cursor = ''
  for (let i = 0; i < 50; i++) {
    const u = `${pds}/xrpc/com.atproto.repo.listRecords?repo=${did}&collection=${COLLECTION}&limit=100${cursor ? '&cursor=' + cursor : ''}`
    const r = await (await fetch(u)).json()
    recs.push(...(r.records || []))
    if (!r.cursor || !(r.records || []).length) break
    cursor = r.cursor
  }
  return { handle, recs }
}

function wilson(w, n, z = 1.96) {
  if (!n) return 0
  const p = w / n, d = 1 + (z * z) / n
  return (p + (z * z) / (2 * n) - z * Math.sqrt((p * (1 - p) + (z * z) / (4 * n)) / n)) / d
}

await discover()
const votes = []
const voters = []
for (const did of dids) {
  try {
    const { handle, recs } = await recordsFor(did)
    const latest = new Map()
    for (const r of recs) {
      const v = r.value || {}
      if (!byId[v.a] || !byId[v.b] || v.a === v.b || (v.winner !== v.a && v.winner !== v.b)) continue
      const t = Date.parse(v.createdAt)
      if (!t || t > Date.now() + 5 * 60e3) continue
      const k = [v.a, v.b].sort().join('|')
      const prev = latest.get(k)
      if (!prev || t > Date.parse(prev.createdAt)) latest.set(k, { uri: r.uri, did, a: v.a, b: v.b, winner: v.winner, createdAt: v.createdAt })
    }
    if (latest.size) { voters.push({ did, handle, votes: latest.size }); votes.push(...latest.values()) }
  } catch (e) { console.warn('recount fail', did, e?.message || e) }
}
votes.sort((x, y) => Date.parse(x.createdAt) - Date.parse(y.createdAt))

const K = 32
const clipS = Object.fromEntries(clips.map((c) => [c.id, { id: c.id, elo: 1500, wins: 0, bouts: 0 }]))
const comicS = {}
const C = (n) => (comicS[n] ??= { comic: n, elo: 1500, wins: 0, bouts: 0 })
const step = (A, B, sa) => {
  const ea = 1 / (1 + 10 ** ((B.elo - A.elo) / 400))
  A.elo += K * (sa - ea); B.elo += K * ((1 - sa) - (1 - ea))
  A.bouts++; B.bouts++; (sa ? A : B).wins++
}
for (const v of votes) {
  const sa = v.winner === v.a ? 1 : 0
  step(clipS[v.a], clipS[v.b], sa)
  const ca = byId[v.a].comic, cb = byId[v.b].comic
  if (ca !== cb) step(C(ca), C(cb), sa)
}
const fin = (o) => ({ ...o, elo: Math.round(o.elo * 10) / 10, wilson: Math.round(wilson(o.wins, o.bouts) * 1000) / 1000 })
const board = {
  updated: new Date().toISOString(),
  collection: COLLECTION,
  votes: votes.length,
  voters: voters.length,
  comics: Object.values(comicS).map(fin).sort((a, b) => b.elo - a.elo),
  clips: Object.values(clipS).filter((c) => c.bouts).map(fin).sort((a, b) => b.elo - a.elo),
}
fs.writeFileSync(path.join(DATA, 'leaderboard.json'), JSON.stringify(board, null, 1))
fs.writeFileSync(path.join(DATA, 'votes.json'), JSON.stringify({ updated: board.updated, voters, votes }, null, 1))
state.dids = [...dids]
fs.writeFileSync(statePath, JSON.stringify(state))
console.log(`tallied ${votes.length} votes from ${voters.length} voters`)
