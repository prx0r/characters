# DATA PROVENANCE — verified origins and corrections

Corrections to source descriptions that don't match their contents.
Verified against the actual data, not the marketing copy.

## scrapsfromtheloft.com — the real thing

- **What it is**: a transcript blog (`scrapsfromtheloft.com`), not a comedy
  club. 599 stand-up transcripts indexed by comedian/special.
- **HF mirror**: `zachgitt/comedy-transcripts` — 419 rows, 19.4 MB,
  description accurately says "scraped from https://scrapsfromtheloft.com".
- **Our copy**: R2 `comedy-specials/transcripts/` — 29 UK comedian
  transcripts, each labeled `"source": "scrapsfromtheloft"` + `source_url`.

## Kaggle `abhinandansharma19/comedians-transcript` — "Comedy Scraps Corpus" (CORRECTED)

- **Do not cite its description.** It claims the corpus was "compiled from
  performances held at 'The Loft' comedy club from 2020 to 2022". There is no
  such club; the name is riffing on scrapsfromtheloft.com, and the club story
  is fabricated.
- **Actual contents** (verified 2026-10-18): 5 pickle files, ~850 KB total:
  - `corpus.pkl` — 20 rows (one per comedian), single blob of text each
  - `dtm.pkl` — 20 × 10,005 term-document matrix
  - `cv.pkl` — CountVectorizer (10,005 terms)
  - `data_clean.pkl`, `data_dtm_NLP3.pkl` — preprocessing artifacts
- **Text format**: closed-caption style with bracketed directions
  (`[rock music playing]`, `[crowd cheering]`), not the site's transcript
  format. So it is neither a mirror of the HF scrape nor club recordings.
- **It is not a mirror** of the 419-transcript HF dataset (20 docs vs 419;
  850 KB vs 19.4 MB). The 20 comedians: Adam Devine, Andrew Santino, Dave
  Chappelle, Drew Michael, Eric Andre, Gary Gulman, Iliza Shlesinger, John
  Mulaney, Maria Bamford, Marlon Wayans, Mike Epps, Neal Brennan, Patton
  Oswalt, Pete Davidson, Ricky Gervais, Shane Gillis, Tig Notaro, Tom Segura,
  Trevor Noah, Vir Das.
- **Verdict**: ignore this dataset; the HF scrape supersedes it. Never
  describe it as a corpus of club performances.
