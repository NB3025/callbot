"""conftest.py — 통합 테스트 fixtures + Hypothesis 커스텀 전략"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime

import pytest
from hypothesis import strategies as st

from callbot.session.enums import AuthStatus, TurnType
from callbot.session.models import PlanListContext, SessionContext, Turn
try:
    from callbot.session.pg_connection import PostgreSQLConnection
except ImportError:
    PostgreSQLConnection = None  # type: ignore[assignment,misc]


# ---------------------------------------------------------------------------
# Hypothesis 커스텀 전략 (테스트 파일 간 공유)
# ---------------------------------------------------------------------------

@st.composite
def plan_list_contexts(draw):
    """유효한 PlanListContext를 생성하는 Hypothesis 전략."""
    return PlanListContext(
        available_plans=draw(st.lists(
            st.fixed_dictionaries({
                "name": st.text(min_size=1, max_size=20),
                "price": st.integers(min_value=0, max_value=200000),
            }),
            max_size=5,
        )),
        current_page=draw(st.integers(min_value=0, max_value=10)),
        page_size=draw(st.integers(min_value=1, max_value=10)),
        current_plan=draw(st.fixed_dictionaries({
            "name": st.text(min_size=1, max_size=20),
        })),
        is_exhausted=draw(st.booleans()),
    )


@st.composite
def turns(draw):
    """유효한 Turn을 생성하는 Hypothesis 전략."""
    return Turn(
        turn_id=draw(st.uuids().map(str)),
        turn_type=draw(st.sampled_from(TurnType)),
        customer_utterance=draw(st.text(min_size=0, max_size=100)),
        bot_response=draw(st.text(min_size=0, max_size=200)),
        intent=draw(st.none() | st.text(max_size=30)),
        entities=draw(st.lists(st.text(max_size=20), max_size=5)),
        stt_confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        intent_confidence=draw(st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        llm_confidence=draw(st.none() | st.floats(min_value=0.0, max_value=1.0, allow_nan=False)),
        verification_status=draw(st.none() | st.text(max_size=20)),
        response_time_ms=draw(st.integers(min_value=0, max_value=10000)),
        is_dtmf_input=draw(st.booleans()),
        is_barge_in=draw(st.booleans()),
        timestamp=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
        )),
    )


@st.composite
def session_contexts(draw):
    """유효한 SessionContext를 생성하는 Hypothesis 전략."""
    return SessionContext(
        session_id=draw(st.uuids().map(str)),
        caller_id=draw(st.text(min_size=1, max_size=20)),
        is_authenticated=draw(st.booleans()),
        customer_info=draw(st.none() | st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.text(max_size=20),
            max_size=3,
        )),
        auth_status=draw(st.sampled_from(AuthStatus)),
        turns=draw(st.lists(turns(), max_size=5)),
        business_turn_count=draw(st.integers(min_value=0, max_value=20)),
        start_time=draw(st.datetimes(
            min_value=datetime(2020, 1, 1),
            max_value=datetime(2030, 12, 31),
        )),
        tts_speed_factor=draw(st.floats(min_value=0.5, max_value=2.0, allow_nan=False)),
        cached_billing_data=draw(st.none() | st.fixed_dictionaries({
            "plan": st.text(min_size=1, max_size=20),
            "amount": st.integers(min_value=0, max_value=200000),
        })),
        injection_detection_count=draw(st.integers(min_value=0, max_value=10)),
        masking_restore_failure_count=draw(st.integers(min_value=0, max_value=10)),
        plan_list_context=draw(st.none() | plan_list_contexts()),
        pending_intent=draw(st.none() | st.text(max_size=30)),
        pending_classification=draw(st.none() | st.dictionaries(
            st.text(min_size=1, max_size=10),
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False),
            max_size=2,
        )),
    )


@pytest.fixture(scope="session")
def pg_dsn() -> str:
    dsn = os.environ.get("CALLBOT_DB_DSN", "postgresql://callbot:callbot@localhost:5432/callbot")
    return dsn


@pytest.fixture(scope="session")
def migrated_db(pg_dsn: str):
    """Alembic upgrade head → 테스트 종료 시 downgrade base."""
    env = {**os.environ, "CALLBOT_DB_DSN": pg_dsn}
    subprocess.run(["uv", "run", "--with", "alembic", "--with", "psycopg2-binary",
                    "alembic", "upgrade", "head"], check=True, env=env)
    yield pg_dsn
    subprocess.run(["uv", "run", "--with", "alembic", "--with", "psycopg2-binary",
                    "alembic", "downgrade", "base"], check=True, env=env)


@pytest.fixture
def pg_connection(migrated_db: str) -> PostgreSQLConnection:
    """통합 테스트용 PostgreSQLConnection."""
    conn = PostgreSQLConnection(dsn=migrated_db, min_connections=1, max_connections=5)
    yield conn
    conn.close()
