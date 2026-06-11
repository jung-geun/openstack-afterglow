"""
라이브러리 설정 레지스트리.

카탈로그는 MySQL `library_catalog` 테이블에 영속화되며, 동기 호출처를 위해
모듈 전역 메모리 캐시(`_catalog` / `_catalog_by_id`)를 유지한다.
기동 초기에는 `_DEFAULT_CATALOG` seed 로 캐시를 채우고, DB 초기화 후
`load_catalog_from_db()` 가 DB 내용으로 캐시를 갱신한다.
실제 파일 스토리지 ID 는 Manila에서 조회해 채운다.
"""

from __future__ import annotations

import logging

from app.models.storage import LibraryConfig

_logger = logging.getLogger(__name__)

# 코드 하드코딩 카탈로그를 seed 상수로 강등. DB 가 비어있을 때만 사용된다.
_DEFAULT_CATALOG: list[LibraryConfig] = [
    LibraryConfig(
        id="python311",
        name="Python 3.11",
        version="3.11",
        packages=["python3.11", "python3.11-pip", "python3.11-venv"],
        depends_on=[],
    ),
    LibraryConfig(
        id="torch",
        name="PyTorch 2.x",
        version="2.4",
        packages=["torch==2.4.0", "torchvision==0.19.0", "torchaudio==2.4.0"],
        depends_on=["python311"],
    ),
    LibraryConfig(
        id="vllm",
        name="vLLM",
        version="0.6",
        packages=["vllm==0.6.0"],
        depends_on=["python311", "torch"],
    ),
    LibraryConfig(
        id="jupyter",
        name="Jupyter Lab",
        version="4.x",
        packages=["jupyterlab==4.2.0", "ipykernel"],
        depends_on=["python311"],
    ),
    LibraryConfig(
        id="apache-php",
        name="Apache + PHP + phpMyAdmin",
        version="8.x",
        packages=["apache2", "libapache2-mod-php", "php", "php-mysql", "phpmyadmin"],
        depends_on=[],
        share_proto="NFS",
    ),
]

# 메모리 캐시 — 기동 초기에는 seed 로 초기화.
_catalog: list[LibraryConfig] = list(_DEFAULT_CATALOG)
_catalog_by_id: dict[str, LibraryConfig] = {lib.id: lib for lib in _catalog}


def get_all() -> list[LibraryConfig]:
    return _catalog


def get_by_id(lib_id: str) -> LibraryConfig:
    if lib_id not in _catalog_by_id:
        raise KeyError(f"알 수 없는 라이브러리: {lib_id}")
    return _catalog_by_id[lib_id]


def resolve_with_deps(selected_ids: list[str]) -> list[str]:
    """
    선택된 라이브러리 ID 목록에서 의존성을 포함한 전체 목록을 토폴로지 정렬로 반환.
    반환 순서: 하위 의존성 먼저 (lowerdir 구성 시 역순으로 사용).
    """
    resolved = []
    visited = set()

    def visit(lib_id: str):
        if lib_id in visited:
            return
        visited.add(lib_id)
        lib = _catalog_by_id.get(lib_id)
        if lib is None:
            return
        for dep in lib.depends_on:
            visit(dep)
        resolved.append(lib_id)

    for lib_id in selected_ids:
        visit(lib_id)

    return resolved


def check_python_version_conflict(selected_ids: list[str]) -> str | None:
    """선택된 라이브러리들 간 Python 버전 충돌 여부 확인.

    각 라이브러리의 version 필드가 Python 버전을 나타내는 경우(id가 python*인 경우)를
    기준으로 충돌을 감지. 충돌 시 에러 메시지를, 충돌이 없으면 None 반환.
    """
    python_libs = [_catalog_by_id[lid] for lid in selected_ids if lid in _catalog_by_id and lid.startswith("python")]
    if len(python_libs) <= 1:
        return None
    versions = {lib.version for lib in python_libs}
    if len(versions) > 1:
        names = ", ".join(lib.name for lib in python_libs)
        return f"Python 버전 충돌: {names} 중 하나만 선택해야 합니다."
    return None


