#!/usr/bin/env python3
"""Judge cached DOLMA IPA, then propose an inventory filter.

Dev clips decide folds. Eval clips only score them. Letter rules are not edited.
Listening clips go to data/dolma/listen/ for a human mark. Empty marks do not
block a fold. A filled mark that names a different pile blocks that clip's phones.
"""
from __future__ import annotations

import json
import os
import sys
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["INVENTORY_PATH"] = str(ROOT / "schemas/gilaki_inventory.json")
os.environ["PRESETS_DIR"] = str(ROOT / "schemas/presets")
sys.path.insert(0, str(ROOT / "api"))

from app.audio import prepare_audio  # noqa: E402
from app.catalog import get_preset, load_inventory  # noqa: E402
from app.rewriter import apply_map, tokenize_ipa  # noqa: E402

DATA = ROOT / "data" / "dolma" / "gilaki"
LISTEN = ROOT / "data" / "dolma" / "listen"
PARQUET = DATA / "test-00000-of-00001.parquet"
CACHE = DATA / "cache" / "test"
MIN_COUNT = 15
MAJORITY = 0.60
# Aliases that existed before this filter. Learning and the "before" score use these.
ORIGINAL = {
    "d͡ʒ": "dʒ",
    "t͡ʃ": "tʃ",
    "y": "ü",
    "æ": "ä",
    "č": "tʃ",
    "š": "ʃ",
    "ž": "ʒ",
    "ǰ": "dʒ",
    "ɑ": "ɒ",
    "ɡ": "g",
    "ɾ": "r",
    "ʁ": "ɣ",
    "χ": "x",
}


def is_dev(clip_id: int) -> bool:
    return clip_id % 5 >= 2


def normalize_gold(text: str) -> str:
    text = unicodedata.normalize("NFC", text or "")
    text = text.replace("\u200c", "").replace("\u200d", "")
    return text.replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")


def plain_letters(text: str) -> str:
    stripped = "".join(ch for ch in normalize_gold(text) if not (0x064B <= ord(ch) <= 0x065F or ord(ch) in (0x0670, 0x0640)))
    return "".join(ch for ch in stripped if not ch.isspace())


