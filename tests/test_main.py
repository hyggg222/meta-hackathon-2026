# Tests for main application factory and Messenger bot wiring
import hashlib
import hmac
import json
import logging
import sqlite3
import time
from typing import Any, List, Optional, Tuple
import cv2
from fastapi.testclient import TestClient
import numpy as np
import pytest

import shrimp.main
from shrimp.messages import t as message
from shrimp.main import build, read_setting
from tests.conftest import FakeSegmenter

# Suppress httpx request logging to prevent query tokens appearing in test logs
logging.getLogger("httpx").setLevel(logging.WARNING)


class RecordingTransport:
    # Test transport capturing sent messages and downloads
    instances: List["RecordingTransport"] = []

    def __init__(self, page_token: str, **kwargs: Any) -> None:
        self.page_token = page_token
        self.sent_texts: List[Tuple[str, str]] = []
        self.sent_quick_replies: List[Optional[List[Tuple[str, str]]]] = []
        self.sent_images: List[Tuple[str, bytes]] = []
        self.download_bytes: bytes = b""
        RecordingTransport.instances.append(self)

    def send_text(
        self,
        recipient_id: str,
        text: str,
        quick_replies: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        # Record sent text message
        self.sent_texts.append((recipient_id, text))
        self.sent_quick_replies.append(quick_replies)

    def send_image(self, recipient_id: str, jpeg: bytes) -> None:
        # Record sent image attachment
        self.sent_images.append((recipient_id, jpeg))

    def download(self, url: str) -> bytes:
        # Return canned payload for download
        return self.download_bytes


def _sign(body: bytes, secret: str) -> str:
    # Compute HMAC-SHA256 signature header for webhook request
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _wait_until(predicate: Any, timeout: float = 3.0, interval: float = 0.05) -> bool:
    # Poll condition until true or timeout reached
    start = time.time()
    while time.time() - start < timeout:
        if predicate():
            return True
        time.sleep(interval)
    return bool(predicate())


def test_missing_meta_api_key_raises(tmp_path: Any) -> None:
    # Raise RuntimeError when META_API_KEY is missing from environment and .env
    with pytest.raises(RuntimeError, match="META_API_KEY is required"):
        build(root=tmp_path, env={})


def test_setting_reader_priority(tmp_path: Any) -> None:
    # Prefer process environment over .env file and read .env when key missing
    env_file = tmp_path / ".env"
    env_file.write_text(
        'ONLY_DOTENV="from_file"\n'
        'IN_BOTH="file_value"\n'
        'SINGLE_QUOTED=\'single\'\n'
    )
    env = {
        "IN_BOTH": "env_value",
        "ONLY_ENV": "from_env",
    }
    assert read_setting("ONLY_DOTENV", root=tmp_path, env=env) == "from_file"
    assert read_setting("IN_BOTH", root=tmp_path, env=env) == "env_value"
    assert read_setting("ONLY_ENV", root=tmp_path, env=env) == "from_env"
    assert read_setting("SINGLE_QUOTED", root=tmp_path, env=env) == "single"
    assert read_setting("NON_EXISTENT", root=tmp_path, env=env) is None


def test_dotenv_and_process_env_build(tmp_path: Any) -> None:
    # Read .env when setting missing and prefer process environment when present
    env_file = tmp_path / ".env"
    env_file.write_text(
        'META_API_KEY="dotenv_key"\n'
        'MESSENGER_PAGE_TOKEN="dotenv_page"\n'
        'MESSENGER_APP_SECRET="dotenv_sec"\n'
        'MESSENGER_VERIFY_TOKEN="dotenv_tok"\n'
    )
    segmenter = FakeSegmenter()

    # Case 1: env mapping lacks MESSENGER_VERIFY_TOKEN; falls back to .env
    env1 = {
        "META_API_KEY": "dotenv_key",
        "MESSENGER_PAGE_TOKEN": "dotenv_page",
        "MESSENGER_APP_SECRET": "dotenv_sec",
    }
    app1 = build(root=tmp_path, env=env1, segmenter=segmenter)
    client1 = TestClient(app1)
    resp1 = client1.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "dotenv_tok",
            "hub.challenge": "ch1",
        },
    )
    assert resp1.status_code == 200
    assert resp1.text == "ch1"

    # Case 2: env mapping has MESSENGER_VERIFY_TOKEN; process env wins over .env
    env2 = {
        "META_API_KEY": "dotenv_key",
        "MESSENGER_PAGE_TOKEN": "dotenv_page",
        "MESSENGER_APP_SECRET": "dotenv_sec",
        "MESSENGER_VERIFY_TOKEN": "override_tok",
    }
    app2 = build(root=tmp_path, env=env2, segmenter=segmenter)
    client2 = TestClient(app2)
    resp2 = client2.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "override_tok",
            "hub.challenge": "ch2",
        },
    )
    assert resp2.status_code == 200
    assert resp2.text == "ch2"

    resp3 = client2.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "dotenv_tok",
            "hub.challenge": "ch2",
        },
    )
    assert resp3.status_code == 403


