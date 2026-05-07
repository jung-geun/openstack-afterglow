"""오브젝트 스토리지 버킷 이름 검증 (Phase 10).

S3 RFC 1123 명명 규칙 + Ceph/Swift/AWS 예약어 + 관리용 시스템 이름을 금지.
순수 함수로 구현 — backend endpoint 와 test 모두에서 직접 호출 가능.
frontend `frontend/src/lib/utils/bucketName.ts` 와 정책을 동일하게 유지해야 함.
"""

from __future__ import annotations

import re

# ---------------------------------------------------------------------------
# 정책 상수
# ---------------------------------------------------------------------------

# 정확한 이름 일치 (case-insensitive). 시스템/관리/벤더 예약어.
_RESERVED_EXACT: frozenset[str] = frozenset(
    {
        "admin",
        "administrator",
        "root",
        "system",
        "default",
        "swift",
        "ceph",
        "rgw",
        "s3",
        "aws",
        "bucket",
        "container",
        "account",
        "test-quarantine",
        ".well-known",
    }
)

# 접미사 (suffix). 우리 시스템 패턴 충돌 방지.
_RESERVED_SUFFIXES: tuple[str, ...] = ("-quarantine", "_segments")

# 접두사 (prefix). 벤더 / Swift internal 충돌 방지.
_RESERVED_PREFIXES: tuple[str, ...] = ("aws-", "amazon-", "_account", "_container")

# 형식 규칙: 3~63자, 소문자/숫자/하이픈, 시작/끝은 소문자/숫자.
# 점(.) 미허용 (TLS host header 접두 충돌 회피).
_FORMAT_RE = re.compile(r"^[a-z0-9][a-z0-9\-]{1,61}[a-z0-9]$")
_IPV4_RE = re.compile(r"^(?:\d{1,3}\.){3}\d{1,3}$")


# ---------------------------------------------------------------------------
# 검증 함수
# ---------------------------------------------------------------------------


def validate_bucket_name(name: str) -> None:
    """버킷 이름 검증. 위반 시 한국어 사유로 ValueError raise.

    호출자(endpoint)는 ValueError 를 catch 해서 HTTPException(400, str(e)) 로 변환.

    검사 순서: 명확한 의미 위반(점/하이픈 시작) → 예약어/패턴 → 길이 → 형식.
    예약어가 형식 검사보다 먼저 — 사용자에게 더 명확한 사유 전달.
    """
    if not isinstance(name, str):
        raise ValueError("이름은 문자열이어야 합니다.")

    if name != name.strip():
        raise ValueError("이름의 앞뒤 공백을 제거해 주세요.")

    if not name:
        raise ValueError("버킷 이름이 비어 있습니다.")

    # 도트/하이픈으로 시작 — 가장 명확한 형식 위반
    if name.startswith("."):
        raise ValueError("버킷 이름은 점(.)으로 시작할 수 없습니다.")
    if name.startswith("-"):
        raise ValueError("버킷 이름은 하이픈(-)으로 시작할 수 없습니다.")

    # 정확한 예약어 (case-insensitive) — 길이/형식과 무관
    lower = name.lower()
    if lower in _RESERVED_EXACT:
        raise ValueError(f"'{name}' 은(는) 관리용 예약 이름이라 사용할 수 없습니다.")

    # 접미사 검사 (case-insensitive)
    for suf in _RESERVED_SUFFIXES:
        if lower.endswith(suf):
            raise ValueError(f"'{suf}' 로 끝나는 이름은 시스템 예약 패턴이라 사용할 수 없습니다.")

    # 접두사 검사 (case-insensitive)
    for pre in _RESERVED_PREFIXES:
        if lower.startswith(pre):
            raise ValueError(f"'{pre}' 로 시작하는 이름은 시스템 예약 패턴이라 사용할 수 없습니다.")

    # 길이 검사
    if len(name) < 3:
        raise ValueError("버킷 이름은 3자 이상이어야 합니다.")
    if len(name) > 63:
        raise ValueError("버킷 이름은 63자 이하여야 합니다.")

    # 형식 검사 — 소문자/숫자/하이픈만, 시작/끝은 소문자/숫자
    if not _FORMAT_RE.match(name):
        # 더 친절한 메시지를 위해 분기
        if not name.islower() and any(ch.isupper() for ch in name):
            raise ValueError("버킷 이름은 소문자만 사용할 수 있습니다.")
        if "." in name:
            raise ValueError("버킷 이름에 점(.)은 사용할 수 없습니다.")
        if "_" in name:
            raise ValueError("버킷 이름에 밑줄(_)은 사용할 수 없습니다.")
        if " " in name:
            raise ValueError("버킷 이름에 공백을 사용할 수 없습니다.")
        # 그 외 특수문자
        for ch in name:
            if not (ch.isalnum() or ch == "-"):
                raise ValueError(f"'{ch}' 문자는 사용할 수 없습니다 (소문자, 숫자, 하이픈만 가능).")
        # 형식상 다른 문제 (예: 시작/끝 하이픈 — 위에서 시작 하이픈은 처리, 끝만 남음)
        if name.endswith("-"):
            raise ValueError("버킷 이름은 하이픈(-)으로 끝날 수 없습니다.")
        raise ValueError("버킷 이름이 명명 규칙과 맞지 않습니다.")

    # 연속 하이픈 금지
    if "--" in name:
        raise ValueError("버킷 이름에 연속된 하이픈(--)을 사용할 수 없습니다.")

    # IP 주소 형식 금지
    if _IPV4_RE.match(name):
        raise ValueError("버킷 이름은 IP 주소 형식일 수 없습니다.")
