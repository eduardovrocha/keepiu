import logging
import os
import subprocess
import tempfile
from typing import Optional

logger = logging.getLogger(__name__)

_MAX_FILE_BYTES = 25 * 1024 * 1024  # 25 MB


def get_audio_duration(file_path: str) -> Optional[float]:
    """Return duration in seconds via ffprobe, or None on failure."""
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                file_path,
            ],
            capture_output=True, text=True, timeout=15,
        )
        return float(result.stdout.strip())
    except Exception as exc:
        logger.warning("ffprobe failed for %s: %s", file_path, exc)
        return None


def extract_audio(file_path: str, max_minutes: int = 10) -> str:
    """
    Convert any media file to WAV mono 16 kHz for OpenAI Whisper.

    Returns the path to a temporary WAV file — caller must delete it.
    Raises ValueError when size/duration limits are exceeded.
    Raises RuntimeError when ffmpeg conversion fails.
    """
    max_seconds = max_minutes * 60

    size = os.path.getsize(file_path)
    if size > _MAX_FILE_BYTES:
        raise ValueError(
            f"File too large for transcription: {size / 1_048_576:.1f} MB "
            f"(limit {_MAX_FILE_BYTES // 1_048_576} MB)"
        )

    duration = get_audio_duration(file_path)
    if duration is not None and duration > max_seconds:
        raise ValueError(
            f"Audio too long for transcription: {duration / 60:.1f} min "
            f"(limit {max_minutes} min)"
        )

    fd, out_path = tempfile.mkstemp(suffix=".wav")
    os.close(fd)

    try:
        result = subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", file_path,
                "-vn",
                "-acodec", "pcm_s16le",
                "-ar", "16000",
                "-ac", "1",
                out_path,
            ],
            capture_output=True,
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(
                f"ffmpeg failed (exit {result.returncode}): "
                f"{result.stderr.decode(errors='replace')[:300]}"
            )
        return out_path
    except Exception:
        if os.path.exists(out_path):
            try:
                os.unlink(out_path)
            except OSError:
                pass
        raise
