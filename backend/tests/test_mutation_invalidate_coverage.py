"""AST-based static check: all mutation routers must call cache invalidation.

Scope: scans every *.py under app/api/ and flags POST/PUT/PATCH/DELETE
handlers that contain no invalidation call.

Exemption tiers:
- EXEMPT_ROUTERS  : file-level (relative path from app/api/) — pending phases or
                    truly no-cache domains.
- EXEMPT_HANDLERS : handler-level (function name) — individual functions that
                    genuinely do not touch any cached resource state.
- INVALIDATING_HELPERS : function names that are known to call invalidation
                    internally; any handler that delegates to one of these is
                    treated as covered (e.g. _simple_action).
"""

import ast
from pathlib import Path

import pytest

API_DIR = Path(__file__).parent.parent / "app" / "api"

# ---------------------------------------------------------------------------
# File-level exemptions (relative path from API_DIR, e.g. "compute/images.py")
# ---------------------------------------------------------------------------
EXEMPT_ROUTERS: set[str] = {
    # Infrastructure / not-a-mutation
    "deps.py",
    # Auth & session — no OS resource cache to invalidate
    "identity/auth.py",
    "identity/profile.py",
    "identity/profile_activity.py",
    # Health / callback — not user-facing resource mutations
    "k3s/health.py",
    "compute/instance_health.py",
    "k3s/callback.py",
    # Validation utility endpoint — not a state-mutating operation
    "common/libraries.py",
    # Admin-only operations — manage OS infra directly; user-facing cache keys
    # are scoped per-project and not affected by these admin actions.
    "identity/admin.py",
    "identity/admin_flavors.py",
    "identity/admin_identity.py",
    "identity/admin_images.py",
    "identity/admin_instances.py",
    "identity/admin_gpu.py",
    "identity/admin_libraries.py",
    "identity/admin_notion.py",
    "identity/admin_orphans.py",
    "identity/admin_services.py",
    # ------------------------------------------------------------------
    # Phase C/D TODO — cache not yet wired up in these modules.
    # Remove each entry as the corresponding phase lands.
    # ------------------------------------------------------------------
    "compute/images.py",  # TODO: Phase C/D — image cache
    "container/clusters.py",  # TODO: Phase C/D — Magnum
    "container/containers.py",  # TODO: Phase C/D — Zun
    "database/instances.py",  # TODO: Phase C/D — Trove
    "k3s/clusters.py",  # TODO: Phase C/D — k3s
    "union/layers.py",  # TODO: Phase C/D — Union layers
    "network/loadbalancers.py",  # TODO: Phase C/D — listener/pool/member sub-resources
    "network/networks.py",  # TODO: Phase C/D — floating_ip / subnet sub-resources
    "network/routers.py",  # TODO: Phase C/D — interface / gateway sub-resources
    "object_storage/containers.py",  # TODO: Phase C/D — Swift object storage
    "object_storage/upload.py",  # TODO: Phase C/D — Swift upload
    "storage/file_storage.py",  # TODO: Phase C/D — access rule sub-resources
    "storage/volumes.py",  # TODO: Phase C/D — volume transfer sub-resources
    "storage/volume_backups.py",  # TODO: Phase C/D — backup / restore
}

# ---------------------------------------------------------------------------
# Handler-level exemptions (function name) — individual functions in otherwise
# scoped files that legitimately do not need cache invalidation.
# ---------------------------------------------------------------------------
EXEMPT_HANDLERS: set[str] = {
    # QGA password reset via Nova compute API — does not alter any field that
    # is stored in the instance cache (status, metadata, etc.).
    "set_admin_password",
}

# ---------------------------------------------------------------------------
# Known invalidating helpers — handlers that *call* one of these functions
# are considered covered even if no direct invalidation call is visible.
# ---------------------------------------------------------------------------
INVALIDATING_HELPERS: set[str] = {
    "_simple_action",  # compute/instances.py — start/stop/reboot/shelve/unshelve
}

# ---------------------------------------------------------------------------
# AST helpers
# ---------------------------------------------------------------------------


def get_http_methods(node: ast.AsyncFunctionDef) -> list[str]:
    """Return HTTP method decorators (post/put/patch/delete) on a function."""
    methods: list[str] = []
    for decorator in node.decorator_list:
        if isinstance(decorator, ast.Call):
            if isinstance(decorator.func, ast.Attribute):
                if decorator.func.attr in ("post", "put", "patch", "delete"):
                    methods.append(decorator.func.attr)
        elif isinstance(decorator, ast.Attribute):
            if decorator.attr in ("post", "put", "patch", "delete"):
                methods.append(decorator.attr)
    return methods


def has_invalidation_call(node: ast.AsyncFunctionDef) -> bool:
    """Return True if the function body contains a cache-invalidation call.

    Detects:
    - cache.invalidate(...)  / invalidate(...)
    - invalidate_tag(...)
    - bump_version(...)
    - invalidate_mutation_count(...)
    - Delegation to a known invalidating helper (e.g. _simple_action)
    """
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            if isinstance(child.func, ast.Attribute):
                if child.func.attr in (
                    "invalidate",
                    "invalidate_tag",
                    "bump_version",
                    "invalidate_mutation_count",
                ):
                    return True
            elif isinstance(child.func, ast.Name):
                if child.func.id in (
                    "invalidate",
                    "invalidate_tag",
                    "bump_version",
                    *INVALIDATING_HELPERS,
                ):
                    return True
    return False


def find_mutation_handlers_without_invalidation(filepath: Path) -> list[str]:
    """Return list of 'file:handler (methods)' strings for failing handlers."""
    source = filepath.read_text()
    tree = ast.parse(source)

    missing: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            if node.name in EXEMPT_HANDLERS:
                continue
            http_methods = get_http_methods(node)
            if http_methods and not has_invalidation_call(node):
                missing.append(f"{filepath.name}:{node.name} ({', '.join(http_methods)})")
    return missing


# ---------------------------------------------------------------------------
# Test
# ---------------------------------------------------------------------------


def test_mutation_handlers_have_invalidation() -> None:
    """All POST/PUT/PATCH/DELETE handlers must call cache invalidation.

    Handlers in EXEMPT_ROUTERS / EXEMPT_HANDLERS are explicitly whitelisted
    with documented reasons above.
    """
    all_missing: list[str] = []

    for py_file in sorted(API_DIR.rglob("*.py")):
        if py_file.name.startswith("_"):
            continue

        rel_path = str(py_file.relative_to(API_DIR))
        if rel_path in EXEMPT_ROUTERS:
            continue

        missing = find_mutation_handlers_without_invalidation(py_file)
        all_missing.extend(missing)

    if all_missing:
        msg = (
            "Mutation handlers missing cache invalidation:\n"
            + "\n".join(f"  - {m}" for m in sorted(all_missing))
            + "\n\nFix: add `await invalidate(...)` + `await cache_invalidation"
            ".invalidate_mutation_count(...)` after the mutation succeeds, or"
            " add the handler to EXEMPT_HANDLERS with a documented reason."
        )
        pytest.fail(msg)
