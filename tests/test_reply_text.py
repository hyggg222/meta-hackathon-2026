# Tests for Vietnamese reply text templates and guard
from dataclasses import replace
from datetime import date
from typing import List, Optional

from shrimp.models import ChartPoint, Dashboard, SampleRow, ShrimpMeasure, TrayResult
from shrimp.reply_text import (
    allowed_numbers_for_dashboard,
    allowed_numbers_for_tray,
    check_reply,
    dashboard_reply,
    safe_reply,
    template_reply,
)


def _make_tray(
    status: str = "ok",
    n_measured: int = 8,
    n_left_out: int = 2,
    mean_length_mm: Optional[float] = 95.2,
    size_per_kg: Optional[float] = 71.0,
    notices: Optional[List[str]] = None,
    num_shrimp: int = 10,
) -> TrayResult:
    # Helper to construct TrayResult for tests
    shrimp = [
        ShrimpMeasure(
            index=i,
            length_px=100.0,
            length_mm=95.2,
            overlapped=(i >= n_measured),
            path=[],
        )
        for i in range(num_shrimp)
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
        notices=notices if notices is not None else [],
        included=list(range(n_measured)),
    )


def _make_dashboard(
    empty: bool = False,
    latest_day: date = date(2026, 11, 2),
    latest_length_mm: Optional[float] = 95.2,
    latest_size_per_kg: Optional[float] = 70.0,
    stall: Optional[bool] = None,
    growth_mm_per_day: Optional[float] = None,
    stall_threshold_mm_per_day: float = 0.33,
    stall_day_cost_vnd: Optional[int] = None,
    value_per_kg_vnd: Optional[int] = None,
    next_class_per_kg: Optional[int] = None,
    next_class_price_vnd: Optional[int] = None,
    next_class_gain_pct: Optional[float] = None,
    days_to_next_class: Optional[int] = None,
    breakeven_mm_per_day: Optional[float] = None,
    price_source: Optional[str] = None,
) -> Dashboard:
    # Helper to construct Dashboard for tests
    rows: List[SampleRow] = []
    chart: List[ChartPoint] = []
    if not empty:
        rows = [
            SampleRow(
                day=latest_day,
                n_measured=8,
                mean_length_mm=latest_length_mm,
                size_per_kg=latest_size_per_kg,
                demo=False,
                growth_mm_per_day=growth_mm_per_day,
            )
        ]
        if latest_length_mm is not None:
            chart = [
                ChartPoint(
                    day=latest_day,
                    mean_length_mm=latest_length_mm,
                    stall=bool(stall),
                )
            ]
    return Dashboard(
        empty=empty,
        latest_length_mm=latest_length_mm,
        latest_size_per_kg=latest_size_per_kg,
        n_latest=8 if not empty else None,
        change_length_mm=None,
        change_size_per_kg=None,
        n_previous=None,
        days_between=None,
        stall=stall,
        stall_day_cost_vnd=stall_day_cost_vnd,
        chart=chart,
        rows=rows,
        notices=[],
        growth_mm_per_day=growth_mm_per_day,
        stall_threshold_mm_per_day=stall_threshold_mm_per_day,
        min_measured=5,
        growth_se_mm_per_day=None,
        stall_unclear=False,
        days_needed=None,
        shrimp_needed=None,
        trend_samples=None,
        trend_span_days=None,
        value_per_kg_vnd=value_per_kg_vnd,
        next_class_per_kg=next_class_per_kg,
        next_class_price_vnd=next_class_price_vnd,
        next_class_gain_pct=next_class_gain_pct,
        days_to_next_class=days_to_next_class,
        breakeven_mm_per_day=breakeven_mm_per_day,
        price_source=price_source,
    )


