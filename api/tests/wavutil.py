from __future__ import annotations

import io
import wave


def pcm_wav(duration_sec: float = 0.25, sample_rate: int = 44100, channels: int = 2) -> bytes:
    """Tiny silent PCM WAV so tests do not depend on fixture files."""
    buf = io.BytesIO()
    nframes = max(1, int(duration_sec * sample_rate))
    with wave.open(buf, "wb") as handle:
        handle.setnchannels(channels)
        handle.setsampwidth(2)
        handle.setframerate(sample_rate)
        handle.writeframes(b"\x00\x00" * nframes * channels)
    return buf.getvalue()
