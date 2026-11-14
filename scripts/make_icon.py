#!/usr/bin/env python3
"""Write the integration's brand icon: a 256x256 RGBA PNG, own artwork (a heater panel with seven bars).

Stdlib only (zlib, struct); re-running gives byte-identical output.

  python3 scripts/make_icon.py [OUTPUT.png]     (default custom_components/adax_direct/brand/icon.png)
"""
from __future__ import annotations

import struct
import sys
import zlib
from pathlib import Path

SIZE = 256
PANEL = (24, 64, 231, 191)          # inclusive corners x0, y0, x1, y1
FILL = (0xE8, 0xE8, 0xE8, 255)
INK = (0x40, 0x40, 0x40, 255)
OUTLINE_PX = 4
BAR_X = (54, 76, 98, 120, 142, 164, 186)
BAR_W = 6
BAR_Y = (88, 167)                   # inclusive


def pixels() -> list[list[tuple[int, int, int, int]]]:
    rows = [[(0, 0, 0, 0)] * SIZE for _ in range(SIZE)]
    x0, y0, x1, y1 = PANEL
    for y in range(y0, y1 + 1):
        for x in range(x0, x1 + 1):
            edge = x - x0 < OUTLINE_PX or x1 - x < OUTLINE_PX or y - y0 < OUTLINE_PX or y1 - y < OUTLINE_PX
            rows[y][x] = INK if edge else FILL
    for bx in BAR_X:
        for y in range(BAR_Y[0], BAR_Y[1] + 1):
            for x in range(bx, bx + BAR_W):
                rows[y][x] = INK
    return rows


def chunk(kind: bytes, data: bytes) -> bytes:
    return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)


def png_bytes() -> bytes:
    raw = b"".join(b"\x00" + b"".join(bytes(p) for p in row) for row in pixels())
    ihdr = struct.pack(">IIBBBBB", SIZE, SIZE, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    out = Path(args[0]) if args else Path(__file__).resolve().parents[1] / "custom_components/adax_direct/brand/icon.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png_bytes())
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
