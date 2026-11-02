# Tests for Messenger webhook router and Graph transport
import hashlib
import hmac
import json
import threading
from typing import Any, Dict, Iterator, List, Optional
from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

from shrimp.messenger import (
    GraphTransport,
    Incoming,
    MessengerConfig,
    TransportError,
    create_messenger_router,
)


class InlineExecutor:
    # Execute submitted task synchronously
    def submit(self, fn: Any, *args: Any, **kwargs: Any) -> Any:
        return fn(*args, **kwargs)


class FakeResponse:
    # Response double for requests
    def __init__(
        self,
        status_code: int = 200,
        content: bytes = b"",
        headers: Optional[Dict[str, str]] = None,
        text: str = "",
        chunks: Optional[List[bytes]] = None,
    ):
        self.status_code = status_code
        self.content = content
        self.headers = headers or {}
        self.text = text or content.decode("utf-8", errors="replace")
        self._chunks = chunks if chunks is not None else [content]

    def iter_content(self, chunk_size: int = 65536) -> Iterator[bytes]:
        yield from self._chunks

    def close(self) -> None:
        pass


class FakeSession:
    # Session double recording requests and returning canned responses
    def __init__(
        self,
        get_resp: Optional[FakeResponse] = None,
        post_resp: Optional[FakeResponse] = None,
    ):
        self.get_resp = get_resp or FakeResponse()
        self.post_resp = post_resp or FakeResponse()
        self.gets: List[Dict[str, Any]] = []
        self.posts: List[Dict[str, Any]] = []

    def get(self, url: str, **kwargs: Any) -> FakeResponse:
        self.gets.append({"url": url, **kwargs})
        return self.get_resp

    def post(self, url: str, **kwargs: Any) -> FakeResponse:
        self.posts.append({"url": url, **kwargs})
        return self.post_resp


def _sign(body: bytes, secret: str = "secret123") -> str:
    # Compute signature header for test body
    mac = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={mac}"


def _make_client(
    config: Optional[MessengerConfig] = None,
    handler: Optional[Any] = None,
    executor: Optional[Any] = None,
) -> TestClient:
    # Helper to construct test client with messenger router
    cfg = config or MessengerConfig(
        verify_token="verify_tok",
        app_secret="secret123",
        allowed_ids=frozenset({"user1", "user2"}),
    )
    cb = handler or (lambda inc: None)
    ex = executor or InlineExecutor()
    app = FastAPI()
    router = create_messenger_router(cfg, cb, executor=ex)
    app.include_router(router)
    return TestClient(app)


def test_verify_ok():
    # Return challenge on valid subscribe request
    client = _make_client()
    resp = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "verify_tok",
            "hub.challenge": "challenge_code",
        },
    )
    assert resp.status_code == 200
    assert resp.text == "challenge_code"


def test_verify_bad_token():
    # Reject request with incorrect verify token
    client = _make_client()
    resp = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "wrong_tok",
            "hub.challenge": "challenge_code",
        },
    )
    assert resp.status_code == 403


def test_verify_bad_mode():
    # Reject request when hub mode is not subscribe
    client = _make_client()
    resp = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "unsubscribe",
            "hub.verify_token": "verify_tok",
            "hub.challenge": "challenge_code",
        },
    )
    assert resp.status_code == 403


def test_verify_missing_params():
    # Reject request without required query params
    client = _make_client()
    resp = client.get("/webhook/messenger")
    assert resp.status_code == 403


