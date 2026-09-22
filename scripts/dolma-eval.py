#!/usr/bin/env python3
"""Score DOLMA Gilaki sentences against each writing map.

Downloads razhan/DOLMA-speech config `gilaki` into data/dolma/ (gitignored).
The dataset card states no license, so clips are not committed and are not
copied onto the API host.

Gold text is Arabic-script spelling, not IPA. The picked map is the one with
the lowest character error rate on the test split after Persian letter
normalization and stripping Arabic diacritics. Recognition uses Allosaurus
in this machine's repo-root .venv.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["INVENTORY_PATH"] = str(ROOT / "schemas/gilaki_inventory.json")
os.environ["PRESETS_DIR"] = str(ROOT / "schemas/presets")
sys.path.insert(0, str(ROOT / "api"))

from app.asr import AllosaurusBackend  # noqa: E402
from app.audio import prepare_audio  # noqa: E402
from app.catalog import load_presets  # noqa: E402
from app.rewriter import apply_map  # noqa: E402

DATA = ROOT / "data" / "dolma" / "gilaki"
HF = "https://huggingface.co/datasets/razhan/DOLMA-speech/resolve/main/gilaki"
FILES = {
    "test": "test-00000-of-00001.parquet",
    "train": "train-00000-of-00001.parquet",
}
# Arabic diacritics, superscript alef, tatweel. Letters such as ۊ stay.
_STRIP = dict.fromkeys(list(range(0x064B, 0x0660)) + [0x0640, 0x0670], None)


def download() -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    for name in FILES.values():
        dest = DATA / name
        if dest.exists() and dest.stat().st_size > 1_000_000:
            print(f"have {dest.name}")
            continue
        url = f"{HF}/{name}"
        print(f"download {url}")
        urllib.request.urlretrieve(url, dest)
        print(f"wrote {dest} ({dest.stat().st_size} bytes)")


def normalize_ortho(text: str, *, strip_marks: bool) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u200c", "").replace("\u200d", "")
    text = text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    if strip_marks:
        text = text.translate(_STRIP)
    return "".join(ch for ch in text if not ch.isspace())


def levenshtein(ref: list[str], hyp: list[str]) -> int:
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1]


def cer(reference: str, hypothesis: str) -> float:
    if not reference:
        return 0.0 if not hypothesis else 1.0
    return levenshtein(list(reference), list(hypothesis)) / len(reference)


def rows(split: str):
    import pyarrow.parquet as pq

    path = DATA / FILES[split]
    if not path.exists():
        download()
    table = pq.read_table(path)
    for i in range(table.num_rows):
        audio = table.column("audio")[i].as_py()
        yield {
            "id": int(table.column("id")[i].as_py()),
            "sentence": table.column("sentence")[i].as_py() or "",
            "english": table.column("english")[i].as_py() or "",
            "audio": audio["bytes"],
        }


def ipa_for(clip: dict, cache: Path) -> str:
    dest = cache / f"{clip['id']}.ipa.txt"
    if dest.exists():
        return dest.read_text(encoding="utf-8").strip()
    prepared = prepare_audio(clip["audio"], max_duration_sec=60)
    result = AllosaurusBackend().recognize(prepared.wav_bytes)
    dest.write_text(result.ipa_string + "\n", encoding="utf-8")
    return result.ipa_string


def main() -> int:
    split = "test"
    limit = None
    args = sys.argv[1:]
    if "--split" in args:
        split = args[args.index("--split") + 1]
    if "--limit" in args:
        limit = int(args[args.index("--limit") + 1])
    if split not in FILES:
        print("split must be test or train", file=sys.stderr)
        return 2

    download()
    cache = DATA / "cache" / split
    cache.mkdir(parents=True, exist_ok=True)
    presets = load_presets()
    totals = {pid: {"plain": 0.0, "raw": 0.0, "n": 0} for pid in presets}
    examples = []
    seen = 0
    for clip in rows(split):
        if limit is not None and seen >= limit:
            break
        seen += 1
        ipa = ipa_for(clip, cache)
        mapped = {pid: apply_map(ipa, preset) for pid, preset in presets.items()}
        gold_plain = normalize_ortho(clip["sentence"], strip_marks=True)
        gold_raw = normalize_ortho(clip["sentence"], strip_marks=False)
        for pid, text in mapped.items():
            totals[pid]["plain"] += cer(gold_plain, normalize_ortho(text, strip_marks=True))
            totals[pid]["raw"] += cer(gold_raw, normalize_ortho(text, strip_marks=False))
            totals[pid]["n"] += 1
        if len(examples) < 5:
            examples.append({"id": clip["id"], "gold": clip["sentence"], "english": clip["english"], "ipa": ipa, "mapped": mapped})
        if seen % 25 == 0:
            print(f"scored {seen}", flush=True)

    if seen == 0:
        print("no clips")
        return 1
    ranked = []
    for pid, row in totals.items():
        n = row["n"] or 1
        ranked.append(
            {
                "id": pid,
                "name": presets[pid].get("name"),
                "script": presets[pid].get("script"),
                "lossy": bool(presets[pid].get("lossy")),
                "cer_plain": row["plain"] / n,
                "cer_raw": row["raw"] / n,
            }
        )
    ranked.sort(key=lambda item: (item["cer_plain"], item["cer_raw"], item["id"]))
    report = {"split": split, "clips": seen, "picked": ranked[0]["id"], "maps": ranked, "examples": examples}
    out = DATA / f"{split}-report.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"clips {seen}  picked {ranked[0]['id']}")
    for item in ranked:
        print(f"  {item['cer_plain']:.3f} plain  {item['cer_raw']:.3f} raw  {item['id']}")
    print(f"report {out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
