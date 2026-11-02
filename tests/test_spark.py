# Tests for Muse Spark reply writer
from datetime import date
import logging
from typing import Any, List, Optional
import pytest

from shrimp.models import Dashboard, ShrimpMeasure, TrayResult
from shrimp.reply_text import dashboard_reply, template_reply
from shrimp.spark import SparkWriter


class FakeResponse:
    # Canned HTTP response for fake session
    def __init__(self, status_code: int = 200, json_data: Any = None):
        self.status_code = status_code
        self._json_data = json_data

    def json(self):
        # Return json data or raise exception
        if isinstance(self._json_data, Exception):
            raise self._json_data
        return self._json_data


class FakeSession:
    # Fake requests session recording calls and returning canned responses
    def __init__(self, response: Any = None, side_effect: Any = None):
        self.response = response
        self.side_effect = side_effect
        self.calls: List[dict] = []

    def post(
        self,
        url: str,
        headers: Any = None,
        json: Any = None,
        timeout: Optional[float] = None,
    ):
        # Record post call and return canned response
        self.calls.append({
            "url": url,
            "headers": headers,
            "json": json,
            "timeout": timeout,
        })
        if self.side_effect is not None:
            if isinstance(self.side_effect, Exception):
                raise self.side_effect
            if callable(self.side_effect):
                return self.side_effect(url, headers=headers, json=json, timeout=timeout)
        return self.response


def _make_canned_json(text: str) -> dict:
    # Construct Meta API response structure
    return {
        "status": "completed",
        "output": [
            {
                "type": "reasoning",
                "content": [{"type": "text", "text": "thinking"}],
            },
            {
                "type": "message",
                "content": [{"type": "output_text", "text": text}],
            },
        ],
    }


def _make_sample_tray(
    status: str = "ok",
    n_measured: int = 8,
    n_left_out: int = 2,
    mean_length_mm: float = 91.5,
    size_per_kg: float = 75.0,
) -> TrayResult:
    # Helper to construct a TrayResult for tests
    shrimp = [
        ShrimpMeasure(
            index=i,
            length_px=100.0,
            length_mm=mean_length_mm,
            overlapped=(i >= n_measured),
            path=[],
        )
        for i in range(10)
    ]
    return TrayResult(
        status=status,
        reference="ruler" if status != "no_reference" else "none",
        scale_px_per_mm=10.0 if status != "no_reference" else None,
        shrimp=shrimp if status != "no_shrimp" else [],
        n_measured=n_measured,
        n_left_out=n_left_out,
        mean_length_mm=mean_length_mm,
        size_per_kg=size_per_kg,
        notices=[],
        included=list(range(n_measured)),
    )


def _make_sample_dashboard(
    latest_length_mm: float = 95.2,
    latest_size_per_kg: float = 70.0,
    growth_mm_per_day: float = 0.50,
) -> Dashboard:
    # Helper to construct a Dashboard for tests
    return Dashboard(
        empty=False,
        latest_day=date(2026, 11, 2),
        latest_length_mm=latest_length_mm,
        latest_size_per_kg=latest_size_per_kg,
        n_latest=8,
        change_length_mm=None,
        change_size_per_kg=None,
        n_previous=None,
        days_between=None,
        stall=False,
        at_harvest=False,
        stall_day_cost_vnd=None,
        chart=[],
        rows=[],
        notices=[],
        growth_mm_per_day=growth_mm_per_day,
        stall_threshold_mm_per_day=0.33,
        harvest_threshold_per_kg=50.0,
        min_measured=5,
    )


def test_write_reply_good_spark_text():
    # Return good Spark text and verify API request format
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    good_text = (
        'Đo được 8 con, bỏ ra 2 con. '
        'Dài trung bình 91.5 mm, khoảng 75 con/kg. '
        'Bạn trả lời "có" để lưu mẫu này, hoặc gõ số các con cần tính, ví dụ: 1 3 5.'
    )
    session = FakeSession(response=FakeResponse(200, _make_canned_json(good_text)))
    writer = SparkWriter(api_key="meta-secret-key-123", session=session)

    res = writer.write_reply(tray, 5, None)

    assert res == good_text
    assert len(session.calls) == 1
    call = session.calls[0]
    assert call["url"] == "https://api.meta.ai/v1/responses"
    assert call["headers"] == {"Authorization": "Bearer meta-secret-key-123"}
    assert call["timeout"] == 15.0
    body = call["json"]
    assert body["model"] == "muse-spark-1.3"
    assert body["reasoning"] == {"effort": "minimal"}
    assert body["max_output_tokens"] == 1500
    prompt = body["input"][0]["content"][0]["text"]
    assert fallback in prompt
    assert "không khuyên" in prompt


