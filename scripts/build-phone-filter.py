#!/usr/bin/env python3
"""Fold every Allosaurus phone onto the Gilaki inventory and write the aliases.

Each phone goes to its nearest inventory phone by panphon feature distance, after
tie bars and diacritics are stripped. OVERRIDES fix the few picks that are
phonetically wrong for Gilaki. The table is kept only if held-out DOLMA CER
improves for both Varg and lossy-Persian with letter rules unchanged.

Needs the local .venv with allosaurus (model downloaded) and panphon.
"""
from __future__ import annotations

import importlib.util
import json
import unicodedata
from pathlib import Path

import allosaurus
import panphon.distance

ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "schemas" / "gilaki_inventory.json"
PHONES = Path(allosaurus.__file__).parent / "pretrained" / "uni2005" / "phone.txt"

_spec = importlib.util.spec_from_file_location("dolma_filter", ROOT / "scripts" / "dolma-filter.py")
dolma = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(dolma)

from app.catalog import get_preset  # noqa: E402
from app.rewriter import apply_map  # noqa: E402

OVERRIDES = {
    "w": "v",
    "ʋ": "v",
    "β": "v",
    "ɹ": "r",
    "ɻ": "r",
    "ɹ̩": "r",
    "ɻ̩": "r",
    "ʀ": "r",
    "ɐ": "a",
    "ts": "s",
    "dz": "z",
    "ʏ": "ü",
    "ʊ": "u",
    "ә": "ə",
}


def strip(phone: str) -> str:
    return "".join(
        ch for ch in unicodedata.normalize("NFC", phone) if ch == "ː" or unicodedata.category(ch) not in {"Mn", "Lm", "Sk"}
    )


def build(inventory: dict) -> dict[str, str]:
    phones = sorted(set(inventory["vowels"]) | set(inventory["consonants"]))
    seed = dict(dolma.ORIGINAL)
    dist = panphon.distance.Distance()
    table = dict(seed)
    for line in PHONES.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        phone = unicodedata.normalize("NFC", line.split()[0])
        if phone in phones or phone in seed:
            continue
        if phone in OVERRIDES:
            table[phone] = OVERRIDES[phone]
            continue
        base = strip(phone)
        base = seed.get(base, base)
        if base not in phones:
            base = min(phones, key=lambda p: dist.weighted_feature_edit_distance(base, p))
        table[phone] = base
    bad = {k: v for k, v in table.items() if v not in phones}
    if bad:
        raise SystemExit(f"fold targets outside inventory: {bad}")
    return dict(sorted(table.items()))


def score(clips: list[dict], aliases: dict[str, str]) -> dict[str, float]:
    out = {}
    for preset_id in ("varg-perso-arabic", "lossy-persian"):
        preset = {**get_preset(preset_id), "aliases": aliases}
        total = sum(
            dolma.cer(dolma.plain_letters(clip["sentence"]), dolma.plain_letters(apply_map(clip["ipa"], preset)))
            for clip in clips
        )
        out[preset_id] = round(total / len(clips), 3)
    return out


def main() -> int:
    inventory = json.loads(INVENTORY.read_text(encoding="utf-8"))
    table = build(inventory)
    clips = dolma.load_clips()
    held_out = [clip for clip in clips if not clip["dev"]]
    before = score(held_out, dict(dolma.ORIGINAL))
    after = score(held_out, table)
    print(f"held-out n={len(held_out)} folds={len(table)}")
    for preset_id in before:
        print(f"  {preset_id:18} {before[preset_id]:.3f} -> {after[preset_id]:.3f}")
    if not all(after[k] < before[k] for k in before):
        print("not written: a preset got worse")
        return 1
    inventory["aliases"] = table
    INVENTORY.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {INVENTORY.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
