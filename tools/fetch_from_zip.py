#!/usr/bin/env python3
"""
List or extract members of a remote zip via HTTP range requests, so one
scene can be pulled out of the 14.7 GB pre-trained bundle without
downloading all of it.

    python tools/fetch_from_zip.py URL --list [--grep truck]
    python tools/fetch_from_zip.py URL --dest data/ --grep truck/
"""
import argparse
import io
import os
import shutil
import urllib.request
import zipfile


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("url")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--grep", default="")
    ap.add_argument("--dest", default="data")
    args = ap.parse_args()

    zf = zipfile.ZipFile(io.BufferedReader(HttpFile(args.url), buffer_size=1 << 20))
    members = [m for m in zf.infolist() if args.grep in m.filename]
    for m in members:
        if args.list:
            print(f"{m.file_size:>14,}  {m.filename}")
            continue
        if m.is_dir():
            continue
        out = os.path.join(args.dest, m.filename)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        print(f"extracting {m.filename} ({m.file_size:,} B)", flush=True)
        with zf.open(m) as src, open(out, "wb") as dst:
            shutil.copyfileobj(src, dst, 8 << 20)


if __name__ == "__main__":
    main()