def test_template_reply_ok():
    # Test ok status across saved options and notices
    t_pending = _make_tray(status="ok", n_measured=8, n_left_out=2, mean_length_mm=95.23, size_per_kg=71.2)
    reply_pending = template_reply(t_pending, min_measured=5, saved=None)
    assert "Đo được 8 con (bỏ 2 con)" in reply_pending
    assert "Dài trung bình 9,5 cm · khoảng 71 con/kg" in reply_pending
    assert 'Trả lời "có"' not in reply_pending
    assert 'Gõ "chọn"' not in reply_pending

    reply_saved = template_reply(t_pending, min_measured=5, saved=True)
    assert reply_saved == "Đã lưu mẫu."

    reply_unsaved = template_reply(t_pending, min_measured=5, saved=False)
    assert "Đã lưu mẫu." not in reply_unsaved

    # Notice: temporary_table / rough_estimate
    t_temp = _make_tray(status="ok", notices=["temporary_table", "rough_estimate"])
    reply_temp = template_reply(t_temp, min_measured=5, saved=None)
    assert "Ước lượng thô, có thể lệch 20%." in reply_temp

    # Notice: outside_table_range (size is None)
    t_outside = _make_tray(status="ok", mean_length_mm=55.0, size_per_kg=None, notices=["outside_table_range"])
    reply_outside = template_reply(t_outside, min_measured=5, saved=None)
    assert "Dài trung bình 5,5 cm · cỡ nằm ngoài bảng (60 đến 140 mm)" in reply_outside
    assert "con/kg" not in reply_outside


def test_template_reply_too_few():
    # Test too_few status with different saved values
    t_few = _make_tray(status="too_few", n_measured=3, n_left_out=7, mean_length_mm=None, size_per_kg=None)
    for saved in [None, False, True]:
        reply = template_reply(t_few, min_measured=5, saved=saved)
        assert reply == (
            "Chỉ có 3 con được tính, cần ít nhất 5 con. Chưa lưu.\n"
            'Xếp tôm không chạm nhau rồi chụp lại, hoặc gõ "chọn 3" để thêm con.'
        )


def test_template_reply_too_few_crowded_says_the_photo_is_crowded():
    # A pile of overlapping shrimp leaves too few: the farmer needs to hear that the photo is the problem
    t = _make_tray(
        status="too_few",
        n_measured=4,
        n_left_out=28,
        mean_length_mm=None,
        size_per_kg=None,
        notices=["crowded"],
        num_shrimp=32,
    )
    reply = template_reply(t, min_measured=5, saved=None)
    assert reply == (
        "Chỉ có 4 con được tính, cần ít nhất 5 con. Chưa lưu.\n"
        "Ảnh có nhiều tôm chồng nhau. Xếp tôm trải ra rồi chụp lại sẽ đo đúng hơn."
    )
    assert check_reply(reply, allowed_numbers_for_tray(t, 5)) is True


def test_template_reply_points_to_the_left_out_view_only_when_something_is_left_out():
    # With left out writes (bỏ N con), without left out omits the bracket
    with_left_out = _make_tray(status="ok", n_measured=8, n_left_out=2)
    without = _make_tray(status="ok", n_measured=8, n_left_out=0)
    assert "Đo được 8 con (bỏ 2 con)" in template_reply(with_left_out, 5, None)
    assert template_reply(without, 5, None).startswith("Đo được 8 con\n")
    assert "xem loại" not in template_reply(with_left_out, 5, None)
    assert "xem loại" not in template_reply(without, 5, None)
    assert check_reply(template_reply(with_left_out, 5, None), allowed_numbers_for_tray(with_left_out, 5)) is True


def test_template_reply_too_few_without_crowded_is_unchanged():
    t = _make_tray(status="too_few", n_measured=3, n_left_out=2, mean_length_mm=None, size_per_kg=None)
    assert "chồng nhau" not in template_reply(t, min_measured=5, saved=None)


def test_template_reply_no_reference():
    # Test no_reference status
    t_ref = _make_tray(status="no_reference", n_measured=8, n_left_out=2, mean_length_mm=None, size_per_kg=None)
    for saved in [None, False, True]:
        reply = template_reply(t_ref, min_measured=5, saved=saved)
        assert "Không thấy thước hoặc thẻ trong ảnh nên chưa tính được mm." in reply
        assert "Đặt thước cạnh tôm rồi chụp lại." in reply


def test_template_reply_no_shrimp():
    # Test no_shrimp status
    t_no_shrimp = _make_tray(status="no_shrimp", n_measured=0, n_left_out=0, mean_length_mm=None, size_per_kg=None)
    for saved in [None, False, True]:
        reply = template_reply(t_no_shrimp, min_measured=5, saved=saved)
        assert "Không thấy con tôm nào trong ảnh." in reply
        assert "Xếp tôm nằm phẳng trên nền sáng rồi chụp lại." in reply


def test_dashboard_reply_empty():
    # Empty dashboard reply
    d = _make_dashboard(empty=True)
    reply = dashboard_reply(d)
    assert reply == "Chưa có lần đo nào. Gửi ảnh khay tôm để bắt đầu."


