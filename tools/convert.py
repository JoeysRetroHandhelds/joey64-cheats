"""
Turns every source under sources/ into Joey64's cheat files under dist/ (README: Format).

    python tools/convert.py

dist/index.json lists every game; dist/<source>/<key>.json holds one source's cheats for one game.
A key is the ROM header's checksums and country byte, "CRC1-CRC2-CC" (as Project64 keys games,
"3E5055B6-2E92DA52-45"), or "CRC1-CRC2" when a source gives no country. Sources stay in their own
files under their own licences; the app merges them on the device.

Needs tools/mupen64plus.ini (game names -> header CRCs), tools/n64-names.tsv (MD5 -> No-Intro
name) and tools/project64.rdb (Project64's game list: names and internal names -> header CRCs), to
place libretro's files, which are named after the game, not keyed by checksum (README: Placing
libretro's files).
"""
import difflib, glob, json, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "sources")
DIST = os.path.join(ROOT, "dist")
JOEY = os.path.join(ROOT, "joey64")

CODE = re.compile(r"^([0-9A-Fa-f]{8}) ([0-9A-Fa-f?]{4})$")
# Codes Joey64 can't run as they are (README: Flags).
GS_BUTTON = ("88", "89", "A8", "A9", "D8", "D9", "DA", "DB")
BOOT = ("F0", "F1", "FF", "EE")
# Codes that belong in their own menu spots, not Cheats (Joey, 2026-11-06): the picture made
# wide, and the game run at 60 fps. Matched by name; "always off" ones turn a game's own
# widescreen off, and stay cheats.
WIDESCREEN = re.compile(r"wide ?screen|anamorphic|16[-:x]9", re.I)
SIXTY = re.compile(r"\b60 ?fps\b|\bsixty (frames|hack)|\bfifty frames|\b60 ?frames", re.I)
# A libretro list with more than this many cheats of one name pattern ("Soldier #42") is a bulk
# list: left out, and counted in the file's "left_out".
BULK = 40

SOURCES = {
    "project64": "GPL-2.0-only",
    "rmg-custom": "GPL-3.0-only",
    "fz-retroben": "GPL-3.0-or-later",
    "libretro": "CC-BY-SA-4.0",
    "joey64": "GPL-3.0-or-later",
}


def key_of(raw):
    m = re.match(r"\s*([0-9A-Fa-f]{8})-([0-9A-Fa-f]{8})(?:-C:([0-9A-Fa-f]{2}))?", raw)
    if not m:
        return None
    k = f"{m.group(1).upper()}-{m.group(2).upper()}"
    return f"{k}-{m.group(3).upper()}" if m.group(3) else k


def flags(codes, options, name=""):
    f = []
    leaf = name.split("\\")[-1]
    if WIDESCREEN.search(leaf) and "always off" not in leaf.lower():
        f.append("widescreen")
    if SIXTY.search(leaf):
        f.append("60fps")
    heads = [c[:2].upper() for c in codes]
    if any(h in GS_BUTTON for h in heads):
        f.append("gs_button")
    if any(h in BOOT for h in heads):
        f.append("boot")
    if any("?" in c[9:] or "X" in c[9:].upper() for c in codes) and not options:
        f.append("needs_value")
    return f


def cheat(name, codes, options=None, note=None):
    codes = [c.upper().replace("X", "?") if "X" in c[9:].upper() else c.upper() for c in codes]
    c = {"name": name.strip(), "codes": codes}
    if options:
        c["options"] = [[v.upper(), label.strip()] for v, label in options]
    if note:
        c["note"] = note.strip()
    fl = flags(codes, options, name)
    if fl:
        c["flags"] = fl
    return c


