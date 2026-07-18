"""Chat(LibreChat 임베드) API 라우터 — lazy import to reduce startup time."""

_ROUTERS = {
    "chat_usage_router": ".usage",
    "chat_admin_router": ".models",
    "chat_conversations_router": ".conversations",
    "chat_completions_router": ".completions",
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS)
