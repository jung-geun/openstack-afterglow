"""Palimpsest 허브 회귀 테스트 — blob store · OCI 번들 · API 계약.

고정하는 계약:
- **선언된 digest 를 신뢰하지 않는다** — 완료 시 재계산해 불일치면 폐기(fail-closed)
- digest·세션 ID 는 경로 조립에 쓰이므로 traversal 을 거부한다
- 번들은 OCI image-layout 이고 **부모 체인 전체**를 담으며 중복 blob 은 한 번만 실린다
- 허브 미설정 배포에서는 503, 비공개 레이어는 존재 여부도 흘리지 않고 404
"""

from __future__ import annotations

import hashlib
import json
import tarfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from app.services.palimpsest_hub_bundle import (
    ANNOTATION_NAME,
    MEDIA_TYPE_MANIFEST,
    BundleError,
    BundleLayer,
    build_manifest,
    extract_blob,
    iter_bundle_tar,
    parse_bundle,
)
from app.services.palimpsest_hub_store import (
    MEDIA_TYPE_LAYER_SQUASHFS,
    HubDigestMismatch,
    HubStoreError,
    HubStoreUnavailable,
    LocalPathBlobStore,
    get_blob_store,
    write_upload_stream,
)


def _sha256(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


@pytest.fixture
def store(tmp_path: Path) -> LocalPathBlobStore:
    return LocalPathBlobStore(tmp_path / "hub")


def _put_blob(store: LocalPathBlobStore, payload: bytes) -> str:
    """테스트 헬퍼 — 업로드 경로를 거쳐 blob 을 넣는다."""
    session_id = "f" * 32
    store.start_upload(session_id)
    store.append_upload(session_id, payload)
    return store.finalize_upload(session_id, None).blob_digest


# ---------------------------------------------------------------------------
# blob store
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_digest",
    ["../../etc/passwd", "sha256:../x", "sha256:zz", "", "sha256:" + "a" * 63],
)
def test_blob_path_rejects_traversal_and_malformed_digest(store, bad_digest):
    with pytest.raises(HubStoreError):
        store.blob_path(bad_digest)


@pytest.mark.parametrize("bad_session", ["../escape", "gg" * 16, "short", "a" * 33])
def test_upload_path_rejects_malformed_session_id(store, bad_session):
    with pytest.raises(HubStoreError):
        store.upload_path(bad_session)


def test_upload_finalize_places_blob_at_content_addressed_path(store):
    payload = b"palimpsest layer bytes"

    digest = _put_blob(store, payload)

    assert digest == _sha256(payload)
    expected = store.root / "blobs" / "sha256" / digest[len("sha256:") :]
    assert expected.is_file()
    assert expected.read_bytes() == payload


def test_finalize_rejects_declared_digest_mismatch_and_discards_bytes(store):
    session_id = "a" * 32
    store.start_upload(session_id)
    store.append_upload(session_id, b"actual bytes")
    wrong = "sha256:" + "b" * 64

    with pytest.raises(HubDigestMismatch):
        store.finalize_upload(session_id, wrong)

    # 거짓 digest 로 올라온 바이트는 남기지 않는다
    assert not store.upload_path(session_id).exists()
    assert not (store.root / "blobs" / "sha256" / ("b" * 64)).exists()


def test_finalize_is_idempotent_for_identical_content(store):
    payload = b"same content"
    first = _put_blob(store, payload)

    session_id = "c" * 32
    store.start_upload(session_id)
    store.append_upload(session_id, payload)
    second = store.finalize_upload(session_id, first)

    assert second.blob_digest == first
    assert not store.upload_path(session_id).exists()  # 임시본 정리됨
    assert store.size(first) == len(payload)


