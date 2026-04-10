"""
Notion Database 동기화 서비스.

OpenStack 인스턴스 목록을 Notion DB에 주기적으로 동기화한다.
각 인스턴스가 하나의 행(페이지)으로 관리된다.
DB의 실제 속성 타입을 읽어 그에 맞는 형식으로 데이터를 전송한다.
"""

import asyncio
import json
import logging
import re

import httpx

_logger = logging.getLogger(__name__)

NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_VERSION = "2022-06-28"
REDIS_CONFIG_KEY = "union:notion:config"

# 속성 이름 → 인스턴스 데이터 키 매핑
# DB에 이 이름의 속성이 있으면 해당 데이터를 채운다.
# relation 타입: 값은 page_id 문자열 (비어있으면 relation 해제)
FIELD_MAP: dict[str, str] = {
    "user": "user_page_id",             # relation → People DB
    "openstack resource": "hypervisor_page_id",  # relation → Hypervisor DB
    "team": "project_name",
    "flavor": "flavor_name",
    "CPU (c)": "vcpus",
    "MEM (G)": "ram_gb",
    "GPU": "gpu_name",
    "GPU 개수": "gpu_count",
    "fixed ip": "fixed_ip",
    "floating ip": "floating_ip",
    "instance id": "instance_id",
    "status": "status",
    "생성된 날짜": "created_at",
}

# ensure_db_properties에서 누락된 속성을 생성할 때의 기본 타입
# relation 속성은 자동 생성 불가 (이미 DB에 존재해야 함)
DEFAULT_PROPERTY_TYPES: dict[str, str] = {
    "team": "select",
    "flavor": "rich_text",
    "CPU (c)": "number",
    "MEM (G)": "number",
    "GPU": "rich_text",
    "GPU 개수": "number",
    "fixed ip": "rich_text",
    "floating ip": "rich_text",
    "instance id": "rich_text",
    "status": "select",
    "생성된 날짜": "date",
}


def _headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


# ---------------------------------------------------------------------------
# DB 설정/검증
# ---------------------------------------------------------------------------

async def validate_notion_config(api_key: str, database_id: str) -> tuple[bool, str]:
    """Notion DB 접근 가능 여부를 확인한다."""
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(
                f"{NOTION_API_BASE}/databases/{database_id}",
                headers=_headers(api_key),
            )
        if resp.status_code == 200:
            return True, "연결 성공"
        body = resp.json()
        msg = body.get("message", resp.text)
        if resp.status_code == 401:
            return False, f"인증 실패: API Key를 확인하세요 — {msg}"
        if resp.status_code == 404:
            return False, "Database를 찾을 수 없습니다. ID를 확인하고, Integration에 DB 접근 권한이 있는지 확인하세요."
        return False, f"Notion API 오류 ({resp.status_code}): {msg}"
    except httpx.TimeoutException:
        return False, "Notion API 응답 시간 초과"
    except Exception as e:
        return False, f"연결 오류: {e}"


async def _get_db_schema(client: httpx.AsyncClient, api_key: str, database_id: str) -> dict:
    """DB의 전체 속성 스키마를 반환한다. {속성이름: {type, ...}}"""
    resp = await client.get(
        f"{NOTION_API_BASE}/databases/{database_id}",
        headers=_headers(api_key),
    )
    resp.raise_for_status()
    return resp.json().get("properties", {})


def _find_title_prop(schema: dict) -> str:
    """스키마에서 title 타입 속성 이름을 반환."""
    for name, defn in schema.items():
        if defn.get("type") == "title":
            return name
    return "Name"


async def ensure_db_properties(api_key: str, database_id: str) -> None:
    """DB에 필요한 속성이 없으면 자동 생성한다. relation 타입은 생략."""
    async with httpx.AsyncClient(timeout=15) as client:
        schema = await _get_db_schema(client, api_key, database_id)
        existing = set(schema.keys())

        missing: dict = {}
        for prop_name, prop_type in DEFAULT_PROPERTY_TYPES.items():
            if prop_name not in existing:
                if prop_type == "number":
                    missing[prop_name] = {"number": {}}
                elif prop_type == "rich_text":
                    missing[prop_name] = {"rich_text": {}}

        if not missing:
            return

        patch_resp = await client.patch(
            f"{NOTION_API_BASE}/databases/{database_id}",
            headers=_headers(api_key),
            json={"properties": missing},
        )
        patch_resp.raise_for_status()
        _logger.info("Notion DB 속성 %d개 자동 생성: %s", len(missing), list(missing.keys()))


