import { BrowserOAuthClient } from '@atproto/oauth-client-browser'

const COLLECTION = 'io.github.prx0r.funnier.vote'
const BASE = new URL('.', location.href).href.replace(/#.*$/, '')
const IS_LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname)
const $ = (s) => document.querySelector(s)
const LS = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem('funnier.' + k)) ?? d } catch { return d } },
  set: (k, v) => localStorage.setItem('funnier.' + k, JSON.stringify(v)),
}

let CLIPS = [], BYID = {}, BOARD = null, PAIRS = [], COMICS = {}, PUBVOTES = []
let LANE = LS.get('lane', 'human'), BOARDKIND = 'all'
const SHORT_MAX = 75 // seconds of each clip we screen when the clip is longer
let client = null, agent = null, me = null
let current = null

// ---------- data ----------
async function loadData() {
  CLIPS = (await (await fetch('clips.json', { cache: 'no-cache' })).json()).filter((c) => c.status !== 'removed')
  BYID = Object.fromEntries(CLIPS.map((c) => [c.id, c]))
  try { BOARD = await (await fetch('data/leaderboard.json', { cache: 'no-cache' })).json() } catch { BOARD = null }
  try { COMICS = (await (await fetch('comics.json', { cache: 'no-cache' })).json()).comics || {} } catch { COMICS = {} }
  try { PUBVOTES = (await (await fetch('data/votes.json', { cache: 'no-cache' })).json()).votes || [] } catch { PUBVOTES = [] }
  try { PAIRS = (await (await fetch('data/pairs.json', { cache: 'no-cache' })).json()).pairs || [] } catch { PAIRS = [] }
}

// ---------- auth (AT Protocol OAuth) ----------
async function initAuth() {
  try {
    client = await BrowserOAuthClient.load({
      clientId: IS_LOCAL ? undefined : BASE + 'client-metadata.json',
      handleResolver: 'https://bsky.social',
    })
    const r = await client.init()
    if (r?.session) {
      agent = r.session
      me = { did: r.session.sub, handle: r.session.sub }
      try {
        const p = await (await fetch('https://public.api.bsky.app/xrpc/app.bsky.actor.getProfile?actor=' + me.did)).json()
        if (p.handle) me.handle = p.handle
      } catch {}
      await flushQueue()
    }
  } catch (e) { console.warn('auth init', e) }
  paintAuth()
}

function paintAuth() {
  const box = $('#auth')
  if (me) {
    box.innerHTML = `<span class="who">@${esc(me.handle)}</span><button id="signout" class="ghost">Sign out</button>`
    $('#signout').onclick = async () => { try { await client.revoke(me.did) } catch {} me = null; agent = null; paintAuth(); paintBanner() }
  } else {
    box.innerHTML = `<form id="signin"><input id="handle" placeholder="you.bsky.social" autocomplete="username" required><button>Sign in with Bluesky</button></form>`
    $('#signin').onsubmit = async (e) => {
      e.preventDefault()
      const h = $('#handle').value.trim().replace(/^@/, '')
      if (!h) return
      try { await client.signIn(h, { scope: 'atproto transition:generic' }) }
      catch (err) { toast('Sign-in failed: ' + (err.message || err)) }
    }
  }
  paintBanner()
}

function paintBanner() {
  const q = LS.get('queue', [])
  const b = $('#banner')
  if (me) b.innerHTML = q.length ? `Publishing ${q.length} pick(s)…` : `Your picks count on the global chart.`
  else b.innerHTML = `Your picks train your own model on this device. <b>Sign in with Bluesky</b> to count them on the global chart too${q.length ? ` (${q.length} waiting)` : ''}.`
}

async function publish(v) {
  const res = await agent.fetchHandler('/xrpc/com.atproto.repo.createRecord', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ repo: me.did, collection: COLLECTION,
      record: { $type: COLLECTION, a: v.a, b: v.b, winner: v.winner, voter: 'human', basis: v.basis || 'watched', ...(v.why ? { why: v.why } : {}), ...(Number.isInteger(v.decisionMs) ? { ms: v.decisionMs } : {}), createdAt: v.createdAt } }),
  })
  if (!res.ok) throw new Error('createRecord ' + res.status + ' ' + (await res.text()))
}

async function flushQueue() {
  let q = LS.get('queue', [])
  while (q.length && agent) {
    try { await publish(q[0]); q.shift(); LS.set('queue', q) } catch (e) { console.warn(e); break }
  }
  paintBanner()
}

// ---------- shared ----------
function pairKey(a, b) { return [a, b].sort().join('|') }
const sig = (x) => 1 / (1 + Math.exp(-x))
const SCALE = 400 / Math.LN10
const LATE_NIGHT = /coco|letterman|tonight|late/i
function bumpSeen(...ids) { const s = LS.get('seen', {}); ids.forEach((i) => (s[i] = (s[i] || 0) + 1)); LS.set('seen', s) }

// ---------- implicit signals -> confidence weight per pick ----------
// decisionMs runs from the moment the Funnier buttons appear to the click.
// <1.5s = snap pick (x1.25), >12s = hesitant (x0.7), otherwise x1.0.
// Picking clip ONE in under 3s while less than 60% of clip TWO was watched = strong (x1.4): you didn't need the rest.
// Old picks without signals keep weight 1.
const SNAP_MS = 1500, SLOW_MS = 12000, LS_WIN_W = 1.2, LS_LOSE_W = 0.6
function timingWeight(v) {
  const ms = v && v.decisionMs
  if (!Number.isFinite(ms)) return 1
  let w = ms < SNAP_MS ? 1.25 : ms > SLOW_MS ? 0.7 : 1
  if (v.winner === v.a && ms < 3000 && Number.isFinite(v.rightFrac) && v.rightFrac < 0.6) w = Math.max(w, 1.4)
  return w
}
function voteWeight(v) {
  let w = timingWeight(v)
  // "Not funny -> next" on clip ONE, then a vote: picking clip TWO confirms it (x1.2), picking ONE anyway is a soft pick (x0.6).
  // Skipping clip TWO to the ballot is the mirror image.
  if (v && v.leftSkipped && !v.rightSkipped) w = v.winner === v.b ? Math.max(w, LS_WIN_W) : Math.min(w, LS_LOSE_W)
  else if (v && v.rightSkipped && !v.leftSkipped) w = v.winner === v.a ? Math.max(w, LS_WIN_W) : Math.min(w, LS_LOSE_W)
  return w
}

// Skips: leaving during a comic's clip = weak negative (SKIP_W = 0.3 of a pick) for that clip, its comic and its style tags.
// Skips during the intro or the ballot, and 3-second passes, are stored but never penalise anyone.
// "Not funny -> next" (stage left-skip / right-skip: ends that clip but stays in the clash) = CLIPSKIP_W = 0.4 of a loss.
const SKIP_W = 0.3, CLIPSKIP_W = 0.4
const PENAL = { left: SKIP_W, right: SKIP_W, 'left-skip': CLIPSKIP_W, 'right-skip': CLIPSKIP_W }
const skipW = (k) => PENAL[k?.stage] || 0
function clipSkips() { const a = LS.get('skips', []); return (Array.isArray(a) ? a : []).filter((k) => k && skipW(k) > 0 && BYID[k.clip]) }

