# Tests for static HTML page labels, routes and safety
import re
from fastapi.testclient import TestClient

from shrimp.app import create_app
from tests.test_app import make_test_service


def test_page_screen_labels():
    # GET / serves HTML containing the three screen labels and disclaimer
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "Photo" in html
    assert "Feed + setup" in html
    assert "Dashboard" in html
    assert "temporary table, not the CP table" in html


def test_page_api_routes():
    # Every /api/ path in the page matches a valid route and method in app.routes
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
    # Page does not append via innerHTML and has no external http/https requests
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert not re.search(r"innerHTML\s*\+=", html), "Found innerHTML += in page"
    assert "http://" not in html
    assert "https://" not in html


def test_page_body_background():
    # The body rule does not use the gray --page variable
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    match = re.search(r"body\s*\{([^}]+)\}", html)
    assert match is not None, "body rule not found in style"
    body_style = match.group(1)
    assert not re.search(r"background[^;]*--page", body_style), (
        "body background must not reference --page"
    )


def test_page_hash_navigation():
    # The served HTML mentions hashchange and the three fragment names photo, feed, dashboard
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "hashchange" in html
    assert "photo" in html
    assert "feed" in html
    assert "dashboard" in html


def test_page_per_kg_text_helper():
    # The HTML contains helper perKgText using Math.round
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "perKgText" in html
    match = re.search(r"function\s+perKgText\s*\([^)]*\)\s*\{[\s\S]*?\}", html)
    assert match is not None, "function perKgText not found"
    assert "Math.round" in match.group(0), "perKgText must use Math.round"


def test_page_chart_date_label_anchors():
    # Chart code contains both text-anchor="start" and text-anchor="end" for date labels
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    chart_match = re.search(
        r"function\s+renderDashboardChart[\s\S]*?function\s+renderDashboardSamplesTable",
        script,
    )
    assert chart_match is not None, "renderDashboardChart function not found"
    chart_code = chart_match.group(0)

    assert 'text-anchor="start"' in chart_code
    assert 'text-anchor="end"' in chart_code
    assert re.search(r'text-anchor="start"[^>]*>\$\{lab\(', chart_code) or (
        re.search(r'text-anchor="start"[\s\S]*?\$\{lab\(', chart_code)
    )
    assert re.search(r'text-anchor="end"[^>]*>\$\{lab\(', chart_code) or (
        re.search(r'text-anchor="end"[\s\S]*?\$\{lab\(', chart_code)
    )


def test_page_in_flight_guard_and_request_counter():
    # In-flight guard and request counter in script
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "inFlight" in html
    assert "requestId" in html


def test_page_parse_number():
    # Helper parseNumber on form values and no Number in submit handlers
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert re.search(r"function\s+parseNumber\s*\(", html) is not None
    assert html.count("parseNumber(") >= 6
    assert "Type a plain number, for example 100 or 45000." in html

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


def test_page_numbers_from_server():
    # Growth and threshold numbers from server without JS division
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "growth_mm_per_day" in html
    assert "stall_threshold_mm_per_day" in html
    assert "harvest_threshold_per_kg" in html
    assert "change_length_mm / " not in html
    assert "/ d.days_between" not in html
    assert "the minimum" in html


def test_page_not_enough_shrimp_text():
    # Not enough shrimp text names both counts
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "needed in each" in html


def test_page_chart_label_gap():
    # Chart code maintains minimum 56 unit gap between date labels
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "// label gap" in html


def test_page_feed_screen_edited_flags():
    # Feed defaults refresh tracking edited flags
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "feedDateEdited" in html
    assert "feedPriceEdited" in html


def test_page_no_reference_and_no_shrimp_count_line():
    # Show measured and left out count line for no_reference and no_shrimp
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    left_out_positions = [m.start() for m in re.finditer(r"left out", html)]
    assert any(
        "no_reference" in html[max(0, p - 800) : p + 800]
        and "no_shrimp" in html[max(0, p - 800) : p + 800]
        for p in left_out_positions
    )


def test_page_review_nits():
    # Lowercase table range mid-sentence and 200 render error message
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "outside the table range: no size per kg" in html
    assert "Outside the table range: no size per kg" not in html
    assert "The photo was saved, but the result could not be shown." in html


