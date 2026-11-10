"""60 fps finder (work order item 34, 2026-11-10). fps-finder.py <state.raw> [more states...]
RDRAM from a mupen64plus M64+SAVE state (as widescreen-finder.py), then libultra's video contexts:
  1. OSViMode tables, found by their NTSC / PAL / MPAL colour burst and sync words (comRegs.burst at +0x0C,
     vSync +0x10, hSync +0x14, leap +0x18, hStart +0x1C).
  2. OSViContext structs pointing at one of them (modep at +0x08): libultra keeps two, __osViCurr and __osViNext,
     0x30 apart. Their u16 at +0x02 is retraceCount: the VI manager sends the game its frame message every
     retraceCount refreshes (osViSetEvent), so 2 = a 30 fps game, 3 = 20 fps.
  3. A candidate GameShark code that holds both retraceCounts at 1 (81xxxxxx 0001): the frame message comes every
     refresh. Many games then also run their logic twice as fast (they count frames, not time), so every
     candidate must be play-tested before it goes into joey64/; it is a lead, not a code."""
import struct, sys

def load(state):
    st = open(state, 'rb').read()
    assert st[:8] == b'M64+SAVE', state
    b = st[0x1BC:0x1BC + 0x800000]
    return b''.join(b[i:i + 4][::-1] for i in range(0, len(b), 4))  # big-endian RDRAM

# (name, burst, vSync values, hSync, leap, hStart) of the libultra mode tables
TV = [('NTSC', 0x03E52239, (0x20C, 0x20D), 0x00000C15, 0x0C150C15, 0x006C02EC),
      ('PAL',  0x0404233A, (0x270, 0x271), 0x00150C69, 0x0C6F0C6E, 0x00800300),
      ('MPAL', 0x04651E39, (0x20C, 0x20D), 0x00040C11, 0x0C190C1A, 0x006C02EC)]

def u32(ram, a): return struct.unpack_from('>I', ram, a)[0]
def u16(ram, a): return struct.unpack_from('>H', ram, a)[0]

def modes(ram):
    out = []
    for name, burst, vs, hs, leap, hst in TV:
        pat = struct.pack('>I', burst)
        a = ram.find(pat)
        while a >= 0:
            if a % 4 == 0 and a >= 0x0C and u32(ram, a + 4) in vs and u32(ram, a + 8) == hs and u32(ram, a + 12) == leap:
                out.append((a - 0x0C, name))
            a = ram.find(pat, a + 4)
    return out

def contexts(ram, mode_addrs):
    want = {0x80000000 | m: m for m, _ in mode_addrs}
    found = []
    for a in range(8, len(ram) - 0x30, 4):
        w = u32(ram, a)
        if w in want:
            ctx = a - 8
            rc = u16(ram, ctx + 2)
            fp = u32(ram, ctx + 4)
            if 1 <= rc <= 6 and (fp == 0 or 0x80000000 <= fp < 0x80800000):
                found.append((ctx, rc, want[w]))
    return found

def gs(addr, v): return '81%06X %04X' % (addr & 0xFFFFFF, v & 0xFFFF)

def report(path):
    ram = load(path)
    ms = modes(ram)
    cs = contexts(ram, ms)
    print('== %s' % path)
    print('  modes: %s' % (', '.join('%s @%06X' % (n, m) for m, n in ms[:6]) or 'none found'))
    if not cs:
        print('  contexts: none found'); return
    for ctx, rc, m in cs:
        print('  context @%06X retraceCount %d (mode @%06X)' % (ctx, rc, m))
    slow = [c for c in cs if c[1] >= 2]
    if slow:
        print('  candidate 60 fps code (both contexts held at 1): ' + ' / '.join(gs(c[0] + 2, 1) for c in cs))
    else:
        print('  retraceCount already 1: the game asks for every refresh (its rate is set elsewhere)')

if __name__ == '__main__':
    for p in sys.argv[1:]:
        report(p)
