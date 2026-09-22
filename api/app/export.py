from __future__ import annotations

from pathlib import Path


def export_paths(stem: str) -> tuple[str, str]:
    """Side-by-side names for one corrected clip. Stem has no suffix."""
    base = Path(stem).name
    if base.endswith(".wav"):
        base = base[: -len(".wav")]
    return f"{base}.wav", f"{base}.ipa.txt"


def write_pair(folder: Path, stem: str, wav_bytes: bytes, ipa: str) -> tuple[Path, Path]:
    folder.mkdir(parents=True, exist_ok=True)
    wav_name, ipa_name = export_paths(stem)
    wav_path = folder / wav_name
    ipa_path = folder / ipa_name
    wav_path.write_bytes(wav_bytes)
    ipa_path.write_text(ipa.strip() + "\n", encoding="utf-8")
    return wav_path, ipa_path


def tokenize_ipa(ipa: str) -> list[str]:
    return [tok for tok in ipa.replace(".", " ").replace("-", " ").split() if tok]


def _levenshtein(ref: list[str], hyp: list[str]) -> int:
    if not ref:
        return len(hyp)
    if not hyp:
        return len(ref)
    prev = list(range(len(hyp) + 1))
    for i, r in enumerate(ref, start=1):
        cur = [i]
        for j, h in enumerate(hyp, start=1):
            ins = cur[j - 1] + 1
            delete = prev[j] + 1
            sub = prev[j - 1] + (0 if r == h else 1)
            cur.append(min(ins, delete, sub))
        prev = cur
    return prev[-1]


def phone_error_rate(reference: str, hypothesis: str) -> float:
    """PER = phone Levenshtein / reference length. Empty reference → 0 if hyp empty else 1."""
    ref = tokenize_ipa(reference)
    hyp = tokenize_ipa(hypothesis)
    if not ref:
        return 0.0 if not hyp else 1.0
    return _levenshtein(ref, hyp) / len(ref)


def score_export_dir(folder: Path) -> dict:
    """Score each `*.wav` against sibling `*.ipa.txt` gold vs `*.hyp.txt` if present.

    Gold is the corrected IPA the speaker saved. Hypothesis is optional (offline ASR).
    Clips without a hyp file are skipped, not failed.
    """
    folder = Path(folder)
    rows = []
    for wav in sorted(folder.glob("*.wav")):
        gold_path = wav.with_name(wav.stem + ".ipa.txt")
        hyp_path = wav.with_name(wav.stem + ".hyp.txt")
        if not gold_path.is_file() or not hyp_path.is_file():
            continue
        gold = gold_path.read_text(encoding="utf-8")
        hyp = hyp_path.read_text(encoding="utf-8")
        rows.append(
            {
                "stem": wav.stem,
                "per": phone_error_rate(gold, hyp),
                "n_ref": len(tokenize_ipa(gold)),
            }
        )
    n = sum(row["n_ref"] for row in rows)
    weighted = sum(row["per"] * row["n_ref"] for row in rows) / n if n else None
    return {"clips": rows, "clip_count": len(rows), "per": weighted}
