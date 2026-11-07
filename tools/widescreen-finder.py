"""Widescreen finder, pass 2. widescreen-finder.py <state.raw> [out.json]
RDRAM from a mupen64plus M64+SAVE state, then three kinds of candidate, best first:
  call  - guPerspective(F) call sites: libultra's guPerspectiveF is found by its pi/180 double, its
          fixed-point wrapper by calling it, and at each call the last instruction setting a3 (the
          aspect argument) is replaced with lui a3,0x3FE3 (1.7734, 16:9 rounded as Project64's SM64 code).
  data  - floats within 1.25..1.41 that code loads (lui + lwc1/lw at that address): x 4/3 in place.
  imm   - lui/ori|addiu pairs building such a float: x 4/3 in place.
Every candidate carries GameShark codes."""
import struct, sys, json

def load(state):
    st = open(state, 'rb').read()
    assert st[:8] == b'M64+SAVE'
    b = st[0x1BC:0x1BC + 0x800000]
    ram = b''.join(b[i:i + 4][::-1] for i in range(0, len(b), 4))
    return struct.unpack('>%dI' % (len(ram) // 4), ram)

def f32(w): return struct.unpack('>f', struct.pack('>I', w & 0xFFFFFFFF))[0]
def w32(f): return struct.unpack('>I', struct.pack('>f', f))[0]
def gs(addr, v): return '81%06X %04X' % (addr & 0xFFFFFF, v & 0xFFFF)
def A(i): return 0x80000000 + i * 4
def s16(x): return x - 0x10000 if x & 0x8000 else x
def rs(x): return (x >> 21) & 31
def rt(x): return (x >> 16) & 31
def op(x): return x >> 26
LUI, ORI, ADDIU, LW, LWC1, LDC1, JAL = 0x0F, 0x0D, 0x09, 0x23, 0x31, 0x35, 0x03

def refs_to(words, addr, ops=(LW, LWC1, LDC1)):
    """Indexes of loads reading addr through lui hi + load lo(base)."""
    hi = ((addr + 0x8000) >> 16) & 0xFFFF; lo = addr & 0xFFFF
    out = []
    for i, w in enumerate(words):
        if op(w) == LUI and (w & 0xFFFF) == hi:
            r = rt(w)
            for j in range(1, 12):
                if i + j >= len(words): break
                x = words[i + j]
                if op(x) in ops and rs(x) == r and (x & 0xFFFF) == lo:
                    out.append(i + j); break
    return out

def func_start(words, i):
    for k in range(i, max(i - 400, 0), -1):
        x = words[k]
        if op(x) == ADDIU and rs(x) == 29 and rt(x) == 29 and s16(x & 0xFFFF) < 0:
            return k
    return None

def callers(words, fi):
    target = 0x0C000000 | ((A(fi) >> 2) & 0x3FFFFFF)
    return [i for i, w in enumerate(words) if w == target]

def sets_a3(x):
    """Does instruction x write register a3 (7)?"""
    o = op(x)
    if o == 0 and ((x >> 11) & 31) == 7 and (x & 0x3F) not in (0x08, 0x09): return True  # SPECIAL rd
    if o in (0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F, 0x20, 0x21, 0x23, 0x24, 0x25) and rt(x) == 7: return True
    if o == 0x11 and rs(x) == 0x00 and rt(x) == 7: return True  # mfc1 a3
    return False

def call_sites(words):
    dbl = struct.pack('>d', 3.1415926 / 180.0)
    ram = struct.pack('>%dI' % len(words), *words)
    found = []
    i = ram.find(dbl)
    while i >= 0:
        for r in refs_to(words, 0x80000000 + i, ops=(LDC1,)):
            fs = func_start(words, r)
            if fs is not None: found.append(fs)
        i = ram.find(dbl, i + 1)
    out = []
    for fF in sorted(set(found)):
        sites = callers(words, fF)
        wrappers = []
        for s in sites:
            w = func_start(words, s)
            # guPerspective: short, calls guPerspectiveF and then guMtxF2L
            if w is not None and s - w < 40: wrappers.append(w)
        for fn in [fF] + sorted(set(wrappers)):
            for s in callers(words, fn):
                if fn == fF and func_start(words, s) in wrappers: continue
                # delay slot first, then backwards
                k = None
                if sets_a3(words[s + 1]): k = s + 1
                else:
                    for j in range(s - 1, max(s - 30, 0), -1):
                        if sets_a3(words[j]): k = j; break
                        if op(words[j]) in (0x02, 0x03) or (op(words[j]) == 0 and (words[j] & 0x3F) == 0x08): break
                if k is None: continue
                out.append({'kind': 'call', 'func': '%08X' % A(fn), 'site': '%08X' % A(s), 'addr': '%08X' % A(k),
                            'was': '%08X' % words[k], 'codes': [gs(A(k), 0x3C07), gs(A(k) + 2, 0x3FE3)]})
    return out

def data_imm(words):
    out = []
    for i, w in enumerate(words):
        if 0x3FA00000 <= w <= 0x3FB47AE1:
            a = A(i); r = refs_to(words, a, ops=(LW, LWC1))
            if r:
                nw = w32(f32(w) * 4 / 3)
                out.append({'kind': 'data', 'addr': '%08X' % a, 'value': round(f32(w), 6), 'loads': len(r),
                            'codes': [gs(a, nw >> 16), gs(a + 2, nw)]})
    for i, w in enumerate(words):
        if op(w) != LUI or not (0x3FA0 <= (w & 0xFFFF) <= 0x3FB4): continue
        hi = w & 0xFFFF; r = rt(w); lo = None
        for j in range(1, 7):
            if i + j >= len(words): break
            x = words[i + j]
            if op(x) in (ORI, ADDIU) and rs(x) == r and rt(x) == r: lo = (i + j, x); break
        v = hi << 16
        if lo: v += (lo[1] & 0xFFFF) if op(lo[1]) == ORI else s16(lo[1] & 0xFFFF)
        nv = w32(f32(v) * 4 / 3); nhi, nlo = nv >> 16, nv & 0xFFFF
        codes = [gs(A(i) + 2, nhi)]
        if lo:
            if op(lo[1]) == ADDIU and nlo & 0x8000: codes = [gs(A(i) + 2, nhi + 1)]
            codes.append(gs(A(lo[0]) + 2, nlo))
        out.append({'kind': 'imm', 'addr': '%08X' % A(i), 'value': round(f32(v), 6), 'codes': codes})
    return out

if __name__ == '__main__':
    words = load(sys.argv[1])
    c = call_sites(words) + data_imm(words)
    print('%d call, %d data, %d imm' % tuple(sum(x['kind'] == k for x in c) for k in ('call', 'data', 'imm')))
    for x in c:
        if x['kind'] == 'call' or (x['kind'] == 'data' and abs(x['value'] - 4 / 3) < 0.03): print('  ', x)
    if len(sys.argv) > 2: json.dump(c, open(sys.argv[2], 'w'), indent=1)