// ---------- your model: personal hierarchical Bradley-Terry, prior = crowd chart ----------
function fitLocal() {
  const votes = LS.get('votes', []).filter((v) => BYID[v.a] && BYID[v.b])
  const g = {}
  for (const c of BOARD?.boards?.all?.comics || []) if (c.bouts) g[c.comic] = (c.elo - 1500) / SCALE
  const comics = [...new Set(CLIPS.map((c) => c.comic))]
  const r = Object.fromEntries(comics.map((k) => [k, g[k] || 0]))
  const o = Object.fromEntries(CLIPS.map((c) => [c.id, 0]))
  const skips = clipSkips()
  const bouts = {}
  for (const v of votes) { bouts[v.a] = (bouts[v.a] || 0) + 1; bouts[v.b] = (bouts[v.b] || 0) + 1 }
  for (let t = 0; t < 250; t++) {
    const gr = Object.fromEntries(comics.map((k) => [k, -0.5 * (r[k] - (g[k] || 0))]))
    const go = Object.fromEntries(CLIPS.map((c) => [c.id, -1.0 * o[c.id]]))
    for (const v of votes) {
      const A = BYID[v.a], B = BYID[v.b]
      const W = v.winner === v.a ? A : B, L = W === A ? B : A
      const p = voteWeight(v) * sig((r[L.comic] + o[L.id]) - (r[W.comic] + o[W.id]))
      gr[W.comic] += p; gr[L.comic] -= p; go[W.id] += p; go[L.id] -= p
    }
    for (const sk of skips) { // skipped mid-clip: a weak loss (0.3 / 0.4 of a pick) for that clip vs an average clip
      const C = BYID[sk.clip]; if (!C) continue
      const p = skipW(sk) * sig(r[C.comic] + o[C.id])
      gr[C.comic] -= p; go[C.id] -= p
    }
    for (const k of comics) r[k] += 0.08 * gr[k]
    for (const c of CLIPS) o[c.id] += 0.08 * go[c.id]
  }
  return { r, o, bouts, n: votes.length, score: (id) => r[BYID[id].comic] + o[id] }
}
let MODEL = null
const STYLES = ['deadpan', 'absurd', 'dark', 'observational', 'storytelling', 'rant', 'one-liners', 'self-deprecating', 'clean']
const TYPES = {
  deadpan: ['The Straight Face', 'You laugh hardest when nobody on stage does.'],
  absurd: ['The Surrealist', 'Logic is optional. The weirder the turn, the bigger your laugh.'],
  dark: ['The Gallows Crowd', 'Nothing is off-limits if the joke earns it.'],
  observational: ['The Noticer', 'You love comics who say the thing everyone saw and nobody said.'],
  storytelling: ['The Long-Game Listener', 'You will happily wait five minutes for one perfect payoff.'],
  rant: ['The Choir', 'Give you a comic with a righteous head of steam and you are in.'],
  'one-liners': ['The Punchline Purist', 'Setup, punch, next. No wasted words.'],
  'self-deprecating': ['The Confessor', 'You trust a comic who makes themselves the target.'],
  clean: ['The Craft Fan', 'You prize precision over shock.'],
}
function fitTraits() {
  // pairwise logistic regression on style differences: P(A beats B) = sig(w . (xA - xB)), L2-regularised
  const votes = LS.get('votes', []).filter((v) => BYID[v.a] && BYID[v.b])
  const w = Object.fromEntries(STYLES.map((t) => [t, 0])), n = {}
  const x = (c) => Object.fromEntries(STYLES.map((t) => [t, (c.style || []).includes(t) ? 1 : 0]))
  const data = votes.map((v) => { const A = x(BYID[v.a]), B = x(BYID[v.b]); const d = {}; STYLES.forEach((t) => { d[t] = A[t] - B[t]; if (d[t]) n[t] = (n[t] || 0) + 1 }); return { d, y: v.winner === v.a ? 1 : 0, k: voteWeight(v) } })
  for (const sk of clipSkips()) { const X = x(BYID[sk.clip]); if (STYLES.some((t) => X[t])) data.push({ d: X, y: 0, k: skipW(sk) }) }
  for (let it = 0; it < 300; it++) {
    const g = Object.fromEntries(STYLES.map((t) => [t, -0.6 * w[t]]))
    for (const { d, y, k } of data) { const p = sig(STYLES.reduce((s, t) => s + w[t] * d[t], 0)); STYLES.forEach((t) => (g[t] += k * (y - p) * d[t])) }
    STYLES.forEach((t) => (w[t] += 0.1 * g[t]))
  }
  return { w, n }
}
let TRAITS = { w: {}, n: {} }
const traitScore = (c) => (c.style || []).reduce((s, t) => s + (TRAITS.w[t] || 0), 0)
function humourType() {
  const top = Object.entries(TRAITS.w).filter(([t]) => (TRAITS.n[t] || 0) >= 2).sort((a, b) => b[1] - a[1])
  if (!top.length || top[0][1] < 0.15) return null
  return { key: top[0][0], name: TYPES[top[0][0]][0], line: TYPES[top[0][0]][1], also: top[1] && top[1][1] > 0.15 ? top[1][0] : null }
}

// ---------- choosing the next double feature ----------
function openPair(a, b) {
  const done = new Set(LS.get('votes', []).map((v) => pairKey(v.a, v.b)))
  const skipped = new Set(LS.get('skipped', []))
  const A = BYID[a], B = BYID[b]
  if (!A || !B || a === b || done.has(pairKey(a, b)) || skipped.has(pairKey(a, b))) return false
  if (LANE === 'mixed') return A.kind !== B.kind || Math.random() < 0.25
  return A.kind === LANE && B.kind === LANE
}
function pool() { return CLIPS.filter((c) => LANE === 'mixed' || c.kind === LANE) }
const shuffle = (a) => a.map((x) => [Math.random(), x]).sort((p, q) => p[0] - q[0]).map((p) => p[1])

function pickForYou() {
  // your model's favourite unseen matchup: its top clip vs the clip it knows least about
  const P = pool(); if (P.length < 2) return null
  const fy = (c) => MODEL.score(c.id) + traitScore(c) + 0.3 * Math.random()
  const top = [...P].sort((x, y) => fy(y) - fy(x))
  for (const a of top.slice(0, 6)) {
    const opp = P.filter((b) => b.comic !== a.comic && openPair(a.id, b.id)).sort((x, y) => (MODEL.bouts[x.id] || 0) - (MODEL.bouts[y.id] || 0) || Math.random() - 0.5)
    if (opp.length) return [a, opp[0]]
  }
  return null
}
function pickTraining() {
  // the pairs the crowd chart is least sure about (computed by the tally)
  const ranked = PAIRS.filter((p) => openPair(p.a, p.b)).slice(0, 40)
  if (!ranked.length) return null
  let x = Math.random() * ranked.reduce((s, p) => s + p.w, 0)
  for (const p of ranked) { x -= p.w; if (x <= 0) return [BYID[p.a], BYID[p.b]] }
  return [BYID[ranked[0].a], BYID[ranked[0].b]]
}
function pickExplore() {
  const seen = LS.get('seen', {}), P = shuffle(pool()).sort((x, y) => (seen[x.id] || 0) - (seen[y.id] || 0))
  for (const a of P) {
    const opts = P.filter((b) => openPair(a.id, b.id))
    if (!opts.length) continue
    const cross = opts.filter((b) => b.comic !== a.comic)
    return [a, (cross.length ? cross : opts)[0]]
  }
  return null
}
const MODES = {
  foryou: ['Picked for you', pickForYou],
  training: ['Training the crowd chart', pickTraining],
  explore: ['Exploring something new', pickExplore],
  shared: ['A friend shared this clash', () => null],
}
function pickPair() {
  const n = LS.get('votes', []).length
  const w = n < 6 ? { training: 0.55, explore: 0.45, foryou: 0 } : { foryou: 0.4, training: 0.4, explore: 0.2 }
  let x = Math.random(), mode = 'explore'
  for (const k of Object.keys(w)) { x -= w[k]; if (x <= 0) { mode = k; break } }
  const order = [mode, ...Object.keys(MODES).filter((k) => k !== mode)]
  for (const m of order) {
    const p = MODES[m][1]()
    if (p) { const pair = Math.random() < 0.5 ? p : [p[1], p[0]]; pair.mode = m; return pair }
  }
  return null
}

// ---------- players ----------
let ytReady = null
function loadYT() {
  if (ytReady) return ytReady
  ytReady = new Promise((res) => {
    window.onYouTubeIframeAPIReady = () => res(window.YT)
    const t = document.createElement('script'); t.src = 'https://www.youtube.com/iframe_api'; document.head.appendChild(t)
  })
  return ytReady
}
// ---------- volume: YouTube's setVolume can only attenuate (0-100), so loud clips get turned down, never quiet ones up past 100 ----------
// effective = clamp(clip.vol (editorial, default 100) + your local offset from "Too loud"/"Too quiet") x your volume slider
const AUD_STEP = 15
const clamp = (x, lo, hi) => Math.max(lo, Math.min(hi, x))
function userVol() { const v = Number(LS.get('vol', 100)); return Number.isFinite(v) ? clamp(v, 0, 100) : 100 }
function audioMap() { const m = LS.get('audio', {}); return m && typeof m === 'object' && !Array.isArray(m) ? m : {} }
function clipVol(c) {
  const base = c?.vol != null && c.vol !== '' && Number.isFinite(Number(c.vol)) ? clamp(Number(c.vol), 0, 100) : 100
  const off = Number(audioMap()[c?.id]?.off) || 0
  return Math.round(clamp(base + off, 0, 100) * userVol() / 100)
}
function audioFeedback(clip, kind) {
  if (!clip || (kind !== 'loud' && kind !== 'quiet')) return
  const m = audioMap(), r = m[clip.id] && typeof m[clip.id] === 'object' ? m[clip.id] : { off: 0, loud: 0, quiet: 0 }
  r[kind] = (Number(r[kind]) || 0) + 1
  r.off = clamp((Number(r.off) || 0) + (kind === 'loud' ? -AUD_STEP : AUD_STEP), -60, 30)
  r.at = new Date().toISOString(); m[clip.id] = r; LS.set('audio', m)
  toast(kind === 'loud' ? `Noted. ${clip.comic} plays ${AUD_STEP}% quieter next time.` : `Noted. ${clip.comic} plays a little louder next time (up to full volume).`)
}
class Screen {
  constructor(side, clip, hostId) { this.side = side; this.clip = clip; this.hostId = hostId; this.started = false; this.ready = new Promise((res) => (this._ready = res)) }
  async mount() {
    const c = this.clip, host = document.getElementById(this.hostId)
    this.start = c.start || 0
    if (!host) return
    if (c.media === 'audio') {
      host.innerHTML = `<audio preload="auto" controls src="${esc(c.src)}"></audio>`
      this.a = host.querySelector('audio')
      this.a.onloadedmetadata = () => { this.applyVol(); this._ready() }
      this.a.onended = () => (this.ended = true)
      return
    }
    const YT = await loadYT()
    if (this.dead || !document.getElementById(this.hostId)) return
    const res = this._ready
    this.p = new YT.Player(this.hostId, {
      host: 'https://www.youtube-nocookie.com', videoId: c.id,
      playerVars: { rel: 0, playsinline: 1, start: this.start, controls: 1, modestbranding: 1 },
      events: { onReady: () => { this.applyVol(); res() }, onStateChange: (e) => { if (e.data === 0) this.ended = true } },
    })
  }
  applyVol() { const v = clipVol(this.clip); try { if (this.a) this.a.volume = v / 100; else this.p?.setVolume?.(v) } catch {} }
  dur() { const d = this.a ? this.a.duration : this.p?.getDuration?.(); return d || this.clip.sec || 0 }
  end() { const d = this.dur(); return this.clip.end || (d ? Math.min(d, this.start + SHORT_MAX) : this.start + SHORT_MAX) }
  t() { return this.a ? this.a.currentTime : this.p?.getCurrentTime?.() || 0 }
  playing() { return this.a ? !this.a.paused : this.p?.getPlayerState?.() === 1 }
  progress() { const s = this.start, e = this.end(); return Math.max(0, Math.min(1, (this.t() - s) / Math.max(1, e - s))) }
  done() { return this.ended || (this.started && this.t() >= this.end() - 0.3) }
  async play() {
    await this.ready; if (this.dead) return
    this.started = true; this.wantPlay = true; this.applyVol()
    if (this.a) { try { await this.a.play() } catch { toast('Tap the screen to start the sound') } return }
    this.p.playVideo()
    setTimeout(() => { // autoplay with sound refused: play muted and say so
      if (this.dead || !this.wantPlay) return // paused or skipped since: don't restart it behind the next clip
      const st = this.p?.getPlayerState?.()
      if (st !== 1 && st !== 3) { this.p.mute(); this.p.playVideo(); toast('Started muted. Tap the screen for sound.') }
    }, 1800)
  }
  toggle() { // tap on the gesture layer: unmute, play/pause
    if (this.a) { this.a.paused ? this.a.play().catch(() => {}) : this.a.pause(); return }
    try { if (this.p?.isMuted?.()) { this.p.unMute(); this.applyVol(); if (!this.playing()) this.p.playVideo(); return } } catch {}
    this.playing() ? this.pause() : this.p?.playVideo?.()
  }
  // called every tick: accumulates real seconds watched, notices seeks back (replay) and jumps ahead (skip)
  track() {
    this.watched = this.watched || 0; this.replays = this.replays || 0
    let t = 0, on = false
    try { t = this.t(); on = this.playing() } catch { return }
    if (!Number.isFinite(t)) return
    if (this.lastT == null) { if (on) this.lastT = t; return } // start tracking at first real playback
    const d = t - this.lastT
    if (on && d > 0 && d < 2) this.watched += d
    if (d < -2) this.replays++
    if (d > 5) this.jumped = true
    this.lastT = t
  }
  screened() { return Math.max(1, this.end() - this.start) }
  // the watch minimum: min(30s, 80% of what we screen), or the clip played to its end
  enough() { return this.ended || (this.watched || 0) >= Math.min(30, 0.8 * this.screened()) - 0.5 || (this.started && this.t() >= this.end() - 0.3 && (this.watched || 0) > 3 && !this.jumped) }
  pause() { this.wantPlay = false; try { this.a ? this.a.pause() : this.p?.pauseVideo?.() } catch {} }
  destroy() { this.dead = true; try { this.a?.pause() } catch {} try { this.p?.destroy?.() } catch {} }
}

