#!/usr/bin/env python3
"""compat-page.py: builds compat/games.json, the data behind the compatibility page (compat/page.html), from
Joey64's test runs, and writes compat/index.html (page.html in a full document, for static hosting).

Inputs (all read-only):
  --results  the device runs' results folder (scratchpad compat/results): fullattract/ (times-<dev>.tsv,
             states/*.proj3, keyed-<dev>.tsv, claims/) and the 82-game compat runs (<run>/status.tsv)
  --map      fullmap.tsv: n, zip, No-Intro name, "compat" for games in the compat set
  --roms     the test library (BigEndian .z64 zips); only the first 64 bytes and the MD5 of each ROM are read
  --gamedb   joey64/gamedb/games.json (per-game settings and issues)
  --app      the joey64 checkout (per-game lists in the app's code: own 16:9 modes, Expansion Pak)
Kept in this repo: compat/notes.tsv (hand-written status and notes, by No-Intro name), tools/mupen64plus.ini
(players, save type, paks by MD5), dist/ and joey64/widescreen.txt (widescreen and 60 fps codes).

Statuses: runs (passed the scripted in-game check, or a 3D scene was seen), starts (draws, no 3D seen yet),
broken (crashes, hangs or draws wrong), notyet (not run yet). notes.tsv overrides any of them.
"""
import argparse, glob, hashlib, json, os, re, zipfile, datetime

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEVICES = {
    'o3p': {'name': 'Odin 3 Portal', 'gpu': 'Adreno 830', 'family': 'Adreno 8xx'},
    'o2p': {'name': 'Odin 2 Portal', 'gpu': 'Adreno 740', 'family': 'Adreno 7xx'},
    'duo': {'name': 'Retroid Pocket Duo', 'gpu': 'Adreno 722', 'family': 'Adreno 7xx'},
    'flip': {'name': 'Retroid Pocket Flip', 'gpu': 'Mali-G52', 'family': 'Mali'},
}
# The 82-game compat runs that count, per device (later runs of a device win per game).
COMPAT_RUNS = [
    ('o3p', 'o3p-audit3-compat'), ('flip', 'flip-lists2-compat'), ('flip', 'flip-rel1-44'),
    ('duo', 'duo-rel1-compat'), ('duo', 'duo-rel2-compat'),
    ('o2p', 'odin2p-cf30-compat'), ('o2p', 'odin2p-cf30-rerun'),
    # 2026-11-12: main 3a5caf0 (core rel2 247364e)
    ('flip', 'flip-golf-compat'), ('duo', 'duo-golf-compat'), ('o2p', 'o2p-golf-compat'),
]
REGIONS = ['USA', 'Europe', 'Japan', 'World', 'Germany', 'France', 'Spain', 'Italy', 'Australia', 'Brazil', 'Korea',
           'China', 'Netherlands', 'Sweden', 'Canada', 'Asia', 'UK', 'Scandinavia']
CHEAT_CARTS = re.compile(r'GameShark|Game Shark|Action Replay|GameBooster|Game Booster|Xplorer|Equalizer|Game Buster|'
                         r'Datel|Code Breaker|Gamebuster', re.I)
WS_NAME = re.compile(r'wide ?screen|16[:x/]9', re.I)
FPS_NAME = re.compile(r'\b60 ?fps\b|\b60fps|\b60 ?hz\b', re.I)


def tsv(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding='utf-8') as f:
        return [l.rstrip('\r\n').split('\t') for l in f if l.strip()]


