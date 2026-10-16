// Checks the characters2 import: theory.json is compact and text-free; the clip->special join and the time map behave.
// Usage (from funnier/): node tools/test-theory.mjs [--c2 ../../characters2]
import fs from 'node:fs'
import path from 'node:path'
import { bitAt, bitsInWindow, posAt } from '../tally/bitmap.mjs'
const arg = (k) => { const i = process.argv.indexOf(k); return i > 0 ? process.argv[i + 1] : null }
const C2 = path.resolve(arg('--c2') || process.env.CHARACTERS2 || '../../characters2')
const fails = [], ok = (c, m) => { if (!c) fails.push(m); console.log((c ? 'PASS ' : 'FAIL ') + m) }
const raw = fs.readFileSync('site/theory.json', 'utf8'), T = JSON.parse(raw), clips = JSON.parse(fs.readFileSync('clips.json', 'utf8'))
ok(raw.length < 40000, `theory.json is compact (${(raw.length / 1024).toFixed(1)} KB)`)
ok(!/"(text|setup|punch_candidate|bit_id)"/.test(raw), 'theory.json carries no bit text or bit rows')
const comicsInClips = [...new Set(clips.map((c) => c.comic))]
ok(comicsInClips.every((c) => T.comics[c]?.ops && T.comics[c]?.sty), 'every comic in clips.json has operator priors + stylometry')
ok(clips.every((c) => 'special_id' in c), 'every clip has special_id (null when the title names no known special)')
ok(clips.filter((c) => c.special_id).every((c) => T.specials[c.special_id]?.durSec > 0), 'every matched special has a duration')
ok(clips.filter((c) => /outtake/i.test(c.title)).every((c) => c.special_id === null), 'outtakes are never mapped into a special')
const norm = clips.find((c) => c.id === 'gN02rRbOlUE')
ok(norm?.special_id === 'norm-macdonald-nothing-special-transcript', 'Nothing Special clip -> norm-macdonald-nothing-special-transcript')
const bp = path.join(C2, 'theory/transcripts/bits_annotated/norm-macdonald/norm-macdonald-nothing-special-transcript.bits.json')
if (fs.existsSync(bp) && norm?.t_start != null) {
  const bits = JSON.parse(fs.readFileSync(bp, 'utf8')).bits, sp = T.specials[norm.special_id]
  const b = bitAt(norm, sp, bits, 20)
  ok(b && /opinion/i.test(bits.slice(bits.indexOf(b) - 3, bits.indexOf(b) + 4).map((x) => x.text).join(' ')), 'time map: 20s into the clip lands on the opinions bit')
  const w = bitsInWindow(norm, sp, bits, 10, 40)
  ok(w.length >= 1 && w.every((x) => x.feat.pos_in_special >= posAt(norm, sp, 10) && x.feat.pos_in_special <= posAt(norm, sp, 40)), `time map: a 30s window maps to ${w.length} bits inside it`)
  ok(bitsInWindow(norm, sp, bits, 12, 12).length === 1, 'time map: a zero-length window gives the bit that was playing')
  ok(bitsInWindow({ ...norm, t_start: null }, sp, bits, 0, 30).length === 0, 'time map: no t_start -> no bits (falls back to special level)')
} else console.log('SKIP time-map checks (no characters2 clone or no t_start)')
console.log(fails.length ? `${fails.length} FAILED` : 'ALL PASS'); process.exit(fails.length ? 1 : 0)