// ---------- the screening: intro face-off -> clip ONE full screen -> clip TWO -> 3s ballot ----------
// stages: intro | left | right | vote | done
const VOTE_MS = 3000, INTRO_MS = 2500
let screens = {}, stage = 'idle', tick = null, armed = false, armedAt = 0, prediction = null
let cur = null, nScreen = 0, timers = [], userStarted = false, moving = false
const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now())
const later = (f, ms) => { const t = setTimeout(f, ms); timers.push(t); return t }
const clearTimers = () => { timers.forEach(clearTimeout); timers = [] }
const q = (sel) => cur?.el?.querySelector(sel) || null
const reduced = () => typeof matchMedia === 'function' && matchMedia('(prefers-reduced-motion: reduce)').matches
function signals() {
  // what the screening tells us about this pick, without asking
  const L = screens.L, R = screens.R, out = {}
  if (!L || !R) return out
  const r1 = (x) => Math.round(x * 10) / 10
  out.leftWatchedSec = r1(L.watched || 0); out.rightWatchedSec = r1(R.watched || 0)
  try { out.rightFrac = Math.round(100 * Math.min(1, (R.watched || 0) / R.screened())) / 100 } catch {}
  out.replayed = (L.replays || 0) + (R.replays || 0) > 0
  out.skippedAhead = !!(L.jumped || R.jumped)
  if (L.skipped) out.leftSkipped = true
  if (R.skipped) out.rightSkipped = true
  return out
}
function chip(c) { return c.kind === 'ai' ? '<span class="chip ai">AI</span>' : '' }
function crowdOf(comic) { const c = BOARD?.boards?.all?.comics?.find((x) => x.comic === comic && x.bouts); return c ? Math.round(c.elo) : null }
// the face-off card: the clip's own thumbnail is the main event (authentic: it's the set you're about to see).
// Caption sits BELOW the picture; nothing is laid over it. YouTube's 16:9 hq720 still (no letterbox bars), falling back
// to hqdefault (4:3 with bars, zoomed to hide them). Only non-YouTube clips use the comic's comics.json photo, if any.
function faceCard(c, side) {
  const P = COMICS[c.comic] || {}, r = crowdOf(c.comic)
  const photo = typeof P.photo === 'string' && /^https:\/\//.test(P.photo) ? P.photo : ''
  const img = c.media === 'youtube'
    ? `<img class="fimg still" src="https://i.ytimg.com/vi/${esc(c.id)}/hq720.jpg" alt="${esc(c.comic)}: ${esc(c.title || '')}" decoding="async" onerror="this.onerror=null;this.classList.add('lb');this.src='${thumb(esc(c.id))}'">`
    : photo ? `<img class="fimg portrait" src="${esc(photo)}" alt="${esc(c.comic)}" decoding="async">`
      : `<span class="fimg none">${esc(c.comic)}</span>`
  return `<div class="face ${side}"><div class="fpic">${img}</div>
    <div class="ftext"><b>${esc(c.comic)}${chip(c)}</b><span>${esc(P.tagline || c.title || '')}</span><em>${r ? r + ' crowd rating' : 'Unrated'}</em></div></div>`
}
function modeLabel() { return current?.mode === 'shared' && sharedRound?.pick ? 'A friend picked one. Do you agree?' : MODES[current?.mode]?.[0] || '' }
function slideHTML(a, b, n, first) {
  const shot = (c, side) => `<button class="pick ${side}" data-side="${side}" aria-label="${esc(c.comic)} was funnier">
      <span class="pimg" ${c.media === 'youtube' ? `style="background-image:url(${thumb(c.id)})"` : ''}></span>
      <span class="pname">${esc(c.comic)}</span><span class="logo">FUNNIER</span></button>`
  const scr = (c, side) => `<div class="screen ${side} small" data-side="${side}">
      <div class="frame"><div id="p${side}${n}"></div><div class="shield" aria-hidden="true"></div></div>
      <div class="label"><span class="side">${side === 'L' ? '1' : '2'}</span><div class="meta"><h3>${esc(c.comic)}${chip(c)}</h3><p>${esc(c.title)} · ${esc(c.channel || '')}</p></div></div>
      <div class="prog"><i></i></div></div>`
  return `<div class="slide" data-n="${n}">
    <div class="intro">
      <div class="introbar"><span class="kicker"><i class="dot"></i>Tonight's screening</span>${modeLabel() ? `<span class="modepill">${esc(modeLabel())}</span>` : ''}</div>
      <div class="faceoff">${faceCard(a, 'L')}<span class="vsx">VS</span>${faceCard(b, 'R')}</div>
      <div class="introfoot">${first ? `<button class="play" data-act="start">▶ Start the show</button>` : `<p class="tapskip">Tap to skip the intro</p>`}</div>
    </div>
    <div class="theatre">${scr(a, 'L')}${scr(b, 'R')}<button class="skipclip" type="button" data-act="skipclip" aria-label="Not funny: skip to clip two">Not funny → #2</button></div>
    <div class="ballot"><p class="bq">Which was funnier?</p><div class="picks">${shot(a, 'L')}${shot(b, 'R')}</div>
      <div class="audiofb" role="group" aria-label="Sound level feedback"><span>Sound off?</span>${[['L', '#1'], ['R', '#2']].map(([sd, n]) => `<button type="button" data-aud="${sd}" data-k="loud">${n} too loud</button><button type="button" data-aud="${sd}" data-k="quiet">${n} too quiet</button>`).join('')}</div>
      <div class="count"><i></i></div><p class="hint">Tap one, or ← / →. No pick in 3s = pass.</p>
      <p class="friendres" aria-live="polite"></p>
      <button class="sharex" type="button" data-act="share">Share this clash ↗</button></div>
  </div>`
}

