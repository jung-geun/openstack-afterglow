"""Common API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "dashboard_router": ".dashboard",
    "libraries_router": ".libraries",
    "metrics_router": ".metrics",
    "sd_targets_router": ".sd_targets",
    "site_router": ".site",
    "user_dashboard_router": ".user_dashboard",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
