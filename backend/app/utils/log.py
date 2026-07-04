"""보안 민감 데이터 마스킹 로그 유틸리티."""

from __future__ import annotations

import logging
import re

# 정확 매칭 대상 필드명 (소문자 + 언더스코어 정규화)
_SENSITIVE_EXACT: frozenset[str] = frozenset(
    {
        "password",
        "passwd",
        "secret",
        "token",
        "access_token",
        "refresh_token",
        "build_token",
        "report_token",
        "monitoring_sd_token",
        "x_auth_token",
        "key",
        "cephx_key",
        "private_key",
        "api_key",
        "kubeconfig",
        "kube_config",
        "authorization",
    }
)

# 필드명에 이 문자열이 포함되면 마스킹
_SENSITIVE_SUBSTR: tuple[str, ...] = (
    "password",
    "passwd",
    "secret",
    "token",
    "private_key",
    "kubeconfig",
)

# JWT/Bearer 패턴
_BEARER_RE = re.compile(r"((?:Bearer|Token)\s+)([A-Za-z0-9\-_\.]{8,})", re.IGNORECASE)
_JWT_RE = re.compile(r"(eyJ[A-Za-z0-9\-_]{4,}\.eyJ[A-Za-z0-9\-_]{4,})\.[A-Za-z0-9\-_]+")


def _normalize_key(key: str) -> str:
    return key.lower().replace("-", "_")


def is_sensitive(key: str) -> bool:
    """필드 이름이 민감 정보 키인지 판별."""
    k = _normalize_key(key)
    return k in _SENSITIVE_EXACT or any(s in k for s in _SENSITIVE_SUBSTR)


def mask_value(val: object) -> str:
    """값을 마스킹. 4자 초과면 앞 4자 + '***', 아니면 전체 '***'."""
    s = str(val) if val is not None else ""
    if not s:
        return "***"
    return (s[:4] + "***") if len(s) > 4 else "***"


def mask_dict(d: dict, *, _depth: int = 3) -> dict:
    """딕셔너리에서 민감 필드를 재귀적으로 마스킹한 복사본 반환."""
    if _depth <= 0:
        return d
    result: dict = {}
    for k, v in d.items():
        if is_sensitive(str(k)):
            result[k] = mask_value(v) if v is not None else v
        elif isinstance(v, dict):
            result[k] = mask_dict(v, _depth=_depth - 1)
        elif isinstance(v, list):
            result[k] = [mask_dict(i, _depth=_depth - 1) if isinstance(i, dict) else i for i in v]
        else:
            result[k] = v
    return result


def mask_str(msg: str) -> str:
    """문자열에서 JWT/Bearer 토큰 패턴을 마스킹."""
    msg = _BEARER_RE.sub(lambda m: m.group(1) + m.group(2)[:4] + "***", msg)
    msg = _JWT_RE.sub(lambda m: m.group(1)[:12] + "***", msg)
    return msg


class SensitiveDataFilter(logging.Filter):
    """로그 레코드에서 민감 데이터를 자동으로 마스킹하는 필터.

    - 메시지 문자열: JWT, Bearer 토큰 패턴 제거
    - extra 필드: 민감 키 이름 감지 후 값 마스킹
    """

    _SKIP_ATTRS: frozenset[str] = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__)

    def filter(self, record: logging.LogRecord) -> bool:
        # 메시지 마스킹
        if isinstance(record.msg, str):
            record.msg = mask_str(record.msg)

        # args 마스킹 (% 포매팅 인자)
        if record.args:
            if isinstance(record.args, dict):
                record.args = mask_dict(record.args)
            elif isinstance(record.args, tuple):
                record.args = tuple(
                    mask_value(a) if isinstance(a, str) and len(a) > 20 and _looks_like_token(a) else a
                    for a in record.args
                )

        # extra 필드 마스킹
        for attr in list(vars(record)):
            if attr in self._SKIP_ATTRS:
                continue
            if is_sensitive(attr):
                val = getattr(record, attr)
                if val is not None:
                    setattr(record, attr, mask_value(val))

        return True


def _looks_like_token(s: str) -> bool:
    """문자열이 토큰처럼 보이는지 휴리스틱 판별 (영숫자+특수문자만, 공백 없음)."""
    return bool(s) and " " not in s and re.fullmatch(r"[A-Za-z0-9\-_\.+/=]{20,}", s) is not None