function laneSelect() {
  const box = $('#lanebox')
  box.innerHTML = `<select id="lane">${[['human', 'Human comics'], ['ai', 'AI comics'], ['mixed', 'Human vs AI']].map(([k, l]) => `<option value="${k}" ${LANE === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`
  $('#lane').onchange = (e) => { LANE = e.target.value; LS.set('lane', LANE); goNext(null) }
}

function setStage(s) {
  stage = s
  if (cur?.el) cur.el.dataset.stage = s
  document.body.classList.toggle('in-theatre', s === 'left' || s === 'right')
  const label = s === 'left' ? 'Not funny → #2' : s === 'right' ? 'Not funny → vote' : ''
  const aria = s === 'left' ? 'Not funny: skip to clip two' : 'Not funny: skip to the vote'
  const sk = q('.skipclip'); if (sk && label) { sk.textContent = label; sk.setAttribute('aria-label', aria) }
  const cb = $('#skipbtn'); if (cb) { cb.hidden = !label; if (label) { cb.textContent = label; cb.setAttribute('aria-label', aria) } }
  updateChrome()
}
function stopScreening() {
  clearInterval(tick); tick = null; clearTimers()
  Object.values(screens).forEach((s) => s.destroy()); screens = {}; armed = false; armedAt = 0
  document.body.classList.remove('in-theatre')
}

// builds the next screening; when `old` is given, the old one slides up and away (TikTok-style)
function newRound(first) { mountScreening(first, null) }
function mountScreening(first, oldEl) {
  current = takeClash() || pickPair()
  if (current?.mode !== 'shared') sharedRound = null
  const host = $('#stage')
  if (!host) return
  if (!current) {
    $('#roundtag').textContent = 'Intermission'
    const msg = LANE === 'ai' ? 'The AI comics are still in rehearsal. Their first sets premiere here soon.' : LANE === 'mixed' ? 'Human vs AI opens when the first AI sets premiere.' : "You've seen every clash on the bill. New shorts arrive daily."
    host.querySelectorAll('.slide').forEach((x) => x !== oldEl && x.remove())
    host.insertAdjacentHTML('beforeend', `<div class="slide empty-slide"><p class="empty">${msg}</p></div>`)
    finishSlide(host, oldEl); cur = { el: host.lastElementChild, n: ++nScreen }; setStage('done'); updateChrome()
    return
  }
  const [a, b] = current, n = ++nScreen
  $('#roundtag').textContent = "Tonight's double feature"
  const pL = MODEL ? sig(MODEL.score(a.id) + traitScore(a) - MODEL.score(b.id) - traitScore(b)) : 0.5
  prediction = { p: pL, side: pL >= 0.5 ? 'L' : 'R' }
  host.insertAdjacentHTML('beforeend', slideHTML(a, b, n, first))
  const el = host.lastElementChild
  cur = { el, n, a, b }
  finishSlide(host, oldEl)
  screens = { L: new Screen('L', a, 'pL' + n), R: new Screen('R', b, 'pR' + n) }
  screens.L.mount(); screens.R.mount()
  setStage('intro')
  bindSlide(el)
  // the face-off: title card, then ONE flashes in, then TWO
  el.classList.add('show-title')
  later(() => el.classList.add('show-L'), reduced() ? 0 : 500)
  later(() => el.classList.add('show-R'), reduced() ? 0 : 1200)
  if (!first || userStarted) later(() => stage === 'intro' && cur?.el === el && startClip('L'), INTRO_MS)
}
function finishSlide(host, oldEl) {
  const el = host.lastElementChild
  if (!oldEl) { host.querySelectorAll('.slide').forEach((x) => x !== el && x.remove()); return }
  if (reduced()) { oldEl.remove(); return }
  el.classList.add('enter'); void el.offsetWidth
  oldEl.classList.add('leave'); el.classList.remove('enter')
  setTimeout(() => oldEl.remove(), 520)
}
function bindSlide(el) {
  el.querySelector('.intro').onclick = () => { if (stage === 'intro') { userStarted = true; startClip('L') } }
  el.querySelectorAll('.pick').forEach((x) => (x.onclick = (e) => { e.stopPropagation(); vote(x.dataset.side) }))
  el.querySelectorAll('.shield').forEach((sh) => (sh.onclick = () => {
    if (tapRevealed) { tapRevealed = false; return } // chrome was hidden: this tap only brings it back
    screens[sh.closest('.screen').dataset.side]?.toggle()
  }))
  const sx = el.querySelector('.sharex')
  if (sx) sx.onclick = (e) => { e.stopPropagation(); shareCurrent() }
  const sk = el.querySelector('.skipclip')
  if (sk) sk.onclick = (e) => { e.stopPropagation(); skipClip() }
  el.querySelectorAll('[data-aud]').forEach((bt) => (bt.onclick = (e) => {
    e.stopPropagation()
    pauseBallot('Countdown paused. Pick when you\u2019re ready.')
    const sd = bt.dataset.aud, clip = sd === 'L' ? cur?.a : cur?.b
    audioFeedback(clip, bt.dataset.k)
    bt.parentElement?.querySelectorAll(`[data-aud="${sd}"]`).forEach((x) => (x.disabled = true)); bt.classList.add('on')
  }))
}
// a tap on the ballot that isn't a pick (share, sound feedback) pauses the 3s countdown; that pick gets no timing signal
function pauseBallot(msg) {
  if (!(stage === 'vote' && armed)) return
  sharedDuringBallot = true; clearTimers()
  const bar = q('.count i'); if (bar) { const t = getComputedStyle(bar).transform; bar.style.transition = 'none'; bar.style.transform = t }
  const h = q('.ballot .hint'); if (h) h.textContent = msg
}
// "Not funny -> next": ends the clip on screen but stays in the clash. Clip ONE -> clip TWO; clip TWO -> the ballot.
// Logged in funnier.skips as stage 'left-skip' / 'right-skip' and counted as 0.4 of a loss for that clip, its comic and styles.
function skipClip() {
  if (!current || !cur || moving || (stage !== 'left' && stage !== 'right')) return false
  const side = stage === 'left' ? 'L' : 'R', sc = screens[side]; if (!sc) return false
  sc.track(); sc.skipped = true; sc.pause()
  const c = sc.clip, [a, b] = current
  const rec = { a: a.id, b: b.id, stage: side === 'L' ? 'left-skip' : 'right-skip', comics: [c.comic], comic: c.comic, clip: c.id,
    style: Array.isArray(c.style) ? c.style : [], watchedSec: Math.round(10 * (sc.watched || 0)) / 10, at: new Date().toISOString() }
  LS.set('skips', [...LS.get('skips', []), rec].slice(-500))
  try { MODEL = fitLocal(); TRAITS = fitTraits() } catch {}
  if (side === 'L') { toast('Skipped to #2. Noted against that clip.'); startClip('R') } else startVote()
  return true
}

function startClip(side) {
  if (!cur || !screens[side]) return
  clearTimers()
  setStage(side === 'L' ? 'left' : 'right')
  bumpShown(screens[side].clip.comic)
  for (const s of ['L', 'R']) {
    const sc = cur.el.querySelector(`.screen.${s}`)
    sc?.classList.toggle('big', s === side); sc?.classList.toggle('small', s !== side)
    sc?.classList.toggle('gone', side === 'R' && s === 'L')
  }
  if (side === 'R') screens.L.pause()
  screens[side].play()
  runTick()
}
function runTick() {
  clearInterval(tick)
  tick = setInterval(() => {
    const L = screens.L, R = screens.R; if (!L || !R || !cur) return
    for (const s of ['L', 'R']) {
      const sc = screens[s]; sc.track()
      const pg = cur.el.querySelector(`.screen.${s} .prog i`)
      if (pg) pg.style.transform = `scaleX(${sc.started ? sc.progress() : 0})`
    }
    // keyboard focus gets swallowed by the YouTube iframe: take it back
    const ae = document.activeElement
    if (ae && ae.tagName === 'IFRAME') { try { ae.blur() } catch {} $('#stage')?.focus?.({ preventScroll: true }) }
    if (stage === 'left' && L.done()) { L.pause(); startClip('R') }
    else if (stage === 'right' && R.done()) { R.pause(); startVote() }
  }, 250)
}
function startVote() {
  clearInterval(tick); tick = null
  setStage('vote')
  armed = true; armedAt = now(); sharedDuringBallot = false // decision time runs from the moment the FUNNIER logos appear
  const bar = q('.count i')
  if (bar) { bar.style.transition = 'none'; bar.style.transform = 'scaleX(1)'; void bar.offsetWidth; bar.style.transition = `transform ${VOTE_MS}ms linear`; bar.style.transform = 'scaleX(0)' }
  later(() => { if (stage === 'vote' && armed) pass() }, VOTE_MS + 60)
}
function pass() {
  if (!current) return
  const [a, b] = current
  armed = false
  LS.set('passes', [...LS.get('passes', []), { a: a.id, b: b.id, ...signals(), at: new Date().toISOString() }].slice(-300))
  LS.set('skipped', [...LS.get('skipped', []), pairKey(a.id, b.id)].slice(-500)); bumpSeen(a.id, b.id)
  toast('No pick, so it\u2019s a pass. Neither comic loses anything.')
  goNext(null)
}

// swipe up / wheel / ArrowUp / PageDown / "Next clash": leave this screening at any stage
function skipClash() {
  if (!current || moving || stage === 'done' || stage === 'idle') return goNext(null)
  const [a, b] = current, sg = signals()
  const on = stage === 'left' ? [a] : stage === 'right' ? [b] : stage === 'vote' ? [a, b] : []
  const sc = stage === 'left' ? screens.L : stage === 'right' ? screens.R : null
  const rec = { a: a.id, b: b.id, stage, comics: on.map((c) => c.comic), clip: sc ? sc.clip.id : null,
    watchedSec: sc ? Math.round(10 * (sc.watched || 0)) / 10 : 0, ...sg, at: new Date().toISOString() }
  if (stage === 'vote' && armedAt) rec.decisionMs = Math.round(now() - armedAt)
  LS.set('skips', [...LS.get('skips', []), rec].slice(-500))
  LS.set('skipped', [...LS.get('skipped', []), pairKey(a.id, b.id)].slice(-500)); bumpSeen(a.id, b.id)
  if (sc) { MODEL = fitLocal(); TRAITS = fitTraits(); paintYou() }
  goNext(null)
}
function goNext() {
  if (moving) return
  moving = true; setTimeout(() => (moving = false), 650)
  const oldEl = cur?.el || null
  stopScreening()
  mountScreening(false, oldEl)
}
function bumpShown(comic) { const s = LS.get('shown', {}); s[comic] = (s[comic] || 0) + 1; LS.set('shown', s) }

async function vote(side) {
  if (!current || !armed || stage !== 'vote') return
  armed = false; setStage('done')
  const [a, b] = current
  const decisionMs = armedAt && !sharedDuringBallot ? Math.max(0, Math.round(now() - armedAt)) : undefined
  const sg = signals()
  const v = { a: a.id, b: b.id, winner: side === 'L' ? a.id : b.id, voter: 'human', basis: 'watched', mode: current.mode, decisionMs, ...sg, createdAt: new Date().toISOString() }
  v.weight = voteWeight(v)
  q(`.pick.${side}`)?.classList.add('won')
  bumpSeen(a.id, b.id)
  const fl = friendLine(a, b, v.winner)
  if (fl) { const fe = q('.friendres'); if (fe) { fe.textContent = fl.text; fe.classList.add('on', fl.agree ? 'agree' : 'disagree') } }
  const pre = fl ? fl.text + ' ' : ''
  // the watch minimum still applies: both clips at least ~30s (or to the end)
  const okL = screens.L?.skipped || screens.L?.enough(), okR = screens.R?.skipped || screens.R?.enough()
  if (!(okL && okR) || (screens.L?.skipped && screens.R?.skipped)) {
    LS.set('partials', [...LS.get('partials', []), v].slice(-300))
    toast(pre + 'Noted, but it only counts when both clips were watched for 30s or to the end.')
    askWhy(v, true)
    later(() => goNext(null), fl ? 2400 : 700)
    return
  }
  LS.set('votes', [...LS.get('votes', []), v])
  const preds = LS.get('preds', []); preds.push({ p: prediction.p, hit: prediction.side === side }); LS.set('preds', preds.slice(-200))
  const dur = LS.get('dur', {}); dur[a.id] = screens.L.dur(); dur[b.id] = screens.R.dur(); LS.set('dur', dur)
  const w = BYID[v.winner]
  const guess = MODEL && MODEL.n >= 3 ? (prediction.side === side ? ' Your model called it.' : ' Your model guessed the other one.') : ''
  later(() => goNext(null), fl ? 2400 : reduced() ? 300 : 900)
  askWhy(v)
  if (agent) {
    try { await publish(v); toast(pre || `${w.comic} takes it.${guess}`) }
    catch { LS.set('queue', [...LS.get('queue', []), v]); toast(`${pre}Saved. It'll publish when Bluesky responds.${guess}`) }
  } else { LS.set('queue', [...LS.get('queue', []), v]); toast(pre || `${w.comic} takes it.${guess}`) }
  MODEL = fitLocal(); TRAITS = fitTraits()
  paintBanner(); paintYou()
}
const WHY = ['Smarter', 'Weirder', 'Darker', 'Better delivery', 'More relatable', 'Better payoff']
let whyT
function askWhy(v, shareOnly) {
  const box = $('#why'); if (!box) return
  box.innerHTML = `${shareOnly ? '' : `<span>Why was it funnier?</span>${WHY.map((w) => `<button data-why>${w}</button>`).join('')}`}<button class="whyshare" type="button">Share this clash ↗</button>`
  box.classList.add('on'); clearTimeout(whyT); whyT = setTimeout(() => box.classList.remove('on'), 5000)
  const ws = box.querySelector('.whyshare')
  if (ws) ws.onclick = (e) => { e.stopPropagation(); clearTimeout(whyT); whyT = setTimeout(() => box.classList.remove('on'), 1500); shareClash(BYID[v.a], BYID[v.b], v.winner === v.a ? 'a' : 'b') }
  box.querySelectorAll('button[data-why]').forEach((b) => (b.onclick = () => {
    const votes = LS.get('votes', []); const last = votes[votes.length - 1]
    if (last && last.createdAt === v.createdAt) { last.why = b.textContent; LS.set('votes', votes) }
    const q2 = LS.get('queue', []); const lq = q2.find((x) => x.createdAt === v.createdAt); if (lq) { lq.why = b.textContent; LS.set('queue', q2) }
    box.classList.remove('on'); toast('Noted. Your model will use that.')
  }))
}
const arenaOn = () => !$('#v-arena')?.hidden
document.addEventListener('keydown', (e) => {
  if (['INPUT', 'TEXTAREA', 'SELECT'].includes(e.target.tagName) || !arenaOn()) return
  if ((e.key === 'ArrowRight' || e.key === 'n' || e.key === 'N') && (stage === 'left' || stage === 'right')) { e.preventDefault(); skipClip() }
  else if (e.key === 'ArrowLeft') vote('L')
  else if (e.key === 'ArrowRight') vote('R')
  else if (e.key === 'ArrowUp' || e.key === 'PageDown') { e.preventDefault(); skipClash() }
  else if ((e.key === ' ' || e.key === 'Enter') && stage === 'intro' && e.target === document.body) { e.preventDefault(); userStarted = true; startClip('L') }
})
function bindGestures() {
  const stageEl = $('#stage'); if (!stageEl) return
  let y0 = null, x0 = null, t0 = 0
  const start = (e) => { const t = e.touches?.[0]; if (!t) return; y0 = t.clientY; x0 = t.clientX; t0 = now() }
  const end = (e) => {
    const t = e.changedTouches?.[0]; if (!t || y0 == null) return
    const dy = t.clientY - y0, dx = t.clientX - x0; y0 = null
    if (dy < -60 && Math.abs(dy) > 1.5 * Math.abs(dx) && now() - t0 < 800) skipClash()
    else if (dx < -60 && Math.abs(dx) > 1.5 * Math.abs(dy) && now() - t0 < 800 && (stage === 'left' || stage === 'right')) { tapRevealed = false; skipClip() }
  }
  // the theatre and its transparent shields sit over the iframe, so swipes land here and not in YouTube
  document.addEventListener('touchstart', (e) => { if (arenaOn() && e.target.closest?.('#stage')) start(e) }, { passive: true })
  document.addEventListener('touchend', (e) => { if (arenaOn() && e.target.closest?.('#stage')) end(e) }, { passive: true })
  let acc = 0, accT = 0
  stageEl.addEventListener('wheel', (e) => {
    if (!arenaOn()) return
    e.preventDefault()
    if (now() - accT > 400) acc = 0
    acc += Math.abs(e.deltaY); accT = now()
    if (acc > 120) { acc = -1e9; skipClash(); setTimeout(() => (acc = 0), 900) }
  }, { passive: false })
  $('#nextclash').onclick = (e) => { e.stopPropagation(); skipClash() }
}

