import { BrowserOAuthClient } from '@atproto/oauth-client-browser'

const COLLECTION = 'io.github.prx0r.funnier.vote'
const BASE = new URL('.', location.href).href.replace(/#.*$/, '')
const IS_LOCAL = ['localhost', '127.0.0.1'].includes(location.hostname)
const $ = (s) => document.querySelector(s)
const LS = {
  get: (k, d) => { try { return JSON.parse(localStorage.getItem('funnier.' + k)) ?? d } catch { return d } },
  set: (k, v) => localStorage.setItem('funnier.' + k, JSON.stringify(v)),
}

let CLIPS = [], BYID = {}, BOARD = null
let client = null, agent = null, me = null
let current = null

// ---------- data ----------
async function loadData() {
  CLIPS = await (await fetch('clips.json', { cache: 'no-cache' })).json()
  BYID = Object.fromEntries(CLIPS.map((c) => [c.id, c]))
  try { BOARD = await (await fetch('data/leaderboard.json', { cache: 'no-cache' })).json() } catch { BOARD = null }
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
      record: { $type: COLLECTION, a: v.a, b: v.b, winner: v.winner, createdAt: v.createdAt } }),
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

function pickPair() {
  const done = new Set(LS.get('votes', []).map((v) => pairKey(v.a, v.b)))
  const seen = LS.get('seen', {})
  const order = [...CLIPS].sort((x, y) => (seen[x.id] || 0) - (seen[y.id] || 0) || Math.random() - 0.5)
  for (const a of order) {
    const pool = CLIPS.filter((b) => b.id !== a.id && !done.has(pairKey(a.id, b.id)))
    if (!pool.length) continue
    const cross = pool.filter((b) => b.comic !== a.comic)
    const src = cross.length && Math.random() < 0.8 ? cross : pool
    const b = src[Math.floor(Math.random() * src.length)]
    return Math.random() < 0.5 ? [a, b] : [b, a]
  }
  return null
}

function card(c, side) {
  return `<article class="card">
    <div class="frame"><iframe src="https://www.youtube-nocookie.com/embed/${c.id}?rel=0" title="${esc(c.title)}" allow="encrypted-media; picture-in-picture; fullscreen" allowfullscreen loading="lazy"></iframe></div>
    <div class="meta"><h3>${esc(c.comic)}</h3><p>${esc(c.title)} · <span class="src">${esc(c.channel)} on YouTube</span></p></div>
    <button class="vote" data-side="${side}">${side === 'L' ? '← This one is funnier' : 'This one is funnier →'}</button>
  </article>`
}

function paintArena() {
  current = pickPair()
  const el = $('#arena')
  if (!current) { el.innerHTML = `<p class="empty">You've judged every matchup we have. More clips are coming.</p>`; return }
  const [a, b] = current
  el.innerHTML = `<div class="duel">${card(a, 'L')}<div class="vs">VS</div>${card(b, 'R')}</div>
    <div class="row"><button id="skip" class="ghost">Skip this pair</button></div>`
  el.querySelectorAll('.vote').forEach((btn) => (btn.onclick = () => vote(btn.dataset.side)))
  $('#skip').onclick = () => { bumpSeen(a.id, b.id); paintArena() }
}

function bumpSeen(...ids) { const s = LS.get('seen', {}); ids.forEach((i) => (s[i] = (s[i] || 0) + 1)); LS.set('seen', s) }

async function vote(side) {
  const [a, b] = current
  const v = { a: a.id, b: b.id, winner: side === 'L' ? a.id : b.id, createdAt: new Date().toISOString() }
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
  if (!BOARD || !BOARD.votes) {
    metas.forEach(m=>m.textContent = 'No published votes yet. Sign in with Bluesky and cast the first one; the board recounts about every 15 minutes.')
    $('#comics').innerHTML = $('#clips').innerHTML = ''
    return
  }
  const ago = Math.round((Date.now() - Date.parse(BOARD.updated)) / 60000)
  metas.forEach(m=>m.textContent = `${BOARD.votes} votes from ${BOARD.voters} Bluesky account${BOARD.voters === 1 ? '' : 's'} · recounted ${ago} min ago · ${BOARD.votes < 30 ? 'early days, rankings will move' : ''}`)
  $('#comics').innerHTML = table(['#', 'Comic', 'Elo', 'Win %', 'Bouts'],
    BOARD.comics.map((c, i) => [i + 1, esc(c.comic), Math.round(c.elo), pct(c.wins, c.bouts), c.bouts]))
  $('#clips').innerHTML = table(['#', 'Clip', 'Comic', 'Elo', 'Win %', 'Bouts'],
    BOARD.clips.map((c, i) => [i + 1, `<a href="https://www.youtube.com/watch?v=${c.id}" target="_blank" rel="noopener">${esc(BYID[c.id]?.title || c.id)}</a>`, esc(BYID[c.id]?.comic || ''), Math.round(c.elo), pct(c.wins, c.bouts), c.bouts]))
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
  el.innerHTML = `<p class="muted">${votes.length} vote(s) on this device. This is the seed of your humour profile.</p>` + table(['#', 'Comic', 'Your Elo', 'Win %', 'Bouts'], rows)
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
