# Tests for the English bot used in the demo (BOT_LANG=en)
import re

import pytest

from shrimp import messages
from shrimp.conversation import Conversation
from shrimp.main import build
from shrimp.messages import MessageError, use
from shrimp.reply_text import dashboard_reply, template_reply
from shrimp.store import Store
from tests.conftest import FakeSegmenter
from tests.test_app import make_test_service
from tests.test_conversation import FakeIncoming, FakeTransport, fake_render, make_ok_segmenter
from tests.test_service import FakeTable

VIETNAMESE_LETTERS = re.compile(
    "[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]", re.IGNORECASE
)


@pytest.fixture
def english():
    use("en")
    yield
    use("vi")


def _convo():
    store = Store(":memory:")
    service = make_test_service(seg=make_ok_segmenter(), store=store, table=FakeTable())
    transport = FakeTransport()
    convo = Conversation(
        service=service,
        transport=transport,
        render=fake_render,
        write_reply=template_reply,
        write_status=dashboard_reply,
        dashboard_url="https://example.test",
    )
    return convo, service, store, transport


def _say(convo, text):
    convo.handle(FakeIncoming(sender_id="u1", text=text))


def _texts(transport):
    return [item[2] for item in transport.sent if item[0] == "text"]


def test_english_photo_save_status_and_help(english):
    convo, service, store, transport = _convo()

    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    assert "Measured 6 shrimp" in _texts(transport)[0]
    assert transport.quick_replies[-1] == [("Save sample", "có"), ("Cancel", "hủy")]

    _say(convo, "yes")
    assert _texts(transport)[-1] == "Sample saved."
    assert len(store.samples()) == 1

    _say(convo, "status")
    assert "Latest measurement" in _texts(transport)[-1]
    assert _texts(transport)[-1].endswith("See the chart: https://example.test")

    _say(convo, "help")
    assert _texts(transport)[-1].startswith("How to use")

    for text in _texts(transport):
        assert not VIETNAMESE_LETTERS.search(text), text


def test_english_commands_work_whatever_the_language():
    # "save", "choose 1 3" and "show left out" are understood even while the bot speaks Vietnamese
    convo, service, store, transport = _convo()
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    _say(convo, "remove 1 2")
    _say(convo, "choose 1")
    _say(convo, "save")
    assert len(store.samples()) == 1
    assert store.samples()[0].n_measured == 5


def test_english_setup_flow(english):
    convo, service, store, transport = _convo()
    _say(convo, "setup")
    assert _texts(transport)[-1].startswith("What is the pond name?")
    assert transport.quick_replies[-1][0][1] == "giữ"
    assert transport.quick_replies[-1][0][0].startswith("Keep ")

    _say(convo, "Pond B")
    assert "feed price per kg" in _texts(transport)[-1]
    _say(convo, "45,000")
    assert "Feed price: 45,000 VND per kg" in _texts(transport)[-1]
    assert transport.quick_replies[-1] == [("Save", "có"), ("Cancel", "hủy")]

    _say(convo, "yes")
    assert _texts(transport)[-1] == "Saved: Pond B, feed price 45,000 VND per kg."
    assert service.settings().pond_name == "Pond B"
    assert service.settings().feed_price_vnd == 45000


def test_english_numbers_use_dots_for_decimals(english):
    convo, service, store, transport = _convo()
    convo.handle(FakeIncoming(sender_id="u1", image_urls=["http://example.com/p.jpg"]))
    first = _texts(transport)[0]
    assert re.search(r"Average length \d+\.\d cm", first)


def test_build_reads_bot_lang(tmp_path):
    try:
        build(root=tmp_path, env={"META_API_KEY": "k", "BOT_LANG": "en"}, segmenter=FakeSegmenter())
        assert messages.t("photo.saved") == "Sample saved."
    finally:
        use("vi")
    with pytest.raises(MessageError):
        build(root=tmp_path, env={"META_API_KEY": "k", "BOT_LANG": "fr"}, segmenter=FakeSegmenter())
    build(root=tmp_path, env={"META_API_KEY": "k"}, segmenter=FakeSegmenter())
    assert messages.t("photo.saved") == "Đã lưu mẫu."
