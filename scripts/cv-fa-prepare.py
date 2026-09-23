#!/usr/bin/env python3
"""Build the Persian phonetic judge from a local Common Voice Persian archive.

Common Voice is CC0, but Mozilla Data Collective asks that files are not
re-shared, so everything stays in gitignored data/cv-fa/ and never goes to the
API host. Download the archive in the browser and put it at
data/cv-fa/archive/cv-corpus-27.0-fa.tar.gz, with validated.tsv and
clip_durations.tsv extracted next to it.

Reference IPA comes from persian_phonemizer. Sentences with any word outside
its dictionary are dropped, because its neural fallback guesses badly.
Output: data/cv-fa/refs.jsonl and data/cv-fa/cache/<clip>.ipa.txt.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import random
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["INVENTORY_PATH"] = str(ROOT / "schemas/gilaki_inventory.json")
os.environ["PRESETS_DIR"] = str(ROOT / "schemas/presets")
sys.path.insert(0, str(ROOT / "api"))

from app.asr import AllosaurusBackend  # noqa: E402
from app.audio import prepare_audio  # noqa: E402

DATA = ROOT / "data" / "cv-fa"
ARCHIVE = DATA / "archive" / "cv-corpus-27.0-fa.tar.gz"
PREFIX = "cv-corpus-27.0-2026-09-11/fa/clips/"
CLIPS = DATA / "clips"
CACHE = DATA / "cache"
REFS = DATA / "refs.jsonl"
PER_SPEAKER = 20
SEED = 1404

csv.field_size_limit(sys.maxsize)


def candidates() -> list[dict]:
    durations = {}
    with open(DATA / "clip_durations.tsv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            durations[row["clip"]] = int(row["duration[ms]"]) / 1000
    by_speaker: dict[str, list[dict]] = defaultdict(list)
    with open(DATA / "validated.tsv", encoding="utf-8") as fh:
        for row in csv.DictReader(fh, delimiter="\t", quoting=csv.QUOTE_NONE):
            seconds = durations.get(row["path"], 0)
            if int(row["up_votes"] or 0) < 2 or int(row["down_votes"] or 0) > 0:
                continue
            if not 2.0 <= seconds <= 8.0:
                continue
            by_speaker[row["client_id"]].append(
                {"path": row["path"], "client_id": row["client_id"], "sentence": row["sentence"], "seconds": seconds}
            )
    rng = random.Random(SEED)
    picked = []
    for speaker in sorted(by_speaker):
        rows = by_speaker[speaker]
        rng.shuffle(rows)
        picked.extend(rows[:PER_SPEAKER])
    rng.shuffle(picked)
    return picked


class Lexicon:
    """persian_phonemizer, with a flag for words it had to guess."""

    def __init__(self) -> None:
        from persian_phonemizer import Phonemizer

        self.inner = Phonemizer()
        self.guessed = 0
        original = self.inner.predict_pronounce

        def flagged(word: str) -> str:
            self.guessed += 1
            return original(word)

        self.inner.predict_pronounce = flagged

    def known(self, sentence: str) -> str | None:
        self.guessed = 0
        try:
            ipa = self.inner.phonemize(sentence)
        except (KeyError, IndexError):
            return None
        return None if self.guessed else ipa


def extract(paths: list[str]) -> None:
    missing = [p for p in paths if not (CLIPS / p).exists()]
    if not missing:
        return
    CLIPS.mkdir(parents=True, exist_ok=True)
    listing = DATA / "extract-list.txt"
    listing.write_text("".join(PREFIX + p + "\n" for p in missing), encoding="utf-8")
    subprocess.run(
        ["tar", "-xzf", str(ARCHIVE), "-C", str(CLIPS), "--strip-components", "3", "-T", str(listing)],
        check=True,
    )
    listing.unlink()


def recognize(path: str) -> str:
    dest = CACHE / f"{path}.ipa.txt"
    if dest.exists():
        return dest.read_text(encoding="utf-8").strip()
    prepared = prepare_audio((CLIPS / path).read_bytes(), max_duration_sec=60)
    result = AllosaurusBackend().recognize(prepared.wav_bytes)
    dest.write_text(result.ipa_string + "\n", encoding="utf-8")
    return result.ipa_string


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=3000)
    args = parser.parse_args()

    refs = []
    if REFS.exists():
        refs = [json.loads(line) for line in REFS.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(refs) < args.count:
        lexicon = Lexicon()
        seen = {row["path"] for row in refs}
        tried = 0
        for row in candidates():
            if len(refs) >= args.count:
                break
            if row["path"] in seen:
                continue
            tried += 1
            ipa = lexicon.known(row["sentence"])
            if ipa:
                refs.append({**row, "ref_ipa": ipa})
        print(f"kept {len(refs)} of {tried} sentences tried (dictionary words only)")
        REFS.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in refs), encoding="utf-8")

    extract([r["path"] for r in refs])
    CACHE.mkdir(parents=True, exist_ok=True)
    for i, row in enumerate(refs, start=1):
        recognize(row["path"])
        if i % 250 == 0:
            print(f"recognized {i}", flush=True)
    speakers = len({r["client_id"] for r in refs})
    print(f"{len(refs)} clips, {speakers} speakers, cache {CACHE}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
