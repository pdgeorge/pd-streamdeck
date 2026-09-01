# pd-streamdeck

A tablet Stream Deck for the dabiverse stack. One service on the Pi serves the deck UI the tablet opens, the music page OBS loads as a browser source, and an HTTP API that anything else can drive.

```
  TABLET (browser, LAN)                    STREAMING PC (cachyowo)
        │                                    ┌──────────────────────┐
        │  http://192.168.20.14:8095         │ OBS 32.x             │
        │  ├── GET  /          deck UI       │  ├─ obs-websocket    │◄──┐
        │  ├── POST /api/...   actions       │  │   :4455           │   │
        │  └── WS   /ws/deck   live state    │  └─ browser source ──┼─┐ │
        ▼                                    └──────────────────────┘ │ │
  ┌──────────────────────────────────────────┐                        │ │
  │  deck_controller  (Pi, FastAPI, :8095)   │  ◄─── /player page ────┘ │
  │                                          │  ◄─── /ws/music ────────┐│
  │   deck.yaml ── buttons are config        │  ◄─── /audio/sad/*.mp3 ─┘│
  │   songs/{sad,hype,chill}/*.mp3           │                          │
  │   obs client ────────────────────────────┼──────────────────────────┘
  │   rabbit publisher ──► twitch_events / dabi_events
  └──────────────────────────────────────────┘
```

Pressing **Sad** posts `{"mood":"sad"}`, the service picks a random file from `songs/sad/` avoiding recent repeats, and tells the OBS page to crossfade into it. Audio plays inside OBS, so it lands in the stream mix with its own volume slider and no virtual audio cables.

## Why it's built this way

**Everything runs on the Pi, nothing new on the streaming PC.** The Pi reaches OBS directly over Tailscale, so there's no desktop-side agent to remember to launch. The OBS connection retries forever with backoff, because the streaming PC comes and goes and the Pi doesn't.

**Music plays through an OBS browser source**, the same pattern `dabi-voice` already uses. Give it its own OBS **audio track** so music is excluded from VOD and highlights while still going out live — retrofitting that later means re-cutting your audio setup.

**Buttons are `deck.yaml`, not code.** Adding a mood is a folder plus three lines. Scene *and* input names are checked against what OBS actually reports on every connect, so a stale name shows as a visibly broken button instead of one that fails the moment you press it mid-stream.

**State flows both ways.** The deck listens to OBS's own events, so switching scenes from the OBS window updates the tablet too. A deck that lies about state is worse than no deck.

## Setup

### 1. Enable obs-websocket (one time, on the streaming PC)

OBS → **Tools → WebSocket Server Settings → Enable WebSocket server**. Note the password. *(Done — confirmed listening on 4455, obs-websocket 5.7.4 under OBS 32.2.1.)*

Verify from the Pi:

```bash
ssh dabi 'timeout 3 bash -c "</dev/tcp/cachyowo/4455" && echo reachable'
```

### 2. Configure

```bash
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # DECK_TOKEN
```

Fill in `DECK_TOKEN` and `OBS_PASSWORD`. Leave `OBS_HOST=cachyowo` unless MagicDNS misbehaves inside Docker, in which case use `100.69.244.83`.

### 3. Placeholder music, so you can test before you have a library

```bash
python3 tools/seed_placeholder_songs.py            # distinct tone per mood
python3 tools/seed_placeholder_songs.py --tts      # or spoken mood names via edge-tts
```

Real audio drops into `songs/<mood>/` any time; `.gitignore` keeps audio out of the repo.

