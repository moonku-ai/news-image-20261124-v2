#!/usr/bin/env python3
"""news-image-20261124 v2 — 'THE WORLD IN ONE DAY', markets-surge edition.
Fresh build for the 24 Nov 2026 news-image bounty. Pure Python stdlib.
Reads atlas.bin (glyph atlas built by tools/make_atlas.py from system TTFs),
draws a 1024x1024 broadsheet front page, writes /output/entry.png (or
entry-v2.png next to this file when run locally).

Deterministic: no clock, no randomness, no network. Two runs -> same bytes.
"""
import os
import struct
import sys
import zlib

W, H = 1024, 1024

# --- palette (rank-1 broadsheet: cream paper, navy, signal red) ---
PAPER = (247, 241, 227)
INK = (20, 20, 20)
NAVY = (14, 42, 74)
RED = (180, 35, 24)
FAINT = (90, 83, 72)
HAIR = (201, 191, 169)
GOLD = (176, 141, 26)
GREEN = (31, 122, 63)
WHITE = (255, 255, 255)
SKY = (214, 228, 240)
LIGHTNAVY = (32, 64, 100)


# ---------------------------------------------------------------- atlas
class Atlas:
    def __init__(self, path):
        data = open(path, "rb").read()
        assert data[:4] == b"ATL3", "bad atlas magic"
        pos = 4
        nfonts = struct.unpack_from(">I", data, pos)[0]; pos += 4
        self.fonts = {}
        for _ in range(nfonts):
            ln = struct.unpack_from(">I", data, pos)[0]; pos += 4
            name = data[pos:pos+ln].decode(); pos += ln
            px = struct.unpack_from(">I", data, pos)[0]; pos += 4
            ng = struct.unpack_from(">I", data, pos)[0]; pos += 4
            glyphs = {}
            for _ in range(ng):
                cp, adv, xoff, yoff, w, h = struct.unpack_from(">IhhhhH", data, pos)
                pos += 14
                blen = struct.unpack_from(">I", data, pos)[0]; pos += 4
                bmp = data[pos:pos+blen]; pos += blen
                glyphs[cp] = (adv, xoff, yoff, w, h, bmp)
            self.fonts[name] = (px, glyphs)

    def text_w(self, font, text):
        _, glyphs = self.fonts[font]
        w = 0
        for ch in text:
            g = glyphs.get(ord(ch))
            if g:
                w += g[0]
            else:
                w += self.fonts[font][0] // 2
        return w

    def line_h(self, font):
        return int(self.fonts[font][0] * 1.25)


