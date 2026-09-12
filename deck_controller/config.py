"""
deck.yaml loading and validation.

The button layout is data, not code. This module turns it into a normalised
structure the API hands to the tablet, and knows how to re-check it against
OBS's real scene list once we're connected -- so a renamed scene shows up as
a visibly broken button rather than a button that quietly does nothing.
"""

import logging
import os
from pathlib import Path
from typing import Any, Optional

import yaml

LOGGER = logging.getLogger("deck.config")

# Action types the controller knows how to execute. A button naming anything
# else is rejected at load time rather than failing on first press.
KNOWN_ACTIONS = {
    "obs.scene",
    "obs.source_toggle",
    "obs.mute",
    "obs.filter",
    "obs.stream",
    "obs.record",
    "music.mood",
    "music.rate",
    "music.stop",
    "music.skip",
    "music.volume",
    "bus.publish",
    "noop",
}

# Required keys per action, checked at load.
REQUIRED_KEYS = {
    "obs.scene": ("scene",),
    "obs.source_toggle": ("source",),
    "obs.mute": ("input",),
    "obs.filter": ("source", "filter"),
    "music.mood": ("mood",),
    # Required so a rate button with no delta fails at load rather than
    # quietly defaulting to +1 the first time you press it mid-stream.
    "music.rate": ("delta",),
    "bus.publish": ("type",),
}

DEFAULT_MUSIC = {
    "no_repeat_window": 3,
    "fade_seconds": 2.0,
    "default_volume": 0.6,
    "loop_mood": True,
}


class ConfigError(Exception):
    """deck.yaml is malformed badly enough that we shouldn't start."""


class DeckConfig:
    def __init__(self, path: str):
        self.path = Path(path)
        self.music: dict = dict(DEFAULT_MUSIC)
        self.pages: list[dict] = []
        self.load()

    # -- loading ------------------------------------------------------------

    def load(self) -> None:
        if not self.path.is_file():
            raise ConfigError(f"deck config not found: {self.path}")

        with open(self.path) as f:
            raw = yaml.safe_load(f) or {}

        if not isinstance(raw, dict):
            raise ConfigError("deck.yaml must be a mapping at the top level")

        music = dict(DEFAULT_MUSIC)
        music.update(raw.get("music") or {})
        music["default_volume"] = _clamp(float(music["default_volume"]), 0.0, 1.0)
        music["fade_seconds"] = max(0.0, float(music["fade_seconds"]))
        music["no_repeat_window"] = max(0, int(music["no_repeat_window"]))
        music["loop_mood"] = bool(music["loop_mood"])
        self.music = music

        pages_raw = raw.get("pages") or []
        if not isinstance(pages_raw, list) or not pages_raw:
            raise ConfigError("deck.yaml needs at least one entry under 'pages'")

        pages: list[dict] = []
        for p_index, page in enumerate(pages_raw):
            if not isinstance(page, dict):
                raise ConfigError(f"page #{p_index} is not a mapping")
            name = str(page.get("name") or f"Page {p_index + 1}")
            columns = int(page.get("columns") or 4)
            buttons: list[dict] = []
            for b_index, button in enumerate(page.get("buttons") or []):
                buttons.append(self._normalise_button(button, name, b_index))
            pages.append({"name": name, "columns": columns, "buttons": buttons})

        self.pages = pages
        LOGGER.info(
            "Loaded %s: %d page(s), %d button(s)",
            self.path,
            len(self.pages),
            sum(len(p["buttons"]) for p in self.pages),
        )

    def _normalise_button(self, button: Any, page_name: str, index: int) -> dict:
        where = f"{page_name}[{index}]"
        if not isinstance(button, dict):
            raise ConfigError(f"{where}: button is not a mapping")

        action = str(button.get("action") or "noop")
        if action not in KNOWN_ACTIONS:
            raise ConfigError(
                f"{where}: unknown action {action!r}. "
                f"Known: {', '.join(sorted(KNOWN_ACTIONS))}"
            )

        for key in REQUIRED_KEYS.get(action, ()):
            if not button.get(key):
                raise ConfigError(f"{where}: action {action!r} requires '{key}'")

        # Everything that isn't presentation is action payload, passed
        # straight to the dispatcher. New action params need no code here.
        presentation = {"label", "icon", "color", "indicator", "confirm"}
        params = {k: v for k, v in button.items() if k not in presentation}

        return {
            "id": f"{page_name}:{index}",
            "label": str(button.get("label") or action),
            "icon": str(button.get("icon") or ""),
            "color": str(button.get("color") or "slate"),
            "indicator": button.get("indicator"),
            "confirm": bool(button.get("confirm", False)),
            "action": action,
            "params": params,
            # Filled in by validate_against_obs() once we know the real
            # scene list. None means "not checked yet".
            "problem": None,
        }

    # -- validation against live OBS ---------------------------------------

    def validate_against_obs(
        self,
        scenes: Optional[list[str]],
        audio_inputs: Optional[list[str]] = None,
    ) -> None:
        """Flag buttons that reference things OBS doesn't have.

        Called on every OBS (re)connect and whenever the scene list changes.
        Passing None (OBS offline) clears the flags -- we can't know.

        Inputs are checked as well as scenes, because a stale input name is
        the sneakier failure: 'Mic/Aux' survives in an OBS config long after
        the platform changed, looks perfectly valid in the UI, and only
        fails at the moment you press it mid-stream.
        """
        known_inputs = set(audio_inputs) if audio_inputs is not None else None

        for page in self.pages:
            for button in page["buttons"]:
                if scenes is None:
                    button["problem"] = None
                    continue

                problem = None
                params = button["params"]

                scene = params.get("scene")
                if scene and scene not in scenes:
                    problem = f"OBS has no scene named {scene!r}"

                if problem is None and known_inputs is not None:
                    audio_input = params.get("input")
                    if audio_input and audio_input not in known_inputs:
                        problem = (
                            f"OBS has no audio-capable input named {audio_input!r}"
                        )

                button["problem"] = problem

    # -- serialisation ------------------------------------------------------

    def as_dict(self) -> dict:
        return {"music": self.music, "pages": self.pages}


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def load_config() -> DeckConfig:
    return DeckConfig(os.getenv("DECK_CONFIG", "/config/deck.yaml"))
