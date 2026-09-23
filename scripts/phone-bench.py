#!/usr/bin/env python3
"""Phone error rate of the recognizer, after the inventory filter, against two references.

DOLMA (Gilaki judge): the Arabic-script sentence read back through the Varg
letters. Ambiguous letters become a set of allowed phones; seat letters are
optional. Persian (phonetic judge): Common Voice sentences through
persian_phonemizer, from scripts/cv-fa-prepare.py.

Splits are by speaker. DOLMA train and Persian are split into propose and
accept; DOLMA test and a quarter of the Persian speakers are final. The worst
10% of clips by baseline PER are treated as bad references and dropped; that
list is frozen in data/bench/dropped.json so later passes score the same clips.

Run with no arguments for the baseline report in data/bench/baseline.json.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ["INVENTORY_PATH"] = str(ROOT / "schemas/gilaki_inventory.json")
os.environ["PRESETS_DIR"] = str(ROOT / "schemas/presets")
sys.path.insert(0, str(ROOT / "api"))

from app.catalog import get_preset, load_inventory  # noqa: E402
from app.rewriter import tokenize_ipa  # noqa: E402

DOLMA = ROOT / "data" / "dolma" / "gilaki"
CVFA = ROOT / "data" / "cv-fa"
BENCH = ROOT / "data" / "bench"
DROPPED = BENCH / "dropped.json"
DROP_SHARE = 0.10
FREEZE_MIN = 1000

INVENTORY = load_inventory()
PHONES = set(INVENTORY["vowels"]) | set(INVENTORY["consonants"])
VOWELS = set(INVENTORY["vowels"])
# Aliases before any learned filter; the "old" baseline.
ORIGINAL = {
    "d͡ʒ": "dʒ", "t͡ʃ": "tʃ", "y": "ü", "æ": "ä", "č": "tʃ", "š": "ʃ", "ž": "ʒ",
    "ǰ": "dʒ", "ɑ": "ɒ", "ɡ": "g", "ɾ": "r", "ʁ": "ɣ", "χ": "x",
}


@dataclass(frozen=True)
class Ref:
    allowed: frozenset
    optional: bool = False

    @property
    def vowel(self) -> bool:
        return bool(self.allowed & VOWELS)


@dataclass
class Clip:
    corpus: str
    key: str
    speaker: str
    split: str
    raw: list[str]
    ref: list[Ref]
    text: str = ""
    meta: dict = field(default_factory=dict)


# DOLMA reference from Varg letters


def _varg_inverse() -> dict[str, set[str]]:
    inverse: dict[str, set[str]] = {}
    for rule in get_preset("varg-perso-arabic")["rules"]:
        inverse.setdefault(rule["out"], set()).add(rule["ipa"])
    return inverse


VARG = _varg_inverse()
# Persian letters that Gilaki text keeps in loanwords, plus DOLMA spelling variants.
LOAN = {
    "ص": {"s"}, "ث": {"s"}, "ط": {"t"}, "ذ": {"z"}, "ض": {"z"}, "ظ": {"z"},
    "ح": {"h"}, "ق": {"ɣ", "g"}, "ء": {"ʔ"}, "ى": {"i", "iː", "j"},
}
MARKS = {"\u064e": {"a", "ä"}, "\u0650": {"e", "ɛ"}, "\u064f": {"o", "u"}, "\u064b": {"a", "n"}}
SKIP = set(" \u200c\u200d\u0640\u0651\u0652\u064c\u0670-") | set("!',.:«»،؟؛?0123456789°٫")
VOWEL_LETTERS = {"ی", "ۊ", "ئ", "ؤ", "أ", "آ", "ا", "ۋ", "ى", "ٚ"}
# Persian-style spelling leaves short vowels out, so one may sit between two written consonants.
SHORT_VOWELS = frozenset({"a", "ä", "e", "ɛ", "ə", "o", "i", "u"})


def dolma_ref(sentence: str) -> list[Ref] | None:
    text = unicodedata.normalize("NFC", sentence or "").replace("ي", "ی").replace("ك", "ک").replace("ة", "ه")
    outputs = sorted(VARG, key=len, reverse=True)
    refs: list[Ref] = []
    for word in "".join(" " if ch in SKIP else ch for ch in text).split():
        letters = _word_refs(word, outputs)
        if letters is None:
            return None
        refs.extend(_with_vowel_slots(letters))
    return refs


def _with_vowel_slots(letters: list[Ref]) -> list[Ref]:
    out: list[Ref] = []
    for k, ref in enumerate(letters):
        if k and not ref.vowel and not letters[k - 1].vowel:
            out.append(Ref(SHORT_VOWELS, optional=True))
        out.append(ref)
    return out


def _word_refs(word: str, outputs: list[str]) -> list[Ref] | None:
    refs: list[Ref] = []
    i = 0
    while i < len(word):
        ch = word[i]
        nxt = word[i + 1] if i + 1 < len(word) else ""
        step = 1
        if word.startswith("نگ", i):
            refs.append(Ref(frozenset({"n", "ŋ"})))
            refs.append(Ref(frozenset({"g"}), optional=True))
            step = 2
        elif ch == "ا" and i == 0 and (nxt in VOWEL_LETTERS or nxt in MARKS):
            refs.append(Ref(frozenset({"ʔ"}), optional=True))
        elif ch == "ه" and i == len(word) - 1 and i > 0:
            refs.append(Ref(frozenset({"h", "e", "ɛ", "ə"})))
        elif ch in ("ی", "ى"):
            refs.append(Ref(frozenset({"i", "iː", "j"})))
        elif ch == "و":
            refs.append(Ref(frozenset({"v", "u", "o"})))
        elif ch in MARKS:
            refs.append(Ref(frozenset(MARKS[ch])))
        elif ch in LOAN:
            refs.append(Ref(frozenset(LOAN[ch])))
        else:
            hit = next((out for out in outputs if word.startswith(out, i)), None)
            if hit is None:
                return None
            refs.append(Ref(frozenset(VARG[hit])))
            step = len(hit)
        i += step
    return refs


# Persian reference from persian_phonemizer IPA

PERSIAN = {
    "æ": {"a", "ä"}, "ɒː": {"ɒ"}, "ɒ": {"ɒ"}, "iː": {"i", "iː"}, "uː": {"u", "uː"}, "e": {"e", "ɛ"},
    "o": {"o"}, "i": {"i", "iː"}, "u": {"u", "uː"}, "ɾ": {"r"}, "r": {"r"}, "ɡ": {"g"}, "q": {"ɣ", "g"},
}


def persian_tokens(ipa: str) -> list[str] | None:
    tokens: list[str] = []
    for ch in unicodedata.normalize("NFC", ipa):
        if ch.isspace() or ch in "،؟.!,:?؛«»-":
            continue
        if ch == "ʰ":
            continue
        if ch == "ː" and tokens:
            tokens[-1] += ch
            continue
        if ch == "ʃ" and tokens and tokens[-1] == "t":
            tokens[-1] = "tʃ"
            continue
        if ch == "ʒ" and tokens and tokens[-1] == "d":
            tokens[-1] = "dʒ"
            continue
        if not ch.isalpha() and ch not in "ʔ":
            return None
        tokens.append(ch)
    return tokens


def persian_ref(ipa: str) -> list[Ref] | None:
    refs = []
    for word in ipa.split():
        tokens = persian_tokens(word)
        if tokens is None:
            return None
        for k, tok in enumerate(tokens):
            allowed = PERSIAN.get(tok, {tok})
            if not allowed <= PHONES:
                return None
            # The phonemizer writes a glottal stop before every vowel-initial word; speakers often drop it.
            refs.append(Ref(frozenset(allowed), optional=(k == 0 and tok == "ʔ")))
    return refs


# Loading and splits


def bucket(speaker: str) -> int:
    return int(hashlib.md5(speaker.encode("utf-8")).hexdigest(), 16) % 100


def load_dolma() -> list[Clip]:
    import pyarrow.parquet as pq

    clips: list[Clip] = []
    for split_name in ("train", "test"):
        table = pq.read_table(DOLMA / f"{split_name}-00000-of-00001.parquet", columns=["id", "speaker_id", "sentence"])
        ids = table.column("id").to_pylist()
        dup = {k for k, v in Counter(ids).items() if v > 1}
        for clip_id, speaker, sentence in zip(ids, table.column("speaker_id").to_pylist(), table.column("sentence").to_pylist()):
            if clip_id in dup:
                continue
            path = DOLMA / "cache" / split_name / f"{clip_id}.ipa.txt"
            if not path.exists():
                continue
            ref = dolma_ref(sentence)
            if not ref:
                continue
            if split_name == "test":
                split = "final"
            else:
                split = "propose" if bucket(speaker) < 60 else "accept"
            clips.append(
                Clip("dolma", str(clip_id), speaker, split, tokenize_ipa(path.read_text(encoding="utf-8")), ref, sentence)
            )
    return clips


def load_persian() -> list[Clip]:
    refs = CVFA / "refs.jsonl"
    if not refs.exists():
        return []
    clips: list[Clip] = []
    for line in refs.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        path = CVFA / "cache" / f"{row['path']}.ipa.txt"
        if not path.exists():
            continue
        ref = persian_ref(row["ref_ipa"])
        if not ref:
            continue
        b = bucket(row["client_id"])
        split = "propose" if b < 50 else "accept" if b < 75 else "final"
        clips.append(
            Clip("persian", row["path"], row["client_id"], split, tokenize_ipa(path.read_text(encoding="utf-8")), ref, row["sentence"])
        )
    return clips


# Filter, alignment, scoring


def apply_filter(raw: list[str], aliases: dict[str, str], rewrites: list[dict] | None = None) -> list[str]:
    out = []
    for tok in raw:
        folded = aliases.get(tok, tok)
        if folded:
            out.append(folded)
    for rule in sorted(rewrites or [], key=lambda r: -len(r["from"])):
        src, dst = rule["from"], rule["to"]
        n = len(src)
        i, res = 0, []
        while i < len(out):
            if out[i : i + n] == src:
                res.extend(dst)
                i += n
            else:
                res.append(out[i])
                i += 1
        out = res
    return out


@lru_cache(maxsize=None)
def _dist() -> object:
    import panphon.distance

    return panphon.distance.Distance()


@lru_cache(maxsize=None)
def sub_cost(phone: str, allowed: frozenset) -> float:
    if phone in allowed:
        return 0.0
    try:
        d = min(_dist().weighted_feature_edit_distance(phone, a) for a in allowed)
    except Exception:
        return 1.2
    return min(1.2, 0.3 + d / 12.0)


def align(hyp: list[str], ref: list[Ref]) -> list[tuple[str, str | None, Ref | None]]:
    n, m = len(hyp), len(ref)
    inf = float("inf")
    dp = [[inf] * (m + 1) for _ in range(n + 1)]
    back = [[""] * (m + 1) for _ in range(n + 1)]
    dp[0][0] = 0.0
    for i in range(n + 1):
        for j in range(m + 1):
            cur = dp[i][j]
            if cur == inf:
                continue
            if i < n and j < m:
                c = cur + sub_cost(hyp[i], ref[j].allowed)
                if c < dp[i + 1][j + 1]:
                    dp[i + 1][j + 1] = c
                    back[i + 1][j + 1] = "sub"
            if i < n:
                c = cur + 1.0
                if c < dp[i + 1][j]:
                    dp[i + 1][j] = c
                    back[i + 1][j] = "ins"
            if j < m:
                c = cur + (0.0 if ref[j].optional else 1.0)
                if c < dp[i][j + 1]:
                    dp[i][j + 1] = c
                    back[i][j + 1] = "del"
    ops = []
    i, j = n, m
    while i or j:
        step = back[i][j]
        if step == "sub":
            ops.append(("ok" if hyp[i - 1] in ref[j - 1].allowed else "sub", hyp[i - 1], ref[j - 1]))
            i, j = i - 1, j - 1
        elif step == "ins":
            ops.append(("ins", hyp[i - 1], None))
            i -= 1
        else:
            ops.append(("skip" if ref[j - 1].optional else "del", None, ref[j - 1]))
            j -= 1
    ops.reverse()
    return ops


@dataclass
class Score:
    errors: int = 0
    total: int = 0
    v_err: int = 0
    v_tot: int = 0
    c_err: int = 0
    c_tot: int = 0

    def add(self, other: "Score") -> None:
        for f in ("errors", "total", "v_err", "v_tot", "c_err", "c_tot"):
            setattr(self, f, getattr(self, f) + getattr(other, f))

    @property
    def per(self) -> float:
        return self.errors / self.total if self.total else 0.0

    def as_dict(self) -> dict:
        return {
            "per": round(self.per, 4),
            "vowel_per": round(self.v_err / self.v_tot, 4) if self.v_tot else None,
            "consonant_per": round(self.c_err / self.c_tot, 4) if self.c_tot else None,
            "ref_phones": self.total,
        }


def score_ops(ops) -> Score:
    s = Score()
    for kind, _, ref in ops:
        if kind == "skip":
            continue
        if kind == "ins":
            s.errors += 1
            continue
        s.total += 1
        bad = kind != "ok"
        s.errors += bad
        if ref.vowel:
            s.v_tot += 1
            s.v_err += bad
        else:
            s.c_tot += 1
            s.c_err += bad
    return s


def score_clip(clip: Clip, aliases: dict[str, str], rewrites=None) -> Score:
    return score_ops(align(apply_filter(clip.raw, aliases, rewrites), clip.ref))


def load_all(drop: bool = True) -> list[Clip]:
    clips = load_dolma() + load_persian()
    if not drop:
        return clips
    frozen = json.loads(DROPPED.read_text(encoding="utf-8")) if DROPPED.exists() else {"share": DROP_SHARE, "corpora": {}}
    changed = False
    sizes = Counter(c.corpus for c in clips)
    for corpus in sorted(sizes):
        if corpus not in frozen["corpora"] and sizes[corpus] >= FREEZE_MIN:
            frozen["corpora"][corpus] = worst_keys([c for c in clips if c.corpus == corpus])
            changed = True
    if changed:
        BENCH.mkdir(parents=True, exist_ok=True)
        DROPPED.write_text(json.dumps(frozen, indent=1) + "\n", encoding="utf-8")
    dropped = {k for keys in frozen["corpora"].values() for k in keys}
    return [c for c in clips if c.key not in dropped]


def worst_keys(clips: list[Clip]) -> list[str]:
    """Worst DROP_SHARE of one corpus by PER under the committed filter."""
    aliases = dict(INVENTORY.get("aliases") or {})
    rows = sorted(((score_clip(c, aliases).per, c.key) for c in clips), reverse=True)
    return sorted(key for _, key in rows[: int(len(rows) * DROP_SHARE)])


def report(clips: list[Clip], aliases: dict[str, str], rewrites=None) -> dict:
    out: dict = {}
    for corpus in sorted({c.corpus for c in clips}):
        for split in ("propose", "accept", "final"):
            s = Score()
            for c in clips:
                if c.corpus == corpus and c.split == split:
                    s.add(score_clip(c, aliases, rewrites))
            if s.total:
                out[f"{corpus}/{split}"] = s.as_dict()
    return out


def confusions(clips: list[Clip], aliases: dict[str, str], limit: int = 25) -> list[dict]:
    pairs: Counter = Counter()
    for c in clips:
        if c.split == "final":
            continue
        for kind, hyp, ref in align(apply_filter(c.raw, aliases), c.ref):
            if kind == "sub":
                pairs[(hyp, "/".join(sorted(ref.allowed)))] += 1
            elif kind == "ins":
                pairs[(hyp, "-")] += 1
            elif kind == "del":
                pairs[("-", "/".join(sorted(ref.allowed)))] += 1
    return [{"hyp": h, "ref": r, "count": n} for (h, r), n in pairs.most_common(limit)]


def main() -> int:
    clips = load_all()
    current = dict(INVENTORY.get("aliases") or {})
    counts = Counter((c.corpus, c.split) for c in clips)
    print("clips:", {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())})
    result = {"clips": {f"{k[0]}/{k[1]}": v for k, v in sorted(counts.items())}}
    for name, aliases in (("raw", {}), ("old", ORIGINAL), ("current", current)):
        result[name] = report(clips, aliases)
        print(name)
        for key, row in result[name].items():
            print(f"  {key:18} PER {row['per']:.3f}  vowels {row['vowel_per']:.3f}  consonants {row['consonant_per']:.3f}")
    result["confusions_current"] = confusions(clips, current)
    BENCH.mkdir(parents=True, exist_ok=True)
    (BENCH / "baseline.json").write_text(json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print("top confusions (hyp -> ref):", [(r["hyp"], r["ref"], r["count"]) for r in result["confusions_current"][:15]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
