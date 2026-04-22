"""Network API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "loadbalancers_router": ".loadbalancers",
    "networks_router": ".networks",
    "routers_router": ".routers",
    "security_groups_router": ".security_groups",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)