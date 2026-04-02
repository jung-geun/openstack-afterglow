from pydantic import BaseModel
from typing import Optional


class ShareInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    share_proto: str
    export_locations: list[str] = []
    metadata: dict = {}
    # Union 전용 메타데이터
    library_name: Optional[str] = None
    library_version: Optional[str] = None
    built_at: Optional[str] = None


class LibraryConfig(BaseModel):
    id: str           # e.g. "python311"
    name: str         # e.g. "Python 3.11"
    version: str      # e.g. "3.11"
    packages: list[str]   # pip packages to install
    depends_on: list[str] = []   # library ids this depends on
    share_id: Optional[str] = None   # prebuilt share id (Strategy A)
    available_prebuilt: bool = False


class VolumeInfo(BaseModel):
    id: str
    name: str
    status: str
    size: int  # GB
    volume_type: Optional[str] = None
    attachments: list[dict] = []
