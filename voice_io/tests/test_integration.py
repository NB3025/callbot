"""callbot.voice_io.tests.test_integration — 벤더 팩토리 통합 단위 테스트

Requirements: 3.4, 3.5, 4.4, 4.5, 5.4
"""
from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from callbot.voice_io.vendor_config import VendorConfig
from callbot.voice_io.vendor_factory import (
    _STT_VENDORS,
    _TTS_VENDORS,
    create_stt_engine,
    create_tts_engine,
    vendor_lifespan,
)
from callbot.voice_io.stt_vendor_adapter import STTVendorAdapter
from callbot.voice_io.tts_vendor_adapter import TTSVendorAdapter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_config(
    stt_vendor: str = "aws-transcribe",
    tts_vendor: str = "aws-polly",
    stt_fallback_vendor: str | None = None,
    tts_fallback_vendor: str | None = None,
) -> VendorConfig:
    return VendorConfig(
        stt_vendor=stt_vendor,
        tts_vendor=tts_vendor,
        stt_fallback_vendor=stt_fallback_vendor,
        tts_fallback_vendor=tts_fallback_vendor,
    )


def _mock_stt_client() -> MagicMock:
    """STTVendorAdapter용 Mock SDK 클라이언트."""
    client = MagicMock()
    client.health_check.return_value = None
    return client


def _mock_tts_client() -> MagicMock:
    """TTSVendorAdapter용 Mock SDK 클라이언트."""
    client = MagicMock()
    client.describe_voices.return_value = {"Voices": []}
    return client


# ---------------------------------------------------------------------------
# Test: create_stt_engine → STTVendorAdapter 인스턴스 반환 확인
# Requirement 3.4
# ---------------------------------------------------------------------------

class TestCreateSTTEngineIntegration:
    """create_stt_engine이 실제 등록된 aws-transcribe 어댑터를 반환하는지 확인."""

    def test_returns_stt_vendor_adapter_instance(self):
        config = _make_config()
        engine = create_stt_engine(config, client=_mock_stt_client())
        assert isinstance(engine, STTVendorAdapter)

    def test_stt_adapter_registered_in_registry(self):
        assert "aws-transcribe" in _STT_VENDORS
        assert _STT_VENDORS["aws-transcribe"] is STTVendorAdapter


# ---------------------------------------------------------------------------
# Test: create_tts_engine → TTSVendorAdapter 인스턴스 반환 확인
# Requirement 3.5
# ---------------------------------------------------------------------------

class TestCreateTTSEngineIntegration:
    """create_tts_engine이 실제 등록된 aws-polly 어댑터를 반환하는지 확인."""

    def test_returns_tts_vendor_adapter_instance(self):
        config = _make_config()
        engine = create_tts_engine(config, client=_mock_tts_client())
        assert isinstance(engine, TTSVendorAdapter)

    def test_tts_adapter_registered_in_registry(self):
        assert "aws-polly" in _TTS_VENDORS
        assert _TTS_VENDORS["aws-polly"] is TTSVendorAdapter


# ---------------------------------------------------------------------------
# Test: vendor_lifespan — health_check 실패 시 서버 중단
# Requirements 4.4, 4.5
# ---------------------------------------------------------------------------

class TestVendorLifespan:
    """vendor_lifespan 헬퍼의 health_check 실패 → RuntimeError 시나리오."""

    def test_stt_health_check_failure_raises_runtime_error(self, monkeypatch):
        """STT health_check 실패 시 RuntimeError로 서버 시작 중단."""
        mock_stt = _mock_stt_client()
        mock_stt.health_check.side_effect = Exception("connection refused")
        mock_tts = _mock_tts_client()

        monkeypatch.setenv("CALLBOT_STT_VENDOR", "aws-transcribe")
        monkeypatch.setenv("CALLBOT_TTS_VENDOR", "aws-polly")

        # Patch create functions to inject mock clients
        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_stt_engine",
            lambda config, **kw: STTVendorAdapter(config=config, client=mock_stt),
        )
        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_tts_engine",
            lambda config, **kw: TTSVendorAdapter(config=config, client=mock_tts),
        )

        with pytest.raises(RuntimeError, match="STT 벤더.*연결 실패"):
            with vendor_lifespan():
                pass

    def test_tts_health_check_failure_raises_runtime_error(self, monkeypatch):
        """TTS health_check 실패 시 RuntimeError로 서버 시작 중단."""
        mock_stt = _mock_stt_client()
        mock_tts = _mock_tts_client()
        mock_tts.describe_voices.side_effect = Exception("connection refused")

        monkeypatch.setenv("CALLBOT_STT_VENDOR", "aws-transcribe")
        monkeypatch.setenv("CALLBOT_TTS_VENDOR", "aws-polly")

        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_stt_engine",
            lambda config, **kw: STTVendorAdapter(config=config, client=mock_stt),
        )
        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_tts_engine",
            lambda config, **kw: TTSVendorAdapter(config=config, client=mock_tts),
        )

        with pytest.raises(RuntimeError, match="TTS 벤더.*연결 실패"):
            with vendor_lifespan():
                pass

    def test_successful_lifespan_yields_engines(self, monkeypatch):
        """health_check 성공 시 엔진 튜플을 yield하고 finally에서 close 호출."""
        mock_stt = _mock_stt_client()
        mock_tts = _mock_tts_client()

        monkeypatch.setenv("CALLBOT_STT_VENDOR", "aws-transcribe")
        monkeypatch.setenv("CALLBOT_TTS_VENDOR", "aws-polly")

        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_stt_engine",
            lambda config, **kw: STTVendorAdapter(config=config, client=mock_stt),
        )
        monkeypatch.setattr(
            "callbot.voice_io.vendor_factory.create_tts_engine",
            lambda config, **kw: TTSVendorAdapter(config=config, client=mock_tts),
        )

        with vendor_lifespan() as (stt, tts):
            assert isinstance(stt, STTVendorAdapter)
            assert isinstance(tts, TTSVendorAdapter)

        # close가 호출되었는지 확인
        mock_stt.close.assert_called_once()
        mock_tts.close.assert_called_once()


# ---------------------------------------------------------------------------
# Test: 폴백 벤더 설정 시 두 어댑터 모두 초기화 확인
# Requirement 5.4
# ---------------------------------------------------------------------------

class TestFallbackVendorInitialization:
    """폴백 벤더 설정 시 (primary, fallback) 튜플 반환 확인."""

    def test_stt_fallback_returns_both_adapters(self):
        config = _make_config(
            stt_fallback_vendor="aws-transcribe",
        )
        result = create_stt_engine(config, client=_mock_stt_client())
        assert isinstance(result, tuple)
        assert len(result) == 2
        primary, fallback = result
        assert isinstance(primary, STTVendorAdapter)
        assert isinstance(fallback, STTVendorAdapter)

    def test_tts_fallback_returns_both_adapters(self):
        config = _make_config(
            tts_fallback_vendor="aws-polly",
        )
        result = create_tts_engine(config, client=_mock_tts_client())
        assert isinstance(result, tuple)
        assert len(result) == 2
        primary, fallback = result
        assert isinstance(primary, TTSVendorAdapter)
        assert isinstance(fallback, TTSVendorAdapter)
