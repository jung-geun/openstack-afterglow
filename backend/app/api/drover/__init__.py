"""Permanent Afterglow compatibility routes for the extracted Drover service."""

_ROUTERS = {
    "drover_admin_router": ".admin",
    "drover_callback_router": ".callback",
    "drover_proxy_router": ".proxy",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        module = importlib.import_module(_ROUTERS[name], __package__)
        return module.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