def test_messenger_disabled_without_settings(
    tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    # Ensure webhook is 404 and dashboard is 200 when messenger settings absent
    caplog.set_level(logging.INFO)
    segmenter = FakeSegmenter()
    env = {"META_API_KEY": "test_api_key"}

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    client = TestClient(app)

    resp_webhook = client.get("/webhook/messenger")
    assert resp_webhook.status_code == 404

    resp_dashboard = client.get("/api/dashboard")
    assert resp_dashboard.status_code == 200

    assert "Messenger disabled" in caplog.text


def test_messenger_disabled_with_partial_settings(
    tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    # Require all three messenger settings to enable the router
    caplog.set_level(logging.INFO)
    segmenter = FakeSegmenter()
    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": "tok",
        "MESSENGER_APP_SECRET": "sec",
        # MESSENGER_VERIFY_TOKEN missing
    }

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    client = TestClient(app)

    resp = client.get("/webhook/messenger")
    assert resp.status_code == 404
    assert "Messenger disabled" in caplog.text


def test_messenger_webhook_verification(
    tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    # Verify challenge response and forbidden on mismatch
    caplog.set_level(logging.INFO)
    segmenter = FakeSegmenter()
    secret_verify = "verify_secret_123"
    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": "page_tok_abc",
        "MESSENGER_APP_SECRET": "app_sec_xyz",
        "MESSENGER_VERIFY_TOKEN": secret_verify,
    }

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    client = TestClient(app)

    # Valid challenge
    resp_ok = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": secret_verify,
            "hub.challenge": "abc",
        },
    )
    assert resp_ok.status_code == 200
    assert resp_ok.text == "abc"

    # Invalid token
    resp_bad = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_token",
            "hub.challenge": "abc",
        },
    )
    assert resp_bad.status_code == 403

    assert "Messenger enabled" in caplog.text
    assert secret_verify not in caplog.text
    assert "page_tok_abc" not in caplog.text
    assert "app_sec_xyz" not in caplog.text


def test_allowed_ids_parsing(
    tmp_path: Any, caplog: pytest.LogCaptureFixture
) -> None:
    # Parse comma separated allowed ids dropping blanks
    caplog.set_level(logging.INFO)
    segmenter = FakeSegmenter()
    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": "page_tok",
        "MESSENGER_APP_SECRET": "app_sec",
        "MESSENGER_VERIFY_TOKEN": "verify_tok",
        "MESSENGER_ALLOWED_IDS": "1, 2,,3",
    }

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    assert app is not None
    assert "Messenger enabled (3 allowed ids)" in caplog.text or "3 allowed ids" in caplog.text


