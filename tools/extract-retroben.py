"""
Writes sources/fz-retroben/retroben.txt: the cheats M64Plus FZ's mupencheat.default adds to
upstream mupen64plus-core's mupencheat.txt (retroben's, 2016-17), in the same format, and nothing
else. Upstream's own list is Project64's older one, which sources/project64 already covers.

    python tools/extract-retroben.py <FZ mupencheat.default> <upstream mupencheat.txt>
"""
import os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def blocks(text):
    """crc line -> (gn line, {cheat name: its lines})."""
    games = {}
    crc = gn = name = None
    for line in text.split("\n"):
        line = line.rstrip("\r")
        if line.startswith("crc "):
            crc, gn, name = line, None, None
            games.setdefault(crc, [None, {}])
        elif line.startswith("gn ") and crc:
            games[crc][0] = line
        elif line.strip().startswith("cn ") and crc:
            name = line.strip()[3:]
            games[crc][1][name] = [line]
        elif crc and name and line.startswith(" "):
            games[crc][1][name].append(line)
        elif not line.strip():
            name = None
    return games


def main(fz, up):
    a = blocks(open(fz, encoding="utf-8", errors="replace").read())
    b = blocks(open(up, encoding="utf-8", errors="replace").read())
    out = [
        "// Cheats M64Plus FZ (github.com/mupen64plus-ae/mupen64plus-ae, app/src/main/assets/mupen64plus_data/mupencheat.default) adds to",
        "// mupen64plus-core's mupencheat.txt, written by retroben in 2016-17. GPL-3.0 (FZ's licence).",
        "// Extracted by tools/extract-retroben.py; the format is mupencheat.txt's.",
        "",
    ]
    n = 0
    for crc, (gn, cheats) in a.items():
        theirs = b.get(crc, [None, {}])[1]
        new = [lines for name, lines in cheats.items() if theirs.get(name) != lines]
        if not new:
            continue
        out += [crc, gn or "gn"]
        for lines in new:
            out += lines
            n += 1
        out.append("")
    dst = os.path.join(ROOT, "sources", "fz-retroben", "retroben.txt")
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    open(dst, "w", encoding="utf-8", newline="\n").write("\n".join(out) + "\n")
    print(f"{n} cheats")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
