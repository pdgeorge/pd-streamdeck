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
  │   songs/{sad,hype,chill,tension}/*.mp3   │                          │
  │   obs client ────────────────────────────┼──────────────────────────┘
  │   rabbit publisher ──► twitch_events / dabi_events
  └──────────────────────────────────────────┘
```

Pressing **Sad** posts `{"mood":"sad"}`, the service picks a random file from `songs/sad/` avoiding recent repeats, and tells the OBS page to crossfade into it. Audio plays inside OBS, so it lands in the stream mix with its own volume slider and no virtual audio cables.

## Quick reference

Everything is on **one port, 8095**, at three paths. `YOUR_TOKEN` is `DECK_TOKEN` from `.env`.

| What | URL |
|---|---|
| Tablet deck | `http://192.168.20.14:8095/?token=YOUR_TOKEN` |
| OBS browser source | `http://192.168.20.14:8095/player/?token=YOUR_TOKEN` |
| Same, with a status panel | add `&debug=1` |
| Health (no token needed) | `http://192.168.20.14:8095/healthz` |

The Pi is `192.168.20.14` on the LAN, or `dabi` over Tailscale. Deployed at `~/projects/pd-streamdeck`, container name `pd-streamdeck`.

## Why it's built this way

**Everything runs on the Pi, nothing new on the streaming PC.** The Pi reaches OBS directly over Tailscale, so there's no desktop-side agent to remember to launch. The OBS connection retries forever with backoff, because the streaming PC comes and goes and the Pi doesn't.

**Music plays through an OBS browser source**, the same pattern `dabi-voice` already uses. Give it its own OBS **audio track** so music is excluded from VOD and highlights while still going out live — retrofitting that later means re-cutting your audio setup.

**Buttons are `deck.yaml`, not code.** Adding a mood is a folder plus three lines. Scene *and* input names are checked against what OBS actually reports on every connect, so a stale name shows as a visibly broken button instead of one that fails the moment you press it mid-stream.

**State flows both ways.** The deck listens to OBS's own events, so switching scenes from the OBS window updates the tablet too. A deck that lies about state is worse than no deck.

## What's on the deck

Three pages, all defined in [`deck.yaml`](deck.yaml):

| Page | Buttons |
|---|---|
| **Scenes** | Starting · Just Chatting · Main · Screen · BRB · Parenting · Webcam · End |
| **Music** | Sad · Hype · Chill · Tension · Skip · Stop · Quieter · Louder · +1 · -1 |
| **Live** | Mic · Discord · Desktop · Alerts · Record · Stream · Dabi Says · Billboard |

Scene buttons highlight green when that scene is live. Mute buttons glow while muted. Record and Stream pulse red when active and need **two taps** (`confirm: true`). A button naming something OBS doesn't have renders greyed with a dashed amber border and shows the reason on tap.

Above the grid, a transport bar carries the **volume slider** — always visible, even with nothing playing, so you can set the level before it hits the stream — plus the current track, its rating, progress, and a **track picker** for going straight to one song.

### Ratings

**+1** and **-1** rate whatever is playing. A rating changes how often that track comes up in its mood: **+1 doubles the odds, -1 halves them**, and the scale stops at ±3 — so a favourite lands about eight times as often as a track you've buried, and nothing is ever excluded outright. A track at -3 still surfaces occasionally; if you want it gone, delete the file.

The current track's score shows next to the mood in the transport bar, green for positive and red for negative, and hides itself entirely when a track is unrated. Ratings also appear beside each track in the picker.

The no-repeat window still applies on top of the weighting, so even a +3 track can't play twice in a row — it comes up more often, not constantly.

Scores live in `data/ratings.json`, keyed by `mood/filename`. **Renaming a file resets its rating**, which is the trade for not maintaining a database of file hashes. The file is written on every rating and is safe to edit or delete by hand; deleting it just resets everything to neutral.

The picker below the volume slider lists every track grouped by mood. Choosing one plays it immediately and drops it into the no-repeat history, so letting the mood roll on afterwards won't replay it straight away. The list reloads after each rating so the scores stay current.

## Setup

### 1. Enable obs-websocket (streaming PC, one time)

OBS → **Tools → WebSocket Server Settings → Enable WebSocket server**. Note the password.

Verify the Pi can reach it:

```bash
ssh dabi 'timeout 3 bash -c "</dev/tcp/100.69.244.83/4455" && echo reachable'
```

*Connection refused* means the port is open but the server is off — that's the setting above. A timeout means something is actually blocking.

### 2. Clone and configure

The external Docker network must already exist (it does — the broadcaster stack owns it):

```bash
ssh dabi
cd ~/projects
git clone git@github.com:pdgeorge/pd-streamdeck.git && cd pd-streamdeck
cp .env.example .env
python3 -c "import secrets; print(secrets.token_urlsafe(24))"   # for DECK_TOKEN
$EDITOR .env
```

Fill in `DECK_TOKEN` and `OBS_PASSWORD`. **Leave `OBS_HOST` as the Tailscale IP** — a hostname will not resolve inside the container; see Troubleshooting.

### 3. Get the music onto the Pi

**A fresh clone has no audio.** The library is deliberately gitignored, so `git clone` brings the four empty mood folders and nothing else — every mood button then returns `400 — Mood 'sad' has no audio files`. Sync it separately:

```bash
# from the machine holding the library
rsync -av --progress songs/ dabi:~/projects/pd-streamdeck/songs/
```

`songs/` is a bind mount, so this works before or after the container starts. If after, `POST /api/music/rescan` rather than rebuilding.

Starting from nothing instead? [`songs/SOURCES.md`](songs/SOURCES.md) lists what's in the library and where it came from, with a stream-safe appendix if you want a library that carries no VOD risk at all, and [`tools/seed_placeholder_songs.py`](tools/seed_placeholder_songs.py) generates a distinct tone per mood so you can test the whole chain before you have real audio.

### 4. Start it

```bash
docker compose up -d --build
docker compose logs -f
```

Healthy startup looks like:

```
Loaded /config/deck.yaml: 3 page(s), 24 button(s)
Music library: {'chill': 10, 'hype': 10, 'sad': 10, 'tension': 10}
Deck up on :8095 -- OBS target 100.69.244.83:4455, auth on
Bus ready; exchanges: twitch_events, dabi_events
Connected to OBS at ws://100.69.244.83:4455
```

`OBS unreachable ... retrying in 2s` just means OBS is closed. That's correct behaviour, not a failure.

### 5. Point OBS at the music page

Add a **Browser Source** with URL `http://192.168.20.14:8095/player/?token=YOUR_TOKEN`

| Setting | Value | Why |
|---|---|---|
| Width × Height | `1` × `1` | The page renders nothing — it's an audio source |
| **Shutdown source when not visible** | **unchecked** | Otherwise music stops dead on every scene change |
| **Refresh browser when scene becomes active** | **unchecked** | Would restart the track on every switch |
| Audio Monitoring | **Monitor and Output** | So you hear it too, not just chat |
| Audio track (Advanced Audio Properties) | its own track | Lets you exclude music from VODs |

Put it in a scene that's always live, or a nested group present everywhere, so it survives scene changes. Add `&debug=1` while setting up to see a status panel, then remove it.

### 6. Point the tablet at the deck

Open `http://192.168.20.14:8095/?token=YOUR_TOKEN` once. The token is saved to localStorage and stripped from the URL, so afterwards just bookmark it or **Add to Home Screen** — it launches fullscreen and landscape.

On Android, set **Developer Options → Stay awake while charging**. More reliable than the Wake Lock API the page also tries.

## Updating

```bash
ssh dabi 'cd ~/projects/pd-streamdeck && git pull && docker compose up -d --build'
```

Changed only `deck.yaml`? No restart needed — `POST /api/config/reload` re-reads it and re-validates against live OBS. Changed only `.env`? `docker compose up -d` recreates without a rebuild.

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
| GET | `/api/music/tracks` | — every track with its rating, grouped by mood |
| POST | `/api/music/play` | `{"mood": "sad"}`, or `{"mood": "sad", "track": "undertale_memory.mp3"}` for a specific one |
| POST | `/api/music/skip` | — (400 if nothing is playing) |
| POST | `/api/music/stop` | — |
| POST | `/api/music/volume` | `{"level": 0.4}` (absolute, what the slider sends) or `{"delta": -0.1}` (what the buttons send) |
| POST | `/api/music/rate` | `{"delta": 1}` — rates the current track (400 if nothing is playing) |
| POST | `/api/music/rescan` | after adding files |
| POST | `/api/bus/publish` | `{"type": "dabi.tts.ready", "exchange": "dabi_events", "payload": {...}}` |
| POST | `/api/action` | `{"action": "music.mood", "params": {"mood": "hype"}}` |

`/api/action` is what the buttons use — it takes a `deck.yaml` action object verbatim, so a new action type needs no UI change.

```bash
curl -X POST http://192.168.20.14:8095/api/music/play \
     -H "X-Deck-Token: $DECK_TOKEN" -H 'Content-Type: application/json' \
     -d '{"mood":"hype"}'
```

Status codes: `503` means OBS or RabbitMQ is disconnected (the body says which), `400` means bad input (unknown mood, unknown action), `401` means a bad or missing token.

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

Top-level `music:` settings: `no_repeat_window` (default 3), `fade_seconds` (2.0), `default_volume` (0.6), `loop_mood` (true — when a track ends, pick another from the same mood).

### `bus.publish` is the cheap integration point

Every exchange in the stack is fanout with consumers filtering on `message.type`. A deck button can therefore drop an event that an existing service already handles, with **no changes to that service** — make Dabi speak, fire the `!other` billboard, or kick off the Chat-on-Trial flow from `twitch-broadcaster/PLANS.md`.

## Running locally

```bash
python3 -m venv .venv && .venv/bin/pip install -r deck_controller/requirements.txt
cd deck_controller && DECK_TOKEN=dev DECK_CONFIG=../deck.yaml MUSIC_LIBRARY=../songs \
  OBS_HOST=127.0.0.1 OBS_PASSWORD=... ../.venv/bin/python app.py
```

OBS and RabbitMQ being unreachable is fine — they retry in the background and every music feature works without them.

## Troubleshooting

| Symptom | Cause |
|---|---|
| `OBS unreachable ... [Errno -2] Name or service not known`, looping, password correct | **DNS, not connectivity.** `OBS_HOST` is a hostname the container can't resolve. Use the Tailscale IP. See below. |
| `OBS unreachable ... Connection refused` | obs-websocket server is off, or OBS is closed. |
| `OBS refused identification (wrong password?)` | Genuinely the password. It's in OBS → Tools → WebSocket Server Settings. |
| Every mood button returns `400 — has no audio files` | The library never got to the Pi. It's gitignored; `rsync` it (step 3). |
| Buttons greyed with a dashed amber border | The scene or input they name no longer exists in OBS. Tap for the reason; fix `deck.yaml` and `POST /api/config/reload`. |
| Music page never connects (`SND` dot red, `page_connected: false`) | OBS hasn't loaded the browser source, or its URL has the wrong token. |
| Music stops on every scene change | "Shutdown source when not visible" is checked on the browser source. |
| Track restarts on every scene change | "Refresh browser when scene becomes active" is checked. |
| Tablet shows stale state | The websocket dropped. It reconnects with backoff; the status dots go red meanwhile. |
| New files not showing up | `POST /api/music/rescan`. The library is scanned at startup, not per request. |

### The DNS one, in full

This is the trap most likely to cost you an hour, because the error reads like a firewall problem.

The Pi's *host* resolves Tailscale MagicDNS names like `cachyowo` fine. The *container* does not — Docker's embedded resolver (`127.0.0.11`) forwards to the host's nameservers rather than to the tailnet. So OBS is running, the password is right, the port is open, and it still fails.

Adding the name to the Pi's `/etc/hosts` **does not help**: Docker writes each container its own hosts file and never inherits the host's (verified). The container-side equivalent is `extra_hosts:` in `docker-compose.yml`, left commented there — but it pins the same IP, so it buys readability, not resilience.

Confirm which side is failing:

```bash
# host: works
ssh dabi 'getent hosts cachyowo'
# container: fails
ssh dabi 'docker exec pd-streamdeck python3 -c "import socket; print(socket.gethostbyname(\"cachyowo\"))"'
```

The service logs an explicit one-shot hint when it detects this.

## Gotchas

- **The music library is not in git.** `.gitignore` drops audio but keeps the mood folders. Back it up separately — a fresh clone will not have it.
- **A mood folder with one file will repeat it**, because there's nothing else to pick. The no-repeat window caps itself at one less than the folder size.
- **Ratings need the `./data` volume.** `songs/` is mounted read-only on purpose, so track scores cannot live next to the audio. If `DECK_STATE_DIR` isn't writable the deck still runs and still rates — it logs `Ratings are in memory only` once and forgets them on restart. Adding the volume to an already-running deployment needs `docker compose up -d` to recreate the container; a `rescan` won't do it.
- **Normalise loudness before adding files.** Sources master at wildly different levels, and with a random picker that means `Hype` blowing the doors off right after `Sad` whispered. The existing library is two-pass `loudnorm`'d to −16 LUFS; there's an ffmpeg recipe in [`songs/SOURCES.md`](songs/SOURCES.md).
- **`Mic/Aux` and `Desktop Audio` are dead Windows leftovers** in the OBS config. They're `wasapi_*` kinds, which Linux OBS can't drive — pressing one returns *"The specified input does not support audio."* The live pulse inputs are `Microphone`, `Discord`, `Default` (desktop audio) and `VR Microphone`. `GET /api/state` lists every audio-capable input under `obs.muted`.
- **Some scenes carry no microphone.** Audio sources are per-scene in OBS, so switching scene changes what's audible. As audited: `Cam` and `RandomBS` have **no audio sources at all** — switching to either kills mic, desktop and Discord simultaneously; `Backpack RTSP`, `Parenting` and `FullscreenVid` carry no mic. The Scenes page deliberately covers only the eight stream-ready scenes; `Cam` and `RandomBS` are left off on purpose. Re-audit after editing scenes with `GET /api/state`.
- **The scene JSON on disk goes stale.** OBS writes it on exit or collection switch, so reading it mid-session can name scenes that no longer match. The live collection is `Pd` (profile `Cyra`). Trust `GET /api/obs/scenes`, not the file — this is why buttons validate at connect time.
- **Music licensing.** The library is commercial game soundtracks, so the separate OBS audio track is doing real work: it keeps music out of the VOD, which is what Audible Magic scans. It does not cover the live stream. See [`songs/SOURCES.md`](songs/SOURCES.md) for the reasoning and a stream-safe alternative.
- **The Pi is on WiFi** (`wlan0`, 192.168.20.14). Fine for audio (~40 KB/s), but it's a reason to keep the tablet on the same LAN.
- **Port 8095** is this service. Also in use on the Pi: 8000, 8001, 8080, 8090, 8787, 3306, 5672, 15672, 11434.

## Related

- [`songs/SOURCES.md`](songs/SOURCES.md) — where the music came from, per-mood picks, and the copyright traps
- [`songs/ATTRIBUTION.md`](songs/ATTRIBUTION.md) — composer credits for everything in the library
- `../dabiverse/ARCHITECTURE.md` — the wider stack this plugs into