# ---------------------------------------------------------------- canvas
class Canvas:
    def __init__(self, w, h, bg):
        self.w, self.h = w, h
        self.px = bytearray(bg * (w * h))

    def _set(self, x, y, c):
        if 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i:i+3] = bytes(c)

    def rect(self, x, y, w, h, c):
        x0, y0 = max(0, x), max(0, y)
        x1, y1 = min(self.w, x + w), min(self.h, y + h)
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(c) * (x1 - x0)
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + len(row)] = row

    def hline(self, x0, x1, y, c, th=1):
        for t in range(th):
            self.rect(x0, y + t, x1 - x0, 1, c)

    def vline(self, x, y0, y1, c, th=1):
        for t in range(th):
            self.rect(x + t, y0, 1, y1 - y0, c)

    def line(self, x0, y0, x1, y1, c, th=1):
        dx, dy = abs(x1 - x0), abs(y1 - y0)
        sx = 1 if x0 < x1 else -1
        sy = 1 if y0 < y1 else -1
        err = dx - dy
        x, y = x0, y0
        while True:
            for a in range(th):
                for b in range(th):
                    self._set(x + a, y + b, c)
            if x == x1 and y == y1:
                break
            e2 = 2 * err
            if e2 > -dy:
                err -= dy; x += sx
            if e2 < dx:
                err += dx; y += sy

    def circle(self, cx, cy, r, c, fill=True):
        for yy in range(cy - r, cy + r + 1):
            for xx in range(cx - r, cx + r + 1):
                d = (xx - cx) ** 2 + (yy - cy) ** 2
                if fill:
                    if d <= r * r:
                        self._set(xx, yy, c)
                else:
                    if r * r - 2 * r <= d <= r * r:
                        self._set(xx, yy, c)

    def poly(self, pts, c):
        """Scanline fill of a polygon (even-odd)."""
        if len(pts) < 3:
            return
        ys = [p[1] for p in pts]
        y0, y1 = max(0, int(min(ys))), min(self.h - 1, int(max(ys)))
        n = len(pts)
        for y in range(y0, y1 + 1):
            xs = []
            for i in range(n):
                x1, y1p = pts[i]
                x2, y2p = pts[(i + 1) % n]
                if (y1p <= y < y2p) or (y2p <= y < y1p):
                    t = (y - y1p) / (y2p - y1p)
                    xs.append(x1 + t * (x2 - x1))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                a, b = int(xs[k] + 0.5), int(xs[k + 1] + 0.5)
                self.rect(a, y, max(0, b - a), 1, c)

    def text(self, atlas, font, x, y, s, c):
        """Draw text with baseline at y; returns width drawn."""
        _, glyphs = atlas.fonts[font]
        cx = x
        for ch in s:
            g = glyphs.get(ord(ch))
            if g is None:
                cx += atlas.fonts[font][0] // 2
                continue
            adv, xoff, yoff, w, h, bmp = g
            gx, gy = cx + xoff, y + yoff
            for row in range(h):
                base = row * w
                for col in range(w):
                    a = bmp[base + col]
                    if a:
                        px, py = gx + col, gy + row
                        if 0 <= px < self.w and 0 <= py < self.h:
                            i = (py * self.w + px) * 3
                            if a == 255:
                                self.px[i:i+3] = bytes(c)
                            else:
                                for k in range(3):
                                    old = self.px[i + k]
                                    self.px[i + k] = (old * (255 - a) + c[k] * a) // 255
            cx += adv
        return cx - x

    def text_center(self, atlas, font, cx, y, s, c):
        w = atlas.text_w(font, s)
        return self.text(atlas, font, cx - w // 2, y, s, c)


def wrap(atlas, font, text, max_w):
    words = text.split(" ")
    lines, cur = [], ""
    for word in words:
        trial = (cur + " " + word).strip()
        if atlas.text_w(font, trial) <= max_w or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def png_bytes(cv):
    raw = bytearray()
    stride = cv.w * 3
    for y in range(cv.h):
        raw.append(0)
        raw += cv.px[y * stride:(y + 1) * stride]

    def chunk(typ, data):
        c = struct.pack(">I", len(data)) + typ + data
        c += struct.pack(">I", zlib.crc32(typ + data) & 0xFFFFFFFF)
        return c

    ihdr = struct.pack(">IIBBBBB", cv.w, cv.h, 8, 2, 0, 0, 0)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr)
            + chunk(b"IDAT", zlib.compress(bytes(raw), 9))
            + chunk(b"IEND", b""))


# ------------------------------------------------------------- content
# Certainty: ● confirmed Tue 24 Nov · ◐ reported Mon 23 Nov · ○ due Tue 24 Nov
HERO = {
    "kicker": "THE DAY IN MARKETS",
    "head": "MARKETS ROAR BACK",
    "body": ("Wall Street's best day in months as Nvidia reinstates Jensen Huang as "
             "chief executive. The Nasdaq jumps 6.51%; Seoul climbs 6%."),
    "chip": "NASDAQ +6.51%",
    "cert": "●",
}

LEADS = [
    {"kicker": "NATO · EUROPE", "head": "RUSSIA TESTS NATO'S SKIES",
     "body": ("NATO airspace violated 25 times in 2026, four times the 2024 total. "
              "A drone crosses Poland; jets enter South Korea."),
     "cert": "●", "art": "radar"},
    {"kicker": "THE HAGUE · MYANMAR", "head": "14 NATIONS BACK GENOCIDE RULING",
     "body": ("Fourteen countries affirm the court ruling that Myanmar committed "
              "genocide against the Rohingya; Britain adds sanctions."),
     "cert": "◐", "art": "scales"},
    {"kicker": "NEPAL · ASIA", "head": "QUAKE SHAKES NEPAL BORDER",
     "body": ("A magnitude 5.6 earthquake strikes Nepal near the Chinese border on "
              "Tuesday. Teams check mountain districts."),
     "cert": "●", "art": "seismo"},
    {"kicker": "INDONESIA · ASIA", "head": "FACTORY FIRE IN INDONESIA",
     "body": ("A major fire at an Indonesian industrial facility causes multiple "
              "casualties and leaves several workers missing."),
     "cert": "●", "art": "fire"},
]

