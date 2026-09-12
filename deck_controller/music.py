"""
Mood-based music: library scanning, random selection, and the authoritative
playback state.

Actual audio playback happens in the browser source inside OBS -- this module
only decides *what* should be playing and tells the page. Keeping the state
here (rather than in the page) means the tablet still knows what's playing
after the browser source reloads, and volume survives an OBS restart.
"""

import asyncio
import json
import logging
import random
from pathlib import Path
from typing import Optional
from urllib.parse import quote

LOGGER = logging.getLogger("deck.music")

AUDIO_EXTENSIONS = {".mp3", ".ogg", ".wav", ".m4a", ".flac", ".opus", ".aac"}

# A rating of +1 makes a track twice as likely to come up, -1 half as likely.
# Clamped so one enthusiastic evening can't turn a mood into a single song on
# repeat, and so a disliked track goes rare rather than silently disappearing
# -- if you want it gone, delete the file.
MIN_SCORE = -3
MAX_SCORE = 3


class MusicError(Exception):
    """Asked for a mood that doesn't exist, or an empty one."""


class TrackRatings:
    """Per-track scores, persisted so a rating survives a container restart.

    Kept outside the library rather than next to the audio because `songs/`
    is bind-mounted read-only -- the container cannot write there even though
    that would be the tidier home. If the state directory turns out to be
    unwritable we keep the scores in memory and say so once, because losing
    ratings is annoying and refusing to play music over it would be worse.
    """

    def __init__(self, path: str):
        self.path = Path(path)
        self.scores: dict[str, int] = {}
        self._warned = False
        self.load()

    def load(self) -> None:
        if not self.path.is_file():
            LOGGER.info("No ratings file at %s yet; starting empty", self.path)
            return
        try:
            raw = json.loads(self.path.read_text())
            self.scores = {
                str(k): _clamp_score(int(v)) for k, v in (raw or {}).items()
            }
            LOGGER.info("Loaded %d track rating(s) from %s", len(self.scores), self.path)
        except (OSError, ValueError, TypeError) as exc:
            LOGGER.warning("Could not read ratings from %s: %s", self.path, exc)

    def save(self) -> None:
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            # Write-and-rename so a crash mid-write can't leave a truncated
            # file that fails to parse on the next start.
            temp = self.path.with_suffix(".tmp")
            temp.write_text(json.dumps(self.scores, indent=2, sort_keys=True))
            temp.replace(self.path)
        except OSError as exc:
            if not self._warned:
                LOGGER.warning(
                    "Ratings are in memory only -- cannot write %s: %s. "
                    "Add a writable volume for DECK_STATE_DIR to keep them.",
                    self.path, exc,
                )
                self._warned = True

    def get(self, key: str) -> int:
        return self.scores.get(key, 0)

    def adjust(self, key: str, delta: int) -> int:
        score = _clamp_score(self.get(key) + int(delta))
        if score:
            self.scores[key] = score
        else:
            # Don't persist zeroes; an unrated track and a track rated back
            # to neutral are the same thing, and this keeps the file small.
            self.scores.pop(key, None)
        self.save()
        return score

    def weight(self, key: str) -> float:
        return 2.0 ** self.get(key)


def _clamp_score(score: int) -> int:
    return max(MIN_SCORE, min(MAX_SCORE, score))