def test_dashboard_reply_stall_states():
    # Test stall states: True, False, None
    d_stall_true = _make_dashboard(
        stall=True,
        growth_mm_per_day=0.20,
        stall_threshold_mm_per_day=0.33,
        stall_day_cost_vnd=4500000,
    )
    reply_true = dashboard_reply(d_stall_true)
    assert "Lần đo mới nhất 02/11: tôm dài 9,5 cm, khoảng 70 con/kg." in reply_true
    assert "Tôm đang lớn chậm: khoảng 0.20 mm mỗi ngày, dưới mức 0.33 bạn đặt. Chỉ là gợi ý, bạn quyết định." in reply_true
    assert "Một ngày không lớn tốn thức ăn khoảng 4.500.000 đ." in reply_true

    d_stall_false = _make_dashboard(
        stall=False,
        growth_mm_per_day=0.45,
    )
    reply_false = dashboard_reply(d_stall_false)
    assert "Tôm vẫn đang lớn: khoảng 0.45 mm mỗi ngày." in reply_false
    assert "Cỡ tôm đạt mức" not in reply_false
    assert "Một ngày không lớn" not in reply_false

    d_stall_none = _make_dashboard(
        stall=None,
        growth_mm_per_day=None,
    )
    reply_none = dashboard_reply(d_stall_none)
    assert "Chưa đủ dữ liệu để so với lần trước." in reply_none


def test_dashboard_reply_unclear_says_what_would_settle_it():
    # Noise: growth cannot be told from the threshold
    d = replace(
        _make_dashboard(stall=None, growth_mm_per_day=0.33),
        stall_unclear=True,
        growth_se_mm_per_day=1.4907,
        days_needed=23,
        shrimp_needed=553,
    )
    reply = dashboard_reply(d)
    assert "Chưa xác định được: kích thước tôm dao động lên xuống, cần đo nhiều mẫu." in reply
    assert "Chưa đủ dữ liệu để so với lần trước." not in reply
    assert check_reply(reply, allowed_numbers_for_dashboard(d)) is True


def test_dashboard_reply_none_fields():
    # Test dashboard when cost, mean, or size are None (never print "None")
    d_no_cost = _make_dashboard(stall_day_cost_vnd=None)
    reply_no_cost = dashboard_reply(d_no_cost)
    assert "tốn thức ăn" not in reply_no_cost
    assert "None" not in reply_no_cost

    d_no_mean = _make_dashboard(latest_length_mm=None, latest_size_per_kg=70.0)
    reply_no_mean = dashboard_reply(d_no_mean)
    assert "dài" not in reply_no_mean
    assert "khoảng 70 con/kg" in reply_no_mean
    assert "None" not in reply_no_mean

    d_no_size = _make_dashboard(latest_length_mm=95.2, latest_size_per_kg=None)
    reply_no_size = dashboard_reply(d_no_size)
    assert "tôm dài 9,5 cm" in reply_no_size
    assert "con/kg" not in reply_no_size
    assert "None" not in reply_no_size

    d_no_both = _make_dashboard(latest_length_mm=None, latest_size_per_kg=None)
    reply_no_both = dashboard_reply(d_no_both)
    assert "dài" not in reply_no_both
    assert "con/kg" not in reply_no_both
    assert "None" not in reply_no_both


def test_dashboard_reply_cost_formatting():
    # Test dot-separated thousands formatting for VND
    d = _make_dashboard(stall_day_cost_vnd=4500000)
    reply = dashboard_reply(d)
    assert "4.500.000 đ" in reply


def test_outputs_pass_check_reply():
    # Every output of template_reply and dashboard_reply passes check_reply with its allowed numbers
    trays = [
        _make_tray(status="ok", mean_length_mm=95.2, size_per_kg=71.0),
        _make_tray(status="ok", notices=["temporary_table", "rough_estimate"]),
        _make_tray(status="ok", mean_length_mm=55.0, size_per_kg=None, notices=["outside_table_range"]),
        _make_tray(status="too_few", n_measured=2, n_left_out=8),
        _make_tray(status="no_reference"),
        _make_tray(status="no_shrimp"),
    ]
    for tray in trays:
        allowed = allowed_numbers_for_tray(tray, min_measured=5)
        for saved in [None, True, False]:
            text = template_reply(tray, min_measured=5, saved=saved)
            assert check_reply(text, allowed) is True, f"Failed for {tray.status}, saved={saved}: {text}"

    dashboards = [
        _make_dashboard(empty=True),
        _make_dashboard(stall=True, growth_mm_per_day=0.20, stall_day_cost_vnd=4500000),
        _make_dashboard(stall=False, growth_mm_per_day=0.45),
        _make_dashboard(stall=None, growth_mm_per_day=None),
        _make_dashboard(latest_length_mm=None),
        _make_dashboard(latest_size_per_kg=None),
    ]
    for d in dashboards:
        allowed = allowed_numbers_for_dashboard(d)
        text = dashboard_reply(d)
        assert check_reply(text, allowed) is True, f"Failed for dashboard: {text}"


