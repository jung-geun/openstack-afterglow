"""라이브러리 빌드 레시피 헬퍼 — DB에서 LibraryRecipe를 조회한다."""

from __future__ import annotations

import logging
import types

_logger = logging.getLogger(__name__)

_UV_BOOTSTRAP = (
    "curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh\nexport PATH=/usr/local/bin:$PATH\n"
)

# python311 설치 스크립트 (v2): Python ThreadPoolExecutor×16 병렬 복사
# 측정값 (CephFS NFS4.2, RTT 20ms): cp -a=1766ms/파일 → parallel=108ms/파일 (16배 빠름)
# 3946개 파일 기준: cp -a ≈116분 → parallel ≈7분
_PYTHON311_INSTALL_SCRIPT = (
    "uv python install cpython-3.11 --install-dir /tmp/py311\n"
    # uv는 cpython-3.11-* (심볼릭 링크) → cpython-3.11.15-* (실제 디렉토리) 구조로 설치한다
    "PYDIR=$(readlink -f /tmp/py311/cpython-3.11-linux-x86_64-gnu 2>/dev/null)\n"
    'if [ -z "$PYDIR" ] || [ ! -d "$PYDIR" ]; then\n'
    "  PYDIR=\"/tmp/py311/$(ls /tmp/py311/ | grep 'cpython-3\\.11\\.' | head -1)\"\n"
    "fi\n"
    "mkdir -p /mnt/share/usr/local\n"
    "cat > /tmp/pycopy.py << 'PYEOF'\n"
    "import os, sys, shutil, concurrent.futures\n"
    "src, dst = sys.argv[1], sys.argv[2]\n"
    "items = []\n"
    "for dp, dirs, files in os.walk(src, followlinks=False):\n"
    "    rel = os.path.relpath(dp, src)\n"
    "    td = dst if rel == '.' else os.path.join(dst, rel)\n"
    "    os.makedirs(td, exist_ok=True)\n"
    "    for n in files: items.append((os.path.join(dp, n), os.path.join(td, n)))\n"
    "    real = []\n"
    "    for n in dirs:\n"
    "        s = os.path.join(dp, n)\n"
    "        if os.path.islink(s): items.append((s, os.path.join(td, n)))\n"
    "        else: real.append(n)\n"
    "    dirs[:] = real\n"
    "def cp(pair):\n"
    "    s, d = pair\n"
    "    if os.path.islink(s):\n"
    "        try: os.symlink(os.readlink(s), d)\n"
    "        except FileExistsError: pass\n"
    "    else: shutil.copy2(s, d)\n"
    "with concurrent.futures.ThreadPoolExecutor(max_workers=16) as ex:\n"
    "    list(ex.map(cp, items))\n"
    "PYEOF\n"
    'python3 /tmp/pycopy.py "$PYDIR" /mnt/share/usr/local\n'
    "mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages\n"
)

# 기본 레시피 정의 — DB seed와 DB 비가용 시 fallback에서 공유 사용
_BUILTIN_RECIPE_DEFS: dict[str, dict] = {
    "python311": {
        "share_size_gb": 5,
        "share_proto": "NFS",
        "apt_packages": [],
        "commands": [
            {"step": "install_uv", "progress_pct": 20, "script": _UV_BOOTSTRAP},
            {
                "step": "install_python311",
                "progress_pct": 80,
                "script": _PYTHON311_INSTALL_SCRIPT,
            },
        ],
    },
    "torch": {
        "share_size_gb": 20,
        "share_proto": "NFS",
        "apt_packages": ["python3.11"],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": _UV_BOOTSTRAP},
            {
                "step": "install_torch",
                "progress_pct": 80,
                "script": (
                    "mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages\n"
                    "uv pip install --python python3.11 --no-cache \\\n"
                    "    --target /mnt/share/usr/local/lib/python3.11/site-packages \\\n"
                    "    torch==2.4.0 torchvision==0.19.0 torchaudio==2.4.0\n"
                ),
            },
        ],
    },
    "vllm": {
        "share_size_gb": 15,
        "share_proto": "NFS",
        "apt_packages": ["python3.11"],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": _UV_BOOTSTRAP},
            {
                "step": "install_vllm",
                "progress_pct": 80,
                "script": (
                    "mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages\n"
                    "uv pip install --python python3.11 --no-cache \\\n"
                    "    --target /mnt/share/usr/local/lib/python3.11/site-packages \\\n"
                    "    vllm==0.6.0\n"
                ),
            },
        ],
    },
    "jupyter": {
        "share_size_gb": 5,
        "share_proto": "NFS",
        "apt_packages": ["python3.11"],
        "commands": [
            {"step": "install_uv", "progress_pct": 10, "script": _UV_BOOTSTRAP},
            {
                "step": "install_jupyter",
                "progress_pct": 80,
                "script": (
                    "mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages\n"
                    "uv pip install --python python3.11 --no-cache \\\n"
                    "    --target /mnt/share/usr/local/lib/python3.11/site-packages \\\n"
                    "    jupyterlab==4.2.0 ipykernel\n"
                ),
            },
        ],
    },
}


