"""Palimpsest 허브 API — digest 로 레이어를 저장·검색·배포한다.

업로드는 OCI Distribution 의 blob upload(POST/PATCH/PUT)를 `/v2/` 없이 차용한다 —
중단 후 재개가 가능하고 구현자에게 익숙하다. **선언된 digest 는 신뢰하지 않는다**:
완료 시 수신 바이트로 digest 를 재계산해 불일치면 폐기한다(fail-closed).

부모 체인 일괄 다운로드는 `POST /bundles` 가 OCI image-layout tar 로 흘린다.
설계는 `docs/palimpsest.md`.
"""

from __future__ import annotations

import logging
import re
import tempfile
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request, UploadFile
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator
from sqlalchemy import select

from app.api.deps import get_token_info, require_admin
from app.config import get_settings
from app.database import get_session_factory
from app.models.db import PalimpsestHubLayer, PalimpsestHubUpload
from app.services.palimpsest_digest import (
    compute_config_digest,
    is_digest_prefix,
    normalize_digest,
    normalize_md5,
)
from app.services.palimpsest_hub_bundle import (
    BundleError,
    BundleLayer,
    extract_blob,
    iter_bundle_tar,
    parse_bundle,
)
from app.services.palimpsest_hub_store import (
    MEDIA_TYPE_LAYER_SQUASHFS,
    HubDigestMismatch,
    HubStoreError,
    HubStoreUnavailable,
    get_blob_store,
    write_upload_stream,
)

_logger = logging.getLogger(__name__)

router = APIRouter()

_NAME_RE = re.compile(r"^[a-z0-9][a-z0-9.+\-]{0,63}$")
_KIND_RE = re.compile(r"^[a-z][a-z0-9_-]{0,15}$")
_UBUNTU_BASE_RE = re.compile(r"^[a-z0-9][a-z0-9.\-]{0,63}$")
_PY_VERSION_RE = re.compile(r"^\d+\.\d+$")
_RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
_MAX_REFS = 32
_MAX_BUNDLE_UPLOAD_BYTES = 64 * 1024 * 1024 * 1024  # 64 GiB


# ---------------------------------------------------------------------------
# 스키마
# ---------------------------------------------------------------------------


