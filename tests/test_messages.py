# Tests for the editable message files (shrimp/messages_vi.txt and messages_en.txt)
import re

import pytest

from shrimp import messages
from shrimp.messages import KEYS, MessageError, load_catalog, parse_catalog, t, use

VIETNAMESE_LETTERS = re.compile(
    "[àáảãạăằắẳẵặâầấẩẫậđèéẻẽẹêềếểễệìíỉĩịòóỏõọôồốổỗộơờớởỡợùúủũụưừứửữựỳýỷỹỵ]", re.IGNORECASE
)


@pytest.fixture(autouse=True)
def back_to_vietnamese():
    yield
    use("vi")


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_file_defines_every_key_and_only_known_ones(lang):
    assert set(load_catalog(lang)) == set(KEYS)


@pytest.mark.parametrize("lang", ["vi", "en"])
def test_texts_use_only_the_placeholders_of_their_key(lang):
    for key, text in load_catalog(lang).items():
        used = set(re.findall(r"{(\w+)}", text))
        assert used <= set(KEYS[key]), (lang, key, used)


def test_english_file_has_no_vietnamese_letters():
    for key, text in load_catalog("en").items():
        assert not VIETNAMESE_LETTERS.search(text), key


def test_parse_catalog_format():
    text = ";; a comment line\n=== a.b\nline one\nline two\n\n\n=== c\nx {n}\n"
    assert parse_catalog(text, "test") == {"a.b": "line one\nline two", "c": "x {n}"}


def test_parse_catalog_rejects_duplicates_text_before_header_and_empty_text():
    with pytest.raises(MessageError, match="twice"):
        parse_catalog("=== a\nx\n=== a\ny\n", "test")
    with pytest.raises(MessageError, match="before the first"):
        parse_catalog("stray text\n=== a\nx\n", "test")
    with pytest.raises(MessageError, match="empty"):
        parse_catalog("=== a\n\n=== b\nx\n", "test")


def _write_files(tmp_path, edit):
    for lang in ("vi", "en"):
        text = (messages.CATALOG_DIR / f"messages_{lang}.txt").read_text(encoding="utf-8")
        if lang == "vi":
            text = edit(text)
        (tmp_path / f"messages_{lang}.txt").write_text(text, encoding="utf-8")


def test_unknown_placeholder_names_the_key_and_the_placeholder(tmp_path):
    _write_files(tmp_path, lambda s: s.replace("Đo được {n} con\n", "Đo được {zzz} con\n", 1))
    with pytest.raises(MessageError) as err:
        load_catalog("vi", directory=tmp_path)
    assert "photo.count" in str(err.value)
    assert "zzz" in str(err.value)


def test_missing_key_is_named(tmp_path):
    _write_files(tmp_path, lambda s: re.sub(r"=== photo\.saved\n.*?\n(?==== )", "", s, count=1, flags=re.S))
    with pytest.raises(MessageError) as err:
        load_catalog("vi", directory=tmp_path)
    assert "photo.saved" in str(err.value)


def test_unknown_language_is_refused():
    with pytest.raises(MessageError):
        use("fr")


def test_vietnamese_text_and_number_style():
    use("vi")
    assert t("photo.too_few", n=3, min=5) == "Chỉ có 3 con được tính, cần ít nhất 5 con. Chưa lưu."
    assert messages.num(9.54) == "9,5"
    assert messages.money(45000) == "45.000"


def test_english_text_and_number_style():
    use("en")
    assert t("photo.too_few", n=3, min=5) == "Only 3 shrimp counted, at least 5 needed. Not saved."
    assert messages.num(9.54) == "9.5"
    assert messages.money(45000) == "45,000"
