"""callbot.voice_io.tts_vendor_adapter — Amazon Polly 기반 TTS 벤더 어댑터

TTSEngine 추상 클래스를 상속하고 VendorAdapter 프로토콜을 구현한다.
모든 메서드는 동기 시그니처를 유지한다.

client 파라미터로 boto3 Polly 클라이언트를 주입받아 테스트 시 Mock 객체를 사용할 수 있다.
"""
from __future__ import annotations

import logging
import time
from typing import Any

from callbot.voice_io.enums import NumberType
from callbot.voice_io.exceptions import VendorConnectionError
from callbot.voice_io.models import AudioStream
from callbot.voice_io.tts_engine import (
    TTS_SPEED_DEFAULT,
    TTS_SPEED_MAX,
    TTS_SPEED_MIN,
    TTSEngine,
    format_amount,
    format_date,
    format_ordinal,
    format_phone,
)
from callbot.voice_io.vendor_config import VendorConfig

logger = logging.getLogger(__name__)

_VENDOR_ID = "aws-polly"


class TTSVendorAdapter(TTSEngine):
    """Amazon Polly 기반 TTS 엔진 구현체.

    TTSEngine 추상 클래스를 상속하고 VendorAdapter 프로토콜을 구현한다.
    모든 메서드는 동기 시그니처를 유지한다.

    client 파라미터(duck typing)로 boto3 Polly 클라이언트를 주입받는다.
    프로덕션에서는 boto3.client("polly"), 테스트에서는 Mock 객체를 사용한다.
    """

    def __init__(self, config: VendorConfig, client: Any = None) -> None:
        """Amazon Polly 클라이언트를 초기화한다.

        Args:
            config: 벤더 연결 설정 (aws_region, tts_voice_id, tts_engine 등)
            client: boto3 Polly 클라이언트 주입 (테스트용). None이면 boto3로 생성 시도.

        Raises:
            VendorConnectionError: boto3 클라이언트 생성 실패 시
        """
        self._config = config
        self._vendor = _VENDOR_ID

        if client is not None:
            self._client = client
        else:
            try:
                import boto3

                self._client = boto3.client(
                    "polly",
                    region_name=config.aws_region,
                )
            except Exception as exc:
                raise VendorConnectionError(
                    vendor=self._vendor,
                    original_message=str(exc),
                ) from exc

        # 세션별 속도 팩터 상태 관리
        self._session_speeds: dict[str, float] = {}
        # 세션별 마지막 응답 텍스트 캐시
        self._last_response: dict[str, str] = {}

    # ------------------------------------------------------------------
    # TTSEngine 추상 메서드 구현
    # ------------------------------------------------------------------

    def synthesize(self, text: str, session_id: str) -> AudioStream:
        """boto3 synthesize_speech()를 호출하여 텍스트를 음성으로 변환한다.

        SSML <prosody rate> 태그로 세션별 속도를 적용한다.

        Returns:
            AudioStream: 합성된 오디오 스트림

        Raises:
            VendorConnectionError: Polly SDK 호출 실패 시
        """
        start = time.monotonic()
        try:
            speed = self._session_speeds.get(session_id, TTS_SPEED_DEFAULT)
            rate_pct = int(speed * 100)
            ssml_text = f'<speak><prosody rate="{rate_pct}%">{text}</prosody></speak>'

            response = self._client.synthesize_speech(
                Text=ssml_text,
                TextType="ssml",
                OutputFormat=self._config.tts_output_format,
                VoiceId=self._config.tts_voice_id,
                Engine=self._config.tts_engine,
                SampleRate=self._config.tts_sample_rate,
            )

            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.info(
                "TTS vendor '%s' synthesize completed in %dms",
                self._vendor,
                elapsed_ms,
            )

            # Extract audio data from response
            audio_data = b""
            audio_stream = response.get("AudioStream")
            if audio_stream is not None:
                if hasattr(audio_stream, "read"):
                    audio_data = audio_stream.read()
                elif isinstance(audio_stream, bytes):
                    audio_data = audio_stream

            self._last_response[session_id] = text

            return AudioStream(
                session_id=session_id,
                data=audio_data,
                sample_rate=int(self._config.tts_sample_rate),
                encoding=self._config.tts_output_format,
            )
        except VendorConnectionError:
            raise
        except Exception as exc:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            logger.error(
                "TTS vendor '%s' synthesize failed: %s (type: %s, elapsed: %dms)",
                self._vendor,
                exc,
                type(exc).__name__,
                elapsed_ms,
            )
            raise VendorConnectionError(
                vendor=self._vendor,
                original_message=str(exc),
            ) from exc

    def stop_playback(self, session_id: str) -> None:
        """해당 세션의 리소스를 해제한다."""
        self._session_speeds.pop(session_id, None)
        self._last_response.pop(session_id, None)

    def set_speed(self, session_id: str, speed_factor: float) -> None:
        """세션별 속도 팩터를 설정한다. speed_factor ∈ [0.7, 1.3] 범위 검증.

        Raises:
            ValueError: 범위 밖 speed_factor
        """
        if not (TTS_SPEED_MIN <= speed_factor <= TTS_SPEED_MAX):
            raise ValueError(
                f"speed_factor must be in [{TTS_SPEED_MIN}, {TTS_SPEED_MAX}], "
                f"got {speed_factor}"
            )
        self._session_speeds[session_id] = speed_factor

    def format_number(self, value: str, number_type: NumberType) -> str:
        """숫자를 한국어 자연어로 변환한다. tts_engine.py 공개 헬퍼 함수에 위임한다."""
        if number_type == NumberType.AMOUNT:
            return format_amount(value)
        elif number_type == NumberType.DATE:
            return format_date(value)
        elif number_type == NumberType.PHONE:
            return format_phone(value)
        elif number_type == NumberType.ORDINAL:
            return format_ordinal(value)
        raise ValueError(f"Unknown NumberType: {number_type}")

    def replay_last_response(self, session_id: str) -> AudioStream:
        """직전 synthesize() 응답 텍스트를 동일한 속도 설정으로 재합성한다.

        Raises:
            KeyError: 해당 세션에 직전 응답이 없는 경우
        """
        text = self._last_response[session_id]
        return self.synthesize(text, session_id)

    # ------------------------------------------------------------------
    # VendorAdapter 프로토콜 구현
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """boto3 polly describe_voices() 테스트 요청으로 연결 상태를 확인한다.

        Returns:
            True: 연결 정상, False: 연결 실패
        """
        try:
            self._client.describe_voices(LanguageCode="ko-KR")
            return True
        except Exception:
            return False

    def close(self) -> None:
        """boto3 클라이언트 연결 및 내부 상태를 정리한다."""
        self._session_speeds.clear()
        self._last_response.clear()
        if hasattr(self._client, "close"):
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("Failed to close Polly client: %s", exc)


# 벤더 팩토리에 AWS Polly 어댑터 등록
from callbot.voice_io.vendor_factory import register_tts_vendor
register_tts_vendor("aws-polly", TTSVendorAdapter)