@pytest.mark.parametrize(
    "bad_spark_text",
    [
        (
            # Wrong number (91.4 instead of 91.5)
            'Đo được 8 con, bỏ ra 2 con. Dài trung bình 91.4 mm, khoảng 75 con/kg. '
            'Trả lời "có" để lưu mẫu này, ví dụ: 1 3 5.'
        ),
        (
            # Forbidden phrase
            'Đo được 8 con, bỏ ra 2 con. Dài 91.5 mm. Bác nên thu hoạch sớm. '
            'Trả lời "có" để lưu, ví dụ: 1 3 5.'
        ),
        (
            # Lacks "co" instruction for unsaved result
            'Đo được 8 con, bỏ ra 2 con. Dài trung bình 91.5 mm, khoảng 75 con/kg. '
            'Gõ số các con cần tính, ví dụ: 1 3 5.'
        ),
        (
            # Lacks "1 3 5" example for unsaved result
            'Đo được 8 con, bỏ ra 2 con. Dài trung bình 91.5 mm, khoảng 75 con/kg. '
            'Trả lời "có" để lưu mẫu này.'
        ),
    ],
)
def test_write_reply_guard_fallbacks(bad_spark_text: str):
    # Fall back to template when Spark text fails guard rules
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    session = FakeSession(response=FakeResponse(200, _make_canned_json(bad_spark_text)))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, None)
    assert res == fallback


def test_write_reply_http_error_fallback():
    # Fall back to template on HTTP 500
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    session = FakeSession(response=FakeResponse(500, _make_canned_json("error")))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, None)
    assert res == fallback


def test_write_reply_no_message_fallback():
    # Fall back to template when response has no message item
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    no_message_json = {
        "status": "completed",
        "output": [{"type": "reasoning", "content": []}],
    }
    session = FakeSession(response=FakeResponse(200, no_message_json))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, None)
    assert res == fallback


def test_write_reply_timeout_fallback():
    # Fall back to template when request times out
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    session = FakeSession(side_effect=TimeoutError("Request timed out"))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, None)
    assert res == fallback


def test_write_reply_empty_text_fallback():
    # Fall back to template when Spark returns empty or whitespace text
    tray = _make_sample_tray()
    fallback = template_reply(tray, 5, None)
    session = FakeSession(response=FakeResponse(200, _make_canned_json("   ")))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, None)
    assert res == fallback


def test_write_reply_saved_true_no_co_requirement():
    # Do not require "co" or "1 3 5" when result is already saved
    tray = _make_sample_tray()
    spark_text = (
        "Đo được 8 con, bỏ ra 2 con. Dài trung bình 91.5 mm, khoảng 75 con/kg. Đã lưu mẫu."
    )
    session = FakeSession(response=FakeResponse(200, _make_canned_json(spark_text)))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_reply(tray, 5, saved=True)
    assert res == spark_text


def test_write_status_good_and_fallback():
    # Return Spark text on valid status, fall back on invalid status text
    dashboard = _make_sample_dashboard()
    fallback = dashboard_reply(dashboard)
    good_text = (
        "Mẫu gần nhất 02/11: dài 95.2 mm, khoảng 70 con/kg. "
        "Tăng trưởng không chậm: 0.50 mm mỗi ngày."
    )
    session = FakeSession(response=FakeResponse(200, _make_canned_json(good_text)))
    writer = SparkWriter(api_key="k", session=session)

    res = writer.write_status(dashboard)
    assert res == good_text

    # Bad text with wrong number falls back
    bad_text = good_text.replace("95.2", "99.9")
    session_bad = FakeSession(response=FakeResponse(200, _make_canned_json(bad_text)))
    writer_bad = SparkWriter(api_key="k", session=session_bad)
    res_bad = writer_bad.write_status(dashboard)
    assert res_bad == fallback


def test_api_key_never_logged_or_returned(caplog):
    # Verify API key never appears in log records or returned string
    secret_key = "super_secret_meta_api_key_xyz987"
    tray = _make_sample_tray()
    dashboard = _make_sample_dashboard()
    leaky_text = f"Đo được 8 con {secret_key}"
    session = FakeSession(response=FakeResponse(200, _make_canned_json(leaky_text)))
    writer = SparkWriter(api_key=secret_key, session=session)

    with caplog.at_level(logging.INFO):
        res1 = writer.write_reply(tray, 5, None)
        res2 = writer.write_status(dashboard)

    assert secret_key not in res1
    assert secret_key not in res2
    assert secret_key not in caplog.text


def test_neither_method_raises_on_exception():
    # Never raise even when session post raises an arbitrary Exception
    tray = _make_sample_tray()
    dashboard = _make_sample_dashboard()
    session = FakeSession(side_effect=Exception("Catastrophic connection failure"))
    writer = SparkWriter(api_key="k", session=session)

    res1 = writer.write_reply(tray, 5, None)
    res2 = writer.write_status(dashboard)

    assert res1 == template_reply(tray, 5, None)
    assert res2 == dashboard_reply(dashboard)


def test_log_one_info_line_per_call(caplog):
    # Log exactly one INFO line per call with elapsed time and usage
    tray = _make_sample_tray()
    good_text = (
        'Đo được 8 con, bỏ ra 2 con. '
        'Dài trung bình 91.5 mm, khoảng 75 con/kg. '
        'Bạn trả lời "có" để lưu mẫu này, hoặc gõ số các con cần tính, ví dụ: 1 3 5.'
    )
    session = FakeSession(response=FakeResponse(200, _make_canned_json(good_text)))
    writer = SparkWriter(api_key="k", session=session)

    with caplog.at_level(logging.INFO):
        writer.write_reply(tray, 5, None)

    records = [r for r in caplog.records if r.name == "shrimp.spark"]
    assert len(records) == 1
    assert records[0].levelno == logging.INFO
    msg = records[0].getMessage()
    assert "Spark" in msg or "spark" in msg
    assert "s" in msg  # elapsed seconds