MEDIUM = [
    ("CAS RULES ON AFCON TITLE TODAY",
     "Top court decides Senegal's title appeal today.", "○"),
    ("GUKESH DEFENDS CROWN",
     "Gukesh, 20, faces Sindarov, 20, in game one tonight.", "○"),
    ("UN WANTS AI RULES IN A YEAR",
     "Guterres wants AI-risk rules agreed within a year.", "◐"),
    ("TRUMP WARNS IRAN",
     "Trump warns of a 'traumatic' outcome if talks fail.", "●"),
    ("MODI OPENS AI CENTRE",
     "Modi opens a new AI centre at IIT Patna.", "●"),
    ("OIL SLIDES ON LIBYA RESTART",
     "Brent falls 3% to $86.70 as a Libyan pipe restarts.", "●"),
]

ALSO = [
    "Ukraine: Zaporizhzhia hit by fresh night attacks",
    "Bangladesh typhoid drive targets 50 million children",
    "SoftBank to invest $2 billion in Intel",
    "China opens Tiangong to a first foreign astronaut",
]

STATS = [("NASDAQ", "+6.51%"), ("S&P", "+4.73%"), ("NIKKEI", "+3.91%"),
         ("KOSPI", "+6%"), ("BRENT", "-2.99%"), ("GOLD", "-0.85%")]

TICKER = ("OVERNIGHT  Poland drone incursion  ·  MORNING  Seoul +6%  ·  "
          "MIDDAY  Nasdaq +6.51%")

# world map: rough continent outlines in (lon, lat)
CONTINENTS = [
    [(-168, 66), (-140, 70), (-125, 72), (-110, 73), (-95, 80), (-85, 70), (-75, 72),
     (-60, 62), (-55, 52), (-65, 45), (-75, 35), (-80, 26), (-85, 30), (-95, 20),
     (-105, 20), (-115, 28), (-125, 40), (-125, 49), (-140, 60), (-155, 58), (-165, 60)],
    [(-45, 60), (-30, 68), (-20, 70), (-30, 76), (-55, 76), (-58, 70)],
    [(-80, 10), (-75, 5), (-80, -5), (-80, -15), (-70, -20), (-70, -35), (-65, -45),
     (-70, -55), (-55, -35), (-40, -20), (-35, -8), (-45, 0), (-55, 5), (-65, 10)],
    [(-17, 15), (-10, 30), (0, 35), (10, 37), (20, 32), (32, 31), (35, 28), (40, 15),
     (48, 11), (51, 10), (40, 0), (40, -10), (35, -20), (30, -30), (20, -35), (15, -30),
     (12, -18), (9, -5), (9, 4), (-8, 5), (-13, 8)],
    [(-10, 36), (-9, 43), (-2, 48), (0, 50), (5, 53), (8, 57), (10, 59), (18, 56),
     (21, 55), (24, 58), (28, 60), (30, 62), (25, 65), (20, 70), (15, 70), (12, 65),
     (5, 60), (0, 55), (-5, 50), (-10, 44)],
    [(30, 62), (40, 68), (50, 70), (60, 70), (70, 72), (80, 73), (90, 75), (100, 76),
     (110, 74), (120, 73), (130, 72), (140, 72), (150, 70), (160, 66), (162, 60),
     (158, 52), (142, 50), (140, 40), (135, 35), (130, 33), (127, 35), (122, 38),
     (120, 30), (115, 22), (108, 18), (105, 10), (100, 8), (95, 15), (90, 22),
     (85, 20), (80, 15), (75, 10), (72, 20), (66, 25), (60, 25), (55, 26), (50, 29),
     (48, 30), (43, 28), (40, 32), (35, 36), (30, 36)],
    [(95, 5), (100, 0), (105, -5), (110, -7), (115, -8), (120, -10), (125, -9),
     (130, -3), (135, -4), (140, -8)],
    [(113, -22), (114, -30), (115, -35), (120, -34), (125, -32), (130, -32),
     (135, -35), (140, -38), (145, -38), (150, -37), (153, -27), (150, -22),
     (146, -19), (142, -11), (137, -12), (132, -12), (130, -13), (126, -14),
     (122, -17), (118, -20)],
]

