"""Tests for BertIntentClassifier.
Feature: callbot-nlu-model
"""
from __future__ import annotations

import math
from unittest.mock import MagicMock

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from callbot.nlu.enums import Intent
from callbot.nlu.intent_classifier import BertIntentClassifier, _RawPrediction


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

NUM_INTENTS = len(list(Intent))
ALL_INTENTS = list(Intent)


def _make_mock_model(logits: list[float]):
    """Return a mock torch model that returns the given logits."""
    import torch

    mock_model = MagicMock()
    logit_tensor = torch.tensor([logits])  # shape [1, N]

    mock_output = MagicMock()
    mock_output.logits = logit_tensor
    mock_model.return_value = mock_output
    return mock_model


def _make_mock_tokenizer():
    """Return a mock tokenizer that returns minimal pt tensors."""
    import torch

    mock_tok = MagicMock()
    mock_tok.return_value = {
        "input_ids": torch.tensor([[1, 2, 3]]),
        "attention_mask": torch.tensor([[1, 1, 1]]),
    }
    return mock_tok


def _make_classifier(logits: list[float]) -> BertIntentClassifier:
    """Build a BertIntentClassifier via from_components with given logits."""
    model = _make_mock_model(logits)
    tokenizer = _make_mock_tokenizer()
    return BertIntentClassifier.from_components(
        model=model,
        tokenizer=tokenizer,
        intent_labels=ALL_INTENTS,
    )


# ---------------------------------------------------------------------------
# Property 1: confidence 범위 불변성
# Feature: callbot-nlu-model, Property 1: confidence 범위 불변성
# Validates: Requirements 1.5, 7.3
# ---------------------------------------------------------------------------

@given(st.text())
@settings(max_examples=100, deadline=None)
def test_confidence_always_in_range(text):
    # Feature: callbot-nlu-model, Property 1: confidence 범위 불변성
    import torch
    logits = [1.0] * NUM_INTENTS
    clf = _make_classifier(logits)
    result = clf.predict(text)
    assert 0.0 <= result.confidence <= 1.0


# ---------------------------------------------------------------------------
# Property 2: intent 타입 불변성
# Feature: callbot-nlu-model, Property 2: intent 타입 불변성
# Validates: Requirements 1.6, 2.2, 7.4
# ---------------------------------------------------------------------------

@given(st.text())
@settings(max_examples=100)
def test_intent_always_valid_enum(text):
    # Feature: callbot-nlu-model, Property 2: intent 타입 불변성
    logits = [1.0] * NUM_INTENTS
    clf = _make_classifier(logits)
    result = clf.predict(text)
    assert isinstance(result.intent, Intent)
    assert result.intent in Intent


# ---------------------------------------------------------------------------
# Property 3: 결정론적 추론
# Feature: callbot-nlu-model, Property 3: 결정론적 추론
# Validates: Requirements 7.1, 7.2
# ---------------------------------------------------------------------------

@given(st.text())
@settings(max_examples=100)
def test_predict_is_deterministic(text):
    # Feature: callbot-nlu-model, Property 3: 결정론적 추론
    logits = [float(i) for i in range(NUM_INTENTS)]
    clf = _make_classifier(logits)
    result1 = clf.predict(text)
    result2 = clf.predict(text)
    assert result1.intent == result2.intent
    assert result1.confidence == result2.confidence
    assert result1.secondary_intents == result2.secondary_intents


# ---------------------------------------------------------------------------
# Property 4: softmax argmax 정확성
# Feature: callbot-nlu-model, Property 4: softmax argmax 정확성
# Validates: Requirements 1.4
# ---------------------------------------------------------------------------

@given(
    st.lists(
        st.floats(min_value=-10.0, max_value=10.0, allow_nan=False, allow_infinity=False),
        min_size=NUM_INTENTS,
        max_size=NUM_INTENTS,
    )
)
@settings(max_examples=100)
def test_softmax_argmax_correctness(logits):
    # Feature: callbot-nlu-model, Property 4: softmax argmax 정확성
    import torch

    clf = _make_classifier(logits)
    result = clf.predict("테스트 텍스트")

    # Compute expected softmax manually
    t = torch.tensor(logits)
    probs = torch.softmax(t, dim=0)
    expected_idx = int(torch.argmax(probs).item())
    expected_confidence = float(probs[expected_idx].item())
    expected_intent = ALL_INTENTS[expected_idx]

    assert result.intent == expected_intent
    assert math.isclose(result.confidence, expected_confidence, rel_tol=1e-5)


