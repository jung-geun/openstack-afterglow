"""Heat smoke-mount 서비스 단위 테스트."""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from app.services.heat import (
    HeatServiceUnavailable,
    HeatStackError,
    create_stack,
    delete_stack,
    render_template,
    wait_for_stack_complete,
)

# ---------------------------------------------------------------------------
# render_template
# ---------------------------------------------------------------------------


def test_render_template_returns_string():
    """builder_smoke.yaml.j2 가 오류 없이 렌더링되어야 한다."""
    result = render_template("builder_smoke.yaml.j2", {})
    assert "heat_template_version" in result
    assert "OS::Nova::Server" in result


# ---------------------------------------------------------------------------
# create_stack
# ---------------------------------------------------------------------------


def _make_conn():
    conn = MagicMock()
    stack = MagicMock()
    stack.id = "stack-abc"
    conn.orchestration.create_stack.return_value = stack
    return conn


class TestCreateStack:
    def test_returns_stack_id(self):
        conn = _make_conn()
        result = create_stack(conn, "my-stack", "template", {"k": "v"})
        assert result == "stack-abc"
        conn.orchestration.create_stack.assert_called_once_with(
            name="my-stack", template="template", parameters={"k": "v"}
        )

    def test_endpoint_error_raises_heat_unavailable(self):
        conn = MagicMock()
        conn.orchestration.create_stack.side_effect = Exception("endpoint not found")
        with pytest.raises(HeatServiceUnavailable):
            create_stack(conn, "s", "t", {})

    def test_generic_error_raises_heat_stack_error(self):
        conn = MagicMock()
        conn.orchestration.create_stack.side_effect = Exception("quota exceeded")
        with pytest.raises(HeatStackError):
            create_stack(conn, "s", "t", {})


# ---------------------------------------------------------------------------
# wait_for_stack_complete
# ---------------------------------------------------------------------------


def _stack_with_status(status: str, outputs: list | None = None) -> MagicMock:
    s = MagicMock()
    s.status = status
    s.outputs = outputs or []
    s.status_reason = ""
    return s


class TestWaitForStackComplete:
    def test_returns_outputs_on_create_complete(self):
        conn = MagicMock()
        conn.orchestration.get_stack.return_value = _stack_with_status(
            "CREATE_COMPLETE",
            [{"output_key": "internal_ip", "output_value": "10.0.0.5"},
             {"output_key": "ssh_host", "output_value": "10.0.0.5"}],
        )
        outputs = wait_for_stack_complete(conn, "stack-1", timeout=10)
        assert outputs["internal_ip"] == "10.0.0.5"

    def test_raises_on_create_failed(self):
        conn = MagicMock()
        stack = _stack_with_status("CREATE_FAILED")
        stack.status_reason = "resource error"
        conn.orchestration.get_stack.return_value = stack
        with pytest.raises(HeatStackError, match="실패"):
            wait_for_stack_complete(conn, "stack-fail", timeout=10)

    def test_raises_on_timeout(self):
        conn = MagicMock()
        conn.orchestration.get_stack.return_value = _stack_with_status("CREATE_IN_PROGRESS")
        with pytest.raises(HeatStackError, match="시간 초과"):
            wait_for_stack_complete(conn, "stack-slow", timeout=1, poll_interval=2)


# ---------------------------------------------------------------------------
# delete_stack
# ---------------------------------------------------------------------------


class TestDeleteStack:
    def test_calls_delete(self):
        conn = MagicMock()
        delete_stack(conn, "stack-del")
        conn.orchestration.delete_stack.assert_called_once_with("stack-del")

    def test_swallows_error(self):
        conn = MagicMock()
        conn.orchestration.delete_stack.side_effect = Exception("already gone")
        delete_stack(conn, "stack-gone")  # 예외 없이 통과