def test_finalize_reports_md5_as_auxiliary_key(store):
    payload = b"md5 is a search key, not authority"
    session_id = "d" * 32
    store.start_upload(session_id)
    store.append_upload(session_id, payload)

    finalized = store.finalize_upload(session_id, None)

    assert finalized.blob_md5 == hashlib.md5(payload).hexdigest()  # noqa: S324
    assert finalized.blob_digest == _sha256(payload)


def test_iter_blob_supports_range_reads(store):
    payload = bytes(range(256)) * 8
    digest = _put_blob(store, payload)

    whole = b"".join(store.iter_blob(digest))
    middle = b"".join(store.iter_blob(digest, start=100, length=50))

    assert whole == payload
    assert middle == payload[100:150]


async def test_write_upload_stream_aborts_when_exceeding_limit(store):
    session_id = "e" * 32
    store.start_upload(session_id)

    async def _chunks():
        yield b"x" * 100
        yield b"y" * 100

    with pytest.raises(HubStoreError):
        await write_upload_stream(store, session_id, _chunks(), max_bytes=150)

    # 상한을 넘긴 세션은 즉시 폐기한다 — 디스크를 채우게 두지 않는다
    assert not store.upload_path(session_id).exists()


def test_get_blob_store_is_unavailable_without_configuration():
    with patch(
        "app.services.palimpsest_hub_store.get_settings",
        return_value=MagicMock(palimpsest_hub_local_path=""),
    ):
        with pytest.raises(HubStoreUnavailable):
            get_blob_store()


def test_prune_uploads_removes_only_stale_sessions(store):
    fresh, stale = "1" * 32, "2" * 32
    store.start_upload(fresh)
    store.start_upload(stale)
    import os

    os.utime(store.upload_path(stale), (0, 0))

    removed = store.prune_uploads(older_than_seconds=3600, now_epoch=10_000)

    assert removed == 1
    assert store.upload_path(fresh).exists()
    assert not store.upload_path(stale).exists()


# ---------------------------------------------------------------------------
# OCI 번들
# ---------------------------------------------------------------------------


def _chain(store: LocalPathBlobStore) -> list[BundleLayer]:
    """루트→리프 3단 체인을 만들고 blob 을 store 에 넣는다."""
    layers = []
    parent = None
    for name, payload in (("uvbase", b"uv"), ("python311", b"python"), ("torch", b"torch")):
        digest = _put_blob(store, payload)
        layers.append(
            BundleLayer(
                blob_digest=digest,
                size_bytes=len(payload),
                name=name,
                config={"name": name, "kind": "squashfs", "parent_digest": parent, "chain_id": digest},
            )
        )
        parent = digest
    return layers


def _read_tar(chunks) -> dict[str, bytes]:
    raw = b"".join(chunks)
    members: dict[str, bytes] = {}
    import io

    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        for info in tar.getmembers():
            handle = tar.extractfile(info)
            members[info.name] = handle.read() if handle else b""
    return members


def test_bundle_is_a_valid_oci_image_layout(store):
    chain = _chain(store)

    members = _read_tar(iter_bundle_tar(store, [chain]))

    assert json.loads(members["oci-layout"])["imageLayoutVersion"] == "1.0.0"
    index = json.loads(members["index.json"])
    assert index["schemaVersion"] == 2
    assert len(index["manifests"]) == 1
    assert index["manifests"][0]["mediaType"] == MEDIA_TYPE_MANIFEST
    assert all(name.startswith("blobs/sha256/") for name in members if name not in {"oci-layout", "index.json"})


def test_bundle_contains_full_parent_chain_root_first(store):
    chain = _chain(store)

    members = _read_tar(iter_bundle_tar(store, [chain]))
    index = json.loads(members["index.json"])
    manifest_digest = index["manifests"][0]["digest"]
    manifest = json.loads(members[f"blobs/sha256/{manifest_digest[len('sha256:') :]}"])

    # "부모 레이어를 추적해 한 번에 다운로드" = manifest 하나에 체인 전체가 있다
    assert [layer["digest"] for layer in manifest["layers"]] == [item.blob_digest for item in chain]
    assert [layer["annotations"][ANNOTATION_NAME] for layer in manifest["layers"]] == [
        "uvbase",
        "python311",
        "torch",
    ]
    for item in chain:
        assert f"blobs/sha256/{item.blob_digest[len('sha256:') :]}" in members


