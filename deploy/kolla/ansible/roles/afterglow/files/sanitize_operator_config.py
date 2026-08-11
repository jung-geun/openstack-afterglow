#!/usr/bin/env python3
"""Copy a valid Afterglow TOML file without legacy builder private-key material."""

from __future__ import annotations

import os
import re
import sys
import tempfile
import tomllib
from pathlib import Path

_SECTION = re.compile(r"^\s*\[([^]]+)\]\s*(?:#.*)?$")
_BUILDER_PRIVATE_KEY = re.compile(r"^\s*ssh_private_key\s*=")


def _sanitize(source_text: str) -> str:
    section = ""
    delimiter: str | None = None
    retained: list[str] = []

    for line in source_text.splitlines(keepends=True):
        if delimiter is not None:
            if line.count(delimiter) % 2:
                delimiter = None
            continue

        match = _SECTION.match(line)
        if match:
            section = match.group(1)

        if section != "builder" or not _BUILDER_PRIVATE_KEY.match(line):
            retained.append(line)
            continue

        value = line.split("=", 1)[1]
        for candidate in ('"""', "'''"):
            if value.count(candidate) % 2:
                delimiter = candidate
                break

    if delimiter is not None:
        raise ValueError("builder.ssh_private_key has an unterminated multiline TOML value")

    return "".join(retained)


def main(source_arg: str, destination_arg: str) -> None:
    source = Path(source_arg)
    destination = Path(destination_arg)
    source_text = source.read_text(encoding="utf-8")
    tomllib.loads(source_text)

    sanitized = _sanitize(source_text)
    parsed = tomllib.loads(sanitized)
    if "ssh_private_key" in parsed.get("builder", {}):
        raise ValueError("builder.ssh_private_key must not be staged")

    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        mode="w", encoding="utf-8", dir=destination.parent, delete=False
    ) as staging_file:
        staging_file.write(sanitized)
        staging_path = Path(staging_file.name)
    os.chmod(staging_path, 0o600)
    os.replace(staging_path, destination)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: sanitize_operator_config.py SOURCE DESTINATION")
    main(sys.argv[1], sys.argv[2])