class MusicLibrary:
    """One subdirectory of the library root = one mood."""

    def __init__(
        self,
        root: str,
        no_repeat_window: int = 3,
        ratings: Optional[TrackRatings] = None,
    ):
        self.root = Path(root)
        self.no_repeat_window = no_repeat_window
        self.ratings = ratings or TrackRatings("/data/ratings.json")
        self.moods: dict[str, list[Path]] = {}
        self._recent: dict[str, list[Path]] = {}
        self.scan()

    def scan(self) -> dict[str, int]:
        moods: dict[str, list[Path]] = {}
        if not self.root.is_dir():
            LOGGER.warning("Music library root %s does not exist", self.root)
            self.moods = {}
            return {}

        for entry in sorted(self.root.iterdir()):
            if not entry.is_dir() or entry.name.startswith("."):
                continue
            tracks = sorted(
                p for p in entry.iterdir()
                if p.is_file() and p.suffix.lower() in AUDIO_EXTENSIONS
            )
            moods[entry.name] = tracks

        self.moods = moods
        counts = {name: len(tracks) for name, tracks in moods.items()}
        LOGGER.info("Music library: %s", counts or "empty")
        return counts

    def mood_names(self) -> list[str]:
        return sorted(self.moods)

    def counts(self) -> dict[str, int]:
        return {name: len(tracks) for name, tracks in self.moods.items()}

    def key_for(self, mood: str, name: str) -> str:
        """Identity of a track for rating purposes: mood plus filename.

        Renaming a file loses its rating. That's the honest trade for not
        keeping a database of file hashes, and renames are rare.
        """
        return f"{mood}/{name}"

    def listing(self) -> dict[str, list[dict]]:
        """Every track with its score, for the tablet's picker."""
        return {
            mood: [
                {"name": t.name, "score": self.ratings.get(self.key_for(mood, t.name))}
                for t in tracks
            ]
            for mood, tracks in self.moods.items()
        }

    def find(self, mood: str, name: str) -> Path:
        """Look up one track by filename within a mood.

        Like pick(), this resolves against the scanned list and never joins
        caller input onto a path, so a crafted name can't reach outside the
        library.
        """
        tracks = self._tracks_for(mood)
        for track in tracks:
            if track.name == name:
                return track
        raise MusicError(f"Mood {mood!r} has no track named {name!r}")

    def _tracks_for(self, mood: str) -> list[Path]:
        tracks = self.moods.get(mood)
        if tracks is None:
            known = ", ".join(self.mood_names()) or "none"
            raise MusicError(f"Unknown mood {mood!r}. Available: {known}")
        if not tracks:
            raise MusicError(f"Mood {mood!r} has no audio files in {self.root / mood}")
        return tracks

    def pick(self, mood: str) -> Path:
        """Weighted-random track from a mood, avoiding the last few picks.

        Mood names are looked up in the scanned dict and never used to build
        a filesystem path, so a hostile mood name can't escape the library.
        """
        tracks = self._tracks_for(mood)

        # Cap the window at one less than the folder size, so there is always
        # at least one legal candidate. Without this, a mood with two files
        # and a window of three excludes everything, falls back to the full
        # list, and cheerfully plays the same track twice in a row -- which
        # is the exact thing the window exists to prevent.
        window = min(self.no_repeat_window, max(0, len(tracks) - 1))
        recent = self._recent.setdefault(mood, [])
        excluded = set(recent[-window:]) if window else set()

        candidates = [t for t in tracks if t not in excluded]
        # Ratings bias the draw without ever excluding anything: a track at
        # -3 still has a 1-in-8 share against a neutral one, so the rotation
        # shrinks towards what you like instead of collapsing onto it.
        weights = [self.ratings.weight(self.key_for(mood, t.name)) for t in candidates]
        chosen = random.choices(candidates, weights=weights, k=1)[0]

        recent.append(chosen)
        self._recent[mood] = recent[-window:] if window else []
        return chosen

    def pick_specific(self, mood: str, name: str) -> Path:
        """A named track, recorded in the no-repeat history like any draw.

        Without the history update, choosing a song by hand and then letting
        the mood roll on could pick that same song again immediately.
        """
        tracks = self._tracks_for(mood)
        chosen = self.find(mood, name)

        window = min(self.no_repeat_window, max(0, len(tracks) - 1))
        recent = self._recent.setdefault(mood, [])
        recent.append(chosen)
        self._recent[mood] = recent[-window:] if window else []
        return chosen

    def url_for(self, path: Path) -> str:
        """Public URL for a track, as served by the /audio static mount."""
        relative = path.relative_to(self.root)
        return "/audio/" + "/".join(quote(part) for part in relative.parts)


