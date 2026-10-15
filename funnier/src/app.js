import { BrowserOAuthClient } from '@atproto/oauth-client-browser'

const COLLECTION = 'io.github.prx0r.funnier.vote'
const BASE = new URL('.', location.href).href.replace(/#.*$/, '')
const IS_LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname)
const $ = (s) => document.querySelector(s)
const LS = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem('funnier.' + k)) ?? d } catch { return d } },
  set: (k, v) => localStorage.setItem('funnier.' + k, JSON.stringify(v)),
}

let CLIPS = [], BYID = {}, BOARD = null, PAIRS = []
let LANE = LS.get('lane', 'human'), BOARDKIND = 'all'
const GATE_SEC = 30
let client = null, agent = null, me = null
let current = null

// ---------- data ----------
async function loadData() {
  CLIPS = (await (await fetch('clips.json', { cache: 'no-cache' })).json()).filter((c) => c.status !== 'removed')
  BYID = Object.fromEntries(CLIPS.map((c) => [c.id, c]))
  try { BOARD = await (await fetch('data/leaderboard.json', { cache: 'no-cache' })).json() } catch { BOARD = null }
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
  if (me) b.innerHTML = q.length ? `Publishing ${q.length} vote(s)…` : `Your votes are published to your Bluesky account and counted on the global board.`
  else b.innerHTML = `You can vote now. <b>Sign in with Bluesky</b> to make your votes count on the global board${q.length ? ` (${q.length} waiting)` : ''}.`
}

