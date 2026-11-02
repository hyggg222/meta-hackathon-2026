# Vietnamese reply texts and guard for shrimp measurement
import re
from typing import Iterable, List, Optional
import unicodedata

from shrimp.models import Dashboard, TrayResult

FORBIDDEN_PHRASES = [
    "thu hoạch ngay",
    "nên thu hoạch",
    "hãy thu hoạch",
    "cần thu hoạch",
    "nên bán",
    "hãy bán",
    "bán ngay",
    "harvest now",
    "sell now",
    "you should",
]

DATE_REGEX = re.compile(r"(?<!\d)(\d{1,2})/(\d{1,2})(?!\d)")
SHRIMP_REGEX = re.compile(
    r"(?i)(?:ví\s*dụ|vi\s*du|tôm\s*số|tom\s*so|tôm|tom|con\s*số|con\s*so|con|các\s*con|cac\s*con|shrimp\s*#?|shrimp\s+number|số|so|#)\s*:?\s*(\d+(?:[\s,]+(?:và\s+|and\s+)?\d+)*)"
)
NUM_REGEX = re.compile(
    r"\b\d{1,3}(?:\.\d{3})+(?:,\d+)?\b|\b\d+,\d+\b|\b\d+\.\d+\b|\b\d+\b"
)


def _remove_diacritics(text: str) -> str:
    # Remove Vietnamese diacritics
    text = text.replace("đ", "d").replace("Đ", "D")
    nfd = unicodedata.normalize("NFD", text)
    return "".join(c for c in nfd if unicodedata.category(c) != "Mn")


def _format_num(val: float) -> str:
    # Format float cleanly without trailing .0 if integer
    if isinstance(val, int) or (isinstance(val, float) and val.is_integer()):
        return str(int(val))
    return f"{val:g}"


def template_reply(
    tray: TrayResult, min_measured: int, saved: Optional[bool] = None
) -> str:
    # Build Vietnamese reply text for tray analysis result
    if tray.status == "too_few":
        crowded = ""
        if "crowded" in tray.notices:
            crowded = (
                "Ảnh có nhiều tôm chồng nhau hoặc dính nhau, nhiều con bị loại. "
                "Xếp tôm trải ra, không chồng lên nhau, rồi chụp lại. "
            )
        return (
            f"Chỉ có {tray.n_measured} con được tính, cần ít nhất {min_measured} con. "
            f"{crowded}"
            "Chưa lưu. Xếp lại tôm không chạm nhau rồi chụp lại, "
            "hoặc gõ thêm số các con cần tính."
        )
    if tray.status == "no_reference":
        return (
            "Không thấy thước hoặc thẻ trong ảnh nên chưa tính được mm. "
            "Đặt thước cạnh tôm rồi chụp lại."
        )
    if tray.status == "no_shrimp":
        return (
            "Không thấy con tôm nào trong ảnh. "
            "Xếp tôm nằm phẳng trên nền sáng rồi chụp lại."
        )

    parts: List[str] = []
    base_counts = f"Đo được {tray.n_measured} con, bỏ ra {tray.n_left_out} con."

    mean_str = (
        f"Dài trung bình {tray.mean_length_mm:.1f} mm"
        if tray.mean_length_mm is not None
        else None
    )
    size_str = (
        f"khoảng {round(tray.size_per_kg)} con/kg"
        if tray.size_per_kg is not None
        else None
    )

    if mean_str is not None and size_str is not None:
        stats = f"{mean_str}, {size_str}."
    elif mean_str is not None:
        stats = f"{mean_str}."
    elif size_str is not None:
        stats = f"{size_str.capitalize()}."
    else:
        stats = None

    if stats:
        parts.append(f"{base_counts} {stats}")
    else:
        parts.append(base_counts)

    if "temporary_table" in tray.notices or "rough_estimate" in tray.notices:
        parts.append(
            "Bảng cỡ tạm thời, chỉ là ước lượng thô, có thể lệch 20% trở lên."
        )
    if "outside_table_range" in tray.notices or (
        tray.size_per_kg is None and tray.status == "ok"
    ):
        parts.append(
            "Kích cỡ nằm ngoài bảng (60 đến 140 mm), không có số con/kg."
        )

    if "crowded" in tray.notices:
        parts.append(
            "Ảnh có nhiều tôm chồng nhau hoặc dính nhau, nhiều con bị loại. "
            "Xếp tôm trải ra, không chồng lên nhau, rồi chụp lại."
        )

    if saved is None:
        parts.append(
            'Trả lời "có" để lưu mẫu này, hoặc gõ số các con cần tính, ví dụ: 1 3 5.'
        )
        parts.append('Gõ "chọn" hoặc "bỏ" kèm số con để thêm hoặc bỏ từng con.')
        if tray.n_left_out > 0:
            parts.append('Gõ "xem loại" để xem các con bị loại.')
    elif saved is True:
        parts.append("Đã lưu mẫu.")
    elif saved is False:
        parts.append("Chưa lưu.")

    return " ".join(parts)