def parse_name(stem):
    """No-Intro name -> title, region, tags, type, bad dump."""
    m = re.match(r'^([^(\[]+?)\s*((?:[(\[].*)?)$', stem)
    title, rest = (m.group(1).strip(), m.group(2)) if m else (stem, '')
    tags = re.findall(r'\(([^)]*)\)', rest)
    bad = '[b]' in rest
    t = re.match(r'^(.*), The( - .*)?$', title)
    if t:
        title = 'The ' + t.group(1) + (t.group(2) or '')
    region = ''
    for tg in tags:
        parts = [p.strip() for p in tg.split(',')]
        if parts and all(p in REGIONS for p in parts):
            region = tg
            break
    low = ' '.join(tags).lower()
    if CHEAT_CARTS.search(stem):
        kind = 'Cheat cart'
    elif 'hack' in low:
        kind = 'Hack'
    elif 'aftermarket' in low or ('unl' in low.split() and 'beta' not in low) or 'homebrew' in low:
        kind = 'Homebrew'
    elif 'beta' in low or 'proto' in low:
        kind = 'Beta'
    elif 'demo' in low or 'kiosk' in low or 'sample' in low:
        kind = 'Demo'
    elif 'debug' in low:
        kind = 'Debug'
    elif 'test program' in low or 'program' in low:
        kind = 'Test cart'
    elif 'add-on' in low:
        kind = 'Add-on'
    else:
        kind = 'Retail'
    other = [tg for tg in tags if tg != region and not re.fullmatch(r'(En|Fr|De|Es|It|Nl|Sv|No|Da|Fi|Pt|Ja|Zh|Ko|Pl)(,\s*\w\w)*', tg)]
    langs = next((tg for tg in tags if re.fullmatch(r'(En|Fr|De|Es|It|Nl|Sv|No|Da|Fi|Pt|Ja|Zh|Ko|Pl)(,\s*\w\w)+', tg)), '')
    return {'title': title, 'region': region, 'tags': other, 'langs': langs, 'type': kind, 'bad': bad}


def rom_info(path, cache):
    st = os.stat(path)
    key = os.path.basename(path)
    c = cache.get(key)
    if c and c.get('size') == st.st_size and c.get('mtime') == int(st.st_mtime):
        return c
    with zipfile.ZipFile(path) as z:
        names = [n for n in z.namelist() if not n.endswith('/')]
        data = z.read(names[0])
    h = data[:64]
    info = {'size': st.st_size, 'mtime': int(st.st_mtime), 'md5': hashlib.md5(data).hexdigest().upper(),
            'crc1': h[0x10:0x14].hex().upper(), 'crc2': h[0x14:0x18].hex().upper(),
            'code': h[0x3B:0x3F].decode('latin-1'), 'cc': h[0x3E]}
    cache[key] = info
    return info


def load_ini(path):
    out, cur = {}, None
    with open(path, encoding='utf-8', errors='replace') as f:
        for line in f:
            line = line.strip()
            m = re.match(r'^\[([0-9A-Fa-f]{32})\]$', line)
            if m:
                cur = out.setdefault(m.group(1).upper(), {})
            elif cur is not None and '=' in line:
                k, v = line.split('=', 1)
                cur[k.strip()] = v.strip()
    for md5, e in out.items():  # RefMD5: inherit the referenced entry's fields
        ref = e.get('RefMD5', '').upper()
        if ref in out:
            for k, v in out[ref].items():
                e.setdefault(k, v)
    return out


def load_cheats():
    idx = json.load(open(os.path.join(HERE, 'dist', 'index.json'), encoding='utf-8'))['games']
    names = {}
    for key, g in idx.items():
        n = []
        for src in g['sources']:
            p = os.path.join(HERE, 'dist', src, key + '.json')
            if os.path.exists(p):
                n += [c.get('name', '') for c in json.load(open(p, encoding='utf-8')).get('cheats', [])]
        names[key.upper()] = n
    ours = set()
    wsf = os.path.join(HERE, 'joey64', 'widescreen.txt')
    if os.path.exists(wsf):
        for line in open(wsf, encoding='utf-8'):
            m = re.match(r'^crc ([0-9A-F]{8})-([0-9A-F]{8})', line.strip(), re.I)
            if m:
                ours.add((m.group(1).upper(), m.group(2).upper()))
    return names, ours


