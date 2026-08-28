"""Waygate API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "waygate_agent_router": ".agent",
    "waygate_proxy_router": ".proxy",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