// ---------- charts ----------
const thumb = (id) => `https://i.ytimg.com/vi/${id}/hqdefault.jpg`
function clipTile(c, i, extra) {
  const k = BYID[c.id] || c
  const img = k.media === 'youtube' ? `<img loading="lazy" src="${thumb(k.id)}" alt="">` : `<div class="comicposter" style="aspect-ratio:16/9"><b>${esc(k.comic)}</b></div>`
  const href = k.media === 'youtube' ? `https://www.youtube.com/watch?v=${k.id}` : '#'
  return `<a class="tile" href="${href}" target="_blank" rel="noopener">${i != null ? `<span class="num">${i + 1}</span>` : ''}
    <div class="poster">${img}<div class="cap"><b>${esc(k.title)}</b><span>${esc(k.comic)}${extra ? ' · ' + extra : ''}</span></div></div></a>`
}
function comicTile(c, i, extra) {
  const first = CLIPS.find((k) => k.comic === c.comic && k.media === 'youtube')
  const bg = first ? `style="background-image:linear-gradient(180deg,rgba(7,7,10,.1),rgba(7,7,10,.95) 75%),url(${thumb(first.id)})"` : ''
  return `<div class="tile"><span class="num">${i + 1}</span><div class="poster comicposter" ${bg}><b>${esc(c.comic)}</b><span class="rating">${extra}</span></div></div>`
}
function paintBoards() {
  const metas = document.querySelectorAll('.boardmeta')
  const sel = `<div class="lanes">${[['all', 'Everyone'], ['human', 'Humans'], ['agent', 'Agents']].map(([k, l]) => `<button data-board="${k}" class="${BOARDKIND === k ? 'on' : ''}">${l}</button>`).join('')}</div>`
  document.querySelectorAll('.boardsel').forEach((x) => (x.innerHTML = sel))
  document.querySelectorAll('[data-board]').forEach((x) => (x.onclick = () => { BOARDKIND = x.dataset.board; paintBoards() }))
  const bd = BOARD?.boards?.[BOARDKIND]
  if (!bd || !bd.votes) {
    metas.forEach((m) => (m.textContent = BOARDKIND === 'agent' ? 'No agent picks yet. Agents vote through the AT Protocol API.' : 'The chart opens with the first published picks. Until then, here is everything in rotation.'))
    const comics = [...new Set(CLIPS.map((c) => c.comic))]
    $('#comics').innerHTML = comics.map((k, i) => comicTile({ comic: k }, i, CLIPS.filter((c) => c.comic === k).length + ' shorts')).join('')
    $('#clips').innerHTML = CLIPS.map((c) => clipTile(c, null, c.channel)).join('')
    return
  }
  const ago = Math.max(0, Math.round((Date.now() - Date.parse(BOARD.updated)) / 60000))
  metas.forEach((m) => (m.textContent = `${bd.votes} picks from ${bd.voters} account${bd.voters === 1 ? '' : 's'} · Bradley-Terry ratings with 95% ranges · updated ${isNaN(ago) ? 'recently' : ago + ' min ago'}`))
  const rng = (r) => (r.lo != null ? ` (${Math.round(r.lo)}–${Math.round(r.hi)})` : '')
  $('#comics').innerHTML = bd.comics.filter((c) => c.bouts).map((c, i) => comicTile(c, i, Math.round(c.elo) + rng(c))).join('')
  $('#clips').innerHTML = bd.clips.filter((c) => c.bouts && BYID[c.id]).slice(0, 10).map((c, i) => clipTile(c, i, Math.round(c.elo))).join('')
}