# ---------------------------------------------------------------------------
# Property 5: get_model_info() 필수 키 포함
# Feature: callbot-nlu-model, Property 5: get_model_info() 필수 키 포함
# Validates: Requirements 4.1
# ---------------------------------------------------------------------------

@given(st.text(), st.text())
@settings(max_examples=100)
def test_get_model_info_has_required_keys(model_path, model_version):
    # Feature: callbot-nlu-model, Property 5: get_model_info() 필수 키 포함
    import torch
    logits = [1.0] * NUM_INTENTS
    model = _make_mock_model(logits)
    tokenizer = _make_mock_tokenizer()
    clf = BertIntentClassifier.from_components(
        model=model,
        tokenizer=tokenizer,
        intent_labels=ALL_INTENTS,
        model_path=model_path,
        model_version=model_version,
    )
    info = clf.get_model_info()
    assert "model_path" in info
    assert "model_version" in info
    assert "loaded_at" in info
    assert info["model_path"] == model_path
    assert info["model_version"] == model_version


# ---------------------------------------------------------------------------
# Property 6: validate_training_data() 유효한 데이터 수락
# Feature: callbot-nlu-model, Property 6: validate_training_data() 유효한 데이터 수락
# Validates: Requirements 5.1, 5.2, 5.3
# ---------------------------------------------------------------------------

@given(st.integers(min_value=40, max_value=60))
@settings(max_examples=100)
def test_validate_accepts_valid_data(count_per_intent):
    # Feature: callbot-nlu-model, Property 6: validate_training_data() 유효한 데이터 수락
    records = []
    for intent in ALL_INTENTS:
        for i in range(count_per_intent):
            records.append({"text": f"발화 텍스트 {intent.value} {i}", "intent": intent.value})
    assert BertIntentClassifier._validate_data(records) is True


# ---------------------------------------------------------------------------
# Property 7: validate_training_data() 유효하지 않은 intent 거부
# Feature: callbot-nlu-model, Property 7: validate_training_data() 유효하지 않은 intent 거부
# Validates: Requirements 5.3
# ---------------------------------------------------------------------------

_VALID_INTENT_VALUES = {i.value for i in Intent}


@given(st.text().filter(lambda x: x not in _VALID_INTENT_VALUES))
@settings(max_examples=100)
def test_validate_rejects_invalid_intent(invalid_intent):
    # Feature: callbot-nlu-model, Property 7: validate_training_data() 유효하지 않은 intent 거부
    # Build a valid base dataset (40 records per intent) then inject one invalid record
    records = []
    for intent in ALL_INTENTS:
        for i in range(40):
            records.append({"text": f"발화 텍스트 {intent.value} {i}", "intent": intent.value})
    records.append({"text": "잘못된 의도 발화", "intent": invalid_intent})
    assert BertIntentClassifier._validate_data(records) is False


# ---------------------------------------------------------------------------
# Property 8: validate_training_data() 의도별 최소 건수 미달 거부
# Feature: callbot-nlu-model, Property 8: validate_training_data() 의도별 최소 건수 미달 거부
# Validates: Requirements 5.1
# ---------------------------------------------------------------------------

@given(st.integers(min_value=0, max_value=39))
@settings(max_examples=100)
def test_validate_rejects_insufficient_count(insufficient_count):
    # Feature: callbot-nlu-model, Property 8: validate_training_data() 의도별 최소 건수 미달 거부
    # All intents get 40 records except the first one which gets insufficient_count
    records = []
    for idx, intent in enumerate(ALL_INTENTS):
        count = insufficient_count if idx == 0 else 40
        for i in range(count):
            records.append({"text": f"발화 텍스트 {intent.value} {i}", "intent": intent.value})
    assert BertIntentClassifier._validate_data(records) is False


# ---------------------------------------------------------------------------
# Task 9 — 단위 테스트 (예제 기반)
# ---------------------------------------------------------------------------

import timeit
import statistics

from callbot.nlu.intent_classifier import IntentClassifier, MockIntentClassifier, ModelLoadError


# ---------------------------------------------------------------------------
# 9.1 초기화 및 에러 처리 테스트
# ---------------------------------------------------------------------------

def test_model_load_error_on_missing_path():
    """존재하지 않는 경로로 BertIntentClassifier 초기화 시 ModelLoadError 발생 (Req 1.8)."""
    with pytest.raises(ModelLoadError):
        BertIntentClassifier("/nonexistent/path")


