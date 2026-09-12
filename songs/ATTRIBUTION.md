# Attribution

**Nothing in this library carries a license obligation.** The previous library was CC-BY, which required a credit line placed where a reasonable person could find it. The current one is commercial game soundtracks you own plus one public-domain Grieg recording — neither of which asks for anything. Purchased music has no attribution clause to satisfy, and Musopen releases its recordings into the public domain.

So this file is no longer a compliance document. It's the credit list, kept because viewers ask what's playing and because the composers deserve the name.

## Composers in this library

| Composer | Work | Where |
|---|---|---|
| Christopher Larkin | Hollow Knight, Hollow Knight: Silksong | chill, hype, tension, sad |
| Darren Korb | Hades, Bastion, Transistor | hype, sad |
| toby fox | UNDERTALE | chill, tension, sad |
| Tomáš Dvořák (Floex) | Machinarium | chill, tension |
| Stuart Chatwood | Darkest Dungeon | tension |
| Kan Gao | To The Moon, Finding Paradise | sad |
| Scott Lloyd Shelly (Resonance Array) | Terraria | chill |
| Lena Raine | Celeste | chill |
| Curtis Schweitzer | Starbound | chill |
| Disasterpeace | FEZ | chill |
| Lifeformed | Dustforce (*Fastfall*) | chill |
| Deniz Akbulut | CrossCode | chill |
| Daisuke Ishiwatari | Guilty Gear Xrd | hype |
| SNK Sound Team | The King of Fighters XIII | hype |
| Danny Baranowsky, remixed by FamilyJules7x | Crypt of the NecroDancer | hype |
| Chris Christodoulou | Risk of Rain Returns | hype |
| Kristofer Maddigan | Cuphead | hype |
| doseone | Enter the Gungeon | hype |
| Rom Di Prisco | Guacamelee! | hype |
| Francisco Cerda | Jamestown | hype |
| Mikko Tarmia | Amnesia: The Dark Descent | tension |
| Ben Prunty | FTL: Advanced Edition | tension |
| Eirik Suhrke | Spelunky 2 | tension |
| River Boy | Cult of the Lamb | tension |
| nK | Momodora: Reverie Under the Moonlight | sad |
| Nintendo (Wakai / Fujii / Yokota / Hama / Kondo) | The Legend of Zelda: Skyward Sword | sad |
| SEGA / PlatinumGames | Bayonetta | sad |
| Edvard Grieg, recorded by the Czech National Symphony Orchestra | *In the Hall of the Mountain King* — Musopen, public domain | tension |

## If you want a panel anyway

A Twitch panel listing the games is a reasonable courtesy even without an obligation, and it answers the question before anyone asks it:

> **Stream music**
>
> Soundtracks from Hollow Knight, Hades, UNDERTALE, Terraria, Celeste, Cuphead, Darkest Dungeon, To The Moon and others — see `!music` for what's playing.

## Doing it per-track, later

The deck knows the currently playing track, and `bus.publish` can post to `channel.command.send_chat`. A `!music` command that answers with what's playing *right now* is a small feature rather than a project — and it's more useful here than it was under the old library, because "what's this track?" is a question people actually ask about game music. Filenames are already `game_track.mp3` for exactly this reason.
