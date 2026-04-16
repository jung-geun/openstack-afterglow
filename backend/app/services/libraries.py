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
