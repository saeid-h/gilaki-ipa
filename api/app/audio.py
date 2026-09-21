from __future__ import annotations

import shutil
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path

TEMP_PREFIX = "gilaki-ipa-"
OUTPUT_RATE = 16000


class AudioPrepError(Exception):
    def __init__(self, status: int, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.status = status
        self.code = code
        self.message = message


@dataclass
class PreparedAudio:
    wav_bytes: bytes
    duration_sec: float
    sample_rate: int = OUTPUT_RATE


def ffmpeg_path() -> str | None:
    return shutil.which("ffmpeg")


def _duration_sec(wav_path: Path) -> float:
    with wave.open(str(wav_path), "rb") as handle:
        frames = handle.getnframes()
        rate = handle.getframerate()
    if rate <= 0:
        raise AudioPrepError(422, "invalid_audio", "Could not read sample rate")
    return frames / float(rate)


def prepare_audio(blob: bytes, max_duration_sec: float) -> PreparedAudio:
    binary = ffmpeg_path()
    if not binary:
        raise AudioPrepError(501, "backend_unavailable", "ffmpeg is not installed")

    src = tempfile.NamedTemporaryFile(prefix=TEMP_PREFIX, suffix=".in", delete=False)
    dst = tempfile.NamedTemporaryFile(prefix=TEMP_PREFIX, suffix=".wav", delete=False)
    src_path = Path(src.name)
    dst_path = Path(dst.name)
    src.close()
    dst.close()
    try:
        src_path.write_bytes(blob)
        cmd = [
            binary,
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-i",
            str(src_path),
            "-vn",
            "-ac",
            "1",
            "-ar",
            str(OUTPUT_RATE),
            "-c:a",
            "pcm_s16le",
            str(dst_path),
        ]
        try:
            proc = subprocess.run(cmd, capture_output=True, timeout=120)
        except subprocess.TimeoutExpired as exc:
            raise AudioPrepError(422, "invalid_audio", "ffmpeg timed out") from exc
        if proc.returncode != 0 or not dst_path.exists() or dst_path.stat().st_size == 0:
            detail = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            raise AudioPrepError(422, "invalid_audio", detail or "unreadable audio")
        duration = _duration_sec(dst_path)
        if duration > max_duration_sec:
            raise AudioPrepError(422, "audio_too_long", f"duration {duration:.2f}s exceeds {max_duration_sec}s")
        return PreparedAudio(
            wav_bytes=dst_path.read_bytes(),
            duration_sec=duration,
            sample_rate=OUTPUT_RATE,
        )
    finally:
        src_path.unlink(missing_ok=True)
        dst_path.unlink(missing_ok=True)