def test_bundle_emits_shared_ancestors_only_once(store):
    chain = _chain(store)
    # 같은 루트를 공유하는 두 번째 leaf
    sibling_payload = b"sibling"
    sibling_digest = _put_blob(store, sibling_payload)
    sibling_chain = [
        *chain[:2],
        BundleLayer(
            blob_digest=sibling_digest,
            size_bytes=len(sibling_payload),
            name="jax",
            config={"name": "jax", "kind": "squashfs", "parent_digest": chain[1].blob_digest},
        ),
    ]

    raw = b"".join(iter_bundle_tar(store, [chain, sibling_chain]))
    import io

    with tarfile.open(fileobj=io.BytesIO(raw), mode="r:") as tar:
        names = [info.name for info in tar.getmembers()]

    assert len(names) == len(set(names)), "중복 blob 이 두 번 실렸다 — content-addressable 위반"
    shared = f"blobs/sha256/{chain[0].blob_digest[len('sha256:') :]}"
    assert names.count(shared) == 1


def test_bundle_round_trips_through_parse(store, tmp_path):
    chain = _chain(store)
    bundle_path = tmp_path / "bundle.tar"
    bundle_path.write_bytes(b"".join(iter_bundle_tar(store, [chain])))

    parsed = parse_bundle(bundle_path)

    assert [entry["blob_digest"] for entry in parsed.layers] == [item.blob_digest for item in chain]
    assert set(parsed.blob_members) == {item.blob_digest for item in chain}

    # 꺼낸 blob 의 바이트가 보존되는지
    staged = tmp_path / "staged"
    leaf = chain[-1]
    extract_blob(bundle_path, parsed.blob_members[leaf.blob_digest], staged)
    assert _sha256(staged.read_bytes()) == leaf.blob_digest


def test_parse_bundle_reconstructs_parent_chain_from_manifest_order(store, tmp_path):
    """🔴 부모 체인의 권위는 manifest layers[] 순서다.

    config blob 에서 parent_digest 를 읽으면 안 된다 — manifest 는 leaf 의 config 만
    참조하므로 조상들이 전부 루트로 import 되어 체인이 조용히 사라진다.
    """
    chain = _chain(store)
    bundle_path = tmp_path / "bundle.tar"
    bundle_path.write_bytes(b"".join(iter_bundle_tar(store, [chain])))

    parsed = parse_bundle(bundle_path)

    parents = [entry["parent_digest"] for entry in parsed.layers]
    assert parents == [None, chain[0].blob_digest, chain[1].blob_digest]


def test_parse_bundle_handles_layers_with_identical_config(store, tmp_path):
    """config 가 완전히 같은 두 레이어가 한 번들에 있어도 manifest 가 깨지지 않아야 한다.

    config blob 은 콘텐츠 주소라 한 번만 실리지만, layers[] 는 두 항목 모두 가져야 한다.
    """
    same_config = {"name": "twin", "kind": "squashfs"}
    payloads = (b"first bytes", b"second bytes")
    twins = [
        BundleLayer(
            blob_digest=_put_blob(store, payload),
            size_bytes=len(payload),
            name="twin",
            config=same_config,
        )
        for payload in payloads
    ]

    bundle_path = tmp_path / "twins.tar"
    bundle_path.write_bytes(b"".join(iter_bundle_tar(store, [twins])))
    parsed = parse_bundle(bundle_path)

    assert [entry["blob_digest"] for entry in parsed.layers] == [t.blob_digest for t in twins]
    assert [entry["parent_digest"] for entry in parsed.layers] == [None, twins[0].blob_digest]


