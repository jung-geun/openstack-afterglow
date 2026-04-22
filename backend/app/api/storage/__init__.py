"""Storage API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "file_storage_router": ".file_storage",
    "security_services_router": ".security_services",
    "share_networks_router": ".share_networks",
    "share_snapshots_router": ".share_snapshots",
    "volume_backups_router": ".volume_backups",
    "volume_snapshots_router": ".volume_snapshots",
    "volumes_router": ".volumes",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
