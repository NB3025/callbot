"""PII 마스킹 유틸리티 — 로깅 시 개인정보를 마스킹한다."""


class PIIMasker:
    """PII 필드를 '***'로 마스킹한 복사본을 반환한다. 원본 dict는 변경하지 않는다."""

    PII_FIELDS = {
        "phone",
        "birthdate",
        "name",
        "address",
        "account_number",
        "card_number",
        "customer_id",
    }

    @staticmethod
    def mask(data: dict) -> dict:
        """PII 필드를 '***'로 마스킹한 복사본 반환. 원본 불변."""
        result = {}
        for key, value in data.items():
            if key in PIIMasker.PII_FIELDS:
                result[key] = "***"
            elif isinstance(value, dict):
                result[key] = PIIMasker.mask(value)
            else:
                result[key] = value
        return result