class HubUploadStartRequest(BaseModel):
    """업로드 세션 시작. digest 를 미리 선언하면 이미 있는 콘텐츠는 즉시 완료로 단축된다."""

    digest: str | None = None

    @field_validator("digest")
    @classmethod
    def _check_digest(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_digest(value)
        if normalized is None:
            raise ValueError("digest 는 sha256:<64hex> 형식이어야 합니다")
        return normalized


class HubLayerMeta(BaseModel):
    """업로드 완료 시 함께 등록할 레이어 메타."""

    name: str
    kind: str = "squashfs"
    ubuntu_base: str | None = None
    python_version: str | None = None
    parent_digest: str | None = None
    chain_id: str | None = None
    is_published: bool = False

    @field_validator("name")
    @classmethod
    def _check_name(cls, value: str) -> str:
        if not _NAME_RE.match(value):
            raise ValueError("name 은 소문자/숫자/점/플러스/하이픈만 허용하며 64자 이하입니다")
        return value

    @field_validator("kind")
    @classmethod
    def _check_kind(cls, value: str) -> str:
        if not _KIND_RE.match(value):
            raise ValueError("kind 형식이 유효하지 않습니다")
        return value

    @field_validator("ubuntu_base")
    @classmethod
    def _check_base(cls, value: str | None) -> str | None:
        if value is not None and not _UBUNTU_BASE_RE.match(value):
            raise ValueError("ubuntu_base 형식이 유효하지 않습니다")
        return value

    @field_validator("python_version")
    @classmethod
    def _check_py(cls, value: str | None) -> str | None:
        if value is not None and not _PY_VERSION_RE.match(value):
            raise ValueError("python_version 은 major.minor 형식이어야 합니다")
        return value

    @field_validator("parent_digest", "chain_id")
    @classmethod
    def _check_digests(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = normalize_digest(value)
        if normalized is None:
            raise ValueError("digest 는 sha256:<64hex> 형식이어야 합니다")
        return normalized


class BundleExportRequest(BaseModel):
    refs: list[str] = Field(..., min_length=1, max_length=_MAX_REFS)

    @field_validator("refs")
    @classmethod
    def _check_refs(cls, values: list[str]) -> list[str]:
        normalized = []
        for value in values:
            digest = normalize_digest(value)
            if digest is None:
                raise ValueError("refs 항목은 sha256:<64hex> 형식이어야 합니다")
            normalized.append(digest)
        return normalized


# ---------------------------------------------------------------------------
# 공통
# ---------------------------------------------------------------------------


def _factory_or_503():
    factory = get_session_factory()
    if factory is None:
        raise HTTPException(status_code=503, detail="DB 연결이 초기화되지 않았습니다")
    return factory


def _store_or_503():
    try:
        return get_blob_store()
    except HubStoreUnavailable as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


def _project_id(token_info: dict) -> str | None:
    return token_info.get("project_id")


def _visible_filter(stmt, token_info: dict):
    """공개(`is_published`) 이거나 사이트 공용(`project_id IS NULL`) 이거나 내 프로젝트 것."""
    project_id = _project_id(token_info)
    return stmt.where(
        PalimpsestHubLayer.is_published.is_(True)
        | PalimpsestHubLayer.project_id.is_(None)
        | (PalimpsestHubLayer.project_id == project_id)
    )


def _layer_dict(row: PalimpsestHubLayer) -> dict[str, Any]:
    return {
        "blob_digest": row.blob_digest,
        "blob_md5": row.blob_md5,
        "size_bytes": row.size_bytes,
        "media_type": row.media_type,
        "config_digest": row.config_digest,
        "chain_id": row.chain_id,
        "parent_digest": row.parent_digest,
        "name": row.name,
        "kind": row.kind,
        "ubuntu_base": row.ubuntu_base,
        "python_version": row.python_version,
        "project_id": row.project_id,
        "is_published": row.is_published,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


async def _load_visible(session, digest: str, token_info: dict) -> PalimpsestHubLayer:
    row = (
        await session.execute(
            _visible_filter(select(PalimpsestHubLayer), token_info).where(PalimpsestHubLayer.blob_digest == digest)
        )
    ).scalar_one_or_none()
    if row is None:
        # 비공개 항목의 존재 여부를 흘리지 않는다 — 403 이 아니라 404
        raise HTTPException(status_code=404, detail="레이어를 찾을 수 없습니다")
    return row


async def _ancestor_chain(session, row: PalimpsestHubLayer, token_info: dict) -> list[PalimpsestHubLayer]:
    """루트 → 자기 자신 순서. 부모가 허브에 없으면 거기서 끊는다(사이클 방어 포함)."""
    chain: list[PalimpsestHubLayer] = [row]
    seen = {row.blob_digest}
    cursor = row.parent_digest
    while cursor:
        if cursor in seen:
            _logger.warning("[palimpsest_hub] 부모 체인 사이클 감지: %s", cursor)
            break
        seen.add(cursor)
        parent = (
            await session.execute(
                _visible_filter(select(PalimpsestHubLayer), token_info).where(PalimpsestHubLayer.blob_digest == cursor)
            )
        ).scalar_one_or_none()
        if parent is None:
            break
        chain.append(parent)
        cursor = parent.parent_digest
    return list(reversed(chain))


# ---------------------------------------------------------------------------
# 검색 / 조회
# ---------------------------------------------------------------------------


@router.get("/layers")
async def search_hub_layers(
    digest: str | None = Query(None),
    digest_prefix: str | None = Query(None),
    md5: str | None = Query(None, description="보조 검색 키. 무결성 권위는 sha256 이다"),
    chain_id: str | None = Query(None),
    name: str | None = Query(None),
    kind: str | None = Query(None),
    parent_digest: str | None = Query(None),
    limit: int = Query(50, ge=1, le=200),
    token_info: dict = Depends(get_token_info),
) -> list[dict[str, Any]]:
    # 입력 검증이 먼저 — 잘못된 요청은 DB/스토어 상태와 무관하게 422 여야 한다.
    stmt = _visible_filter(select(PalimpsestHubLayer), token_info)

    for value, column, label in (
        (digest, PalimpsestHubLayer.blob_digest, "digest"),
        (chain_id, PalimpsestHubLayer.chain_id, "chain_id"),
        (parent_digest, PalimpsestHubLayer.parent_digest, "parent_digest"),
    ):
        if value is not None:
            normalized = normalize_digest(value)
            if normalized is None:
                raise HTTPException(status_code=422, detail=f"{label} 는 sha256:<64hex> 형식이어야 합니다")
            stmt = stmt.where(column == normalized)

    if digest_prefix is not None:
        if not is_digest_prefix(digest_prefix):
            raise HTTPException(status_code=422, detail="digest_prefix 는 hex 4~64자여야 합니다")
        bare = digest_prefix.strip().lower().removeprefix("sha256:")
        stmt = stmt.where(PalimpsestHubLayer.blob_digest.startswith(f"sha256:{bare}"))

    if md5 is not None:
        normalized_md5 = normalize_md5(md5)
        if normalized_md5 is None:
            raise HTTPException(status_code=422, detail="md5 는 32자리 hex 여야 합니다")
        stmt = stmt.where(PalimpsestHubLayer.blob_md5 == normalized_md5)

    if name is not None:
        if not _NAME_RE.match(name):
            raise HTTPException(status_code=422, detail="name 형식이 유효하지 않습니다")
        stmt = stmt.where(PalimpsestHubLayer.name == name)

    if kind is not None:
        if not _KIND_RE.match(kind):
            raise HTTPException(status_code=422, detail="kind 형식이 유효하지 않습니다")
        stmt = stmt.where(PalimpsestHubLayer.kind == kind)

    factory = _factory_or_503()
    async with factory() as session:
        rows = (await session.execute(stmt.order_by(PalimpsestHubLayer.id.desc()).limit(limit))).scalars().all()
        return [_layer_dict(row) for row in rows]


@router.get("/layers/{digest}")
async def get_hub_layer(digest: str, token_info: dict = Depends(get_token_info)) -> dict[str, Any]:
    normalized = normalize_digest(digest)
    if normalized is None:
        raise HTTPException(status_code=422, detail="digest 는 sha256:<64hex> 형식이어야 합니다")
    factory = _factory_or_503()
    async with factory() as session:
        row = await _load_visible(session, normalized, token_info)
        chain = await _ancestor_chain(session, row, token_info)
        return {
            **_layer_dict(row),
            "ancestors": [item.blob_digest for item in chain[:-1]],
            "chain_complete": (chain[0].parent_digest is None),
        }


@router.get("/layers/{digest}/ancestors")
async def get_hub_layer_ancestors(digest: str, token_info: dict = Depends(get_token_info)) -> list[dict[str, Any]]:
    """루트 → 자기 자신 순서. 허브에 없는 조상에서 끊기며 `chain_complete` 로 판별한다."""
    normalized = normalize_digest(digest)
    if normalized is None:
        raise HTTPException(status_code=422, detail="digest 는 sha256:<64hex> 형식이어야 합니다")
    factory = _factory_or_503()
    async with factory() as session:
        row = await _load_visible(session, normalized, token_info)
        return [_layer_dict(item) for item in await _ancestor_chain(session, row, token_info)]


@router.get("/layers/{digest}/blob")
async def download_hub_blob(
    digest: str, request: Request, token_info: dict = Depends(get_token_info)
) -> StreamingResponse:
    normalized = normalize_digest(digest)
    if normalized is None:
        raise HTTPException(status_code=422, detail="digest 는 sha256:<64hex> 형식이어야 합니다")
    factory = _factory_or_503()
    store = _store_or_503()
    async with factory() as session:
        row = await _load_visible(session, normalized, token_info)

    if not store.exists(normalized):
        raise HTTPException(status_code=404, detail="blob 이 저장소에 없습니다")

    total = row.size_bytes
    start, length, status_code = 0, total, 200
    headers = {
        "Accept-Ranges": "bytes",
        "Cache-Control": "no-store",
        "Content-Disposition": f'attachment; filename="{normalized[len("sha256:") : len("sha256:") + 12]}.sqsh"',
    }

    range_header = request.headers.get("range")
    if range_header:
        match = _RANGE_RE.match(range_header.strip())
        if not match:
            raise HTTPException(status_code=416, detail="지원하지 않는 Range 형식입니다")
        raw_start, raw_end = match.group(1), match.group(2)
        if raw_start:
            start = int(raw_start)
            end = int(raw_end) if raw_end else total - 1
        else:  # suffix range: bytes=-N
            suffix = int(raw_end or 0)
            start = max(0, total - suffix)
            end = total - 1
        if start >= total or end < start:
            raise HTTPException(status_code=416, detail="Range 가 blob 범위를 벗어났습니다")
        end = min(end, total - 1)
        length = end - start + 1
        status_code = 206
        headers["Content-Range"] = f"bytes {start}-{end}/{total}"

    headers["Content-Length"] = str(length)
    return StreamingResponse(
        store.iter_blob(normalized, start=start, length=length),
        status_code=status_code,
        media_type=row.media_type or MEDIA_TYPE_LAYER_SQUASHFS,
        headers=headers,
    )


# ---------------------------------------------------------------------------
# 업로드 (POST → PATCH… → PUT)
# ---------------------------------------------------------------------------


@router.post("/uploads")
async def start_upload(req: HubUploadStartRequest, token_info: dict = Depends(get_token_info)) -> dict[str, Any]:
    factory = _factory_or_503()
    store = _store_or_503()

    # 이미 있는 콘텐츠면 업로드 자체를 건너뛴다 — content-addressable 의 이점.
    if req.digest and store.exists(req.digest):
        async with factory() as session:
            existing = (
                await session.execute(select(PalimpsestHubLayer).where(PalimpsestHubLayer.blob_digest == req.digest))
            ).scalar_one_or_none()
        return {
            "session_id": None,
            "completed": True,
            "blob_digest": req.digest,
            "already_present": True,
            "registered": existing is not None,
        }

    session_id = uuid.uuid4().hex
    store.start_upload(session_id)
    async with factory() as session:
        session.add(
            PalimpsestHubUpload(
                id=session_id,
                declared_digest=req.digest,
                received_bytes=0,
                project_id=_project_id(token_info),
                created_by=token_info.get("user_id"),
            )
        )
        await session.commit()
    return {"session_id": session_id, "completed": False, "received_bytes": 0}


async def _owned_upload(session, session_id: str, token_info: dict) -> PalimpsestHubUpload:
    upload = await session.get(PalimpsestHubUpload, session_id)
    if upload is None:
        raise HTTPException(status_code=404, detail="업로드 세션을 찾을 수 없습니다")
    # 남의 세션에 바이트를 밀어 넣지 못하게 한다(IDOR)
    if upload.project_id is not None and upload.project_id != _project_id(token_info):
        raise HTTPException(status_code=404, detail="업로드 세션을 찾을 수 없습니다")
    return upload


@router.patch("/uploads/{session_id}")
async def append_upload(
    session_id: str, request: Request, token_info: dict = Depends(get_token_info)
) -> dict[str, Any]:
    factory = _factory_or_503()
    store = _store_or_503()
    settings = get_settings()

    async with factory() as session:
        upload = await _owned_upload(session, session_id, token_info)
        already = upload.received_bytes

    try:
        total = await write_upload_stream(
            store,
            session_id,
            request.stream(),
            already_received=already,
            max_bytes=settings.palimpsest_hub_max_blob_bytes,
        )
    except HubStoreError as exc:
        async with factory() as session:
            upload = await session.get(PalimpsestHubUpload, session_id)
            if upload is not None:
                await session.delete(upload)
                await session.commit()
        raise HTTPException(status_code=413, detail=str(exc)) from exc

    async with factory() as session:
        upload = await session.get(PalimpsestHubUpload, session_id)
        if upload is not None:
            upload.received_bytes = total
            await session.commit()
    return {"session_id": session_id, "received_bytes": total}


@router.put("/uploads/{session_id}")
async def finalize_upload(
    session_id: str, meta: HubLayerMeta, token_info: dict = Depends(get_token_info)
) -> dict[str, Any]:
    """수신 바이트의 digest 를 재계산해 검증하고 레이어로 등록한다."""
    factory = _factory_or_503()
    store = _store_or_503()

    async with factory() as session:
        upload = await _owned_upload(session, session_id, token_info)
        declared = upload.declared_digest

    try:
        finalized = store.finalize_upload(session_id, declared)
    except HubDigestMismatch as exc:
        async with factory() as session:
            row = await session.get(PalimpsestHubUpload, session_id)
            if row is not None:
                await session.delete(row)
                await session.commit()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except HubStoreError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    config = {
        "name": meta.name,
        "kind": meta.kind,
        "ubuntu_base": meta.ubuntu_base,
        "python_version": meta.python_version,
        "parent_digest": meta.parent_digest,
        "chain_id": meta.chain_id,
        "blob_digest": finalized.blob_digest,
    }

    async with factory() as session:
        existing = (
            await session.execute(
                select(PalimpsestHubLayer).where(PalimpsestHubLayer.blob_digest == finalized.blob_digest)
            )
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PalimpsestHubLayer(
                    blob_digest=finalized.blob_digest,
                    blob_md5=finalized.blob_md5,
                    size_bytes=finalized.size_bytes,
                    media_type=MEDIA_TYPE_LAYER_SQUASHFS,
                    config_digest=compute_config_digest(config),
                    chain_id=meta.chain_id,
                    parent_digest=meta.parent_digest,
                    name=meta.name,
                    kind=meta.kind,
                    ubuntu_base=meta.ubuntu_base,
                    python_version=meta.python_version,
                    config_json=config,
                    project_id=_project_id(token_info),
                    is_published=meta.is_published,
                    created_by=token_info.get("user_id"),
                )
            )
        upload = await session.get(PalimpsestHubUpload, session_id)
        if upload is not None:
            await session.delete(upload)
        await session.commit()

    return {
        "blob_digest": finalized.blob_digest,
        "blob_md5": finalized.blob_md5,
        "size_bytes": finalized.size_bytes,
        "already_present": existing is not None,
    }


@router.delete("/uploads/{session_id}", status_code=204)
async def abort_upload(session_id: str, token_info: dict = Depends(get_token_info)) -> None:
    factory = _factory_or_503()
    store = _store_or_503()
    async with factory() as session:
        upload = await _owned_upload(session, session_id, token_info)
        await session.delete(upload)
        await session.commit()
    store.abort_upload(session_id)


# ---------------------------------------------------------------------------
# 번들 (부모 체인 일괄 다운로드 / 가져오기)
# ---------------------------------------------------------------------------


@router.post("/bundles")
async def export_bundle(req: BundleExportRequest, token_info: dict = Depends(get_token_info)) -> StreamingResponse:
    """요청한 leaf 들의 **부모 체인 전체**를 OCI image-layout tar 로 흘린다."""
    factory = _factory_or_503()
    store = _store_or_503()

    chains: list[list[BundleLayer]] = []
    async with factory() as session:
        for ref in req.refs:
            row = await _load_visible(session, ref, token_info)
            chain_rows = await _ancestor_chain(session, row, token_info)
            if chain_rows[0].parent_digest is not None:
                raise HTTPException(
                    status_code=409,
                    detail=f"부모 체인이 허브에 완전하지 않습니다: {chain_rows[0].parent_digest} 누락",
                )
            for item in chain_rows:
                if not store.exists(item.blob_digest):
                    raise HTTPException(status_code=409, detail=f"blob 이 저장소에 없습니다: {item.blob_digest}")
            chains.append(
                [
                    BundleLayer(
                        blob_digest=item.blob_digest,
                        size_bytes=item.size_bytes,
                        name=item.name,
                        config=dict(item.config_json or {}),
                    )
                    for item in chain_rows
                ]
            )

    try:
        stream = iter_bundle_tar(store, chains)
    except BundleError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return StreamingResponse(
        stream,
        media_type="application/x-tar",
        headers={
            "Cache-Control": "no-store",
            "Content-Disposition": 'attachment; filename="palimpsest-bundle.tar"',
        },
    )


@router.post("/bundles/import")
async def import_bundle(file: UploadFile, token_info: dict = Depends(get_token_info)) -> dict[str, Any]:
    """번들을 받아 blob digest 를 **전부 재검증**한 뒤 허브에 등록한다."""
    factory = _factory_or_503()
    store = _store_or_503()

    imported: list[str] = []
    skipped: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory(prefix="palimpsest-import-") as tmpdir:
        tmp = Path(tmpdir)
        bundle_path = tmp / "bundle.tar"
        size = 0
        with bundle_path.open("wb") as out:
            while chunk := await file.read(1024 * 1024):
                size += len(chunk)
                if size > _MAX_BUNDLE_UPLOAD_BYTES:
                    raise HTTPException(status_code=413, detail="번들 크기 상한을 초과했습니다")
                out.write(chunk)

        try:
            parsed = parse_bundle(bundle_path)
        except (BundleError, HubStoreError) as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        async with factory() as session:
            for entry in parsed.layers:
                declared = entry["blob_digest"]
                try:
                    staged = tmp / f"blob-{declared[len('sha256:') :][:16]}"
                    extract_blob(bundle_path, parsed.blob_members[declared], staged)
                    finalized = store.ingest_file(staged)
                    staged.unlink(missing_ok=True)
                    # 번들이 선언한 digest 와 실제 바이트가 다르면 받지 않는다(fail-closed).
                    if finalized.blob_digest != declared:
                        store.delete(finalized.blob_digest)
                        skipped.append({"digest": declared, "error": "digest 불일치"})
                        continue
                except (BundleError, HubStoreError, KeyError, OSError) as exc:
                    skipped.append({"digest": declared, "error": str(exc)[:200]})
                    continue

                existing = (
                    await session.execute(select(PalimpsestHubLayer).where(PalimpsestHubLayer.blob_digest == declared))
                ).scalar_one_or_none()
                if existing is not None:
                    skipped.append({"digest": declared, "error": "이미 허브에 있음"})
                    continue

                config = dict(entry.get("config") or {})
                # 부모는 **manifest layers[] 순서**에서 온 값을 쓴다(parse_bundle 이 채운다).
                # config 는 leaf 것만 실려 오므로 여기서 읽으면 조상이 전부 루트가 된다.
                parent_digest = normalize_digest(entry.get("parent_digest") or "")
                name = config.get("name") or entry.get("name") or ""
                if not _NAME_RE.match(name or ""):
                    skipped.append({"digest": declared, "error": "레이어 이름 형식이 유효하지 않습니다"})
                    continue
                kind = config.get("kind") or "squashfs"
                if not _KIND_RE.match(kind):
                    skipped.append({"digest": declared, "error": "kind 형식이 유효하지 않습니다"})
                    continue

                session.add(
                    PalimpsestHubLayer(
                        blob_digest=declared,
                        blob_md5=finalized.blob_md5,
                        size_bytes=finalized.size_bytes,
                        media_type=MEDIA_TYPE_LAYER_SQUASHFS,
                        config_digest=compute_config_digest(config or {"blob_digest": declared}),
                        chain_id=normalize_digest(config.get("chain_id") or ""),
                        parent_digest=parent_digest,
                        name=name,
                        kind=kind,
                        ubuntu_base=config.get("ubuntu_base"),
                        python_version=config.get("python_version"),
                        config_json=config or {"blob_digest": declared},
                        project_id=_project_id(token_info),
                        is_published=False,
                        created_by=token_info.get("user_id"),
                    )
                )
                imported.append(declared)
            await session.commit()

    return {"imported": imported, "imported_count": len(imported), "skipped": skipped}


# ---------------------------------------------------------------------------
# 삭제
# ---------------------------------------------------------------------------


@router.delete("/layers/{digest}", status_code=204, dependencies=[Depends(require_admin)])
async def delete_hub_layer(digest: str) -> None:
    """관리자 전용. **자식이 있으면 거부**한다 — union.md §10 GC 규칙을 계승한다."""
    normalized = normalize_digest(digest)
    if normalized is None:
        raise HTTPException(status_code=422, detail="digest 는 sha256:<64hex> 형식이어야 합니다")
    factory = _factory_or_503()
    store = _store_or_503()

    async with factory() as session:
        row = (
            await session.execute(select(PalimpsestHubLayer).where(PalimpsestHubLayer.blob_digest == normalized))
        ).scalar_one_or_none()
        if row is None:
            raise HTTPException(status_code=404, detail="레이어를 찾을 수 없습니다")
        child = (
            await session.execute(
                select(PalimpsestHubLayer.id).where(PalimpsestHubLayer.parent_digest == normalized).limit(1)
            )
        ).scalar_one_or_none()
        if child is not None:
            raise HTTPException(status_code=409, detail="자식 레이어가 있어 삭제할 수 없습니다")
        await session.delete(row)
        await session.commit()
    store.delete(normalized)
