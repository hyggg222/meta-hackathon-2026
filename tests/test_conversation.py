# Tests for conversation handling
from dataclasses import dataclass, field
import threading
import time
from typing import Any, List, Optional, Tuple
import numpy as np
import pytest

from shrimp.conversation import HELP_TEXT, Conversation
from shrimp.models import Dashboard, SegmentationError, TrayResult
from shrimp.store import Store
from tests.conftest import FakeSegmenter
from tests.test_app import make_test_service
from tests.test_service import FakeTable


@dataclass
class FakeIncoming:
    sender_id: str
    mid: str = "m1"
    text: Optional[str] = None
    image_urls: List[str] = field(default_factory=list)


class FakeTransport:
    def __init__(self, download_bytes: bytes = b"fake_jpeg"):
        self.download_bytes = download_bytes
        self.sent: List[Tuple[str, str, Any]] = []
        self.download_exc: Optional[Exception] = None
        self.download_started: Optional[threading.Event] = None
        self.download_event: Optional[threading.Event] = None

    def send_text(self, recipient_id: str, text: str) -> None:
        self.sent.append(("text", recipient_id, text))

    def send_image(self, recipient_id: str, jpeg: bytes) -> None:
        self.sent.append(("image", recipient_id, jpeg))

    def download(self, url: str) -> bytes:
        if self.download_started is not None:
            self.download_started.set()
        if self.download_event is not None:
            self.download_event.wait(timeout=5)
        if self.download_exc is not None:
            raise self.download_exc
        return self.download_bytes


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def fake_render(photo: bytes, tray: TrayResult) -> bytes:
    return b"RENDERED_JPEG"


def fake_write_reply(tray: TrayResult, min_measured: int, saved: Optional[bool]) -> str:
    return f"REPLY:{tray.status}:n={tray.n_measured}:min={min_measured}:saved={saved}"


def fake_write_status(dashboard: Dashboard) -> str:
    return f"STATUS:empty={dashboard.empty}"


def make_ok_segmenter():
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = [np.zeros((300, 300), bool) for _ in range(6)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True
    return FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})


def make_too_few_segmenter():
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = [np.zeros((300, 300), bool) for _ in range(2)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True
    return FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})


def make_no_shrimp_segmenter():
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    return FakeSegmenter({"ruler": [ruler], "shrimp": []})


def make_no_reference_segmenter():
    shrimp = [np.zeros((300, 300), bool) for _ in range(5)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True
    return FakeSegmenter({"ruler": [], "credit card": [], "shrimp": shrimp})


def test_photo_ok_flow():
    # Photo sends image then text, does not save to store, keeps pending
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    clock = FakeClock()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        clock=clock,
    )

    incoming = FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"])
    convo.handle(incoming)

    assert len(transport.sent) == 2
    assert transport.sent[0] == ("image", "u1", b"RENDERED_JPEG")
    assert transport.sent[1][0] == "text"
    assert transport.sent[1][1] == "u1"
    assert "REPLY:ok:n=6:min=5:saved=None" in transport.sent[1][2]
    assert len(store.samples()) == 0

    # Sending yes verifies pending entry exists and saves
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert len(store.samples()) == 1


def test_photo_no_shrimp_and_no_reference_do_not_keep_pending():
    # no_shrimp and no_reference send both photo and text but keep no pending entry
    for seg in (make_no_shrimp_segmenter(), make_no_reference_segmenter()):
        store = Store(":memory:")
        service = make_test_service(seg=seg, store=store, table=FakeTable())
        transport = FakeTransport()
        convo = Conversation(
            service=service,
            transport=transport,
            render=fake_render,
            write_reply=fake_write_reply,
            write_status=fake_write_status,
        )

        convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
        assert len(transport.sent) == 2
        assert transport.sent[0][0] == "image"
        assert transport.sent[1][0] == "text"

        # Subsequent yes says to send photo first because no pending entry
        transport.sent.clear()
        convo.handle(FakeIncoming(sender_id="u1", text="có"))
        assert len(transport.sent) == 1
        assert transport.sent[0] == (
            "text",
            "u1",
            'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
        )
        assert len(store.samples()) == 0