def parse_pj64(text):
    """Project64 / RMG .cht: [CRC1-CRC2-C:CC], Name=, then $Folder\\Name, codes, 'XX Label' options, Note=."""
    games = {}
    for blk in re.split(r"^\[", text, flags=re.M)[1:]:
        head, _, body = blk.partition("\n")
        key = key_of(head)
        if not key:
            continue
        g = games.setdefault(key, {"name": None, "cheats": []})
        cur = None
        for line in body.split("\n"):
            line = line.strip()
            if line.startswith("Name=") and g["name"] is None:
                g["name"] = line[5:].strip()
            elif line.startswith("$"):
                cur = {"name": line[1:], "codes": [], "options": [], "note": None}
                g["cheats"].append(cur)
            elif cur is None or not line:
                continue
            elif CODE.match(line[:13]) and (len(line) == 13 or line[13] == " "):
                # An option row ("0D Double Mushroom", "0001 1 Lap") never has 8 hex digits first.
                cur["codes"].append(line[:13])
            elif re.match(r"^[0-9A-Fa-f]{2,4} ", line) and cur["codes"]:
                v, _, label = line.partition(" ")
                cur["options"].append((v, label))
            elif line.startswith("Note="):
                cur["note"] = line[5:]
        g["cheats"] = [cheat(c["name"], c["codes"], c["options"], c["note"]) for c in g["cheats"] if c["codes"]]
    return games


def parse_mupen(text):
    """mupencheat.txt: crc / gn / cn / cd / indented codes with 'VV:"Label",...' options."""
    games = {}
    g = cur = None
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        s = line.strip()
        if line.startswith("crc "):
            key = key_of(line[4:])
            g = games.setdefault(key, {"name": None, "cheats": []})
            cur = None
        elif line.startswith("gn ") and g is not None:
            g["name"] = line[3:].strip()
        elif s.startswith("cn ") and g is not None:
            cur = {"name": s[3:], "codes": [], "options": [], "note": None}
            g["cheats"].append(cur)
        elif s.startswith("cd ") and cur is not None:
            cur["note"] = s[3:]
        elif cur is not None and CODE.match(s[:13]):
            cur["codes"].append(s[:13])
            rest = s[13:].strip()
            if rest:
                cur["options"] += re.findall(r'([0-9A-Fa-f]{2,4}):"([^"]*)"', rest)
    for g in games.values():
        g["cheats"] = [cheat(c["name"], c["codes"], c["options"], c["note"]) for c in g["cheats"] if c["codes"]]
    return games


def parse_libretro(text):
    """libretro .cht: cheatN_desc / cheatN_code ("A B;C D" or "+"), no value options."""
    vals = dict(re.findall(r'^(\w+)\s*=\s*"?(.*?)"?\s*$', text, flags=re.M))
    n = int(vals.get("cheats", "0") or 0)
    out = []
    for i in range(n):
        name = vals.get(f"cheat{i}_desc", "").strip()
        code = vals.get(f"cheat{i}_code", "")
        parts = re.findall(r"([0-9A-Fa-f]{8})[ :]?([0-9A-Fa-fXx?]{4})", code)
        if not name or not parts:
            continue
        out.append(cheat(name, [f"{a} {b}" for a, b in parts]))
    return out


def drop_bulk(cheats):
    groups = {}
    for c in cheats:
        groups.setdefault(re.sub(r"\d+", "#", c["name"]), []).append(c)
    bulk = {p for p, cs in groups.items() if len(cs) > BULK}
    kept = [c for c in cheats if re.sub(r"\d+", "#", c["name"]) not in bulk]
    return kept, len(cheats) - len(kept)


