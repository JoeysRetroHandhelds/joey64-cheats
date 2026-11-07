# joey64-cheats

The cheat lists Joey64 downloads. The app ships with no cheats. When you open Cheats for a game,
it reads `dist/index.json` from this repo's `release` branch, fetches that game's files, and
keeps them.

## Sources

Each source stays in its own folder under its own licence. The repo holds separate works, so a
GPLv2-only list and a GPLv3 list are never merged into one file. The app merges them on the
device.

| Folder | From | Licence |
|---|---|---|
| `sources/project64/` | Project64 `Config/Cheats`, and `Config/Enhancements` in `enhancements/` (github.com/project64/project64) | GPL-2.0-only (Project64's licence) |
| `sources/rmg-custom/` | Rosalie's Mupen GUI `Data/Cheats/Custom` (github.com/Rosalie241/RMG) | GPL-3.0 |
| `sources/fz-retroben/` | retroben's codes in M64Plus FZ's `mupencheat.default`, only the ones it adds to mupen64plus-core's list (`tools/extract-retroben.py`) | GPL-3.0 |
| `sources/libretro/` | libretro-database `cht/Nintendo - Nintendo 64` (github.com/libretro/libretro-database) | CC BY-SA 4.0 |
| `joey64/` | codes we write or fix ourselves, in mupencheat.txt format | GPL-3.0-or-later |

The copied files are never edited. Fixes go in `joey64/`.

Each source folder has a `SOURCE.md` with the commit it was copied from.

## Format

`python tools/convert.py` writes `dist/`.

- **`dist/index.json`:** `{"format": 1, "games": {key: {"game": name, "sources": {source: cheat count}, "extras"?: ["widescreen", "60fps"]}}}`.
- **`dist/<source>/<key>.json`:** `{"source", "license", "key", "game", "cheats": [...], "left_out"?}`.

**Keys.** A key is the ROM header's two checksums and its country byte, `CRC1-CRC2-CC`
(`3E5055B6-2E92DA52-45` is Mario Kart 64 (USA)). When no source gives the country, the key is
`CRC1-CRC2`.

**Placing libretro's files.** libretro's files are named after the game (GoodN64 or No-Intro
names, sometimes the ROM's internal name), so they're placed with three tables:
- `tools/mupen64plus.ini` (mupen64plus-core, GPL-2.0+) gives a GoodN64 name or MD5 its header checksums.
- `tools/n64-names.tsv` (Joey64's box-art table, from libretro-database, CC BY-SA 4.0) gives a No-Intro name its MD5.
- `tools/project64.rdb` (Project64's `Config/Project64.rdb`, GPL-2.0-only) gives its game names and
  internal names their header checksums. Only read by `convert.py`; nothing of it goes in `dist/`.

A file is placed by its exact name first. Otherwise by its name with the naming styles evened
out (`(USA)` and `(U)`, `(Rev A)` and `(V1.1)`, `&` and `and`, no "The", spaces or punctuation),
then by an internal name, then by a name a few letters off with the same country and version.
Each of those guesses is checked against the other sources' codes for that game: the share of
the file's code addresses they also poke. A guessed name is dropped when it shares none (the
others have cheats there, at other places: another version); an internal or near name needs half
its addresses shared; two games that fit as well leave the file unplaced. Files found by their
exact name go first, so the game keeps that name and its cheats come first.

Files that match no game are listed in `tools/unplaced-libretro.txt`. These are mostly betas,
GameCube releases and hacks the tables don't have.

**Cheats.** Each cheat has:
- `name`: folders separated by `\`, for example `Infinite Items\2 player Mode\Player 1`.
- `codes`: GameShark codes, `"8016609D 00??"`.

It can also have:
- `options`: `[[value, label], ...]`. The value replaces the `?` digits.
- `note`
- `flags`: see below.

## Flags

- **`gs_button`:** needs the GameShark's own button (codes starting 88, 89, A8, A9, D8 to DB). Joey64 has none, so it hides these.
- **`boot`:** a boot-time code (F0, F1, FF, EE). It works only from the game's start, so turning it on needs a reset.
- **`widescreen`, `60fps`:** codes that make the picture wide or run the game at 60 fps (50 for PAL games), matched by name. Most come from Project64's Enhancements, where only these are taken: its other enhancements are fixes for its own plugins, mostly on by default there. "Always off" codes are left out: they turn a game's own widescreen off. These belong in their own menu spots, not Cheats (Joey, 2026-11-06), so Joey64 keeps them off the Cheats page. `index.json` lists them per game in `"extras"`.
- **`needs_value`:** a `?` or `X` value with no options to pick from. Joey64 hides these for now.

**Bulk lists.** libretro's bulk lists are left out and counted in `left_out`. A bulk list is more
than 40 cheats whose names differ only in their numbers, for example Turok's 30,911 "Soldier #42"
spawn codes.

## Updating

1. `tools/update-sources.sh` pulls the four sources and copies them in.
2. `tools/convert.py` writes `dist/`.

Review the change on `main`, then move the `release` branch to it. Nothing goes live
unreviewed. The app reads `release` and checks it again at most once a week.

## Widescreen finder (trial, 2026-11-06)

`tools/widescreen-finder.py <state.raw>` reads RDRAM from a mupen64plus save state and lists places a 4:3 aspect lives, each with GameShark codes for 16:9: guPerspective call sites (the aspect argument, a3), floats near 4:3 that code loads, and instructions building them. `tools/widescreen-sheet.py` puts screenshots of each try side by side.

Checked against Project64's codes: it finds the same spots for Super Mario 64, Mario Kart 64 and Banjo-Kazooie. Tried on five games with no code, from Joey's states on the Thor:

- GoldenEye 007 (U): works, `81003D84 3C07` + `81003D86 3FE3` (more on both sides). Not play-tested yet: HUD, culling at the edges, other levels.
- Conker's Bad Fur Day (U), Perfect Dark (U) (Rev 1), Cruis'n USA (U): no change from any candidate. They build the projection their own way, so these need work by hand.
- Yoshi's Story (U): the guPerspective calls changed nothing visible; not found.

Nothing found here goes into `joey64/` until it's play-tested.

## Weekly update

`.github/workflows/weekly-update.yml` runs Mondays (and by hand): `tools/update-sources.sh` pulls the sources and writes their commits into each `SOURCE.md`, `tools/convert.py` rebuilds `dist/`, and when anything changed the result goes on the `weekly-update` branch with a pull request into `main`. `release`, the branch Joey64 downloads, moves only after review: `git branch -f release main && git push origin release`.