def test_photo_segmentation_error_and_download_failure():
    # SegmentationError and download failure send Vietnamese apology and do not raise
    store = Store(":memory:")
    seg_err = FakeSegmenter(exc=SegmentationError("SAM failure"))
    service = make_test_service(seg=seg_err, store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    # SegmentationError
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    assert len(transport.sent) == 1
    assert transport.sent[0] == ("text", "u1", "Chưa xử lý được ảnh này. Bạn chụp lại giúp mình nhé.")

    # Download failure
    transport.sent.clear()
    transport.download_exc = ConnectionError("network drop")
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    assert len(transport.sent) == 1
    assert transport.sent[0] == ("text", "u1", "Chưa tải được ảnh. Bạn gửi lại giúp mình nhé.")


def test_yes_with_ok_pending():
    # Yes with ok pending saves one sample, writes saved=True, and drops entry
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    convo.handle(FakeIncoming(sender_id="u1", text="Có"))
    assert len(transport.sent) == 1
    assert transport.sent[0] == ("text", "u1", "REPLY:ok:n=6:min=5:saved=True")
    assert len(store.samples()) == 1

    # Following yes finds no pending entry
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="Có"))
    assert transport.sent[0] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )


def test_yes_with_too_few_pending():
    # Yes with too_few saves nothing, writes saved=False, and keeps entry
    store = Store(":memory:")
    service = make_test_service(seg=make_too_few_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    convo.handle(FakeIncoming(sender_id="u1", text="ok"))
    assert len(transport.sent) == 1
    assert transport.sent[0] == ("text", "u1", "REPLY:too_few:n=2:min=5:saved=False")
    assert len(store.samples()) == 0

    # Entry is kept, so another yes still attempts to save (and gets too_few again)
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="ok"))
    assert transport.sent[0] == ("text", "u1", "REPLY:too_few:n=2:min=5:saved=False")


def test_yes_without_pending_entry():
    # Yes without pending says to send photo first
    service = make_test_service()
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", text="yes"))
    assert len(transport.sent) == 1
    assert transport.sent[0] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )


@pytest.mark.parametrize("word", ["Có", "CO", "ok", "Lưu", "dong y", "y"])
def test_yes_variants(word):
    # Accent and case variants are recognized as yes
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text=word))
    assert len(store.samples()) == 1


def test_numbers_choose_shrimp_and_save():
    # Numbers re-choose shrimp, resend photo and reply, and save saves chosen count
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    clock = FakeClock()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        clock=clock,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    # Send 1 3 5
    convo.handle(FakeIncoming(sender_id="u1", text="1 3 5"))
    assert len(transport.sent) == 2
    assert transport.sent[0] == ("image", "u1", b"RENDERED_JPEG")
    assert transport.sent[1] == ("text", "u1", "REPLY:too_few:n=3:min=5:saved=None")

    # Send comma-separated 1,3,5 gives same result
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="1,3,5"))
    assert len(transport.sent) == 2
    assert transport.sent[1] == ("text", "u1", "REPLY:too_few:n=3:min=5:saved=None")

    # Now choose 5 shrimp (1, 2, 3, 4, 5) and save
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="1 2 3 4 5"))
    assert transport.sent[1] == ("text", "u1", "REPLY:ok:n=5:min=5:saved=None")

    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    samples = store.samples()
    assert len(samples) == 1
    assert samples[0].n_measured == 5


def test_numbers_out_of_range_and_empty():
    # Numbers 0, 99, 1 99 or empty list send range message and do not change pending
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    for bad in ("0", "99", "1 99", ", ,"):
        convo.handle(FakeIncoming(sender_id="u1", text=bad))
        assert transport.sent[-1] == ("text", "u1", "Số con phải từ 1 đến 6. Ví dụ: 1 3 5.")

    # Pending entry still intact and unchanged (6 shrimp ok)
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert len(store.samples()) == 1
    assert store.samples()[0].n_measured == 6


def test_numbers_without_pending_and_after_ttl():
    # Numbers without pending or after ttl say to send photo first
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    clock = FakeClock()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        ttl_seconds=1800,
        clock=clock,
    )

    # Without pending
    convo.handle(FakeIncoming(sender_id="u1", text="1 3 5"))
    assert transport.sent[-1] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )

    # After ttl
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    clock.advance(1801)
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="1 3 5"))
    assert transport.sent[-1] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )


def test_numbers_analysis_not_found():
    # AnalysisNotFound in summary drops pending and sends expired message
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    # Clear service cache to trigger AnalysisNotFound
    service._analyses.clear()
    transport.sent.clear()

    convo.handle(FakeIncoming(sender_id="u1", text="1 2 3"))
    assert transport.sent[-1] == ("text", "u1", "Ảnh này đã hết hạn, bạn gửi lại giúp mình nhé.")

    # Subsequent yes finds no pending entry
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.sent[-1] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )


def test_cancel_drops_entry():
    # Cancel drops pending entry and confirms
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    convo.handle(FakeIncoming(sender_id="u1", text="huỷ"))
    assert transport.sent[0] == ("text", "u1", "Đã bỏ kết quả vừa rồi.")

    # Following yes asks for photo
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.sent[0] == (
        "text",
        "u1",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )


def test_status_with_and_without_url():
    # Status calls write_status and appends dashboard_url when present
    service = make_test_service()
    transport = FakeTransport()
    convo_with_url = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        dashboard_url="https://example.com/shrimp",
    )

    convo_with_url.handle(FakeIncoming(sender_id="u1", text="tình hình"))
    assert transport.sent[-1] == (
        "text",
        "u1",
        "STATUS:empty=True\nXem biểu đồ: https://example.com/shrimp",
    )

    transport.sent.clear()
    convo_no_url = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )
    convo_no_url.handle(FakeIncoming(sender_id="u1", text="dashboard"))
    assert transport.sent[-1] == ("text", "u1", "STATUS:empty=True")


def test_unknown_text_and_empty_give_help():
    # Unknown text and empty message return the standard help text
    service = make_test_service()
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    help_expected = HELP_TEXT

    for msg in (FakeIncoming(sender_id="u1", text="xin chào"), FakeIncoming(sender_id="u1", text=""), FakeIncoming(sender_id="u1", text=None)):
        transport.sent.clear()
        convo.handle(msg)
        assert transport.sent[0] == ("text", "u1", help_expected)


def test_two_senders_isolation():
    # Senders do not see or overwrite each other's pending entries
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    # Sender 1 uploads photo
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p1.jpg"]))

    # Sender 2 says yes -> no pending entry
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u2", text="có"))
    assert transport.sent[0] == (
        "text",
        "u2",
        'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
    )

    # Sender 1 can still save
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.sent[0] == ("text", "u1", "REPLY:ok:n=6:min=5:saved=True")
    assert len(store.samples()) == 1


def test_sender_serialisation():
    # Two messages from same sender are serialised; different senders do not block
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    transport.download_started = threading.Event()
    transport.download_event = threading.Event()

    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    # Thread 1: u1 sends photo, which blocks in download
    t1 = threading.Thread(
        target=convo.handle,
        args=(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]),),
    )
    t1.start()
    assert transport.download_started.wait(timeout=2)

    # Thread 2: u2 sends a status message, should complete immediately while u1 is blocked
    u2_done = threading.Event()

    def handle_u2():
        convo.handle(FakeIncoming(sender_id="u2", text="tình hình"))
        u2_done.set()

    t2 = threading.Thread(target=handle_u2)
    t2.start()
    assert u2_done.wait(timeout=2), "Different sender was blocked by u1 download"
    t2.join()

    # Thread 3: u1 sends yes, must wait for u1 photo to complete
    u1_yes_handled = []

    def handle_u1_yes():
        convo.handle(FakeIncoming(sender_id="u1", text="có"))
        u1_yes_handled.append(time.time())

    t3 = threading.Thread(target=handle_u1_yes)
    t3.start()
    time.sleep(0.1)
    assert len(u1_yes_handled) == 0, "u1 second message ran before first completed"

    # Now release download
    transport.download_event.set()
    t1.join()
    t3.join()
    assert len(u1_yes_handled) == 1
    assert len(store.samples()) == 1


def test_help_text_lists_every_function():
    # The guide names each thing the farmer can do, one per numbered line
    lines = [ln for ln in HELP_TEXT.splitlines() if ln.strip()]
    assert lines[0].upper().startswith("HƯỚNG DẪN")
    numbered = [ln for ln in lines if ln[:2] in ("1.", "2.", "3.", "4.", "5.", "6.")]
    assert len(numbered) == 6
    for needle in ("ảnh", '"có"', "1 3 5", '"hủy"', '"tình hình"', '"hướng dẫn"'):
        assert any(needle in ln for ln in numbered), needle
    assert len(HELP_TEXT) < 1000


@pytest.mark.parametrize("word", ["hướng dẫn", "Huong dan", "help", "menu", "trợ giúp"])
def test_guide_words_show_the_help(word):
    # The farmer can ask for the guide again at any time, even with a result pending
    service = make_test_service()
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )
    convo.handle(FakeIncoming(sender_id="u1", text=word))
    assert transport.sent == [("text", "u1", HELP_TEXT)]


SORRY_TEXT = "Có lỗi khi xử lý, bạn thử lại giúp mình nhé."


def test_unexpected_error_on_save_still_answers():
    # A failure while saving must not leave the farmer without an answer
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()

    def boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    service.save = boom
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.sent == [("text", "u1", SORRY_TEXT)]


def test_unexpected_error_on_status_still_answers():
    # A failure while reading the dashboard must not leave the farmer without an answer
    service = make_test_service()
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
    )

    def boom(*args, **kwargs):
        raise RuntimeError("database is locked")

    service.dashboard = boom
    convo.handle(FakeIncoming(sender_id="u1", text="tình hình"))
    assert transport.sent == [("text", "u1", SORRY_TEXT)]