// ---------- comics ----------
const slugOf = (name) => COMICS[name]?.slug || name.toLowerCase().replace(/[^a-z0-9]+/g, '-')
function comicStats(name) {
  const bd = BOARD?.boards?.all, crowd = bd?.comics?.find((c) => c.comic === name && c.bouts)
  const mine = MODEL ? Math.round(1500 + SCALE * (MODEL.r[name] || 0)) : null
  const clips = CLIPS.filter((c) => c.comic === name)
  const rated = clips.map((c) => ({ c, r: bd?.clips?.find((x) => x.id === c.id && x.bouts) })).sort((a, b) => (b.r?.elo || 0) - (a.r?.elo || 0))
  const styles = {}; clips.forEach((c) => (c.style || []).forEach((t) => (styles[t] = (styles[t] || 0) + 1)))
  // head-to-head from published + local picks
  const h2h = {}
  for (const v of [...PUBVOTES, ...LS.get('votes', [])]) {
    const A = BYID[v.a]?.comic, B = BYID[v.b]?.comic; if (!A || !B || A === B || (A !== name && B !== name)) continue
    const opp = A === name ? B : A, won = BYID[v.winner]?.comic === name
    h2h[opp] = h2h[opp] || { w: 0, n: 0 }; h2h[opp].n++; if (won) h2h[opp].w++
  }
  return { crowd, mine, clips, rated, styles: Object.entries(styles).sort((a, b) => b[1] - a[1]).map((x) => x[0]), h2h }
}
function paintComics() {
  const el = $('#comicsview'), route = location.hash.match(/^#comic\/(.+)$/)
  const names = [...new Set(CLIPS.map((c) => c.comic))]
  if (route) {
    const name = names.find((n) => slugOf(n) === route[1])
    if (name) return paintProfile(el, name)
  }
  el.innerHTML = `<div class="head"><h2>Comics</h2></div><p class="muted">Tap a comic for their profile, best-rated shorts and head-to-heads.</p>
    <div class="grid">${names.map((n) => { const st = comicStats(n), first = st.clips.find((k) => k.media === 'youtube')
      return `<a class="ccard" href="#comic/${slugOf(n)}"><div class="cimg" style="background-image:linear-gradient(180deg,rgba(7,7,10,0) 30%,rgba(7,7,10,.95)),url(${COMICS[n]?.photo || (first ? thumb(first.id) : '')})"></div>
        <div class="ctext"><b>${esc(n)}</b><span>${esc(COMICS[n]?.tagline || '')}</span><em>${st.crowd ? Math.round(st.crowd.elo) + ' crowd rating' : st.clips.length + ' shorts'}</em></div></a>` }).join('')}
      <div class="ccard soon"><div class="cimg ai"></div><div class="ctext"><b>AI comedians</b><span>In rehearsal. Soon you'll train your own and premiere them here.</span><em>Coming soon</em></div></div>
    </div>`
}
function paintProfile(el, name) {
  const P = COMICS[name] || {}, st = comicStats(name), first = st.clips.find((k) => k.media === 'youtube')
  const rng = st.crowd?.lo != null ? ` <small>${Math.round(st.crowd.lo)}–${Math.round(st.crowd.hi)}</small>` : ''
  el.innerHTML = `<a class="back" href="#comics">← All comics</a>
    <section class="hero" style="background-image:linear-gradient(90deg,rgba(7,7,10,.98) 25%,rgba(7,7,10,.55) 60%,rgba(7,7,10,.2)),url(${P.photo || (first ? thumb(first.id).replace('hqdefault', 'maxresdefault') : '')})">
      <div class="hinner"><span class="eyebrow">Comedian</span><h1>${esc(name)}</h1><p class="tag">${esc(P.tagline || '')}</p>
      <div class="facts">${(P.facts || []).map((f) => `<span>${esc(f)}</span>`).join('')}</div>
      <div class="stats"><div><b>${st.crowd ? Math.round(st.crowd.elo) + rng : '—'}</b><span>Crowd rating</span></div><div><b>${st.mine ?? '—'}</b><span>Your model</span></div><div><b>${st.clips.length}</b><span>Shorts</span></div></div>
      <div class="styles">${st.styles.map((t) => `<span class="chip">${t}</span>`).join('')}</div></div></section>
    <div class="cols"><div><h3>About</h3><p class="${P.bio ? '' : 'muted'}">${P.bio ? esc(P.bio) : 'Profile coming soon. Bio, influences and specials will live here.'}</p>
      ${Object.entries(P.links || {}).map(([k, u]) => `<a class="btn ghost" href="${esc(u)}" target="_blank" rel="noopener">${esc(k)}</a>`).join(' ')}</div>
      <div><h3>Head-to-head</h3>${Object.keys(st.h2h).length ? `<div class="bars">${Object.entries(st.h2h).map(([o, r]) => `<div class="barrow"><span>vs ${esc(o)}</span><div class="track"><i style="left:0;width:${(100 * r.w) / r.n}%"></i></div><span class="v">${Math.round((100 * r.w) / r.n)}% · ${r.n}</span></div>`).join('')}</div>` : '<p class="muted">No matchups yet. Every pick involving this comic shows up here.</p>'}</div></div>
    ${specialsHTML(P.specials)}
    <h3 class="shelf">Best-rated shorts</h3><div class="rail">${st.rated.map(({ c, r }, i) => clipTile(c, r ? i : null, r ? Math.round(r.elo) : c.channel)).join('')}</div>`
  bindSpecials(el)
  scrollTo({ top: 0 })
}

// ---------- specials: Letterboxd-style log, kept on this device ----------
const SPK = 'specials'
const spGet = () => { const x = LS.get(SPK, {}); return x && typeof x === 'object' ? x : {} }
const spMine = (id) => spGet()[id] || {}
function spSet(id, patch) {
  const all = spGet(), cur = { ...(all[id] || {}), ...patch, at: new Date().toISOString() }
  if (!cur.seen && !cur.stars && !cur.note) delete all[id]; else all[id] = cur
  LS.set(SPK, all)
}
function allSpecials() { return Object.entries(COMICS).flatMap(([comic, p]) => (Array.isArray(p?.specials) ? p.specials : []).map((s) => ({ ...s, comic }))) }
function specialsSeen() { const ids = new Set(allSpecials().map((s) => s.id)), m = spGet(); return Object.keys(m).filter((id) => ids.has(id) && m[id].seen).length }
const hue = (s) => [...String(s)].reduce((h, c) => (h * 31 + c.charCodeAt(0)) % 360, 7)
function starsHTML(n) {
  return `<div class="stars" role="radiogroup" aria-label="Your rating">${[1, 2, 3, 4, 5].map((i) => {
    const f = n >= i ? 'full' : n >= i - 0.5 ? 'half' : ''
    return `<button class="st ${f}" data-star="${i}" aria-label="${i} star${i > 1 ? 's' : ''}">★</button>` }).join('')}</div>`
}
function specialCard(s) {
  const m = spMine(s.id), h = hue(s.id)
  return `<article class="sp${m.seen ? ' seen' : ''}" data-sp="${esc(s.id)}">
    <div class="spart" style="background:linear-gradient(160deg,hsl(${h} 70% 22%) 0%,#0b0b0e 75%)">
      <span class="spyear">${esc(s.year)}</span>
      <b>${esc(s.title)}</b>
      <span class="spdist">${esc(s.distributor || '')}${s.runtimeMin ? ' · ' + s.runtimeMin + ' min' : ''}</span>
      ${m.stars ? `<span class="spmine">★ ${m.stars}</span>` : ''}
    </div>
    <div class="spact">
      <button class="seenbtn${m.seen ? ' on' : ''}" data-act="seen" aria-pressed="${!!m.seen}">${m.seen ? '✓ Seen' : '+ Seen'}</button>
      ${starsHTML(m.stars || 0)}
      <button class="notebtn${m.note ? ' on' : ''}" data-act="note" aria-label="Note">✎</button>
    </div>
    <div class="spnote" ${m.note ? '' : 'hidden'}><textarea maxlength="280" rows="2" placeholder="A line for future you…">${esc(m.note || '')}</textarea></div>
    <div class="splinks">${(s.where || []).map((w) => `<a href="${esc(w.url)}" target="_blank" rel="noopener">${esc(w.name)}</a>`).join('')}</div>
  </article>`
}
function specialsHTML(list) {
  if (!Array.isArray(list) || !list.length) return ''
  const sorted = [...list].sort((a, b) => (a.year || 0) - (b.year || 0))
  return `<div class="sphead"><h3 class="shelf">Specials</h3><span class="muted" id="spsum">${spSummary(list)}</span></div>
    <div class="spgrid">${sorted.map(specialCard).join('')}</div>
    <p class="muted small">Your log stays on this device. Availability varies by country, so "Where to watch" opens a search.</p>`
}
function spSummary(list) {
  const m = spGet(), seen = list.filter((s) => m[s.id]?.seen).length, rated = list.map((s) => m[s.id]?.stars).filter((x) => x > 0)
  const avg = rated.length ? (rated.reduce((a, b) => a + b, 0) / rated.length).toFixed(1) : null
  return `${seen}/${list.length} seen${avg ? ` · your avg ★ ${avg}` : ''}`
}
function bindSpecials(root) {
  const grid = root.querySelector('.spgrid'); if (!grid) return
  const list = () => [...grid.querySelectorAll('.sp')].map((x) => allSpecials().find((s) => s.id === x.dataset.sp)).filter(Boolean)
  const repaint = (id, focusNote) => {
    const s = allSpecials().find((x) => x.id === id), old = grid.querySelector(`.sp[data-sp="${CSS.escape(id)}"]`)
    if (!s || !old) return
    old.outerHTML = specialCard(s)
    const sum = root.querySelector('#spsum'); if (sum) sum.textContent = spSummary(list())
    if (focusNote) grid.querySelector(`.sp[data-sp="${CSS.escape(id)}"] textarea`)?.focus()
    paintYou()
  }
  grid.onclick = (e) => {
    const card = e.target.closest('.sp'); if (!card) return
    const id = card.dataset.sp, m = spMine(id), star = e.target.closest('[data-star]'), act = e.target.closest('[data-act]')?.dataset.act
    if (star) {
      const i = +star.dataset.star, r = star.getBoundingClientRect()
      let n = e.clientX && e.clientX < r.left + r.width / 2 ? i - 0.5 : i // tap the left half for a half star
      if (n === m.stars) n = 0 // tap your rating again to clear it
      spSet(id, { stars: n, seen: n > 0 ? true : m.seen }); return repaint(id)
    }
    if (act === 'seen') { spSet(id, { seen: !m.seen, ...(m.seen ? { stars: 0 } : {}) }); return repaint(id) }
    if (act === 'note') { const box = card.querySelector('.spnote'); box.hidden = !box.hidden; if (!box.hidden) box.querySelector('textarea').focus() }
  }
  let nt
  grid.oninput = (e) => {
    if (e.target.tagName !== 'TEXTAREA') return
    const id = e.target.closest('.sp').dataset.sp, val = e.target.value.slice(0, 280)
    clearTimeout(nt); nt = setTimeout(() => { spSet(id, { note: val }); e.target.closest('.sp').querySelector('.notebtn')?.classList.toggle('on', !!val) }, 300)
  }
}

// ---------- your model ----------
function paintYou() {
  const el = $('#you'), votes = LS.get('votes', [])
  if (!votes.length) {
    const ns = specialsSeen()
    el.innerHTML = `<h2>Your model</h2><p class="empty">Every pick trains a small model of your sense of humour, right here on your device.<br>Watch a double feature to start it.</p>${ns ? `<p class="sure">${ns} special${ns === 1 ? '' : 's'} seen · <a href="#comics">log more in Comics</a></p>` : ''}`
    return
  }
  MODEL = MODEL || fitLocal()
  const preds = LS.get('preds', []).slice(3), last = preds.slice(-30)
  const acc = last.length ? Math.round((100 * last.filter((p) => p.hit).length) / last.length) : null
  const comics = Object.entries(MODEL.r).map(([k, x]) => ({ k, elo: Math.round(1500 + SCALE * x) })).sort((a, b) => b.elo - a.elo)
  const lo = Math.min(...comics.map((c) => c.elo)) - 40, hi = Math.max(...comics.map((c) => c.elo)) + 40
  const bars = comics.map((c) => `<div class="barrow"><span>${esc(c.k)}</span><div class="track"><i style="left:0;width:${(100 * (c.elo - lo)) / (hi - lo)}%"></i></div><span class="v">${c.elo}</span></div>`).join('')
  // learned traits
  const dur = LS.get('dur', {})
  let longW = 0, longN = 0, lnW = 0, lnN = 0
  for (const v of votes) {
    const A = BYID[v.a], B = BYID[v.b]; if (!A || !B) continue
    const da = dur[v.a], db = dur[v.b]
    if (da && db && Math.abs(da - db) > 20) { longN++; if ((da > db ? v.a : v.b) === v.winner) longW++ }
    const la = LATE_NIGHT.test(A.channel || ''), lb = LATE_NIGHT.test(B.channel || '')
    if (la !== lb) { lnN++; if ((la ? v.a : v.b) === v.winner) lnW++ }
  }
  const trait = (label, w, n, a, b) => {
    if (n < 2) return `<div class="barrow"><span>${label}</span><div class="track center"></div><span class="v">learning</span></div>`
    const p = w / n, left = Math.min(50, 100 * p), width = Math.abs(100 * p - 50)
    return `<div class="barrow"><span>${label}</span><div class="track center"><i style="left:${p >= 0.5 ? 50 : left}%;width:${width}%"></i></div><span class="v">${Math.round(100 * p)}% ${p >= 0.5 ? a : b}</span></div>`
  }
  const best = Object.keys(MODEL.o).filter((id) => MODEL.bouts[id]).sort((x, y) => MODEL.score(y) - MODEL.score(x)).slice(0, 5)
  el.innerHTML = `<h2>Your model</h2>
    <div class="kpis">
      <div class="kpi"><b>${votes.length}</b><span>picks trained on</span></div>
      <div class="kpi"><b>${acc == null ? '—' : acc + '%'}</b><span>how often it predicts you${last.length ? ` (last ${last.length})` : ''}</span></div>
      <div class="kpi"><b>${esc(comics[0].k.split(' ').slice(-1)[0])}</b><span>your top comic so far</span></div>
      <div class="kpi"><b>${new Set(votes.flatMap((v) => [v.a, v.b])).size}</b><span>shorts seen</span></div>
    </div>
    ${sureLine(votes)}
    ${(() => { const h = humourType(); return h ? `<div class="type"><span class="eyebrow">Your humour type</span><b>${h.name}</b><p>${h.line}${h.also ? ` With a streak of <i>${h.also}</i>.` : ''}</p></div>` : `<div class="type"><span class="eyebrow">Your humour type</span><b>Still reading you…</b><p>A few more picks across different styles and it will name your type.</p></div>` })()}
    <h3>Styles you laugh at</h3><div class="bars">${STYLES.map((t) => { const x = TRAITS.w[t] || 0, wd = Math.min(50, Math.abs(x) * 40); return `<div class="barrow"><span>${t}</span><div class="track center"><i style="left:${x >= 0 ? 50 : 50 - wd}%;width:${wd}%"></i></div><span class="v">${(TRAITS.n[t] || 0) < 2 ? 'learning' : (x > 0 ? '+' : '') + x.toFixed(2)}</span></div>` }).join('')}</div>
    ${skipLists()}
    <h3>Comics, as your model sees them</h3><p class="muted">It starts from the crowd chart and moves toward your picks.</p><div class="bars">${bars}</div>
    <h3>What it's learning about you</h3><div class="bars">
      ${trait('Longer bits', longW, longN, 'longer', 'shorter')}
      ${trait('Late-night TV', lnW, lnN, 'late-night', 'specials')}
    </div>
    ${best.length ? `<h3>Your funniest so far</h3><div class="rail">${best.map((id, i) => clipTile({ id }, i)).join('')}</div>` : ''}
    <div id="youglobal"></div>
    <h3>Why this matters</h3>
    <p class="note">Your model is a portable critic. When we build the AI comedians, it can <b>judge their drafts for you</b>, tune a comic to <b>your</b> sense of humour, or sit on a panel next to other people's models. <button class="btn" id="export" style="margin-left:6px">Download my model</button></p>`
  $('#export').onclick = () => {
    const blob = new Blob([JSON.stringify({ kind: 'funnier.taste-model', version: 1, created: new Date().toISOString(), picks: votes.length, accuracy: acc, comics, clips: Object.fromEntries(Object.entries(MODEL.o).filter(([id]) => MODEL.bouts[id]).map(([id, x]) => [id, Math.round(SCALE * (MODEL.r[BYID[id].comic] + x))])) }, null, 2)], { type: 'application/json' })
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = 'funnier-taste-model.json'; a.click()
  }
  if (me) fetch('data/taste/' + me.did.replace(/[^a-z0-9]/gi, '_') + '.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).then((t) => {
    if (!t) return
    $('#youglobal').innerHTML = `<h3>You vs the crowd</h3><p class="muted">From your ${t.votes} published picks.</p><div class="bars">${t.comics.map((c) => `<div class="barrow"><span>${esc(c.comic)}</span><div class="track center"><i style="left:${c.vsCrowd >= 0 ? 50 : 50 + Math.max(-50, c.vsCrowd / 4)}%;width:${Math.min(50, Math.abs(c.vsCrowd) / 4)}%"></i></div><span class="v">${c.vsCrowd > 0 ? '+' : ''}${c.vsCrowd}</span></div>`).join('')}</div>`
  }).catch(() => {})
}

