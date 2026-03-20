class SecretNotFoundError(Exception):
    """Secrets_Manager에서 시크릿 조회 실패."""


class InvalidTokenError(Exception):
    """JWT 서명 검증 실패 또는 형식 오류."""


class TokenExpiredError(Exception):
    """JWT exp 만료."""


class RevokedTokenError(Exception):
    """Token_Store에서 폐기 확인."""


class DecryptionError(Exception):
    """AES-GCM 인증 태그 검증 실패."""


class TokenNotFoundError(Exception):
    """존재하지 않는 Masking_Token으로 detokenize."""