class MusicPlayer:
    """Server-side playback state plus the command channel to the OBS page."""

    def __init__(self, library: MusicLibrary, settings: dict, broadcast_state):
        self.library = library
        self.fade = float(settings.get("fade_seconds", 2.0))
        self.loop_mood = bool(settings.get("loop_mood", True))
        self.volume = float(settings.get("default_volume", 0.6))

        self._broadcast_state = broadcast_state
        self._clients: set = set()          # connected player pages
        self._lock = asyncio.Lock()

        self.playing = False
        self.mood: Optional[str] = None
        self.track: Optional[str] = None
        self.position = 0.0
        self.duration = 0.0

    # -- player page plumbing ----------------------------------------------

    def add_client(self, ws) -> None:
        self._clients.add(ws)

    def discard_client(self, ws) -> None:
        self._clients.discard(ws)

    @property
    def page_connected(self) -> bool:
        return bool(self._clients)

    async def _send(self, message: dict) -> None:
        dead = []
        for ws in list(self._clients):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop and let it reconnect
                dead.append(ws)
        for ws in dead:
            self._clients.discard(ws)

    async def sync_client(self, ws) -> None:
        """Bring a freshly connected page in line with server state."""
        await ws.send_json({
            "action": "sync",
            "volume": self.volume,
            "fade": self.fade,
            "playing": self.playing,
        })

    # -- commands -----------------------------------------------------------

    async def play_mood(self, mood: str, track: Optional[str] = None) -> dict:
        """Play a mood. Naming a track plays that one instead of drawing.

        A directly chosen track still joins the no-repeat history, so asking
        for a song by name doesn't let the next random draw immediately
        repeat it.
        """
        async with self._lock:
            if track:
                path = self.library.pick_specific(mood, track)
            else:
                path = self.library.pick(mood)
            self.mood = mood
            self.track = path.name
            self.playing = True
            self.position = 0.0
            self.duration = 0.0
            await self._send({
                "action": "play",
                "url": self.library.url_for(path),
                "track": path.name,
                "mood": mood,
                "fade": self.fade,
                "volume": self.volume,
            })
        await self._broadcast_state()
        return {"mood": mood, "track": path.name, "score": self.score}

    async def skip(self) -> dict:
        if not self.mood:
            raise MusicError("Nothing is playing, so there's nothing to skip")
        return await self.play_mood(self.mood)

    async def rate(self, delta: int) -> dict:
        """Nudge the current track's odds of coming up again.

        Rates what's playing rather than taking a track name, because the
        button is pressed in reaction to what you're hearing -- and that
        keeps the deck from needing to know anything about the library.
        """
        if not (self.mood and self.track):
            raise MusicError("Nothing is playing, so there's nothing to rate")

        key = self.library.key_for(self.mood, self.track)
        score = self.library.ratings.adjust(key, delta)
        LOGGER.info("Rated %s -> %+d", key, score)
        await self._broadcast_state()
        return {"mood": self.mood, "track": self.track, "score": score}

    @property
    def score(self) -> int:
        """Rating of whatever is playing; 0 when nothing is."""
        if not (self.mood and self.track):
            return 0
        return self.library.ratings.get(self.library.key_for(self.mood, self.track))

    async def stop(self) -> dict:
        async with self._lock:
            self.playing = False
            self.mood = None
            self.track = None
            self.position = 0.0
            self.duration = 0.0
            await self._send({"action": "stop", "fade": self.fade})
        await self._broadcast_state()
        return {"stopped": True}

    async def set_volume(
        self, level: Optional[float] = None, delta: Optional[float] = None
    ) -> dict:
        if level is None and delta is None:
            raise MusicError("Pass either 'level' or 'delta'")
        target = self.volume + delta if level is None else level
        self.volume = max(0.0, min(1.0, float(target)))
        await self._send({"action": "volume", "volume": self.volume, "fade": 0.25})
        await self._broadcast_state()
        return {"volume": self.volume}

    # -- reports from the player page --------------------------------------

    async def on_page_event(self, message: dict) -> None:
        event = message.get("event")

        if event == "progress":
            self.position = float(message.get("position") or 0.0)
            self.duration = float(message.get("duration") or 0.0)
            # Progress is noisy; the deck picks it up on the next state push
            # rather than getting a broadcast per second.
            return

        if event == "ended":
            if self.loop_mood and self.mood:
                LOGGER.info("Track ended, continuing mood %r", self.mood)
                try:
                    await self.play_mood(self.mood)
                    return
                except MusicError as exc:
                    LOGGER.warning("Could not continue mood: %s", exc)
            self.playing = False
            self.track = None
            self.mood = None

        elif event == "error":
            LOGGER.error("Player page error: %s", message.get("message"))
            self.playing = False

        elif event == "playing":
            self.playing = True
            self.duration = float(message.get("duration") or 0.0)

        await self._broadcast_state()

    # -- snapshot -----------------------------------------------------------

    def snapshot(self) -> dict:
        return {
            "playing": self.playing,
            "mood": self.mood,
            "track": self.track,
            "score": self.score,
            "volume": round(self.volume, 3),
            "position": round(self.position, 1),
            "duration": round(self.duration, 1),
            "page_connected": self.page_connected,
            "moods": self.library.counts(),
        }