function skipLists() {
  const shown = LS.get('shown', {}) || {}, sk = {}
  for (const k of clipSkips()) { const c = BYID[k.clip].comic; sk[c] = (sk[c] || 0) + 1 }
  const comics = Object.keys(shown).filter((c) => shown[c] > 0)
  if (!comics.length) return ''
  const most = comics.filter((c) => sk[c]).map((c) => ({ c, r: Math.min(1, sk[c] / shown[c]), n: sk[c] })).sort((a, b) => b.r - a.r || b.n - a.n).slice(0, 3)
  const never = comics.filter((c) => !sk[c] && shown[c] >= 2).sort((a, b) => shown[b] - shown[a]).slice(0, 3)
  if (!most.length && !never.length) return ''
  const li = (arr) => arr.length ? arr.join('') : '<li class="muted">Nobody yet</li>'
  return `<div class="skipcols"><div><h3>Most skipped</h3><ul>${li(most.map((m) => `<li><b>${esc(m.c)}</b><span>${m.n} skip${m.n === 1 ? '' : 's'} · ${Math.round(100 * m.r)}% of their clips</span></li>`))}</ul></div>
    <div><h3>Never skip</h3><ul>${li(never.map((c) => `<li><b>${esc(c)}</b><span>watched ${shown[c]} times, never skipped</span></li>`))}</ul></div></div>`
}
function sureLine(votes) {
  const ms = votes.map((v) => v.decisionMs).filter((x) => Number.isFinite(x) && x >= 0).sort((a, b) => a - b)
  const ns = specialsSeen()
  const sp = `<span>${ns} special${ns === 1 ? '' : 's'} seen</span>`
  if (!ms.length) return `<p class="sure"><b>How sure you were</b><span>timing starts with your next pick</span>${sp}</p>`
  const med = ms.length % 2 ? ms[(ms.length - 1) / 2] : (ms[ms.length / 2 - 1] + ms[ms.length / 2]) / 2
  const snap = Math.round((100 * ms.filter((x) => x < SNAP_MS).length) / ms.length)
  return `<p class="sure"><b>How sure you were</b><span>median ${(med / 1000).toFixed(1)}s to decide</span><span>${snap}% snap picks (under ${SNAP_MS / 1000}s)</span>${sp}</p>`
}