def test_parse_bundle_rejects_contradictory_parent_for_shared_ancestor(store, tmp_path):
    """두 manifest 가 같은 blob 에 서로 다른 부모를 주장하면 번들이 모순이다 — 거부한다."""
    chain = _chain(store)
    # 같은 leaf 를 부모 없이 루트로 주장하는 두 번째 체인
    contradictory = [
        BundleLayer(
            blob_digest=chain[-1].blob_digest,
            size_bytes=chain[-1].size_bytes,
            name=chain[-1].name,
            config={"name": chain[-1].name, "kind": "squashfs"},
        )
    ]
    bundle_path = tmp_path / "contradictory.tar"
    bundle_path.write_bytes(b"".join(iter_bundle_tar(store, [chain, contradictory])))

    with pytest.raises(BundleError, match="모순"):
        parse_bundle(bundle_path)


def test_bundle_export_rejects_size_mismatch(store):
    chain = _chain(store)
    lying = [BundleLayer(**{**chain[0].__dict__, "size_bytes": 99999})]

    with pytest.raises(BundleError):
        b"".join(iter_bundle_tar(store, [lying]))


def test_build_manifest_rejects_empty_chain():
    with pytest.raises(BundleError):
        build_manifest([], {})


def test_parse_bundle_rejects_missing_index(tmp_path):
    bundle = tmp_path / "bad.tar"
    with tarfile.open(bundle, "w") as tar:
        payload = tmp_path / "x"
        payload.write_bytes(b"noise")
        tar.add(payload, arcname="blobs/sha256/" + "a" * 64)

    with pytest.raises(BundleError):
        parse_bundle(bundle)


def test_parse_bundle_rejects_unsafe_member_paths(tmp_path):
    bundle = tmp_path / "evil.tar"
    payload = tmp_path / "payload"
    payload.write_bytes(b"pwn")
    with tarfile.open(bundle, "w") as tar:
        tar.add(payload, arcname="../../etc/passwd")

    with pytest.raises(BundleError):
        parse_bundle(bundle)


def test_parse_bundle_rejects_manifest_referencing_absent_blob(store, tmp_path):
    chain = _chain(store)
    bundle_path = tmp_path / "bundle.tar"
    bundle_path.write_bytes(b"".join(iter_bundle_tar(store, [chain])))

    # leaf blob 멤버를 뺀 번들을 다시 만든다
    stripped = tmp_path / "stripped.tar"
    leaf_member = f"blobs/sha256/{chain[-1].blob_digest[len('sha256:') :]}"
    import io

    with tarfile.open(bundle_path, "r:") as src, tarfile.open(stripped, "w") as dst:
        for info in src.getmembers():
            if info.name == leaf_member:
                continue
            handle = src.extractfile(info)
            dst.addfile(info, io.BytesIO(handle.read() if handle else b""))

    with pytest.raises(BundleError):
        parse_bundle(stripped)


def test_media_type_is_project_specific_not_oci_generic():
    # 표준 도구가 squashfs 를 tar 레이어로 오해하지 않도록 고유 mediaType 을 쓴다
    assert MEDIA_TYPE_LAYER_SQUASHFS == "application/vnd.afterglow.palimpsest.layer.squashfs.v1"


# ---------------------------------------------------------------------------
# API 계약
# ---------------------------------------------------------------------------