def test_page_photo_routes_and_no_samples():
    # The script posts to /api/analyses, summary, and save, and no longer posts to /api/samples
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert not re.search(r'fetch\(\s*[`"\']/api/samples', html)
    assert "/api/analyses" in html

    fetch_calls = re.findall(
        r'fetch\(\s*[`"\'](/api/[^`"\']+)[`"\'](?:\s*,\s*\{[^}]*method:\s*[`"\']([A-Z]+)[`"\'])?',
        html,
    )
    posted_paths = {
        re.sub(r"\$\{[^}]+\}", "{analysis_id}", path)
        for path, method in fetch_calls
        if method == "POST"
    }
    assert "/api/analyses" in posted_paths
    assert "/api/analyses/{analysis_id}/summary" in posted_paths
    assert "/api/analyses/{analysis_id}/save" in posted_paths
    assert "/api/samples" not in posted_paths


def test_page_photo_overlay_and_choice_elements():
    # The script builds polygon from outline, polyline from path, aria-pressed, and checkbox rows
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "<polygon" in html
    assert "outline" in html
    assert "<polyline" in html
    assert "path" in html
    assert "aria-pressed" in html
    assert 'type="checkbox"' in html


def test_page_photo_labels_and_hint():
    # Overlay has left out and cm labels, Measure photo, Save sample, and Tap a shrimp hint
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "left out" in html
    assert " cm" in html
    assert "Measure photo" in html
    assert "Save sample" in html
    assert "Tap a shrimp" in html


def test_page_summary_in_flight_guard():
    # Summary call has in-flight guard, request counter, and latest summary wins comment
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "// latest summary wins" in html
    match = re.search(
        r"// latest summary wins\s*\n\s*(?:const|let|var)\s+(\w+)",
        html,
    )
    assert match is not None
    var_name = match.group(1).lower()
    assert "summary" in var_name or "request" in var_name


def test_page_no_mean_computed_in_page():
    # The page does not compute a mean; numbers come from the server
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "reduce(" not in html
    assert not re.search(r"length_mm[\s\S]{0,100}/\s*(?:shrimp|count|items|included|n)", html)


def test_page_dashboard_wording():
    # Page contains Growth looks slow, Growth is not slow, and needed in each
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "Growth looks slow" in html
    assert "Growth is not slow" in html
    assert "needed in each" in html


def test_page_dashboard_no_stall_wording_and_setup_label():
    # Dashboard script has no Stall flag or >stall< text, and setup label is updated
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    dash_match = re.search(
        r"function\s+renderDashboardChart[\s\S]*?function\s+saveFeedHandler",
        script,
    )
    assert dash_match is not None, "dashboard code block not found"
    dash_code = dash_match.group(0)

    assert "Stall flag" not in dash_code
    assert ">stall<" not in dash_code
    assert "Growth looks slow under" in html


def test_page_dashboard_growth_strip_and_table():
    # Dashboard script uses growth_mm_per_day for strip and table rows, mm/day header, strip and costrow classes
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert ".strip" in html
    assert ".costrow" in html
    assert "<th>mm/day</th>" in html

    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    dash_match = re.search(
        r"function\s+renderDashboardChart[\s\S]*?function\s+saveFeedHandler",
        script,
    )
    assert dash_match is not None, "dashboard code block not found"
    dash_code = dash_match.group(0)

    assert dash_code.count("growth_mm_per_day") >= 2


def test_page_dashboard_chart_elements():
    # Chart code contains text-anchor start and end, // label gap, and #8a5a00
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    chart_match = re.search(
        r"function\s+renderDashboardChart[\s\S]*?function\s+renderDashboardSamplesTable",
        script,
    )
    assert chart_match is not None, "renderDashboardChart function not found"
    chart_code = chart_match.group(0)

    assert 'text-anchor="start"' in chart_code
    assert 'text-anchor="end"' in chart_code
    assert "// label gap" in chart_code
    assert "#8a5a00" in chart_code


def test_page_no_growth_threshold_comparison():
    # No comparison of growth with a threshold in JS
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    script_match = re.search(r"<script>([\s\S]*?)</script>", html)
    assert script_match is not None, "<script> tag not found"
    script = script_match.group(1)

    assert "< d.stall_threshold" not in script
    assert not re.search(r"[<>]=?\s*d\.stall_threshold", script)


def test_page_dash_enter_feed_button():
    # dash-enter-feed-btn still exists in HTML
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert 'id="dash-enter-feed-btn"' in html





