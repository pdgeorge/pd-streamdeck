"""
pd-streamdeck controller.

Runs on the Pi. Serves three things on one port:

  /            the deck UI          (the tablet opens this)
  /player      the music page       (OBS browser source -- audio plays here)
  /api/*       the HTTP API         (the tablet, and anything else you build)

plus two websockets: /ws/deck pushes live state to the tablet, /ws/music
carries playback commands to the OBS page.

It holds one outbound connection to obs-websocket on the streaming PC, and
one to the existing RabbitMQ broker.
"""

import logging
import os
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import uvicorn
from dotenv import load_dotenv
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from bus import Bus, BusError, build_bus
from config import ConfigError, DeckConfig, load_config
from music import MusicError, MusicLibrary, MusicPlayer, TrackRatings
from obs_client import ObsClient, ObsError

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
LOGGER = logging.getLogger("deck")

BASE_DIR = Path(__file__).resolve().parent


def _find_static(name: str) -> Path:
    """In Docker the front-end sits next to app.py; in the repo it's one
    level up. Same trick dabi-voice uses to locate shared/."""
    for candidate in (BASE_DIR / name, BASE_DIR.parent / name):
        if candidate.is_dir():
            return candidate
    return BASE_DIR / name


DECK_DIR = _find_static("deck")
PLAYER_DIR = _find_static("player")

HTTP_PORT = int(os.getenv("DECK_HTTP_PORT", "8095"))
DECK_TOKEN = os.getenv("DECK_TOKEN", "").strip()
MUSIC_LIBRARY = os.getenv("MUSIC_LIBRARY", "/songs")
# Somewhere writable, unlike the read-only songs/ mount. Holds track ratings.
DECK_STATE_DIR = os.getenv("DECK_STATE_DIR", "/data")

OBS_HOST = os.getenv("OBS_HOST", "localhost")
OBS_PORT = int(os.getenv("OBS_PORT", "4455"))
OBS_PASSWORD = os.getenv("OBS_PASSWORD", "")


# ---------------------------------------------------------------------------
# Live state fan-out to the tablet
# ---------------------------------------------------------------------------

class Deck:
    """Holds the pieces and pushes a combined state snapshot to the tablet."""

    def __init__(self):
        self.config: DeckConfig = load_config()
        self.deck_clients: set[WebSocket] = set()
        self.library = MusicLibrary(
            MUSIC_LIBRARY,
            self.config.music["no_repeat_window"],
            TrackRatings(str(Path(DECK_STATE_DIR) / "ratings.json")),
        )
        self.player = MusicPlayer(self.library, self.config.music, self.broadcast_state)
        self.obs = ObsClient(OBS_HOST, OBS_PORT, OBS_PASSWORD, self.on_obs_change)
        self.bus: Bus = build_bus()

    async def on_obs_change(self) -> None:
        # Re-check button scene references whenever OBS's view of the world
        # changes, so a renamed scene shows as broken on the tablet.
        self.config.validate_against_obs(
            self.obs.scenes if self.obs.connected else None,
            list(self.obs.muted) if self.obs.connected else None,
        )
        await self.broadcast_state()

    def snapshot(self) -> dict:
        return {
            "obs": self.obs.snapshot(),
            "music": self.player.snapshot(),
            "bus": self.bus.snapshot(),
        }

    async def broadcast_state(self) -> None:
        message = {"type": "state", "state": self.snapshot()}
        dead = []
        for ws in list(self.deck_clients):
            try:
                await ws.send_json(message)
            except Exception:  # noqa: BLE001 - drop and let it reconnect
                dead.append(ws)
        for ws in dead:
            self.deck_clients.discard(ws)


# Populated by lifespan() before any request is served. Module-level so
# every route reaches the same instance without a dependency dance.
deck: "Deck" = None  # type: ignore[assignment]


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def check_token(request_token: Optional[str]) -> bool:
    """Websocket path: the token arrives as a query param."""
    return not DECK_TOKEN or request_token == DECK_TOKEN


async def guard(
    x_deck_token: Optional[str] = Header(default=None),
    token: Optional[str] = Query(default=None),
) -> None:
    """HTTP path: header preferred, query param accepted so a request is
    still easy to fire from curl or a browser address bar."""
    if not DECK_TOKEN:
        return
    if x_deck_token == DECK_TOKEN or token == DECK_TOKEN:
        return
    raise HTTPException(status_code=401, detail="Bad or missing deck token")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    global deck
    deck = Deck()
    deck.obs.start()
    deck.bus.start()
    LOGGER.info(
        "Deck up on :%s -- OBS target %s:%s, auth %s",
        HTTP_PORT, OBS_HOST, OBS_PORT, "on" if DECK_TOKEN else "OFF",
    )
    if not DECK_TOKEN:
        LOGGER.warning("DECK_TOKEN is empty: the API is open to anyone on the network")
    try:
        yield
    finally:
        await deck.obs.stop()
        await deck.bus.stop()


