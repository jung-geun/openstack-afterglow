"""사용자 셀프서비스 프로젝트 관리 API."""

import asyncio
import logging

from fastapi import APIRouter, Depends, HTTPException, Path
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_token_info, require_project_manager
from app.database import get_session
from app.models.db import ProjectInvitation, ProjectRole

router = APIRouter()
_logger = logging.getLogger(__name__)


class CreateProjectRequest(BaseModel):
    name: str
    description: str = ""


class CreateInvitationRequest(BaseModel):
    email: str
    keystone_role: str = "member"


# ─── 프로젝트 생성 ────────────────────────────────────────────────────────────


@router.post("", status_code=201)
async def create_project(
    req: CreateProjectRequest,
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """인증된 사용자가 프로젝트를 생성합니다. 생성자는 자동으로 manager가 됩니다."""
    from app.services.project_service import create_project_for_user

    if not req.name.strip():
        raise HTTPException(status_code=422, detail="프로젝트 이름을 입력하세요")

    return await create_project_for_user(
        name=req.name.strip(),
        description=req.description,
        user_id=token_info["user_id"],
        username=token_info.get("username", ""),
        session=session,
    )


# ─── 멤버 조회 ────────────────────────────────────────────────────────────────


@router.get("/{project_id}/members")
async def list_project_members(
    project_id: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """프로젝트 멤버 목록 (Keystone role 할당 + manager 뱃지 + 본인 그룹 멤버 확장)."""
    await require_project_manager(project_id, token_info)

    # afterglow manager 목록
    result = await session.execute(
        select(ProjectRole).where(
            ProjectRole.project_id == project_id,
            ProjectRole.role == "manager",
        )
    )
    manager_user_ids = {r.user_id for r in result.scalars().all()}
    current_user_id = token_info["user_id"]

    def _list_members():
        from app.services import keystone

        ks = keystone._get_admin_ks_client()
        assignments = ks.role_assignments.list(project=project_id)

        members = []
        seen: set[str] = set()
        group_ids: list[str] = []

        # 직접 할당된 사용자 수집
        for a in assignments:
            user_raw = getattr(a, "user", None)
            group_raw = getattr(a, "group", None)
            if user_raw:
                user_id = user_raw.get("id") if isinstance(user_raw, dict) else getattr(user_raw, "id", None)
                if not user_id or user_id in seen:
                    continue
                seen.add(user_id)
                try:
                    u = ks.users.get(user_id)
                    members.append(
                        {
                            "user_id": user_id,
                            "username": u.name or "",
                            "email": getattr(u, "email", "") or "",
                            "is_manager": user_id in manager_user_ids,
                            "source": "direct",
                        }
                    )
                except Exception:
                    members.append(
                        {
                            "user_id": user_id,
                            "username": "",
                            "email": "",
                            "is_manager": user_id in manager_user_ids,
                            "source": "direct",
                        }
                    )
            elif group_raw:
                group_id = group_raw.get("id") if isinstance(group_raw, dict) else getattr(group_raw, "id", None)
                if group_id and group_id not in group_ids:
                    group_ids.append(group_id)

        # 본인이 속한 그룹의 멤버 확장
        for group_id in group_ids:
            try:
                group_members = list(ks.users.list(group=group_id))
                if not any(m.id == current_user_id for m in group_members):
                    continue
                try:
                    group_info = ks.groups.get(group_id)
                    group_name = group_info.name or group_id
                except Exception:
                    group_name = group_id
                for m in group_members:
                    if m.id in seen:
                        continue
                    seen.add(m.id)
                    members.append(
                        {
                            "user_id": m.id,
                            "username": m.name or "",
                            "email": getattr(m, "email", "") or "",
                            "is_manager": m.id in manager_user_ids,
                            "source": "group",
                            "group_name": group_name,
                        }
                    )
            except Exception:
                continue

        return members

    try:
        return {"items": await asyncio.to_thread(_list_members)}
    except Exception:
        raise HTTPException(status_code=500, detail="멤버 목록 조회 실패")


# ─── 초대 ─────────────────────────────────────────────────────────────────────


@router.post("/{project_id}/invitations", status_code=201)
async def create_invitation(
    req: CreateInvitationRequest,
    project_id: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """이메일 주소로 프로젝트에 초대합니다."""
    await require_project_manager(project_id, token_info)

    project_name = await _get_project_name(project_id)

    from app.services.project_service import create_invitation

    return await create_invitation(
        project_id=project_id,
        project_name=project_name,
        invited_email=req.email.lower().strip(),
        invited_by=token_info["user_id"],
        invited_by_name=token_info.get("username", ""),
        session=session,
    )


@router.get("/{project_id}/invitations")
async def list_invitations(
    project_id: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """프로젝트 초대 목록 조회."""
    await require_project_manager(project_id, token_info)

    result = await session.execute(
        select(ProjectInvitation)
        .where(ProjectInvitation.project_id == project_id)
        .order_by(ProjectInvitation.created_at.desc())
    )
    invitations = result.scalars().all()
    return {
        "items": [
            {
                "id": inv.id,
                "invited_email": inv.invited_email,
                "invited_by_name": inv.invited_by_name,
                "status": inv.status,
                "keystone_role": inv.keystone_role,
                "expires_at": inv.expires_at.isoformat() + "Z",
                "accepted_at": inv.accepted_at.isoformat() + "Z" if inv.accepted_at else None,
                "created_at": inv.created_at.isoformat() + "Z",
            }
            for inv in invitations
        ]
    }


@router.delete("/{project_id}/invitations/{invitation_id}", status_code=204)
async def revoke_invitation(
    project_id: str = Path(...),
    invitation_id: int = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """초대 취소 (pending 상태만 가능)."""
    await require_project_manager(project_id, token_info)

    result = await session.execute(
        select(ProjectInvitation).where(
            ProjectInvitation.id == invitation_id,
            ProjectInvitation.project_id == project_id,
        )
    )
    inv = result.scalar_one_or_none()
    if inv is None:
        raise HTTPException(status_code=404, detail="초대를 찾을 수 없습니다")
    if inv.status != "pending":
        raise HTTPException(status_code=409, detail="취소할 수 없는 상태의 초대입니다")

    inv.status = "revoked"
    await session.commit()


# ─── 매니저 관리 ──────────────────────────────────────────────────────────────


@router.post("/{project_id}/managers/{user_id}", status_code=204)
async def promote_manager(
    project_id: str = Path(...),
    user_id: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """프로젝트 멤버를 manager로 승격합니다."""
    await require_project_manager(project_id, token_info)

    from app.services.project_service import promote_to_manager

    await promote_to_manager(project_id, user_id, token_info["user_id"], session)


@router.delete("/{project_id}/managers/{user_id}", status_code=204)
async def demote_manager(
    project_id: str = Path(...),
    user_id: str = Path(...),
    token_info: dict = Depends(get_token_info),
    session: AsyncSession = Depends(get_session),
):
    """manager 권한을 해제합니다. 마지막 manager는 해제할 수 없습니다."""
    await require_project_manager(project_id, token_info)

    from app.services.project_service import demote_manager

    await demote_manager(project_id, user_id, session)


# ─── 헬퍼 ─────────────────────────────────────────────────────────────────────


async def _get_project_name(project_id: str) -> str:
    from app.services import keystone

    def _lookup():
        ks = keystone._get_admin_ks_client()
        try:
            p = ks.projects.get(project_id)
            return p.name or project_id
        except Exception:
            return project_id

    try:
        return await asyncio.to_thread(_lookup)
    except Exception:
        return project_id
