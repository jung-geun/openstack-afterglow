from pydantic import BaseModel, Field


class CreateDbInstanceRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    flavor_id: str = Field(..., min_length=1)
    volume_size: int = Field(..., ge=1, le=1024)
    datastore_type: str = Field(..., min_length=1)
    datastore_version: str = Field(..., min_length=1)
    databases: list[str] = []
    restore_backup_id: str | None = None


class CreateDatabaseRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    character_set: str = "utf8"
    collate: str = "utf8_general_ci"


class CreateUserRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=64)
    password: str = Field(..., min_length=1)
    databases: list[str] = []


class CreateBackupRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str = ""


class RestoreFromBackupRequest(BaseModel):
    backup_id: str
    name: str = Field(..., min_length=1, max_length=255)
    flavor_id: str
    volume_size: int = Field(..., ge=1, le=1024)
