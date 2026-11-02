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
        self.quick_replies: List[Optional[List[Tuple[str, str]]]] = []
        self.download_exc: Optional[Exception] = None
        self.download_started: Optional[threading.Event] = None
        self.download_event: Optional[threading.Event] = None

    def send_text(
        self,
        recipient_id: str,
        text: str,
        quick_replies: Optional[List[Tuple[str, str]]] = None,
    ) -> None:
        self.sent.append(("text", recipient_id, text))
        self.quick_replies.append(quick_replies)

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


def _convo_with_pending(store=None):
    # A conversation whose sender u1 has a pending 6-shrimp result with everything counted
    store = store or Store(":memory:")
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
    assert transport.sent[-1] == ("text", "u1", "REPLY:ok:n=6:min=5:saved=None")
    transport.sent.clear()
    return convo, transport, store


def test_remove_and_add_change_the_current_choice():
    # "bỏ 1 3" and "chọn 1" work on what is counted now; the farmer never retypes the list
    convo, transport, _ = _convo_with_pending()

    convo.handle(FakeIncoming(sender_id="u1", text="bỏ 1 3"))
    assert transport.sent == [
        ("image", "u1", b"RENDERED_JPEG"),
        ("text", "u1", "REPLY:too_few:n=4:min=5:saved=None"),
    ]

    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="chọn 1"))
    assert transport.sent[1] == ("text", "u1", "REPLY:ok:n=5:min=5:saved=None")

    # adding what is already counted, or removing what is already out, changes nothing
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="chọn 1"))
    assert transport.sent[1] == ("text", "u1", "REPLY:ok:n=5:min=5:saved=None")
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="bỏ 3"))
    assert transport.sent[1] == ("text", "u1", "REPLY:ok:n=5:min=5:saved=None")


@pytest.mark.parametrize("text", ["chon 2,4", "Chọn 2, 4", "thêm 2 4", "them 2 4"])
def test_add_variants_after_removing(text):
    # Accent, case, commas and the word "thêm" all add to the choice
    convo, transport, _ = _convo_with_pending()
    convo.handle(FakeIncoming(sender_id="u1", text="bỏ 2 4 6"))
    assert transport.sent[-1] == ("text", "u1", "REPLY:too_few:n=3:min=5:saved=None")
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text=text))
    assert transport.sent[-1] == ("text", "u1", "REPLY:ok:n=5:min=5:saved=None")


def test_add_all_and_remove_all():
    # "chọn hết" counts every shrimp and "bỏ hết" counts none
    convo, transport, _ = _convo_with_pending()
    convo.handle(FakeIncoming(sender_id="u1", text="bỏ hết"))
    assert transport.sent[-1] == ("text", "u1", "REPLY:too_few:n=0:min=5:saved=None")
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="chọn tất cả"))
    assert transport.sent[-1] == ("text", "u1", "REPLY:ok:n=6:min=5:saved=None")


def test_add_remove_out_of_range_missing_numbers_and_no_pending():
    # Bad numbers or no result to change get a short answer and change nothing
    convo, transport, _ = _convo_with_pending()
    for text in ("bỏ 9", "chọn 0", "chọn 1 99", "bỏ", "chọn"):
        transport.sent.clear()
        convo.handle(FakeIncoming(sender_id="u1", text=text))
        assert len(transport.sent) == 1 and transport.sent[0][0] == "text", text
        assert "từ 1 đến 6" in transport.sent[0][2], text

    # the choice is unchanged: saving still saves all six
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.sent[-1] == ("text", "u1", "REPLY:ok:n=6:min=5:saved=True")

    # nothing pending now
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="bỏ 1"))
    assert transport.sent == [
        (
            "text",
            "u1",
            'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
        )
    ]


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
    assert lines[0] == "Cách dùng"
    numbered = [ln for ln in lines if ln[:2] in ("1.", "2.", "3.", "4.", "5.", "6.", "7.", "8.", "9.")]
    assert len(numbered) == 9
    for needle in (
        "ảnh",
        '"có"',
        '"chọn 1 3"',
        '"bỏ 1 3"',
        '"xem loại"',
        "1 3 5",
        '"hủy"',
        '"tình hình"',
        '"hướng dẫn"',
    ):
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


def _convo_with_left_out_view():
    # Like _convo_with_pending, with a second renderer for the left-out view
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        render_left_out=lambda photo, tray: b"LEFT_OUT_JPEG",
    )
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()
    return convo, transport


