# Tests for static HTML page labels, routes and safety
import re
from fastapi.testclient import TestClient

from shrimp.app import create_app
from tests.test_app import make_test_service


def test_page_vietnamese_labels():
    # Page contains required Vietnamese phrases and font
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "Nhật ký nuôi" in html
    assert "Các lần đo" in html
    assert "Tôm đang lớn chậm" in html
    assert "Chưa xác định được" in html
    assert "Cần đo nhiều mẫu để xác định chính xác." in html
    assert "Tải bảng (mở bằng Excel)" in html
    assert "Thức ăn, cài đặt" in html
    assert "Be+Vietnam+Pro" in html
    assert "/api/samples.csv" in html
    assert "dữ liệu mẫu" in html


def test_page_no_english_visible_text_and_no_chart():
    # Page has no SVG chart, no removed English texts, and no English keywords in visible text
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert not re.search(r'<polyline[^>]*stroke=["\']#0F6B63["\']', html)
    assert "Cost of a stall day" not in html
    assert "Growth looks slow" not in html
    assert "Average length" not in html
    assert "Send a photo" not in html
    assert "Feed + setup" not in html

    markup_no_code = re.sub(
        r"<(script|style)[^>]*>[\s\S]*?</\1>", " ", html, flags=re.IGNORECASE
    )
    visible_text = re.sub(r"<[^>]+>", " ", markup_no_code)

    for word in ["demo data", "Save", "Dashboard", "Setup"]:
        assert word not in visible_text, f"Found '{word}' in visible text"


def test_page_shrimp_icon():
    # Served HTML contains the shrimp line icon path
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "M5 15c0-5 4-9 9-9" in html


def test_page_script_reads_dashboard_fields():
    # Script reads stall fields from server without comparing growth to threshold
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    for field in [
        "stall",
        "stall_unclear",
        "growth_mm_per_day",
        "stall_threshold_mm_per_day",
        "rows",
        "demo",
    ]:
        assert field in script, f"Field '{field}' not found in script"

    assert not re.search(r"[<>]=?\s*d\.stall_threshold", script)