def test_post_text_message():
    # Process valid text message from allowed sender
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {"mid": "mid_1", "text": "hello"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    assert len(received) == 1
    assert received[0].sender_id == "user1"
    assert received[0].mid == "mid_1"
    assert received[0].text == "hello"
    assert received[0].image_urls == []


def test_post_quick_reply_payload():
    # Message carrying quick_reply payload uses that payload as Incoming.text
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {
                            "mid": "mid_qr1",
                            "text": "Lưu mẫu",
                            "quick_reply": {"payload": "có"},
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
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 1
    assert received[0].sender_id == "user1"
    assert received[0].mid == "mid_qr1"
    assert received[0].text == "có"


def test_post_quick_reply_payload_without_text():
    # Message with quick_reply payload but no text field still counts as text message
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {
                            "mid": "mid_qr2",
                            "quick_reply": {"payload": "xem loại"},
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
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 1
    assert received[0].sender_id == "user1"
    assert received[0].text == "xem loại"


def test_post_photo_message():
    # Extract image attachment URLs into Incoming
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {
                            "mid": "mid_2",
                            "text": "shrimp photo",
                            "attachments": [
                                {
                                    "type": "image",
                                    "payload": {"url": "https://cdn.example.com/p1.jpg"},
                                },
                                {
                                    "type": "video",
                                    "payload": {"url": "https://cdn.example.com/v.mp4"},
                                },
                                {
                                    "type": "image",
                                    "payload": {"url": "https://cdn.example.com/p2.jpg"},
                                },
                            ],
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
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 1
    assert received[0].mid == "mid_2"
    assert received[0].text == "shrimp photo"
    assert received[0].image_urls == [
        "https://cdn.example.com/p1.jpg",
        "https://cdn.example.com/p2.jpg",
    ]


def test_post_wrong_signature():
    # Reject request with invalid signature header
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    raw = b'{"object": "page"}'
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": "sha256=0000bad"},
    )
    assert resp.status_code == 403
    assert len(received) == 0


def test_post_missing_signature():
    # Reject request with missing signature header
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    raw = b'{"object": "page"}'
    resp = client.post("/webhook/messenger", content=raw)
    assert resp.status_code == 403
    assert len(received) == 0


def test_post_unauthorized_sender():
    # Ignore messages from sender id not in allowed set
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "stranger"},
                        "message": {"mid": "mid_3", "text": "hi"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 0


def test_post_echo_message_ignored():
    # Ignore bot echo messages
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {"mid": "mid_4", "text": "echo", "is_echo": True},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 0


def test_post_delivery_ignored():
    # Ignore non-message events such as delivery or read
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "delivery": {"mids": ["mid_5"], "watermark": 1234},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 0


def test_post_non_json_body():
    # Return 200 and ignore body that cannot be parsed as JSON
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    raw = b"this is not json"
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 0


def test_post_unknown_object():
    # Return 200 and ignore payload whose object is not page
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    raw = b'{"object": "instagram", "entry": []}'
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert len(received) == 0


def test_post_duplicate_mid():
    # Ignore duplicate mid received in subsequent request
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {"mid": "mid_dup", "text": "dup"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    sig = _sign(raw)
    resp1 = client.post("/webhook/messenger", content=raw, headers={"X-Hub-Signature-256": sig})
    assert resp1.status_code == 200
    resp2 = client.post("/webhook/messenger", content=raw, headers={"X-Hub-Signature-256": sig})
    assert resp2.status_code == 200
    assert len(received) == 1


def test_post_mid_eviction_1001():
    # Evict oldest mid after 1000 items and handle it again
    received: List[Incoming] = []
    client = _make_client(handler=received.append)

    def _post(mid_str: str) -> None:
        p = {
            "object": "page",
            "entry": [
                {
                    "messaging": [
                        {
                            "sender": {"id": "user1"},
                            "message": {"mid": mid_str, "text": "x"},
                        }
                    ]
                }
            ],
        }
        r = json.dumps(p).encode("utf-8")
        client.post("/webhook/messenger", content=r, headers={"X-Hub-Signature-256": _sign(r)})

    _post("mid_0")
    assert len(received) == 1

    for i in range(1, 1001):
        _post(f"mid_{i}")
    assert len(received) == 1001

    _post("mid_0")
    assert len(received) == 1002


def test_post_slow_handler_default_executor():
    # Route returns 200 before slow background handler finishes
    entered = threading.Event()
    release = threading.Event()

    def slow_handler(inc: Incoming) -> None:
        entered.set()
        release.wait(timeout=2.0)

    cfg = MessengerConfig(
        verify_token="verify_tok",
        app_secret="secret123",
        allowed_ids=frozenset({"user1"}),
    )
    app = FastAPI()
    # Use default ThreadPoolExecutor
    router = create_messenger_router(cfg, slow_handler, executor=None)
    app.include_router(router)
    client = TestClient(app)

    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {"mid": "mid_slow", "text": "slow"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200
    assert entered.wait(timeout=1.0)
    release.set()


def test_post_handler_raises():
    # Uncaught exception in handler does not alter 200 response
    def failing_handler(inc: Incoming) -> None:
        raise RuntimeError("database crash")

    client = _make_client(handler=failing_handler)
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user1"},
                        "message": {"mid": "mid_err", "text": "err"},
                    }
                ]
            }
        ],
    }
    raw = json.dumps(payload).encode("utf-8")
    resp = client.post(
        "/webhook/messenger",
        content=raw,
        headers={"X-Hub-Signature-256": _sign(raw)},
    )
    assert resp.status_code == 200