def dashboard_reply(d: Dashboard) -> str:
    # Build Vietnamese reply text for dashboard status
    if d.empty:
        return "Chưa có mẫu nào. Gửi ảnh khay tôm để bắt đầu."

    parts: List[str] = []

    date_val = getattr(d, "latest_day", None)
    if date_val is None and getattr(d, "rows", None):
        date_val = d.rows[-1].day
    elif date_val is None and getattr(d, "chart", None):
        date_val = d.chart[-1].day

    date_str = ""
    if date_val is not None:
        if hasattr(date_val, "strftime"):
            date_str = date_val.strftime("%d/%m")
        elif isinstance(date_val, str):
            if "-" in date_val:
                p = date_val.split("-")
                date_str = f"{p[2]}/{p[1]}"
            else:
                date_str = date_val

    prefix = f"Mẫu gần nhất {date_str}:" if date_str else "Mẫu gần nhất:"

    mean_str = (
        f"dài {d.latest_length_mm:.1f} mm"
        if d.latest_length_mm is not None
        else None
    )
    size_str = (
        f"khoảng {round(d.latest_size_per_kg)} con/kg"
        if d.latest_size_per_kg is not None
        else None
    )

    if mean_str is not None and size_str is not None:
        parts.append(f"{prefix} {mean_str}, {size_str}.")
    elif mean_str is not None:
        parts.append(f"{prefix} {mean_str}.")
    elif size_str is not None:
        parts.append(f"{prefix} {size_str}.")
    else:
        if date_str:
            parts.append(f"Mẫu gần nhất {date_str}.")
        else:
            parts.append("Mẫu gần nhất.")

    if d.stall is True:
        growth_val = d.growth_mm_per_day if d.growth_mm_per_day is not None else 0.0
        thresh_str = _format_num(d.stall_threshold_mm_per_day)
        parts.append(
            f"Tăng trưởng có vẻ chậm: {growth_val:.2f} mm mỗi ngày, "
            f"dưới mức {thresh_str} bạn đặt. Đây chỉ là gợi ý, bạn quyết định."
        )
    elif d.stall is False:
        growth_val = d.growth_mm_per_day if d.growth_mm_per_day is not None else 0.0
        parts.append(f"Tăng trưởng không chậm: {growth_val:.2f} mm mỗi ngày.")
    elif d.stall_unclear and d.growth_se_mm_per_day is not None:
        parts.append(
            "Chưa đủ chắc để nói tôm còn lớn hay không: "
            f"mỗi mẫu dao động khoảng ±{d.growth_se_mm_per_day:.2f} mm mỗi ngày "
            f"so với mức {_format_num(d.stall_threshold_mm_per_day)} bạn đặt. "
            f"Cần thêm khoảng {d.shrimp_needed} con mỗi mẫu, "
            f"hoặc đợi khoảng {d.days_needed} ngày giữa hai lần đo. "
            "Đây chỉ là gợi ý, bạn quyết định."
        )
    else:
        parts.append("Chưa đủ dữ liệu để so với mẫu trước.")

    if d.at_harvest:
        harvest_thresh_str = _format_num(d.harvest_threshold_per_kg)
        parts.append(
            f"Cỡ tôm đạt mức {harvest_thresh_str} con/kg bạn đặt. "
            "Chỉ để bạn tham khảo, bạn quyết định."
        )

    if d.value_per_kg_vnd is not None and d.latest_size_per_kg is not None:
        val_str = f"{d.value_per_kg_vnd:,}".replace(",", ".")
        parts.append(
            f"Ở cỡ {round(d.latest_size_per_kg)} con/kg, giá khoảng {val_str} đ/kg (bảng giá mặc định, bạn có thể khác)."
        )

    if d.next_class_per_kg is not None and d.next_class_gain_pct is not None:
        days_text = ""
        if d.days_to_next_class is not None:
            days_text = f" (còn khoảng {d.days_to_next_class} ngày nếu tôm lớn như vừa đo, rất thô)"
        gain_str = _format_num(d.next_class_gain_pct)
        parts.append(
            f"Bậc cỡ {d.next_class_per_kg} con/kg thường được giá hơn khoảng {gain_str}%{days_text}."
        )

    if d.breakeven_mm_per_day is not None:
        parts.append(
            f"Thức ăn chỉ hòa vốn nếu tôm lớn trên khoảng {d.breakeven_mm_per_day:.2f} mm mỗi ngày (chưa tính điện, công, rủi ro)."
        )

    if d.stall_day_cost_vnd is not None:
        cost_str = f"{d.stall_day_cost_vnd:,}".replace(",", ".")
        parts.append(f"Một ngày không lớn tốn thức ăn khoảng {cost_str} đ.")

    return " ".join(parts)