app = FastAPI(title="pd-streamdeck", lifespan=lifespan)


@app.exception_handler(ObsError)
async def _obs_error(_request, exc: ObsError):
    return JSONResponse(status_code=503, content={"ok": False, "error": str(exc)})


@app.exception_handler(MusicError)
async def _music_error(_request, exc: MusicError):
    return JSONResponse(status_code=400, content={"ok": False, "error": str(exc)})


@app.exception_handler(BusError)
async def _bus_error(_request, exc: BusError):
    return JSONResponse(status_code=503, content={"ok": False, "error": str(exc)})


# -- read-only ---------------------------------------------------------------

@app.get("/healthz")
async def healthz():
    return {"ok": True, "obs": deck.obs.connected, "bus": deck.bus.connected}


@app.get("/api/state", dependencies=[Depends(guard)])
async def get_state():
    return {"ok": True, "state": deck.snapshot()}


@app.get("/api/config", dependencies=[Depends(guard)])
async def get_config():
    return {"ok": True, "config": deck.config.as_dict()}


@app.post("/api/config/reload", dependencies=[Depends(guard)])
async def reload_config():
    """Re-read deck.yaml without restarting the container."""
    try:
        deck.config.load()
    except ConfigError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    deck.config.validate_against_obs(
        deck.obs.scenes if deck.obs.connected else None,
        list(deck.obs.muted) if deck.obs.connected else None,
    )
    await deck.broadcast_state()
    return {"ok": True, "config": deck.config.as_dict()}


@app.get("/api/obs/scenes", dependencies=[Depends(guard)])
async def get_scenes():
    return {"ok": True, "scenes": deck.obs.scenes, "current": deck.obs.current_scene}


@app.get("/api/music/moods", dependencies=[Depends(guard)])
async def get_moods():
    return {"ok": True, "moods": deck.library.counts()}


# -- OBS ---------------------------------------------------------------------

class SceneRequest(BaseModel):
    scene: str


class SourceRequest(BaseModel):
    source: str
    scene: Optional[str] = None
    visible: Optional[bool] = None


class MuteRequest(BaseModel):
    input: str
    muted: Optional[bool] = None


class FilterRequest(BaseModel):
    source: str
    filter: str
    enabled: Optional[bool] = None


class OutputRequest(BaseModel):
    mode: str = "toggle"


@app.post("/api/obs/scene", dependencies=[Depends(guard)])
async def post_scene(req: SceneRequest):
    return {"ok": True, "result": await deck.obs.set_scene(req.scene)}


@app.post("/api/obs/source", dependencies=[Depends(guard)])
async def post_source(req: SourceRequest):
    result = await deck.obs.toggle_source(req.source, req.scene, req.visible)
    return {"ok": True, "result": result}


@app.post("/api/obs/mute", dependencies=[Depends(guard)])
async def post_mute(req: MuteRequest):
    result = await deck.obs.set_mute(req.input, req.muted)
    await deck.broadcast_state()
    return {"ok": True, "result": result}


@app.post("/api/obs/filter", dependencies=[Depends(guard)])
async def post_filter(req: FilterRequest):
    result = await deck.obs.set_filter(req.source, req.filter, req.enabled)
    return {"ok": True, "result": result}


@app.post("/api/obs/stream", dependencies=[Depends(guard)])
async def post_stream(req: OutputRequest):
    return {"ok": True, "result": await deck.obs.output("stream", req.mode)}


@app.post("/api/obs/record", dependencies=[Depends(guard)])
async def post_record(req: OutputRequest):
    return {"ok": True, "result": await deck.obs.output("record", req.mode)}


# -- music -------------------------------------------------------------------

class PlayRequest(BaseModel):
    mood: str
    # Naming a track plays that one; leaving it out draws from the mood.
    track: Optional[str] = None


class RateRequest(BaseModel):
    delta: int


class VolumeRequest(BaseModel):
    level: Optional[float] = None
    delta: Optional[float] = None


@app.post("/api/music/play", dependencies=[Depends(guard)])
async def post_play(req: PlayRequest):
    return {"ok": True, "result": await deck.player.play_mood(req.mood, req.track)}


@app.get("/api/music/tracks", dependencies=[Depends(guard)])
async def get_tracks():
    """Every track with its rating, for the tablet's track picker."""
    return {"ok": True, "tracks": deck.library.listing()}


@app.post("/api/music/rate", dependencies=[Depends(guard)])
async def post_rate(req: RateRequest):
    return {"ok": True, "result": await deck.player.rate(req.delta)}


@app.post("/api/music/skip", dependencies=[Depends(guard)])
async def post_skip():
    return {"ok": True, "result": await deck.player.skip()}


@app.post("/api/music/stop", dependencies=[Depends(guard)])
async def post_stop():
    return {"ok": True, "result": await deck.player.stop()}


@app.post("/api/music/volume", dependencies=[Depends(guard)])
async def post_volume(req: VolumeRequest):
    result = await deck.player.set_volume(req.level, req.delta)
    return {"ok": True, "result": result}


