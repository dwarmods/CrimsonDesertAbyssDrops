#!/usr/bin/env python3
"""Build Abyss Kill Drops DMM overlay zips from a vanilla dropsetinfo table."""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
ROOT = TOOLS.parent
sys.path.insert(0, str(TOOLS))

from dropset import load_index, make_artifact_entry, parse_record, patch_record, rec_name, verify_patch, write_table  # noqa: E402


def load_config(path: Path) -> dict:
    return json.loads(path.read_text())


def resolve(root: Path, maybe: str | Path) -> Path:
    p = Path(maybe)
    return p if p.is_absolute() else root / p


def package_readme(n: int, version: str, game_version: str, percent: str) -> str:
    extra = (
        "\n**Install only one Abyss Kill Drops rate version at a time** "
        "(e.g. do not mount 1-in-30 together with this file).\n"
        if n != 30
        else "\n**Install only one Abyss Kill Drops rate version at a time** "
        "(e.g. do not mount 1-in-20 together with 1-in-30).\n"
    )
    return f"""# Abyss Kill Drops (1 in {n}) v{version}

Regular enemies get about a 1-in-{n} ({percent}) chance to drop one Abyss Artifact when killed.
{extra}
## What it changes
- Adds an Abyss Artifact roll to 35 common enemy and faction drop sets (bandits, soldiers, mercenaries, bounty hunters and hostile factions). See sets.txt.
- The roll is independent; it doesn't replace or reduce any existing loot.
- Bosses, civilians, animals, chests, quest rewards, and sets that already drop Artifacts are unchanged.
- Only the base drop table is replaced; DLC drop data is left vanilla.

## Requirements
- Crimson Desert (Steam), **{game_version}**. This version was rebuilt on the {game_version} drop table and is not for earlier game versions.
- Definitive Mod Manager (DMM)

## Install
1. Remove any older Abyss Kill Drops versions from DMM first (including other rate variants).
2. Import this zip in DMM and mount.

## Compatibility
- Works alongside DesertLink Add Item 1.3.13.
- Conflicts with any other mod that replaces or edits dropsetinfo (the drop table). Only one can win.
- A game patch that changes the drop table will need an updated version of this mod.

## Uninstall
Unmount in DMM.
"""


def package_manifest(cfg: dict, n: int, percent: str, version: str, game_version: str) -> dict:
    return {
        "format": cfg["format"],
        "id": f"AbyssKillDrops_1in{n}",
        "title": f"Abyss Kill Drops (1 in {n})",
        "author": cfg["author"],
        "version": version,
        "description": (
            f"Regular enemies have about a 1-in-{n} ({percent}) chance to drop an Abyss Artifact on kill. "
            "Affects 35 common enemy and faction drop sets. Bosses, civilians, animals, chests and quest drops are unchanged. "
            f"Install only one Abyss Kill Drops rate version at a time. Built for game {game_version}."
        ),
        "enabled": True,
        "priority": cfg.get("priority", 1),
        "files_dir": cfg.get("files_dir", "files"),
    }


def sets_text(cfg: dict) -> str:
    return "".join(f"- {entry['name']}\n" for entry in cfg["drop_sets"])


def load_vanilla(base: Path) -> tuple[bytes, bytes, bytes, list[tuple[int, bytes]]]:
    body_path = base / "dropsetinfo.staticinfobody"
    hdr_path = base / "dropsetinfo.staticinfoheader"
    if not body_path.is_file() or not hdr_path.is_file():
        raise SystemExit(f"vanilla body/header not found under {base}")
    vbody = body_path.read_bytes()
    vhdr = hdr_path.read_bytes()
    prefix, recs = load_index(vbody, vhdr)
    return vbody, vhdr, prefix, recs


def resolve_targets(cfg: dict, vanilla: list[tuple[int, bytes]]) -> list[int]:
    vanilla_map = {k: b for k, b in vanilla}
    targets: list[int] = []
    for entry in cfg["drop_sets"]:
        name, key = entry["name"], int(entry["key"])
        if key not in vanilla_map:
            raise SystemExit(f"missing target {name} key={key} in vanilla table")
        got = rec_name(vanilla_map[key])
        if got != name:
            raise SystemExit(f"name mismatch key={key}: {got!r} vs {name!r}")
        targets.append(key)
    expected = 35
    if len(targets) != expected:
        raise SystemExit(f"expected {expected} set keys, got {len(targets)}")
    return targets