def check_reply(text: str, allowed_numbers: Iterable[float]) -> bool:
    # Check reply text against forbidden phrases and allowed numbers
    if not text or not text.strip():
        return False

    lower_text = text.lower()
    no_dia_text = _remove_diacritics(lower_text)

    for phrase in FORBIDDEN_PHRASES:
        if phrase in lower_text:
            return False
        phrase_no_dia = _remove_diacritics(phrase)
        if phrase_no_dia in no_dia_text:
            return False

    # Exempt date positions (dd/mm)
    date_spans: List[tuple] = []
    for m in DATE_REGEX.finditer(text):
        day = int(m.group(1))
        month = int(m.group(2))
        if 1 <= day <= 31 and 1 <= month <= 12:
            date_spans.append((m.start(1), m.end(1)))
            date_spans.append((m.start(2), m.end(2)))

    # Exempt shrimp numbers
    shrimp_spans: List[tuple] = []
    for m in SHRIMP_REGEX.finditer(text):
        nums_part = m.group(1)
        base_offset = m.start(1)
        for num_m in re.finditer(r"\d+", nums_part):
            shrimp_spans.append(
                (base_offset + num_m.start(), base_offset + num_m.end())
            )

    allowed_list = [float(x) for x in allowed_numbers if x is not None]

    # Find and validate all numbers
    for m in NUM_REGEX.finditer(text):
        span = (m.start(), m.end())
        # Check if exempt as date
        if any(s <= span[0] and span[1] <= e for s, e in date_spans):
            continue
        # Check if exempt as shrimp number
        if any(s <= span[0] and span[1] <= e for s, e in shrimp_spans):
            continue

        raw = m.group(0)
        candidates: List[tuple] = []
        if "." in raw and "," in raw:
            val = float(raw.replace(".", "").replace(",", "."))
            prec = len(raw.split(",")[1])
            candidates.append((val, prec))
        elif "," in raw:
            val = float(raw.replace(",", "."))
            prec = len(raw.split(",")[1])
            candidates.append((val, prec))
        elif "." in raw:
            dots = raw.count(".")
            after_last = raw.split(".")[-1]
            if dots > 1 or len(after_last) == 3:
                candidates.append((float(raw.replace(".", "")), 0))
            if len(after_last) != 3 or dots == 1:
                candidates.append((float(raw), len(after_last)))
        else:
            candidates.append((float(raw), 0))

        matched = False
        for val, prec in candidates:
            for a in allowed_list:
                if prec == 0:
                    if abs(round(a) - val) < 1e-6 or abs(a - val) < 1e-6:
                        matched = True
                        break
                else:
                    if abs(round(a, prec) - val) < 1e-6:
                        matched = True
                        break
            if matched:
                break

        if not matched:
            return False

    return True