@app.post("/api/music/rescan", dependencies=[Depends(guard)])
async def post_rescan():
    counts = deck.library.scan()
    await deck.broadcast_state()
    return {"ok": True, "moods": counts}


# -- bus ---------------------------------------------------------------------

class PublishRequest(BaseModel):
    type: str
    exchange: Optional[str] = None
    payload: Optional[dict] = None


@app.post("/api/bus/publish", dependencies=[Depends(guard)])
async def post_publish(req: PublishRequest):
    exchange = req.exchange or os.getenv("TWITCH_EXCHANGE", "twitch_events")
    result = await deck.bus.publish(exchange, req.type, req.payload)
    return {"ok": True, "result": result}


# -- the generic dispatcher the buttons use ---------------------------------

class ActionRequest(BaseModel):
    action: str
    params: dict = {}


@app.post("/api/action", dependencies=[Depends(guard)])
async def post_action(req: ActionRequest):
    """One endpoint the tablet posts a button's action object to.

    Keeping dispatch here rather than in the UI means a new action type is a
    change in exactly two places (deck.yaml and this function), never in the
    tablet code.
    """
    action, p = req.action, req.params

    if action == "obs.scene":
        result = await deck.obs.set_scene(p["scene"])
    elif action == "obs.source_toggle":
        result = await deck.obs.toggle_source(
            p["source"], p.get("scene"), p.get("visible")
        )
    elif action == "obs.mute":
        result = await deck.obs.set_mute(p["input"], p.get("muted"))
        await deck.broadcast_state()
    elif action == "obs.filter":
        result = await deck.obs.set_filter(
            p["source"], p["filter"], p.get("enabled")
        )
    elif action == "obs.stream":
        result = await deck.obs.output("stream", p.get("mode", "toggle"))
    elif action == "obs.record":
        result = await deck.obs.output("record", p.get("mode", "toggle"))
    elif action == "music.mood":
        result = await deck.player.play_mood(p["mood"], p.get("track"))
    elif action == "music.rate":
        result = await deck.player.rate(p.get("delta", 1))
    elif action == "music.skip":
        result = await deck.player.skip()
    elif action == "music.stop":
        result = await deck.player.stop()
    elif action == "music.volume":
        result = await deck.player.set_volume(p.get("level"), p.get("delta"))
    elif action == "bus.publish":
        result = await deck.bus.publish(
            p.get("exchange") or os.getenv("TWITCH_EXCHANGE", "twitch_events"),
            p["type"],
            p.get("payload"),
        )
    elif action == "noop":
        result = {}
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action {action!r}")

    return {"ok": True, "result": result}


# -- websockets --------------------------------------------------------------

@app.websocket("/ws/deck")
async def ws_deck(ws: WebSocket, token: Optional[str] = Query(default=None)):
    if not check_token(token):
        await ws.close(code=4401)
        return

    await ws.accept()
    deck.deck_clients.add(ws)
    try:
        await ws.send_json({
            "type": "hello",
            "config": deck.config.as_dict(),
            "state": deck.snapshot(),
        })
        while True:
            # The tablet only sends keepalive pings; actions go over HTTP so
            # they get a real status code back.
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("Deck socket closed: %s", exc)
    finally:
        deck.deck_clients.discard(ws)


@app.websocket("/ws/music")
async def ws_music(ws: WebSocket, token: Optional[str] = Query(default=None)):
    if not check_token(token):
        await ws.close(code=4401)
        return

    await ws.accept()
    deck.player.add_client(ws)
    LOGGER.info("Music page connected")
    await deck.broadcast_state()
    try:
        await deck.player.sync_client(ws)
        while True:
            message = await ws.receive_json()
            await deck.player.on_page_event(message)
    except WebSocketDisconnect:
        pass
    except Exception as exc:  # noqa: BLE001
        LOGGER.info("Music socket closed: %s", exc)
    finally:
        deck.player.discard_client(ws)
        LOGGER.info("Music page disconnected")
        await deck.broadcast_state()


# -- static (must be mounted last: "/" swallows everything) ------------------

@app.get("/player", include_in_schema=False)
async def player_no_slash(request: Request):
    """Forgive the missing trailing slash.

    Without this, an OBS browser source pointed at /player?token=... just
    404s: a blank source, no audio, and no error anywhere the streamer would
    look. Preserves the query string so the token survives the redirect.
    """
    query = request.url.query
    return RedirectResponse(url="/player/" + (f"?{query}" if query else ""))


Path(MUSIC_LIBRARY).mkdir(parents=True, exist_ok=True)
app.mount("/audio", StaticFiles(directory=MUSIC_LIBRARY), name="audio")
app.mount("/player", StaticFiles(directory=str(PLAYER_DIR), html=True), name="player")
app.mount("/", StaticFiles(directory=str(DECK_DIR), html=True), name="deck")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
