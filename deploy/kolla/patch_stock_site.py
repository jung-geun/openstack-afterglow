#!/usr/bin/env python3
"""Install or remove the exact Afterglow import in Kolla's stock site.yml."""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

BEGIN = "# BEGIN openstack-afterglow plugin"
END = "# END openstack-afterglow plugin"
BLOCK = f"{BEGIN}\n- import_playbook: afterglow-site.yml\n{END}\n"


def fail(message: str) -> None:
    raise RuntimeError(message)

def managed_block_bounds(original: str) -> tuple[int, int]:
    start = original.index(BEGIN)
    end = original.index(END)
    if end < start:
        fail("managed marker is malformed")
    finish = end + len(END)
    if original[finish : finish + 1] == "\n":
        finish += 1
    return start, finish


def patch(path: Path, action: str) -> None:
    try:
        original = path.read_text(encoding="utf-8")
        original_stat = path.stat()
    except OSError as error:
        fail(f"cannot read {path}: {error}")

    begin_count = original.count(BEGIN)
    end_count = original.count(END)
    if begin_count != end_count or begin_count > 1:
        fail(f"managed marker in {path} is malformed")

    if action == "install":
        if begin_count:
            start, finish = managed_block_bounds(original)
            if original[start:finish] != BLOCK:
                fail(f"managed block in {path} does not match the expected content")
            return
        updated = original.rstrip() + "\n\n" + BLOCK
    else:
        if not begin_count:
            return
        start, finish = managed_block_bounds(original)
        if original[start:finish] != BLOCK:
            fail(f"managed block in {path} does not match the expected content")
        updated = (original[:start].rstrip() + "\n" + original[finish:].lstrip("\n")).rstrip() + "\n"

    temporary = path.with_name(f".{path.name}.afterglow.tmp")
    try:
        temporary.write_text(updated, encoding="utf-8")
        os.chmod(temporary, stat.S_IMODE(original_stat.st_mode))
        os.chown(temporary, original_stat.st_uid, original_stat.st_gid)
        os.replace(temporary, path)
    except OSError as error:
        temporary.unlink(missing_ok=True)
        fail(f"cannot update {path}: {error}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("install", "remove"))
    parser.add_argument("site_path", type=Path)
    args = parser.parse_args()
    try:
        patch(args.site_path, args.action)
    except RuntimeError as error:
        print(error, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
