#!/usr/bin/env python3
"""Verify built Abyss Kill Drops overlays against the vanilla table.

Checks, for every rate variant:
  - record count and key order match vanilla
  - exactly the configured drop sets differ
  - each changed record only appends the artifact entry and bumps total_drop_rate

Optionally compare the built body/header to a reference folder or zip
(byte-for-byte) so a rebuild can be confirmed against a known-good release.
"""
from __future__ import annotations

import argparse
import json
import sys
import zipfile
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from dropset import load_index, rec_name, verify_patch  # noqa: E402

BODY_REL = "files/0008/gamedata/binarystaticinfo__/bin/dropsetinfo.staticinfobody"
HDR_REL = "files/0008/gamedata/binarystaticinfo__/bin/dropsetinfo.staticinfoheader"


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def resolve(root: Path, maybe: str | Path) -> Path:
    p = Path(maybe)
    return p if p.is_absolute() else root / p


def read_table_from_dir(folder: Path) -> tuple[bytes, bytes]:
    return (folder / BODY_REL).read_bytes(), (folder / HDR_REL).read_bytes()


def read_table_from_zip(zpath: Path) -> tuple[bytes, bytes]:
    with zipfile.ZipFile(zpath) as zf:
        return zf.read(BODY_REL), zf.read(HDR_REL)


def load_built(path: Path) -> tuple[bytes, bytes]:
    if path.is_dir():
        return read_table_from_dir(path)
    if path.is_file() and path.suffix == ".zip":
        return read_table_from_zip(path)
    raise SystemExit(f"not a built overlay folder or zip: {path}")


def find_reference(ref_root: Path, n: int, version: str) -> Path | None:
    candidates = [
        ref_root / f"AbyssKillDrops_1in{n}_v{version}.zip",
        ref_root / f"AbyssKillDrops_1in{n}_v{version}",
        ref_root / f"AbyssKillDrops_1in{n}.zip",
        ref_root / f"AbyssKillDrops_1in{n}",
    ]
    for c in candidates:
        if c.exists():
            return c
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--base", type=Path, default=None)
    parser.add_argument("--dist", type=Path, default=None, help="directory of built zips/folders")
    parser.add_argument("--version", default=None)
    parser.add_argument(
        "--reference",
        type=Path,
        default=None,
        help="optional folder of known-good zips/folders to compare body/header bytes",
    )
    args = parser.parse_args(argv)

    root = args.root.resolve()
    cfg_path = resolve(root, args.config or "config/mod.json")
    cfg = load_config(cfg_path)
    version = args.version or cfg["version"]
    base = resolve(root, args.base or cfg["vanilla_base"])
    dist = resolve(root, args.dist or "dist")
    item_key = int(cfg["item_key"])
    target_keys = {int(e["key"]) for e in cfg["drop_sets"]}
    names = {int(e["key"]): e["name"] for e in cfg["drop_sets"]}

    vbody = (base / "dropsetinfo.staticinfobody").read_bytes()
    vhdr = (base / "dropsetinfo.staticinfoheader").read_bytes()
    prefix, vanilla = load_index(vbody, vhdr)
    print(f"vanilla records={len(vanilla)} body={len(vbody)} hdr={len(vhdr)}")

    if not dist.is_dir():
        raise SystemExit(f"dist directory not found: {dist}")

    checked = 0
    for rate_spec in cfg["rates"]:
        n = int(rate_spec["n"])
        rate = int(rate_spec["rate"])
        folder = dist / f"AbyssKillDrops_1in{n}_v{version}"
        zpath = dist / f"AbyssKillDrops_1in{n}_v{version}.zip"
        source = folder if folder.is_dir() else zpath
        if not source.exists():
            raise SystemExit(f"missing build output for 1-in-{n}: {folder} or {zpath}")
        body, hdr = load_built(source)
        pfx, recs = load_index(body, hdr)
        if pfx != prefix:
            raise SystemExit(f"1-in-{n}: header prefix changed")
        if len(recs) != len(vanilla):
            raise SystemExit(f"1-in-{n}: record count {len(recs)} vs vanilla {len(vanilla)}")
        verify_patch(vanilla, recs, target_keys, item_key, rate)
        for key, raw in recs:
            if key in names and rec_name(raw) != names[key]:
                raise SystemExit(f"1-in-{n}: name drift on key {key}")
        print(
            f"1-in-{n}: records={len(recs)} changed={len(target_keys)} "
            f"body={len(body)} (+{len(body) - len(vbody)}) OK"
        )

        if args.reference:
            ref = find_reference(resolve(root, args.reference), n, version)
            if ref is None:
                raise SystemExit(f"1-in-{n}: no reference overlay under {args.reference}")
            rbody, rhdr = load_built(ref)
            if body != rbody:
                raise SystemExit(f"1-in-{n}: staticinfobody does not match {ref}")
            if hdr != rhdr:
                raise SystemExit(f"1-in-{n}: staticinfoheader does not match {ref}")
            print(f"1-in-{n}: body/header match {ref.name}")
        checked += 1

    if checked != len(cfg["rates"]):
        raise SystemExit("not all rate variants were checked")
    print(f"OK verified {checked} variants")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
