"""Common API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "announcements_router": ".announcements",
    "dashboard_router": ".dashboard",
    "grafana_auth_router": ".grafana_auth",
    "libraries_router": ".libraries",
    "metrics_router": ".metrics",
    "sd_targets_router": ".sd_targets",
    "site_router": ".site",
    "tutorial_status_router": ".tutorial_status",
    "user_dashboard_router": ".user_dashboard",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
