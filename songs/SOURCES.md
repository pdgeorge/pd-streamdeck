# Where the music comes from

**The library is populated.** 132 tracks are already in place: 38 chill, 58 hype, 21 sad, 15 tension. All two-pass loudness-normalised to -16 LUFS and re-encoded at 192 kbps, so a random pick never jumps in volume between a chiptune track and an orchestra. See [`ATTRIBUTION.md`](ATTRIBUTION.md) for the credit line to paste into a Twitch panel.

What's in there now:

| Source | License | Tracks |
|---|---|---|
| Kevin MacLeod (Incompetech) | CC BY 4.0 | 39 |
| Ozzed — 3 chiptune albums | Creative Commons | 46 |
| Musopen classical | Public Domain | 30 |
| Eric Skiff — *Resistor Anthems* | CC BY 4.0 | 17 |

**Not downloaded: Scott Buckley.** His site returns HTTP 406 from Mod_Security to any scripted request — a deliberate anti-scraping measure I didn't try to work around. He's the single best source on this page for `sad` and `hype`, so it's worth ten minutes of clicking: grab `Penumbra`, `Incredulity`, `Wildflowers`, `In This Moment` for sad, and `Song Of The Forge`, `Aphelion`, `Born Of The Sky` for hype, from <https://www.scottbuckley.com.au/library/>. Drop them in, then `POST /api/music/rescan`.

Everything below is the research this selection came from.

---

Everything listed here is either **CC0/public-domain** or **CC-BY** (free, credit required), or is explicitly licensed for streaming. Nothing here should ever mute a VOD.

---

## First, the bad news about Terraria and Skyrim

Game soundtracks are **not** copyright-free. Terraria's music is Scott Lloyd Shelly's (Resonance Array) and is sold as a paid album; Skyrim's is Jeremy Soule's, owned by Bethesda/ZeniMax; fighting-game music belongs to Capcom, SNK, Arc System Works and friends.

There's a meaningful distinction worth knowing:

- **Game audio while you're actually playing that game** is broadly tolerated — it's incidental to the gameplay you're licensed to broadcast.
- **Ripping the OST to use as standalone background music** is not covered by anything, and it's exactly what a deck button would be doing.

