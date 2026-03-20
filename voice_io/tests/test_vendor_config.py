"""VendorConfig 단위 테스트.

Requirements: 3.1, 3.2, 3.3, 5.1
"""
from __future__ import annotations

import os
from unittest.mock import patch

import pytest

from callbot.voice_io.vendor_config import VendorConfig


class TestVendorConfigFields:
    """Requirement 3.1: VendorConfig 필드 존재 및 타입 검증."""

    def test_required_fields_stt_and_tts_vendor(self):
        cfg = VendorConfig(stt_vendor="aws-transcribe", tts_vendor="aws-polly")
        assert cfg.stt_vendor == "aws-transcribe"
        assert cfg.tts_vendor == "aws-polly"

    def test_default_values(self):
        cfg = VendorConfig(stt_vendor="aws-transcribe", tts_vendor="aws-polly")
        assert cfg.aws_region == "ap-northeast-2"
        assert cfg.tts_voice_id == "Seoyeon"
        assert cfg.tts_engine == "neural"
        assert cfg.tts_output_format == "pcm"
        assert cfg.tts_sample_rate == "16000"
        assert cfg.stt_language_code == "ko-KR"
        assert cfg.stt_media_encoding == "pcm"
        assert cfg.stt_sample_rate == 16000

    def test_tts_sample_rate_is_str(self):
        """Polly API가 문자열을 요구하므로 tts_sample_rate는 str 타입."""
        cfg = VendorConfig(stt_vendor="x", tts_vendor="y")
        assert isinstance(cfg.tts_sample_rate, str)

    def test_stt_sample_rate_is_int(self):
        """Transcribe SDK가 정수를 요구하므로 stt_sample_rate는 int 타입."""
        cfg = VendorConfig(stt_vendor="x", tts_vendor="y")
        assert isinstance(cfg.stt_sample_rate, int)

    def test_fallback_vendors_default_none(self):
        """Requirement 5.1: 폴백 벤더 필드는 선택적이며 기본값 None."""
        cfg = VendorConfig(stt_vendor="x", tts_vendor="y")
        assert cfg.stt_fallback_vendor is None
        assert cfg.tts_fallback_vendor is None

    def test_fallback_vendors_can_be_set(self):
        cfg = VendorConfig(
            stt_vendor="x",
            tts_vendor="y",
            stt_fallback_vendor="fallback-stt",
            tts_fallback_vendor="fallback-tts",
        )
        assert cfg.stt_fallback_vendor == "fallback-stt"
        assert cfg.tts_fallback_vendor == "fallback-tts"

    def test_no_api_key_fields(self):
        """Requirement 3.3: AWS IAM 인증이므로 API 키 필드 없음."""
        cfg = VendorConfig(stt_vendor="x", tts_vendor="y")
        assert not hasattr(cfg, "api_key")
        assert not hasattr(cfg, "secret_key")
        assert not hasattr(cfg, "stt_api_key")
        assert not hasattr(cfg, "tts_api_key")


class TestVendorConfigFromEnv:
    """Requirement 3.2: from_env() 환경변수 로드 및 기본값."""

    def test_from_env_defaults_when_no_env_vars(self):
        """환경변수 미설정 시 합리적 기본값 제공."""
        with patch.dict(os.environ, {}, clear=True):
            cfg = VendorConfig.from_env()
        assert cfg.stt_vendor == "aws-transcribe"
        assert cfg.tts_vendor == "aws-polly"
        assert cfg.aws_region == "ap-northeast-2"
        assert cfg.tts_voice_id == "Seoyeon"
        assert cfg.tts_engine == "neural"
        assert cfg.tts_output_format == "pcm"
        assert cfg.tts_sample_rate == "16000"
        assert cfg.stt_language_code == "ko-KR"
        assert cfg.stt_media_encoding == "pcm"
        assert cfg.stt_sample_rate == 16000
        assert cfg.stt_fallback_vendor is None
        assert cfg.tts_fallback_vendor is None

    def test_from_env_reads_all_env_vars(self):
        """모든 환경변수가 올바르게 매핑되는지 검증."""
        env = {
            "CALLBOT_STT_VENDOR": "custom-stt",
            "CALLBOT_TTS_VENDOR": "custom-tts",
            "CALLBOT_AWS_REGION": "us-east-1",
            "CALLBOT_TTS_VOICE_ID": "Jihye",
            "CALLBOT_TTS_ENGINE": "standard",
            "CALLBOT_TTS_OUTPUT_FORMAT": "mp3",
            "CALLBOT_TTS_SAMPLE_RATE": "22050",
            "CALLBOT_STT_LANGUAGE_CODE": "en-US",
            "CALLBOT_STT_MEDIA_ENCODING": "flac",
            "CALLBOT_STT_SAMPLE_RATE": "8000",
            "CALLBOT_STT_FALLBACK_VENDOR": "fallback-stt",
            "CALLBOT_TTS_FALLBACK_VENDOR": "fallback-tts",
        }
        with patch.dict(os.environ, env, clear=True):
            cfg = VendorConfig.from_env()
        assert cfg.stt_vendor == "custom-stt"
        assert cfg.tts_vendor == "custom-tts"
        assert cfg.aws_region == "us-east-1"
        assert cfg.tts_voice_id == "Jihye"
        assert cfg.tts_engine == "standard"
        assert cfg.tts_output_format == "mp3"
        assert cfg.tts_sample_rate == "22050"
        assert cfg.stt_language_code == "en-US"
        assert cfg.stt_media_encoding == "flac"
        assert cfg.stt_sample_rate == 8000
        assert cfg.stt_fallback_vendor == "fallback-stt"
        assert cfg.tts_fallback_vendor == "fallback-tts"

    def test_from_env_stt_sample_rate_converted_to_int(self):
        """stt_sample_rate는 환경변수(str)에서 int로 변환."""
        with patch.dict(os.environ, {"CALLBOT_STT_SAMPLE_RATE": "44100"}, clear=True):
            cfg = VendorConfig.from_env()
        assert cfg.stt_sample_rate == 44100
        assert isinstance(cfg.stt_sample_rate, int)

    def test_from_env_tts_sample_rate_stays_str(self):
        """tts_sample_rate는 환경변수에서 str 그대로 유지."""
        with patch.dict(os.environ, {"CALLBOT_TTS_SAMPLE_RATE": "22050"}, clear=True):
            cfg = VendorConfig.from_env()
        assert cfg.tts_sample_rate == "22050"
        assert isinstance(cfg.tts_sample_rate, str)


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------
from unittest.mock import patch as mock_patch

