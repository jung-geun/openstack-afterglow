import importlib.util
from pathlib import Path

_SANITIZER_PATH = (
    Path(__file__).resolve().parents[2] / "deploy/kolla/ansible/roles/afterglow/files/sanitize_operator_config.py"
)
_SPEC = importlib.util.spec_from_file_location("kolla_operator_config_sanitizer", _SANITIZER_PATH)
assert _SPEC and _SPEC.loader
_SANITIZER = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SANITIZER)


def test_sanitizer_removes_multiline_builder_private_key(tmp_path: Path) -> None:
    source = tmp_path / "afterglow.conf"
    destination = tmp_path / "afterglow.operator.conf"
    source.write_text(
        "[app]\n"
        'site_name = "Operator Afterglow"\n'
        "\n"
        "[builder]\n"
        'ssh_user = "builder"\n'
        'ssh_private_key = """\n'
        "not-a-real-private-key\n"
        "still-not-a-real-private-key\n"
        '"""\n'
        "\n"
        "[chat]\n"
        "enabled = true\n"
    )

    _SANITIZER.main(str(source), str(destination))

    sanitized = _SANITIZER.tomllib.loads(destination.read_text())
    assert sanitized["app"]["site_name"] == "Operator Afterglow"
    assert sanitized["builder"]["ssh_user"] == "builder"
    assert "ssh_private_key" not in sanitized["builder"]
    assert sanitized["chat"]["enabled"] is True
    assert destination.stat().st_mode & 0o777 == 0o600
