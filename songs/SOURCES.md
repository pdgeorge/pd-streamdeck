# Where the music comes from

**The library is 40 tracks pulled from game soundtracks you own** — ten each in `chill`, `hype`, `tension` and `sad`. Every file is two-pass loudness-normalised to -16 LUFS (-1.5 dBTP, LRA 11) and re-encoded at 192 kbps, so a random pick never jumps in volume between a Cuphead big-band number and an Amnesia ambient cue.

Source: `/media/Bucket_Drive/Media/Game Soundtracks/`, plus two tracks that were already in `sad/` and one public-domain Grieg recording in `tension/`.

**This is why `songs/` is gitignored and stays that way.** These are purchased copies, not redistributable. The library moves between your own machines with `rsync` and never through the repo; a fresh clone gets four empty mood folders and every mood button returns `400 — Mood 'sad' has no audio files` until you sync. See the README for the command.

Filenames follow `game_track.mp3` because the deck displays the filename as the now-playing track — so what's on the tablet, and in any future `!music` response, reads as something a person recognises.

## `songs/chill/` — unhurried, melodic, loops without demanding attention

| Track | Game | Composer |
|---|---|---|
| Overworld Day | Terraria | Scott Lloyd Shelly |
| Overworld Night | Terraria | Scott Lloyd Shelly |
| Quiet and Falling | Celeste | Lena Raine |
| Dirtmouth | Hollow Knight | Christopher Larkin |
| Horsehead Nebula | Starbound | Curtis Schweitzer |
| Adventure | FEZ | Disasterpeace |
| The Glasshouse With Butterfly | Machinarium | Tomáš Dvořák |
| Waterfall | UNDERTALE | toby fox |
| Cider Time | Dustforce | Lifeformed |
| Autumn's Rise | CrossCode | Deniz Akbulut |

Two Terraria tracks because that was the reference point for this mood. All instrumental, all written to loop under gameplay, none of them pull focus from a voice.

## `songs/hype/` — fighting-game energy

| Track | Game | Composer |
|---|---|---|
| Storyteller | Guilty Gear Xrd | Daisuke Ishiwatari |
| Scourge of the Furies | Hades | Darren Korb |
| Esaka Continues | The King of Fighters XIII | SNK Sound Team |
| Infernal Descent (1-1 Remix) | Crypt of the NecroDancer | FamilyJules7x, after Danny Baranowsky |
| Coalescence | Risk of Rain Returns | Chris Christodoulou |
| Floral Fury | Cuphead | Kristofer Maddigan |
| BULLET HELL YES | Enter the Gungeon | doseone |
| Final Boss | Guacamelee! | Rom Di Prisco |
| Lace | Hollow Knight: Silksong | Christopher Larkin |
| Turning the Tide | Jamestown | Francisco Cerda |

*Storyteller* set the register — vocal guitar rock — and KOF XIII and the FamilyJules metal remix sit next to it deliberately. Cuphead and Guacamelee are the outliers on texture, so the mood isn't ten minutes of the same guitar tone. Two tracks here have vocals, which compete with a voice more than the rest of the library does.

## `songs/tension/` — something is about to happen

| Track | Game | Composer |
|---|---|---|
| Explore the Ruins | Darkest Dungeon | Stuart Chatwood |
| Terror and Madness | Darkest Dungeon | Stuart Chatwood |
| Theme For Unknown | Amnesia: The Dark Descent | Mikko Tarmia |
| Lost Ship (Battle) | FTL: Advanced Edition | Ben Prunty |
| Soul Sanctum | Hollow Knight | Christopher Larkin |
| Premonition | UNDERTALE | toby fox |
| Hidden dangers | Spelunky 2 | Eirik Suhrke |
| The Night | Cult of the Lamb | River Boy |
| The Black Brotherhood Theme | Machinarium | Tomáš Dvořák |
| In the Hall of the Mountain King | — | Grieg, Musopen recording (public domain) |

