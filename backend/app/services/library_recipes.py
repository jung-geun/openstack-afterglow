"""라이브러리 빌드 레시피 헬퍼 — DB에서 LibraryRecipe를 조회한다."""

from __future__ import annotations

import logging

_logger = logging.getLogger(__name__)


async def get_recipe(library_id: str, version: int | None = None):
    """library_id + version(없으면 최신)으로 LibraryRecipe를 조회한다.

    레시피가 없으면 None 반환.
    """
    from app.database import get_session_factory
    from app.models.db import LibraryRecipe

    factory = get_session_factory()
    if factory is None:
        return None

    from sqlalchemy import select

    async with factory() as session:
        q = select(LibraryRecipe).where(LibraryRecipe.library_id == library_id)
        if version is not None:
            q = q.where(LibraryRecipe.version == version)
        else:
            q = q.order_by(LibraryRecipe.version.desc())
        return (await session.execute(q)).scalars().first()


async def seed_default_recipes() -> None:
    """_INSTALL_SCRIPTS 기반 기본 레시피를 DB에 없으면 삽입한다."""
    from app.database import get_session_factory
    from app.models.db import LibraryRecipe

    factory = get_session_factory()
    if factory is None:
        return

    from sqlalchemy import select

    _UV_BOOTSTRAP = "curl -LsSf https://astral.sh/uv/install.sh | UV_INSTALL_DIR=/usr/local/bin sh\nexport PATH=/usr/local/bin:$PATH\n"

    _DEFAULTS: list[dict] = [
        {
            "library_id": "python311",
            "share_size_gb": 5,
            "share_proto": "NFS",
            "apt_packages": [],
            "commands": [
                {
                    "step": "install_uv",
                    "progress_pct": 20,
                    "script": _UV_BOOTSTRAP,
                },
                {
                    "step": "install_python311",
                    "progress_pct": 80,
                    "script": (
                        "uv python install cpython-3.11 --install-dir /tmp/py311\n"
                        "PYDIR=$(ls /tmp/py311/ | grep cpython-3.11 | head -1)\n"
                        "mkdir -p /mnt/share/usr/local\n"
                        'cp -a /tmp/py311/"$PYDIR"/. /mnt/share/usr/local/\n'
                        "mkdir -p /mnt/share/usr/local/lib/python3.11/site-packages\n"
                    ),
                },
            ],
        },
        {
            "library_id": "torch",
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
        {
            "library_id": "vllm",
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
        {
            "library_id": "jupyter",
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
    ]

    async with factory() as session:
        for entry in _DEFAULTS:
            lib_id = entry["library_id"]
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
