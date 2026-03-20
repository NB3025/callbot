"""mTLS 인증서 제공자 — SecretsManager에서 인증서를 조회하고 임시 파일로 제공."""

from __future__ import annotations

import logging
import os
import tempfile

from callbot.security.secrets_manager import SecretsManager

logger = logging.getLogger(__name__)


class mTLSCertificateProvider:
    """SecretsManager에서 mTLS 클라이언트 인증서/키를 조회하여 임시 파일로 제공.

    context manager 패턴을 지원하며, 종료 시 임시 파일을 안전하게 삭제한다.

    Raises:
        SecretNotFoundError: SecretsManager에서 인증서/키 조회 실패 시
    """

    def __init__(
        self,
        secrets_manager: SecretsManager,
        cert_secret_name: str = "callbot/anytelecom-mtls-cert",
        key_secret_name: str = "callbot/anytelecom-mtls-key",
    ) -> None:
        cert_content = secrets_manager.get_secret(cert_secret_name)
        key_content = secrets_manager.get_secret(key_secret_name)

        self._cert_path = self._write_temp(cert_content)
        self._key_path = self._write_temp(key_content)

    @staticmethod
    def _write_temp(content: str) -> str:
        fd, path = tempfile.mkstemp()
        try:
            os.write(fd, content.encode())
        finally:
            os.close(fd)
        os.chmod(path, 0o600)
        return path

    @property
    def cert_path(self) -> str:
        return self._cert_path

    @property
    def key_path(self) -> str:
        return self._key_path

    def cleanup(self) -> None:
        """임시 파일 안전 삭제. 실패 시 경고 로깅, 예외 전파 안 함."""
        for path in (self._cert_path, self._key_path):
            try:
                os.unlink(path)
            except Exception as exc:
                logger.warning("Failed to delete temp file %s: %s", path, exc)

    def __enter__(self) -> mTLSCertificateProvider:
        return self

    def __exit__(self, *args: object) -> None:
        self.cleanup()

    def __del__(self) -> None:
        if hasattr(self, "_cert_path"):
            self.cleanup()
