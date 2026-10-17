"""R2 cleanup: fix comedian attribution + normalize clip/audio key names.

- Fallback folder `comedians/nextup-comedy/`: recover the comedian from the
  title (parens like "(Ayoade Bamgboye: ...)" or hashtags like #davelandau)
  and re-file under the correct comedian.
- Old scheme `nextup-{vid}.json` / `nextup-{vid}.m4a`: if the new-scheme
  `{comedian}-{vid}` key exists, delete the old; otherwise rename.
- `--dry-run` prints what would change.

Usage: python3 r2_cleanup.py [--dry-run]
"""
from __future__ import annotations
import json, os, re, sys

import boto3

R2_ENDPOINT = "https://954612afb5a97bb15dddcdc70176813d.r2.cloudflarestorage.com"
R2_KEY = "36c9d71d3defa6b43f53536bdc6f65f3"
R2_SECRET = "c55689c3f176e4b839a7fb93861778960ed1020ba6253decec11538e7b187691"
R2_BUCKET = "comedy-specials"

s3 = boto3.client("s3", endpoint_url=R2_ENDPOINT,
                  aws_access_key_id=R2_KEY, aws_secret_access_key=R2_SECRET,
                  region_name="auto")

HASHTAG_NAMES = {
    "davelandau": "Dave Landau",
    "lonilove": "Loni Love",
    "ayoadebamgboye": "Ayoade Bamgboye",
}

KNOWN_NAMES = [
    "Josh Jones", "Geoff Norcott", "Rosco McClelland", "Susie McCabe",
    "Alasdair Beckett-King", "Clinton Baptiste", "Tom Ward", "Jen Brister",
    "Jason Byrne", "Zoe Lyons", "Emmanuel Sonubi", "Rachel Parris",
    "Ted Hill", "Lou Taylor", "Miles Jupp", "Hal Cruttenden",
    "Marcus Brigstocke", "Tommy Tiernan", "Bill Hicks", "Dominic Holland",
    "Stuart Laws", "Lara Ricote", "Markus Birdman", "President Obonjo",
    "Alison Spittle", "Alistair Barrie", "Paul Sinha", "Isabelle Farah",
    "Paddy Young", "Ricky Balshaw", "Russell Hicks", "Josh Glanc",
    "Andy Parsons", "Kiri Pritchard-McLean", "Ian Smith", "Sukh Kaur Ojla",
    "Angela Barnes", "Lucy Porter", "Milton Jones", "Felicity Ward",
    "Chris Forbes", "Sarah Roberts", "Andrew White",
    "Ayoade Bamgboye", "Dave Landau", "Loni Love",
]

FOLDER_FIXES = {  # mistyped folder slug -> canonical name
    "marcus-brigstock": "Marcus Brigstocke",
    "jason-bryne": "Jason Byrne",
}


def slugify(s: str, maxlen: int = 60) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:maxlen]


def recover_name(title: str) -> str | None:
    m = re.search(r"\(([A-Z][a-zA-Z'\u2019\-]+(?:\s+[A-Z][a-zA-Z'\u2019\-]+){0,2})\s*[:)]", title)
    if m:
        return m.group(1).strip()
    low = title.lower()
    for name in sorted(KNOWN_NAMES, key=len, reverse=True):
        if name.lower() in low:
            return name
    for tag in re.findall(r"#([A-Za-z]+)", title):
        name = HASHTAG_NAMES.get(tag.lower())
        if name:
            return name
    return None


def list_keys(prefix: str) -> list[dict]:
    keys, token = [], None
    while True:
        kw = {"Bucket": R2_BUCKET, "Prefix": prefix, "MaxKeys": 1000}
        if token:
            kw["ContinuationToken"] = token
        resp = s3.list_objects_v2(**kw)
        keys.extend({"Key": o["Key"], "Size": o["Size"]} for o in resp.get("Contents", []))
        if not resp.get("IsTruncated"):
            break
        token = resp.get("NextContinuationToken")
    return keys


