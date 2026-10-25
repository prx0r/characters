// node tally/test-sources.mjs : AT + D1-export vote merge (latest per voter per pair, cross-source dedup, events aliasing)
import { mergeVotes, eventsForTraining, fetchExport, voteWeight, ANON_W, LOW_WATCH_W } from './sources.mjs'
const fails = [], ok = (c, m) => { if (!c) fails.push(m); console.log((c ? 'PASS ' : 'FAIL ') + m) }
const byId = { A: {}, B: {}, C: {} }
const at = [{ did: 'did:plc:x', a: 'A', b: 'B', winner: 'A', createdAt: '2026-10-10T10:00:00.000Z', voter: 'human' }]
const d1 = [
  { voter: 'd1:aaaaaaaaaaaaaaaa', a: 'B', b: 'A', winner: 'A', createdAt: '2026-10-10T10:00:00.000Z' }, // same pick as the AT record: same person
  { voter: 'd1:aaaaaaaaaaaaaaaa', a: 'A', b: 'C', winner: 'C', createdAt: '2026-10-11T10:00:00.000Z' },
  { voter: 'd1:bbbbbbbbbbbbbbbb', a: 'A', b: 'B', winner: 'B', createdAt: '2026-10-10T09:00:00.000Z' },
  { voter: 'd1:bbbbbbbbbbbbbbbb', a: 'B', b: 'A', winner: 'A', createdAt: '2026-10-12T09:00:00.000Z' }, // re-vote: latest wins
  { voter: 'd1:cccccccccccccccc', a: 'A', b: 'Z', winner: 'A', createdAt: '2026-10-10T09:00:00.000Z' }, // unknown clip
  { voter: 'alice@example.com', a: 'A', b: 'B', winner: 'A', createdAt: '2026-10-10T09:00:00.000Z' }, // not a hashed voter
]
const m = mergeVotes(at, d1, byId)
ok(m.alias['d1:aaaaaaaaaaaaaaaa'] === 'did:plc:x', 'a D1 voter whose pick matches an AT record exactly is aliased to that DID')
ok(m.votes.filter((v) => v.did === 'did:plc:x').length === 2 && m.votes.filter((v) => v.did === 'did:plc:x' && v.a === 'A' && v.b === 'B' || v.did === 'did:plc:x' && v.a === 'B' && v.b === 'A').length === 1, 'the cross-source copy collapses into one vote; the other D1 vote joins the DID')
const b = m.votes.filter((v) => v.did === 'd1:bbbbbbbbbbbbbbbb')
ok(b.length === 1 && b[0].winner === 'A', 'latest vote per voter per pair')
ok(!m.votes.some((v) => v.b === 'Z' || v.did === 'alice@example.com'), 'unknown clips and non-hashed voters are dropped')
ok(m.votes.length === 3 && m.d1Voters['d1:bbbbbbbbbbbbbbbb'] === 1, `3 votes in total (${m.votes.length})`)
const ev = eventsForTraining([{ voter: 'd1:aaaaaaaaaaaaaaaa', kind: 'pass', a: 'A', b: 'C', createdAt: '2026-10-11T10:00:00.000Z', signals: { policy: { m: 'explore' } } }], m.alias)
ok(ev.length === 1 && ev[0].user === 'did:plc:x' && ev[0].signals.policy.m === 'explore', 'export events feed train-screening under the canonical voter')
// signed-out device votes: reduced weight, folded into the person when one of their picks matches a signed-in copy
{
  const T1 = '2026-10-13T10:00:00.000Z', T2 = '2026-10-13T11:00:00.000Z', T3 = '2026-10-13T12:00:00.000Z'
  const d1b = [{ voter: 'd1:eeeeeeeeeeeeeeee', a: 'A', b: 'B', winner: 'B', createdAt: T1 }, { voter: 'd1:ffffffffffffffff', a: 'A', b: 'C', winner: 'A', createdAt: T1, signals: { lowWatch: true } }]
  const anon = [
    { voter: 'dv:1111111111111111', a: 'B', b: 'A', winner: 'B', createdAt: T1 }, // same pick as d1:eeee -> that device is that person
    { voter: 'dv:1111111111111111', a: 'B', b: 'C', winner: 'C', createdAt: T2 }, // ... so this one counts at full weight under d1:eeee
    { voter: 'dv:2222222222222222', a: 'A', b: 'B', winner: 'A', createdAt: T2 },
    { voter: 'dv:2222222222222222', a: 'A', b: 'B', winner: 'B', createdAt: T3 }, // re-vote: latest wins (dedupe per device per pair)
    { voter: 'dv:2222222222222222', a: 'A', b: 'C', winner: 'C', createdAt: T2, basis: 'partial', signals: { lowWatch: true } }, // under-watched
    { voter: 'dv:3333333333333333', a: 'A', b: 'Z', winner: 'A', createdAt: T2 }, // unknown clip
    { voter: 'd1:4444444444444444', a: 'A', b: 'B', winner: 'A', createdAt: T2 }, // wrong prefix for the anon export
  ]
  const n = mergeVotes([], d1b, byId, { anonVotes: anon })
  ok(n.alias['dv:1111111111111111'] === 'd1:eeeeeeeeeeeeeeee', 'a device whose pick matches a signed-in copy exactly is aliased to that voter')
  const e = n.votes.filter((v) => v.did === 'd1:eeeeeeeeeeeeeeee')
  ok(e.length === 2 && e.every((v) => v.w === 1) && e.find((v) => v.a === 'A' && v.b === 'B' || v.a === 'B' && v.b === 'A').source === 'd1', `the copies collapse (signed-in copy kept) and the linked device's other pick counts in full (${JSON.stringify(e.map((v) => [v.source, v.w]))})`)
  const d2 = n.votes.filter((v) => v.did === 'dv:2222222222222222')
  ok(d2.length === 2 && d2.find((v) => v.b === 'B').winner === 'B', 'signed-out: latest pick per device per pair')
  ok(d2.find((v) => v.b === 'B').w === ANON_W && d2.find((v) => v.b === 'C').w === ANON_W * LOW_WATCH_W, `signed-out x${ANON_W}; signed-out + under-watched x${ANON_W * LOW_WATCH_W}`)
  ok(n.votes.find((v) => v.did === 'd1:ffffffffffffffff').w === LOW_WATCH_W, 'the under-watched half-weight rule still applies to signed-in votes')
  ok(!n.votes.some((v) => v.b === 'Z' || v.did === 'd1:4444444444444444' && v.source === 'anon'), 'anon rows: unknown clips and non-dv voters dropped')
  ok(n.anonVoters['dv:2222222222222222'] === 2 && !n.anonVoters['dv:1111111111111111'] && n.d1Voters['d1:eeeeeeeeeeeeeeee'] === 2, `voter counts: unlinked devices apart, linked device under its person (${JSON.stringify([n.anonVoters, n.d1Voters])})`)
  ok(voteWeight({ did: 'did:plc:x', basis: 'partial' }) === LOW_WATCH_W && voteWeight({ did: 'did:plc:x' }) === 1, 'AT records marked basis partial are half weight')
  const m0 = mergeVotes(at, d1, byId); ok(m0.votes.length === 3 && m0.votes.every((v) => v.w === 1), 'without signed-out votes nothing changes (all full weight)')
}
const pages = { '': { votes: [{ x: 1 }], next: 'c1' }, c1: { votes: [{ x: 2 }], next: null } }
const got = await fetchExport('https://api.test', 'votes', { fetchImpl: async (u) => ({ ok: true, json: async () => pages[new URL(u).searchParams.get('cursor') || ''] }) })
ok(got.length === 2, 'fetchExport follows the cursor')
console.log(fails.length ? `${fails.length} FAILED` : 'ALL PASS'); process.exit(fails.length ? 1 : 0)
