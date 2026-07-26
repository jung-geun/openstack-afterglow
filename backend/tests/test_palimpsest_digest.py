"""Palimpsest 콘텐츠 주소화 회귀 테스트.

docs/palimpsest.md §3 의 digest 규칙을 고정한다:
- 레이어 정체성 = `.sqsh` blob 바이트의 sha256
- chain_id = OCI chainID 방식 (스택 전체의 정체성)
- digest 미확보는 pending 으로 남고 **빌드/소비를 막지 않는다**
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.models.db import LayerArtifact
from app.services.palimpsest_digest import (
    DIGEST_PENDING,
    DIGEST_READY,
    DIGEST_SENTINEL,
    DigestError,
    build_layer_config,
    compute_chain_id,
    compute_config_digest,
    is_digest_prefix,
    normalize_digest,
    normalize_md5,
    parse_digest_sentinel,
    parse_digest_sentinels,
    require_digest,
)
from app.services.palimpsest_layers import (
    load_ancestor_chain,
    load_lineage,
    recompute_descendant_chain_ids,
    resolve_digest_fields,
)
from app.services.recipe_blocks import (
    squashfs_nvidia_driver_layer,
    squashfs_python_layer,
    squashfs_stacked_layer,
    squashfs_system_apt_layer,
    squashfs_uv_layer,
)

_HEX_A = "a" * 64
_HEX_B = "b" * 64
_HEX_C = "c" * 64


# ---------------------------------------------------------------------------
# 정규화 / 검증
# ---------------------------------------------------------------------------


def test_normalize_digest_accepts_bare_and_prefixed_hex():
    assert normalize_digest(_HEX_A) == f"sha256:{_HEX_A}"
    assert normalize_digest(f"sha256:{_HEX_A}") == f"sha256:{_HEX_A}"
    assert normalize_digest(f"SHA256:{_HEX_A.upper()}") == f"sha256:{_HEX_A}"


@pytest.mark.parametrize("bad", [None, "", "sha256:", "zz" * 32, _HEX_A[:63], f"sha256:{_HEX_A}extra"])
def test_normalize_digest_rejects_malformed(bad):
    assert normalize_digest(bad) is None


def test_require_digest_raises_on_malformed():
    with pytest.raises(DigestError):
        require_digest("nope", field="blob_digest")


def test_normalize_md5_is_lowercased_and_length_checked():
    assert normalize_md5("A" * 32) == "a" * 32
    assert normalize_md5("a" * 31) is None
    assert normalize_md5(None) is None


def test_is_digest_prefix_requires_at_least_four_hex_chars():
    assert is_digest_prefix("abcd")
    assert is_digest_prefix(f"sha256:{_HEX_A[:10]}")
    assert not is_digest_prefix("abc")
    assert not is_digest_prefix("zzzz")


# ---------------------------------------------------------------------------
# sentinel 파싱
# ---------------------------------------------------------------------------


def _sentinel(layer: str, sha: str, md5: str = "d" * 32, size: str = "1024") -> str:
    return f"{DIGEST_SENTINEL}layer={layer} sha256={sha} md5={md5} size={size}\n"


def test_parse_digest_sentinels_maps_by_layer_name():
    console = "noise\n" + _sentinel("uvbase", _HEX_A) + "more noise\n" + _sentinel("python311", _HEX_B)

    reports = parse_digest_sentinels(console)

    assert set(reports) == {"uvbase", "python311"}
    assert reports["uvbase"].blob_digest == f"sha256:{_HEX_A}"
    assert reports["python311"].blob_digest == f"sha256:{_HEX_B}"
    assert reports["python311"].size_bytes == 1024


def test_parse_digest_sentinels_last_wins_for_repeated_layer():
    console = _sentinel("uvbase", _HEX_A) + _sentinel("uvbase", _HEX_B)

    assert parse_digest_sentinels(console)["uvbase"].blob_digest == f"sha256:{_HEX_B}"


def test_parse_digest_sentinels_skips_entries_without_valid_sha256():
    # 빌드 VM 에서 sha256sum 이 실패하면 빈 값이 방출된다 — 조용히 건너뛰고 pending 으로 남긴다.
    console = _sentinel("uvbase", "") + _sentinel("python311", _HEX_B)

    reports = parse_digest_sentinels(console)

    assert "uvbase" not in reports
    assert "python311" in reports


def test_parse_digest_sentinels_tolerates_missing_size():
    # macOS/BSD stat 처럼 `stat -c` 가 없는 환경에서는 size 가 비어 온다.
    console = _sentinel("uvbase", _HEX_A, size="")

    assert parse_digest_sentinels(console)["uvbase"].size_bytes is None


def test_parse_digest_sentinels_returns_empty_for_no_console():
    assert parse_digest_sentinels(None) == {}
    assert parse_digest_sentinels("") == {}
    assert parse_digest_sentinels("아무 sentinel 도 없는 콘솔") == {}


def test_parse_digest_sentinel_filters_by_layer_name():
    console = _sentinel("uvbase", _HEX_A) + _sentinel("python311", _HEX_B)

    assert parse_digest_sentinel(console, "uvbase").blob_digest == f"sha256:{_HEX_A}"
    assert parse_digest_sentinel(console, "없는레이어") is None
    # 이름을 주지 않으면 마지막 항목
    assert parse_digest_sentinel(console).blob_digest == f"sha256:{_HEX_B}"


# ---------------------------------------------------------------------------
# chain_id / config_digest
# ---------------------------------------------------------------------------


def test_chain_id_of_root_is_its_own_blob_digest():
    assert compute_chain_id(None, _HEX_A) == f"sha256:{_HEX_A}"


def test_chain_id_is_deterministic_and_parent_sensitive():
    root_a = compute_chain_id(None, _HEX_A)
    root_b = compute_chain_id(None, _HEX_B)

    assert compute_chain_id(root_a, _HEX_C) == compute_chain_id(root_a, _HEX_C)
    # 같은 레이어라도 부모 스택이 다르면 chain_id 가 달라야 한다 — 스택 정체성이기 때문.
    assert compute_chain_id(root_a, _HEX_C) != compute_chain_id(root_b, _HEX_C)
    # 순서가 뒤바뀌면 다른 스택이다.
    assert compute_chain_id(root_a, _HEX_B) != compute_chain_id(root_b, _HEX_A)


def test_config_digest_is_key_order_independent_but_value_sensitive():
    base = build_layer_config(
        name="torch",
        kind="pip",
        ubuntu_base="ubuntu-24.04",
        python_version="3.11",
        pip_packages=["torch", "numpy"],
        apt_packages=None,
        parent_digest=_HEX_A,
    )
    reordered = dict(reversed(list(base.items())))
    assert compute_config_digest(base) == compute_config_digest(reordered)

    # pip 패키지는 정렬되어 들어가므로 나열 순서는 정체성에 영향이 없다
    swapped = build_layer_config(
        name="torch",
        kind="pip",
        ubuntu_base="ubuntu-24.04",
        python_version="3.11",
        pip_packages=["numpy", "torch"],
        apt_packages=None,
        parent_digest=_HEX_A,
    )
    assert compute_config_digest(swapped) == compute_config_digest(base)

    changed = dict(base, python_version="3.12")
    assert compute_config_digest(changed) != compute_config_digest(base)


# ---------------------------------------------------------------------------
# resolve_digest_fields (세션 필요)
# ---------------------------------------------------------------------------


class _FakeSession:
    """`session.get` 과 `session.execute(select(...))` 만 지원하는 최소 세션."""

    def __init__(self, rows: dict[int, LayerArtifact] | None = None):
        self.rows = rows or {}

    async def get(self, _model, pk):
        return self.rows.get(pk)

    async def execute(self, statement):
        params = statement.compile().params
        parent_id = next((v for k, v in params.items() if k.startswith("parent_id")), None)
        children = [row for row in self.rows.values() if row.parent_id == parent_id]
        return _FakeResult(children)


class _FakeResult:
    def __init__(self, rows):
        self._rows = rows

    def scalars(self):
        return self

    def all(self):
        return list(self._rows)


def _artifact(**kwargs) -> LayerArtifact:
    defaults = dict(
        name="layer",
        kind="uv",
        sqsh_filename="layer-latest.sqsh",
        share_id="share-1",
        parent_id=None,
        blob_digest=None,
        chain_id=None,
        digest_state=DIGEST_PENDING,
    )
    defaults.update(kwargs)
    return LayerArtifact(**defaults)


def _fields_kwargs(**overrides):
    base = dict(
        name="uvbase",
        kind="uv",
        ubuntu_base="ubuntu-24.04",
        python_version=None,
        pip_packages=[],
        apt_packages=[],
    )
    base.update(overrides)
    return base


@pytest.mark.asyncio
async def test_resolve_digest_fields_without_report_stays_pending():
    fields = await resolve_digest_fields(_FakeSession(), report=None, parent_artifact_id=None, **_fields_kwargs())

    assert fields["digest_state"] == DIGEST_PENDING
    assert fields["blob_digest"] is None
    assert fields["chain_id"] is None
    # config_digest 는 빌드 의도만으로 계산되므로 digest 가 없어도 채워진다
    assert fields["config_digest"].startswith("sha256:")


@pytest.mark.asyncio
async def test_resolve_digest_fields_for_root_sets_chain_id_to_digest():
    report = parse_digest_sentinels(_sentinel("uvbase", _HEX_A))["uvbase"]

    fields = await resolve_digest_fields(_FakeSession(), report=report, parent_artifact_id=None, **_fields_kwargs())

    assert fields["digest_state"] == DIGEST_READY
    assert fields["blob_digest"] == f"sha256:{_HEX_A}"
    assert fields["chain_id"] == f"sha256:{_HEX_A}"
    assert fields["blob_md5"] == "d" * 32


@pytest.mark.asyncio
async def test_resolve_digest_fields_for_child_chains_from_parent():
    parent = _artifact(blob_digest=f"sha256:{_HEX_A}", chain_id=f"sha256:{_HEX_A}", digest_state=DIGEST_READY)
    parent.id = 1
    report = parse_digest_sentinels(_sentinel("python311", _HEX_B))["python311"]

    fields = await resolve_digest_fields(
        _FakeSession({1: parent}),
        report=report,
        parent_artifact_id=1,
        **_fields_kwargs(name="python311", kind="python", python_version="3.11"),
    )

    assert fields["chain_id"] == compute_chain_id(f"sha256:{_HEX_A}", _HEX_B)


@pytest.mark.asyncio
async def test_resolve_digest_fields_leaves_chain_id_null_when_parent_pending():
    # 부모가 아직 백필되지 않았으면 자식 chain_id 를 임의로 만들지 않는다 —
    # 루트 취급하면 서로 다른 스택이 같은 chain_id 를 갖게 된다.
    parent = _artifact(digest_state=DIGEST_PENDING)
    parent.id = 1
    report = parse_digest_sentinels(_sentinel("python311", _HEX_B))["python311"]

    fields = await resolve_digest_fields(
        _FakeSession({1: parent}),
        report=report,
        parent_artifact_id=1,
        **_fields_kwargs(name="python311", kind="python"),
    )

    assert fields["digest_state"] == DIGEST_READY
    assert fields["blob_digest"] == f"sha256:{_HEX_B}"
    assert fields["chain_id"] is None


@pytest.mark.asyncio
async def test_recompute_descendant_chain_ids_fills_children_after_backfill():
    root = _artifact(blob_digest=f"sha256:{_HEX_A}", chain_id=f"sha256:{_HEX_A}", digest_state=DIGEST_READY)
    root.id = 1
    child = _artifact(name="python311", parent_id=1, blob_digest=f"sha256:{_HEX_B}", digest_state=DIGEST_READY)
    child.id = 2
    grandchild = _artifact(name="torch", parent_id=2, blob_digest=f"sha256:{_HEX_C}", digest_state=DIGEST_READY)
    grandchild.id = 3
    session = _FakeSession({1: root, 2: child, 3: grandchild})

    updated = await recompute_descendant_chain_ids(session, 1)

    expected_child = compute_chain_id(root.chain_id, _HEX_B)
    assert updated == 2
    assert child.chain_id == expected_child
    assert grandchild.chain_id == compute_chain_id(expected_child, _HEX_C)


@pytest.mark.asyncio
async def test_recompute_descendant_chain_ids_stops_at_digestless_node():
    root = _artifact(blob_digest=f"sha256:{_HEX_A}", chain_id=f"sha256:{_HEX_A}", digest_state=DIGEST_READY)
    root.id = 1
    child = _artifact(name="python311", parent_id=1, blob_digest=None, digest_state=DIGEST_PENDING)
    child.id = 2
    grandchild = _artifact(name="torch", parent_id=2, blob_digest=f"sha256:{_HEX_C}", digest_state=DIGEST_READY)
    grandchild.id = 3
    session = _FakeSession({1: root, 2: child, 3: grandchild})

    updated = await recompute_descendant_chain_ids(session, 1)

    assert updated == 0
    assert child.chain_id is None
    assert grandchild.chain_id is None


@pytest.mark.asyncio
async def test_lineage_helpers_agree_on_opposite_orders():
    root = _artifact(name="uvbase")
    root.id = 1
    child = _artifact(name="python311", parent_id=1)
    child.id = 2
    leaf = _artifact(name="torch", parent_id=2)
    leaf.id = 3
    session = _FakeSession({1: root, 2: child, 3: leaf})

    lineage = await load_lineage(session, leaf)
    ancestors = await load_ancestor_chain(session, leaf)

    assert [row.name for row in lineage] == ["torch", "python311", "uvbase"]
    assert [row.name for row in ancestors] == ["uvbase", "python311", "torch"]


@pytest.mark.asyncio
async def test_load_lineage_survives_parent_cycle():
    a = _artifact(name="a", parent_id=2)
    a.id = 1
    b = _artifact(name="b", parent_id=1)
    b.id = 2

    lineage = await load_lineage(_FakeSession({1: a, 2: b}), a)

    assert [row.name for row in lineage] == ["a", "b"]


# ---------------------------------------------------------------------------
# 빌드 스크립트가 sentinel 을 방출하는가
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("factory", "layer_name"),
    [
        (lambda: squashfs_uv_layer("uvbase"), "uvbase"),
        (lambda: squashfs_python_layer("python311", "3.11"), "python311"),
        (lambda: squashfs_system_apt_layer("systools", ["curl"]), "systools"),
        (lambda: squashfs_nvidia_driver_layer("nvidia580", "580"), "nvidia580"),
        (
            lambda: squashfs_stacked_layer(
                "torch",
                python_version="3.11",
                pip_packages=["torch"],
                parent_exports=[("10.0.0.1:/layers/py", "python311-latest.sqsh")],
            ),
            "torch",
        ),
    ],
)
def test_every_squashfs_recipe_emits_digest_sentinel_after_mksquashfs(factory, layer_name):
    script = factory()

    assert f"{DIGEST_SENTINEL}layer={layer_name} sha256=${{PALIMPSEST_SHA256:-}}" in script
    # digest 계산은 mksquashfs 뒤에 와야 한다 — 파일이 존재해야 해시를 뜬다
    assert script.index("mksquashfs") < script.index("PALIMPSEST_SHA256")


def test_digest_computation_never_fails_the_build():
    # run-build.sh 는 `set -euo pipefail` 이다. digest 계산이 실패해도 빌드를 죽이면 안 된다 —
    # digest 는 백필할 수 있지만 빌드 산출물은 되살릴 수 없다.
    script = squashfs_uv_layer("uvbase")

    for line in script.splitlines():
        if line.startswith("PALIMPSEST_"):
            assert line.endswith("|| true"), line


@pytest.mark.asyncio
async def test_layer_artifact_model_exposes_digest_columns():
    # 마이그레이션 057 과 ORM 이 어긋나면 artifacts 엔드포인트가 500 이 된다(waygate 전례).
    columns = {column.name for column in LayerArtifact.__table__.columns}

    assert {"blob_digest", "blob_md5", "config_digest", "chain_id", "digest_state"} <= columns
    assert LayerArtifact.__table__.columns["digest_state"].nullable is False


def test_digest_indexes_exist_for_search_paths():
    index_columns = {tuple(col.name for col in idx.columns) for idx in LayerArtifact.__table__.indexes}

    assert ("blob_digest",) in index_columns
    assert ("chain_id",) in index_columns


def test_select_by_digest_compiles():
    # digest 검색 쿼리가 ORM 상에서 성립하는지(컬럼 오타 방어)
    stmt = select(LayerArtifact).where(LayerArtifact.blob_digest == f"sha256:{_HEX_A}")

    assert "blob_digest" in str(stmt)