def _builtin_recipe_ns(library_id: str) -> types.SimpleNamespace | None:
    """DB 비가용 시 빌트인 기본 레시피를 SimpleNamespace로 반환한다."""
    d = _BUILTIN_RECIPE_DEFS.get(library_id)
    if d is None:
        return None
    return types.SimpleNamespace(
        library_id=library_id,
        version=1,
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
    """기본 라이브러리 레시피를 DB에 없으면 삽입한다."""
    from app.database import get_session_factory
    from app.models.db import LibraryRecipe

    factory = get_session_factory()
    if factory is None:
        return

    from sqlalchemy import select

    async with factory() as session:
        for lib_id, entry in _BUILTIN_RECIPE_DEFS.items():
            existing = (
                await session.execute(
                    select(LibraryRecipe).where(
                        LibraryRecipe.library_id == lib_id,
                        LibraryRecipe.version == 1,
                    )
                )
            ).scalar_one_or_none()
            if existing is not None:
                continue
            session.add(
                LibraryRecipe(
                    library_id=lib_id,
                    version=1,
                    commands=entry["commands"],
                    apt_packages=entry.get("apt_packages", []),
                    pip_packages=[],
                    share_size_gb=entry["share_size_gb"],
                    share_proto=entry["share_proto"],
                    cloud_init_template_version=1,
                )
            )
            _logger.info("[library_recipes] 기본 레시피 seed: %s", lib_id)
        await session.commit()

    # python311 v2: 병렬 Python 복사 (cp -a → ThreadPoolExecutor×16)
    # v1이 DB에 있어도 v2가 없으면 삽입 — get_recipe()는 최신 버전(desc)을 선택
    async with factory() as session:
        v2_exists = (
            await session.execute(
                select(LibraryRecipe).where(
                    LibraryRecipe.library_id == "python311",
                    LibraryRecipe.version == 2,
                )
            )
        ).scalar_one_or_none()
        if v2_exists is None:
            entry = _BUILTIN_RECIPE_DEFS["python311"]
            session.add(
                LibraryRecipe(
                    library_id="python311",
                    version=2,
                    commands=entry["commands"],
                    apt_packages=entry.get("apt_packages", []),
                    pip_packages=[],
                    share_size_gb=entry["share_size_gb"],
                    share_proto=entry["share_proto"],
                    cloud_init_template_version=1,
                )
            )
            await session.commit()
            _logger.info("[library_recipes] python311 v2 seed: 병렬 Python 복사 적용")

    # pytorch = torch 동일 (alias)
    async with factory() as session:
        torch_row = (
            await session.execute(
                select(LibraryRecipe).where(
                    LibraryRecipe.library_id == "torch",
                    LibraryRecipe.version == 1,
                )
            )
        ).scalar_one_or_none()
        pytorch_exists = (
            await session.execute(
                select(LibraryRecipe).where(
                    LibraryRecipe.library_id == "pytorch",
                    LibraryRecipe.version == 1,
                )
            )
        ).scalar_one_or_none()
        if torch_row and not pytorch_exists:
            session.add(
                LibraryRecipe(
                    library_id="pytorch",
                    version=1,
                    commands=torch_row.commands,
                    apt_packages=torch_row.apt_packages,
                    pip_packages=torch_row.pip_packages,
                    share_size_gb=torch_row.share_size_gb,
                    share_proto=torch_row.share_proto,
                    cloud_init_template_version=torch_row.cloud_init_template_version,
                )
            )
            await session.commit()
            _logger.info("[library_recipes] pytorch alias seed 완료")
