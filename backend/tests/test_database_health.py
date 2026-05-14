"""database.py circuit breaker + init_db 옵션 검증 단위 테스트."""

from unittest.mock import MagicMock, patch


def test_mark_db_unhealthy_blocks_is_db_available():
    """mark_db_unhealthy 호출 후 is_db_available이 False를 반환한다."""
    import app.database as db_mod

    original_engine = db_mod._engine
    original_until = db_mod._db_unhealthy_until
    try:
        db_mod._engine = MagicMock()  # 엔진은 존재한다고 가정
        db_mod._db_unhealthy_until = 0.0  # 건강 상태 초기화

        assert db_mod.is_db_available() is True

        db_mod.mark_db_unhealthy(seconds=30)
        assert db_mod.is_db_available() is False
    finally:
        db_mod._engine = original_engine
        db_mod._db_unhealthy_until = original_until


def test_circuit_breaker_recovers_after_timeout():
    """circuit breaker 만료 후 is_db_available이 다시 True를 반환한다."""
    import time

    import app.database as db_mod

    original_engine = db_mod._engine
    original_until = db_mod._db_unhealthy_until
    try:
        db_mod._engine = MagicMock()
        db_mod._db_unhealthy_until = 0.0

        # 이미 만료된 시점으로 설정
        db_mod._db_unhealthy_until = time.time() - 1.0
        assert db_mod.is_db_available() is True
    finally:
        db_mod._engine = original_engine
        db_mod._db_unhealthy_until = original_until


def test_is_db_available_false_when_engine_none():
    """엔진이 없으면 circuit breaker 상태와 무관하게 False."""
    import app.database as db_mod

    original_engine = db_mod._engine
    original_until = db_mod._db_unhealthy_until
    try:
        db_mod._engine = None
        db_mod._db_unhealthy_until = 0.0
        assert db_mod.is_db_available() is False
    finally:
        db_mod._engine = original_engine
        db_mod._db_unhealthy_until = original_until


def test_init_db_passes_timeout_options():
    """init_db가 create_async_engine에 connect_timeout/pool_timeout/pool_recycle을 전달한다."""
    captured_kwargs: dict = {}

    def fake_engine(url, **kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    with patch("app.database.create_async_engine", side_effect=fake_engine), patch("app.database.async_sessionmaker"):
        import app.database as db_mod

        original_engine = db_mod._engine
        original_factory = db_mod._session_factory
        try:
            db_mod.init_db("mysql+aiomysql://u:p@localhost/db")
        finally:
            db_mod._engine = original_engine
            db_mod._session_factory = original_factory

    assert captured_kwargs.get("pool_timeout") == 10
    assert captured_kwargs.get("pool_recycle") == 1800
    assert captured_kwargs.get("connect_args", {}).get("connect_timeout") == 10


def test_init_db_uses_custom_timeouts():
    """init_db에 명시적으로 전달한 timeout 값이 엔진에 그대로 반영된다."""
    captured_kwargs: dict = {}

    def fake_engine(url, **kwargs):
        captured_kwargs.update(kwargs)
        return MagicMock()

    with patch("app.database.create_async_engine", side_effect=fake_engine), patch("app.database.async_sessionmaker"):
        import app.database as db_mod

        original_engine = db_mod._engine
        original_factory = db_mod._session_factory
        try:
            db_mod.init_db(
                "mysql+aiomysql://u:p@localhost/db",
                connect_timeout=20,
                pool_timeout=30,
            )
        finally:
            db_mod._engine = original_engine
            db_mod._session_factory = original_factory

    assert captured_kwargs.get("pool_timeout") == 30
    assert captured_kwargs.get("connect_args", {}).get("connect_timeout") == 20


def test_mark_db_unhealthy_uses_init_db_default():
    """seconds 미지정 시 init_db에서 설정한 unhealthy_seconds를 기본값으로 사용한다."""
    import time

    import app.database as db_mod

    original_engine = db_mod._engine
    original_until = db_mod._db_unhealthy_until
    original_default = db_mod._default_unhealthy_seconds
    try:
        db_mod._engine = MagicMock()
        db_mod._db_unhealthy_until = 0.0
        db_mod._default_unhealthy_seconds = 7

        before = time.time()
        db_mod.mark_db_unhealthy()  # 인자 없이 호출
        elapsed = db_mod._db_unhealthy_until - before
        assert 6.5 <= elapsed <= 7.5
    finally:
        db_mod._engine = original_engine
        db_mod._db_unhealthy_until = original_until
        db_mod._default_unhealthy_seconds = original_default


def test_init_db_noop_on_empty_url():
    """url이 비어있으면 엔진이 초기화되지 않는다."""
    import app.database as db_mod

    original_engine = db_mod._engine
    try:
        db_mod._engine = None
        db_mod.init_db("")
        assert db_mod._engine is None
    finally:
        db_mod._engine = original_engine
