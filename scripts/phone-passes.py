#!/usr/bin/env python3
"""Search for inventory-filter rules, one pass at a time, using scripts/phone-bench.py.

Passes:
  smoking  recognizer symbols outside the inventory: re-decide their fold or delete them
  rare     inventory phones the recognizer emits far more or less often than the references
  context  common confusions: two-phone merges, splits, and substitutions next to a neighbour

Candidates come from the propose split. Each is tested alone on the accept split:
  - the Persian judge must gain at least MIN_GAIN in PER with a bootstrap 90% interval above 0,
    and DOLMA must not lose more than TOLERANCE;
  - a rule about ə or ü is judged by DOLMA instead (logged as dolma-only);
  - a rule the Persian clips barely touch is judged by DOLMA, but only if the Persian clips it
    does touch show no loss (logged as dolma-sparse), so a vetoed rule cannot return split
    into narrow contexts;
  - every output phone must be within MAX_FEATURE_DISTANCE of an input phone.
A kept rule stays in force for later candidates, and alignment is rebuilt each round.

At the end of the pass the final split must not get worse on either corpus, DOLMA test CER
must not rise for Varg or lossy-Persian, and academic-Latin output must not grow by more
than 5%. Otherwise the whole pass is rolled back.

  phone-passes.py smoking            dry run, logs to data/bench/pass-smoking.json
  phone-passes.py smoking --write    also writes the kept rules into gilaki_inventory.json
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import unicodedata
from collections import Counter, defaultdict
from dataclasses import dataclass
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
from app.rewriter import apply_map, tokenize_ipa  # noqa: E402

INVENTORY_PATH = ROOT / "schemas" / "gilaki_inventory.json"
SUMMARY = ROOT / "schemas" / "phone_filter_passes.json"
MIN_GAIN = 0.002
TOLERANCE = 0.0005
MIN_SUPPORT = 15
MIN_PERSIAN_CLIPS = 30
MAX_FEATURE_DISTANCE = 8.0
MAX_CANDIDATES = 40
MAX_ROUNDS = 3
BOOTSTRAP = 1000
GILAKI_ONLY = {"ə", "ü"}


@dataclass
class State:
    aliases: dict
    rewrites: list

    def copy(self) -> "State":
        return State(dict(self.aliases), [dict(r) for r in self.rewrites])


def fold(state: State, raw: str) -> str:
    return state.aliases.get(raw, raw)


def indexed(raw: list[str], state: State) -> list[tuple[str, tuple[int, int]]]:
    seq = [(fold(state, tok), (i, i + 1)) for i, tok in enumerate(raw)]
    seq = [(p, span) for p, span in seq if p]
    for rule in sorted(state.rewrites, key=lambda r: -len(r["from"])):
        src, dst, n = rule["from"], rule["to"], len(rule["from"])
        out, i = [], 0
        while i < len(seq):
            if [p for p, _ in seq[i : i + n]] == src:
                span = (seq[i][1][0], seq[i + n - 1][1][1])
                out.extend((p, span) for p in dst)
                i += n
            else:
                out.append(seq[i])
                i += 1
        seq = out
    return seq


def clip_score(clip, state: State):
    return bench.score_clip(clip, state.aliases, state.rewrites)


def nearest_member(phone: str, allowed: frozenset) -> str:
    return min(sorted(allowed), key=lambda a: bench.sub_cost(phone, frozenset({a})))


def feature_distance(a: str, b: str) -> float:
    if a == b:
        return 0.0
    base = "".join(ch for ch in unicodedata.normalize("NFC", a) if ch == "ː" or unicodedata.category(ch) not in {"Mn", "Lm", "Sk"})
    try:
        return bench._dist().weighted_feature_edit_distance(base or a, b)
    except Exception:
        return 99.0


def guard(cand: dict) -> bool:
    if cand["kind"] == "alias":
        return cand["to"] == "" or feature_distance(cand["from"], cand["to"]) <= MAX_FEATURE_DISTANCE
    return all(any(feature_distance(s, t) <= MAX_FEATURE_DISTANCE for s in cand["from"]) for t in cand["to"])


def touches_gilaki_only(cand: dict) -> bool:
    if cand["kind"] == "alias":
        phones = {cand["from"], cand["to"]}
    else:
        phones = set(cand["from"]) | set(cand["to"])
    return bool(phones & GILAKI_ONLY)


def apply_candidate(state: State, cand: dict) -> State:
    new = state.copy()
    if cand["kind"] == "alias":
        new.aliases[cand["from"]] = cand["to"]
    else:
        new.rewrites.append({"from": cand["from"], "to": cand["to"]})
    return new


def affected(clip, state: State, cand: dict) -> bool:
    if cand["kind"] == "alias":
        return cand["from"] in clip.raw
    seq = [p for p, _ in indexed(clip.raw, state)]
    n = len(cand["from"])
    return any(seq[i : i + n] == cand["from"] for i in range(len(seq) - n + 1))


def describe(cand: dict) -> str:
    if cand["kind"] == "alias":
        return f"{cand['from']} -> {cand['to'] or 'delete'}"
    return f"{' '.join(cand['from'])} -> {' '.join(cand['to']) or 'delete'}"


# Evidence from the propose split


def evidence(clips, state: State):
    votes: dict[str, Counter] = defaultdict(Counter)
    raw_total: Counter = Counter()
    raw_ins: Counter = Counter()
    hyp_count: Counter = Counter()
    ref_count: Counter = Counter()
    merges: Counter = Counter()
    splits: Counter = Counter()
    context: Counter = Counter()
    confusion: Counter = Counter()
    for clip in clips:
        seq = indexed(clip.raw, state)
        phones = [p for p, _ in seq]
        ops = bench.align(phones, clip.ref)
        for ref in clip.ref:
            if not ref.optional:
                for a in ref.allowed:
                    ref_count[a] += 1 / len(ref.allowed)
        h = 0
        rows = []
        for kind, hyp, ref in ops:
            if hyp is None:
                rows.append((kind, None, None, ref))
                continue
            span = seq[h][1]
            raw = clip.raw[span[0]] if span[1] - span[0] == 1 else None
            rows.append((kind, hyp, raw, ref))
            hyp_count[hyp] += 1
            h += 1
        for k, (kind, hyp, raw, ref) in enumerate(rows):
            if raw is not None:
                raw_total[raw] += 1
                if kind == "ins":
                    raw_ins[raw] += 1
                elif kind in ("ok", "sub"):
                    votes[raw][hyp if kind == "ok" else nearest_member(raw, ref.allowed)] += 1
            if kind == "sub":
                confusion[(hyp, nearest_member(hyp, ref.allowed))] += 1
            nxt = rows[k + 1] if k + 1 < len(rows) else None
            if nxt is None:
                continue
            if kind == "ins" and nxt[0] in ("ok", "sub"):
                merges[((hyp, nxt[1]), nearest_member(nxt[1], nxt[3].allowed))] += 1
            if kind in ("ok", "sub") and nxt[0] == "ins":
                merges[((hyp, nxt[1]), nearest_member(hyp, ref.allowed))] += 1
            if kind in ("ok", "sub") and nxt[0] == "del":
                splits[(hyp, (nearest_member(hyp, ref.allowed), nearest_member(hyp, nxt[3].allowed)))] += 1
            if kind == "sub" and nxt[0] == "ok":
                context[((hyp, nxt[1]), (nearest_member(hyp, ref.allowed), nxt[1]))] += 1
    return {
        "votes": votes, "raw_total": raw_total, "raw_ins": raw_ins, "hyp_count": hyp_count,
        "ref_count": ref_count, "merges": merges, "splits": splits, "context": context, "confusion": confusion,
    }


def alias_candidates(ev, state: State, symbols) -> list[dict]:
    out = []
    for raw in symbols:
        total = ev["raw_total"][raw]
        if total < MIN_SUPPORT:
            continue
        current = fold(state, raw)
        for target, n in ev["votes"][raw].most_common(3):
            if target != current and n >= MIN_SUPPORT and target in bench.PHONES:
                out.append({"kind": "alias", "from": raw, "to": target, "support": n})
        if ev["raw_ins"][raw] / total >= 0.5 and current != "":
            out.append({"kind": "alias", "from": raw, "to": "", "support": ev["raw_ins"][raw]})
    return out


def pass_candidates(name: str, ev, state: State, clips) -> list[dict]:
    raw_symbols = {tok for c in clips for tok in c.raw}
    if name == "smoking":
        produced = {fold(state, t) for t in raw_symbols} - {""}
        referenced = {a for a, n in ev["ref_count"].items() if n >= 1}
        ev["sets"] = {
            "hyp_only": sorted(produced - referenced),
            "ref_only": sorted(referenced - produced),
            "raw_outside_inventory": len([s for s in raw_symbols if s not in bench.PHONES]),
        }
        symbols = [s for s in raw_symbols if s not in bench.PHONES]
        symbols += [s for s in raw_symbols if fold(state, s) in ev["sets"]["hyp_only"]]
        for ref_only in ev["sets"]["ref_only"]:
            symbols += [s for s in raw_symbols if ev["votes"][s][ref_only] >= MIN_SUPPORT]
        return alias_candidates(ev, state, sorted(set(symbols)))
    if name == "rare":
        off = []
        for phone in bench.PHONES:
            hyp, ref = ev["hyp_count"][phone], ev["ref_count"][phone]
            if hyp + ref < MIN_SUPPORT:
                continue
            ratio = (hyp + 1) / (ref + 1)
            if ratio >= 2 or ratio <= 0.5:
                off.append(phone)
        ev["sets"] = {"frequency_off": sorted(off)}
        symbols = [s for s in raw_symbols if fold(state, s) in off or s in off]
        for phone in off:
            symbols += [s for s in raw_symbols if ev["votes"][s][phone] >= MIN_SUPPORT]
        return alias_candidates(ev, state, sorted(set(symbols)))
    out = []
    for ((a, b), target), n in ev["merges"].most_common():
        if n >= MIN_SUPPORT and target in bench.PHONES:
            out.append({"kind": "rewrite", "from": [a, b], "to": [target], "support": n})
    for (a, (t1, t2)), n in ev["splits"].most_common():
        if n >= MIN_SUPPORT and [t1, t2] != [a]:
            out.append({"kind": "rewrite", "from": [a], "to": [t1, t2], "support": n})
    for ((a, b), (t, b2)), n in ev["context"].most_common():
        if n >= MIN_SUPPORT:
            out.append({"kind": "rewrite", "from": [a, b], "to": [t, b2], "support": n})
    return out


# Testing a candidate on the accept split


class Judge:
    def __init__(self, clips, state: State):
        self.clips = clips
        self.cache = {id(c): clip_score(c, state) for c in clips}

    def rescore(self, state: State, subset) -> None:
        for c in subset:
            self.cache[id(c)] = clip_score(c, state)

    def test(self, state: State, cand: dict, rng) -> dict:
        new_state = apply_candidate(state, cand)
        result = {}
        changed = {}
        for corpus in ("persian", "dolma"):
            clips = [c for c in self.clips if c.corpus == corpus]
            hit = [c for c in clips if affected(c, state, cand)]
            if not clips:
                continue
            before = np.array([self.cache[id(c)].errors for c in clips], dtype=float)
            totals = np.array([self.cache[id(c)].total for c in clips], dtype=float)
            after = before.copy()
            index = {id(c): k for k, c in enumerate(clips)}
            for c in hit:
                s = clip_score(c, new_state)
                changed[id(c)] = s
                after[index[id(c)]] = s.errors
            diff = before - after
            gain = diff.sum() / totals.sum()
            samples = rng.integers(0, len(clips), size=(BOOTSTRAP, len(clips)))
            boot = diff[samples].sum(axis=1) / totals[samples].sum(axis=1)
            result[corpus] = {"gain": float(gain), "low": float(np.percentile(boot, 5)), "clips": len(hit)}
        return {"stats": result, "changed": changed, "state": new_state}


def decide(cand: dict, stats: dict) -> tuple[bool, str]:
    fa, gk = stats.get("persian"), stats.get("dolma")
    dolma_ok = gk is not None and gk["gain"] >= MIN_GAIN and gk["low"] > 0
    if touches_gilaki_only(cand):
        return dolma_ok, "dolma-only"
    if not fa or fa["clips"] < MIN_PERSIAN_CLIPS:
        # Sparse in Persian: DOLMA decides, but only if the Persian clips it does touch do not disagree.
        persian_agrees = not fa or fa["clips"] == 0 or (fa["gain"] >= 0 and fa["low"] >= 0)
        return dolma_ok and persian_agrees, "dolma-sparse"
    ok = fa["gain"] >= MIN_GAIN and fa["low"] > 0 and (gk is None or gk["gain"] >= -TOLERANCE)
    return ok, "persian"


# End-of-pass checks on the final split


def final_report(clips, state: State) -> dict:
    out = {}
    for corpus in ("dolma", "persian"):
        s = bench.Score()
        for c in clips:
            if c.corpus == corpus and c.split == "final":
                s.add(clip_score(c, state))
        if s.total:
            out[f"{corpus}_final_per"] = round(s.per, 4)
    test = [c for c in dolma.load_clips()]
    maps = {k: get_preset(k) for k in ("varg-perso-arabic", "lossy-persian", "academic-latin")}
    cers = {"varg-perso-arabic": 0.0, "lossy-persian": 0.0}
    latin_len = 0
    for clip in test:
        filtered = " ".join(bench.apply_filter(tokenize_ipa(clip["ipa"]), state.aliases, state.rewrites))
        gold = dolma.plain_letters(clip["sentence"])
        for key in cers:
            cers[key] += dolma.cer(gold, dolma.plain_letters(apply_map(filtered, {**maps[key], "aliases": {}})))
        latin_len += len(apply_map(filtered, {**maps["academic-latin"], "aliases": {}}))
    for key in cers:
        out[f"cer_{key}"] = round(cers[key] / len(test), 4)
    out["academic_latin_chars"] = latin_len
    return out


def final_ok(before: dict, after: dict) -> list[str]:
    problems = []
    for key in ("dolma_final_per", "persian_final_per", "cer_varg-perso-arabic", "cer_lossy-persian"):
        if key in before and after.get(key, 0) > before[key] + 1e-9:
            problems.append(f"{key} {before[key]} -> {after[key]}")
    if after["academic_latin_chars"] > before["academic_latin_chars"] * 1.05:
        problems.append("academic-latin output grew by more than 5%")
    return problems


def run_pass(name: str, clips, state: State) -> tuple[State, dict]:
    rng = np.random.default_rng(1404)
    propose = [c for c in clips if c.split == "propose"]
    judge = Judge([c for c in clips if c.split == "accept"], state)
    start = final_report(clips, state)
    print("start", start, flush=True)
    kept, tried, sets = [], [], None
    for round_no in range(1, MAX_ROUNDS + 1):
        ev = evidence(propose, state)
        cands = pass_candidates(name, ev, state, propose)
        sets = sets or ev.get("sets")
        seen = {describe(t["rule"]) for t in tried}
        cands = [c for c in sorted(cands, key=lambda c: -c["support"]) if describe(c) not in seen]
        cands = [c for c in cands if guard(c)][:MAX_CANDIDATES]
        print(f"round {round_no}: {len(cands)} candidates", flush=True)
        accepted = 0
        for cand in cands:
            if cand["kind"] == "alias" and cand["to"] == fold(state, cand["from"]):
                continue
            out = judge.test(state, cand, rng)
            ok, basis = decide(cand, out["stats"])
            row = {"rule": cand, "basis": basis, "stats": out["stats"], "kept": ok, "round": round_no}
            tried.append(row)
            if ok:
                state = out["state"]
                for key, score in out["changed"].items():
                    judge.cache[key] = score
                kept.append(row)
                accepted += 1
                print(f"  keep {describe(cand):24} {basis:10} {json.dumps(out['stats'])}", flush=True)
        if not accepted:
            break
    end = final_report(clips, state)
    problems = final_ok(start, end)
    log = {"pass": name, "sets": sets, "start": start, "end": end, "problems": problems,
           "kept": kept, "tried": len(tried), "rejected_sample": [t for t in tried if not t["kept"]][:30]}
    print("end", end, flush=True)
    if problems:
        print("rolled back:", problems, flush=True)
    return state, log


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=["smoking", "rare", "context"])
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()

    inventory = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
    state = State(dict(inventory.get("aliases") or {}), list(inventory.get("rewrites") or []))
    clips = bench.load_all()
    print({k: v for k, v in Counter(f"{c.corpus}/{c.split}" for c in clips).items()}, flush=True)
    new_state, log = run_pass(args.name, clips, state)
    bench.BENCH.mkdir(parents=True, exist_ok=True)
    (bench.BENCH / f"pass-{args.name}.json").write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str) + "\n", encoding="utf-8")
    if log["problems"] or not log["kept"]:
        print("nothing written")
        return 0
    if args.write:
        inventory["aliases"] = dict(sorted(new_state.aliases.items()))
        if new_state.rewrites:
            inventory["rewrites"] = new_state.rewrites
        INVENTORY_PATH.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        summary = json.loads(SUMMARY.read_text(encoding="utf-8")) if SUMMARY.exists() else {"passes": []}
        summary["passes"] = [p for p in summary["passes"] if p["pass"] != args.name]
        summary["passes"].append({
            "pass": args.name,
            "start": log["start"],
            "end": log["end"],
            "rules": [
                {"rule": describe(k["rule"]), "basis": k["basis"],
                 "gain": {c: round(v["gain"], 4) for c, v in k["stats"].items()}}
                for k in log["kept"]
            ],
        })
        SUMMARY.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
        print(f"wrote {len(log['kept'])} rules")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