def test_transport_send_text():
    # Send text message to Graph API messages endpoint
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session, version="v21.0")
    transport.send_text("recip1", "hello farmer")

    assert len(session.posts) == 1
    post = session.posts[0]
    assert post["url"] == "https://graph.facebook.com/v21.0/me/messages"
    assert post["params"] == {"access_token": "tok123"}
    assert post["json"] == {
        "recipient": {"id": "recip1"},
        "messaging_type": "RESPONSE",
        "message": {"text": "hello farmer"},
    }


def test_transport_send_text_split():
    # Split text longer than 1900 characters at line break
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    line1 = "A" * 1000
    line2 = "B" * 999
    text = f"{line1}\n{line2}"
    assert len(text) == 2000

    transport.send_text("recip1", text)
    assert len(session.posts) == 2
    assert session.posts[0]["json"]["message"]["text"] == line1
    assert session.posts[1]["json"]["message"]["text"] == line2


def test_transport_send_text_quick_replies():
    # Send text with quick-reply buttons attaches formatted quick_replies
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    buttons = [("Lưu mẫu", "có"), ("Hủy", "hủy")]
    transport.send_text("recip1", "hello", quick_replies=buttons)

    assert len(session.posts) == 1
    post = session.posts[0]
    assert post["json"]["message"] == {
        "text": "hello",
        "quick_replies": [
            {"content_type": "text", "title": "Lưu mẫu", "payload": "có"},
            {"content_type": "text", "title": "Hủy", "payload": "hủy"},
        ],
    }


def test_transport_send_text_quick_replies_split_only_on_last_chunk():
    # Split text attaches quick_replies only to the last chunk
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    line1 = "A" * 1000
    line2 = "B" * 999
    text = f"{line1}\n{line2}"
    buttons = [("Lưu mẫu", "có")]
    transport.send_text("recip1", text, quick_replies=buttons)

    assert len(session.posts) == 2
    assert "quick_replies" not in session.posts[0]["json"]["message"]
    assert session.posts[0]["json"]["message"]["text"] == line1
    assert session.posts[1]["json"]["message"]["quick_replies"] == [
        {"content_type": "text", "title": "Lưu mẫu", "payload": "có"}
    ]
    assert session.posts[1]["json"]["message"]["text"] == line2


def test_transport_send_text_quick_replies_limits():
    # 14 buttons cut to 13 and title cut to 20 characters
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    long_title = "Tiêu đề này dài hơn hai mươi ký tự"
    assert len(long_title) > 20
    buttons = [(f"{long_title} {i}", f"payload_{i}") for i in range(14)]
    transport.send_text("recip1", "choose", quick_replies=buttons)

    assert len(session.posts) == 1
    qrs = session.posts[0]["json"]["message"]["quick_replies"]
    assert len(qrs) == 13
    for qr in qrs:
        assert len(qr["title"]) <= 20
        assert qr["content_type"] == "text"


def test_transport_send_text_no_buttons_matches_today():
    # When quick_replies is None or empty no quick_replies field is present
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    transport.send_text("recip1", "hello", quick_replies=None)
    assert "quick_replies" not in session.posts[0]["json"]["message"]

    transport.send_text("recip1", "hello", quick_replies=[])
    assert "quick_replies" not in session.posts[1]["json"]["message"]


def test_transport_send_image():
    # Send image via multipart form upload to Graph API
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    jpeg_data = b"\xff\xd8\xff\xe0fakejpeg"
    transport.send_image("recip1", jpeg_data)

    assert len(session.posts) == 1
    post = session.posts[0]
    assert post["url"] == "https://graph.facebook.com/v21.0/me/messages"
    assert post["params"] == {"access_token": "tok123"}
    assert post["data"]["recipient"] == json.dumps({"id": "recip1"})
    assert post["data"]["message"] == json.dumps(
        {"attachment": {"type": "image", "payload": {"is_reusable": False}}}
    )
    assert post["files"]["filedata"] == ("reply.jpg", jpeg_data, "image/jpeg")


def test_transport_download_ok():
    # Download binary content over http/https
    session = FakeSession(get_resp=FakeResponse(status_code=200, content=b"shrimp_data"))
    transport = GraphTransport(page_token="tok123", session=session)
    data = transport.download("https://example.com/photo.jpg")

    assert data == b"shrimp_data"
    assert len(session.gets) == 1
    assert session.gets[0]["url"] == "https://example.com/photo.jpg"
    assert session.gets[0]["stream"] is True
    assert session.gets[0]["timeout"] == 20