def build_one(
    cfg: dict,
    prefix: bytes,
    vanilla: list[tuple[int, bytes]],
    target_set: set[int],
    rate_spec: dict,
    version: str,
    game_version: str,
    out_root: Path,
) -> Path:
    n = int(rate_spec["n"])
    rate = int(rate_spec["rate"])
    percent = rate_spec["percent"]
    item_key = int(cfg["item_key"])
    patched = [
        (key, patch_record(raw, item_key, rate) if key in target_set else raw)
        for key, raw in vanilla
    ]
    verify_patch(vanilla, patched, target_set, item_key, rate)
    body, hdr = write_table(prefix, patched)
    prefix2, recs2 = load_index(body, hdr)
    if prefix2 != prefix:
        raise RuntimeError("header prefix changed")
    verify_patch(vanilla, recs2, target_set, item_key, rate)

    folder = out_root / f"AbyssKillDrops_1in{n}_v{version}"
    if folder.exists():
        shutil.rmtree(folder)
    dest = folder / cfg.get("overlay_path", "files/0008/gamedata/binarystaticinfo__/bin")
    dest.mkdir(parents=True)
    (dest / "dropsetinfo.staticinfobody").write_bytes(body)
    (dest / "dropsetinfo.staticinfoheader").write_bytes(hdr)
    (folder / "manifest.json").write_text(
        json.dumps(package_manifest(cfg, n, percent, version, game_version), indent=2) + "\n"
    )
    (folder / "README.md").write_text(package_readme(n, version, game_version, percent))
    (folder / "sets.txt").write_text(sets_text(cfg))

    zpath = out_root / f"AbyssKillDrops_1in{n}_v{version}.zip"
    if zpath.exists():
        zpath.unlink()
    shutil.make_archive(str(out_root / f"AbyssKillDrops_1in{n}_v{version}"), "zip", root_dir=folder)
    if not zpath.is_file():
        raise RuntimeError(f"zip not written: {zpath}")
    print(
        f"1-in-{n}: rate={rate} body={len(body)} hdr={len(hdr)} records={len(recs2)} "
        f"delta={len(body) - sum(len(r) for _, r in vanilla)} zip={zpath.name} ({zpath.stat().st_size} bytes)"
    )
    return zpath


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root")
    parser.add_argument("--config", type=Path, default=None, help="path to config/mod.json")
    parser.add_argument("--base", type=Path, default=None, help="directory with vanilla body/header")
    parser.add_argument("--out", type=Path, default=None, help="output directory (default: dist/)")
    parser.add_argument("--version", default=None, help="override package version (default: config)")
    args = parser.parse_args(argv)

    root = args.root.resolve()
    cfg_path = args.config or (root / "config" / "mod.json")
    cfg = load_config(resolve(root, cfg_path) if not Path(cfg_path).is_absolute() else cfg_path)
    version = args.version or cfg["version"]
    game_version = cfg["game_version"]
    base = resolve(root, args.base or cfg["vanilla_base"])
    out_root = resolve(root, args.out or "dist")
    out_root.mkdir(parents=True, exist_ok=True)

    vbody, vhdr, prefix, vanilla = load_vanilla(base)
    targets = resolve_targets(cfg, vanilla)
    target_set = set(targets)
    item_key = int(cfg["item_key"])
    print(f"vanilla records={len(vanilla)} body={len(vbody)} hdr={len(vhdr)}")
    print(f"targets={len(targets)} all present by key and name")

    # The constructed artifact entry must match an existing vanilla artifact row.
    sample = make_artifact_entry(item_key, 10000)
    if not any(sample in parse_record(raw)["entries"] for _, raw in vanilla):
        raise SystemExit("constructed artifact entry (rate 10000) not found in vanilla table")

    for rate_spec in cfg["rates"]:
        build_one(cfg, prefix, vanilla, target_set, rate_spec, version, game_version, out_root)
    print(f"OK {len(cfg['rates'])} builds in {out_root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