def good_names():
    """GoodN64 names (mupen64plus.ini) and No-Intro names (n64-names.tsv) -> header keys."""
    ini = open(os.path.join(ROOT, "tools", "mupen64plus.ini"), encoding="utf-8", errors="replace").read()
    by_md5, by_name = {}, {}
    for md5, body in re.findall(r"^\[([0-9A-Fa-f]{32})\]\n(.*?)(?=^\[|\Z)", ini, flags=re.M | re.S):
        name = re.search(r"^GoodName=(.*)$", body, flags=re.M)
        crc = re.search(r"^CRC=([0-9A-Fa-f]{8}) ([0-9A-Fa-f]{8})", body, flags=re.M)
        if not crc:
            continue
        k = f"{crc.group(1).upper()}-{crc.group(2).upper()}"
        by_md5[md5.lower()] = k
        if name:
            n = name.group(1).strip()
            by_name.setdefault(n, k)
            by_name.setdefault(re.sub(r"\s*\[[^\]]*\]", "", n).strip(), k)
    for line in open(os.path.join(ROOT, "tools", "n64-names.tsv"), encoding="utf-8"):
        if line.startswith("#") or "\t" not in line:
            continue
        md5, name = line.rstrip("\n").split("\t", 1)
        if md5.lower() in by_md5:
            by_name.setdefault(name, by_md5[md5.lower()])
    return by_name


REGION = [
    (r"\(japan, usa\)", "(ju)"), (r"\(usa, europe\)", "(ue)"), (r"\(usa\)", "(u)"), (r"\(europe\)", "(e)"),
    (r"\(japan\)", "(j)"), (r"\(germany\)", "(g)"), (r"\(france\)", "(f)"), (r"\(italy\)", "(i)"),
    (r"\(spain\)", "(s)"), (r"\(australia\)", "(a)"), (r"\(korea\)", "(k)"), (r"\(brazil\)", "(b)"),
]


def norm(name):
    """A game name as it's compared: GoodN64's "(U) (V1.1)", No-Intro's "(USA) (Rev A)" and libretro's
    "(U) v1.1" alike; no dump marks, language lists, "the", "and" / "&", spaces or punctuation."""
    n = name.lower()
    n = re.sub(r"\[[^\]]*\]", "", n)
    for a, b in REGION:
        n = re.sub(a, b, n)
    n = re.sub(r"\((?:en|ja|fr|de|es|it|nl|pt|sv|no|da|fi)(?:,[a-z]{2})*\)", "", n)
    n = re.sub(r"\(m\d\)", "", n)
    n = re.sub(r"\((?:v ?1\.0|rev 0)\)", "", n)
    n = re.sub(r"\(rev a\)", "(v1.1)", n)
    n = re.sub(r"\(rev (\d)\)", lambda m: f"(v1.{m.group(1)})", n)
    n = re.sub(r"\(v?(\d)\.(\d)\)", r"(v\1.\2)", n)
    n = re.sub(r"\bv(\d\.\d)\b", r"(v\1)", n)
    n = n.replace("(v1.0)", "")
    n = n.replace("&", "and").replace(" _ ", " and ")
    n = re.sub(r"\b(?:the|and)\b", "", n)
    return re.sub(r"[^a-z0-9()]+", "", n)


def rdb_entries():
    """Project64.rdb's games: (key "CRC1-CRC2", Good Name, Internal Name)."""
    out, cur = [], None
    for line in open(os.path.join(ROOT, "tools", "project64.rdb"), encoding="utf-8", errors="replace"):
        line = line.strip()
        m = re.match(r"^\[([0-9A-F]{8})-([0-9A-F]{8})-C:[0-9A-F]{2}\]$", line, re.I)
        if m:
            cur = {"key": f"{m.group(1).upper()}-{m.group(2).upper()}"}
            out.append(cur)
        elif cur is not None and "=" in line:
            k, v = line.split("=", 1)
            if k == "Good Name": cur["good"] = v.strip()
            if k == "Internal Name": cur["internal"] = re.sub(r"\s+", " ", v.upper()).strip()
    return out


def addresses(codes):
    return {c.split()[0][2:].upper() for c in codes if len(c.split()[0]) == 8}


def split_region(n):
    m = re.search(r"\(([a-z]{1,2})\)", n)
    return re.sub(r"\([^)]*\)", "", n), m.group(1) if m else "", re.findall(r"\(v\d+\)", n)


