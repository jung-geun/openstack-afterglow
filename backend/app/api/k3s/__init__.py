"""K3s API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "k3s_callback_router": ".callback",
    "k3s_clusters_router": ".clusters",
    "k3s_configmaps_router": ".configmaps",
    "k3s_health_router": ".health",
    "k3s_secrets_router": ".secrets",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
