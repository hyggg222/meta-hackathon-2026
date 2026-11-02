# Muse Spark client for rewriting Vietnamese reply texts through guards
import logging
import time
from typing import Any, Optional
import requests

from shrimp.models import Dashboard, TrayResult
from shrimp.reply_text import (
    _remove_diacritics,
    allowed_numbers_for_dashboard,
    allowed_numbers_for_tray,
    dashboard_reply,
    safe_reply,
    template_reply,
)

logger = logging.getLogger(__name__)

ROLE_PROMPT = (
    "Bạn là trợ lý thân thiện cho người nuôi tôm nhỏ, "
    "dùng từ ngữ mộc mạc, dễ hiểu, tối đa 60 từ."
)

RULES_PROMPT = (
    "Quy tắc bắt buộc:\n"
    "- Chỉ dùng các con số xuất hiện trong bản nháp; giữ nguyên chính xác từng số.\n"
    "- Tuyệt đối không khuyên nông dân thu hoạch, bán hay cho ăn nhiều hay ít; "
    "không khuyên bảo hay đưa ra lời khuyên nào.\n"
    "- Giữ nguyên mọi câu cảnh báo.\n"
    "- Giữ nguyên ý nghĩa câu hỏi hoặc hướng dẫn ở cuối: đối với kết quả chưa lưu, "
    'bắt buộc phải nói trả lời "có" để lưu, hoặc gõ số các con tôm ví dụ 1 3 5.'
)


def _normalize_quotes(text: str) -> str:
    # Normalize double and single quotes to ascii double quote
    quotes = ['"', "'", "“", "”", "‘", "’", "«", "»", "＂", "＇", "`"]
    for q in quotes:
        text = text.replace(q, '"')
    return text


def _has_required_phrases(text: str) -> bool:
    # Check if text contains normalized quoted co and example 1 3 5
    norm = _remove_diacritics(text.lower())
    norm = _normalize_quotes(norm)
    return '"co"' in norm and "1 3 5" in norm


def _build_prompt(draft: str) -> str:
    # Build Vietnamese prompt for rewriting draft reply text
    return (
        f"{ROLE_PROMPT}\n\n"
        f"{RULES_PROMPT}\n\n"
        f"Bản nháp:\n{draft}\n\n"
        "Hãy viết lại bản nháp trên cho tự nhiên, mộc mạc. "
        "Chỉ trả lời nội dung đã viết lại, không có dấu ngoặc kép bọc ngoài, không dùng định dạng markdown."
    )


def _extract_text(resp: Any) -> Optional[str]:
    # Extract candidate text from response JSON
    if resp is None or getattr(resp, "status_code", None) != 200:
        return None
    try:
        data = resp.json()
    except Exception:
        return None
    if not isinstance(data, dict) or data.get("error"):
        return None
    outputs = data.get("output")
    if not isinstance(outputs, list):
        return None
    for item in outputs:
        if isinstance(item, dict) and item.get("type") == "message":
            contents = item.get("content")
            if isinstance(contents, list):
                for c in contents:
                    if isinstance(c, dict) and c.get("type") == "output_text":
                        text = c.get("text")
                        if isinstance(text, str):
                            stripped = text.strip()
                            if stripped:
                                return stripped
            return None
    return None


class SparkWriter:
    # Generates rewritten reply texts via Meta Muse Spark with guard validation
    def __init__(
        self,
        api_key: str,
        session: Any = None,
        model: str = "muse-spark-1.3",
        timeout: float = 15.0,
    ):
        # Initialize SparkWriter with API credentials and HTTP session
        self.api_key = api_key
        self.session = session if session is not None else requests.Session()
        self.model = model
        self.timeout = timeout

    def _call_spark(self, prompt: str) -> Optional[str]:
        # Call Meta API with prompt and extract message text
        try:
            url = "https://api.meta.ai/v1/responses"
            headers = {"Authorization": f"Bearer {self.api_key}"}
            payload = {
                "model": self.model,
                "input": [
                    {
                        "role": "user",
                        "content": [{"type": "input_text", "text": prompt}],
                    }
                ],
                "reasoning": {"effort": "minimal"},
                "max_output_tokens": 1500,
            }
            resp = self.session.post(
                url, headers=headers, json=payload, timeout=self.timeout
            )
            return _extract_text(resp)
        except Exception:
            return None

    def write_reply(
        self,
        tray: TrayResult,
        min_measured: int,
        saved: Optional[bool] = None,
    ) -> str:
        # Rewrite tray result reply text with Muse Spark or fallback to template
        start = time.monotonic()
        fallback = ""
        try:
            fallback = template_reply(tray, min_measured, saved)
        except Exception:
            fallback = "Kết quả đo khay tôm."

        candidate: Optional[str] = None
        result = fallback
        try:
            prompt = _build_prompt(fallback)
            candidate = self._call_spark(prompt)
            if candidate is not None:
                if saved is None and tray.status in ("ok", "too_few"):
                    if not _has_required_phrases(candidate):
                        candidate = None
            allowed = allowed_numbers_for_tray(tray, min_measured)
            result = safe_reply(candidate, fallback, allowed)
            if self.api_key and len(self.api_key) >= 4 and self.api_key in result:
                result = fallback
            if self.api_key and len(self.api_key) >= 4 and self.api_key in result:
                result = result.replace(self.api_key, "")
            if not result or not result.strip():
                result = fallback
        except Exception:
            candidate = None
            result = fallback

        if not result or not result.strip():
            result = "Kết quả đo khay tôm."

        elapsed = time.monotonic() - start
        if candidate is not None and result == candidate:
            logger.info("Spark text used in %.3fs", elapsed)
        else:
            logger.info("Fallback text used in %.3fs", elapsed)

        return result

    def write_status(self, dashboard: Dashboard) -> str:
        # Rewrite dashboard status reply text with Muse Spark or fallback to template
        start = time.monotonic()
        fallback = ""
        try:
            fallback = dashboard_reply(dashboard)
        except Exception:
            fallback = "Tình hình ao tôm."

        candidate: Optional[str] = None
        result = fallback
        try:
            prompt = _build_prompt(fallback)
            candidate = self._call_spark(prompt)
            allowed = allowed_numbers_for_dashboard(dashboard)
            result = safe_reply(candidate, fallback, allowed)
            if self.api_key and len(self.api_key) >= 4 and self.api_key in result:
                result = fallback
            if self.api_key and len(self.api_key) >= 4 and self.api_key in result:
                result = result.replace(self.api_key, "")
            if not result or not result.strip():
                result = fallback
        except Exception:
            candidate = None
            result = fallback

        if not result or not result.strip():
            result = "Tình hình ao tôm."

        elapsed = time.monotonic() - start
        if candidate is not None and result == candidate:
            logger.info("Spark text used in %.3fs", elapsed)
        else:
            logger.info("Fallback text used in %.3fs", elapsed)

        return result