def test_check_reply_forbidden_phrases():
    # Rejects forbidden phrases case-insensitive and without diacritics
    allowed = [91.5]
    assert check_reply("nên thu hoạch", allowed) is False
    assert check_reply("bán ngay", allowed) is False
    assert check_reply("Bạn nên thu hoạch", allowed) is False
    assert check_reply("nen thu hoach", allowed) is False
    assert check_reply("ban ngay", allowed) is False
    assert check_reply("Ban nen thu hoach", allowed) is False
    assert check_reply("thu hoạch ngay", allowed) is False
    assert check_reply("hãy thu hoạch", allowed) is False
    assert check_reply("cần thu hoạch", allowed) is False
    assert check_reply("nên bán", allowed) is False
    assert check_reply("hãy bán", allowed) is False
    assert check_reply("harvest now", allowed) is False
    assert check_reply("sell now", allowed) is False
    assert check_reply("you should", allowed) is False


def test_check_reply_numbers_validation():
    # Validates numbers against allowed set, dates, and shrimp numbers
    allowed = [91.5]
    # Rejects number not in allowed set (91.4 vs 91.5)
    assert check_reply("Dài 91.4 mm", allowed) is False
    # Accepts matching number
    assert check_reply("Dài 91.5 mm", allowed) is True
    # Rejects empty or whitespace text
    assert check_reply("", allowed) is False
    assert check_reply("   ", allowed) is False

    # Passes for dd/mm date and shrimp numbers even if not in allowed_numbers
    assert check_reply("Mẫu ngày 02/11 có tôm số 1", []) is True
    assert check_reply("Mẫu ngày 15/05 có các con 1 3 5", []) is True
    assert check_reply("Ngày 02/11 tôm 1 dài 91.5 mm", [91.5]) is True


def test_safe_reply():
    # Tests safe_reply behavior
    allowed = [91.5]
    fallback = "Mẫu dài 91.5 mm"

    # Valid candidate
    assert safe_reply("Dài 91.5 mm", fallback, allowed) == "Dài 91.5 mm"
    # None candidate
    assert safe_reply(None, fallback, allowed) == fallback
    # Violating phrase candidate
    assert safe_reply("Bạn nên thu hoạch", fallback, allowed) == fallback
    # Empty candidate
    assert safe_reply("", fallback, allowed) == fallback
    # Wrong number candidate
    assert safe_reply("Dài 91.4 mm", fallback, allowed) == fallback


def test_no_text_contains_forbidden_words():
    # No text contains harvest, sell, alarm, or stall
    trays = [
        _make_tray(status="ok", mean_length_mm=95.2, size_per_kg=71.0),
        _make_tray(status="ok", notices=["temporary_table", "rough_estimate"]),
        _make_tray(status="ok", mean_length_mm=55.0, size_per_kg=None, notices=["outside_table_range"]),
        _make_tray(status="too_few", n_measured=2, n_left_out=8),
        _make_tray(status="no_reference"),
        _make_tray(status="no_shrimp"),
    ]
    texts = []
    for tray in trays:
        for saved in [None, True, False]:
            texts.append(template_reply(tray, min_measured=5, saved=saved))

    dashboards = [
        _make_dashboard(empty=True),
        _make_dashboard(stall=True, growth_mm_per_day=0.20, stall_day_cost_vnd=4500000),
        _make_dashboard(stall=False, growth_mm_per_day=0.45),
        _make_dashboard(stall=None, growth_mm_per_day=None),
    ]
    for d in dashboards:
        texts.append(dashboard_reply(d))

    for text in texts:
        lower = text.lower()
        for forbidden in ["harvest", "sell", "alarm", "stall"]:
            assert forbidden not in lower, f"Forbidden '{forbidden}' found in: {text}"


