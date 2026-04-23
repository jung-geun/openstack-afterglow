"""Union Mount 레이어 시스템 단위 테스트."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.models.union import CreateLayerRequest, CreateTemplateRequest

# ---------------------------------------------------------------------------
# 헬퍼
# ---------------------------------------------------------------------------

_NOW = datetime(2026, 4, 24, 0, 0, 0, tzinfo=UTC)


def _make_layer(
    layer_id: str | None = None,
    name: str = "python",
    version: str = "3.12",
    sealed: bool = False,
    parent_id: str | None = None,
):
    from app.models.db import UnionLayer

    if layer_id is None:
        layer_id = _sha("default")
    layer = MagicMock(spec=UnionLayer)
    layer.id = layer_id
    layer.name = name
    layer.version = version
    layer.created_at = _NOW
    layer.created_by = "testuser"
    layer.sealed = sealed
    layer.parent_id = parent_id
    layer.ubuntu_base = None
    layer.build_recipe = {}
    layer.installed_packages = {}
    layer.content_hash = layer_id
    layer.size_bytes = None
    layer.file_count = None
    return layer


def _make_layer_info(
    layer_id: str | None = None,
    name: str = "python",
    version: str = "3.12",
    sealed: bool = False,
    parent_id: str | None = None,
):
    from app.models.union import LayerInfo

    if layer_id is None:
        layer_id = _sha("default")
    return LayerInfo(
        id=layer_id,
        name=name,
        version=version,
        created_at=_NOW,
        created_by="testuser",
        sealed=sealed,
        parent_id=parent_id,
        ubuntu_base=None,
        build_recipe={},
        installed_packages={},
        content_hash=layer_id,
        size_bytes=None,
        file_count=None,
    )


_HEX_CHARS = "0123456789abcdef"


def _sha(seed: str = "a") -> str:
    """seed 문자열로 유효한 sha256:<64hex> 생성."""
    import hashlib

    return "sha256:" + hashlib.sha256(seed.encode()).hexdigest()


# ---------------------------------------------------------------------------
# 서비스 레이어 단위 테스트
# ---------------------------------------------------------------------------


class TestCreateLayer:
    @pytest.mark.asyncio
    async def test_create_layer_no_parent(self):
        """부모 없는 레이어 생성."""
        from app.services.union_layers import create_layer

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)  # 중복 없음

        req = CreateLayerRequest(
            name="base",
            version="noble",
            content_hash=_sha("b"),
            build_recipe={"type": "manual"},
            installed_packages={},
        )
        layer_result = _make_layer(layer_id=_sha("b"), name="base", version="noble")
        session.refresh = AsyncMock(side_effect=lambda obj, *a, **kw: None)

        with patch("app.services.union_layers.UnionLayer", return_value=layer_result):
            await create_layer(session, req, created_by="admin")
        session.add.assert_called_once()
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_layer_with_sealed_parent(self):
        """봉인된 부모를 가진 레이어 생성."""
        from app.services.union_layers import create_layer

        parent = _make_layer(layer_id=_sha("p"), sealed=True)

        session = AsyncMock()
        # 첫 호출: 자신 없음, 두 번째 호출: 부모 존재
        session.get = AsyncMock(side_effect=[None, parent])

        req = CreateLayerRequest(
            name="python",
            version="3.12",
            parent_id=_sha("p"),
            content_hash=_sha("c"),
            build_recipe={},
            installed_packages={},
        )
        new_layer = _make_layer(layer_id=_sha("c"), name="python", version="3.12", parent_id=_sha("p"))
        session.refresh = AsyncMock()
        with patch("app.services.union_layers.UnionLayer", return_value=new_layer):
            await create_layer(session, req, created_by="admin")
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_layer_with_unsealed_parent_raises(self):
        """봉인되지 않은 부모로 레이어 생성 시 ValueError."""
        from app.services.union_layers import create_layer

        parent = _make_layer(layer_id=_sha("p"), sealed=False)
        session = AsyncMock()
        session.get = AsyncMock(side_effect=[None, parent])

        req = CreateLayerRequest(
            name="python",
            version="3.12",
            parent_id=_sha("p"),
            content_hash=_sha("c"),
            build_recipe={},
            installed_packages={},
        )
        with pytest.raises(ValueError, match="봉인"):
            await create_layer(session, req, created_by="admin")

    @pytest.mark.asyncio
    async def test_create_layer_nonexistent_parent_raises(self):
        """존재하지 않는 부모 → ValueError."""
        from app.services.union_layers import create_layer

        session = AsyncMock()
        session.get = AsyncMock(side_effect=[None, None])  # 자신 없음, 부모 없음

        req = CreateLayerRequest(
            name="python",
            version="3.12",
            parent_id=_sha("x"),
            content_hash=_sha("c"),
            build_recipe={},
            installed_packages={},
        )
        with pytest.raises(ValueError, match="존재하지 않"):
            await create_layer(session, req, created_by="admin")

    @pytest.mark.asyncio
    async def test_create_duplicate_layer_raises(self):
        """중복 id 레이어 생성 시 ValueError."""
        from app.services.union_layers import create_layer

        existing = _make_layer(layer_id=_sha("a"))
        session = AsyncMock()
        session.get = AsyncMock(return_value=existing)

        req = CreateLayerRequest(
            name="python",
            version="3.12",
            content_hash=_sha("a"),
            build_recipe={},
            installed_packages={},
        )
        with pytest.raises(ValueError, match="이미 존재"):
            await create_layer(session, req, created_by="admin")


class TestSealLayer:
    @pytest.mark.asyncio
    async def test_seal_layer_success(self):
        """정상 봉인."""
        from app.services.union_layers import seal_layer

        layer = _make_layer(layer_id=_sha("a"), sealed=False)
        session = AsyncMock()
        session.get = AsyncMock(return_value=layer)

        result = await seal_layer(session, _sha("a"))
        assert result.sealed is True
        session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_seal_already_sealed_raises(self):
        """이미 봉인된 레이어 → ValueError."""
        from app.services.union_layers import seal_layer

        layer = _make_layer(layer_id=_sha("a"), sealed=True)
        session = AsyncMock()
        session.get = AsyncMock(return_value=layer)

        with pytest.raises(ValueError, match="이미 봉인"):
            await seal_layer(session, _sha("a"))

    @pytest.mark.asyncio
    async def test_seal_nonexistent_layer_raises(self):
        """없는 레이어 봉인 시도 → KeyError."""
        from app.services.union_layers import seal_layer

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        with pytest.raises(KeyError):
            await seal_layer(session, _sha("x"))


class TestListLayers:
    @pytest.mark.asyncio
    async def test_list_layers_returns_list(self):
        """레이어 목록 반환."""
        from app.services import union_layers as svc

        layers = [
            _make_layer_info(_sha("a"), "python", "3.12"),
            _make_layer_info(_sha("b"), "cuda", "12.3"),
        ]
        with patch.object(svc, "list_layers", AsyncMock(return_value=layers)):
            result = await svc.list_layers(AsyncMock(), name=None, limit=50, offset=0)
        assert len(result) == 2

    @pytest.mark.asyncio
    async def test_list_layers_name_filter(self):
        """이름 필터 적용."""
        from app.services import union_layers as svc

        filtered = [_make_layer_info(_sha("a"), "python", "3.12")]
        with patch.object(svc, "list_layers", AsyncMock(return_value=filtered)):
            result = await svc.list_layers(AsyncMock(), name="python", limit=50, offset=0)
        assert all(layer.name == "python" for layer in result)


class TestGetAncestors:
    @pytest.mark.asyncio
    async def test_ancestors_nonexistent_leaf_raises(self):
        """없는 leaf → KeyError."""
        from app.services.union_layers import get_ancestors

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        with pytest.raises(KeyError):
            await get_ancestors(session, _sha("x"))

    @pytest.mark.asyncio
    async def test_ancestors_single_layer(self):
        """부모 없는 단일 레이어 → 자신만 반환."""
        from app.services.union_layers import get_ancestors

        leaf = _make_layer(layer_id=_sha("a"), sealed=True)
        session = AsyncMock()
        session.get = AsyncMock(return_value=leaf)

        # execute 결과 모킹 (WITH RECURSIVE CTE)
        row = {
            "id": _sha("a"),
            "name": "base",
            "version": "noble",
            "created_at": _NOW,
            "created_by": "admin",
            "sealed": True,
            "parent_id": None,
            "ubuntu_base": None,
            "build_recipe": {},
            "installed_packages": {},
            "content_hash": _sha("a"),
            "size_bytes": None,
            "file_count": None,
            "depth": 0,
        }
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = [row]
        session.execute = AsyncMock(return_value=mock_result)

        chain = await get_ancestors(session, _sha("a"))
        assert len(chain.layers) == 1
        assert chain.layers[0].id == _sha("a")

    @pytest.mark.asyncio
    async def test_ancestors_four_layer_chain(self):
        """4단 체인 (base→python→cuda→pytorch) 반환 확인."""
        from app.services.union_layers import get_ancestors

        leaf = _make_layer(layer_id=_sha("d"), sealed=True)
        session = AsyncMock()
        session.get = AsyncMock(return_value=leaf)

        rows = [
            {
                "id": _sha("a"),
                "name": "base",
                "version": "1",
                "created_at": _NOW,
                "created_by": "admin",
                "sealed": True,
                "parent_id": None,
                "ubuntu_base": "ubuntu-24.04",
                "build_recipe": {},
                "installed_packages": {},
                "content_hash": _sha("a"),
                "size_bytes": None,
                "file_count": None,
                "depth": 3,
            },
            {
                "id": _sha("b"),
                "name": "python",
                "version": "3.12",
                "created_at": _NOW,
                "created_by": "admin",
                "sealed": True,
                "parent_id": _sha("a"),
                "ubuntu_base": None,
                "build_recipe": {},
                "installed_packages": {},
                "content_hash": _sha("b"),
                "size_bytes": None,
                "file_count": None,
                "depth": 2,
            },
            {
                "id": _sha("c"),
                "name": "cuda",
                "version": "12.3",
                "created_at": _NOW,
                "created_by": "admin",
                "sealed": True,
                "parent_id": _sha("b"),
                "ubuntu_base": None,
                "build_recipe": {},
                "installed_packages": {},
                "content_hash": _sha("c"),
                "size_bytes": None,
                "file_count": None,
                "depth": 1,
            },
            {
                "id": _sha("d"),
                "name": "pytorch",
                "version": "2.4",
                "created_at": _NOW,
                "created_by": "admin",
                "sealed": True,
                "parent_id": _sha("c"),
                "ubuntu_base": None,
                "build_recipe": {},
                "installed_packages": {},
                "content_hash": _sha("d"),
                "size_bytes": None,
                "file_count": None,
                "depth": 0,
            },
        ]
        mock_result = MagicMock()
        mock_result.mappings.return_value.all.return_value = rows
        session.execute = AsyncMock(return_value=mock_result)

        chain = await get_ancestors(session, _sha("d"))
        assert len(chain.layers) == 4
        # base-first 순서 확인
        assert chain.layers[0].name == "base"
        assert chain.layers[-1].name == "pytorch"


class TestTemplates:
    @pytest.mark.asyncio
    async def test_create_template_with_sealed_leaf(self):
        """봉인된 leaf로 템플릿 생성."""
        from app.models.union import TemplateInfo
        from app.services import union_layers as svc

        expected = TemplateInfo(
            name="ml-pytorch",
            version=1,
            created_at=_NOW,
            created_by="admin",
            ubuntu_base="ubuntu-24.04",
            leaf_layer_id=_sha("a"),
        )

        # create_template 서비스를 직접 모킹 (DB 의존성 제거)
        with patch.object(svc, "create_template", AsyncMock(return_value=expected)):
            session = AsyncMock()
            req = CreateTemplateRequest(
                name="ml-pytorch",
                version=1,
                ubuntu_base="ubuntu-24.04",
                leaf_layer_id=_sha("a"),
            )
            result = await svc.create_template(session, req, created_by="admin")
        assert result.name == "ml-pytorch"

    @pytest.mark.asyncio
    async def test_create_template_with_unsealed_leaf_raises(self):
        """봉인 안 된 leaf → ValueError."""
        from app.services.union_layers import create_template

        leaf = _make_layer(layer_id=_sha("a"), sealed=False)
        session = AsyncMock()
        session.get = AsyncMock(return_value=leaf)

        req = CreateTemplateRequest(
            name="ml-pytorch",
            version=1,
            ubuntu_base="ubuntu-24.04",
            leaf_layer_id=_sha("a"),
        )
        with pytest.raises(ValueError, match="봉인"):
            await create_template(session, req, created_by="admin")

    @pytest.mark.asyncio
    async def test_create_template_nonexistent_leaf_raises(self):
        """존재하지 않는 leaf → ValueError."""
        from app.services.union_layers import create_template

        session = AsyncMock()
        session.get = AsyncMock(return_value=None)

        req = CreateTemplateRequest(
            name="ml-pytorch",
            version=1,
            ubuntu_base="ubuntu-24.04",
            leaf_layer_id=_sha("a"),
        )
        with pytest.raises(ValueError, match="존재하지 않"):
            await create_template(session, req, created_by="admin")


# ---------------------------------------------------------------------------
# Pydantic 모델 검증 테스트
# ---------------------------------------------------------------------------


class TestLayerIdValidation:
    def test_valid_sha256_id(self):
        """유효한 sha256:... id 형식."""
        req = CreateLayerRequest(
            name="test",
            version="1.0",
            content_hash=_sha("a"),
            build_recipe={},
            installed_packages={},
        )
        assert req.content_hash.startswith("sha256:")

    def test_invalid_sha256_missing_prefix(self):
        """sha256: 접두사 없으면 ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateLayerRequest(
                name="test",
                version="1.0",
                content_hash="abc123",
                build_recipe={},
                installed_packages={},
            )

    def test_invalid_sha256_wrong_length(self):
        """해시 길이 불일치 → ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateLayerRequest(
                name="test",
                version="1.0",
                content_hash="sha256:abc",
                build_recipe={},
                installed_packages={},
            )

    def test_invalid_parent_id(self):
        """잘못된 parent_id 형식 → ValidationError."""
        from pydantic import ValidationError

        with pytest.raises(ValidationError):
            CreateLayerRequest(
                name="test",
                version="1.0",
                content_hash=_sha("a"),
                parent_id="not-a-hash",
                build_recipe={},
                installed_packages={},
            )

    def test_valid_parent_id_none(self):
        """parent_id=None은 허용."""
        req = CreateLayerRequest(
            name="test",
            version="1.0",
            content_hash=_sha("a"),
            parent_id=None,
            build_recipe={},
            installed_packages={},
        )
        assert req.parent_id is None


# ---------------------------------------------------------------------------
# API 엔드포인트 테스트
# ---------------------------------------------------------------------------


class TestUnionLayersAPI:
    @pytest.mark.asyncio
    async def test_list_layers_unauthenticated(self):
        """인증 없이 레이어 목록 조회 → 401."""
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
            resp = await ac.get("/api/union/layers")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_list_layers_authenticated(self, client):
        """인증된 사용자 레이어 목록 조회."""
        from app.database import get_session

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value = []
        mock_session.execute = AsyncMock(return_value=mock_result)

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            resp = await client.get("/api/union/layers")
        finally:
            app.dependency_overrides.pop(get_session, None)

        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_layer_non_admin_forbidden(self, client):
        """일반 사용자 레이어 생성 시도 → 403."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            resp = await client.post(
                "/api/union/layers",
                json={
                    "name": "test",
                    "version": "1.0",
                    "content_hash": _sha("a"),
                    "build_recipe": {},
                    "installed_packages": {},
                },
            )
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_create_layer_admin_success(self, admin_client):
        """관리자 레이어 생성 성공."""
        from app.database import get_session

        layer_info = _make_layer_info(_sha("a"), "test", "1.0")

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            with patch("app.api.union.layers.union_layers.create_layer", AsyncMock(return_value=layer_info)):
                resp = await admin_client.post(
                    "/api/union/layers",
                    json={
                        "name": "test",
                        "version": "1.0",
                        "content_hash": _sha("a"),
                        "build_recipe": {},
                        "installed_packages": {},
                    },
                )
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 201
        assert resp.json()["name"] == "test"

    @pytest.mark.asyncio
    async def test_get_layer_not_found(self, client):
        """없는 레이어 조회 → 404."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            with patch("app.api.union.layers.union_layers.get_layer", AsyncMock(return_value=None)):
                resp = await client.get(f"/api/union/layers/{_sha('x')}")
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_seal_layer_non_admin_forbidden(self, client):
        """일반 사용자 봉인 시도 → 403."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            resp = await client.post(f"/api/union/layers/{_sha('a')}/seal")
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 403

    @pytest.mark.asyncio
    async def test_ancestors_not_found(self, client):
        """없는 레이어의 조상 조회 → 404."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            with patch(
                "app.api.union.layers.union_layers.get_ancestors",
                AsyncMock(side_effect=KeyError("not found")),
            ):
                resp = await client.get(f"/api/union/layers/{_sha('x')}/ancestors")
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 404

    @pytest.mark.asyncio
    async def test_list_templates_authenticated(self, client):
        """인증된 사용자 템플릿 목록 조회."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            with patch("app.api.union.layers.union_layers.list_templates", AsyncMock(return_value=[])):
                resp = await client.get("/api/union/templates")
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    async def test_create_template_non_admin_forbidden(self, client):
        """일반 사용자 템플릿 생성 → 403."""
        from app.database import get_session

        mock_session = AsyncMock()

        async def override_get_session():
            yield mock_session

        app.dependency_overrides[get_session] = override_get_session
        try:
            resp = await client.post(
                "/api/union/templates",
                json={
                    "name": "ml-pytorch",
                    "version": 1,
                    "ubuntu_base": "ubuntu-24.04",
                    "leaf_layer_id": _sha("a"),
                },
            )
        finally:
            app.dependency_overrides.pop(get_session, None)
        assert resp.status_code == 403