async function publish(v) {
  const res = await agent.fetchHandler('/xrpc/com.atproto.repo.createRecord', {
    method: 'POST', headers: { 'content-type': 'application/json' },
    body: JSON.stringify({ repo: me.did, collection: COLLECTION,
      record: { $type: COLLECTION, a: v.a, b: v.b, winner: v.winner, voter: 'human', basis: v.basis || 'watched', createdAt: v.createdAt } }),
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

// ---------- arena ----------
function pairKey(a, b) { return [a, b].sort().join('|') }

function laneOK(a, b) {
  if (LANE === 'mixed') return true
  return a.kind === LANE && b.kind === LANE
}

function pickPair() {
  const done = new Set(LS.get('votes', []).map((v) => pairKey(v.a, v.b)))
  const skipped = new Set(LS.get('skipped', []))
  const open = (a, b) => BYID[a] && BYID[b] && !done.has(pairKey(a, b)) && !skipped.has(pairKey(a, b)) && laneOK(BYID[a], BYID[b])
  // exploit: sample from the most informative pairs the backend computed (weighted by w); explore 20% of the time
  const ranked = LANE === 'mixed' ? [] : PAIRS.filter((p) => open(p.a, p.b)).slice(0, 40)
  if (ranked.length && Math.random() > 0.2) {
    const tot = ranked.reduce((s, p) => s + p.w, 0)
    let r = Math.random() * tot
    for (const p of ranked) { r -= p.w; if (r <= 0) return Math.random() < 0.5 ? [BYID[p.a], BYID[p.b]] : [BYID[p.b], BYID[p.a]] }
  }
  const seen = LS.get('seen', {})
  const pool = CLIPS.filter((c) => LANE === 'mixed' || c.kind === LANE)
  const order = [...pool].sort((x, y) => (seen[x.id] || 0) - (seen[y.id] || 0) || Math.random() - 0.5)
  for (const a of order) {
    const opts = pool.filter((b) => b.id !== a.id && open(a.id, b.id) && (LANE !== 'mixed' || b.kind !== a.kind || Math.random() < 0.3))
    if (!opts.length) continue
    const cross = opts.filter((b) => b.comic !== a.comic)
    const src = cross.length && Math.random() < 0.8 ? cross : opts
    const b = src[Math.floor(Math.random() * src.length)]
    return Math.random() < 0.5 ? [a, b] : [b, a]
  }
  return null
}

// ---------- players + watch gate ----------
let ytReady = null
function loadYT() {
  if (ytReady) return ytReady
  ytReady = new Promise((res) => {
    window.onYouTubeIframeAPIReady = () => res(window.YT)
    const t = document.createElement('script'); t.src = 'https://www.youtube.com/iframe_api'; document.head.appendChild(t)
  })
  return ytReady
}
const watched = { L: 0, R: 0 }, need = { L: GATE_SEC, R: GATE_SEC }
let gateTimer = null, players = {}

function card(c, side) {
  const tag = c.kind === 'ai' ? '<span class="chip ai">AI set</span>' : '<span class="chip">Human set</span>'
  const media = c.media === 'audio'
    ? `<div class="frame audio"><audio id="p${side}" controls preload="none" src="${esc(c.src)}"></audio></div>`
    : `<div class="frame"><div id="p${side}"></div></div>`
  const src = c.media === 'audio' ? esc(c.channel || 'Funnier') : `${esc(c.channel)} on YouTube`
  return `<article class="card">${media}
    <div class="meta"><h3>${esc(c.comic)} ${tag}</h3><p>${esc(c.title)} · <span class="src">${src}</span></p>
    <div class="bar"><i id="g${side}"></i></div></div>
    <button class="vote" data-side="${side}" disabled>${side === 'L' ? '← This one is funnier' : 'This one is funnier →'}</button>
  </article>`
}

function gatePaint() {
  for (const s of ['L', 'R']) { const el = $('#g' + s); if (el) el.style.width = Math.min(100, (100 * watched[s]) / need[s]) + '%' }
  const ok = (watched.L >= need.L && watched.R >= need.R) || LS.get('unlocked', false)
  document.querySelectorAll('.vote').forEach((b) => (b.disabled = !ok))
  const h = $('#gatehint'); if (h) h.textContent = ok ? 'Pick the funnier one.' : `Watch at least ${GATE_SEC}s of each to unlock voting.`
}

async function mountPlayers(a, b) {
  watched.L = watched.R = 0; need.L = need.R = GATE_SEC
  clearInterval(gateTimer); players = {}
  const YT = await loadYT()
  for (const [side, c] of [['L', a], ['R', b]]) {
    if (c.sec) need[side] = Math.min(GATE_SEC, Math.max(5, c.sec * 0.8))
    if (c.media === 'audio') { players[side] = { audio: $('#p' + side) }; continue }
    players[side] = new YT.Player('p' + side, {
      host: 'https://www.youtube-nocookie.com', videoId: c.id,
      playerVars: { rel: 0, playsinline: 1, modestbranding: 0 },
      events: { onReady: (e) => { const d = e.target.getDuration?.(); if (d) need[side] = Math.min(GATE_SEC, Math.max(5, d * 0.8)) } },
    })
  }
  gateTimer = setInterval(() => {
    for (const s of ['L', 'R']) {
      const p = players[s]; if (!p) continue
      const playing = p.audio ? !p.audio.paused : p.getPlayerState?.() === 1
      if (playing) watched[s] += 1
    }
    gatePaint()
  }, 1000)
  gatePaint()
}

function paintArena() {
  current = pickPair()
  const el = $('#arena')
  const lanes = `<div class="lanes">${[['human', 'Human sets'], ['ai', 'AI sets'], ['mixed', 'Human vs AI']].map(([k, l]) => `<button data-lane="${k}" class="${LANE === k ? 'on' : ''}">${l}</button>`).join('')}</div>`
  if (!current) {
    el.innerHTML = lanes + `<p class="empty">${LANE === 'ai' ? 'No AI sets are published yet. The first Freaktown sets are on the way.' : LANE === 'mixed' ? 'Human vs AI opens once AI sets are published.' : "You've judged every matchup here. More clips are coming."}</p>`
  } else {
    const [a, b] = current
    el.innerHTML = lanes + `<div class="duel">${card(a, 'L')}<div class="vs">VS</div>${card(b, 'R')}</div>
      <div class="row"><span id="gatehint" class="muted"></span><button id="skip" class="ghost">Skip this pair</button><button id="unlock" class="ghost">I already know both</button></div>`
    el.querySelectorAll('.vote').forEach((btn) => (btn.onclick = () => vote(btn.dataset.side)))
    $('#skip').onclick = () => { LS.set('skipped', [...LS.get('skipped', []), pairKey(a.id, b.id)]); bumpSeen(a.id, b.id); paintArena() }
    $('#unlock').onclick = () => { watched.L = need.L; watched.R = need.R; current.basis = 'prior'; gatePaint() }
    mountPlayers(a, b)
  }
  el.querySelectorAll('[data-lane]').forEach((b) => (b.onclick = () => { LANE = b.dataset.lane; LS.set('lane', LANE); paintArena() }))
}

function bumpSeen(...ids) { const s = LS.get('seen', {}); ids.forEach((i) => (s[i] = (s[i] || 0) + 1)); LS.set('seen', s) }

async function vote(side) {
  const [a, b] = current
  const v = { a: a.id, b: b.id, winner: side === 'L' ? a.id : b.id, voter: 'human', basis: current.basis || 'watched', createdAt: new Date().toISOString() }
  LS.set('votes', [...LS.get('votes', []), v])
  bumpSeen(a.id, b.id)
  const w = BYID[v.winner]
  if (agent) {
    try { await publish(v); toast(`Counted: ${w.comic} wins. Published to your Bluesky repo.`) }
    catch (e) { LS.set('queue', [...LS.get('queue', []), v]); toast('Saved; will publish when Bluesky responds.') }
  } else {
    LS.set('queue', [...LS.get('queue', []), v]); toast(`${w.comic} wins. Sign in to count it globally.`)
  }
  paintBanner(); paintYou(); paintArena()
}

// ---------- boards ----------
function paintBoards() {
  const metas = document.querySelectorAll('.boardmeta')
  const sel = `<div class="lanes">${[['all', 'Everyone'], ['human', 'Humans'], ['agent', 'Agents']].map(([k, l]) => `<button data-board="${k}" class="${BOARDKIND === k ? 'on' : ''}">${l}</button>`).join('')}</div>`
  document.querySelectorAll('.boardsel').forEach((x) => (x.innerHTML = sel))
  document.querySelectorAll('[data-board]').forEach((x) => (x.onclick = () => { BOARDKIND = x.dataset.board; paintBoards() }))
  const bd = BOARD?.boards?.[BOARDKIND]
  if (!bd || !bd.votes) {
    metas.forEach((m) => (m.textContent = BOARDKIND === 'agent' ? 'No agent votes yet. Agents vote via the AT Protocol API (see AGENTS-VOTING.md in the repo).' : 'No published votes yet. Sign in with Bluesky and cast the first one; the board recounts about every 15 minutes.'))
    $('#comics').innerHTML = $('#clips').innerHTML = ''
    return
  }
  const ago = Math.max(0, Math.round((Date.now() - Date.parse(BOARD.updated)) / 60000))
  metas.forEach((m) => (m.textContent = `${bd.votes} votes from ${bd.voters} account${bd.voters === 1 ? '' : 's'} · Bradley-Terry rating with 95% interval · recounted ${isNaN(ago) ? 'recently' : ago + ' min ago'}${bd.votes < 100 ? ' · early days, intervals are wide' : ''}`))
  const ci = (r) => (r.lo != null ? `<span class="ci">${Math.round(r.lo)}–${Math.round(r.hi)}</span>` : '')
  $('#comics').innerHTML = table(['#', 'Comic', 'Rating', '95% range', 'Win %', 'Bouts'],
    bd.comics.filter((c) => c.bouts).map((c, i) => [i + 1, esc(c.comic), Math.round(c.elo), ci(c), pct(c.wins, c.bouts), c.bouts]))
  $('#clips').innerHTML = table(['#', 'Clip', 'Comic', 'Type', 'Rating', '95% range', 'Bouts'],
    bd.clips.filter((c) => c.bouts).map((c, i) => [i + 1, BYID[c.id]?.media === 'youtube' ? `<a href="https://www.youtube.com/watch?v=${c.id}" target="_blank" rel="noopener">${esc(BYID[c.id]?.title || c.id)}</a>` : esc(BYID[c.id]?.title || c.id), esc(c.comic), BYID[c.id]?.kind === 'ai' ? 'AI' : 'Human', Math.round(c.elo), ci(c), c.bouts]))
}

function paintYou() {
  const votes = LS.get('votes', [])
  const el = $('#you')
  if (!votes.length) { el.innerHTML = `<p class="empty">Vote a few times and your own humour ranking shows up here.</p>`; return }
  const elo = {}, wins = {}, bouts = {}
  for (const v of votes) {
    const A = BYID[v.a]?.comic, B = BYID[v.b]?.comic
    if (!A || !B || A === B) continue
    const ra = elo[A] ?? 1500, rb = elo[B] ?? 1500
    const ea = 1 / (1 + 10 ** ((rb - ra) / 400)), sa = v.winner === v.a ? 1 : 0
    elo[A] = ra + 32 * (sa - ea); elo[B] = rb + 32 * ((1 - sa) - (1 - ea))
    const W = sa ? A : B
    wins[W] = (wins[W] || 0) + 1; bouts[A] = (bouts[A] || 0) + 1; bouts[B] = (bouts[B] || 0) + 1
  }
  const rows = Object.keys(elo).sort((x, y) => elo[y] - elo[x]).map((c, i) => [i + 1, esc(c), Math.round(elo[c]), pct(wins[c] || 0, bouts[c]), bouts[c]])
  el.innerHTML = `<p class="muted">${votes.length} vote(s) on this device. This is the seed of your humour profile.</p>` + table(['#', 'Comic', 'Your Elo', 'Win %', 'Bouts'], rows) + '<div id="youglobal"></div>'
  if (me) fetch('data/taste/' + me.did.replace(/[^a-z0-9]/gi, '_') + '.json', { cache: 'no-cache' }).then((r) => (r.ok ? r.json() : null)).then((t) => {
    if (!t) return
    $('#youglobal').innerHTML = `<h3>Your published taste profile</h3><p class="muted">From ${t.votes} published vote(s), blended with the crowd until you have more. "vs crowd" shows where your taste departs.</p>` +
      table(['#', 'Comic', 'Your rating', 'vs crowd'], t.comics.map((c, i) => [i + 1, esc(c.comic), c.elo, (c.vsCrowd > 0 ? '+' : '') + c.vsCrowd]))
  }).catch(() => {})
}

// ---------- utils ----------
function table(h, rows) {
  return `<table><thead><tr>${h.map((x) => `<th>${x}</th>`).join('')}</tr></thead><tbody>${rows.map((r) => `<tr>${r.map((x) => `<td>${x}</td>`).join('')}</tr>`).join('')}</tbody></table>`
}
function pct(w, n) { return n ? Math.round((100 * w) / n) + '%' : '–' }
function esc(s) { return String(s).replace(/[&<>"']/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c])) }
let tt
function toast(m) { const t = $('#toast'); t.textContent = m; t.classList.add('on'); clearTimeout(tt); tt = setTimeout(() => t.classList.remove('on'), 3200) }

function tabs() {
  const show = (id) => {
    document.querySelectorAll('[data-tab]').forEach((b) => b.classList.toggle('on', b.dataset.tab === id))
    document.querySelectorAll('section.view').forEach((s) => (s.hidden = s.id !== 'v-' + id))
  }
  document.querySelectorAll('[data-tab]').forEach((b) => (b.onclick = () => show(b.dataset.tab)))
  show('arena')
}

;(async () => {
  tabs()
  await loadData()
  paintArena(); paintBoards(); paintYou(); paintBanner()
  initAuth()
})()