# ---------------------------------------------------------------------------
# 인스턴스 데이터 → Notion properties 변환 (DB 속성 타입에 맞게)
# ---------------------------------------------------------------------------

def _format_value(prop_type: str, value) -> dict | None:
    """DB 속성 타입에 맞는 Notion property value를 생성한다."""
    if prop_type == "title":
        return {"title": [{"text": {"content": str(value)}}]} if value else {"title": []}
    elif prop_type == "rich_text":
        return {"rich_text": [{"text": {"content": str(value)}}]} if value else {"rich_text": []}
    elif prop_type == "number":
        try:
            return {"number": int(value) if value else 0}
        except (ValueError, TypeError):
            return {"number": 0}
    elif prop_type == "select":
        return {"select": {"name": str(value)}} if value else {"select": None}
    elif prop_type == "multi_select":
        items = str(value).split(", ") if value else []
        return {"multi_select": [{"name": v.strip()} for v in items if v.strip()]}
    elif prop_type == "url":
        return {"url": str(value) if value else None}
    elif prop_type == "email":
        return {"email": str(value) if value else None}
    elif prop_type == "phone_number":
        return {"phone_number": str(value) if value else None}
    elif prop_type == "checkbox":
        return {"checkbox": bool(value)}
    elif prop_type == "date":
        if value:
            return {"date": {"start": str(value)}}
        return {"date": None}
    elif prop_type == "relation":
        # value: page_id 문자열, page_id 리스트, 또는 빈 값(relation 해제)
        if not value:
            return {"relation": []}
        if isinstance(value, str):
            return {"relation": [{"id": value}]}
        if isinstance(value, list):
            return {"relation": [{"id": pid} for pid in value if pid]}
        return {"relation": []}
    else:
        # 지원하지 않는 타입은 건너뛴다 (people, formula, rollup 등)
        return None


def _build_instance_properties(schema: dict, title_prop: str, inst: dict) -> dict:
    """인스턴스 dict를 DB 스키마에 맞는 Notion page properties로 변환."""
    props: dict = {}

    # title 속성
    props[title_prop] = _format_value("title", inst.get("name", ""))

    # 나머지 속성: DB에 존재하고 FIELD_MAP에 매핑이 있는 것만
    for prop_name, prop_def in schema.items():
        if prop_name == title_prop:
            continue
        data_key = FIELD_MAP.get(prop_name)
        if data_key is None:
            continue  # 매핑 없는 속성은 건너뛴다
        prop_type = prop_def.get("type", "")
        value = inst.get(data_key, "")
        formatted = _format_value(prop_type, value)
        if formatted is not None:
            props[prop_name] = formatted

    return props


# ---------------------------------------------------------------------------
# 동기화 로직
# ---------------------------------------------------------------------------

async def _fetch_all_pages(client: httpx.AsyncClient, api_key: str, database_id: str) -> list[dict]:
    """DB의 모든 페이지를 가져온다 (페이지네이션 처리)."""
    pages: list[dict] = []
    has_more = True
    start_cursor = None

    while has_more:
        body: dict = {"page_size": 100}
        if start_cursor:
            body["start_cursor"] = start_cursor

        resp = await client.post(
            f"{NOTION_API_BASE}/databases/{database_id}/query",
            headers=_headers(api_key),
            json=body,
        )
        if resp.status_code != 200:
            _logger.error("Notion DB query 실패 (%d): %s", resp.status_code, resp.text)
            resp.raise_for_status()

        data = resp.json()
        pages.extend(data.get("results", []))
        has_more = data.get("has_more", False)
        start_cursor = data.get("next_cursor")

    return pages


def _extract_rich_text(page: dict, prop_name: str) -> str:
    """페이지에서 rich_text 속성의 plain_text를 추출한다."""
    prop = page.get("properties", {}).get(prop_name, {})
    prop_type = prop.get("type", "")
    if prop_type == "title":
        arr = prop.get("title", [])
    elif prop_type == "rich_text":
        arr = prop.get("rich_text", [])
    else:
        return ""
    return arr[0].get("plain_text", "") if arr else ""