def near_names(n, by_norm):
    """Keys of the names closest to [n] with its country and version, when one is within a few
    letters ("Mace - The Dark Ages" for "Mace - The Dark Age"). Plain names only: no "(Beta)"."""
    base, reg, ver = split_region(n)
    if not reg:
        return set()
    best, out = 0.0, set()
    for k, keys in by_norm.items():
        b2, r2, v2 = split_region(k)
        if r2 != reg or v2 != ver or "(" in re.sub(r"\((?:[a-z]{1,2}|v\d+)\)", "", k):
            continue
        r = difflib.SequenceMatcher(None, base, b2).ratio()
        if r > best:
            best, out = r, set(keys)
        elif r == best:
            out |= keys
    return out if best >= 0.85 else set()


class Placer:
    """
    Finds the game a libretro file is for (README: Placing libretro's files): its name as one of
    the tables gives it; else Project64's internal name; else a near name. Every guess is checked
    against the other sources' codes for that game: the share of the file's code addresses they
    also poke. A name match is kept unless it shares none (the others have cheats there, none at
    the same places: another version). An internal name or near name needs half its addresses
    shared. Two games that fit as well leave the file unplaced.
    """

    def __init__(self, names, found):
        self.exact = names
        self.by_norm, self.by_internal = {}, {}
        for n, k in names.items():
            self.by_norm.setdefault(norm(n), set()).add(k)
        for e in rdb_entries():
            if e.get("good"):
                self.by_norm.setdefault(norm(e["good"]), set()).add(e["key"])
            if e.get("internal"):
                self.by_internal.setdefault(e["internal"], set()).add(e["key"])
        self.others = {}
        for src in ("project64", "rmg-custom", "fz-retroben"):
            for k, g in found[src].items():
                s = self.others.setdefault("-".join(k.split("-")[:2]), set())
                for c in g["cheats"]:
                    s |= addresses(c["codes"])

    def place(self, title, cheats):
        k = self.exact.get(title) or self.exact.get(re.sub(r"\s*\[[^\]]*\]", "", title).strip())
        if k:
            return k, True
        n = norm(title)
        if n in self.by_norm:
            how, cands = "name", self.by_norm[n]
        elif re.sub(r"\s+", " ", title.upper()).strip() in self.by_internal:
            how, cands = "internal", self.by_internal[re.sub(r"\s+", " ", title.upper()).strip()]
        else:
            how, cands = "near", near_names(n, self.by_norm)
        mine = set()
        for c in cheats:
            mine |= addresses(c["codes"])
        scored = []
        for k in cands:
            o = self.others.get(k)
            scored.append((len(mine & o) / len(mine) if mine and o else -1.0, k))
        scored.sort(reverse=True)
        if not scored or (len(scored) > 1 and scored[0][0] <= scored[1][0]):
            return None, False
        share, k = scored[0]
        if share == 0 or (how != "name" and share < 0.5):
            return None, False
        return k, False


