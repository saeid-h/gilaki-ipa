#!/usr/bin/env python3
"""Score phone error rate on a local export folder. Never uploads clips.

Each clip is a triple:
  name.wav
  name.ipa.txt   gold (speaker-corrected)
  name.hyp.txt   optional hypothesis from a local recognizer run

Prints weighted PER. Exit 0 if the folder has no scorable pairs (so CI stays green).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "api"))

from app.export import score_export_dir  # noqa: E402


def main() -> int:
    folder = Path(sys.argv[1] if len(sys.argv) > 1 else "clips")
    if not folder.is_dir():
        print(f"no clip folder at {folder} — nothing to score")
        return 0
    out = score_export_dir(folder)
    if out["clip_count"] == 0:
        print(f"{folder}: no wav+ipa.txt+hyp.txt triples")
        return 0
    print(f"{folder}: {out['clip_count']} clips, PER={out['per']:.4f}")
    for row in out["clips"]:
        print(f"  {row['stem']}: {row['per']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