Either way, [Twitch's Audible Magic scanning mutes VODs in 30-minute blocks](https://www.streamscheme.com/can-you-play-video-game-music-on-twitch/) when it detects a match, so even the tolerated case costs you VODs. The good news: the *vibes* you named — Terraria's unhurried melodic chiptune, Skyrim's orchestral swell, fighting-game intensity — are all extremely well covered by composers who give their work away. That's what's below.

## Second, the classical trap

You said you're up for classical, so this is the single most important thing on this page:

**A public-domain composition is not a public-domain recording.** Beethoven died in 1827 and his *score* is free to anyone. A 2015 Berlin Philharmonic *performance* of it is a brand-new copyrighted sound recording, and using it will get you flagged exactly like using a pop song.

You need recordings that are themselves PD or CC0. [Musopen](https://musopen.org/) exists precisely for this — it's a non-profit that pays professional orchestras to record the classical repertoire and releases those recordings into the public domain (CC0). That's the safe classical source.

Three specific pieces that trip people up because they *sound* old but aren't:

| Piece | Why it's not safe |
|---|---|
| "Albinoni's" Adagio in G minor | Actually written by Remo Giazotto (d. 1998). Not PD. |
| Barber — Adagio for Strings | Barber d. 1981. Not PD. |
| Orff — *O Fortuna* (Carmina Burana) | Orff d. 1982. Not PD. |

---

## The core sources

| Source | License | Attribution | Best for |
|---|---|---|---|
| [Scott Buckley](https://www.scottbuckley.com.au/library/) | CC-BY 4.0 | Yes | sad, hype, tension — the standout |
| [Alexander Nakarada](https://www.free-stock-music.com/artist/alexander-nakarada/) | CC-BY 4.0 | Yes | hype, tension — battle/epic |
| [Kevin MacLeod / Incompetech](https://incompetech.com/music/royalty-free/music.html) | CC-BY | Yes | everything; 2000+ tracks, mood-tagged |
| [Eric Skiff — Resistor Anthems](http://ericskiff.com/music/) | CC-BY 4.0 | Yes | chill, hype — chiptune |
| [Ozzed](https://ozzed.net/music/) | Creative Commons | Yes | chill, hype — 8-bit |
| [Chris Zabriskie](https://freemusicarchive.org/music/Chris_Zabriskie/) | CC-BY 4.0 | Yes | sad, chill — ambient/piano |
| [Musopen](https://musopen.org/) | CC0 / PD | No | classical, all moods |
| [StreamBeats](https://www.streambeats.com/) | Stream-licensed | **No** | everything; ~1000 tracks, zero obligations |
| [Free Music Archive](https://freemusicarchive.org/) | Varies — check each | Varies | aggregator |

If you want the absolute lowest-friction start: **StreamBeats requires no attribution at all** and has genre-sorted albums you can bulk-download. Grab that first, then cherry-pick the CC-BY composers below for the tracks that actually have character.

---

## `songs/chill/` — the Terraria feeling

Unhurried, melodic, slightly wistful, loops forever without demanding attention.

**Chiptune (closest to the Terraria texture)**
- **Ozzed** — the albums *Dunes at Night*, *Lesser than Three*, *8-bit Empire*. Whole albums download as zips or torrents.
- **Eric Skiff** — `Come and Find Me`, `We're all under the stars`, `Behind the waterfall lies the beginning`, `Prologue`

**Ambient / piano**
- **Chris Zabriskie** — the *Cylinder* series (`Cylinder Five`, `Cylinder Seven`, `Cylinder Nine`), `Prelude No. 20`
- **Scott Buckley** — `Home Was You`, `Echoes Of Home` (his own note calls it Ghibli-ish), `Amberlight`

**Classical (Musopen)**
- Satie — *Gymnopédie No. 1*, *Gnossiennes*
- Debussy — *Clair de Lune*, *Rêverie*
- Chopin — the slower Nocturnes

## `songs/hype/` — Skyrim battle and fighting-game energy

**Orchestral**
- **Scott Buckley** — `Song Of The Forge` (an epic dwarven war march — the closest you'll legally get to the Skyrim register), `Aphelion`, `Born Of The Sky`
- **Alexander Nakarada** — `Mega Boss Fight`, `Superepic`, `Battle Loop`

**Chiptune / fighting-game energy**
- **Eric Skiff** — `A Night Of Dizzy Spells`, `Chibi Ninja`, `Jumpshot`, `We're the Resistors`, `HHavok-main`

**Classical (Musopen)**
- Wagner — *Ride of the Valkyries*
- Holst — *Mars, the Bringer of War* (also excellent for tension)
- Beethoven — Symphony No. 5, first movement
- Tchaikovsky — *1812 Overture*, finale

**Kevin MacLeod** — filter his catalogue by the `Epic`, `Action` and `Driving` tags.

## `songs/tension/` — something is about to happen

- **Scott Buckley** — `Eyes In The Void` (dark chaotic gothic orchestral), `Unraveling`
- **Kevin MacLeod** — the `Suspenseful`, `Unnerving` and `Eerie` tags; there's a well-known collection of ~128 scary cinematic cues
- **Alexander Nakarada** — his darker orchestral material

**Classical (Musopen)**
- Mussorgsky — *Night on Bald Mountain*
- Grieg — *In the Hall of the Mountain King* (the accelerating build is almost purpose-made for this)
- Bach — *Toccata and Fugue in D minor*
- Holst — *Mars*

## `songs/sad/` — the emotional moment

- **Scott Buckley** — `Penumbra`, `Incredulity`, `Wildflowers`, `In This Moment`, `Unraveling`. This is where he's strongest; his own tags call them bittersweet and introspective.
- **Chris Zabriskie** — `There's Probably No Time`, `Undercover Vampire Policeman`, and most of the ambient piano catalogue
- **Kevin MacLeod** — the `Somber` tag; there's a collection of ~78 sad cinematic cues

**Classical (Musopen)**
- Chopin — *Nocturne Op. 9 No. 2*
- Beethoven — *Moonlight Sonata*, first movement
- Satie — *Gymnopédie No. 1* (works in both chill and sad)
- Schubert — *Ave Maria*

---

---

## Tracks that can't go in here, and what replaced them

Some specific game tracks are worth wanting and impossible to use. Two examples, with the free substitutes chosen to match them:

**"Dejected Groose"** — *The Legend of Zelda: Skyward Sword*, Nintendo (Wakai / Fujii / Yokota / Hama / Kondo). A gentle bittersweet lament: a comic character given real pathos, carried on strings and brass. Nintendo has no free release and is the worst possible rights-holder to test. Closest free matches now in `sad/`:

- `brahms_sym3-poco-allegretto` — the canonical bittersweet cello melody; warm rather than devastating, which is the hard part to match
- `borodin_quartet2-nocturne` — tender and lyrical, same "sad but fond" register
- `grieg_aases-death` — already there, and closer than it first looks

**"EV27-2 Truth"** — *Bayonetta*, SEGA / PlatinumGames. A late-game revelation cue: solemn, weighted, building. Closest free matches now in `sad/`:

- `brahms_sym1-andante-sostenuto` — solemn and building, the same slow reveal
- `mendelssohn_scottish-adagio` — brooding
- `suk_meditation` — already there; a solemn chorale, arguably the closest single match in the library

A note on sourcing: unauthorised OST rips are all over archive.org, YouTube and elsewhere. Being freely *available* is not being freely *licensed*. The Musopen material in this library came from archive.org because that specific item carries a Public Domain Mark; a Bayonetta OST upload sitting next to it carries nothing.

Also worth separating: **owning** a soundtrack and being allowed to **broadcast** it are different things. A legally bought copy still trips Audible Magic and still costs you the VOD block.

## Practical notes

**Aim for 8–15 tracks per mood.** The no-repeat window is 3, and it caps itself at one less than the folder size — so a folder of 4 gives you genuinely varied rotation, and a folder of 2 just alternates.

**Normalise the loudness before you drop files in.** Different sources master at wildly different levels, and with a random picker that means `Hype` blowing the doors off right after `Sad` whispered. One pass with ffmpeg fixes it:

```bash
# -16 LUFS is a reasonable target for background music under voice
for f in songs/*/*.mp3; do
  ffmpeg -i "$f" -af loudnorm=I=-16:TP=-1.5:LRA=11 -c:a libmp3lame -q:a 2 "${f%.mp3}.norm.mp3" \
    && mv "${f%.mp3}.norm.mp3" "$f"
done
```

**Keep the artist in the filename** — `scott-buckley_penumbra.mp3`. The deck shows the filename as the now-playing track, so attribution becomes something you can read off the tablet instead of looking up.

**Then rescan:** `POST /api/music/rescan`, or restart the container.

## Attribution, practically

CC-BY needs credit "such that a person can reasonably find the source". For a live stream that normally means a **Twitch panel** listing the composers you use, which covers your whole library in one place and needs no per-track work.

Worth knowing for later: `overlay_controller` already has the `#a <trigger> <response>` custom-command system, so a `!music` panel-equivalent in chat is a two-minute job. And because the deck knows the current track and can `bus.publish` to `channel.command.send_chat`, a `!music` that answers with what's *actually playing right now* is a small feature away.

StreamBeats and Musopen need no attribution at all, if you'd rather not think about it.