def main():
    found = {s: {} for s in SOURCES}
    report = []

    for f in sorted(glob.glob(os.path.join(SRC, "project64", "*.cht"))):
        found["project64"].update(parse_pj64(open(f, encoding="utf-8", errors="replace").read()))
    # Project64's Enhancements (Config/Enhancements/*.enh, the same .cht format): only its widescreen
    # and frame-rate codes are taken, for their own menu spots. Its other enhancements are fixes
    # Project64 applies for its own plugins (OnByDefault, PluginList) and aren't cheats.
    for f in sorted(glob.glob(os.path.join(SRC, "project64", "enhancements", "*.enh"))):
        for k, g in parse_pj64(open(f, encoding="utf-8", errors="replace").read()).items():
            keep = [c for c in g["cheats"] if {"widescreen", "60fps"} & set(c.get("flags", []))]
            if not keep:
                continue
            have = found["project64"].setdefault(k, {"name": g["name"], "cheats": []})
            seen = {c["name"] for c in have["cheats"]}
            have["cheats"] += [c for c in keep if c["name"] not in seen]
    for f in sorted(glob.glob(os.path.join(SRC, "rmg-custom", "*.cht"))):
        found["rmg-custom"].update(parse_pj64(open(f, encoding="utf-8", errors="replace").read()))
    for f in sorted(glob.glob(os.path.join(SRC, "fz-retroben", "*.txt"))):
        found["fz-retroben"].update(parse_mupen(open(f, encoding="utf-8", errors="replace").read()))
    for f in sorted(glob.glob(os.path.join(JOEY, "*.txt"))):
        found["joey64"].update(parse_mupen(open(f, encoding="utf-8", errors="replace").read()))

    placer = Placer(good_names(), found)
    unplaced = []
    left_out_total = 0
    placed = []
    for f in sorted(glob.glob(os.path.join(SRC, "libretro", "*.cht"))):
        title = os.path.splitext(os.path.basename(f))[0]
        cheats = parse_libretro(open(f, encoding="utf-8", errors="replace").read())
        k, exact = placer.place(title, cheats)
        if k:
            placed.append((not exact, title, k, cheats))
        else:
            unplaced.append(title)
    # Files found by their exact name first: the game is called by that name, and its cheats come first.
    for _, title, k, cheats in sorted(placed, key=lambda p: p[:2]):
        cheats, left = drop_bulk(cheats)
        left_out_total += left
        if not cheats:
            continue
        g = found["libretro"].setdefault(k, {"name": title, "cheats": [], "left_out": 0})
        seen = {c["name"] for c in g["cheats"]}
        g["cheats"] += [c for c in cheats if c["name"] not in seen]
        g["left_out"] += left

    # libretro's and other country-less keys join the game's full key when one source has it.
    full = {}
    for games in found.values():
        for k in games:
            if k.count("-") == 2:
                full.setdefault(k.rsplit("-", 1)[0], set()).add(k)
    for games in found.values():
        for k in [k for k in games if k.count("-") == 1 and len(full.get(k, ())) == 1]:
            to = next(iter(full[k]))
            if to not in games:
                games[to] = games.pop(k)

    if os.path.isdir(DIST):
        for f in glob.glob(os.path.join(DIST, "*", "*.json")) + glob.glob(os.path.join(DIST, "*.json")):
            os.remove(f)
    index = {}
    for src, games in found.items():
        if not games:
            continue
        os.makedirs(os.path.join(DIST, src), exist_ok=True)
        for k, g in sorted(games.items()):
            if not g["cheats"]:
                continue
            out = {"source": src, "license": SOURCES[src], "key": k, "game": g["name"], "cheats": g["cheats"]}
            if g.get("left_out"):
                out["left_out"] = g["left_out"]
            with open(os.path.join(DIST, src, k + ".json"), "w", encoding="utf-8", newline="\n") as fh:
                json.dump(out, fh, ensure_ascii=False, separators=(",", ":"))
            e = index.setdefault(k, {"game": g["name"], "sources": {}})
            e["sources"][src] = len(g["cheats"])
            extras = sorted({f for c in g["cheats"] for f in c.get("flags", []) if f in ("widescreen", "60fps")})
            if extras:
                e["extras"] = sorted(set(e.get("extras", [])) | set(extras))
            if not e["game"]:
                e["game"] = g["name"]
        report.append(f"{src:12s} {len(games):5d} games {sum(len(g['cheats']) for g in games.values()):7d} cheats")

    with open(os.path.join(DIST, "index.json"), "w", encoding="utf-8", newline="\n") as fh:
        json.dump({"format": 1, "games": dict(sorted(index.items()))}, fh, ensure_ascii=False, separators=(",", ":"))
    report.append(f"index        {len(index):5d} keys; libretro: {len(unplaced)} files with no matching game, {left_out_total} bulk cheats left out")
    with open(os.path.join(ROOT, "tools", "unplaced-libretro.txt"), "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(unplaced) + "\n")
    print("\n".join(report))


if __name__ == "__main__":
    sys.exit(main())