@pytest.mark.parametrize("text", ["xem loại", "Xem loai", "loại"])
def test_left_out_view_shows_the_shrimp_that_are_not_counted(text):
    # "xem loại" sends a second photo that numbers the left-out shrimp, and says how to add one
    convo, transport = _convo_with_left_out_view()
    convo.handle(FakeIncoming(sender_id="u1", text="bỏ 2 5"))
    transport.sent.clear()

    convo.handle(FakeIncoming(sender_id="u1", text=text))
    assert transport.sent[0] == ("image", "u1", b"LEFT_OUT_JPEG")
    assert transport.sent[1][0] == "text"
    assert 'chọn 2 5' in transport.sent[1][2]


def test_left_out_view_when_nothing_is_left_out():
    convo, transport = _convo_with_left_out_view()
    convo.handle(FakeIncoming(sender_id="u1", text="xem loại"))
    assert transport.sent == [("text", "u1", "Không có con nào bị loại.")]


def test_left_out_view_without_a_pending_result():
    service = make_test_service()
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        render_left_out=lambda photo, tray: b"LEFT_OUT_JPEG",
    )
    convo.handle(FakeIncoming(sender_id="u1", text="xem loại"))
    assert transport.sent == [
        (
            "text",
            "u1",
            'Bạn gửi ảnh khay tôm trước nhé, mình sẽ đo rồi bạn trả lời "có" để lưu.',
        )
    ]


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


def test_conversation_quick_reply_buttons_on_photo_ok():
    # After photo with status ok and left-out shrimp: 3 buttons
    store = Store(":memory:")
    # Ok segmenter with 6 shrimp, min_measured is 5, so 1 left out if we have 7 or overlapped
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    shrimp = [np.zeros((300, 300), bool) for _ in range(7)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True
    # 7 shrimp, 1 overlapped
    shrimp[-1][100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
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
    assert transport.quick_replies[-1] == [
        ("Lưu mẫu", "có"),
        ("Xem con bị loại", "xem loại"),
        ("Hủy", "hủy"),
    ]


def test_conversation_quick_reply_buttons_on_photo_ok_no_left_out():
    # After photo with status ok and 0 left out: 2 buttons (no "Xem con bị loại")
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
    assert len(transport.sent) == 2
    assert transport.quick_replies[-1] == [
        ("Lưu mẫu", "có"),
        ("Hủy", "hủy"),
    ]


def test_conversation_quick_reply_buttons_on_too_few():
    # After photo with status too_few: "Xem con bị loại" (if left out) and "Hủy"
    store = Store(":memory:")
    ruler = np.zeros((300, 300), bool)
    ruler[20:50, 20:200] = True
    # 3 shrimp, 1 overlapped -> 2 measured, 1 left out (< min 5)
    shrimp = [np.zeros((300, 300), bool) for _ in range(3)]
    for i, s in enumerate(shrimp):
        s[100 + i * 20 : 110 + i * 20, 50:150] = True
    shrimp[-1][100:110, 50:150] = True
    seg = FakeSegmenter({"ruler": [ruler], "shrimp": shrimp})
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
    assert transport.quick_replies[-1] == [
        ("Xem con bị loại", "xem loại"),
        ("Hủy", "hủy"),
    ]


def test_conversation_quick_replies_after_save_help_and_cancel():
    # Successful save gives Tình hình and Hướng dẫn; help gives Tình hình; cancel gives none
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

    # 1. Photo then save ("có")
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()
    transport.quick_replies.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert transport.quick_replies[-1] == [
        ("Tình hình", "tình hình"),
        ("Hướng dẫn", "hướng dẫn"),
    ]

    # 2. Help text ("hướng dẫn")
    transport.sent.clear()
    transport.quick_replies.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="hướng dẫn"))
    assert transport.quick_replies[-1] == [("Tình hình", "tình hình")]

    # 3. Photo then cancel ("hủy")
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    transport.sent.clear()
    transport.quick_replies.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="hủy"))
    assert transport.quick_replies[-1] is None


def test_conversation_left_out_view_quick_replies():
    # Left-out view gets "Thêm tất cả" and "Hủy"
    convo, transport = _convo_with_left_out_view()
    transport.sent.clear()
    transport.quick_replies.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="xem loại"))
    assert transport.quick_replies[-1] == [
        ("Thêm tất cả", "chọn hết"),
        ("Hủy", "hủy"),
    ]


def test_conversation_tapping_is_same_as_typing():
    # Feeding payload strings as incoming.text behaves identically to typing commands
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

    # Tap "có" (payload from button) saves pending
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    assert len(store.samples()) == 0
    convo.handle(FakeIncoming(sender_id="u1", text="có"))
    assert len(store.samples()) == 1

    # Tap "tình hình" queries status
    transport.sent.clear()
    convo.handle(FakeIncoming(sender_id="u1", text="tình hình"))
    assert "STATUS:empty=False" in transport.sent[-1][2]