def test_transport_download_rejects_scheme():
    # Reject non-http/https URL schemes
    session = FakeSession()
    transport = GraphTransport(page_token="tok123", session=session)
    with pytest.raises(TransportError):
        transport.download("file:///etc/passwd")


def test_transport_download_rejects_large_content_length():
    # Refuse download when Content-Length header exceeds 15 MB
    over_limit = 16 * 1024 * 1024
    session = FakeSession(
        get_resp=FakeResponse(
            status_code=200,
            headers={"Content-Length": str(over_limit)},
        )
    )
    transport = GraphTransport(page_token="tok123", session=session)
    with pytest.raises(TransportError):
        transport.download("https://example.com/huge.jpg")


def test_transport_download_rejects_large_stream():
    # Refuse download when stream content exceeds 15 MB
    chunk_1mb = b"x" * (1024 * 1024)
    chunks = [chunk_1mb] * 16
    session = FakeSession(
        get_resp=FakeResponse(
            status_code=200,
            chunks=chunks,
        )
    )
    transport = GraphTransport(page_token="tok123", session=session)
    with pytest.raises(TransportError):
        transport.download("https://example.com/huge_stream.jpg")


def test_transport_download_non_2xx():
    # Raise TransportError on non-2xx status code
    session = FakeSession(get_resp=FakeResponse(status_code=404, text="Not Found"))
    transport = GraphTransport(page_token="tok123", session=session)
    with pytest.raises(TransportError):
        transport.download("https://example.com/missing.jpg")


def test_transport_strips_token():
    # Redact page token from error messages
    session = FakeSession(
        post_resp=FakeResponse(
            status_code=401,
            text='{"error": "bad token secret_page_token_abc"}',
        )
    )
    transport = GraphTransport(page_token="secret_page_token_abc", session=session)
    with pytest.raises(TransportError) as excinfo:
        transport.send_text("recip1", "hello")
    assert "secret_page_token_abc" not in str(excinfo.value)


def test_verify_non_ascii_token_is_403_not_500():
    # A non-ASCII verify token must be rejected, never crash the route
    client = _make_client()
    resp = client.get(
        "/webhook/messenger",
        params={
            "hub.mode": "subscribe",
            "hub.verify_token": "tồm",
            "hub.challenge": "c",
        },
    )
    assert resp.status_code == 403


def test_post_non_ascii_signature_is_403_not_500():
    # A signature header with non-ASCII characters must be rejected, never crash the route
    client = _make_client()
    resp = client.post(
        "/webhook/messenger",
        content=b"{}",
        headers={"X-Hub-Signature-256": b"sha256=\xe0\xe1"},
    )
    assert resp.status_code == 403


@pytest.mark.parametrize("verify_token,app_secret", [("", "secret"), ("tok", ""), ("", "")])
def test_empty_secret_or_token_is_refused(verify_token, app_secret):
    # An empty app secret would make the signature forgeable, so the router refuses to start
    cfg = MessengerConfig(
        verify_token=verify_token, app_secret=app_secret, allowed_ids=frozenset({"u"})
    )
    with pytest.raises(ValueError):
        create_messenger_router(cfg, lambda inc: None, executor=InlineExecutor())


def _post_message(client, sender, message):
    # Post one signed webhook event holding a single message
    body = json.dumps(
        {"object": "page", "entry": [{"messaging": [{"sender": {"id": sender}, "message": message}]}]}
    ).encode()
    return client.post(
        "/webhook/messenger", content=body, headers={"X-Hub-Signature-256": _sign(body)}
    )


def test_sticker_is_not_a_photo():
    # Stickers arrive as image attachments with a sticker_id and must not count as photos
    seen: List[Incoming] = []
    client = _make_client(handler=seen.append)
    resp = _post_message(
        client,
        "user1",
        {
            "mid": "m-sticker",
            "attachments": [
                {
                    "type": "image",
                    "payload": {"url": "https://x/s.png", "sticker_id": 369239263222822},
                }
            ],
        },
    )
    assert resp.status_code == 200
    assert len(seen) == 1
    assert seen[0].image_urls == []


def test_ignored_sender_is_logged(caplog):
    # The id of a sender not on the allow-list is logged so the owner can add it
    client = _make_client(handler=lambda inc: None)
    with caplog.at_level("INFO", logger="shrimp.messenger"):
        resp = _post_message(client, "stranger99", {"mid": "m1", "text": "hi"})
    assert resp.status_code == 200
    assert any("stranger99" in r.getMessage() for r in caplog.records)