def allowed_numbers_for_tray(
    tray: TrayResult, min_measured: int
) -> List[float]:
    # Return all allowed numbers for a tray result template
    allowed: List[float] = [
        float(tray.n_measured),
        float(tray.n_left_out),
        float(min_measured),
        20.0,
        60.0,
        140.0,
        1.0,
        3.0,
        5.0,
    ]
    if tray.mean_length_mm is not None:
        allowed.append(float(tray.mean_length_mm))
        allowed.append(round(float(tray.mean_length_mm), 1))
    if tray.size_per_kg is not None:
        allowed.append(float(tray.size_per_kg))
        allowed.append(float(round(tray.size_per_kg)))

    num_shrimp = len(tray.shrimp) if tray.shrimp else 0
    for i in range(1, num_shrimp + 1):
        allowed.append(float(i))
    if tray.included:
        for idx in tray.included:
            allowed.append(float(idx + 1))

    seen = set()
    result = []
    for x in allowed:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def allowed_numbers_for_dashboard(d: Dashboard) -> List[float]:
    # Return all allowed numbers for a dashboard reply
    allowed: List[float] = [
        float(d.stall_threshold_mm_per_day),
        round(float(d.stall_threshold_mm_per_day), 2),
        float(d.harvest_threshold_per_kg),
        float(round(d.harvest_threshold_per_kg)),
        float(d.min_measured),
    ]
    if d.latest_length_mm is not None:
        allowed.append(float(d.latest_length_mm))
        allowed.append(round(float(d.latest_length_mm), 1))
    if d.latest_size_per_kg is not None:
        allowed.append(float(d.latest_size_per_kg))
        allowed.append(float(round(d.latest_size_per_kg)))
    if d.growth_mm_per_day is not None:
        allowed.append(float(d.growth_mm_per_day))
        allowed.append(round(float(d.growth_mm_per_day), 2))
    if d.growth_se_mm_per_day is not None:
        allowed.append(float(d.growth_se_mm_per_day))
        allowed.append(round(float(d.growth_se_mm_per_day), 2))
    if d.days_needed is not None:
        allowed.append(float(d.days_needed))
    if d.shrimp_needed is not None:
        allowed.append(float(d.shrimp_needed))
    if d.stall_day_cost_vnd is not None:
        allowed.append(float(d.stall_day_cost_vnd))
    if d.n_latest is not None:
        allowed.append(float(d.n_latest))
    if d.n_previous is not None:
        allowed.append(float(d.n_previous))
    if d.days_between is not None:
        allowed.append(float(d.days_between))
    if d.change_length_mm is not None:
        allowed.append(float(d.change_length_mm))
        allowed.append(round(float(d.change_length_mm), 1))
    if d.change_size_per_kg is not None:
        allowed.append(float(d.change_size_per_kg))
        allowed.append(float(round(d.change_size_per_kg)))
    if d.value_per_kg_vnd is not None:
        allowed.append(float(d.value_per_kg_vnd))
    if d.next_class_per_kg is not None:
        allowed.append(float(d.next_class_per_kg))
    if d.next_class_gain_pct is not None:
        allowed.append(float(d.next_class_gain_pct))
        allowed.append(round(float(d.next_class_gain_pct), 1))
        allowed.append(float(round(d.next_class_gain_pct)))
    if d.days_to_next_class is not None:
        allowed.append(float(d.days_to_next_class))
    if d.breakeven_mm_per_day is not None:
        allowed.append(float(d.breakeven_mm_per_day))
        allowed.append(round(float(d.breakeven_mm_per_day), 2))

    date_val = getattr(d, "latest_day", None)
    if date_val is None and getattr(d, "rows", None):
        date_val = d.rows[-1].day
    elif date_val is None and getattr(d, "chart", None):
        date_val = d.chart[-1].day
    if date_val is not None and hasattr(date_val, "day"):
        allowed.append(float(date_val.day))
        allowed.append(float(date_val.month))

    seen = set()
    result = []
    for x in allowed:
        if x not in seen:
            seen.add(x)
            result.append(x)
    return result


def safe_reply(
    candidate: Optional[str], fallback: str, allowed_numbers: Iterable[float]
) -> str:
    # Validate candidate with check_reply or fall back to template text
    if candidate is not None and check_reply(candidate, allowed_numbers):
        return candidate
    return fallback
