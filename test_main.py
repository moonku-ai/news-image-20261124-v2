#!/usr/bin/env python3
"""Tests for news-image-20261124 v2 (stdlib only, run: python3 test_main.py)."""
import hashlib
import os
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import main as M


def test_atlas_loads():
    a = M.Atlas(os.path.join(HERE, "atlas.bin"))
    assert len(a.fonts) == 8, a.fonts.keys()
    for name in ("serif_bold", "sans_bold", "serif_ital", "sans_reg"):
        assert name in a.fonts
        assert len(a.fonts[name][1]) > 100
    assert a.text_w("serif_bold", "THE WORLD IN ONE DAY") < 1024
    print("ok atlas loads")


def test_wrap_fits():
    a = M.Atlas(os.path.join(HERE, "atlas.bin"))
    # every body/headline must wrap within its column width
    for lead in M.LEADS:
        assert len(M.wrap(a, "sans_bold", lead["head"], 348)) <= 2, lead["head"]
        assert len(M.wrap(a, "sans_reg_s", lead["body"], 348)) <= 3, lead["body"]
    for head, body, _ in M.MEDIUM:
        assert len(M.wrap(a, "sans_bold", head, 460)) == 1, head
        assert len(M.wrap(a, "sans_reg_s", body, 460)) == 1, body
    for item in M.ALSO:
        assert len(M.wrap(a, "sans_reg_s", item, 464)) == 1, item
    assert len(M.wrap(a, "sans_reg", M.HERO["body"], 552)) <= 3
    print("ok wrap fits")


def test_render_dims_and_size():
    cv = M.build()
    data = M.png_bytes(cv)
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", data[16:24])
    assert (w, h) == (1024, 1024), (w, h)
    assert len(data) <= 1048576, len(data)
    # IDAT decompresses to 1024 rows of (1 + 3072) bytes
    pos = 8
    idat = b""
    while pos < len(data):
        ln = struct.unpack(">I", data[pos:pos+4])[0]
        typ = data[pos+4:pos+8]
        if typ == b"IDAT":
            idat += data[pos+8:pos+8+ln]
        pos += 12 + ln
    raw = zlib.decompress(idat)
    assert len(raw) == 1024 * (1 + 1024 * 3), len(raw)
    print(f"ok render dims+size ({len(data)} bytes)")


def test_determinism():
    outs = []
    for name in ("det-a.png", "det-b.png"):
        p = os.path.join(HERE, name)
        subprocess.run([sys.executable, os.path.join(HERE, "main.py"), p],
                       check=True, capture_output=True)
        outs.append(hashlib.sha256(open(p, "rb").read()).hexdigest())
        os.remove(p)
    assert outs[0] == outs[1], outs
    print("ok determinism", outs[0][:16])


def test_clean_dir():
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        for f in ("main.py", "atlas.bin"):
            src = os.path.join(HERE, f)
            dst = os.path.join(d, f)
            with open(src, "rb") as a, open(dst, "wb") as b:
                b.write(a.read())
        out = os.path.join(d, "entry.png")
        r = subprocess.run([sys.executable, "main.py", out], cwd=d,
                           capture_output=True, text=True)
        assert r.returncode == 0, r.stderr
        assert os.path.getsize(out) > 50000
    print("ok clean-dir run")


if __name__ == "__main__":
    test_atlas_loads()
    test_wrap_fits()
    test_render_dims_and_size()
    test_determinism()
    test_clean_dir()
    print("ALL TESTS PASS")
