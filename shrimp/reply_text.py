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
        crowded_sentence = "Ảnh có nhiều tôm chồng nhau. Xếp tôm trải ra rồi chụp lại sẽ đo đúng hơn."
        first_line = f"Chỉ có {tray.n_measured} con được tính, cần ít nhất {min_measured} con. Chưa lưu."
        if "crowded" in tray.notices:
            return f"{first_line}\n{crowded_sentence}"
        else:
            return f'{first_line}\nXếp tôm không chạm nhau rồi chụp lại, hoặc gõ "chọn 3" để thêm con.'

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

    if saved is True:
        return "Đã lưu mẫu."
    if saved is False and tray.status == "ok":
        return "Chưa lưu."

    lines: List[str] = []
    if tray.n_left_out > 0:
        lines.append(f"Đo được {tray.n_measured} con (bỏ {tray.n_left_out} con)")
    else:
        lines.append(f"Đo được {tray.n_measured} con")

    cm_str = ""
    if tray.mean_length_mm is not None:
        cm_val = tray.mean_length_mm / 10.0
        cm_str = f"{cm_val:.1f}".replace(".", ",")

    if tray.size_per_kg is not None:
        size_val = round(tray.size_per_kg)
        lines.append(f"Dài trung bình {cm_str} cm · khoảng {size_val} con/kg")
    else:
        lines.append(f"Dài trung bình {cm_str} cm · cỡ nằm ngoài bảng (60 đến 140 mm)")

    if "temporary_table" in tray.notices or "rough_estimate" in tray.notices:
        lines.append("Ước lượng thô, có thể lệch 20%.")

    if "crowded" in tray.notices:
        lines.append("")
        lines.append("Ảnh có nhiều tôm chồng nhau. Xếp tôm trải ra rồi chụp lại sẽ đo đúng hơn.")

    return "\n".join(lines)


def dashboard_reply(d: Dashboard) -> str:
    # Build Vietnamese reply text for dashboard status
    if d.empty:
        return "Chưa có lần đo nào. Gửi ảnh khay tôm để bắt đầu."

    lines: List[str] = []

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

    prefix = f"Lần đo mới nhất {date_str}:" if date_str else "Lần đo mới nhất:"

    cm_str = None
    if d.latest_length_mm is not None:
        cm_val = d.latest_length_mm / 10.0
        cm_str = f"tôm dài {cm_val:.1f}".replace(".", ",") + " cm"

    size_str = (
        f"khoảng {round(d.latest_size_per_kg)} con/kg"
        if d.latest_size_per_kg is not None
        else None
    )

    if cm_str is not None and size_str is not None:
        lines.append(f"{prefix} {cm_str}, {size_str}.")
    elif cm_str is not None:
        lines.append(f"{prefix} {cm_str}.")
    elif size_str is not None:
        lines.append(f"{prefix} {size_str}.")
    else:
        if date_str:
            lines.append(f"Lần đo mới nhất {date_str}.")
        else:
            lines.append("Lần đo mới nhất.")

    if d.stall is True:
        growth_val = d.growth_mm_per_day if d.growth_mm_per_day is not None else 0.0
        thresh_str = _format_num(d.stall_threshold_mm_per_day)
        lines.append(
            f"Tôm đang lớn chậm: khoảng {growth_val:.2f} mm mỗi ngày, "
            f"dưới mức {thresh_str} bạn đặt. Chỉ là gợi ý, bạn quyết định."
        )
    elif d.stall is False:
        growth_val = d.growth_mm_per_day if d.growth_mm_per_day is not None else 0.0
        lines.append(f"Tôm vẫn đang lớn: khoảng {growth_val:.2f} mm mỗi ngày.")
    elif d.stall_unclear:
        lines.append("Chưa xác định được: kích thước tôm dao động lên xuống, cần đo nhiều mẫu.")
    else:
        lines.append("Chưa đủ dữ liệu để so với lần trước.")

    if d.at_harvest:
        harvest_thresh_str = _format_num(d.harvest_threshold_per_kg)
        lines.append(
            f"Cỡ tôm đạt mức {harvest_thresh_str} con/kg bạn đặt (chỉ để tham khảo, bạn quyết định)."
        )

    if d.value_per_kg_vnd is not None and d.latest_size_per_kg is not None:
        val_str = f"{d.value_per_kg_vnd:,}".replace(",", ".")
        lines.append(
            f"Ở cỡ {round(d.latest_size_per_kg)} con/kg, giá khoảng {val_str} đ/kg (bảng giá mặc định, bạn có thể khác)."
        )

    if d.next_class_per_kg is not None and d.next_class_gain_pct is not None:
        days_text = ""
        if d.days_to_next_class is not None:
            days_text = f" (còn khoảng {d.days_to_next_class} ngày nếu tôm lớn như vừa đo, rất thô)"
        gain_str = _format_num(d.next_class_gain_pct)
        lines.append(
            f"Bậc cỡ {d.next_class_per_kg} con/kg thường được giá hơn khoảng {gain_str}%{days_text}."
        )

    if d.breakeven_mm_per_day is not None:
        lines.append(
            f"Thức ăn chỉ hòa vốn nếu tôm lớn trên khoảng {d.breakeven_mm_per_day:.2f} mm mỗi ngày (chưa tính điện, công, rủi ro)."
        )

    if d.stall_day_cost_vnd is not None:
        cost_str = f"{d.stall_day_cost_vnd:,}".replace(",", ".")
        lines.append(f"Một ngày không lớn tốn thức ăn khoảng {cost_str} đ.")

    return "\n".join(lines)


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
        cm_val = float(tray.mean_length_mm) / 10.0
        allowed.append(cm_val)
        allowed.append(round(cm_val, 1))
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
        cm_val = float(d.latest_length_mm) / 10.0
        allowed.append(cm_val)
        allowed.append(round(cm_val, 1))
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