async def sync_to_notion(api_key: str, database_id: str, instances: list[dict]) -> dict:
    """인스턴스 목록을 Notion DB에 동기화한다. 결과 통계 반환."""
    stats = {"created": 0, "updated": 0, "archived": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=30) as client:
        # DB 스키마 읽기
        schema = await _get_db_schema(client, api_key, database_id)
        title_prop = _find_title_prop(schema)

        # 기존 페이지 조회 → {instance_id: page_id} 맵
        existing_pages = await _fetch_all_pages(client, api_key, database_id)
        has_instance_id_prop = "instance id" in schema
        page_map: dict[str, str] = {}
        for page in existing_pages:
            if has_instance_id_prop:
                key = _extract_rich_text(page, "instance id")
            else:
                key = _extract_rich_text(page, title_prop)
            if key:
                page_map[key] = page["id"]

        seen_keys = set()
        sem = asyncio.Semaphore(3)  # Notion API rate limit: 3 req/s

        async def _upsert(inst: dict) -> None:
            inst_id = inst.get("instance_id", "")
            name = inst.get("name", "")
            match_key = inst_id if has_instance_id_prop else name
            if not match_key:
                return
            seen_keys.add(match_key)
            properties = _build_instance_properties(schema, title_prop, inst)

            async with sem:
                try:
                    if match_key in page_map:
                        resp = await client.patch(
                            f"{NOTION_API_BASE}/pages/{page_map[match_key]}",
                            headers=_headers(api_key),
                            json={"properties": properties},
                        )
                    else:
                        resp = await client.post(
                            f"{NOTION_API_BASE}/pages",
                            headers=_headers(api_key),
                            json={
                                "parent": {"database_id": database_id},
                                "properties": properties,
                            },
                        )

                    if resp.status_code >= 400:
                        _logger.warning(
                            "Notion 페이지 동기화 실패 (instance=%s, status=%d): %s",
                            name, resp.status_code, resp.text,
                        )
                        stats["errors"] += 1
                    else:
                        stats["updated" if match_key in page_map else "created"] += 1

                except Exception as e:
                    _logger.warning("Notion 페이지 동기화 실패 (instance=%s): %s", name, e)
                    stats["errors"] += 1

        await asyncio.gather(*[_upsert(inst) for inst in instances])

        # Notion에만 있고 OpenStack에 없는 페이지 → openstack resource relation 해제 후 아카이브
        has_resource_prop = "openstack resource" in schema

        async def _archive(key: str, page_id: str) -> None:
            async with sem:
                try:
                    body: dict = {"archived": True}
                    if has_resource_prop:
                        body["properties"] = {"openstack resource": {"relation": []}}
                    resp = await client.patch(
                        f"{NOTION_API_BASE}/pages/{page_id}",
                        headers=_headers(api_key),
                        json=body,
                    )
                    if resp.status_code < 400:
                        stats["archived"] += 1
                    else:
                        stats["errors"] += 1
                except Exception as e:
                    _logger.warning("Notion 페이지 아카이브 실패 (key=%s): %s", key, e)
                    stats["errors"] += 1

        to_archive = [(k, pid) for k, pid in page_map.items() if k not in seen_keys]
        if to_archive:
            await asyncio.gather(*[_archive(k, pid) for k, pid in to_archive])

    _logger.info(
        "Notion 동기화 완료: created=%d updated=%d archived=%d errors=%d",
        stats["created"], stats["updated"], stats["archived"], stats["errors"],
    )
    return stats


# ---------------------------------------------------------------------------
# GPU 이름 추출 헬퍼
# ---------------------------------------------------------------------------