def test_template_reply_crowded():
    # Crowded notice adds Vietnamese warning after empty line and passes check_reply
    tray_crowded = _make_tray(status="ok", notices=["crowded"])
    reply = template_reply(tray_crowded, min_measured=5)
    crowded_sentence = (
        "Ảnh có nhiều tôm chồng nhau. Xếp tôm trải ra rồi chụp lại sẽ đo đúng hơn."
    )
    assert f"\n\n{crowded_sentence}" in reply
    assert 'Trả lời "có"' not in reply

    allowed = allowed_numbers_for_tray(tray_crowded, min_measured=5)
    assert check_reply(reply, allowed) is True

    tray_normal = _make_tray(status="ok", notices=[])
    reply_normal = template_reply(tray_normal, min_measured=5)
    assert crowded_sentence not in reply_normal


def test_template_reply_exact_lines_from_brief():
    # Brief exact lines: ok tray (8 measured, 2 left out, mean 95.2 mm, size 71, temporary_table & rough_estimate)
    tray = _make_tray(
        status="ok",
        n_measured=8,
        n_left_out=2,
        mean_length_mm=95.2,
        size_per_kg=71.0,
        notices=["temporary_table", "rough_estimate"],
    )
    reply = template_reply(tray, min_measured=5, saved=None)
    expected = (
        "Đo được 8 con (bỏ 2 con)\n"
        "Dài trung bình 9,5 cm · khoảng 71 con/kg\n"
        "Ước lượng thô, có thể lệch 20%."
    )
    assert reply == expected
    assert check_reply(reply, allowed_numbers_for_tray(tray, 5)) is True

    # With crowded notice
    tray_crowded = replace(tray, notices=["temporary_table", "rough_estimate", "crowded"])
    reply_crowded = template_reply(tray_crowded, min_measured=5, saved=None)
    expected_crowded = (
        "Đo được 8 con (bỏ 2 con)\n"
        "Dài trung bình 9,5 cm · khoảng 71 con/kg\n"
        "Ước lượng thô, có thể lệch 20%.\n\n"
        "Ảnh có nhiều tôm chồng nhau. Xếp tôm trải ra rồi chụp lại sẽ đo đúng hơn."
    )
    assert reply_crowded == expected_crowded
    assert check_reply(reply_crowded, allowed_numbers_for_tray(tray_crowded, 5)) is True

    # With saved=True
    assert template_reply(tray, min_measured=5, saved=True) == "Đã lưu mẫu."


def test_check_reply_accepts_decimal_comma():
    tray = _make_tray(mean_length_mm=95.2, size_per_kg=71.0)
    allowed = allowed_numbers_for_tray(tray, min_measured=5)
    assert check_reply("Dài trung bình 9,5 cm · khoảng 71 con/kg", allowed) is True

def test_dashboard_reply_pricing_lines():
    # dashboard_reply formats size price, next class gain/days, and feed break-even
    d = _make_dashboard(
        latest_length_mm=125.0,
        latest_size_per_kg=36.0,
        growth_mm_per_day=0.5,
        stall=False,
        value_per_kg_vnd=141200,
        next_class_per_kg=30,
        next_class_price_vnd=155000,
        next_class_gain_pct=9.8,
        days_to_next_class=23,
        breakeven_mm_per_day=0.27,
        price_source="Tepbac national median",
    )
    reply = dashboard_reply(d)

    # Dotted thousands and formatted text
    assert "Ở cỡ 36 con/kg, giá khoảng 141.200 đ/kg (bảng giá mặc định, bạn có thể khác)." in reply
    assert "Bậc cỡ 30 con/kg thường được giá hơn khoảng 9.8% (còn khoảng 23 ngày nếu tôm lớn như vừa đo, rất thô)." in reply
    assert "Thức ăn chỉ hòa vốn nếu tôm lớn trên khoảng 0.27 mm mỗi ngày (chưa tính điện, công, rủi ro)." in reply

    # Forbidden words check
    for word in ["nên", "thu hoạch", "bán"]:
        assert word not in reply.lower()

    # Passes check_reply with allowed numbers
    allowed = allowed_numbers_for_dashboard(d)
    assert check_reply(reply, allowed) is True

    # Without days_to_next_class
    d_no_days = replace(d, days_to_next_class=None)
    reply_no_days = dashboard_reply(d_no_days)
    assert "Bậc cỡ 30 con/kg thường được giá hơn khoảng 9.8%." in reply_no_days
    assert "còn khoảng" not in reply_no_days
    assert check_reply(reply_no_days, allowed_numbers_for_dashboard(d_no_days)) is True

