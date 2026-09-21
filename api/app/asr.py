from __future__ import annotations

from dataclasses import dataclass


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

    def recognize(self, wav_bytes: bytes, dialect: str = "unspecified") -> AsrResult:
        raise RuntimeError(
            "Allosaurus backend is stubbed. Install allosaurus + ffmpeg, then implement "
            "tempfile-in-memory recognition in api/app/asr.py (do not keep the wav)."
        )


def get_backend(name: str) -> AsrBackend:
    if name == "mock":
        return MockBackend()
    if name == "allosaurus":
        return AllosaurusBackend()
    raise ValueError(f"Unknown ASR backend: {name}")