Two Darkest Dungeon tracks because it's the best-in-class soundtrack for this mood and the two cover different registers: slow creeping dread, and active panic. The Grieg is the one survivor of the previous library — public domain, no attribution needed, and the accelerating build is almost purpose-made for this button.

## `songs/sad/` — the emotional moment

| Track | Game | Composer |
|---|---|---|
| Dejected Groose | The Legend of Zelda: Skyward Sword | Nintendo (Wakai / Fujii / Yokota / Hama / Kondo) |
| EV27-2 Truth | Bayonetta | SEGA / PlatinumGames |
| For River — Piano (Johnny's Version) | To The Moon | Kan Gao |
| Time is a Place (Piano Vers.) | Finding Paradise | Kan Gao |
| Reflection | Hollow Knight | Christopher Larkin |
| Memory | UNDERTALE | toby fox |
| Mother, I'm Here (Zulf's Theme) | Bastion | Darren Korb |
| Paper Boats | Transistor | Darren Korb |
| Reverie | Momodora: Reverie Under the Moonlight | nK |
| Lament of Orpheus | Hades | Darren Korb |

Built around the two tracks that were already here: solemn, weighted and melodic rather than bleak and ambient. *Paper Boats* and *Lament of Orpheus* have vocals — fine for a button you press for a beat, worth swapping if you leave Sad running under talking.

## The VOD question

Everything here except the Grieg is commercial music. Owning the soundtrack and being licensed to broadcast it are different things, and [Twitch's Audible Magic scanning mutes VODs in 30-minute blocks](https://www.streamscheme.com/can-you-play-video-game-music-on-twitch/) on a match.

The mitigation is already in the setup: the README has the music browser source on **its own OBS audio track**, excluded from VOD and highlights. Music that isn't in the VOD can't get the VOD muted — live viewers hear it, the recording doesn't contain it. That handles the muting risk; it doesn't cover a live DMCA claim, which is a separate and much rarer thing. If you ever want the exposure gone entirely rather than reduced, the appendix below is the stream-safe route.

## Adding or replacing a track

Normalise before it goes in, or it will be louder or quieter than everything else. Two passes — measure, then apply the measurement:

```bash
# pass 1: measure
ffmpeg -i in.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11:print_format=json -f null -
# pass 2: apply the measured_* values it printed
ffmpeg -i in.mp3 -af loudnorm=I=-16:TP=-1.5:LRA=11:measured_I=…:measured_TP=…:measured_LRA=…:measured_thresh=…:offset=…:linear=true \
  -ar 44100 -c:a libmp3lame -b:a 192k songs/<mood>/game_track.mp3
```

Then `POST /api/music/rescan`, or restart the container.

**Ten per mood is the number to hold.** The no-repeat window is 3 and caps itself at one less than the folder size, so ten gives genuinely varied rotation without the folder turning into something you never curate. Adding an eleventh is a good moment to ask which one it replaces.

---

# Appendix: the stream-safe route

This was the previous library — 132 CC-BY and public-domain tracks, all free, none of them ever a VOD risk. It's here because the research is still valid if you ever want to switch back, or want a second set for VOD-safe segments.

## The classical trap

**A public-domain composition is not a public-domain recording.** Beethoven died in 1827 and his *score* is free to anyone. A 2015 Berlin Philharmonic *performance* of it is a brand-new copyrighted sound recording, and using it gets you flagged exactly like using a pop song. [Musopen](https://musopen.org/) exists precisely for this — a non-profit that pays professional orchestras to record the repertoire and releases those *recordings* into the public domain. That's the safe classical source, and it's where the Grieg in `tension/` came from.

Three pieces that trip people up because they *sound* old but aren't: "Albinoni's" Adagio in G minor (actually Remo Giazotto, d. 1998), Barber's Adagio for Strings (d. 1981), and Orff's *O Fortuna* (d. 1982).

## The sources

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

Lowest friction of the lot: StreamBeats needs no attribution at all and downloads as genre-sorted albums. Scott Buckley is the one worth manual effort — his site returns HTTP 406 to scripted requests, so it's ten minutes of clicking, and he's the best free match for `sad` and `hype` on this page.
