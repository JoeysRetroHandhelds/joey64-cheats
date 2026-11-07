"""sheet.py <shots dir> <game num> [names...]: one picture per game. Base shown 4:3, each code shown
stretched to 16:9 (what a widescreen screen would show), labelled, with how much it differs from base."""
import sys, os, glob
from PIL import Image, ImageDraw, ImageChops, ImageStat
d, num = sys.argv[1], sys.argv[2]
files = sorted(glob.glob(os.path.join(d, num + '_*.png')))
names = [os.path.basename(f)[len(num) + 1:-4] for f in files]
if len(sys.argv) > 3:
    keep = sys.argv[3:]; files = [f for f, n in zip(files, names) if n in keep]; names = [n for n in names if n in keep]
def game_area(im):
    # the 4:3 picture in the middle of the screen: crop pillarbox by non-black columns
    g = im.convert('L'); w, h = g.size
    cols = [x for x in range(w) if max(g.crop((x, 0, x + 1, h)).getextrema()) > 8]
    rows = [y for y in range(h) if max(g.crop((0, y, w, y + 1)).getextrema()) > 8]
    return im.crop((cols[0], rows[0], cols[-1] + 1, rows[-1] + 1)) if cols and rows else im
base = game_area(Image.open(files[names.index('base')]).convert('RGB')) if 'base' in names else None
H = 270; tiles = []
for f, n in zip(files, names):
    im = game_area(Image.open(f).convert('RGB'))
    diff = ''
    if base is not None and n != 'base':
        a = im.resize((160, 120)); b = base.resize((160, 120))
        diff = ' diff %.0f' % sum(ImageStat.Stat(ImageChops.difference(a, b)).mean)
    w = int(H * (4 / 3 if n == 'base' else 16 / 9))
    t = Image.new('RGB', (w, H + 24), (20, 20, 30)); t.paste(im.resize((w, H)), (0, 24))
    ImageDraw.Draw(t).text((6, 5), n + diff, fill=(255, 255, 255))
    tiles.append(t)
cols = 3; rows = (len(tiles) + cols - 1) // cols
W = max(t.width for t in tiles)
out = Image.new('RGB', (cols * (W + 8), rows * (H + 32)), (0, 0, 0))
for i, t in enumerate(tiles):
    out.paste(t, ((i % cols) * (W + 8), (i // cols) * (H + 32)))
out.save(os.path.join(d, 'sheet_%s.png' % num))
print(os.path.join(d, 'sheet_%s.png' % num), names)