def test_signed_post_text_message(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Run conversation on signed text from allowed sender and drop unallowed
    caplog.set_level(logging.INFO)
    RecordingTransport.instances.clear()
    monkeypatch.setattr(shrimp.main, "GraphTransport", RecordingTransport)

    app_secret = "test_secret_999"
    page_token = "secret_page_tok"
    verify_token = "secret_verify_tok"
    segmenter = FakeSegmenter()

    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": page_token,
        "MESSENGER_APP_SECRET": app_secret,
        "MESSENGER_VERIFY_TOKEN": verify_token,
        "MESSENGER_ALLOWED_IDS": "user_allowed, other_allowed",
    }

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    client = TestClient(app)
    transport = RecordingTransport.instances[-1]

    # Message from allowed sender
    allowed_payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user_allowed"},
                        "message": {"mid": "mid_text_1", "text": "hello"},
                    }
                ]
            }
        ],
    }
    raw_allowed = json.dumps(allowed_payload).encode("utf-8")
    resp1 = client.post(
        "/webhook/messenger",
        content=raw_allowed,
        headers={"x-hub-signature-256": _sign(raw_allowed, app_secret)},
    )
    assert resp1.status_code == 200

    assert _wait_until(lambda: len(transport.sent_texts) > 0)
    assert transport.sent_texts[0][0] == "user_allowed"
    assert message("help.text") in transport.sent_texts[0][1]

    # Message from sender not in allow-list
    unallowed_payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user_unknown"},
                        "message": {"mid": "mid_text_2", "text": "hello"},
                    }
                ]
            }
        ],
    }
    raw_unallowed = json.dumps(unallowed_payload).encode("utf-8")
    resp2 = client.post(
        "/webhook/messenger",
        content=raw_unallowed,
        headers={"x-hub-signature-256": _sign(raw_unallowed, app_secret)},
    )
    assert resp2.status_code == 200
    time.sleep(0.2)
    assert len(transport.sent_texts) == 1

    # Ensure secrets never leak in logs
    assert app_secret not in caplog.text
    assert page_token not in caplog.text
    assert verify_token not in caplog.text


def test_signed_post_image_message(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # Process image attachment, render reply and send no_shrimp without saving
    caplog.set_level(logging.INFO)
    RecordingTransport.instances.clear()
    monkeypatch.setattr(shrimp.main, "GraphTransport", RecordingTransport)

    app_secret = "secret_image_post"
    page_token = "page_token_image"
    verify_token = "verify_token_image"
    segmenter = FakeSegmenter({})

    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": page_token,
        "MESSENGER_APP_SECRET": app_secret,
        "MESSENGER_VERIFY_TOKEN": verify_token,
        "MESSENGER_ALLOWED_IDS": "farmer_1",
    }

    app = build(root=tmp_path, env=env, segmenter=segmenter)
    client = TestClient(app)
    transport = RecordingTransport.instances[-1]

    img = np.zeros((80, 80, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".jpg", img)
    transport.download_bytes = enc.tobytes()

    image_payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "farmer_1"},
                        "message": {
                            "mid": "mid_img_100",
                            "attachments": [
                                {
                                    "type": "image",
                                    "payload": {"url": "https://example.com/tray.jpg"},
                                }
                            ],
                        },
                    }
                ]
            }
        ],
    }
    raw = json.dumps(image_payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"x-hub-signature-256": _sign(raw, app_secret)},
    )
    assert resp.status_code == 200

    assert _wait_until(
        lambda: len(transport.sent_images) > 0 and len(transport.sent_texts) > 0
    )
    assert transport.sent_images[0][0] == "farmer_1"
    assert isinstance(transport.sent_images[0][1], bytes)
    assert len(transport.sent_images[0][1]) > 0

    assert transport.sent_texts[0][0] == "farmer_1"
    assert "Không thấy con tôm nào" in transport.sent_texts[0][1]

    # Confirm nothing saved in database
    db_path = tmp_path / "data" / "shrimp.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM samples WHERE demo = 0")
    row = cur.fetchone()
    conn.close()
    assert row[0] == 0

    assert app_secret not in caplog.text
    assert page_token not in caplog.text
    assert verify_token not in caplog.text


def test_app_info_logs_are_visible(tmp_path: Any) -> None:
    # The app's own INFO lines (for example an ignored sender id) must reach the console
    logging.getLogger("shrimp").handlers.clear()
    logging.getLogger("shrimp").setLevel(logging.WARNING)
    build(root=tmp_path, env={"META_API_KEY": "k"}, segmenter=FakeSegmenter())
    shrimp_logger = logging.getLogger("shrimp")
    assert shrimp_logger.isEnabledFor(logging.INFO)
    assert shrimp_logger.handlers


class FakeSparkWriter:
    # Stand-in for SparkWriter so no test calls the network
    instances: List["FakeSparkWriter"] = []

    def __init__(self, api_key: str, **kwargs: Any) -> None:
        self.api_key = api_key
        FakeSparkWriter.instances.append(self)

    def write_reply(self, tray: Any, min_measured: int, saved: Any = None) -> str:
        return "SPARK-REPLY"

    def write_status(self, dashboard: Any) -> str:
        return "SPARK-STATUS"


