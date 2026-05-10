"""Union Mount 레이어 시스템 Pydantic 모델."""

from datetime import datetime

from pydantic import BaseModel, Field, field_validator, model_validator

_SHA256_PREFIX = "sha256:"
_HEX_LEN = 64


def _validate_sha256_id(v: str) -> str:
    if not v.startswith(_SHA256_PREFIX):
        raise ValueError(f"id는 'sha256:'으로 시작해야 합니다 (받은 값: {v!r})")
    hex_part = v[len(_SHA256_PREFIX) :]
    if len(hex_part) != _HEX_LEN or not all(c in "0123456789abcdef" for c in hex_part):
        raise ValueError(f"sha256 해시는 정확히 {_HEX_LEN}자의 소문자 16진수여야 합니다")
    return v


class CreateLayerRequest(BaseModel):
    """새 레이어 등록 요청."""

    name: str = Field(min_length=1, max_length=128)
    version: str = Field(min_length=1, max_length=64)
    parent_id: str | None = None  # None = 최상위 레이어 (단일 상속)
    parent_ids: list[str] | None = None  # 다중 상속 (실험, opt-in). 2개 이상.
    ubuntu_base: str | None = Field(default=None, max_length=255)
    build_recipe: dict = Field(default_factory=dict)
    installed_packages: dict = Field(default_factory=dict)
    content_hash: str  # sha256:<64hex>
    size_bytes: int | None = None
    file_count: int | None = None
    project_id: str | None = None  # 명시적 지정 시 사용, 미지정 시 토큰에서 자동 추출
    license_type: str | None = None
    max_concurrent_mounts: int | None = None

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, v: str) -> str:
        return _validate_sha256_id(v)

    @field_validator("parent_id")
    @classmethod
    def validate_parent_id(cls, v: str | None) -> str | None:
        if v is not None:
            return _validate_sha256_id(v)
        return v

    @field_validator("parent_ids")
    @classmethod
    def validate_parent_ids(cls, v: list[str] | None) -> list[str] | None:
        if v is None:
            return v
        if len(v) < 2:
            raise ValueError("parent_ids는 2개 이상이어야 합니다 (단일 부모는 parent_id를 사용하세요)")
        if len(set(v)) != len(v):
            raise ValueError("parent_ids에 중복된 항목이 있습니다")
        for pid in v:
            _validate_sha256_id(pid)
        return v

    @model_validator(mode="after")
    def validate_parent_exclusivity(self) -> "CreateLayerRequest":
        if self.parent_id is not None and self.parent_ids is not None:
            raise ValueError("parent_id와 parent_ids는 동시에 지정할 수 없습니다 (mutually exclusive)")
        return self


class LayerInfo(BaseModel):
    """레이어 상세 정보."""

    id: str
    name: str
    version: str
    created_at: datetime
    created_by: str
    sealed: bool
    sealed_at: datetime | None = None
    parent_id: str | None = None  # 단일 상속 시 사용 (multi 모드에서는 NULL)
    parent_ids: list[str] | None = None  # 다중 상속 시 사용 (single 모드에서는 NULL)
    project_id: str | None = None
    ubuntu_base: str | None = None
    build_recipe: dict = {}
    installed_packages: dict = {}
    content_hash: str
    size_bytes: int | None = None
    file_count: int | None = None
    license_type: str | None = None
    max_concurrent_mounts: int | None = None


class SealLayerResponse(BaseModel):
    """레이어 봉인 응답."""

    id: str
    sealed: bool
    sealed_at: datetime | None = None


class AncestorChain(BaseModel):
    """조상 체인 (base-first 순서)."""

    layers: list[LayerInfo]


class ForkLayerRequest(BaseModel):
    """레이어 fork 요청 — sealed 레이어에서 새 RW 레이어 파생."""

    content_hash: str  # sha256:<64hex> — 새 레이어의 고유 식별자
    version: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=128)  # 미지정 시 원본 name 상속

    @field_validator("content_hash")
    @classmethod
    def validate_content_hash(cls, v: str) -> str:
        return _validate_sha256_id(v)


class SnapshotLayerRequest(BaseModel):
    """레이어 Manila 스냅샷 생성 요청."""

    share_id: str = Field(min_length=1, description="레이어를 백업할 Manila share ID")
    name: str | None = Field(default=None, max_length=255)
    description: str | None = Field(default=None, max_length=255)


class RestoreLayerRequest(BaseModel):
    """레이어 Manila 스냅샷 복원 요청."""

    share_id: str = Field(min_length=1, description="복원 대상 Manila share ID")
    snapshot_id: str = Field(min_length=1, description="복원에 사용할 스냅샷 ID")


class CreateTemplateRequest(BaseModel):
    """새 템플릿 생성 요청."""

    name: str = Field(min_length=1, max_length=128)
    version: int = Field(ge=1)
    ubuntu_base: str = Field(min_length=1, max_length=255)
    leaf_layer_id: str  # sha256:<64hex>
    parent_version: int | None = None
    note: str | None = None

    @field_validator("leaf_layer_id")
    @classmethod
    def validate_leaf_layer_id(cls, v: str) -> str:
        return _validate_sha256_id(v)


class TemplateInfo(BaseModel):
    """템플릿 상세 정보."""

    name: str
    version: int
    created_at: datetime
    created_by: str
    parent_version: int | None = None
    ubuntu_base: str
    leaf_layer_id: str
    note: str | None = None
    resolved_stack: list[LayerInfo] | None = None  # GET 시 조상 체인 포함


# ---------------------------------------------------------------------------
# 마운트 추적
# ---------------------------------------------------------------------------


class RecordMountRequest(BaseModel):
    """마운트 기록 요청."""

    vm_hostname: str = Field(min_length=1, max_length=255)
    leaf_layer_id: str  # sha256:<64hex>

    @field_validator("leaf_layer_id")
    @classmethod
    def validate_leaf_layer_id(cls, v: str) -> str:
        return _validate_sha256_id(v)


class MountInfo(BaseModel):
    """마운트 기록 정보."""

    id: int
    user_id: str
    vm_hostname: str
    leaf_layer_id: str
    mounted_at: datetime
    unmounted_at: datetime | None = None


# ---------------------------------------------------------------------------
# 스토리지 통계
# ---------------------------------------------------------------------------


class StorageStats(BaseModel):
    """레이어 스토리지 사용량 집계."""

    total_layers: int
    sealed_layers: int
    total_size_bytes: int
    total_file_count: int


# ---------------------------------------------------------------------------
# Builder CephX 접근 관리
# ---------------------------------------------------------------------------


class BuilderAccessRequest(BaseModel):
    """빌더 VM CephX 접근 요청."""

    cephx_user: str = Field(min_length=1, max_length=128)
    access_level: str = Field(default="rw", pattern="^(rw|ro)$")

    @model_validator(mode="after")
    def validate_user_not_empty(self) -> "BuilderAccessRequest":
        if not self.cephx_user.strip():
            raise ValueError("cephx_user는 비어 있을 수 없습니다")
        return self


class BuilderAccessInfo(BaseModel):
    """빌더 VM CephX 접근 정보."""

    access_id: str
    cephx_user: str
    access_level: str
    share_id: str
