from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=1, max_length=255)
    password: str = Field(..., min_length=1, max_length=1024)
    project_name: str = Field("", max_length=255)
    domain_name: str = Field("Default", max_length=255)


class TokenResponse(BaseModel):
    token: str
    project_id: str
    project_name: str
    user_id: str
    username: str
    expires_at: str
    roles: list[str] = []
    default_project_id: str = ""


class UserInfo(BaseModel):
    user_id: str
    username: str
    project_id: str
    project_name: str
    roles: list[str]


class ProjectInfo(BaseModel):
    id: str
    name: str
    description: str = ""
    domain_id: str | None = None
    enabled: bool = True


class GitLabCallbackRequest(BaseModel):
    code: str = Field(..., min_length=1, max_length=2048)
    state: str = Field(..., min_length=1, max_length=256)
