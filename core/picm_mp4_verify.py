"""Bounded ISO-BMFF MP4 box inspection for owner-only PICM handoff.

This rejects arbitrary binary masquerading as MP4. It does NOT decode the
video, certify AI generation, or replace GPU-side ffprobe and quality checks.
"""
from pathlib import Path
import struct

MAX_BOXES = 2048
MAX_FILE = 128 * 1024 * 1024
MIN_FILE = 2048


def valid_mp4_container(path):
    f = Path(path)
    size = f.stat().st_size
    if not MIN_FILE <= size <= MAX_FILE:
        return False
    types = set()
    offset = 0
    seen = 0
    first = True
    with f.open("rb") as stream:
        while offset < size:
            if seen >= MAX_BOXES or size - offset < 8:
                return False
            stream.seek(offset)
            header = stream.read(8)
            if len(header) != 8:
                return False
            box_size, box_type = struct.unpack(">I4s", header)
            overhead = 8
            if box_size == 1:
                extended = stream.read(8)
                if len(extended) != 8:
                    return False
                box_size = struct.unpack(">Q", extended)[0]
                overhead = 16
            elif box_size == 0:
                box_size = size - offset
            if box_size < overhead or box_size > size - offset:
                return False
            # Reject fake prefix outside of the actual file's box chain.
            if first:
                if box_type != b"ftyp" or box_size < overhead + 8 or box_size > 256:
                    return False
                first = False
                brand = stream.read(4)
                if len(brand) != 4 or not all(32 <= b < 127 for b in brand):
                    return False
            if box_type == b"mdat" and box_size < overhead + 256:
                return False
            if box_type == b"moov":
                if box_size < overhead + 16:
                    return False
                # At least one video/movie metadata child box is required;
                # no need to load the full file into RAM on cPanel.
                content = stream.read(min(box_size - overhead, 2 * 1024 * 1024))
                if b"trak" not in content or b"mvhd" not in content:
                    return False
            types.add(box_type)
            offset += box_size
            seen += 1
    return offset == size and {b"ftyp", b"moov", b"mdat"} <= types