def app_lists(app):
    def ids(rel, start):
        p = os.path.join(app, rel)
        if not os.path.exists(p):
            return {}
        t = open(p, encoding='utf-8').read()
        i = t.find(start)
        seg = t[i:i + 3000] if i >= 0 else ''
        return dict(re.findall(r'"(N[A-Z0-9]{2})" to "([^"]*)"', seg)) or {k: '' for k in re.findall(r'"(N[A-Z0-9]{2})"', seg[:400])}
    own = ids('app/src/main/java/com/joeysretro/joey64/video/GameExtras.kt', 'object OwnWidescreen')
    exp = {}
    for f in glob.glob(os.path.join(app, 'app/src/main/java/**/*.kt'), recursive=True):
        t = open(f, encoding='utf-8').read()
        m = re.search(r'NEEDED_BY = setOf\(([^)]*)\)', t)
        if m:
            exp = {k: '' for k in re.findall(r'"(N[A-Z0-9]{2})"', m.group(1))}
            break
    return own, exp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--results', required=True)
    ap.add_argument('--map', required=True)
    ap.add_argument('--roms', required=True)
    ap.add_argument('--gamedb', required=True)
    ap.add_argument('--app', required=True)
    ap.add_argument('--cache', help='ROM header cache (JSON), kept between runs')
    ap.add_argument('--build', default='', help='the app build the results come from, for the page header')
    a = ap.parse_args()

    cache = json.load(open(a.cache, encoding='utf-8')) if a.cache and os.path.exists(a.cache) else {}
    ini = load_ini(os.path.join(HERE, 'tools', 'mupen64plus.ini'))
    cheats, ours = load_cheats()
    own16, exppak = app_lists(a.app)
    gamedb = json.load(open(a.gamedb, encoding='utf-8'))['games']
    notes = {r[0]: r[1:] for r in tsv(os.path.join(HERE, 'compat', 'notes.tsv')) if r and not r[0].startswith('#')}

    fa = os.path.join(a.results, 'fullattract')
    times, keyed = {}, {}
    for dev in DEVICES:
        for r in tsv(os.path.join(fa, 'times-%s.tsv' % dev))[1:]:
            if len(r) >= 7:
                times[r[0]] = {'secs': r[2], 'fps': r[3], 'states': r[4], 'end': r[5], 'dev': r[6]}
        for r in tsv(os.path.join(fa, 'keyed-%s.tsv' % dev))[1:]:
            if len(r) >= 4:
                keyed[r[0]] = {'status': r[1], 'k3': int(r[3] or 0), 'dev': dev}
    proj = {}
    for p in glob.glob(os.path.join(fa, 'states', '*.proj3')):
        n = os.path.basename(p).split('-')[0]
        proj.setdefault(n, [0, 0])
        proj[n][1] += 1
        if 'ratio' in open(p, encoding='utf-8', errors='replace').read():
            proj[n][0] += 1
    compat = {}  # name -> {dev: status}
    for dev, run in COMPAT_RUNS:
        for r in tsv(os.path.join(a.results, run, 'status.tsv')):
            if len(r) >= 3:
                compat.setdefault(r[2], {})[dev] = r[1]

    games, seen = [], set()
    rows = tsv(a.map)
    for r in rows + [[None, None, name, 'compat-only'] for name in compat]:
        n, zf, stem = r[0], r[1], r[2]
        flag = r[3] if len(r) > 3 else ''
        if stem in seen:
            continue
        seen.add(stem)
        nm = parse_name(stem)
        g = {'name': stem, 'title': nm['title'], 'region': nm['region'], 'tags': nm['tags'], 'langs': nm['langs'],
             'type': nm['type'], 'bad': nm['bad'], 'on': [], 'set': [], 'iss': []}
        info = None
        if zf:
            try:
                info = rom_info(os.path.join(a.roms, zf), cache)
            except Exception as e:
                g['iss'].append('ROM not read: %s' % e)
            if a.cache and len(cache) % 100 == 0:
                json.dump(cache, open(a.cache, 'w', encoding='utf-8'))
        code = info['code'][1:3] if info else ''
        gid = ('N' + code) if info else ''
        if info:
            e = ini.get(info['md5'], {})
            g['players'] = e.get('Players', '')
            g['save'] = e.get('SaveType', '')
            g['paks'] = [p for p, k in (('Controller Pak', 'Mempak'), ('Rumble Pak', 'Rumble'), ('Transfer Pak', 'Transferpak'))
                         if e.get(k, '').lower() == 'yes']
            key = '%s-%s-%02X' % (info['crc1'], info['crc2'], info['cc'])
            cn = cheats.get(key) or cheats.get('%s-%s' % (info['crc1'], info['crc2'])) or []
            ws = any(WS_NAME.search(x) for x in cn) or (info['crc1'], info['crc2']) in ours
            g['ws'] = 'own' if gid in own16 else ('code' if ws else '')
            if gid in own16 and own16[gid]:
                g['wsWhere'] = own16[gid].split(', ', 1)[-1]
            g['f60'] = any(FPS_NAME.search(x) for x in cn)
            g['exp'] = gid in exppak
            for d in gamedb:
                if d.get('id') == gid and (not d.get('crc') or d['crc'].upper() == info['crc1'] + info['crc2']):
                    g['set'] += [s['what'] for s in d.get('settings', [])]
        else:
            g.update({'players': '', 'save': '', 'paks': [], 'ws': '', 'f60': False, 'exp': False})
        # status
        cs = compat.get(stem, {})
        t = times.get(n) if n else None
        st, ev = 'notyet', ''
        if cs:
            okd = [d for d, s in cs.items() if s == 'ok']
            g['on'] = sorted(okd, key=list(DEVICES).index)
            if okd:
                st = 'runs'
                ev = 'Passed the scripted in-game check (button presses, frames compared with reference) on ' + \
                     ', '.join(DEVICES[d]['name'] for d in g['on']) + '.'
            else:
                st, ev = 'broken', 'Failed the scripted in-game check.'
        if t and st == 'notyet':
            g['on'] = [t['dev']]
            y = proj.get(n, [0, 0])
            k = keyed.get(n)
            if t['end'] == 'ok':
                if y[0] > 0:
                    st, ev = 'runs', 'Started with no buttons pressed; a 3D scene was seen in its first 150 s.'
                elif k and k['k3'] > 0:
                    st, ev = 'runs', 'No 3D in its intro; with scripted button presses a 3D scene was seen.'
                else:
                    st = 'starts'
                    ev = ('Draws, but no 3D scene was seen, even with scripted button presses.' if k else
                          'Draws, but no 3D scene in its first 150 s without input; the pass with button presses comes next.')
            elif t['end'].startswith('died'):
                st, ev = 'broken', 'The app closed %s s in.' % t['end'].split('@')[-1]
            else:
                st, ev = 'broken', 'No progress in 300 s.'
        if t and t['fps'].isdigit():
            g['fps'], g['fpsDev'] = int(t['fps']), t['dev']
        nt = notes.get(stem)
        if nt:
            if nt[0]:
                st = nt[0]
            if len(nt) > 1 and nt[1]:
                g['note'] = nt[1]
        g['status'], g['ev'] = st, ev
        if flag == 'compat-only':
            g['type'] = g['type'] if g['type'] != 'Retail' else 'Hack'
        games.append(g)

    games.sort(key=lambda g: (re.sub(r'^the ', '', g['title'].lower()), g['region'], g['name']))
    out = {'generated': datetime.date.today().isoformat(), 'build': a.build, 'devices': DEVICES,
           'counts': {s: sum(1 for g in games if g['status'] == s) for s in ('runs', 'starts', 'broken', 'notyet')},
           'games': games}
    os.makedirs(os.path.join(HERE, 'compat'), exist_ok=True)
    with open(os.path.join(HERE, 'compat', 'games.json'), 'w', encoding='utf-8', newline='\n') as f:
        json.dump(out, f, ensure_ascii=False, separators=(',', ':'))
    page = os.path.join(HERE, 'compat', 'page.html')
    if os.path.exists(page):
        body = open(page, encoding='utf-8').read()
        with open(os.path.join(HERE, 'compat', 'index.html'), 'w', encoding='utf-8', newline='\n') as f:
            f.write('<!doctype html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
                    '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
                    '</head>\n<body>\n' + body + '\n</body>\n</html>\n')
    if a.cache:
        json.dump(cache, open(a.cache, 'w', encoding='utf-8'))
    print(len(games), 'games', out['counts'])


if __name__ == '__main__':
    main()
