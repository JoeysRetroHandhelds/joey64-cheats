"""
Writes boxart/index.tsv, the list of Joey64's own covers the app downloads (README: Box art).

    python tools/boxart-index.py

One line per boxart/<rom md5>.png: the ROM's MD5, the picture's own MD5 (the app fetches a cover
again when it changes) and the game's name. Names are kept from the index as it is; a new picture
gets its name from boxart/README.md's table. A line whose picture is gone is dropped.
"""
import glob, hashlib, os, re, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ART = os.path.join(ROOT, "boxart")
INDEX = os.path.join(ART, "index.tsv")
MD5 = re.compile(r"^[0-9a-f]{32}$")
HEADER = ("# Joey64's own covers (boxart/README.md), written by tools/boxart-index.py.\n"
          "# rom md5\tpicture md5\tgame; each picture is boxart/<rom md5>.png\n")


def main():
    names = {}
    if os.path.exists(INDEX):
        for line in open(INDEX, encoding="utf-8"):
            cols = line.rstrip("\n").split("\t")
            if len(cols) >= 3 and MD5.match(cols[0]):
                names[cols[0]] = cols[2]
    for line in open(os.path.join(ART, "README.md"), encoding="utf-8"):
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) >= 2 and MD5.match(cols[0]):
            names.setdefault(cols[0], cols[1])
    rows = []
    for f in sorted(glob.glob(os.path.join(ART, "*.png"))):
        rom = os.path.splitext(os.path.basename(f))[0]
        if not MD5.match(rom):
            sys.exit(f"{f}: not named <rom md5>.png")
        pic = hashlib.md5(open(f, "rb").read()).hexdigest()
        rows.append(f"{rom}\t{pic}\t{names.get(rom, '?')}\n")
    with open(INDEX, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(HEADER + "".join(rows))
    print(f"boxart/index.tsv: {len(rows)} covers")


if __name__ == "__main__":
    main()
