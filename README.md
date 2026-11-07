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
names), so they're placed with two tables:
- `tools/mupen64plus.ini` (mupen64plus-core, GPL-2.0+) gives a GoodN64 name or MD5 its header checksums.
- `tools/n64-names.tsv` (Joey64's box-art table, from libretro-database, CC BY-SA 4.0) gives a No-Intro name its MD5.

Files that match no game are listed in `tools/unplaced-libretro.txt`. These are mostly files
named after the ROM's internal name, or after dumps the tables don't have.

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
