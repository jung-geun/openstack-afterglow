"""
라이브러리 설정 레지스트리.
실제 파일 스토리지 ID 는 Manila에서 조회해 채운다.
"""

from app.models.storage import LibraryConfig

LIBRARY_CATALOG: list[LibraryConfig] = [
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
]

_catalog_by_id = {lib.id: lib for lib in LIBRARY_CATALOG}


def get_all() -> list[LibraryConfig]:
    return LIBRARY_CATALOG


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