def _status_message(client: TestClient, app_secret: str, mid: str) -> None:
    # Post a signed "tinh hinh" message from the allowed sender
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {"sender": {"id": "u1"}, "message": {"mid": mid, "text": "tình hình"}}
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"x-hub-signature-256": _sign(raw, app_secret)},
    )
    assert resp.status_code == 200


def _messenger_env(**extra: str) -> dict:
    env = {
        "META_API_KEY": "test_api_key",
        "MESSENGER_PAGE_TOKEN": "page_tok",
        "MESSENGER_APP_SECRET": "app_secret_1",
        "MESSENGER_VERIFY_TOKEN": "verify_tok_1",
        "MESSENGER_ALLOWED_IDS": "u1",
    }
    env.update(extra)
    return env


def test_spark_replies_used_when_enabled(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # SPARK_REPLIES=1 puts Muse Spark in charge of the reply texts, built with the API key
    RecordingTransport.instances.clear()
    FakeSparkWriter.instances.clear()
    monkeypatch.setattr(shrimp.main, "GraphTransport", RecordingTransport)
    monkeypatch.setattr(shrimp.main, "SparkWriter", FakeSparkWriter)

    app = build(root=tmp_path, env=_messenger_env(SPARK_REPLIES="1"), segmenter=FakeSegmenter())
    client = TestClient(app)
    transport = RecordingTransport.instances[-1]

    _status_message(client, "app_secret_1", "m-spark")
    assert _wait_until(lambda: len(transport.sent_texts) > 0)
    assert "SPARK-STATUS" in transport.sent_texts[0][1]
    assert FakeSparkWriter.instances[-1].api_key == "test_api_key"


def test_spark_replies_off_by_default(tmp_path: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    # Without SPARK_REPLIES the fixed templates are used and no Spark writer is built
    RecordingTransport.instances.clear()
    FakeSparkWriter.instances.clear()
    monkeypatch.setattr(shrimp.main, "GraphTransport", RecordingTransport)
    monkeypatch.setattr(shrimp.main, "SparkWriter", FakeSparkWriter)

    app = build(root=tmp_path, env=_messenger_env(), segmenter=FakeSegmenter())
    client = TestClient(app)
    transport = RecordingTransport.instances[-1]

    _status_message(client, "app_secret_1", "m-plain")
    assert _wait_until(lambda: len(transport.sent_texts) > 0)
    assert "SPARK-STATUS" not in transport.sent_texts[0][1]
    assert FakeSparkWriter.instances == []


def test_spark_replies_wires_photo_to_template_and_status_to_spark(
    tmp_path: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    # SPARK_REPLIES=1 wires write_reply to template_reply and write_status to SparkWriter
    RecordingTransport.instances.clear()
    FakeSparkWriter.instances.clear()
    monkeypatch.setattr(shrimp.main, "GraphTransport", RecordingTransport)
    monkeypatch.setattr(shrimp.main, "SparkWriter", FakeSparkWriter)

    app = build(root=tmp_path, env=_messenger_env(SPARK_REPLIES="1"), segmenter=FakeSegmenter())
    client = TestClient(app)
    transport = RecordingTransport.instances[-1]

    # Status uses Spark
    _status_message(client, "app_secret_1", "m-spark-status")
    assert _wait_until(lambda: len(transport.sent_texts) > 0)
    assert "SPARK-STATUS" in transport.sent_texts[0][1]

    # Photo uses template_reply, NOT spark.write_reply
    transport.sent_texts.clear()
    img = np.zeros((80, 80, 3), dtype=np.uint8)
    _, enc = cv2.imencode(".jpg", img)
    transport.download_bytes = enc.tobytes()
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "u1"},
                        "message": {
                            "mid": "m-spark-photo",
                            "attachments": [{"type": "image", "payload": {"url": "https://cdn.example.com/p.jpg"}}],
                        },
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"x-hub-signature-256": _sign(raw, "app_secret_1")},
    )
    assert resp.status_code == 200
    assert _wait_until(lambda: len(transport.sent_texts) > 0)
    assert "SPARK-REPLY" not in transport.sent_texts[0][1]