def test_empty_string_returns_unclassified():
    """빈 문자열 입력 → UNCLASSIFIED, 0.0, [] 반환 (Req 2.4)."""
    clf = BertIntentClassifier.from_components(
        model=_make_mock_model([1.0] * NUM_INTENTS),
        tokenizer=_make_mock_tokenizer(),
        intent_labels=ALL_INTENTS,
    )
    result = clf.predict("")
    assert result.intent == Intent.UNCLASSIFIED
    assert result.confidence == 0.0
    assert result.secondary_intents == []


def test_model_version_from_model_info_json():
    """from_components(model_version="1.2.3") → get_model_info()["model_version"] == "1.2.3" (Req 4.2)."""
    clf = BertIntentClassifier.from_components(
        model=_make_mock_model([1.0] * NUM_INTENTS),
        tokenizer=_make_mock_tokenizer(),
        intent_labels=ALL_INTENTS,
        model_version="1.2.3",
    )
    assert clf.get_model_info()["model_version"] == "1.2.3"


def test_model_version_unknown_when_no_model_info():
    """from_components(model_version="unknown") → get_model_info()["model_version"] == "unknown" (Req 4.3)."""
    clf = BertIntentClassifier.from_components(
        model=_make_mock_model([1.0] * NUM_INTENTS),
        tokenizer=_make_mock_tokenizer(),
        intent_labels=ALL_INTENTS,
        model_version="unknown",
    )
    assert clf.get_model_info()["model_version"] == "unknown"


# ---------------------------------------------------------------------------
# 9.2 from_env() 및 하위 호환성 테스트
# ---------------------------------------------------------------------------

def test_from_env_returns_bert_classifier_when_path_set(monkeypatch):
    """NLU_MODEL_PATH 설정 시 from_env()가 BertIntentClassifier 생성 시도 → ModelLoadError (Req 6.3)."""
    monkeypatch.setenv("NLU_MODEL_PATH", "/some/path")
    with pytest.raises(ModelLoadError):
        IntentClassifier.from_env()


def test_from_env_returns_mock_when_no_path(monkeypatch):
    """NLU_MODEL_PATH 미설정 시 from_env()가 MockIntentClassifier 사용 (Req 6.4)."""
    monkeypatch.delenv("NLU_MODEL_PATH", raising=False)
    result = IntentClassifier.from_env()
    assert isinstance(result._model, MockIntentClassifier)


def test_mock_classifier_still_works():
    """MockIntentClassifier.predict() 호출 → _RawPrediction 반환 (Req 6.1)."""
    mock_clf = MockIntentClassifier()
    result = mock_clf.predict("요금 조회")
    assert isinstance(result, _RawPrediction)


def test_intent_classifier_default_uses_mock():
    """IntentClassifier(model=None) 기본값 MockIntentClassifier 유지 (Req 6.2)."""
    ic = IntentClassifier(model=None)
    assert isinstance(ic._model, MockIntentClassifier)


# ---------------------------------------------------------------------------
# 9.3 추론 지연시간 벤치마크 테스트
# ---------------------------------------------------------------------------

def test_inference_latency_p95():
    """P95 추론 지연시간 ≤ 300ms 검증 (Req 3.1)."""
    clf = BertIntentClassifier.from_components(
        model=_make_mock_model([1.0] * NUM_INTENTS),
        tokenizer=_make_mock_tokenizer(),
        intent_labels=ALL_INTENTS,
    )
    times = [timeit.timeit(lambda: clf.predict("이번 달 요금이 얼마예요?"), number=1) for _ in range(100)]
    p95 = sorted(times)[94]  # 95th percentile (0-indexed: index 94)
    assert p95 < 0.3  # 300ms


# ---------------------------------------------------------------------------
# 9.4 모델 파라미터 수 테스트
# ---------------------------------------------------------------------------

def test_model_parameter_count():
    """실제 tiny torch 모델 파라미터 수 ≤ 100M 검증 (Req 3.2)."""
    import torch
    import torch.nn as nn

    class TinyModel(nn.Module):
        def __init__(self):
            super().__init__()
            self.linear = nn.Linear(10, 13)

        def forward(self, **kwargs):
            out = MagicMock()
            out.logits = torch.zeros(1, 13)
            return out

    model = TinyModel()
    param_count = sum(p.numel() for p in model.parameters())
    assert param_count <= 100_000_000  # 100M
