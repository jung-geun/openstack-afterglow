"""Identity API routers — lazy import to reduce startup time."""

_ROUTERS = {
    "admin_router": ".admin",
    "auth_router": ".auth",
    "mcp_access_router": ".mcp_access",
}

# OIDC 인증 API 라우터 - main.py에서 /api/v1/auth 경로로 마운트
_ATTR_ROUTERS = {
    "gitlab_auth_router": (".auth", "gitlab_router"),
}


def __getattr__(name: str):
    if name in _ROUTERS:
        import importlib

        mod = importlib.import_module(_ROUTERS[name], __package__)
        return mod.router
    if name in _ATTR_ROUTERS:
        import importlib

        module_path, attr = _ATTR_ROUTERS[name]
        mod = importlib.import_module(module_path, __package__)
        return getattr(mod, attr)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = list(_ROUTERS) + list(_ATTR_ROUTERS)
