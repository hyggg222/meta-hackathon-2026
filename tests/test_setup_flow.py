# Tests for the "cài đặt" conversation in the Messenger bot
import pytest

from shrimp.conversation import Conversation
from shrimp.store import Store
from tests.test_app import make_test_service
from tests.test_conversation import (
    FakeClock,
    FakeIncoming,
    FakeTransport,
    fake_render,
    fake_write_reply,
    fake_write_status,
    make_ok_segmenter,
)
from tests.test_service import FakeTable


def _setup_convo(clock=None):
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    kwargs = {"clock": clock} if clock is not None else {}
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=fake_write_reply,
        write_status=fake_write_status,
        **kwargs,
    )
    return convo, service, transport


def _say(convo, text, sender="u1"):
    convo.handle(FakeIncoming(sender_id=sender, text=text))


def _last(transport):
    return transport.sent[-1][2]


def test_setup_asks_name_then_price_then_saves():
    # "cài đặt" asks one question at a time and saves only after the farmer confirms
    convo, service, transport = _setup_convo()
    before = service.settings()

    _say(convo, "cài đặt")
    assert "Tên ao" in _last(transport)
    assert service.settings() == before

    _say(convo, "Ao số 2")
    assert "Giá thức ăn" in _last(transport)
    assert service.settings() == before

    _say(convo, "45.000")
    assert "Ao số 2" in _last(transport)
    assert "45.000" in _last(transport)
    assert service.settings() == before
    assert transport.quick_replies[-1] == [("Lưu", "có"), ("Hủy", "hủy")]

    _say(convo, "có")
    saved = service.settings()
    assert saved.pond_name == "Ao số 2"
    assert saved.feed_price_vnd == 45000
    assert saved.stall_mm_per_day == before.stall_mm_per_day
    assert saved.min_measured == before.min_measured

    # the setup is over: a number is now treated as a number for shrimp, not as a price
    _say(convo, "7")
    assert "Bạn gửi ảnh khay tôm trước" in _last(transport)


@pytest.mark.parametrize(
    "answer,expected",
    [("45000", 45000), ("45k", 45000), ("45,000 đ", 45000), ("  52.500 ", 52500)],
)
def test_setup_price_formats(answer, expected):
    convo, service, transport = _setup_convo()
    _say(convo, "cài đặt")
    _say(convo, "Ao 1")
    _say(convo, answer)
    _say(convo, "có")
    assert service.settings().feed_price_vnd == expected


@pytest.mark.parametrize("bad", ["abc", "0", "-5", "12", "5000000000", "45 nghìn rưỡi"])
def test_setup_bad_price_asks_again_and_changes_nothing(bad):
    convo, service, transport = _setup_convo()
    before = service.settings()
    _say(convo, "cài đặt")
    _say(convo, "Ao 1")
    _say(convo, bad)
    assert "Giá thức ăn" in _last(transport)
    assert "từ 1.000" in _last(transport)

    _say(convo, "có")  # still waiting for a price, so this saves nothing
    assert service.settings() == before


def test_setup_cancel_at_any_step_changes_nothing():
    convo, service, transport = _setup_convo()
    before = service.settings()

    _say(convo, "cài đặt")
    _say(convo, "hủy")
    assert "Đã hủy" in _last(transport)

    _say(convo, "cài đặt")
    _say(convo, "Ao 9")
    _say(convo, "hủy")
    _say(convo, "cài đặt")
    _say(convo, "Ao 9")
    _say(convo, "50000")
    _say(convo, "hủy")
    assert service.settings() == before


def test_setup_keep_current_name():
    convo, service, transport = _setup_convo()
    current = service.settings().pond_name
    _say(convo, "cài đặt")
    assert transport.quick_replies[-1] == [("Giữ " + current, "giữ")]
    _say(convo, "giữ")
    _say(convo, "45000")
    _say(convo, "có")
    assert service.settings().pond_name == current


def test_setup_long_name_is_rejected():
    convo, service, transport = _setup_convo()
    before = service.settings()
    _say(convo, "cài đặt")
    _say(convo, "x" * 101)
    assert "Tên ao" in _last(transport)
    assert "ngắn hơn" in _last(transport)
    assert service.settings() == before


def test_setup_ends_when_a_photo_arrives_and_when_it_times_out():
    clock = FakeClock()
    convo, service, transport = _setup_convo(clock=clock)
    before = service.settings()

    _say(convo, "cài đặt")
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    _say(convo, "Ao 5")  # not an answer any more
    assert service.settings() == before

    _say(convo, "cài đặt")
    clock.advance(1801)
    _say(convo, "45000")  # too late: setup expired, a number without a photo
    assert "Bạn gửi ảnh khay tôm trước" in _last(transport)
    assert service.settings() == before


def test_setup_is_per_sender():
    convo, service, transport = _setup_convo()
    _say(convo, "cài đặt", sender="u1")
    _say(convo, "Ao của u1", sender="u2")  # u2 never started a setup
    assert service.settings().pond_name != "Ao của u1"
    assert "Giá thức ăn" not in _last(transport)