from hypothesis import given, settings
from hypothesis import strategies as st


# 문자/숫자만 포함하는 텍스트 전략 (환경변수 값으로 안전한 문자열)
_safe_text = st.text(
    min_size=1,
    alphabet=st.characters(whitelist_categories=("L", "N")),
)


class TestVendorConfigFromEnvPBT:
    """Property 9: VendorConfig from_env 환경변수 매핑.

    Validates: Requirements 3.1, 3.2
    """

    # Feature: callbot-voice-io, Property 9: VendorConfig from_env 환경변수 매핑
    @given(
        stt_vendor=_safe_text,
        tts_vendor=_safe_text,
        aws_region=_safe_text,
        tts_voice_id=_safe_text,
        tts_engine=_safe_text,
        tts_output_format=_safe_text,
        tts_sample_rate=_safe_text,
        stt_language_code=_safe_text,
        stt_media_encoding=_safe_text,
        stt_sample_rate=st.integers(min_value=1, max_value=96000),
        stt_fallback_vendor=_safe_text,
        tts_fallback_vendor=_safe_text,
    )
    @settings(max_examples=100)
    def test_from_env_maps_all_env_vars(
        self,
        stt_vendor: str,
        tts_vendor: str,
        aws_region: str,
        tts_voice_id: str,
        tts_engine: str,
        tts_output_format: str,
        tts_sample_rate: str,
        stt_language_code: str,
        stt_media_encoding: str,
        stt_sample_rate: int,
        stt_fallback_vendor: str,
        tts_fallback_vendor: str,
    ) -> None:
        """**Validates: Requirements 3.1, 3.2**

        모든 환경변수를 랜덤 값으로 설정한 뒤 from_env() 결과가
        각 환경변수 값과 정확히 일치하는지 검증한다.
        """
        env = {
            "CALLBOT_STT_VENDOR": stt_vendor,
            "CALLBOT_TTS_VENDOR": tts_vendor,
            "CALLBOT_AWS_REGION": aws_region,
            "CALLBOT_TTS_VOICE_ID": tts_voice_id,
            "CALLBOT_TTS_ENGINE": tts_engine,
            "CALLBOT_TTS_OUTPUT_FORMAT": tts_output_format,
            "CALLBOT_TTS_SAMPLE_RATE": tts_sample_rate,
            "CALLBOT_STT_LANGUAGE_CODE": stt_language_code,
            "CALLBOT_STT_MEDIA_ENCODING": stt_media_encoding,
            "CALLBOT_STT_SAMPLE_RATE": str(stt_sample_rate),
            "CALLBOT_STT_FALLBACK_VENDOR": stt_fallback_vendor,
            "CALLBOT_TTS_FALLBACK_VENDOR": tts_fallback_vendor,
        }

        with mock_patch.dict(os.environ, env, clear=True):
            cfg = VendorConfig.from_env()

        assert cfg.stt_vendor == stt_vendor
        assert cfg.tts_vendor == tts_vendor
        assert cfg.aws_region == aws_region
        assert cfg.tts_voice_id == tts_voice_id
        assert cfg.tts_engine == tts_engine
        assert cfg.tts_output_format == tts_output_format
        assert cfg.tts_sample_rate == tts_sample_rate
        assert cfg.stt_language_code == stt_language_code
        assert cfg.stt_media_encoding == stt_media_encoding
        assert cfg.stt_sample_rate == stt_sample_rate
        assert isinstance(cfg.stt_sample_rate, int)
        assert cfg.stt_fallback_vendor == stt_fallback_vendor
        assert cfg.tts_fallback_vendor == tts_fallback_vendor

    # Feature: callbot-voice-io, Property 9: VendorConfig from_env 환경변수 매핑 (기본값)
    @given(data=st.data())
    @settings(max_examples=100)
    def test_from_env_defaults_when_env_vars_unset(self, data: st.DataObject) -> None:
        """**Validates: Requirements 3.1, 3.2**

        환경변수가 설정되지 않은 경우 from_env()가 기본값을 반환하는지 검증한다.
        """
        with mock_patch.dict(os.environ, {}, clear=True):
            cfg = VendorConfig.from_env()

        assert cfg.stt_vendor == "aws-transcribe"
        assert cfg.tts_vendor == "aws-polly"
        assert cfg.aws_region == "ap-northeast-2"
        assert cfg.tts_voice_id == "Seoyeon"
        assert cfg.tts_engine == "neural"
        assert cfg.tts_output_format == "pcm"
        assert cfg.tts_sample_rate == "16000"
        assert cfg.stt_language_code == "ko-KR"
        assert cfg.stt_media_encoding == "pcm"
        assert cfg.stt_sample_rate == 16000
        assert isinstance(cfg.stt_sample_rate, int)
        assert isinstance(cfg.tts_sample_rate, str)
        assert cfg.stt_fallback_vendor is None
        assert cfg.tts_fallback_vendor is None