def get_dependency_tree(lib_id: str) -> dict:
    """라이브러리의 의존성 트리를 반환한다 (재귀)."""
    lib = _catalog_by_id.get(lib_id)
    if lib is None:
        return {"id": lib_id, "name": "알 수 없음", "deps": []}
    return {
        "id": lib.id,
        "name": lib.name,
        "version": lib.version,
        "visibility": lib.visibility,
        "deps": [get_dependency_tree(dep_id) for dep_id in lib.depends_on],
    }


def validate_compatibility(
    selected_ids: list[str],
    ubuntu_version: str | None = None,
) -> list[str]:
    """선택된 라이브러리 조합의 호환성을 검증.

    Returns:
        경고/에러 메시지 목록. 빈 리스트이면 호환.
    """
    messages: list[str] = []

    # 알 수 없는 라이브러리 ID 확인
    unknown = [lid for lid in selected_ids if lid not in _catalog_by_id]
    if unknown:
        messages.append(f"알 수 없는 라이브러리: {', '.join(unknown)}")

    known_ids = [lid for lid in selected_ids if lid in _catalog_by_id]
    if not known_ids:
        return messages

    # Python 버전 충돌 확인
    conflict = check_python_version_conflict(known_ids)
    if conflict:
        messages.append(conflict)

    # Ubuntu 버전 호환성 확인
    if ubuntu_version:
        incompatible = []
        for lid in known_ids:
            lib = _catalog_by_id[lid]
            if lib.ubuntu_versions and ubuntu_version not in lib.ubuntu_versions:
                incompatible.append(f"{lib.name} (지원: {', '.join(lib.ubuntu_versions)})")
        if incompatible:
            messages.append(f"Ubuntu {ubuntu_version} 미지원 라이브러리: {'; '.join(incompatible)}")

    return messages


# ---------------------------------------------------------------------------
# DB 연동 — 카탈로그 영속화 및 캐시 갱신
# ---------------------------------------------------------------------------


def _row_to_config(row) -> LibraryConfig:
    """LibraryCatalog ORM row → LibraryConfig (id 필드 매핑)."""
    return LibraryConfig(
        id=row.library_id,
        name=row.name,
        version=row.version,
        packages=list(row.packages or []),
        depends_on=list(row.depends_on or []),
        share_proto=row.share_proto,
        ubuntu_versions=list(row.ubuntu_versions or []),
        visibility=row.visibility,
        license_type=row.license_type,
        max_concurrent_mounts=row.max_concurrent_mounts,
    )


async def load_catalog_from_db() -> None:
    """DB의 LibraryCatalog rows를 읽어 메모리 캐시를 갱신한다.

    DB가 미초기화이거나 행이 없으면 기존 캐시(_DEFAULT_CATALOG 포함)를 유지한다.
    """
    global _catalog, _catalog_by_id

    from app.database import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return

    from sqlalchemy import select

    from app.models.db import LibraryCatalog

    async with factory() as session:
        rows = (await session.execute(select(LibraryCatalog))).scalars().all()

    if not rows:
        return

    configs = [_row_to_config(row) for row in rows]
    _catalog = configs
    _catalog_by_id = {lib.id: lib for lib in configs}
    _logger.info("[libraries] DB 카탈로그 로드 완료: %d개", len(configs))


async def seed_default_catalog() -> None:
    """DB에 없는 _DEFAULT_CATALOG 항목만 INSERT (멱등)."""
    from app.database import get_session_factory

    factory = get_session_factory()
    if factory is None:
        return

    from sqlalchemy import select

    from app.models.db import LibraryCatalog

    async with factory() as session:
        for cfg in _DEFAULT_CATALOG:
            existing = (
                await session.execute(select(LibraryCatalog).where(LibraryCatalog.library_id == cfg.id))
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                LibraryCatalog(
                    library_id=cfg.id,
                    name=cfg.name,
                    version=cfg.version,
                    packages=list(cfg.packages),
                    depends_on=list(cfg.depends_on),
                    share_proto=cfg.share_proto,
                    ubuntu_versions=list(cfg.ubuntu_versions),
                    visibility=cfg.visibility,
                    license_type=cfg.license_type,
                    max_concurrent_mounts=cfg.max_concurrent_mounts,
                )
            )
            _logger.info("[libraries] 기본 카탈로그 seed: %s", cfg.id)
        await session.commit()


async def reload_catalog() -> None:
    """CRUD 후 캐시를 DB 기준으로 다시 로드한다 (load_catalog_from_db alias)."""
    await load_catalog_from_db()
