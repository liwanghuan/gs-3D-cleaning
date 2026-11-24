#!/usr/bin/env python3
"""
Pixel size of JPEG members of a remote zip, reading only the first bytes of
each (SOF marker), via HTTP range requests. Used to find the resolution a
3DGS model was trained at (the size of the images in cfg_args `images`).

    python tools/remote_jpeg_size.py URL --prefix bicycle/images_4/ [--max 3]
"""
import argparse
import io
import struct
import zipfile
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from fetch_from_zip import HttpFile  # noqa: E402


def jpeg_size(buf):
    i = 2
    while i < len(buf) - 9:
        if buf[i] != 0xFF:
            i += 1
            continue
        marker = buf[i + 1]
        seglen = struct.unpack(">H", buf[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7, 0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h, w = struct.unpack(">HH", buf[i + 5:i + 9])
            return w, h
        i += 2 + seglen
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--prefix", required=True)
    ap.add_argument("--max", type=int, default=3)
    a = ap.parse_args()
    zf = zipfile.ZipFile(io.BufferedReader(HttpFile(a.url), buffer_size=1 << 18))
    ms = sorted((m for m in zf.infolist() if m.filename.startswith(a.prefix)
                 and m.filename.lower().endswith((".jpg", ".jpeg"))), key=lambda m: m.filename)
    picks = ms[:: max(1, len(ms) // a.max)][: a.max]
    sizes = set()
    for m in picks:
        with zf.open(m) as f:
            s = jpeg_size(f.read(256 << 10))
        sizes.add(s)
        print(f"{m.filename}: {s[0]}x{s[1]}")
    print(f"{len(ms)} images under {a.prefix}; distinct sizes in sample: {sorted(sizes)}")


if __name__ == "__main__":
    main()
