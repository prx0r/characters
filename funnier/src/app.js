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
      record: { $type: COLLECTION, a: v.a, b: v.b, winner: v.winner, voter: 'human', basis: v.basis || 'watched', ...(v.why ? { why: v.why } : {}), createdAt: v.createdAt } }),
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

// ---------- your model: personal hierarchical Bradley-Terry, prior = crowd chart ----------
function fitLocal() {
  const votes = LS.get('votes', []).filter((v) => BYID[v.a] && BYID[v.b])
  const g = {}
  for (const c of BOARD?.boards?.all?.comics || []) if (c.bouts) g[c.comic] = (c.elo - 1500) / SCALE
  const comics = [...new Set(CLIPS.map((c) => c.comic))]
  const r = Object.fromEntries(comics.map((k) => [k, g[k] || 0]))
  const o = Object.fromEntries(CLIPS.map((c) => [c.id, 0]))
  const bouts = {}
  for (const v of votes) { bouts[v.a] = (bouts[v.a] || 0) + 1; bouts[v.b] = (bouts[v.b] || 0) + 1 }
  for (let t = 0; t < 250; t++) {
    const gr = Object.fromEntries(comics.map((k) => [k, -0.5 * (r[k] - (g[k] || 0))]))
    const go = Object.fromEntries(CLIPS.map((c) => [c.id, -1.0 * o[c.id]]))
    for (const v of votes) {
      const A = BYID[v.a], B = BYID[v.b]
      const W = v.winner === v.a ? A : B, L = W === A ? B : A
      const p = sig((r[L.comic] + o[L.id]) - (r[W.comic] + o[W.id]))
      gr[W.comic] += p; gr[L.comic] -= p; go[W.id] += p; go[L.id] -= p
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
  const data = votes.map((v) => { const A = x(BYID[v.a]), B = x(BYID[v.b]); const d = {}; STYLES.forEach((t) => { d[t] = A[t] - B[t]; if (d[t]) n[t] = (n[t] || 0) + 1 }); return { d, y: v.winner === v.a ? 1 : 0 } })
  for (let it = 0; it < 300; it++) {
    const g = Object.fromEntries(STYLES.map((t) => [t, -0.6 * w[t]]))
    for (const { d, y } of data) { const p = sig(STYLES.reduce((s, t) => s + w[t] * d[t], 0)); STYLES.forEach((t) => (g[t] += (y - p) * d[t])) }
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
class Screen {
  constructor(side, clip) { this.side = side; this.clip = clip; this.started = false; this.ready = new Promise((res) => (this._ready = res)) }
  async mount() {
    const c = this.clip, host = $('#p' + this.side)
    this.start = c.start || 0
    if (c.media === 'audio') {
      host.innerHTML = `<audio preload="auto" controls src="${esc(c.src)}"></audio>`
      this.a = host.querySelector('audio')
      this.a.onloadedmetadata = () => this._ready()
      return
    }
    const YT = await loadYT()
    {
      const res = this._ready
      this.p = new YT.Player('p' + this.side, {
        host: 'https://www.youtube-nocookie.com', videoId: c.id,
        playerVars: { rel: 0, playsinline: 1, start: this.start, controls: 1 },
        events: { onReady: () => res(), onStateChange: (e) => { if (e.data === 0) this.ended = true } },
      })
    }
  }
  dur() { const d = this.a ? this.a.duration : this.p?.getDuration?.(); return d || this.clip.sec || 0 }
  end() { const d = this.dur(); return this.clip.end || (d ? Math.min(d, this.start + SHORT_MAX) : this.start + SHORT_MAX) }
  t() { return this.a ? this.a.currentTime : this.p?.getCurrentTime?.() || 0 }
  playing() { return this.a ? !this.a.paused : this.p?.getPlayerState?.() === 1 }
  progress() { const s = this.start, e = this.end(); return Math.max(0, Math.min(1, (this.t() - s) / Math.max(1, e - s))) }
  done() { return this.ended || this.t() >= this.end() - 0.3 }
  async play() {
    await this.ready; this.started = true
    if (this.a) { try { await this.a.play() } catch { toast('Tap the screen to start the sound') } return }
    this.p.playVideo()
    setTimeout(() => { // autoplay with sound refused: play muted and say so
      const st = this.p.getPlayerState?.()
      if (st !== 1 && st !== 3) { this.p.mute(); this.p.playVideo(); toast('Your browser started it muted. Tap the screen for sound.') }
    }, 1800)
  }
  pause() { this.a ? this.a.pause() : this.p?.pauseVideo?.() }
  destroy() { try { this.p?.destroy?.() } catch {} }
}

// ---------- the screening ----------
let screens = {}, phase = 'idle', tick = null, armed = false, prediction = null
function chip(c) { return c.kind === 'ai' ? '<span class="chip ai">AI</span>' : '' }
function screenHTML(c, side) {
  return `<div class="screen ${side} idle" id="s${side}">
    <div class="frame"><div id="p${side}"></div><div class="cover"><span class="ph">${side === 'L' ? 'ONE' : 'TWO'}</span></div></div>
    <div class="label"><span class="side">${side === 'L' ? '1' : '2'}</span>
      <div class="meta"><h3>${esc(c.comic)}${chip(c)}</h3><p>${esc(c.title)} · ${esc(c.channel || '')}</p></div>
      <span class="status" id="st${side}">${side === 'L' ? 'Up first' : 'Up next'}</span></div>
    <div class="prog"><i id="pg${side}"></i></div></div>`
}
function laneSelect() {
  const box = $('#lanebox')
  box.innerHTML = `<select id="lane">${[['human', 'Human comics'], ['ai', 'AI comics'], ['mixed', 'Human vs AI']].map(([k, l]) => `<option value="${k}" ${LANE === k ? 'selected' : ''}>${l}</option>`).join('')}</select>`
  $('#lane').onchange = (e) => { LANE = e.target.value; LS.set('lane', LANE); newRound(phase !== 'idle') }
}

function newRound(autoplay) {
  clearInterval(tick); Object.values(screens).forEach((s) => s.destroy()); screens = {}; armed = false
  current = pickPair()
  const el = $('#arena')
  if (!current) {
    $('#roundtag').textContent = 'Intermission'
    el.innerHTML = `<p class="empty">${LANE === 'ai' ? 'The AI comics are still in rehearsal. Their first sets premiere here soon.' : LANE === 'mixed' ? 'Human vs AI opens when the first AI sets premiere.' : "You've seen every double feature on the bill. New shorts arrive daily."}</p>`
    return
  }
  const [a, b] = current
  $('#roundtag').textContent = MODES[current.mode][0]
  const pL = MODEL ? sig(MODEL.score(a.id) + traitScore(a) - MODEL.score(b.id) - traitScore(b)) : 0.5
  prediction = { p: pL, side: pL >= 0.5 ? 'L' : 'R' }
  el.innerHTML = `<div class="theater"><div class="screens">${screenHTML(a, 'L')}${screenHTML(b, 'R')}</div>
    ${autoplay ? '' : `<div class="start"><div class="inner"><h2>Tonight's<br>double feature</h2><p>Two shorts, back to back. Then you pick the funnier one.</p><button class="play" id="go">▶ Start the show</button></div></div>`}</div>
    <div class="verdict" id="verdict">
      <button class="fbtn L" data-side="L">← FUNNIER</button>
      <div class="mid"><span class="vs">or</span><button id="replay">Replay</button><button id="skip">Skip pair</button></div>
      <button class="fbtn R" data-side="R">FUNNIER →</button></div>
    <p class="hint" id="hint"></p><div class="why" id="why"></div>`
  el.querySelectorAll('.fbtn').forEach((x) => (x.onclick = () => vote(x.dataset.side)))
  $('#skip').onclick = () => { LS.set('skipped', [...LS.get('skipped', []), pairKey(a.id, b.id)]); bumpSeen(a.id, b.id); newRound(true) }
  $('#replay').onclick = () => { screens.R?.pause(); screens.L.p?.seekTo?.(screens.L.start, true); if (screens.L.a) screens.L.a.currentTime = screens.L.start; screens.L.ended = false; phase = 'L'; screens.L.play() }
  screens = { L: new Screen('L', a), R: new Screen('R', b) }
  screens.L.mount(); screens.R.mount()
  phase = 'ready'
  const go = () => { $('.start')?.remove(); phase = 'L'; screens.L.play(); runTick() }
  if (autoplay) go(); else $('#go').onclick = go
}

function setLive(side) {
  for (const s of ['L', 'R']) {
    const el = $('#s' + s); if (!el) continue
    el.classList.toggle('live', s === side); el.classList.toggle('idle', s !== side)
  }
}
function runTick() {
  clearInterval(tick)
  tick = setInterval(() => {
    const L = screens.L, R = screens.R; if (!L || !R) return
    for (const s of ['L', 'R']) {
      const sc = screens[s], pg = $('#pg' + s), st = $('#st' + s)
      if (pg) pg.style.width = (sc.started ? 100 * sc.progress() : 0) + '%'
      if (sc.playing()) $('#s' + s + ' .cover')?.classList.add('gone')
      if (st) st.textContent = sc.playing() ? 'Now playing' : sc.started && sc.done() ? 'Seen' : sc.started ? 'Paused' : s === 'L' ? 'Up first' : 'Up next'
    }
    // whichever screen is actually playing is the live one (user may click around)
    if (R.playing()) { phase = 'R'; setLive('R') } else if (L.playing()) { phase = 'L'; setLive('L') }
    if (phase === 'L' && L.done()) { L.pause(); phase = 'R'; setLive('R'); R.play() }
    if (phase === 'R' && R.done()) R.pause()
    // the verdict arrives partway through the second short
    const secR = R.started ? R.t() - R.start : 0
    if (!armed && R.started && (R.progress() >= 0.4 || secR >= 20 || R.done())) {
      armed = true; $('#verdict')?.classList.add('on'); $('#hint').textContent = 'Use ← or → on your keyboard, too.'
    }
  }, 250)
}

async function vote(side) {
  if (!current || !armed) return
  const [a, b] = current
  const v = { a: a.id, b: b.id, winner: side === 'L' ? a.id : b.id, voter: 'human', basis: 'watched', mode: current.mode, createdAt: new Date().toISOString() }
  LS.set('votes', [...LS.get('votes', []), v])
  const preds = LS.get('preds', []); preds.push({ p: prediction.p, hit: prediction.side === side }); LS.set('preds', preds.slice(-200))
  // remember lengths for your model's length preference
  const dur = LS.get('dur', {}); dur[a.id] = screens.L.dur(); dur[b.id] = screens.R.dur(); LS.set('dur', dur)
  bumpSeen(a.id, b.id)
  const w = BYID[v.winner]
  const guess = MODEL && MODEL.n >= 3 ? (prediction.side === side ? ' Your model called it.' : ' Your model guessed the other one.') : ''
  if (agent) {
    try { await publish(v); toast(`${w.comic} takes it.${guess}`) }
    catch { LS.set('queue', [...LS.get('queue', []), v]); toast(`Saved. It'll publish when Bluesky responds.${guess}`) }
  } else { LS.set('queue', [...LS.get('queue', []), v]); toast(`${w.comic} takes it.${guess}`) }
  MODEL = fitLocal(); TRAITS = fitTraits()
  paintBanner(); paintYou(); newRound(true); askWhy(v)
}
const WHY = ['Smarter', 'Weirder', 'Darker', 'Better delivery', 'More relatable', 'Better payoff']
let whyT
function askWhy(v) {
  const box = $('#why'); if (!box) return
  box.innerHTML = `<span>Why was it funnier?</span>${WHY.map((w) => `<button>${w}</button>`).join('')}`
  box.classList.add('on'); clearTimeout(whyT); whyT = setTimeout(() => box.classList.remove('on'), 9000)
  box.querySelectorAll('button').forEach((b) => (b.onclick = () => {
    const votes = LS.get('votes', []); const last = votes[votes.length - 1]
    if (last && last.createdAt === v.createdAt) { last.why = b.textContent; LS.set('votes', votes) }
    const q = LS.get('queue', []); const lq = q.find((x) => x.createdAt === v.createdAt); if (lq) { lq.why = b.textContent; LS.set('queue', q) }
    box.classList.remove('on'); toast('Noted. Your model will use that.')
  }))
}
document.addEventListener('keydown', (e) => {
  if (e.target.tagName === 'INPUT') return
  if (e.key === 'ArrowLeft') vote('L'); if (e.key === 'ArrowRight') vote('R')
})

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
    <h3 class="shelf">Best-rated shorts</h3><div class="rail">${st.rated.map(({ c, r }, i) => clipTile(c, r ? i : null, r ? Math.round(r.elo) : c.channel)).join('')}</div>`
  scrollTo({ top: 0 })
}

// ---------- your model ----------
function paintYou() {
  const el = $('#you'), votes = LS.get('votes', [])
  if (!votes.length) {
    el.innerHTML = `<h2>Your model</h2><p class="empty">Every pick trains a small model of your sense of humour, right here on your device.<br>Watch a double feature to start it.</p>`
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
    ${(() => { const h = humourType(); return h ? `<div class="type"><span class="eyebrow">Your humour type</span><b>${h.name}</b><p>${h.line}${h.also ? ` With a streak of <i>${h.also}</i>.` : ''}</p></div>` : `<div class="type"><span class="eyebrow">Your humour type</span><b>Still reading you…</b><p>A few more picks across different styles and it will name your type.</p></div>` })()}
    <h3>Styles you laugh at</h3><div class="bars">${STYLES.map((t) => { const x = TRAITS.w[t] || 0, wd = Math.min(50, Math.abs(x) * 40); return `<div class="barrow"><span>${t}</span><div class="track center"><i style="left:${x >= 0 ? 50 : 50 - wd}%;width:${wd}%"></i></div><span class="v">${(TRAITS.n[t] || 0) < 2 ? 'learning' : (x > 0 ? '+' : '') + x.toFixed(2)}</span></div>` }).join('')}</div>
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

// ---------- utils ----------
function esc(s) { return String(s ?? '').replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])) }
let tt
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => t.classList.remove('on'), 3200) }
function tabs() {
  const show = (id) => {
    document.querySelectorAll('nav [data-tab]').forEach((b) => b.classList.toggle('on', b.dataset.tab === id))
    document.querySelectorAll('section.view').forEach((s) => (s.hidden = s.id !== 'v-' + id))
    if (id !== 'arena') Object.values(screens).forEach((s) => s.pause())
    scrollTo({ top: 0 })
  }
  document.querySelectorAll('[data-tab]').forEach((b) => (b.onclick = (e) => { e.preventDefault(); if (b.dataset.tab === 'comics') location.hash = 'comics'; show(b.dataset.tab) }))
  const route = () => { if (/^#comic/.test(location.hash)) { show('comics'); paintComics() } }
  addEventListener('hashchange', route)
  show('arena'); window._route = route
}

;(async () => {
  tabs()
  await loadData()
  MODEL = fitLocal(); TRAITS = fitTraits()
  laneSelect(); newRound(false); paintBoards(); paintYou(); paintComics(); paintBanner(); window._route()
  initAuth()
})()