def _gpu_info_from_flavor(flavor_name: str, extra_specs: dict) -> tuple[str, int]:
    """플레이버에서 (GPU 이름, GPU 개수) 를 추출한다."""
    alias = extra_specs.get("pci_passthrough:alias", "")
    if alias:
        gpu_name = ""
        count = 0
        for entry in alias.split(","):
            entry = entry.strip()
            if ":" not in entry:
                continue
            dev, num = entry.rsplit(":", 1)
            if "audio" in dev.lower():
                continue
            if not gpu_name:
                gpu_name = dev
            try:
                count += int(num)
            except ValueError:
                count += 1
        if count > 0:
            return gpu_name, count

    # 이름 기반 fallback: gpu.3090_8c_16g → "3090"
    m = re.match(r'^gpu\.([^_]+)', flavor_name)
    if m:
        return m.group(1), 1

    return "", 0


# ---------------------------------------------------------------------------
# Redis config helpers
# ---------------------------------------------------------------------------

async def get_notion_config() -> dict | None:
    from app.services.cache import _get_redis
    try:
        r = await _get_redis()
        raw = await r.get(REDIS_CONFIG_KEY)
        if not raw:
            return None
        return json.loads(raw)
    except Exception:
        _logger.warning("Notion 설정 읽기 실패", exc_info=True)
        return None


async def save_notion_config(config: dict) -> None:
    from app.services.cache import _get_redis
    r = await _get_redis()
    await r.set(REDIS_CONFIG_KEY, json.dumps(config))


async def delete_notion_config() -> None:
    from app.services.cache import _get_redis
    r = await _get_redis()
    await r.delete(REDIS_CONFIG_KEY)


def mask_api_key(key: str) -> str:
    if len(key) <= 10:
        return "****"
    return key[:7] + "****" + key[-4:]


# ---------------------------------------------------------------------------
# 하이퍼바이저 동기화
# ---------------------------------------------------------------------------

# 실제 Hypervisor DB 컬럼명에 맞춘 매핑
HYPERVISOR_FIELD_MAP: dict[str, str] = {
    "core": "vcpus",
    "사용중인 core": "vcpus_used",
    "ram": "memory_size_gb",
    "사용중인 ram": "memory_used_gb",
}

HYPERVISOR_DEFAULT_PROPERTY_TYPES: dict[str, str] = {
    "core": "number",
    "사용중인 core": "number",
    "ram": "number",
    "사용중인 ram": "number",
}


async def ensure_hypervisor_db_properties(api_key: str, database_id: str) -> None:
    """하이퍼바이저 DB에 필요한 속성이 없으면 자동 생성한다."""
    async with httpx.AsyncClient(timeout=15) as client:
        schema = await _get_db_schema(client, api_key, database_id)
        existing = set(schema.keys())

        missing: dict = {}
        for prop_name, prop_type in HYPERVISOR_DEFAULT_PROPERTY_TYPES.items():
            if prop_name not in existing:
                if prop_type == "number":
                    missing[prop_name] = {"number": {}}
                elif prop_type == "rich_text":
                    missing[prop_name] = {"rich_text": {}}

        if not missing:
            return

        patch_resp = await client.patch(
            f"{NOTION_API_BASE}/databases/{database_id}",
            headers=_headers(api_key),
            json={"properties": missing},
        )
        patch_resp.raise_for_status()
        _logger.info("Notion 하이퍼바이저 DB 속성 %d개 자동 생성: %s", len(missing), list(missing.keys()))


