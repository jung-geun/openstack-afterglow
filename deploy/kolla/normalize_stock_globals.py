#!/usr/bin/env python3
"""Remove only an exact duplicate Afterglow document from Kolla globals.yml."""

from __future__ import annotations

import argparse
import os
import shutil
import stat
import sys
from pathlib import Path

import yaml


def fail(message: str) -> None:
    raise RuntimeError(message)


def normalize(stock_globals: Path, plugin_globals: Path, backup: Path) -> str:
    try:
        original = stock_globals.read_text(encoding="utf-8")
        original_stat = stock_globals.stat()
        plugin = yaml.safe_load(plugin_globals.read_text(encoding="utf-8")) or {}
    except (OSError, yaml.YAMLError) as error:
        fail(f"cannot read Kolla globals: {error}")

    separator = "\n---\n"
    documents = original.split(separator)
    if len(documents) == 1:
        try:
            yaml.safe_load(original)
        except yaml.YAMLError as error:
            fail(f"stock globals.yml is invalid: {error}")
        return "stock globals.yml already has one document"
    if len(documents) != 2:
        fail("stock globals.yml has multiple documents that are not an exact plugin duplicate")

    try:
        first = yaml.safe_load(documents[0]) or {}
        duplicate = yaml.safe_load(documents[1]) or {}
    except yaml.YAMLError as error:
        fail(f"stock globals.yml is invalid: {error}")
    if not isinstance(first, dict) or not isinstance(duplicate, dict) or duplicate != plugin:
        fail("stock globals.yml trailing document does not exactly match plugin globals")
    if backup.exists():
        fail(f"refusing to overwrite existing backup: {backup}")

    temporary = stock_globals.with_name(f".{stock_globals.name}.afterglow.tmp")
    backup_created = False
    try:
        temporary.write_text(documents[0].rstrip() + "\n", encoding="utf-8")
        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        shutil.copy2(stock_globals, backup)
        backup_created = True
        os.replace(temporary, stock_globals)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        if backup_created:
            try:
                backup.unlink()
            except OSError:
                pass
        fail(f"cannot normalize stock globals.yml: {error}")
    return "removed exact duplicate Afterglow globals document"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("stock_globals", type=Path)
    parser.add_argument("plugin_globals", type=Path)
    parser.add_argument("backup", type=Path)
    args = parser.parse_args()
    try:
        print(normalize(args.stock_globals, args.plugin_globals, args.backup))
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
