"""빌트인 AI 채팅 관리자 통계 라우터 테스트.

DB 없이 stats 서비스를 monkeypatch 하여 라우터 계약만 검증:
- require_admin 게이트(비관리자 403)
- range 정규화(미지원 값 → all), project_id 전달
- 응답 묶음(overview/by_model/monthly/by_user/projects) 구조
- 사용자 페이지네이션 엔드포인트
"""

from app.services.chat import stats as stats_service

_URL = "/api/v1/chat/admin/stats"


class TestAdminGate:
    async def test_stats_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.get(_URL)
        assert resp.status_code == 403

    async def test_stats_users_forbidden_for_non_admin(self, non_admin_client):
        resp = await non_admin_client.get(f"{_URL}/users")
        assert resp.status_code == 403


class TestStatsBundle:
    async def test_bundle_shape_and_range_normalization(self, admin_client, monkeypatch):
        captured = {}

        async def fake_overview(rng, pid):
            captured["overview"] = (rng, pid)
            return {"total_tokens": 42, "active_users": 3}

        async def fake_by_model(rng, pid):
            return [{"model_name": "gpt-4o", "total_tokens": 42}]

        async def fake_monthly(rng, pid):
            return [{"month": "2026-07", "ts": 1, "total_tokens": 42}]

        async def fake_by_user(rng, pid, limit=20, offset=0):
            captured["by_user_limit"] = limit
            return [{"user_id": "u1", "total_tokens": 42}]

        async def fake_projects(rng):
            return ["p1", "p2"]

        monkeypatch.setattr(stats_service, "overview", fake_overview)
        monkeypatch.setattr(stats_service, "by_model", fake_by_model)
        monkeypatch.setattr(stats_service, "monthly", fake_monthly)
        monkeypatch.setattr(stats_service, "by_user", fake_by_user)
        monkeypatch.setattr(stats_service, "projects_with_usage", fake_projects)

        # 미지원 range 는 'all' 로 정규화되어야 함
        resp = await admin_client.get(f"{_URL}?range=bogus&project_id=p1&user_limit=5")
        assert resp.status_code == 200
        body = resp.json()
        assert body["range"] == "all"
        assert body["project_id"] == "p1"
        assert captured["overview"] == ("all", "p1")
        assert captured["by_user_limit"] == 5
        assert body["overview"]["total_tokens"] == 42
        assert body["by_model"][0]["model_name"] == "gpt-4o"
        assert body["monthly"][0]["month"] == "2026-07"
        assert body["by_user"][0]["user_id"] == "u1"
        assert body["projects"] == ["p1", "p2"]

    async def test_valid_range_preserved(self, admin_client, monkeypatch):
        captured = {}

        async def fake_overview(rng, pid):
            captured["rng"] = rng
            return {}

        async def _empty(*a, **k):
            return []

        monkeypatch.setattr(stats_service, "overview", fake_overview)
        monkeypatch.setattr(stats_service, "by_model", _empty)
        monkeypatch.setattr(stats_service, "monthly", _empty)
        monkeypatch.setattr(stats_service, "by_user", _empty)
        monkeypatch.setattr(stats_service, "projects_with_usage", _empty)

        resp = await admin_client.get(f"{_URL}?range=30d")
        assert resp.status_code == 200
        assert captured["rng"] == "30d"


class TestStatsUsers:
    async def test_users_pagination(self, admin_client, monkeypatch):
        captured = {}

        async def fake_by_user(rng, pid, limit=20, offset=0):
            captured.update({"rng": rng, "pid": pid, "limit": limit, "offset": offset})
            return [{"user_id": "u1"}]

        monkeypatch.setattr(stats_service, "by_user", fake_by_user)
        resp = await admin_client.get(f"{_URL}/users?range=90d&project_id=p9&limit=50&offset=100")
        assert resp.status_code == 200
        assert resp.json()["users"][0]["user_id"] == "u1"
        assert captured == {"rng": "90d", "pid": "p9", "limit": 50, "offset": 100}
