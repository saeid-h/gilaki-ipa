from __future__ import annotations

import tempfile
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from .audio import TEMP_PREFIX
from .catalog import load_inventory
from .settings import settings


@dataclass
class Phone:
    ipa: str
    start: float | None = None
    end: float | None = None


@dataclass
class AsrResult:
    phones: list[Phone]
    backend: str
    duration_sec: float | None = None
    sample_rate: int = 16000

    @property
    def ipa_string(self) -> str:
        return " ".join(phone.ipa for phone in self.phones)


class AsrBackend:
    name = "base"

    def recognize(self, wav_bytes: bytes, dialect: str = "unspecified") -> AsrResult:
        raise NotImplementedError


# Allosaurus spelling for Gilaki phones that the uni2005 unit file uses a different glyph for.
_ALLOSAURUS_SPELLING = {"ü": "y"}


def inventory_phones(inventory: dict | None = None) -> set[str]:
    inventory = inventory or load_inventory()
    return set(inventory.get("vowels") or []) | set(inventory.get("consonants") or [])


def inventory_unit_phones(inventory: dict | None = None) -> list[str]:
    """Gilaki phones spelled as Allosaurus unit tokens (one per line, no spaces)."""
    return sorted(_ALLOSAURUS_SPELLING.get(phone, phone) for phone in inventory_phones(inventory))


def inventory_unit_path(inventory: dict | None = None) -> Path:
    phones = inventory_unit_phones(inventory)
    path = Path(tempfile.gettempdir()) / "gilaki-allosaurus-unit.txt"
    text = "\n".join(phones) + "\n"
    if not path.exists() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")
    return path


def allosaurus_lang_id() -> str:
    """Allosaurus `lang_id`. A file path constrains decoding to that unit list.

    `ipa` (the library default) is the full ~230-phone set and jumps between
    similar world phones, which reads as random Gilaki. `ipa`/`glk`/empty use
    the Gilaki inventory file instead. Set `ALLOSAURUS_LANG=all` for unconstrained.
    """
    requested = (settings.allosaurus_lang or "glk").strip().lower()
    if requested in {"", "ipa", "glk"}:
        return str(inventory_unit_path())
    if requested in {"all", "unconstrained"}:
        return "ipa"
    return requested


def normalize_token(token: str, inventory: dict | None = None) -> str:
    """Map Allosaurus (or other) symbols onto the Gilaki inventory aliases."""
    inventory = inventory or load_inventory()
    token = unicodedata.normalize("NFC", token)
    aliases = inventory.get("aliases") or {}
    return aliases.get(token, token)


def normalize_phones(tokens: list[str], inventory: dict | None = None) -> list[str]:
    return [normalize_token(token, inventory) for token in tokens if token]


def _is_float_token(token: str) -> bool:
    try:
        float(token)
    except ValueError:
        return False
    return True


def parse_allosaurus_output(raw: str) -> list[Phone]:
    """Parse space-separated phones or `start duration phone` timestamp lines."""
    text = (raw or "").strip()
    if not text:
        return []
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    timestamped = True
    parsed: list[Phone] = []
    for line in lines:
        parts = line.split()
        if len(parts) < 3 or len(parts) % 3 != 0:
            timestamped = False
            break
        triples: list[Phone] = []
        ok = True
        for i in range(0, len(parts), 3):
            try:
                start = float(parts[i])
                duration = float(parts[i + 1])
            except ValueError:
                ok = False
                break
            triples.append(Phone(ipa=parts[i + 2], start=start, end=start + duration))
        if not ok:
            timestamped = False
            break
        parsed.extend(triples)
    if timestamped and parsed:
        return parsed
    tokens = text.replace("\n", " ").split()
    return [Phone(ipa=token) for token in tokens if token and not _is_float_token(token)]


class MockBackend(AsrBackend):
    """Deterministic backend so web/Android work before a real model is installed."""

    name = "mock"

    def recognize(self, wav_bytes: bytes, dialect: str = "unspecified") -> AsrResult:
        # Placeholder phrase: "mə šənâ" — enough to test mapping and RTL.
        phones = [
            Phone("m", 0.10, 0.18),
            Phone("ə", 0.18, 0.28),
            Phone("ʃ", 0.32, 0.44),
            Phone("ə", 0.44, 0.54),
            Phone("n", 0.54, 0.62),
            Phone("ɒ", 0.62, 0.80),
        ]
        return AsrResult(phones=phones, backend=self.name, duration_sec=1.0)


class AllosaurusBackend(AsrBackend):
    name = "allosaurus"
    _recognizer = None

    @classmethod
    def recognizer(cls):
        if cls._recognizer is None:
            try:
                from allosaurus.app import read_recognizer
            except ImportError as exc:
                raise RuntimeError(
                    "allosaurus is not installed. pip install -r api/requirements-allosaurus.txt "
                    "inside the repo-root .venv"
                ) from exc
            cls._recognizer = read_recognizer()
        return cls._recognizer

    def recognize(self, wav_bytes: bytes, dialect: str = "unspecified") -> AsrResult:
        handle = tempfile.NamedTemporaryFile(prefix=TEMP_PREFIX, suffix=".wav", delete=False)
        path = Path(handle.name)
        handle.close()
        try:
            path.write_bytes(wav_bytes)
            raw = self.recognizer().recognize(
                str(path),
                lang_id=allosaurus_lang_id(),
                timestamp=True,
            )
        except Exception as exc:  # noqa: BLE001 — surface as 501 backend_unavailable
            raise RuntimeError(f"allosaurus failed: {exc}") from exc
        finally:
            path.unlink(missing_ok=True)

        inventory = load_inventory()
        allowed = inventory_phones(inventory)
        phones: list[Phone] = []
        for phone in parse_allosaurus_output(str(raw) if raw is not None else ""):
            ipa = normalize_token(phone.ipa, inventory)
            if ipa not in allowed:
                continue
            phones.append(Phone(ipa=ipa, start=phone.start, end=phone.end))
        return AsrResult(phones=phones, backend=self.name)


def get_backend(name: str) -> AsrBackend:
    if name == "mock":
        return MockBackend()
    if name == "allosaurus":
        return AllosaurusBackend()
    raise ValueError(f"Unknown ASR backend: {name}")
