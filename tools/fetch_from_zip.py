#!/usr/bin/env python3
"""
List or extract members of a remote zip via HTTP range requests, so one
scene can be pulled out of the 14.7 GB pre-trained bundle without
downloading all of it.

    python tools/fetch_from_zip.py URL --list [--grep truck]
    python tools/fetch_from_zip.py URL --dest data/ --grep truck/
    python tools/fetch_from_zip.py URL --dest data/ --prefix room/cfg_args --prefix room/input.ply
"""
import argparse
import io
import os
import struct
import urllib.request
import zipfile
import zlib


class HttpFile(io.RawIOBase):
    def __init__(self, url):
        self.url, self.pos = url, 0
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req) as r:
            self.size = int(r.headers["Content-Length"])

    def seekable(self): return True
    def readable(self): return True
    def tell(self): return self.pos

    def seek(self, off, whence=0):
        self.pos = {0: off, 1: self.pos + off, 2: self.size + off}[whence]
        return self.pos

    def read(self, n=-1):
        if n is None or n < 0:
            n = self.size - self.pos
        if n == 0 or self.pos >= self.size:
            return b""
        end = min(self.pos + n, self.size) - 1
        req = urllib.request.Request(self.url, headers={"Range": f"bytes={self.pos}-{end}"})
        with urllib.request.urlopen(req) as r:
            data = r.read()
        self.pos += len(data)
        return data

    def readinto(self, b):
        data = self.read(len(b))
        b[:len(data)] = data
        return len(data)


def stream_member(url, m, out):
    """
    One HTTP range request for the member's whole compressed span, inflated
    while streaming and CRC-checked. Much faster than zf.open() over HttpFile,
    which issues a request per buffer read.
    """
    hdr = urllib.request.Request(url, headers={"Range": f"bytes={m.header_offset}-{m.header_offset + 29}"})
    with urllib.request.urlopen(hdr) as r:
        lh = r.read()
    assert lh[:4] == b"PK\x03\x04", "bad local header"
    n_name, n_extra = struct.unpack("<HH", lh[26:30])
    start = m.header_offset + 30 + n_name + n_extra
    end = start + m.compress_size - 1
    if m.compress_type == zipfile.ZIP_DEFLATED:
        dec = zlib.decompressobj(-15)
    elif m.compress_type == zipfile.ZIP_STORED:
        dec = None
    else:
        raise ValueError(f"compression {m.compress_type} not supported")
    crc, n = 0, 0
    req = urllib.request.Request(url, headers={"Range": f"bytes={start}-{end}"})
    with urllib.request.urlopen(req) as r, open(out, "wb") as dst:
        while True:
            chunk = r.read(8 << 20)
            if not chunk:
                break
            data = dec.decompress(chunk) if dec else chunk
            crc = zlib.crc32(data, crc)
            n += len(data)
            dst.write(data)
        if dec:
            tail = dec.flush()
            crc = zlib.crc32(tail, crc)
            n += len(tail)
            dst.write(tail)
    assert n == m.file_size, f"{m.filename}: size {n} != {m.file_size}"
    assert crc == m.CRC, f"{m.filename}: CRC mismatch"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep", default="")
    ap.add_argument("--prefix", action="append", default=[],
                    help="keep members whose name starts with this (repeatable)")
    ap.add_argument("--dest", default="data")
    args = ap.parse_args()

    zf = zipfile.ZipFile(io.BufferedReader(HttpFile(args.url), buffer_size=1 << 20))
    members = [m for m in zf.infolist() if args.grep in m.filename
               and (not args.prefix or any(m.filename.startswith(p) for p in args.prefix))]
    for m in members:
        if args.list:
            print(f"{m.file_size:>14,}  {m.filename}")
            continue
        if m.is_dir():
            continue
        out = os.path.join(args.dest, m.filename)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        print(f"extracting {m.filename} ({m.file_size:,} B)", flush=True)
        stream_member(args.url, m, out)


if __name__ == "__main__":
    main()
