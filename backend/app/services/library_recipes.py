"""라이브러리 빌드 레시피 — recipe_blocks 조합으로 정의하고 DB(LibraryRecipe)에 seed한다.

새 라이브러리 추가 절차:
  1. libraries.py `_DEFAULT_CATALOG`(또는 admin 카탈로그 CRUD API)에 카탈로그 항목 추가
  2. 아래 `_BUILTIN_RECIPE_DEFS`에 recipe_blocks 조합으로 레시피 추가 (version=1)
  3. 백엔드 재시작 시 자동 seed → 관리자 페이지에서 빌드 가능

레시피를 수정할 때는 동일 library_id에 version을 올려 추가한다 —
get_recipe()는 최신 버전을 선택하고, 기존 DB 행은 이력으로 보존된다.
"""

from __future__ import annotations

import logging
import types

from app.services import recipe_blocks as rb

_logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# 빌트인 레시피 정의 — DB seed와 DB 비가용 시 fallback에서 공유 사용
#
# version 이력:
#   python311 v1: cp -a 직렬 복사 / v2: ThreadPoolExecutor×16 병렬 복사
#              v3: recipe_blocks.python_layer 로 재정의 (v2와 동등 동작)
#   torch/vllm/jupyter v1: apt python3.11 의존 (Ubuntu 24.04에 없어 빌드 실패)
#                      v2: uv 관리 CPython 기반으로 수정 (Ubuntu 버전 무관)
#   apache-php v1: apt_capture_layer 기반 시스템 패키지 스택 (신규)
# ---------------------------------------------------------------------------

_BUILTIN_RECIPE_DEFS: dict[str, dict] = {
    "python311": {
        "version": 3,
        "share_size_gb": 5,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {"step": "install_uv", "progress_pct": 20, "script": rb.uv_bootstrap()},
            {"step": "install_python311", "progress_pct": 80, "script": rb.python_layer("3.11")},
        ],
    },
    "torch": {
        "version": 2,
        "share_size_gb": 20,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": rb.uv_bootstrap()},
            {
                "step": "install_torch",
                "progress_pct": 80,
                "script": rb.pip_layer(
                    ["torch==2.4.0", "torchvision==0.19.0", "torchaudio==2.4.0"],
                    python_version="3.11",
                ),
            },
        ],
    },
    "vllm": {
        "version": 2,
        "share_size_gb": 15,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": rb.uv_bootstrap()},
            {
                "step": "install_vllm",
                "progress_pct": 80,
                "script": rb.pip_layer(["vllm==0.6.0"], python_version="3.11"),
            },
        ],
    },
    "jupyter": {
        "version": 2,
        "share_size_gb": 5,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": rb.uv_bootstrap()},
            {
                "step": "install_jupyter",
                "progress_pct": 80,
                "script": rb.pip_layer(["jupyterlab==4.2.0", "ipykernel"], python_version="3.11"),
            },
        ],
    },
    "apache-php": {
        "version": 1,
        "share_size_gb": 5,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {
                "step": "install_apache_php",
                "progress_pct": 80,
                "script": rb.apt_capture_layer(
                    ["apache2", "libapache2-mod-php", "php", "php-mysql", "phpmyadmin"],
                    debconf_selections=[
                        "phpmyadmin phpmyadmin/dbconfig-install boolean false",
                        "phpmyadmin phpmyadmin/reconfigure-webserver multiselect apache2",
                    ],
                ),
            },
        ],
    },
}

# pytorch = torch 동일 (alias)
_RECIPE_ALIASES: dict[str, str] = {"pytorch": "torch"}


def _builtin_recipe_ns(library_id: str) -> types.SimpleNamespace | None:
    """DB 비가용 시 빌트인 기본 레시피를 SimpleNamespace로 반환한다."""
    real_id = _RECIPE_ALIASES.get(library_id, library_id)
    d = _BUILTIN_RECIPE_DEFS.get(real_id)
    if d is None:
        return None
    return types.SimpleNamespace(
        library_id=library_id,
        version=d["version"],
        share_proto=d.get("share_proto", "NFS"),
        share_size_gb=d.get("share_size_gb", 5),
        base_image_id=None,
        apt_packages=list(d.get("apt_packages", [])),
        commands=list(d.get("commands", [])),
    )


async def get_recipe(library_id: str, version: int | None = None):
    """library_id + version(없으면 최신)으로 LibraryRecipe를 조회한다.

    DB 비가용 시 빌트인 기본 레시피를 반환한다. 레시피가 없으면 None 반환.
    """
    from app.database import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return _builtin_recipe_ns(library_id)

    from sqlalchemy import select

    from app.models.db import LibraryRecipe

    async with factory() as session:
        q = select(LibraryRecipe).where(LibraryRecipe.library_id == library_id)
        if version is not None:
            q = q.where(LibraryRecipe.version == version)
        else:
            q = q.order_by(LibraryRecipe.version.desc())
        row = (await session.execute(q)).scalars().first()
        if row is None:
            # DB에 없으면 빌트인 fallback
            return _builtin_recipe_ns(library_id)
        return row


async def seed_default_recipes() -> None:
    """빌트인 레시피를 (library_id, version) 단위로 DB에 없으면 삽입한다 (멱등).

    레시피 정의가 바뀔 때 version을 올리면 다음 기동 시 자동으로 새 버전이
    seed되고 get_recipe()가 이를 선택한다. 구 버전 행은 이력으로 남는다.
    """
    from app.database import get_session_factory
    from app.models.db import LibraryRecipe

    factory = get_session_factory()
    if factory is None:
        return

    from sqlalchemy import select

    seed_targets = dict(_BUILTIN_RECIPE_DEFS)
    for alias, real_id in _RECIPE_ALIASES.items():
        seed_targets[alias] = _BUILTIN_RECIPE_DEFS[real_id]

    async with factory() as session:
        for lib_id, entry in seed_targets.items():
            existing = (
                await session.execute(
                    select(LibraryRecipe).where(
                        LibraryRecipe.library_id == lib_id,
                        LibraryRecipe.version == entry["version"],
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                LibraryRecipe(
                    library_id=lib_id,
                    version=entry["version"],
                    commands=entry["commands"],
                    apt_packages=entry.get("apt_packages", []),
                    pip_packages=[],
                    share_size_gb=entry["share_size_gb"],
                    share_proto=entry["share_proto"],
                    cloud_init_template_version=1,
                )
            )
            _logger.info("[library_recipes] 레시피 seed: %s v%d", lib_id, entry["version"])
        await session.commit()
