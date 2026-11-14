# Abyss Kill Drops

A [Crimson Desert](https://www.nexusmods.com/crimsondesert) mod. Regular enemies get a chance to drop an Abyss Artifact on kill. Pick your rate: 1 in 20, 30 (default), 50, 100, 200, 300 or 500. No other loot is touched.

- **Nexus Mods:** [crimsondesert/mods/4177](https://www.nexusmods.com/crimsondesert/mods/4177)
- **Current version:** 2.1.0, built for game **2.05.00**
- **Author:** Stas ([dwarmods](https://github.com/dwarmods))

This repository is the public source for the build script, the list of drop sets, and the release workflow. The v2.1.0 packages and this repo were built with AI assistance.

## What it does

The mod is a [Definitive Mod Manager](https://www.nexusmods.com/) (DMM) file overlay (`crimson_browser_mod_v1`). It replaces the base-game drop table (`dropsetinfo.staticinfobody` / `.staticinfoheader`) and leaves DLC drop data alone.

On each of 35 regular-enemy and faction drop sets it appends one independent Abyss Artifact roll (item key 75001) and bumps that set's `total_drop_rate` to match. Drop rates use a scale of 1,000,000 = 100%:

| Variant | Rate value | Chance |
| --- | ---: | ---: |
| 1 in 20 | 50,000 | 5.00% |
| 1 in 30 (default) | 33,333 | 3.33% |
| 1 in 50 | 20,000 | 2.00% |
| 1 in 100 | 10,000 | 1.00% |
| 1 in 200 | 5,000 | 0.50% |
| 1 in 300 | 3,333 | 0.33% |
| 1 in 500 | 2,000 | 0.20% |

The 35 sets are listed in [`config/sets.txt`](config/sets.txt) and [`config/mod.json`](config/mod.json). Bosses, civilians, animals, chests, quest rewards, and sets that already drop Artifacts are not changed. The extra roll does not replace or reduce any existing loot.

**Install only one rate version at a time.**

## Install

1. You need Crimson Desert (Steam) **2.05.00** and DMM.
2. Remove any older Abyss Kill Drops version from DMM first, including a different rate.
3. Download one zip from [Releases](https://github.com/dwarmods/CrimsonDesertAbyssDrops/releases) or from [Nexus Mods](https://www.nexusmods.com/crimsondesert/mods/4177).
4. Import the zip in DMM and mount it.

It works alongside DesertLink Add Item 1.3.13. It conflicts with any other mod that replaces or edits the drop table; only one can win. A game patch that changes the drop table needs a rebuilt version of this mod.

To uninstall, unmount it in DMM. Artifacts you already collected stay in your inventory.

v2.1.0 is not for game 2.04.x. The 2.04 files remain on the Nexus page under Old Files.

## Build

You need Python 3.10 or later. No third-party packages.

```bash
python tools/build.py
python tools/verify.py
```

That writes seven overlay folders and zips under `dist/`, using the vanilla 2.05.00 table in `base/2.05.00/` and the rates and set keys in `config/mod.json`.

Useful options:

```bash
python tools/build.py --version 2.1.0 --out dist
python tools/verify.py --reference /path/to/known-good-zips
```

`--reference` compares each built `.staticinfobody` and `.staticinfoheader` to a known-good release, byte for byte.

## After a game update

1. Extract the new vanilla `dropsetinfo.staticinfobody` and `dropsetinfo.staticinfoheader` from the game (DMM or a similar unpacker; the files may also appear as `dropsetinfo.pabgb` / `.pabgh`).
2. Put them in a new folder, for example `base/2.06.00/`.
3. Point `vanilla_base` and `game_version` in `config/mod.json` at that folder, and bump `version`.
4. Run `python tools/build.py` and `python tools/verify.py`. Verification fails if a listed set key is missing or a set name no longer matches, so the 35 keys are not guessed.
5. Tag `vX.Y.Z` and push it (see below).

## CI and releases

- [`.github/workflows/ci.yml`](.github/workflows/ci.yml) runs the build and verification on every push to `main` and on pull requests.
- [`.github/workflows/release.yml`](.github/workflows/release.yml) runs on a `v*` tag (or a manual `workflow_dispatch`). It builds, verifies, and creates a GitHub Release with the seven zips. If the repository secret `NEXUSMODS_API_KEY` is set, it then uploads a new version of each existing Nexus file through the official [Nexus Mods upload action](https://github.com/Nexus-Mods/upload-action) (v3 upload API). The 1-in-30 file is marked as the main download; the other rates are optional. If the secret is missing, the Nexus step is skipped with a warning and the GitHub Release is still published.

To cut a release:

```bash
git tag v2.2.0
git push origin v2.2.0
```

Enabling Nexus auto-upload takes a personal API key and one file ID per rate variant. Those steps are listed in the workflow file comments and should be done in the repository Settings; this repo does not store the key.

## Game data in this repository

`base/2.05.00/` holds the vanilla 2.05.00 drop table (body and header) so the overlays can be rebuilt in CI. That table is copyright Pearl Abyss. It is included only because each released overlay already ships the full table with 35 sets patched; committing the vanilla original adds no new game data beyond what the public downloads already contain. Do not use these files for anything other than rebuilding this mod.

## License

The build scripts, configuration, and documentation in this repository are released under the [MIT License](LICENSE). Game data remains the property of Pearl Abyss.