class _EmptySession:
    """검색 결과가 비어 있는 최소 세션."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *_):
        return False

    async def execute(self, _stmt):
        return _EmptyResult()


class _EmptyResult:
    def scalars(self):
        return self

    def all(self):
        return []

    def scalar_one_or_none(self):
        return None


def _patch_factory(module: str):
    return patch(f"app.api.palimpsest.hub.{module}", return_value=lambda: _EmptySession())


async def test_hub_routes_are_mounted_under_v1_only():
    from app.main import app

    paths = {route.path for route in app.routes if "/palimpsest/hub" in route.path}

    assert paths == {
        "/api/v1/palimpsest/hub/layers",
        "/api/v1/palimpsest/hub/layers/{digest}",
        "/api/v1/palimpsest/hub/layers/{digest}/ancestors",
        "/api/v1/palimpsest/hub/layers/{digest}/blob",
        "/api/v1/palimpsest/hub/uploads",
        "/api/v1/palimpsest/hub/uploads/{session_id}",
        "/api/v1/palimpsest/hub/bundles",
        "/api/v1/palimpsest/hub/bundles/import",
    }


@pytest.mark.parametrize(
    ("param", "value"),
    [
        ("digest", "nope"),
        ("digest_prefix", "abc"),
        ("md5", "xyz"),
        ("chain_id", "sha256:zz"),
        ("parent_digest", "bad"),
        ("name", "Bad Name"),
        ("kind", "UPPER"),
    ],
)
async def test_hub_search_rejects_malformed_filters(client, param, value):
    resp = await client.get("/api/v1/palimpsest/hub/layers", params={param: value})

    assert resp.status_code == 422, resp.text


async def test_hub_search_returns_empty_without_leaking_other_projects(client):
    captured = {}

    class _Session(_EmptySession):
        async def execute(self, stmt):
            captured["sql"] = str(stmt)
            return _EmptyResult()

    with patch("app.api.palimpsest.hub.get_session_factory", return_value=lambda: _Session()):
        resp = await client.get("/api/v1/palimpsest/hub/layers")

    assert resp.status_code == 200
    assert resp.json() == []
    # 가시성 조건(공개 OR 사이트공용 OR 내 프로젝트)이 항상 붙어야 한다
    assert "is_published" in captured["sql"]
    assert "project_id" in captured["sql"]


async def test_hub_upload_is_unavailable_when_store_not_configured(client):
    # 허브를 설정하지 않은 배포에서는 503 — 500 이 아니다
    with (
        patch("app.api.palimpsest.hub.get_session_factory", return_value=lambda: _EmptySession()),
        patch(
            "app.api.palimpsest.hub.get_blob_store",
            side_effect=HubStoreUnavailable("[palimpsest] hub_local_path 가 설정되지 않았습니다"),
        ),
    ):
        resp = await client.post("/api/v1/palimpsest/hub/uploads", json={})

    # 본문은 확인하지 않는다 — 이 앱은 5xx 응답의 detail 을 마스킹한다(내부 경로 노출 금지).
    # 구체적 사유는 서버 로그에만 남는다.
    assert resp.status_code == 503


async def test_hub_upload_start_rejects_malformed_declared_digest(client):
    resp = await client.post("/api/v1/palimpsest/hub/uploads", json={"digest": "not-a-digest"})

    assert resp.status_code == 422


async def test_hub_layer_detail_hides_invisible_layer_as_404(client):
    with patch("app.api.palimpsest.hub.get_session_factory", return_value=lambda: _EmptySession()):
        resp = await client.get(f"/api/v1/palimpsest/hub/layers/sha256:{'a' * 64}")

    # 비공개/타 프로젝트 레이어의 존재를 확인해 주면 안 된다
    assert resp.status_code == 404


async def test_hub_delete_requires_admin(non_admin_client):
    resp = await non_admin_client.delete(f"/api/v1/palimpsest/hub/layers/sha256:{'a' * 64}")

    assert resp.status_code == 403


async def test_hub_bundle_export_requires_at_least_one_ref(client):
    resp = await client.post("/api/v1/palimpsest/hub/bundles", json={"refs": []})

    assert resp.status_code == 422


async def test_hub_bundle_export_rejects_malformed_ref(client):
    resp = await client.post("/api/v1/palimpsest/hub/bundles", json={"refs": ["nope"]})

    assert resp.status_code == 422
