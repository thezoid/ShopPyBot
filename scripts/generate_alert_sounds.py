"""Generate ShopPyBot's alert sounds as original, public-domain WAV files.

These tones are synthesized from scratch with the Python standard library only
(`wave`, `math`, `struct`) — no samples, no downloads, no third-party assets.
The output is therefore free of any copyright/licensing encumbrance (CC0 /
public domain). Re-run this script to regenerate the three alert sounds:

    python scripts/generate_alert_sounds.py

It writes notification.wav, available.wav, and buy.wav into `core/sounds/`.
`utils.play_sound()` loads `{name}.mp3` first, then `{name}.wav`, so removing the
old `.mp3` files makes these `.wav` files take effect.
"""

import math
import os
import struct
import wave

SAMPLE_RATE = 44100  # Hz
# Output lands in the bundled package, not next to this dev-only script.
_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DIR = os.path.join(_REPO_ROOT, "core", "sounds")


def _synth(notes, total_dur, decay):
    """Render a mono float buffer from overlapping decaying notes.

    notes: list of (freq_hz, start_sec, dur_sec). Each note is a sine plus two
    soft harmonics under an exponential decay with a short click-free fade-in.
    """
    total = int(total_dur * SAMPLE_RATE)
    buf = [0.0] * total
    for freq, start, dur in notes:
        s0 = int(start * SAMPLE_RATE)
        n = int(dur * SAMPLE_RATE)
        for i in range(n):
            idx = s0 + i
            if idx >= total:
                break
            t = i / SAMPLE_RATE
            env = math.exp(-decay * t)
            fade_in = min(1.0, t / 0.004)  # ~4ms fade-in removes the attack click
            sample = (
                math.sin(2 * math.pi * freq * t)
                + 0.30 * math.sin(2 * math.pi * 2 * freq * t)
                + 0.12 * math.sin(2 * math.pi * 3 * freq * t)
            )
            buf[idx] += sample * env * fade_in
    return buf


def _write_wav(name, buf):
    """Normalize to -1 dBFS-ish and write 16-bit mono PCM."""
    peak = max(1e-9, max(abs(x) for x in buf))
    scale = 0.9 / peak
    path = os.path.join(_DIR, f"{name}.wav")
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SAMPLE_RATE)
        frames = bytearray()
        for x in buf:
            v = max(-1.0, min(1.0, x * scale))
            frames += struct.pack("<h", int(v * 32767))
        w.writeframes(bytes(frames))
    return path


# Note frequencies (equal temperament): C5..C6
C5, E5, G5, A5, C6 = 523.25, 659.25, 783.99, 880.00, 1046.50

# Three distinct cues:
#   notification — gentle two-note "ping" (low-key, frequent)
#   available    — bright ascending triad (attention: item in stock)
#   buy          — celebratory ascending arpeggio resolving up an octave (success)
SOUNDS = {
    "notification": (
        [(G5, 0.00, 0.40), (C6, 0.08, 0.42)],
        0.55,
        8.0,
    ),
    "available": (
        [(C5, 0.00, 0.25), (E5, 0.12, 0.25), (G5, 0.24, 0.55)],
        0.85,
        6.0,
    ),
    "buy": (
        [(C5, 0.00, 0.22), (E5, 0.12, 0.22), (G5, 0.24, 0.22), (C6, 0.36, 0.60)],
        1.00,
        5.0,
    ),
}


def main():
    for name, (notes, total, decay) in SOUNDS.items():
        path = _write_wav(name, _synth(notes, total, decay))
        print(f"wrote {path}")


if __name__ == "__main__":
    main()