def main():
    dry = "--dry-run" in sys.argv
    all_keys = {o["Key"] for o in list_keys("comedians/")}

    # --- 1. Fallback folders: comedians/nextup-comedy/{clips,audio} ---
    for obj in list_keys("comedians/nextup-comedy/"):
        key = obj["Key"]
        if key.endswith(".json"):
            data = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
            name = recover_name(data.get("title", ""))
            if not name:
                print(f"UNRESOLVED: {key} — {data.get('title', '')[:70]}")
                continue
            data["comedian"] = name
            cslug = slugify(name)
            vid = data.get("id", "")
            new_json = f"comedians/{cslug}/clips/{cslug}-{slugify(vid)}.json"
            print(f"FALLBACK {key} -> {new_json}  ({name})")
            if not dry:
                s3.put_object(Bucket=R2_BUCKET, Key=new_json,
                              Body=json.dumps(data, ensure_ascii=False).encode(),
                              ContentType="application/json")
                # audio: same basename if present
                old_audio = key.replace("/clips/", "/audio/").replace(".json", ".m4a")
                new_audio = f"comedians/{cslug}/audio/{cslug}-{slugify(vid)}.m4a"
                if old_audio in all_keys:
                    s3.copy_object(Bucket=R2_BUCKET, Key=new_audio,
                                   CopySource={"Bucket": R2_BUCKET, "Key": old_audio})
                    s3.delete_object(Bucket=R2_BUCKET, Key=old_audio)
                    print(f"  audio -> {new_audio}")
                s3.delete_object(Bucket=R2_BUCKET, Key=key)
        # audio is moved together with its json above; true orphans are left alone

    # --- 2. Old-scheme keys under comedian folders: nextup-{vid}.{ext} ---
    for obj in list_keys("comedians/"):
        key = obj["Key"]
        m = re.match(r"comedians/([^/]+)/(clips|audio)/nextup-([a-z0-9\-]+)\.(json|m4a)$", key)
        if not m:
            continue
        cslug, kind, vid, ext = m.groups()
        new_key = f"comedians/{cslug}/{kind}/{cslug}-{vid}.{ext}"
        if new_key in all_keys:
            print(f"DUP REMOVE {key} (new-scheme exists)")
            if not dry:
                s3.delete_object(Bucket=R2_BUCKET, Key=key)
        else:
            print(f"RENAME {key} -> {new_key}")
            if not dry:
                s3.copy_object(Bucket=R2_BUCKET, Key=new_key,
                               CopySource={"Bucket": R2_BUCKET, "Key": key})
                s3.delete_object(Bucket=R2_BUCKET, Key=key)

    # --- 3c. Folder fixes (mistyped slugs) + display-name normalization ---
    for obj in list_keys("comedians/"):
        key = obj["Key"]
        m = re.match(r"comedians/([^/]+)/(clips|audio)/(.+)$", key)
        if not m:
            continue
        cslug, kind, fname = m.groups()
        canonical = FOLDER_FIXES.get(cslug)
        if canonical:
            new_cslug = slugify(canonical)
            new_fname = (fname.replace(f"{cslug}-", f"{new_cslug}-", 1)
                         if fname.startswith(f"{cslug}-") else fname)
            new_key = f"comedians/{new_cslug}/{kind}/{new_fname}"
            print(f"FOLDER FIX {key} -> {new_key}")
            if not dry:
                if kind == "clips":
                    data = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
                    data["comedian"] = canonical
                    s3.put_object(Bucket=R2_BUCKET, Key=new_key,
                                  Body=json.dumps(data, ensure_ascii=False).encode(),
                                  ContentType="application/json")
                else:
                    s3.copy_object(Bucket=R2_BUCKET, Key=new_key,
                                   CopySource={"Bucket": R2_BUCKET, "Key": key})
                s3.delete_object(Bucket=R2_BUCKET, Key=key)
        elif kind == "clips":
            name = next((n for n in KNOWN_NAMES if slugify(n) == cslug), None)
            if name:
                data = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
                if data.get("comedian") != name:
                    print(f"NAME FIX {key}: {data.get('comedian')!r} -> {name!r}")
                    if not dry:
                        data["comedian"] = name
                        s3.put_object(Bucket=R2_BUCKET, Key=key,
                                      Body=json.dumps(data, ensure_ascii=False).encode(),
                                      ContentType="application/json")

    # --- 3a. Normalize clip metadata: ensure `id` exists (= video_id) ---
    clips = [o for o in list_keys("comedians/")
             if re.match(r"comedians/[^/]+/clips/.+\.json$", o["Key"])]
    stem_map = {}  # any historical stem -> (comedian_slug, current clip stem)
    for o in clips:
        key = o["Key"]
        cslug = key.split("/")[1]
        stem = key.split("/")[-1][:-5]
        data = json.loads(s3.get_object(Bucket=R2_BUCKET, Key=key)["Body"].read())
        vid = data.get("id") or data.get("video_id")
        if vid and not data.get("id"):
            print(f"NORMALIZE add id={vid} -> {key}")
            if not dry:
                data["id"] = vid
                s3.put_object(Bucket=R2_BUCKET, Key=key,
                              Body=json.dumps(data, ensure_ascii=False).encode(),
                              ContentType="application/json")
        if vid:
            vslug = slugify(vid)
            stem_map[vslug] = (cslug, stem)
            stem_map[f"{cslug}-{vslug}"] = (cslug, stem)
            stem_map[f"nextup-{vslug}"] = (cslug, stem)

    # --- 3b. Legacy prefixes: shorts/ (dupes) + shorts-audio/ (migrate to audio/) ---
    for obj in list_keys("shorts-audio/"):
        key = obj["Key"]
        stem = key.split("/")[-1][:-4]
        match = stem_map.get(stem)
        if not match:
            print(f"UNMATCHED legacy audio: {key}")
            continue
        cslug, clip_stem = match
        new_key = f"comedians/{cslug}/audio/{clip_stem}.m4a"
        if new_key in all_keys:
            print(f"LEGACY DUP REMOVE {key}")
            if not dry:
                s3.delete_object(Bucket=R2_BUCKET, Key=key)
            continue
        print(f"MIGRATE {key} -> {new_key}")
        if not dry:
            s3.copy_object(Bucket=R2_BUCKET, Key=new_key,
                           CopySource={"Bucket": R2_BUCKET, "Key": key})
            s3.delete_object(Bucket=R2_BUCKET, Key=key)

    for obj in list_keys("shorts/"):
        key = obj["Key"]
        stem = key.split("/")[-1][:-5]
        if stem in stem_map:
            print(f"LEGACY DUP REMOVE {key}")
            if not dry:
                s3.delete_object(Bucket=R2_BUCKET, Key=key)
        else:
            print(f"UNMATCHED legacy clip: {key}")

    print("dry-run done" if dry else "cleanup done")


if __name__ == "__main__":
    main()
