#!/usr/bin/env python3
"""Parse and patch Crimson Desert dropsetinfo body/header tables."""
from __future__ import annotations

import struct
from typing import Iterable

# Trailing bytes after the common drop-entry fields, keyed by the entry's dtag.
# Taken from the 2.05.00 table layout used to build v2.1.0. Do not invent tags.
VARIANT_TAIL = {
    0: 4,
    1: 4,
    2: 4,
    3: 4,
    4: 4,
    5: 4,
    6: 4,
    7: 34,
    8: 34,
    9: 4,
    0xA: 8,
    0xB: 0,
    0xC: 4,
    0xD: 5,
    16: 10,
    0xE: 3,
    0xF: 34,
    0x11: 2,
}


def load_index(body: bytes, hdr: bytes) -> tuple[bytes, list[tuple[int, bytes]]]:
    prefix = hdr[:2]
    n = (len(hdr) - 2) // 8
    recs: list[tuple[int, bytes]] = []
    for i in range(n):
        o = 2 + i * 8
        key, off = struct.unpack_from("<II", hdr, o)
        end = struct.unpack_from("<I", hdr, o + 8 + 4)[0] if i + 1 < n else len(body)
        recs.append((key, body[off:end]))
    return prefix, recs


def write_table(prefix: bytes, recs: Iterable[tuple[int, bytes]]) -> tuple[bytes, bytes]:
    body = bytearray()
    hdr = bytearray(prefix)
    for key, raw in recs:
        off = len(body)
        hdr += struct.pack("<II", key, off)
        body += raw
    return bytes(body), bytes(hdr)


def cstr_end(b: bytes, off: int = 0) -> int:
    ln = struct.unpack_from("<I", b, off)[0]
    return off + 4 + ln


def rec_name(b: bytes) -> str:
    end = cstr_end(b)
    return b[4:end].decode("utf-8")


def parse_record(b: bytes) -> dict:
    off = cstr_end(b)
    key, newf, is_blocked, is_eq, roll_type, slot, tag, roll_count, nlist = struct.unpack_from(
        "<I BBBB H II I", b, off
    )
    list_start = off + 22
    off = list_start
    entries = []
    for _ in range(nlist):
        start = off
        presence = b[off]
        off += 1
        if presence == 0:
            entries.append(b[start:off])
            continue
        off += 8
        dtag = b[off]
        off += 1
        off += 4 + 4 + 4 + 4 + 8 + 8 + 8 + 8 + 2 + 1
        tail = VARIANT_TAIL.get(dtag)
        if tail is None:
            raise ValueError(f"unknown tag {dtag} at {start} in key={key}")
        off += tail
        entries.append(b[start:off])
    trailer = b[off:]
    if len(trailer) < 28:
        raise ValueError(f"short trailer {len(trailer)} key={key}")
    need, total, skip = struct.unpack_from("<QQQ", trailer, 0)
    return {
        "key": key,
        "newf": newf,
        "nlist": nlist,
        "list_count_off": list_start - 4,
        "entries": entries,
        "trailer": trailer,
        "need": need,
        "total": total,
        "skip": skip,
        "raw": b,
    }


def make_artifact_entry(item_key: int, rate: int) -> bytes:
    entry = (
        bytes([1])
        + struct.pack("<Q", item_key)
        + bytes([0])
        + struct.pack("<IIII", 0, 0, 0, 0)
        + struct.pack("<Q", rate)
        + struct.pack("<Q", 0)
        + struct.pack("<Q", 1)
        + struct.pack("<Q", 1)
        + struct.pack("<H", 65535)
        + bytes([0])
        + struct.pack("<I", item_key)
    )
    if len(entry) != 65:
        raise RuntimeError(f"artifact entry size {len(entry)} != 65")
    return entry


def patch_record(raw: bytes, item_key: int, rate: int) -> bytes:
    p = parse_record(raw)
    new_count = p["nlist"] + 1
    entry = make_artifact_entry(item_key, rate)
    new_total = p["total"] + rate
    new_trailer = struct.pack("<Q", p["need"]) + struct.pack("<Q", new_total) + p["trailer"][16:]
    head = bytearray(raw[: p["list_count_off"]])
    head += struct.pack("<I", new_count)
    return bytes(head) + b"".join(p["entries"]) + entry + new_trailer


def verify_patch(
    vanilla_recs: list[tuple[int, bytes]],
    patched_recs: list[tuple[int, bytes]],
    target_keys: set[int],
    item_key: int,
    rate: int,
) -> list[int]:
    """Raise if anything other than the appended artifact entry and total bump differs."""
    if len(vanilla_recs) != len(patched_recs):
        raise RuntimeError(f"record count {len(vanilla_recs)} vs {len(patched_recs)}")
    if [k for k, _ in vanilla_recs] != [k for k, _ in patched_recs]:
        raise RuntimeError("key order changed")
    artifact = make_artifact_entry(item_key, rate)
    changed: list[int] = []
    for (vk, vb), (pk, pb) in zip(vanilla_recs, patched_recs):
        if vk != pk:
            raise RuntimeError("key mismatch")
        if vb == pb:
            if vk in target_keys:
                raise RuntimeError(f"target key {vk} was not changed")
            continue
        if vk not in target_keys:
            raise RuntimeError(f"non-target key {vk} changed")
        vp, pp = parse_record(vb), parse_record(pb)
        if pp["nlist"] != vp["nlist"] + 1:
            raise RuntimeError(f"{vk} nlist {vp['nlist']} -> {pp['nlist']}")
        if pp["entries"][:-1] != vp["entries"]:
            raise RuntimeError(f"{vk} existing entries changed")
        if pp["entries"][-1] != artifact:
            raise RuntimeError(f"{vk} appended entry mismatch")
        if pp["total"] != vp["total"] + rate:
            raise RuntimeError(f"{vk} total {vp['total']} -> {pp['total']}")
        if pp["need"] != vp["need"] or pp["skip"] != vp["skip"]:
            raise RuntimeError(f"{vk} trailer neighbours changed")
        if pp["trailer"][16:] != vp["trailer"][16:]:
            raise RuntimeError(f"{vk} trailer tail changed")
        if rec_name(vb) != rec_name(pb):
            raise RuntimeError(f"{vk} name changed")
        changed.append(vk)
    if set(changed) != target_keys:
        raise RuntimeError(f"changed {len(changed)} expected {len(target_keys)}")
    return changed
