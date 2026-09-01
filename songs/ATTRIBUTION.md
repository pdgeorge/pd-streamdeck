# Attribution

The library is CC-BY except the classical, which is public domain and needs no credit. CC-BY asks that credit be placed where a reasonable person could find it — for a live stream, a **Twitch panel** is the accepted way, and it covers the whole library at once rather than per track.

## Paste this into a Twitch panel

> **Stream music**
>
> Kevin MacLeod — incompetech.com — CC BY 4.0
> Eric Skiff — *Resistor Anthems* — ericskiff.com/music — CC BY 4.0
> Ozzed — ozzed.net — Creative Commons
> Classical recordings — Musopen — public domain

That's the whole obligation discharged. Below is the detail, in case you want it.

---

## Kevin MacLeod — CC BY 4.0

Source: <https://incompetech.com/music/royalty-free/music.html>

Required form of credit:

> Music: "Song Name" by Kevin MacLeod (incompetech.com)
> Licensed under Creative Commons: By Attribution 4.0
> http://creativecommons.org/licenses/by/4.0/

Tracks in this library: see `songs/*/kevin-macleod_*.mp3`.

## Eric Skiff — *Resistor Anthems* — CC BY 4.0

Source: <http://ericskiff.com/music/>

His requested form, verbatim:

> Music: Eric Skiff - Song Name - Resistor Anthems - Available at http://EricSkiff.com/music

Tracks in this library: see `songs/*/eric-skiff_*.mp3`.

## Ozzed — Creative Commons

Source: <https://ozzed.net/music/>

Ozzed asks to be credited as composer, preferably with a link back to ozzed.net. Albums used: *Dunes at Night*, *8-bit Empire*, *Lesser than Three*.

Tracks in this library: see `songs/*/ozzed_*.mp3`.

## Classical — Musopen — Public Domain Mark 1.0

Source: <https://archive.org/details/MusopenCollectionAsFlac> (the Musopen Collection)

**No attribution required.** Musopen commissions professional recordings of public-domain repertoire and releases the *recordings* into the public domain, which is what makes them safe — a public-domain composition performed on a modern commercial recording is not.

Composers used: Bach, Beethoven, Borodin, Brahms, Dvořák, Grieg, Haydn, Mendelssohn, Mozart, Rimsky-Korsakov, Schubert, Smetana, Suk, Tchaikovsky.

---

## Doing it automatically, later

The deck already knows the currently playing track, and `bus.publish` can post to `channel.command.send_chat`. So a `!music` chat command that answers with what's playing *right now* is a small feature rather than a project. Worth doing if you ever want per-track credit rather than a panel — but the panel alone satisfies CC-BY.