async def sync_hypervisors_to_notion(api_key: str, database_id: str, hypervisors: list[dict]) -> dict:
    """하이퍼바이저 목록을 Notion DB에 동기화한다. 결과 통계 반환."""
    stats = {"created": 0, "updated": 0, "archived": 0, "errors": 0}

    async with httpx.AsyncClient(timeout=30) as client:
        schema = await _get_db_schema(client, api_key, database_id)
        title_prop = _find_title_prop(schema)

        existing_pages = await _fetch_all_pages(client, api_key, database_id)
        page_map: dict[str, str] = {}
        for page in existing_pages:
            key = _extract_rich_text(page, title_prop)
            if key:
                page_map[key] = page["id"]

        seen_keys: set[str] = set()
        sem = asyncio.Semaphore(3)

        async def _upsert(h: dict) -> None:
            name = h.get("name", "")
            if not name:
                return
            seen_keys.add(name)

            props: dict = {title_prop: _format_value("title", name)}
            for prop_name, prop_def in schema.items():
                if prop_name == title_prop:
                    continue
                data_key = HYPERVISOR_FIELD_MAP.get(prop_name)
                if data_key is None:
                    continue
                prop_type = prop_def.get("type", "")
                formatted = _format_value(prop_type, h.get(data_key, ""))
                if formatted is not None:
                    props[prop_name] = formatted

            async with sem:
                try:
                    if name in page_map:
                        resp = await client.patch(
                            f"{NOTION_API_BASE}/pages/{page_map[name]}",
                            headers=_headers(api_key),
                            json={"properties": props},
                        )
                    else:
                        resp = await client.post(
                            f"{NOTION_API_BASE}/pages",
                            headers=_headers(api_key),
                            json={"parent": {"database_id": database_id}, "properties": props},
                        )
                    if resp.status_code >= 400:
                        _logger.warning("Notion 하이퍼바이저 동기화 실패 (%s, %d): %s", name, resp.status_code, resp.text)
                        stats["errors"] += 1
                    else:
                        stats["updated" if name in page_map else "created"] += 1
                except Exception as e:
                    _logger.warning("Notion 하이퍼바이저 동기화 실패 (%s): %s", name, e)
                    stats["errors"] += 1

        await asyncio.gather(*[_upsert(h) for h in hypervisors])

        async def _archive(key: str, page_id: str) -> None:
            async with sem:
                try:
                    resp = await client.patch(
                        f"{NOTION_API_BASE}/pages/{page_id}",
                        headers=_headers(api_key),
                        json={"archived": True},
                    )
                    stats["archived" if resp.status_code < 400 else "errors"] += 1
                except Exception as e:
                    _logger.warning("Notion 하이퍼바이저 아카이브 실패 (%s): %s", key, e)
                    stats["errors"] += 1

        to_archive = [(k, pid) for k, pid in page_map.items() if k not in seen_keys]
        if to_archive:
            await asyncio.gather(*[_archive(k, pid) for k, pid in to_archive])

    _logger.info(
        "Notion 하이퍼바이저 동기화 완료: created=%d updated=%d archived=%d errors=%d",
        stats["created"], stats["updated"], stats["archived"], stats["errors"],
    )
    return stats


# ---------------------------------------------------------------------------
# 사용자 DB 조회 (이메일 → page_id 매핑)
# ---------------------------------------------------------------------------

async def fetch_user_page_ids_by_email(api_key: str, users_database_id: str) -> dict[str, str]:
    """People DB에서 이메일(lower) → Notion page_id 맵을 반환한다 (조회 전용).

    인스턴스 DB의 'user' relation 속성에 설정할 page_id를 얻기 위해 사용한다.
    """
    email_to_page_id: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            pages = await _fetch_all_pages(client, api_key, users_database_id)
            for page in pages:
                props = page.get("properties", {})
                # 이메일: "이메일" 속성 (email 또는 rich_text 타입)
                email_prop = props.get("이메일", {})
                email = ""
                if email_prop.get("type") == "email":
                    email = email_prop.get("email", "") or ""
                elif email_prop.get("type") == "rich_text":
                    arr = email_prop.get("rich_text", [])
                    email = arr[0].get("plain_text", "") if arr else ""
                if email:
                    email_to_page_id[email.lower()] = page["id"]
    except Exception:
        _logger.warning("People DB 이메일 조회 실패", exc_info=True)
    return email_to_page_id


async def fetch_hypervisor_page_ids_by_name(api_key: str, hypervisors_database_id: str) -> dict[str, str]:
    """Hypervisor DB에서 이름(title) → Notion page_id 맵을 반환한다.

    인스턴스 DB의 'openstack resource' relation 속성에 설정할 page_id를 얻기 위해 사용한다.
    하이퍼바이저 동기화 완료 후 호출해야 한다.
    """
    name_to_page_id: dict[str, str] = {}
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            schema = await _get_db_schema(client, api_key, hypervisors_database_id)
            title_prop = _find_title_prop(schema)
            pages = await _fetch_all_pages(client, api_key, hypervisors_database_id)
            for page in pages:
                name = _extract_rich_text(page, title_prop)
                if name:
                    name_to_page_id[name] = page["id"]
    except Exception:
        _logger.warning("Hypervisor DB 이름 조회 실패", exc_info=True)
    return name_to_page_id
