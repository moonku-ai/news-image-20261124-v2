# tools/make_atlas.py — FRESH build for news-image-20261124 v2.
# Minimal TTF parser + grayscale glyph rasterizer (own code, stdlib only).
# Reads system TTFs, writes atlas.bin in our own ATL3 format for main.py.
# Usage: python3 tools/make_atlas.py  (run from the repo root)
import struct, sys, os

FONTS = [
    ("serif_bold",   "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", 46),
    ("serif_bold_s", "/usr/share/fonts/truetype/liberation/LiberationSerif-Bold.ttf", 30),
    ("serif_reg",    "/usr/share/fonts/truetype/liberation/LiberationSerif-Regular.ttf", 26),
    ("serif_ital",   "/usr/share/fonts/truetype/liberation/LiberationSerif-Italic.ttf", 24),
    ("sans_bold",    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 22),
    ("sans_bold_s",  "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 15),
    ("sans_reg",     "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20),
    ("sans_reg_s",   "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 15),
]

CHARS = ("".join(chr(c) for c in range(32, 127))
         + "\u2013\u2014\u2018\u2019\u201c\u201d\u2022\u2026\u00b0\u00d7\u00b1"
         + "\u25b2\u25bc\u25cf\u25cb\u2191\u2193\u00e9\u00e8\u00fc\u00f6\u00e4")

def u16(b, o): return struct.unpack_from(">H", b, o)[0]
def i16(b, o): return struct.unpack_from(">h", b, o)[0]
def u32(b, o): return struct.unpack_from(">I", b, o)[0]
def i32(b, o): return struct.unpack_from(">i", b, o)[0]

class TTF:
    def __init__(self, path):
        self.data = open(path, "rb").read()
        d = self.data
        n = u16(d, 4)
        self.tables = {}
        for i in range(n):
            o = 12 + 16 * i
            tag = d[o:o+4].decode("latin1")
            self.tables[tag] = (u32(d, o+8), u32(d, o+12))
        self.upem = u16(d, self.tables["head"][0] + 18)
        self.index_to_loc = i16(d, self.tables["head"][0] + 50)
        self.num_glyphs = u16(d, self.tables["maxp"][0] + 4)
        self.cmap = self._parse_cmap()
        hmtx_off = self.tables["hmtx"][0]
        self.adv = [u16(d, hmtx_off + 4 * g) for g in range(self.num_glyphs)]

    def _parse_cmap(self):
        d = self.data
        off, _ = self.tables["cmap"]
        n = u16(d, off + 2)
        best = None
        for i in range(n):
            plat, enc, sub = u16(d, off + 4 + 8*i), u16(d, off + 6 + 8*i), u32(d, off + 8 + 8*i)
            fmt = u16(d, off + sub)
            if fmt == 4 and (plat, enc) in ((3, 1), (0, 3), (0, 4)):
                best = off + sub
                break
            if fmt == 12 and best is None:
                best = off + sub
        if best is None:
            raise ValueError("no usable cmap")
        fmt = u16(d, best)
        cmap = {}
        if fmt == 4:
            seg = u16(d, best + 6) // 2
            end = [u16(d, best + 14 + 2*i) for i in range(seg)]
            start = [u16(d, best + 16 + 2*seg + 2*i) for i in range(seg)]
            delta = [i16(d, best + 16 + 4*seg + 2*i) for i in range(seg)]
            roff = best + 16 + 6*seg
            for i in range(seg):
                if start[i] == 0xFFFF:
                    break
                for c in range(start[i], end[i] + 1):
                    if delta[i] != 0:
                        g = (c + delta[i]) % 65536
                    else:
                        ro = u16(d, roff + 2*i)
                        if ro == 0:
                            g = 0
                        else:
                            g = u16(d, roff + 2*i + ro + 2*(c - start[i]))
                    if g:
                        cmap[c] = g
        else:  # format 12
            ng = u32(d, best + 12)
            for i in range(ng):
                s, e, g0 = u32(d, best + 16 + 12*i), u32(d, best + 20 + 12*i), u32(d, best + 24 + 12*i)
                for c in range(s, e + 1):
                    cmap[c] = g0 + (c - s)
        return cmap

    def glyph_outline(self, gid):
        """Return list of contours; each contour is a list of (x, y, on_curve)."""
        d = self.data
        lo, _ = self.tables["loca"]
        if self.index_to_loc == 0:
            g0 = 2 * u16(d, lo + 2*gid); g1 = 2 * u16(d, lo + 2*gid + 2)
        else:
            g0 = u32(d, lo + 4*gid); g1 = u32(d, lo + 4*gid + 4)
        if g0 == g1:
            return []
        go, _ = self.tables["glyf"]
        o = go + g0
        ncont = i16(d, o)
        if ncont < 0:  # composite: not supported, treat as empty
            return []
        endpts = [u16(d, o + 10 + 2*i) for i in range(ncont)]
        npts = endpts[-1] + 1
        inst_len = u16(d, o + 10 + 2*ncont)
        flags = []
        p = o + 10 + 2*ncont + 2 + inst_len
        while len(flags) < npts:
            f = d[p]; p += 1
            flags.append(f)
            if f & 8:
                rep = d[p]; p += 1
                flags.extend([f] * rep)
        xs = []
        x = 0
        for f in flags:
            if f & 2:
                v = d[p]; p += 1
                x += v if (f & 16) else -v
            elif not (f & 16):
                x += i16(d, p); p += 2
            xs.append(x)
        ys = []
        y = 0
        for f in flags:
            if f & 4:
                v = d[p]; p += 1
                y += v if (f & 32) else -v
            elif not (f & 32):
                y += i16(d, p); p += 2
            ys.append(y)
        pts = [(xs[i], ys[i], bool(flags[i] & 1)) for i in range(npts)]
        contours = []
        s = 0
        for e in endpts:
            contours.append(pts[s:e+1])
            s = e + 1
        return contours

def flatten(contour):
    """Expand a contour to a polyline of on-curve points (quadratic beziers)."""
    pts = contour
    if not pts:
        return []
    # rotate so contour starts on-curve
    if not pts[0][2]:
        for i, pt in enumerate(pts):
            if pt[2]:
                pts = pts[i:] + pts[:i]
                break
        else:
            pts = pts[:]  # all off-curve: midpoints
    out = [pts[0][:2]]
    n = len(pts)
    i = 1
    while i <= n:
        cur = pts[i % n]
        if cur[2]:
            out.append(cur[:2]); i += 1
        else:
            nxt = pts[(i+1) % n]
            end = ((cur[0]+nxt[0])/2, (cur[1]+nxt[1])/2) if not nxt[2] else nxt[:2]
            p0 = out[-1]
            # subdivide quadratic
            segs = max(2, int(((abs(cur[0]-p0[0]) + abs(cur[1]-p0[1]) +
                                abs(end[0]-cur[0]) + abs(end[1]-cur[1])) / 24) + 1))
            for s in range(1, segs + 1):
                t = s / segs
                x = (1-t)**2*p0[0] + 2*(1-t)*t*cur[0] + t*t*end[0]
                y = (1-t)**2*p0[1] + 2*(1-t)*t*cur[1] + t*t*end[1]
                out.append((x, y))
            i += 2 if nxt[2] else 1
            if nxt[2]:
                out.append(nxt[:2])
    return out

def rasterize(ttf, gid, px, ss=2):
    contours = ttf.glyph_outline(gid)
    if not contours:
        return None
    scale = px * ss / ttf.upem
    polys = []
    minx = miny = 1e9; maxx = maxy = -1e9
    for c in contours:
        poly = [(x * scale, -y * scale) for (x, y) in flatten(c)]
        if len(poly) >= 2:
            polys.append(poly)
            for (x, y) in poly:
                minx = min(minx, x); maxx = max(maxx, x)
                miny = min(miny, y); maxy = max(maxy, y)
    if not polys:
        return None
    x0 = int(minx) - 1; x1 = int(maxx) + 2
    y0 = int(miny) - 1; y1 = int(maxy) + 2
    W = x1 - x0; H = y1 - y0
    # supersampled coverage, span fill via slice assignment
    cov = bytearray(W * H)
    for y in range(H):
        cy = y0 + y + 0.5
        xs = []
        for poly in polys:
            n = len(poly)
            for i in range(n):
                x1p, y1p = poly[i]; x2p, y2p = poly[(i+1) % n]
                if (y1p <= cy < y2p) or (y2p <= cy < y1p):
                    t = (cy - y1p) / (y2p - y1p)
                    xs.append(x1p + t * (x2p - x1p))
        xs.sort()
        row = y * W
        for k in range(0, len(xs) - 1, 2):
            a = max(0, int(xs[k] + 0.5) - x0); b = min(W, int(xs[k+1] + 0.5) - x0)
            if b > a:
                cov[row+a:row+b] = b"\xff" * (b - a)
    w = max(1, W // ss); h = max(1, H // ss)
    bmp = bytearray(w * h)
    for y in range(h):
        for x in range(w):
            s = 0
            for dy in range(ss):
                yy = y*ss + dy
                if yy >= H:
                    break
                base = yy*W + x*ss
                s += sum(cov[base:base+ss])
            bmp[y*w + x] = min(255, s // (ss*ss))
    adv = int(round(ttf.adv[gid] * px / ttf.upem))
    return {"adv": adv, "xoff": x0 // ss, "yoff": y0 // ss, "w": w, "h": h, "bmp": bytes(bmp)}

def main():
    out = bytearray()
    out += b"ATL3"
    out += struct.pack(">I", len(FONTS))
    total = 0
    for name, path, px in FONTS:
        ttf = TTF(path)
        glyphs = {}
        for ch in CHARS:
            gid = ttf.cmap.get(ord(ch))
            if not gid:
                continue
            g = rasterize(ttf, gid, px)
            if g is None:
                continue
            glyphs[ord(ch)] = g
        nb = name.encode()
        out += struct.pack(">I", len(nb)) + nb
        out += struct.pack(">I", px) + struct.pack(">I", len(glyphs))
        for cp in sorted(glyphs):
            g = glyphs[cp]
            out += struct.pack(">IhhhhH", cp, g["adv"], g["xoff"], g["yoff"], g["w"], g["h"])
            out += struct.pack(">I", len(g["bmp"])) + g["bmp"]
        total += len(glyphs)
        print(f"{name} px={px}: {len(glyphs)} glyphs")
    open("atlas.bin", "wb").write(bytes(out))
    print(f"atlas.bin: {len(out)} bytes, {total} glyphs total")

if __name__ == "__main__":
    main()