**[`songs/SOURCES.md`](songs/SOURCES.md)** has the researched list of stream-safe sources with specific track picks per mood, plus the two copyright traps worth knowing (game OSTs aren't free; a public-domain *composition* is not a public-domain *recording*).

### 4. Deploy on the Pi

```bash
ssh dabi
cd ~/projects && git clone <this repo> pd-streamdeck && cd pd-streamdeck
cp .env.example .env && $EDITOR .env
docker compose up -d --build
docker compose logs -f
```

Port **8095** was free at the time of writing (8000, 8001, 8080, 8090, 8787, 3306, 5672, 15672 and 11434 are taken).

### 5. Point OBS at the music page

Add a **Browser Source**:

- URL `http://192.168.20.14:8095/player/?token=YOUR_TOKEN`
- Size can be 1×1 — the page renders nothing. Add `&debug=1` to see a status panel while setting up.
- Audio monitoring: **Monitor and Output**, so you hear the music too.
- Uncheck "Shutdown source when not visible" so music keeps playing across scene changes.
- Put it on its own **audio track** (Advanced Audio Properties) to keep music out of your VODs.

### 6. Point the tablet at the deck

Open `http://192.168.20.14:8095/?token=YOUR_TOKEN` once. The token is saved to localStorage and stripped from the URL, so bookmark or "Add to Home Screen" afterwards — it launches fullscreen and landscape.

The transport bar across the top carries a **volume slider** (always visible, even with nothing playing, so you can set the level before it hits the stream) plus the current track and progress. `Quieter`/`Louder` on the Music page still step ±10% if you'd rather not aim.

On Android, set **Developer Options → Stay awake while charging**. It's far more reliable than the Wake Lock API the page also tries.

## The API

Every `/api/*` call takes `X-Deck-Token: <token>` (or `?token=`). `/healthz` is open.

| Method | Path | Body |
|---|---|---|
| GET | `/api/state` | — |
| GET | `/api/config` | — |
| POST | `/api/config/reload` | re-read `deck.yaml` without restarting |
| GET | `/api/obs/scenes` | — |
| POST | `/api/obs/scene` | `{"scene": "Just Chatting"}` |
| POST | `/api/obs/source` | `{"source": "X", "scene": null, "visible": null}` — omit `visible` to toggle |
| POST | `/api/obs/mute` | `{"input": "Microphone", "muted": null}` — omit `muted` to toggle |
| POST | `/api/obs/filter` | `{"source": "X", "filter": "Y", "enabled": null}` |
| POST | `/api/obs/stream` | `{"mode": "toggle"}` — `start`/`stop`/`toggle` |
| POST | `/api/obs/record` | `{"mode": "toggle"}` |
| GET | `/api/music/moods` | — |
| POST | `/api/music/play` | `{"mood": "sad"}` |
| POST | `/api/music/skip` | — |
| POST | `/api/music/stop` | — |
| POST | `/api/music/volume` | `{"level": 0.4}` (absolute, what the slider sends) or `{"delta": -0.1}` (what the buttons send) |
| POST | `/api/music/rescan` | after adding files |
| POST | `/api/bus/publish` | `{"type": "dabi.tts.ready", "exchange": "dabi_events", "payload": {...}}` |
| POST | `/api/action` | `{"action": "music.mood", "params": {"mood": "hype"}}` |

`/api/action` is what the buttons use — it takes a `deck.yaml` action object verbatim, so a new action type needs no UI change.

```bash
curl -X POST http://dabi:8095/api/music/play \
     -H "X-Deck-Token: $DECK_TOKEN" -H 'Content-Type: application/json' \
     -d '{"mood":"hype"}'
```

Websockets: `/ws/deck?token=` (state to the tablet), `/ws/music?token=` (commands to the OBS page).

## Actions available in `deck.yaml`

| Action | Required keys | Notes |
|---|---|---|
| `obs.scene` | `scene` | highlights when live |
| `obs.source_toggle` | `source` | `scene` optional, defaults to current |
| `obs.mute` | `input` | `indicator: mute` glows while muted; name validated at connect |
| `obs.filter` | `source`, `filter` | omit `enabled` to toggle |
| `obs.stream` | — | `mode`, `indicator: stream` |
| `obs.record` | — | `mode`, `indicator: record` |
| `music.mood` | `mood` | highlights while that mood plays |
| `music.skip` / `music.stop` | — | |
| `music.volume` | `level` or `delta` | |
| `bus.publish` | `type` | `exchange`, `payload` |

Presentation keys on any button: `label`, `icon` (emoji), `color` (`indigo`, `slate`, `amber`, `rose`, `sky`, `violet`, `emerald`), `indicator`, and `confirm: true` for a two-tap guard on things like ending the stream.

### `bus.publish` is the cheap integration point

Every exchange in the stack is fanout with consumers filtering on `message.type`. A deck button can therefore drop an event that an existing service already handles, with **no changes to that service** — make Dabi speak, fire the `!other` billboard, or kick off the Chat-on-Trial flow from `twitch-broadcaster/PLANS.md`.

## Testing

```bash
python3 -m venv .venv && .venv/bin/pip install -r deck_controller/requirements.txt
python3 tools/seed_placeholder_songs.py
cd deck_controller && DECK_TOKEN=dev DECK_CONFIG=../deck.yaml MUSIC_LIBRARY=../songs \
  ../.venv/bin/python app.py
```

OBS and RabbitMQ being unreachable is fine — they retry in the background and every music feature works without them.

## Gotchas

- **obs-websocket is disabled by default.** Nothing works until step 1. The deck shows `OBS` red and OBS actions return `503` with a clear reason.
- **The music library is not in git.** `.gitignore` drops audio files but keeps the mood folders. Back up `songs/` separately, or sync it to the Pi outside git.
- **A mood folder with one file will repeat it**, because there's nothing else to pick. The no-repeat window caps itself at one less than the folder size.
- **Adding files needs a rescan** — `POST /api/music/rescan`, or restart the container. The library is scanned at startup, not per request.
- **`Mic/Aux` and `Desktop Audio` are dead Windows leftovers** in your OBS config. They're `wasapi_*` source kinds, which Linux OBS can't drive — pressing one returns *"The specified input does not support audio."* The live pulse inputs are `Microphone`, `Discord`, `Default` (desktop audio) and `VR Microphone`; `deck.yaml` uses those. `GET /api/state` lists every audio-capable input in `obs.muted`.
- **Some scenes carry no microphone.** Audio sources are per-scene in OBS, so switching scene changes what's audible. As audited: `Cam` and `RandomBS` have **no audio sources at all** (switching to either kills mic, desktop and Discord simultaneously); `Backpack RTSP`, `Parenting` and `FullscreenVid` carry no mic. The Scenes page deliberately covers only the eight scenes that are stream-ready — `Cam` and `RandomBS` are left off on purpose. Re-audit after editing scenes:

  ```bash
  curl -s -H "X-Deck-Token: $DECK_TOKEN" http://dabi:8095/api/state | jq '.state.obs.muted'
  ```

- **The scene JSON on disk goes stale.** OBS writes it on exit or collection switch, so a file read mid-session can name scenes that no longer match. The live collection is `Pd` (profile `Cyra`). Trust `GET /api/obs/scenes`, not the file — this is why buttons validate at connect time.
- **Music licensing.** Twitch mutes VODs and issues strikes for copyrighted audio. The separate-audio-track setup protects VODs but not the live stream — point `songs/` at something like Streambeats or Pretzel.
- **The Pi is on WiFi** (`wlan0`, 192.168.20.14). Fine for audio (~40 KB/s), but it's the reason to keep the tablet on the same LAN rather than routing through Tailscale where you can.
