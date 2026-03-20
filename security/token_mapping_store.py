"""Token Mapping Store: Masking_Token ↔ 암호화된 PII 매핑 저장소.

PII 원문을 키로 저장하지 않고 SHA-256 해시를 인덱스로 사용하여,
저장소 자체가 유출되어도 PII가 노출되지 않도록 한다.
"""

from abc import ABC, abstractmethod

from callbot.security.exceptions import TokenNotFoundError


class TokenMappingStoreBase(ABC):
    """Masking_Token ↔ 암호화된 PII 매핑 추상 인터페이스.

    인메모리 구현체를 기본으로 제공하며, 이후 PostgreSQL 구현체로
    교체 가능하도록 생성자 주입 패턴을 지원한다.
    """

    @abstractmethod
    def store_with_pii_hash(self, token: str, ciphertext: bytes, pii_hash: str) -> None:
        """토큰→암호문, PII 해시→토큰 매핑을 저장한다.

        Args:
            token: UUID 형태의 Masking_Token.
            ciphertext: AES-256-GCM으로 암호화된 PII 바이너리.
            pii_hash: PII 원문의 SHA-256 hex digest.
        """

    @abstractmethod
    def get_ciphertext(self, token: str) -> bytes:
        """토큰으로 암호문을 조회한다.

        Args:
            token: UUID 형태의 Masking_Token.

        Returns:
            암호화된 PII 바이너리.

        Raises:
            TokenNotFoundError: 토큰이 존재하지 않을 때.
        """

    @abstractmethod
    def get_token_by_pii_hash(self, pii_hash: str) -> str | None:
        """PII 해시로 기존 토큰을 조회한다 (1:1 매핑).

        Args:
            pii_hash: PII 원문의 SHA-256 hex digest.

        Returns:
            매핑된 토큰 문자열, 없으면 None.
        """


class InMemoryTokenMappingStore(TokenMappingStoreBase):
    """인메모리 기반 Token Mapping Store 구현체."""

    def __init__(self) -> None:
        self._token_to_cipher: dict[str, bytes] = {}
        self._pii_hash_to_token: dict[str, str] = {}

    def store_with_pii_hash(self, token: str, ciphertext: bytes, pii_hash: str) -> None:
        self._token_to_cipher[token] = ciphertext
        self._pii_hash_to_token[pii_hash] = token

    def get_ciphertext(self, token: str) -> bytes:
        try:
            return self._token_to_cipher[token]
        except KeyError:
            raise TokenNotFoundError(f"Token not found: {token}")

    def get_token_by_pii_hash(self, pii_hash: str) -> str | None:
        return self._pii_hash_to_token.get(pii_hash)