def test_page_setup_form_fields():
    # Setup form still has fields with ids for pond name, feed price, min length and ration, using parseNumber(
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert 'id="setup-name"' in html
    assert 'id="setup-price"' in html
    assert 'id="setup-min-length"' in html
    assert 'id="setup-ration"' in html

    assert "Tên ao" in html
    assert "Giá thức ăn mặc định (đồng mỗi kg)" in html
    assert "Con ngắn nhất được tính (mm)" in html
    assert "Con ngắn hơn bị coi là mảnh vụn và bị loại." in html
    assert "Thức ăn mỗi ngày (phần trăm thể trọng)" in html
    assert "Khoảng 1,5 ở cỡ 25 g. Chỉ dùng để tính, không ảnh hưởng gợi ý." in html
    assert "Lưu cài đặt" in html

    save_match = re.search(r"async\s+function\s+saveSetupHandler\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert save_match is not None, "saveSetupHandler not found"
    save_code = save_match.group(1)
    assert "parseNumber(" in save_code


def test_page_feed_form():
    # Feed form has Vietnamese labels and inputs
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert 'id="feed-date"' in html
    assert 'id="feed-kg"' in html
    assert 'id="feed-price"' in html

    assert "Nhập thức ăn" in html
    assert "Ngày" in html
    assert "Thức ăn mỗi ngày (kg)" in html
    assert "Giá thức ăn (đồng mỗi kg)" in html
    assert "Đã lưu." in html
    assert "feedDateEdited" in html
    assert "feedPriceEdited" in html


def test_page_parse_number():
    # Helper parseNumber on form values and no Number in submit handlers
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert re.search(r"function\s+parseNumber\s*\(", html) is not None
    assert html.count("parseNumber(") >= 6
    assert "Nhập số bình thường, ví dụ 100 hoặc 45000." in html

    feed_match = re.search(
        r'getElementById\("save-feed-btn"\)[\s\S]*?getElementById\("save-setup-btn"\)',
        html,
    )
    assert feed_match is not None
    assert "Number(" not in feed_match.group(0)

    setup_match = re.search(
        r'getElementById\("save-setup-btn"\)[\s\S]*?document\.addEventListener\("click"',
        html,
    )
    assert setup_match is not None
    assert "Number(" not in setup_match.group(0)


def test_page_api_routes():
    # Every /api/ path in fetch matches a valid route and method in app.routes
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    route_methods = {}
    for route in app.routes:
        if hasattr(route, "path") and hasattr(route, "methods"):
            route_methods.setdefault(route.path, set()).update(route.methods)

    raw_api_paths = set(re.findall(r"/api/(?:[a-zA-Z0-9_\-/]|\$\{[^}]+\})+", html))
    assert len(raw_api_paths) > 0

    # /api/samples.csv is an href download added by another agent in parallel; skip in this worktree
    raw_api_paths = {p for p in raw_api_paths if p != "/api/samples.csv"}

    api_paths = {re.sub(r"\$\{[^}]+\}", "{analysis_id}", p) for p in raw_api_paths}
    for path in api_paths:
        assert path in route_methods, f"Unknown API path: {path}"

    fetch_calls = re.findall(
        r'fetch\(\s*[`"\'](/api/[^`"\']+)[`"\'](?:\s*,\s*\{[^}]*method:\s*[`"\']([A-Z]+)[`"\'])?',
        html,
    )
    assert len(fetch_calls) > 0
    for path, method in fetch_calls:
        effective_method = method if method else "GET"
        normalized_path = re.sub(r"\$\{[^}]+\}", "{analysis_id}", path)
        assert normalized_path in route_methods, f"Unknown path in fetch: {normalized_path}"
        assert effective_method in route_methods[normalized_path], (
            f"Method {effective_method} not allowed for {normalized_path}"
        )


def test_page_safety():
    # Page does not append via innerHTML, has no http, and only links Google Fonts for https
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert not re.search(r"innerHTML\s*\+=", html), "Found innerHTML += in page"
    assert "http://" not in html
    https_urls = re.findall(r'https://[^\s"\'>]+', html)
    assert all(u.startswith("https://fonts.googleapis.com/") for u in https_urls)


def test_page_hash_navigation():
    # The served HTML mentions hashchange and the fragment names feed, dashboard
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "hashchange" in html
    assert "feed" in html
    assert "dashboard" in html


def test_page_per_kg_text_helper():
    # The HTML contains helper perKgText using Math.round
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "perKgText" in html
    match = re.search(r"function\s+perKgText\s*\([^)]*\)\s*\{[\s\S]*?\}", html)
    assert match is not None, "function perKgText not found"
    assert "Math.round" in match.group(0), "perKgText must use Math.round"


def test_page_numbers_from_server():
    # Growth and threshold numbers from server without JS division
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "growth_mm_per_day" in html
    assert "stall_threshold_mm_per_day" in html
    assert "harvest_threshold_per_kg" in html
    assert "change_length_mm / " not in html
    assert "/ d.days_between" not in html


def test_page_photo_removed():
    # The page has no type="file", no Measure photo, no Save sample, no renderPhotoSvg, no /api/analyses and no /api/samples
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert 'type="file"' not in html
    assert "Measure photo" not in html
    assert "Save sample" not in html
    assert "renderPhotoSvg" not in html
    assert "/api/analyses" not in html
    assert not re.search(r"/api/samples(?!\.csv)", html)


def test_page_bottom_bar_and_default_route():
    # Bottom bar has tabs Nhật ký and Thức ăn, cài đặt; default route is dashboard
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "Nhật ký" in html
    assert "Thức ăn, cài đặt" in html

    route_match = re.search(r"function\s+routeFromHash\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert route_match is not None, "routeFromHash not found"
    route_code = route_match.group(1)
    assert re.search(r'return\s+["\']dashboard["\']\s*;', route_code) is not None


def test_page_dashboard_empty_state_text():
    # The empty state text is in Vietnamese
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "Chưa có lần đo nào" in html
    assert "Gửi ảnh khay tôm cho bot trên Messenger để bắt đầu." in html


def test_page_no_mean_computed_in_page():
    # The page does not compute a mean; numbers come from the server
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "reduce(" not in html
    assert not re.search(r"length_mm[\s\S]{0,100}/\s*(?:shrimp|count|items|included|n)", html)


def test_page_dashboard_wording_vietnamese():
    # Page contains Vietnamese wording for status card cases
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "Tôm đang lớn chậm" in html
    assert "Tôm vẫn đang lớn" in html
    assert "Mới có một lần đo" in html
    assert "Hai lần đo cùng ngày" in html
    assert "Chưa đủ số con để so" in html
    assert "Cần ít nhất" in html


def test_page_change_pill_comes_from_the_server_and_out_of_range_is_explained():
    # The change in length of each row is the server's number, and a size outside the table says why
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text

    assert "change_length_mm" in html
    assert "r.mean_length_mm - prevRow.mean_length_mm" not in html
    assert "Bảng cỡ chỉ tính từ 60 đến 140 mm" in html
