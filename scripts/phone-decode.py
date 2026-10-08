#!/usr/bin/env python3
"""Re-decode cached Allosaurus frame scores with a Gilaki phone-pair prior.

Reads data/bench/lattice/ from scripts/cache-lattice.py. Three decoders:

- greedy: Allosaurus's own rule (a phone repeated across blanks is merged),
  with a different blank factor `emit`.
- ctc: standard CTC greedy, where a blank separates two equal phones.
- beam: CTC prefix beam search over inventory phones (recognizer units folded
  through the inventory aliases), scored as recognizer log-probability plus
  `weight` times a phone bigram log-probability plus `bonus` per phone.

The bigram is trained on DOLMA propose sentences only, minus any sentence that
also occurs in accept or final, so neither tuning nor the final check sees its
training text. Settings are tuned on accept; the best one is kept only if
final PER improves on both corpora and DOLMA test CER, academic-Latin length
and schwa errors do not get worse. `--write` stores the kept decoder in
schemas/phone_decoder.json, which the API loads; `--check` re-judges that file.
The beam itself lives in api/app/decoder.py so the server and this script
decode identically.
"""
from __future__ import annotations

import argparse
import importlib.util
import itertools
import json
import math
import sys
from collections import defaultdict
from multiprocessing import Pool
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def _load(name: str, file: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


bench = _load("phone_bench", "phone-bench.py")
dolma = _load("dolma_filter", "dolma-filter.py")

from app.catalog import get_preset  # noqa: E402
from app.decoder import BOS, EOS, beam_search  # noqa: E402
from app.rewriter import apply_map  # noqa: E402

LATTICE = ROOT / "data" / "bench" / "lattice"
OUT = ROOT / "schemas" / "phone_decoder.json"
REPORT = ROOT / "data" / "bench" / "decode.json"
ALIASES = dict(bench.INVENTORY.get("aliases") or {})
REWRITES = list(bench.INVENTORY.get("rewrites") or [])
PHONES = sorted(bench.PHONES)
CAND_FLOOR = -9.0
CAND_MAX = 6
BEAM = 8
SMOOTH = 5.0

UNITS: list[str] = []
UNIT_PHONE: list[str] = []


def _init_units() -> None:
    global UNITS, UNIT_PHONE
    UNITS = json.loads((LATTICE / "units.json").read_text(encoding="utf-8"))
    UNIT_PHONE = [""] + [ALIASES.get(u, u) if u else "" for u in UNITS[1:]]


def lattice_key(corpus: str, key: str, split: str) -> Path:
    if corpus == "dolma":
        return LATTICE / "dolma" / ("test" if split == "final" else "train") / f"{key}.npz"
    return LATTICE / "persian" / f"{key}.npz"


# Phone-pair prior


def train_bigram(clips) -> dict:
    held = {c.text for c in clips if c.corpus == "dolma" and c.split != "propose"}
    seen: set[str] = set()
    pair: dict = defaultdict(float)
    uni: dict = defaultdict(float)
    for c in clips:
        if c.corpus != "dolma" or c.split != "propose" or c.text in held or c.text in seen:
            continue
        seen.add(c.text)
        toks = [(frozenset([BOS]), 1.0)] + [(r.allowed, 0.5 if r.optional else 1.0) for r in c.ref] + [(frozenset([EOS]), 1.0)]
        for i, (a_set, a_inc) in enumerate(toks):
            for a in a_set:
                uni[a] += a_inc / len(a_set)
            skip = 1.0
            for b_set, b_inc in toks[i + 1 :]:
                w = a_inc * skip * b_inc / (len(a_set) * len(b_set))
                for a in a_set:
                    for b in b_set:
                        pair[(a, b)] += w
                skip *= 1.0 - b_inc
                if skip == 0.0:
                    break
    vocab = PHONES + [EOS]
    total = sum(uni[p] for p in vocab)
    p_uni = {p: (uni[p] + 0.5) / (total + 0.5 * len(vocab)) for p in vocab}
    table: dict = {}
    for a in [BOS] + PHONES:
        ctx = sum(pair[(a, b)] for b in vocab)
        table[a] = {b: round(math.log((pair[(a, b)] + SMOOTH * p_uni[b]) / (ctx + SMOOTH)), 4) for b in vocab}
    return {"sentences": len(seen), "logprob": table}


# Decoders


def decode_greedy(z, emit: float, ctc: bool) -> list[str]:
    out, prev = [], -1
    blank = z["blank"] / emit
    for t in range(len(blank)):
        best = 0 if blank[t] >= z["lp"][t, 0] else int(z["idx"][t, 0])
        if best != prev and best != 0:
            out.append(UNIT_PHONE[best])
            prev = best
        elif ctc and best == 0:
            prev = 0
    return bench.apply_filter([p for p in out if p], {}, REWRITES)


def decode_beam(z, emit: float, weight: float, bonus: float, merge: bool, lm: dict) -> list[str]:
    out = beam_search(
        z["blank"], z["idx"], z["lp"], UNITS, ALIASES,
        emit=emit, weight=weight, bonus=bonus, merge=merge, lm=lm,
        beam=BEAM, cand_floor=CAND_FLOOR, cand_max=CAND_MAX,
    )
    return bench.apply_filter([phone for phone, _, _ in out], {}, REWRITES)


def run(cfg: dict, z, lm: dict) -> list[str]:
    if cfg["kind"] == "beam":
        return decode_beam(z, cfg["emit"], cfg["weight"], cfg["bonus"], cfg["merge"], lm)
    return decode_greedy(z, cfg["emit"], cfg["kind"] == "ctc")


# Scoring

_WORK: dict = {}


def _worker_init(lm: dict) -> None:
    _init_units()
    _WORK["lm"] = lm


def _score_job(job):
    cfg, items = job
    lm = _WORK["lm"]
    out = []
    for corpus, key, split, ref in items:
        hyp = run(cfg, np.load(lattice_key(corpus, key, split)), lm)
        out.append((corpus, bench.score_ops(bench.align(hyp, ref)), schwa_errors(hyp, ref)))
    return out


def schwa_errors(hyp, ref) -> tuple[int, int]:
    err = tot = 0
    for kind, _, r in bench.align(hyp, ref):
        if r is not None and r.allowed == frozenset(["ə"]) and kind != "skip":
            tot += 1
            err += kind != "ok"
    return err, tot


def evaluate(pool, cfgs, clips, split: str) -> list[dict]:
    items = [(c.corpus, c.key, c.split, c.ref) for c in clips if c.split == split]
    chunks = [items[i : i + 60] for i in range(0, len(items), 60)]
    jobs = [(cfg, chunk) for cfg in cfgs for chunk in chunks]
    results = pool.map(_score_job, jobs, chunksize=1)
    rows = []
    for n, cfg in enumerate(cfgs):
        agg = {"dolma": bench.Score(), "persian": bench.Score()}
        schwa = [0, 0]
        for res in results[n * len(chunks) : (n + 1) * len(chunks)]:
            for corpus, score, (se, st) in res:
                agg[corpus].add(score)
                if corpus == "dolma":
                    schwa[0] += se
                    schwa[1] += st
        rows.append(
            {
                "cfg": cfg,
                "dolma": round(agg["dolma"].per, 4),
                "persian": round(agg["persian"].per, 4),
                "schwa": round(schwa[0] / schwa[1], 4) if schwa[1] else None,
            }
        )
    return rows


def test_cer(cfg: dict, lm: dict) -> dict:
    _init_units()
    maps = {k: get_preset(k) for k in ("varg-perso-arabic", "lossy-persian", "academic-latin")}
    cers = {"varg-perso-arabic": 0.0, "lossy-persian": 0.0}
    latin = 0
    test = dolma.load_clips()
    for clip in test:
        hyp = " ".join(run(cfg, np.load(LATTICE / "dolma" / "test" / f"{clip['id']}.npz"), lm))
        gold = dolma.plain_letters(clip["sentence"])
        for key in cers:
            cers[key] += dolma.cer(gold, dolma.plain_letters(apply_map(hyp, {**maps[key], "aliases": {}, "rewrites": []})))
        latin += len(apply_map(hyp, {**maps["academic-latin"], "aliases": {}, "rewrites": []}))
    out = {f"cer_{k}": round(v / len(test), 4) for k, v in cers.items()}
    out["academic_latin_chars"] = latin
    return out


def grid() -> list[dict]:
    cfgs = [{"kind": k, "emit": e} for k in ("greedy", "ctc") for e in (0.6, 0.8, 1.0, 1.2, 1.5)]
    for emit, weight, bonus, merge in itertools.product(
        (0.8, 1.0, 1.2, 1.5, 2.0), (0.0, 0.3, 0.6, 1.0, 1.5, 2.0), (0.0, 0.5, 1.0, 1.5, 2.0), (True, False)
    ):
        cfgs.append({"kind": "beam", "emit": emit, "weight": weight, "bonus": bonus, "merge": merge})
    return cfgs


BASELINE = {"kind": "greedy", "emit": 1.0}


def judge(pool, clips, cfg: dict, table: dict) -> tuple[dict, dict, list[str]]:
    before, after = evaluate(pool, [BASELINE, cfg], clips, "final")
    before.update(test_cer(BASELINE, table))
    after.update(test_cer(cfg, table))
    print("final before", before)
    print("final after ", after)
    problems = []
    for key in ("dolma", "persian"):
        if after[key] >= before[key]:
            problems.append(f"{key} final PER {before[key]} -> {after[key]}")
    for key in ("cer_varg-perso-arabic", "cer_lossy-persian", "schwa"):
        if after[key] > before[key] + 1e-9:
            problems.append(f"{key} {before[key]} -> {after[key]}")
    if after["academic_latin_chars"] > before["academic_latin_chars"] * 1.05:
        problems.append("academic-latin output grew by more than 5%")
    return before, after, problems


def check(workers: int) -> int:
    """Re-judge the committed schemas/phone_decoder.json on the final split."""
    doc = json.loads(OUT.read_text(encoding="utf-8"))
    table = (doc.get("bigram") or {}).get("logprob") or {}
    clips = [c for c in bench.load_all() if lattice_key(c.corpus, c.key, c.split).exists()]
    with Pool(workers, initializer=_worker_init, initargs=(table,)) as pool:
        _, _, problems = judge(pool, clips, doc["decoder"], table)
    print("rejected:" if problems else "ok", problems or "")
    return 1 if problems else 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()

    _init_units()
    if args.check:
        return check(args.workers)
    clips = [c for c in bench.load_all() if lattice_key(c.corpus, c.key, c.split).exists()]
    lm = train_bigram(bench.load_all(drop=False))
    print(f"{len(clips)} clips with lattices; bigram from {lm['sentences']} sentences")
    table = lm["logprob"]
    baseline = BASELINE
    with Pool(args.workers, initializer=_worker_init, initargs=(table,)) as pool:
        rows = evaluate(pool, grid(), clips, "accept")
        base = next(r for r in rows if r["cfg"] == baseline)
        print("accept baseline", base)
        for r in sorted(rows, key=lambda r: r["dolma"])[:12]:
            print("  ", r)
        ok = [r for r in rows if r["persian"] <= base["persian"] and r["schwa"] <= base["schwa"] and r["cfg"] != baseline]
        ok = [r for r in ok if r["cfg"]["kind"] == "beam"]
        best = min(ok, key=lambda r: r["dolma"]) if ok else None
        print("best on accept", best)
        if best is None or best["dolma"] >= base["dolma"]:
            print("nothing beats the baseline on accept")
            return 0
        before, after, problems = judge(pool, clips, best["cfg"], table)
    REPORT.write_text(json.dumps({"accept": rows, "final": [before, after]}, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if problems:
        print("rejected:", problems)
        return 0
    print("kept")
    if args.write:
        cfg = dict(best["cfg"])
        doc = {"decoder": cfg, "beam": BEAM, "cand_floor": CAND_FLOOR, "cand_max": CAND_MAX, "before": before, "after": after}
        if cfg["kind"] == "beam" and cfg["weight"]:
            doc["bigram"] = {"sentences": lm["sentences"], "logprob": table}
        OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