# (lon, lat, number, nudge dx, nudge dy) — Europe cluster nudged apart
PINS = [
    (127, 37, "1", 0, 0),
    (6, 46, "2", -6, -10),
    (21, 52, "3", 8, -8),
    (4, 52, "4", -14, 4),
    (84, 28, "5", 0, 0),
    (107, -6, "6", 0, 0),
    (96, 21, "7", 0, 0),
    (17, 26, "8", 0, 0),
    (7, 46, "9", 10, 10),
]

# ------------------------------------------------------------- illustrations
def art_candles(cv, x, y, w, h):
    """Rising candlestick chart on a navy panel."""
    cv.rect(x, y, w, h, NAVY)
    cv.rect(x, y, w, h, NAVY)
    # gridlines
    for i in range(1, 4):
        gy = y + h * i // 4
        for gx in range(x + 8, x + w - 8, 6):
            cv.rect(gx, gy, 3, 1, LIGHTNAVY)
    base = y + h - 18
    top = y + 14
    # candles: (open, close) as fractions of height, rising overall
    data = [(0.62, 0.55), (0.55, 0.48), (0.50, 0.52), (0.44, 0.34),
            (0.36, 0.40), (0.30, 0.20), (0.22, 0.12)]
    n = len(data)
    cw = (w - 24) // n
    for i, (o, c) in enumerate(data):
        cx0 = x + 12 + i * cw + 3
        bw = cw - 8
        yo = base - int((base - top) * (1 - o))
        yc = base - int((base - top) * (1 - c))
        up = c < o
        col = GREEN if up else RED
        # wick
        cv.vline(cx0 + bw // 2, min(yo, yc) - 6, max(yo, yc) + 6, WHITE, 2)
        cv.rect(cx0, min(yo, yc), bw, max(4, abs(yc - yo)), col)
    # trend arrow
    cv.line(x + 14, base - 20, x + w - 16, top + 8, GOLD, 3)
    ax, ay = x + w - 16, top + 8
    cv.poly([(ax, ay), (ax - 16, ay + 2), (ax - 4, ay + 14)], GOLD)
    cv.text(ATLAS, "sans_bold", x + 12, y + 26, "NASDAQ", (180, 200, 220))
    cv.text(ATLAS, "sans_bold", x + 12, y + 46, "+6.51%", GOLD)


def art_radar(cv, x, y, w, h):
    """Radar screen with jets crossing a border."""
    cv.rect(x, y, w, h, SKY)
    cx, cy, r = x + w // 2 - 30, y + h // 2, min(w, h) // 2 - 14
    for rr in (r, r * 2 // 3, r // 3):
        cv.circle(cx, cy, rr, NAVY, fill=False)
    cv.line(cx - r, cy, cx + r, cy, NAVY)
    cv.line(cx, cy - r, cx, cy + r, NAVY)
    # sweep
    cv.line(cx, cy, cx + r - 6, cy - r + 10, RED, 2)
    # dashed border
    bx = x + w - 42
    for yy in range(y + 8, y + h - 8, 10):
        cv.rect(bx, yy, 2, 6, RED)
    # jets (simple deltas)
    for jx, jy, s in ((x + 22, y + 26, 1), (x + 52, y + h - 34, -1)):
        cv.poly([(jx, jy - 10 * s), (jx - 9, jy + 8 * s), (jx, jy + 4 * s),
                 (jx + 9, jy + 8 * s)], NAVY)
    cv.circle(cx + 18, cy - 12, 4, RED)
    cv.circle(cx - 22, cy + 16, 4, RED)


def art_scales(cv, x, y, w, h):
    """Scales of justice on a cream panel."""
    cv.rect(x, y, w, h, (233, 224, 200))
    cx = x + w // 2
    top = y + 16
    cv.rect(cx - 2, top, 5, h - 52, NAVY)
    cv.circle(cx, top - 4, 6, NAVY)
    cv.line(x + 18, top + 16, x + w - 18, top + 16, NAVY, 3)
    for side in (-1, 1):
        px = cx + side * (w // 2 - 26)
        cv.line(px, top + 16, px, top + 44, NAVY, 2)
        cv.poly([(px - 26, top + 44), (px + 26, top + 44), (px, top + 62)], GOLD)
        cv.line(px - 26, top + 44, px + 26, top + 44, NAVY, 2)
    cv.rect(cx - 26, y + h - 22, 52, 6, NAVY)
    cv.text(ATLAS, "sans_bold", x + 10, y + h - 4, "ICJ", NAVY)


def art_seismo(cv, x, y, w, h):
    """Seismograph trace over a mountain."""
    cv.rect(x, y, w, h, SKY)
    # mountain
    cv.poly([(x + 8, y + h - 8), (x + w // 2 - 20, y + 22), (x + w // 2 + 6, y + 52),
             (x + w - 8, y + h - 8)], NAVY)
    cv.poly([(x + w // 2 - 20, y + 22), (x + w // 2 - 8, y + 36),
             (x + w // 2 - 2, y + 28), (x + w // 2 + 6, y + 52)], WHITE)
    # paper strip with trace
    sy = y + h - 34
    cv.rect(x + 10, sy, w - 20, 24, WHITE)
    pts = []
    import math
    for i in range(w - 20):
        t = i / max(1, w - 20)
        amp = 2 + 9 * math.sin(t * 40) ** 2 * (1 if 0.35 < t < 0.7 else 0.15)
        pts.append((x + 10 + i, sy + 12 + int(amp * math.sin(t * 90))))
    for i in range(len(pts) - 1):
        cv.line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1], RED, 2)
    cv.text(ATLAS, "sans_bold", x + 10, y + 18, "M 5.6", RED)


def art_fire(cv, x, y, w, h):
    """Factory silhouette with flames."""
    cv.rect(x, y, w, h, (40, 32, 28))
    # factory
    cv.rect(x + 14, y + h - 52, w - 28, 44, (70, 58, 48))
    cv.rect(x + w - 52, y + 26, 12, h - 34, (70, 58, 48))
    for wx in range(x + 22, x + w - 60, 18):
        cv.rect(wx, y + h - 42, 10, 10, GOLD)
    # flames
    fx = x + w // 2
    cv.poly([(fx - 34, y + h - 50), (fx - 12, y + h - 96), (fx - 2, y + h - 70),
             (fx + 12, y + h - 100), (fx + 34, y + h - 50)], (214, 94, 20))
    cv.poly([(fx - 18, y + h - 50), (fx - 6, y + h - 82), (fx + 4, y + h - 64),
             (fx + 18, y + h - 50)], GOLD)
    # smoke
    for sx, sy, sr in ((x + w - 46, y + 14, 6), (x + w - 38, y + 4, 4)):
        cv.circle(sx, sy, sr, (160, 150, 135))


ARTS = {"candles": art_candles, "radar": art_radar, "scales": art_scales,
        "seismo": art_seismo, "fire": art_fire}

# ---------------------------------------------------------------- layout
def build():
    global ATLAS
    base = os.path.dirname(os.path.abspath(__file__))
    ATLAS = Atlas(os.path.join(base, "atlas.bin"))
    cv = Canvas(W, H, PAPER)
    A = ATLAS
    MX = 28  # side margin

    # top double rule
    cv.rect(0, 0, W, 4, NAVY)
    cv.rect(0, 8, W, 1, NAVY)

    # kicker line
    cv.text(A, "sans_bold_s", MX, 30, "TUESDAY 24 NOVEMBER 2026", NAVY)
    right = "THE DAY IN ONE PAGE"
    cv.text(A, "sans_bold_s", W - MX - A.text_w("sans_bold_s", right), 30, right, NAVY)
    cv.hline(MX, W - MX, 38, HAIR)

    # masthead
    cv.text_center(A, "serif_bold", W // 2, 84, "THE WORLD IN ONE DAY", INK)
    cv.hline(MX, W - MX, 92, INK, 2)
    # subhead
    sub = ("Stocks roar back as Huang returns; NATO counts 25 airspace violations")
    cv.text_center(A, "serif_ital", W // 2, 114,
                   sub, RED)

    # stats strip (navy band)
    sy = 124
    cv.rect(0, sy, W, 34, NAVY)
    seg = W // len(STATS)
    for i, (lab, val) in enumerate(STATS):
        cx = seg * i + seg // 2
        txt = lab + "  " + val
        w = A.text_w("sans_bold_s", txt)
        cv.text(A, "sans_bold_s", cx - w // 2, sy + 22, txt, WHITE)
        if i:
            cv.vline(seg * i, sy + 6, sy + 28, LIGHTNAVY)

    # ticker
    ty = 168
    cv.text(A, "sans_bold_s", MX, ty + 12, "THE DAY IN UTC", RED)
    tw = A.text_w("sans_bold_s", "THE DAY IN UTC") + 12
    lines = wrap(A, "sans_reg_s", TICKER, W - 2 * MX - tw)
    cv.text(A, "sans_reg_s", MX + tw, ty + 12, lines[0], INK)
    cv.hline(MX, W - MX, 184, INK, 2)

    # ---- hero lead ----
    hy = 196
    cv.text(A, "sans_bold_s", MX, hy + 13, HERO["kicker"], RED)
    hw = A.text_w("sans_bold_s", HERO["kicker"])
    cv.text(A, "sans_bold_s", MX + hw + 8, hy + 13, HERO["cert"], RED)
    cv.text(A, "serif_bold_s", MX, hy + 48, HERO["head"], INK)
    # hero illustration left, body right
    ix, iy, iw, ih = MX, hy + 58, 400, 96
    ARTS["candles"](cv, ix, iy, iw, ih)
    bx = ix + iw + 16
    bw = W - MX - bx
    blines = wrap(A, "sans_reg", HERO["body"], bw)
    yy = iy + 8
    for ln in blines:
        cv.text(A, "sans_reg", bx, yy, ln, INK)
        yy += A.line_h("sans_reg")
    # chip under body
    cv.rect(bx, iy + ih - 26, A.text_w("sans_bold", HERO["chip"]) + 16, 22, RED)
    cv.text(A, "sans_bold", bx + 8, iy + ih - 10, HERO["chip"], WHITE)
    cv.hline(MX, W - MX, hy + 160, HAIR)

    # ---- 2x2 illustrated leads ----
    gy = hy + 168
    cell_w = (W - 2 * MX - 16) // 2
    cell_h = 136
    for idx, lead in enumerate(LEADS):
        cx0 = MX + (idx % 2) * (cell_w + 16)
        cy0 = gy + (idx // 2) * (cell_h + 10)
        # illustration
        ARTS[lead["art"]](cv, cx0, cy0 + 18, 118, cell_h - 18)
        tx = cx0 + 128
        tw2 = cell_w - 128
        cv.text(A, "sans_bold_s", tx, cy0 + 13, lead["kicker"], RED)
        kw = A.text_w("sans_bold_s", lead["kicker"])
        cv.text(A, "sans_bold_s", tx + kw + 6, cy0 + 13, lead["cert"], RED)
        hl = wrap(A, "sans_bold", lead["head"], tw2)
        yy = cy0 + 34
        for ln in hl:
            cv.text(A, "sans_bold", tx, yy, ln, INK)
            yy += A.line_h("sans_bold")
        bl = wrap(A, "sans_reg_s", lead["body"], tw2)
        for ln in bl[:3]:
            cv.text(A, "sans_reg_s", tx, yy, ln, FAINT)
            yy += A.line_h("sans_reg_s")
    my = gy + 2 * cell_h + 10
    cv.hline(MX, W - MX, my, HAIR)

    # ---- medium stories: 2 cols x 3 rows ----
    my += 8
    col_w = (W - 2 * MX - 16) // 2
    row_h = 48
    for i, (head, body, cert) in enumerate(MEDIUM):
        cx0 = MX + (i % 2) * (col_w + 16)
        cy0 = my + (i // 2) * row_h
        cv.rect(cx0, cy0 + 4, 7, 7, RED)
        hl = wrap(A, "sans_bold", head, col_w - 16)
        yy = cy0 + 14
        cv.text(A, "sans_bold", cx0 + 14, yy, hl[0], INK)
        if len(hl) == 1:
            cv.text(A, "sans_bold_s", cx0 + 14 + A.text_w("sans_bold", hl[0]) + 6,
                    yy, cert, RED)
        yy += A.line_h("sans_bold")
        bl = wrap(A, "sans_reg_s", body, col_w - 16)
        for ln in bl[:1]:
            cv.text(A, "sans_reg_s", cx0 + 14, yy, ln, FAINT)
            yy += A.line_h("sans_reg_s")
    ay = my + 3 * row_h + 4
    cv.hline(MX, W - MX, ay, HAIR)

    # ---- ALSO ----
    ay += 10
    cv.text(A, "sans_bold_s", MX, ay + 11, "ALSO IN THE NEWS", NAVY)
    ay += 18
    for i, item in enumerate(ALSO):
        cx0 = MX + (i % 2) * (col_w + 16)
        cy0 = ay + (i // 2) * 20
        cv.rect(cx0, cy0 + 4, 5, 5, NAVY)
        lines = wrap(A, "sans_reg_s", item, col_w - 12)
        cv.text(A, "sans_reg_s", cx0 + 12, cy0 + 13, lines[0], INK)
    map_top = ay + 2 * 20 + 8
    cv.hline(MX, W - MX, map_top, HAIR)

    # ---- map: WHERE IT HAPPENED ----
    map_top += 10
    cv.text(A, "sans_bold_s", MX, map_top + 11, "WHERE IT HAPPENED", NAVY)
    cv.text(A, "sans_reg_s", MX + A.text_w("sans_bold_s", "WHERE IT HAPPENED") + 10,
            map_top + 11, "1 Seoul  2 Geneva  3 Warsaw  4 The Hague  5 Nepal  "
            "6 Jakarta  7 Myanmar  8 Libya  9 Lausanne", FAINT)
    m_y0 = map_top + 18
    m_y1 = 972
    m_h = m_y1 - m_y0
    cv.rect(MX, m_y0, W - 2 * MX, m_h, (233, 240, 244))
    cv.rect(MX, m_y0, W - 2 * MX, m_h, NAVY)  # border via outline below
    cv.rect(MX + 1, m_y0 + 1, W - 2 * MX - 2, m_h - 2, (233, 240, 244))

    def proj(lon, lat):
        x = MX + (lon + 180) / 360.0 * (W - 2 * MX)
        y = m_y0 + (72 - lat) / 124.0 * m_h
        return (x, y)

    for cont in CONTINENTS:
        cv.poly([proj(lon, lat) for lon, lat in cont], (178, 190, 205))
    for lon, lat, num, ndx, ndy in PINS:
        px, py = proj(lon, lat)
        px, py = int(px), int(py)
        qx, qy = px + ndx, py + ndy
        if ndx or ndy:
            cv.line(px, py, qx, qy, RED)
        cv.circle(qx, qy, 9, RED)
        nw = A.text_w("sans_bold_s", num)
        cv.text(A, "sans_bold_s", qx - nw // 2, qy + 5, num, WHITE)

    # ---- footer ----
    fy = 982
    cv.hline(MX, W - MX, fy, INK, 2)
    cv.text(A, "sans_reg_s", MX, fy + 15,
            "Sources: Reuters, The Conversation, Horizon markets, CareerIndia, "
            "Chess.com, Middle East Eye.", FAINT)
    cv.text(A, "sans_reg_s", MX, fy + 30,
            "Compiled Tue 24 Nov 2026.  ● confirmed today  "
            "◐ reported Monday  ○ due later today", FAINT)
    return cv


def main():
    cv = build()
    data = png_bytes(cv)
    out = sys.argv[1] if len(sys.argv) > 1 else "/output/entry.png"
    if out.startswith("/output/"):
        os.makedirs("/output", exist_ok=True)
    with open(out, "wb") as f:
        f.write(data)
    print(f"wrote {out}: {len(data)} bytes, {W}x{H}")


if __name__ == "__main__":
    main()
