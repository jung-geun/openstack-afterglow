#!/usr/bin/env python3
"""Validate immutable Waygate OCI image references before deployment mutation."""

from __future__ import annotations

import re
import sys

_REMOTE_DIGEST_REF = re.compile(
    r"^[a-z0-9]+(?:[._-][a-z0-9]+)*(?::[0-9]+)?/"
    r"[a-z0-9]+(?:[._/-][a-z0-9]+)*@sha256:[0-9a-f]{64}$"
)
_LOCAL_SOURCE_REF = re.compile(r"^afterglow-local/waygate-(?:api|worker):[0-9a-f]{12}$")


def validate_image_ref(reference: str, *, source_mode: bool) -> None:
    pattern = _LOCAL_SOURCE_REF if source_mode else _REMOTE_DIGEST_REF
    if not pattern.fullmatch(reference):
        expected = (
            "afterglow-local/waygate-{api|worker}:<12-hex-commit>"
            if source_mode
            else "registry/repository@sha256:<64-lowercase-hex>"
        )
        raise ValueError(f"invalid Waygate image reference; expected {expected}")


def main(reference: str, source_mode_arg: str) -> None:
    normalized_mode = source_mode_arg.strip().lower()
    if normalized_mode not in {"true", "false"}:
        raise ValueError("source mode must be true or false")
    validate_image_ref(reference, source_mode=normalized_mode == "true")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        raise SystemExit("usage: validate_image_ref.py IMAGE_REF SOURCE_MODE")
    try:
        main(sys.argv[1], sys.argv[2])
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
