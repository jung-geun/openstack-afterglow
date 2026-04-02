from pydantic import BaseModel


class LoginRequest(BaseModel):
    username: str
    password: str
    project_name: str = ""
    domain_name: str = "Default"


class TokenResponse(BaseModel):
    token: str
    project_id: str
    project_name: str
    user_id: str
    username: str
    expires_at: str


class UserInfo(BaseModel):
    user_id: str
    username: str
    project_id: str
    project_name: str
    roles: list[str]