def cer(reference: str, hypothesis: str) -> float:
    ref = list(reference)
    hyp = list(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            cur.append(min(cur[j - 1] + 1, prev[j] + 1, prev[j - 1] + (r != h)))
        prev = cur
    return prev[-1] / len(ref)


def strip_modifiers(phone: str) -> str:
    kept = []
    for ch in unicodedata.normalize("NFC", phone):
        if ch == "ː":
            kept.append(ch)
            continue
        if unicodedata.category(ch) in {"Mn", "Sk"}:
            continue
        kept.append(ch)
    return "".join(kept)


def canonical(phone: str, aliases: dict[str, str]) -> str:
    raw = unicodedata.normalize("NFC", phone)
    base = strip_modifiers(raw)
    folded = aliases.get(raw, aliases.get(base, base))
    folded = aliases.get(strip_modifiers(folded), folded)
    return strip_modifiers(folded) if folded != raw else folded


def invert_varg() -> dict[str, set[str]]:
    preset = get_preset("varg-perso-arabic")
    inverse: dict[str, set[str]] = defaultdict(set)
    for rule in preset["rules"]:
        inverse[rule["out"]].add(rule["ipa"])
    return dict(inverse)


def gold_tokens(text: str, outputs: list[str]) -> list[str]:
    text = "".join(ch for ch in normalize_gold(text) if not ch.isspace())
    tokens = []
    i = 0
    while i < len(text):
        hit = next((out for out in outputs if text.startswith(out, i)), None)
        if hit:
            tokens.append(hit)
            i += len(hit)
        else:
            i += 1
    return tokens


def align(hyp: list[str], gold: list[str], matches) -> list[tuple]:
    n, m = len(hyp), len(gold)
    dp = [[0] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    for i in range(1, n + 1):
        dp[i][0] = i
        back[i][0] = "ins"
    for j in range(1, m + 1):
        dp[0][j] = j
        back[0][j] = "del"
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            ok = matches(hyp[i - 1], gold[j - 1])
            sub = dp[i - 1][j - 1] + (0 if ok else 1)
            ins = dp[i - 1][j] + 1
            delete = dp[i][j - 1] + 1
            best = min(sub, ins, delete)
            dp[i][j] = best
            if best == sub:
                back[i][j] = "ok" if ok else "sub"
            elif best == ins:
                back[i][j] = "ins"
            else:
                back[i][j] = "del"
    ops = []
    i, j = n, m
    while i > 0 or j > 0:
        step = back[i][j]
        if step in {"ok", "sub"}:
            ops.append((step, hyp[i - 1], gold[j - 1]))
            i -= 1
            j -= 1
        elif step == "ins":
            ops.append(("ins", hyp[i - 1], None))
            i -= 1
        else:
            ops.append(("del", None, gold[j - 1]))
            j -= 1
    ops.reverse()
    return ops


def load_clips() -> list[dict]:
    import pyarrow.parquet as pq

    table = pq.read_table(PARQUET, columns=["id", "sentence", "english", "audio"])
    clips = []
    for i in range(table.num_rows):
        clip_id = int(table.column("id")[i].as_py())
        ipa_path = CACHE / f"{clip_id}.ipa.txt"
        if not ipa_path.exists():
            continue
        audio = table.column("audio")[i].as_py()
        clips.append(
            {
                "id": clip_id,
                "sentence": table.column("sentence")[i].as_py() or "",
                "english": table.column("english")[i].as_py() or "",
                "ipa": ipa_path.read_text(encoding="utf-8").strip(),
                "audio": audio["bytes"],
                "dev": is_dev(clip_id),
            }
        )
    return clips


def load_marks() -> dict[int, str]:
    path = LISTEN / "marks.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    marks = {}
    for row in data.get("clips", []):
        mark = (row.get("mark") or "").strip()
        if mark:
            marks[int(row["id"])] = mark
    return marks


def contradict(mark: str, pile: str) -> bool:
    if not mark:
        return False
    if mark == "right sound" and pile == "wrong":
        return True
    if mark == "wrong sound" and pile in {"right", "wrong_symbol"}:
        return True
    if mark == "wrong symbol" and pile == "wrong":
        return True
    return False


def main() -> int:
    inventory = load_inventory()
    seed = dict(ORIGINAL)
    inventory_phones = set(inventory.get("vowels") or []) | set(inventory.get("consonants") or [])
    inverse = invert_varg()
    outputs = sorted(inverse, key=len, reverse=True)
    varg = get_preset("varg-perso-arabic")
    lossy = get_preset("lossy-persian")
    clips = load_clips()
    marks = load_marks()

    def matches(phone: str, letter: str) -> bool:
        return canonical(phone, seed) in inverse.get(letter, set())

    pile_counts = Counter()
    phone_targets: dict[str, Counter] = defaultdict(Counter)
    phone_roles: dict[str, Counter] = defaultdict(Counter)
    clip_piles: dict[int, Counter] = {}
    blocked: set[str] = set()

    for clip in clips:
        if not clip["dev"]:
            continue
        hyp = tokenize_ipa(clip["ipa"])
        gold = gold_tokens(clip["sentence"], outputs)
        ops = align(hyp, gold, matches)
        local = Counter()
        mark = marks.get(clip["id"], "")
        for kind, phone, letter in ops:
            if phone is None:
                continue
            can = canonical(phone, seed)
            raw = unicodedata.normalize("NFC", phone)
            if kind == "ok" and can in inventory_phones and (raw == can or raw in seed):
                pile = "right"
            elif kind == "ok":
                pile = "wrong_symbol"
                phone_targets[raw][can] += 1
            elif kind == "ins":
                pile = "insertion"
                phone_targets[raw][""] += 1
            else:
                pile = "wrong"
            local[pile] += 1
            pile_counts[pile] += 1
            phone_roles[raw][pile] += 1
            if contradict(mark, pile):
                blocked.add(raw)
        clip_piles[clip["id"]] = local

    dev_total = sum(pile_counts.values()) or 1
    print("dev phones", dev_total)
    for name in ("right", "wrong_symbol", "wrong", "insertion"):
        count = pile_counts[name]
        print(f"  {name:14} {count:6}  {count / dev_total:.3f}")

    accepted: dict[str, str] = {}
    for phone, targets in phone_targets.items():
        if phone in seed or phone in inventory_phones or phone in blocked:
            continue
        total = sum(phone_roles[phone].values())
        if total < MIN_COUNT:
            continue
        target, hits = targets.most_common(1)[0]
        if hits / total < MAJORITY:
            continue
        if target == phone:
            continue
        if target and target not in inventory_phones:
            continue
        accepted[phone] = target

    print(f"accepted {len(accepted)} folds")
    for phone, target in sorted(accepted.items(), key=lambda item: -sum(phone_roles[item[0]].values()))[:25]:
        shown = target or "delete"
        print(f"  {phone} -> {shown}  n={sum(phone_roles[phone].values())}")

    merged = dict(seed)
    merged.update(accepted)

    def score(split_dev: bool, aliases: dict[str, str]) -> dict[str, float]:
        totals = {"varg-perso-arabic": 0.0, "lossy-persian": 0.0}
        n = 0
        for clip in clips:
            if clip["dev"] != split_dev:
                continue
            n += 1
            gold = plain_letters(clip["sentence"])
            for preset, key in ((varg, "varg-perso-arabic"), (lossy, "lossy-persian")):
                mapped = apply_map(clip["ipa"], {**preset, "aliases": aliases})
                totals[key] += cer(gold, plain_letters(mapped))
        return {key: totals[key] / n for key in totals} | {"n": n}

    before = score(False, seed)
    after = score(False, merged)
    print(f"eval n={before['n']}")
    print(f"  varg  {before['varg-perso-arabic']:.3f} -> {after['varg-perso-arabic']:.3f}")
    print(f"  lossy {before['lossy-persian']:.3f} -> {after['lossy-persian']:.3f}")

    keep = after["varg-perso-arabic"] < before["varg-perso-arabic"] and after["lossy-persian"] <= before["lossy-persian"] + 0.01
    print("keep folds" if keep else "reject folds")

    listen = pick_listen(clips, clip_piles)
    write_listen(listen)
    write_reports(
        pile_counts,
        dev_total,
        accepted,
        before,
        after,
        keep,
        clips,
        merged if keep else seed,
        inverse,
        phone_roles,
    )
    if keep:
        write_aliases(inventory, accepted)
    return 0


def pick_listen(clips: list[dict], clip_piles: dict[int, Counter]) -> list[dict]:
    dev = [clip for clip in clips if clip["dev"] and clip["id"] in clip_piles]

    def score_for(pile: str, clip: dict) -> int:
        return clip_piles[clip["id"]][pile]

    chosen = []
    seen = set()

    def take(pile: str, k: int) -> None:
        ranked = sorted(dev, key=lambda clip: score_for(pile, clip), reverse=True)
        got = 0
        for clip in ranked:
            if clip["id"] in seen or score_for(pile, clip) < 2:
                continue
            chosen.append({**clip, "auto_pile": pile})
            seen.add(clip["id"])
            got += 1
            if got >= k:
                break

    take("right", 3)
    take("wrong_symbol", 4)
    take("wrong", 3)
    return chosen


def write_listen(clips: list[dict]) -> None:
    LISTEN.mkdir(parents=True, exist_ok=True)
    previous = {}
    marks_path = LISTEN / "marks.json"
    if marks_path.exists():
        for row in json.loads(marks_path.read_text(encoding="utf-8")).get("clips", []):
            previous[int(row["id"])] = row.get("mark") or ""
    rows = []
    for clip in clips:
        wav = LISTEN / f"{clip['id']}.wav"
        if not wav.exists():
            prepared = prepare_audio(clip["audio"], max_duration_sec=60)
            wav.write_bytes(prepared.wav_bytes)
        rows.append(
            {
                "id": clip["id"],
                "auto_pile": clip["auto_pile"],
                "sentence": clip["sentence"],
                "english": clip["english"],
                "ipa": clip["ipa"],
                "mark": previous.get(clip["id"], ""),
            }
        )
    (LISTEN / "marks.json").write_text(json.dumps({"clips": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"listen {len(rows)} clips in {LISTEN}")


def write_aliases(inventory: dict, accepted: dict[str, str]) -> None:
    path = ROOT / "schemas" / "gilaki_inventory.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    aliases = dict(data.get("aliases") or {})
    aliases.update(accepted)
    data["aliases"] = dict(sorted(aliases.items(), key=lambda item: item[0]))
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(accepted)} aliases into {path.name}")


def write_reports(pile_counts, dev_total, accepted, before, after, keep, clips, aliases, inverse, phone_roles) -> None:
    varg = get_preset("varg-perso-arabic")
    letter_miss = Counter()
    outputs = sorted(inverse, key=len, reverse=True)

    def matches(phone: str, letter: str) -> bool:
        return canonical(phone, aliases) in inverse.get(letter, set())

    for clip in clips:
        if clip["dev"]:
            continue
        hyp = tokenize_ipa(clip["ipa"])
        gold = gold_tokens(clip["sentence"], outputs)
        for kind, phone, letter in align(hyp, gold, matches):
            if kind == "sub" and letter:
                letter_miss[letter] += 1
            if kind == "del" and letter:
                letter_miss[letter] += 1
    remaining = [{"letter": letter, "misses": count} for letter, count in letter_miss.most_common(20)]
    top_wrong = sorted(
        ({"phone": phone, "count": roles["wrong"]} for phone, roles in phone_roles.items() if roles["wrong"]),
        key=lambda row: -row["count"],
    )[:20]
    report = {
        "dev_phones": dev_total,
        "piles": dict(pile_counts),
        "accepted": accepted,
        "kept": keep,
        "eval_before": before,
        "eval_after": after,
        "remaining_letters": remaining,
        "top_wrong_phones": top_wrong,
    }
    dest = DATA / "filter-report.json"
    dest.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    summary = ROOT / "schemas" / "phone_filter_remaining.json"
    summary.write_text(
        json.dumps(
            {
                "note": "Eval letter misses after the filter. Input for a later map pass. Letter rules were not changed.",
                "eval_before": before,
                "eval_after": after,
                "kept": keep,
                "dev_piles": dict(pile_counts),
                "top_wrong_phones": top_wrong,
                "letters": remaining,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"report {dest}")


if __name__ == "__main__":
    raise SystemExit(main())
