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


def normalize_token(token: str, inventory: dict | None = None) -> str:
    """Map Allosaurus (or other) symbols onto the Gilaki inventory aliases."""
    inventory = inventory or load_inventory()
    token = unicodedata.normalize("NFC", token)
    aliases = inventory.get("aliases") or {}
    return aliases.get(token, token)


def normalize_phones(tokens: list[str], inventory: dict | None = None) -> list[str]:
    return [normalize_token(token, inventory) for token in tokens if token]


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
        if len(parts) >= 3:
            try:
                start = float(parts[0])
                duration = float(parts[1])
            except ValueError:
                timestamped = False
                break
            parsed.append(Phone(ipa=parts[2], start=start, end=start + duration))
        else:
            timestamped = False
            break
    if timestamped and parsed:
        return parsed
    tokens = text.replace("\n", " ").split()
    return [Phone(ipa=token) for token in tokens]


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
                lang_id=settings.allosaurus_lang or "ipa",
                timestamp=True,
            )
        except Exception as exc:  # noqa: BLE001 — surface as 501 backend_unavailable
            raise RuntimeError(f"allosaurus failed: {exc}") from exc
        finally:
            path.unlink(missing_ok=True)

        inventory = load_inventory()
        phones: list[Phone] = []
        for phone in parse_allosaurus_output(str(raw) if raw is not None else ""):
            phones.append(
                Phone(
                    ipa=normalize_token(phone.ipa, inventory),
                    start=phone.start,
                    end=phone.end,
                )
            )
        return AsrResult(phones=phones, backend=self.name)


def get_backend(name: str) -> AsrBackend:
    if name == "mock":
        return MockBackend()
    if name == "allosaurus":
        return AllosaurusBackend()
    raise ValueError(f"Unknown ASR backend: {name}")
