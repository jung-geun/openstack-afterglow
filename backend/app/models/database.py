from pydantic import BaseModel, Field


class DbUserSpec(BaseModel):
    """DB 인스턴스 초기 유저 스펙."""

    name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)
    host: str = "%"
    databases: list[str] = []


class CreateDbInstanceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    flavor_id: str = Field(..., min_length=1)
    volume_size: int = Field(..., ge=1, le=1024)
    datastore_type: str = Field(..., min_length=1)
    datastore_version: str = Field(..., min_length=1)
    # 기존 선택 필드
    databases: list[str] = []
    restore_backup_id: str | None = None
    # Horizon 5탭 확장 필드
    availability_zone: str | None = None
    volume_type: str | None = None
    nics: list[str] = []  # network UUID 목록
    locality: str | None = None  # "affinity" | "anti-affinity"
    users: list[DbUserSpec] = []
    is_public: bool = False
    allowed_cidrs: list[str] = []
    configuration_id: str | None = None
    replica_of: str | None = None
    replica_count: int | None = None


class CreateDatabaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    character_set: str = "utf8"
    collate: str = "utf8_general_ci"


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)
    host: str = "%"
    databases: list[str] = []


class CreateBackupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class RestoreFromBackupRequest(BaseModel):
    backup_id: str
    name: str = Field(..., min_length=1, max_length=255)
    flavor_id: str
    volume_size: int = Field(..., ge=1, le=1024)
