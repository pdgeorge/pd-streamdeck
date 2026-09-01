#!/usr/bin/env python3
"""
Drop placeholder audio into each mood folder so the whole chain is testable
before the real library exists.

Two modes:

  default   a short, obviously-distinct tone motif per mood, generated with
            nothing but the standard library. Works anywhere, no installs.

  --tts     spoken mood names ("sad", "hype", ...) via edge-tts, which is
            already in the DabiReborn stack. Easier to identify by ear when
            you're testing several buttons in a row.

Usage:
    python3 tools/seed_placeholder_songs.py
    python3 tools/seed_placeholder_songs.py --tts
    python3 tools/seed_placeholder_songs.py --count 3 --seconds 12
"""

import argparse
import math
import struct
import subprocess
import sys
import wave
from pathlib import Path

SAMPLE_RATE = 44100

# One motif per mood: (base frequency Hz, interval ratios, note seconds).
# Distinct enough that you can tell which button you pressed with your eyes
# on the game rather than the tablet.
MOTIFS = {
    "sad":     (220.0, [1.0, 1.2, 0.9, 0.8], 1.4),          # descending, minor-ish
    "hype":    (440.0, [1.0, 1.25, 1.5, 2.0], 0.35),        # fast ascending
    "chill":   (261.6, [1.0, 1.5, 1.33, 1.5], 1.8),         # slow, open
    "tension": (146.8, [1.0, 1.06, 1.0, 1.06], 0.5),        # low, wavering
}
DEFAULT_MOTIF = (330.0, [1.0, 1.2, 1.4], 1.0)


def render_tone(path: Path, seconds: float, motif) -> None:
    base, ratios, note_len = motif
    frames = bytearray()
    total = int(SAMPLE_RATE * seconds)

    for i in range(total):
        t = i / SAMPLE_RATE
        note_index = int(t / note_len) % len(ratios)
        freq = base * ratios[note_index]

        # Per-note envelope so notes articulate instead of running together.
        pos = (t % note_len) / note_len
        env = min(1.0, pos * 12) * min(1.0, (1.0 - pos) * 4)

        # Overall fade so looping in the player doesn't click.
        if t < 0.05:
            env *= t / 0.05
        if t > seconds - 0.25:
            env *= max(0.0, (seconds - t) / 0.25)

        sample = math.sin(2 * math.pi * freq * t)
        sample += 0.3 * math.sin(4 * math.pi * freq * t)   # a little body
        value = int(max(-1.0, min(1.0, sample * env * 0.28)) * 32767)
        frames += struct.pack("<h", value)

    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes(bytes(frames))


def render_tts(path: Path, text: str) -> bool:
    """Speak the mood name using edge-tts if it's installed."""
    try:
        subprocess.run(
            ["edge-tts", "--voice", "en-GB-RyanNeural",
             "--text", text, "--write-media", str(path.with_suffix(".mp3"))],
            check=True, capture_output=True,
        )
        return True
    except (FileNotFoundError, subprocess.CalledProcessError) as exc:
        print(f"  edge-tts unavailable ({exc.__class__.__name__}); using a tone instead")
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--library", default="songs", help="library root (default: songs)")
    parser.add_argument("--count", type=int, default=2, help="files per mood")
    parser.add_argument("--seconds", type=float, default=10.0, help="tone length")
    parser.add_argument("--tts", action="store_true", help="speak mood names via edge-tts")
    parser.add_argument("--force", action="store_true", help="overwrite existing placeholders")
    args = parser.parse_args()

    root = Path(args.library)
    if not root.is_dir():
        print(f"No library at {root.resolve()} -- run this from the repo root.")
        return 1

    moods = [d for d in sorted(root.iterdir()) if d.is_dir() and not d.name.startswith(".")]
    if not moods:
        print(f"No mood folders in {root.resolve()}. Create some, e.g. songs/sad/")
        return 1

    made = 0
    for mood_dir in moods:
        motif = MOTIFS.get(mood_dir.name, DEFAULT_MOTIF)
        print(f"{mood_dir.name}:")
        for n in range(1, args.count + 1):
            stem = f"_placeholder_{mood_dir.name}_{n}"
            wav_path = mood_dir / f"{stem}.wav"
            mp3_path = mood_dir / f"{stem}.mp3"

            if not args.force and (wav_path.exists() or mp3_path.exists()):
                print(f"  {stem}: exists, skipping")
                continue

            if args.tts and render_tts(wav_path, f"{mood_dir.name}. Take {n}."):
                print(f"  {mp3_path.name}: spoken")
            else:
                # Vary pitch slightly per file so "random pick" is audible.
                base, ratios, note_len = motif
                varied = (base * (1.0 + 0.08 * (n - 1)), ratios, note_len)
                render_tone(wav_path, args.seconds, varied)
                print(f"  {wav_path.name}: {args.seconds:.0f}s tone")
            made += 1

    print(f"\n{made} placeholder file(s) written.")
    print("Now: POST /api/music/rescan (or restart the container) to pick them up.")
    print("Replace them with real audio whenever you're ready -- .gitignore already")
    print("keeps audio out of the repo.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
