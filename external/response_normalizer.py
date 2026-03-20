"""callbot.external.response_normalizer — API 응답 정규화."""
from __future__ import annotations


class ResponseNormalizer:
    """AnyTelecom API raw 응답을 비즈니스 로직이 기대하는 표준 형식으로 변환.

    정규화는 멱등: ``normalize(normalize(data)) == normalize(data)``
    """

    @staticmethod
    def normalize(system: str, operation: str, raw_data: dict) -> dict:
        """raw API 응답 → 표준 형식 dict."""
        key = (system, operation)
        handler = _HANDLERS.get(key)
        if handler is None:
            raise ValueError(
                f"Unknown normalization target: system={system!r}, operation={operation!r}"
            )
        return handler(raw_data)


# ---------------------------------------------------------------------------
# 오퍼레이션별 정규화 핸들러 (private)
# ---------------------------------------------------------------------------


def _normalize_customer_info(data: dict) -> dict:
    """고객_식별 / 고객_정보_조회 → {"customer_info": {...}}"""
    if "customer_info" in data:
        return data
    return {"customer_info": data}


def _normalize_verify_auth(data: dict) -> dict:
    """인증_검증 → {"verified": bool, "has_password": bool}"""
    if set(data.keys()) == {"verified", "has_password"}:
        return data
    return {
        "verified": data.get("verified", False),
        "has_password": data.get("has_password", False),
    }


def _normalize_charges(data: dict) -> dict:
    """요금_조회 → {"charges": [...]}"""
    if "charges" in data and len(data) == 1:
        return data
    return {"charges": data.get("charges", [])}


def _normalize_payments(data: dict) -> dict:
    """납부_확인 → {"payments": [...]}"""
    if "payments" in data and len(data) == 1:
        return data
    return {"payments": data.get("payments", [])}


def _normalize_plans(data: dict) -> dict:
    """요금제_목록_조회 → {"plans": [...]}"""
    if "plans" in data and len(data) == 1:
        return data
    return {"plans": data.get("plans", [])}


def _normalize_change_plan(data: dict) -> dict:
    """요금제_변경 → {"transaction_id": str, "result": str}"""
    if set(data.keys()) == {"transaction_id", "result"}:
        return data
    return {
        "transaction_id": data.get("transaction_id", ""),
        "result": data.get("result", ""),
    }


def _normalize_rollback(data: dict) -> dict:
    """요금제_변경_롤백 → {"transaction_id": str, "rollback_result": str}"""
    if set(data.keys()) == {"transaction_id", "rollback_result"}:
        return data
    return {
        "transaction_id": data.get("transaction_id", ""),
        "rollback_result": data.get("rollback_result", ""),
    }


_HANDLERS: dict[tuple[str, str], callable] = {
    ("billing", "요금_조회"): _normalize_charges,
    ("billing", "납부_확인"): _normalize_payments,
    ("billing", "요금제_목록_조회"): _normalize_plans,
    ("billing", "요금제_변경"): _normalize_change_plan,
    ("billing", "요금제_변경_롤백"): _normalize_rollback,
    ("customer_db", "고객_식별"): _normalize_customer_info,
    ("customer_db", "인증_검증"): _normalize_verify_auth,
    ("customer_db", "고객_정보_조회"): _normalize_customer_info,
}