// ---------- chrome: the menu fades away during a screening, the logo never does ----------
let showTab = () => {}, chromeT = null, chromeHidden = false, nearTop = false, tapRevealed = false
const HIDE_FIRST_MS = 1500, HIDE_AFTER_MS = 2500, TOP_ZONE = 80
function screeningActive() { return !!current && arenaOn() && ['intro', 'left', 'right', 'vote', 'done'].includes(stage) }
function setChromeHidden(h) { chromeHidden = h; document.body.classList.toggle('chrome-hidden', h) }
function scheduleHide(ms) {
  clearTimeout(chromeT)
  chromeT = setTimeout(function hide() {
    if (!screeningActive()) return setChromeHidden(false)
    const hdr = $('#chrome'), focused = hdr && hdr.querySelector(':focus-visible')
    if (nearTop || focused || $('#auth input') === document.activeElement) { chromeT = setTimeout(hide, 600); return }
    setChromeHidden(true)
  }, ms)
}
function showChrome(ms = HIDE_AFTER_MS) {
  if (chromeHidden) setChromeHidden(false)
  if (screeningActive()) scheduleHide(ms); else clearTimeout(chromeT)
}
let wasActive = false
function updateChrome() {
  const sb = $('#sharebtn'); if (sb) sb.hidden = !current || !arenaOn()
  const act = screeningActive()
  if (act && !wasActive) scheduleHide(HIDE_FIRST_MS)
  if (!act) { clearTimeout(chromeT); setChromeHidden(false) }
  document.body.classList.toggle('screening', act)
  wasActive = act
}
function bindChrome() {
  addEventListener('pointermove', (e) => {
    if (e.pointerType && e.pointerType !== 'mouse') return
    nearTop = e.clientY <= TOP_ZONE
    if (screeningActive()) showChrome()
  }, { passive: true })
  document.addEventListener('mouseleave', () => (nearTop = false))
  // touch/pen: the first tap while the menu is hidden only reveals it (the shield then skips play/pause)
  document.addEventListener('pointerdown', (e) => {
    if (e.pointerType === 'mouse') { tapRevealed = false; return }
    tapRevealed = chromeHidden && !!e.target.closest?.('.shield')
    if (screeningActive()) showChrome()
  }, { capture: true, passive: true })
  document.addEventListener('focusin', (e) => { if (e.target.closest?.('#chrome, #brand')) showChrome() })
  document.addEventListener('keydown', (e) => { if (e.key === 'Tab') showChrome() })
  const sb = $('#sharebtn'); if (sb) sb.onclick = (e) => { e.stopPropagation(); shareCurrent() }
  const kb = $('#skipbtn'); if (kb) kb.onclick = (e) => { e.stopPropagation(); skipClip() }
  const vr = $('#vol')
  if (vr) {
    vr.value = String(userVol())
    vr.oninput = () => { LS.set('vol', clamp(Math.round(Number(vr.value) || 0), 0, 100)); Object.values(screens).forEach((x) => x.applyVol()); showChrome() }
  }
}

// ---------- share a clash: #clash/<clipA>/<clipB>&pick=a|b, no backend ----------
const SHARE_BASE = 'https://prx0r.github.io/characters/'
let pendingClash = null, sharedRound = null, sharedDuringBallot = false
function parseClash(h) {
  const m = String(h || '').match(/^#clash\/([^/&?]+)\/([^/&?]+)(?:[&?]pick=([ab]))?/)
  if (!m) return null
  const d = (x) => { try { return decodeURIComponent(x) } catch { return x } }
  return { a: d(m[1]), b: d(m[2]), pick: m[3] || null }
}
function takeClash() {
  const sh = pendingClash; pendingClash = null
  if (!sh) return null
  const A = BYID[sh.a], B = BYID[sh.b]
  if (!A || !B || sh.a === sh.b) { setTimeout(() => toast('That clash is no longer on the bill, so here is tonight\u2019s instead.'), 400); return null }
  const pair = [A, B]; pair.mode = 'shared'
  sharedRound = { ...sh, key: pairKey(sh.a, sh.b) }
  return pair
}
function friendLine(a, b, winner) {
  if (!sharedRound?.pick || sharedRound.key !== pairKey(a.id, b.id)) return null
  const fw = BYID[sharedRound.pick === 'a' ? sharedRound.a : sharedRound.b]
  if (!fw) return null
  const agree = fw.id === winner
  return { agree, text: agree ? `You agreed with your friend: ${fw.comic}.` : `You disagreed. Your friend picked ${fw.comic}.` }
}
function clashURL(a, b, pick) {
  const base = IS_LOCAL ? BASE : SHARE_BASE
  return `${base}#clash/${encodeURIComponent(a.id)}/${encodeURIComponent(b.id)}${pick === 'a' || pick === 'b' ? '&pick=' + pick : ''}`
}
function myPick(a, b) {
  const v = [...LS.get('votes', []), ...LS.get('partials', [])].filter((x) => x && pairKey(x.a, x.b) === pairKey(a.id, b.id)).pop()
  return v ? (v.winner === a.id ? 'a' : v.winner === b.id ? 'b' : null) : null
}
function shareCurrent() {
  if (!current || !current[0] || !current[1]) return toast('Nothing on screen to share yet.')
  pauseBallot('Countdown paused. Pick when you\u2019re ready.') // sharing mid-ballot pauses the 3s countdown
  const [a, b] = current
  shareClash(a, b, myPick(a, b))
}
async function copyText(t) {
  try { await navigator.clipboard.writeText(t); return true } catch {}
  try {
    const ta = document.createElement('textarea'); ta.value = t; ta.setAttribute('readonly', ''); ta.style.cssText = 'position:fixed;opacity:0;top:0'
    document.body.appendChild(ta); ta.select(); const ok = document.execCommand('copy'); ta.remove(); return ok
  } catch { return false }
}
async function shareClash(a, b, pick) {
  if (!a || !b) return
  const url = clashURL(a, b, pick)
  const text = pick ? `I picked my winner. ${a.comic} vs ${b.comic}: which is funnier?` : `${a.comic} vs ${b.comic}: which is funnier?`
  if (navigator.share) {
    try { await navigator.share({ title: 'Funnier: settle this clash', text, url }); return }
    catch (e) { if (e && e.name === 'AbortError') return }
  }
  if (await copyText(url)) toast(pick ? 'Link copied. Your friend sees your pick only after they vote.' : 'Link copied. Send it to a friend.')
  else toast('Copy this link: ' + url)
}

// ---------- utils ----------
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])) }
let tt
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => t.classList.remove('on'), 3200) }
function tabs() {
  const show = (id) => {
    document.querySelectorAll('nav [data-tab]').forEach((b) => b.classList.toggle('on', b.dataset.tab === id))
    document.querySelectorAll('section.view').forEach((s) => (s.hidden = s.id !== 'v-' + id))
    if (id !== 'arena') Object.values(screens).forEach((s) => s.pause())
    document.body.classList.toggle('in-theatre', id === 'arena' && (stage === 'left' || stage === 'right'))
    scrollTo({ top: 0 })
    updateChrome()
  }
  showTab = show
  const brand = $('#brand')
  if (brand) brand.onclick = (e) => { // the logo always brings you back to the screening
    e.preventDefault()
    const wasAway = !arenaOn()
    if (location.hash) history.replaceState(null, '', location.pathname + location.search)
    show('arena'); showChrome(2500)
    if (wasAway && (stage === 'left' || stage === 'right')) screens[stage === 'left' ? 'L' : 'R']?.play()
  }
  document.querySelectorAll('[data-tab]').forEach((b) => (b.onclick = (e) => { e.preventDefault(); if (b.dataset.tab === 'comics') location.hash = 'comics'; show(b.dataset.tab) }))
  const route = () => {
    const sh = parseClash(location.hash)
    if (sh) { pendingClash = sh; history.replaceState(null, '', location.pathname + location.search); show('arena'); if (CLIPS.length) goNext(null); return }
    if (/^#comic/.test(location.hash)) { show('comics'); paintComics() }
  }
  addEventListener('hashchange', route)
  show('arena'); window._route = route
}

;(async () => {
  tabs()
  await loadData()
  MODEL = fitLocal(); TRAITS = fitTraits()
  const sh = parseClash(location.hash)
  if (sh) { pendingClash = sh; history.replaceState(null, '', location.pathname + location.search) }
  laneSelect(); bindGestures(); bindChrome(); newRound(true); paintBoards(); paintYou(); paintComics(); paintBanner(); window._route()
  initAuth()
})()
