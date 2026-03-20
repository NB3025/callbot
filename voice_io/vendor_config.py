from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class VendorConfig:
    """STT/TTS 벤더 연결 설정.

    VoiceIOConfig(임계값/타임아웃)와 별도로 벤더 연결 정보만 관리한다.
    AWS 벤더는 IAM 자격 증명으로 인증하므로 API 키 필드가 불필요하다.
    """
    stt_vendor: str                          # "aws-transcribe"
    tts_vendor: str                          # "aws-polly"
    aws_region: str = "ap-northeast-2"       # 서울 리전 (기본)
    tts_voice_id: str = "Seoyeon"            # 한국어 Neural 음성
    tts_engine: str = "neural"               # "neural" | "standard"
    tts_output_format: str = "pcm"           # "pcm" | "mp3" | "ogg_vorbis"
    tts_sample_rate: str = "16000"           # 전화 품질: 16kHz (str for Polly API)
    stt_language_code: str = "ko-KR"         # 한국어
    stt_media_encoding: str = "pcm"          # PCM 16-bit LE
    stt_sample_rate: int = 16000             # 16kHz 권장 (int for Transcribe SDK)

    stt_fallback_vendor: Optional[str] = None
    tts_fallback_vendor: Optional[str] = None

    @classmethod
    def from_env(cls) -> VendorConfig:
        """환경변수에서 설정을 로드한다.

        환경변수:
        - CALLBOT_STT_VENDOR (기본: aws-transcribe)
        - CALLBOT_TTS_VENDOR (기본: aws-polly)
        - CALLBOT_AWS_REGION (기본: ap-northeast-2)
        - CALLBOT_TTS_VOICE_ID (기본: Seoyeon)
        - CALLBOT_TTS_ENGINE (기본: neural)
        - CALLBOT_TTS_OUTPUT_FORMAT (기본: pcm)
        - CALLBOT_TTS_SAMPLE_RATE (기본: 16000)
        - CALLBOT_STT_LANGUAGE_CODE (기본: ko-KR)
        - CALLBOT_STT_MEDIA_ENCODING (기본: pcm)
        - CALLBOT_STT_SAMPLE_RATE (기본: 16000)
        - CALLBOT_STT_FALLBACK_VENDOR (선택)
        - CALLBOT_TTS_FALLBACK_VENDOR (선택)

        AWS 인증: IAM 자격 증명 (AWS_ACCESS_KEY_ID/AWS_SECRET_ACCESS_KEY 또는 IAM Role)
        """
        return cls(
            stt_vendor=os.environ.get("CALLBOT_STT_VENDOR", "aws-transcribe"),
            tts_vendor=os.environ.get("CALLBOT_TTS_VENDOR", "aws-polly"),
            aws_region=os.environ.get("CALLBOT_AWS_REGION", "ap-northeast-2"),
            tts_voice_id=os.environ.get("CALLBOT_TTS_VOICE_ID", "Seoyeon"),
            tts_engine=os.environ.get("CALLBOT_TTS_ENGINE", "neural"),
            tts_output_format=os.environ.get("CALLBOT_TTS_OUTPUT_FORMAT", "pcm"),
            tts_sample_rate=os.environ.get("CALLBOT_TTS_SAMPLE_RATE", "16000"),
            stt_language_code=os.environ.get("CALLBOT_STT_LANGUAGE_CODE", "ko-KR"),
            stt_media_encoding=os.environ.get("CALLBOT_STT_MEDIA_ENCODING", "pcm"),
            stt_sample_rate=int(os.environ.get("CALLBOT_STT_SAMPLE_RATE", "16000")),
            stt_fallback_vendor=os.environ.get("CALLBOT_STT_FALLBACK_VENDOR"),
            tts_fallback_vendor=os.environ.get("CALLBOT_TTS_FALLBACK_VENDOR"),
        )
