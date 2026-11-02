# Tests for static HTML page labels, routes and safety
import re
from fastapi.testclient import TestClient

from shrimp.app import create_app
from tests.test_app import make_test_service


def test_page_screen_labels():
    # GET / serves HTML containing screen labels and disclaimer
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

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
    # The served HTML mentions hashchange and the fragment names feed, dashboard
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    resp = client.get("/")
    assert resp.status_code == 200
    html = resp.text

    assert "hashchange" in html
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
    assert "/api/samples" not in html


def test_page_app_bar_and_default_route():
    # App bar has buttons Dashboard and Feed + setup and no Photo; default route is dashboard
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    appbar_match = re.search(r'<nav class="appbar"[^>]*>([\s\S]*?)</nav>', html)
    assert appbar_match is not None, "appbar not found"
    appbar = appbar_match.group(1)

    assert "Dashboard" in appbar
    assert "Feed + setup" in appbar
    assert "Photo" not in appbar

    route_match = re.search(r"function\s+routeFromHash\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert route_match is not None, "routeFromHash not found"
    route_code = route_match.group(1)
    assert re.search(r'return\s+["\']dashboard["\']\s*;', route_code) is not None


def test_page_dashboard_empty_state_text():
    # The empty state text Send a photo of your tray to the bot on Messenger is in the script
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert "Send a photo of your tray to the bot on Messenger" in html


def test_page_setup_min_length_field():
    # Setup form has setup-min-length input, label Shortest shrimp that counts, and script reads/writes min_length_mm with parseNumber(
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text
    assert 'id="setup-min-length"' in html
    assert "Shortest shrimp that counts" in html
    assert "min_length_mm" in html

    load_match = re.search(r"async\s+function\s+loadSettings\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert load_match is not None, "loadSettings not found"
    assert "min_length_mm" in load_match.group(1)

    save_match = re.search(r"async\s+function\s+saveSetupHandler\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert save_match is not None, "saveSetupHandler not found"
    save_code = save_match.group(1)
    assert "min_length_mm" in save_code
    assert "parseNumber(" in save_code


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







def test_page_num_class_is_not_a_round_badge():
    # The numbers in the dashboard use class num for tabular digits, never a round badge
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text

    for rule in re.findall(r"(?m)^\s*(?:\.dash\s+)?\.num[^{]*\{([^}]*)\}", html):
        assert "border-radius:50%" not in rule
        assert "width:28px" not in rule


def test_page_says_unclear_when_samples_are_too_noisy():
    # The dashboard shows the server's "unclear" verdict with what would settle it
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text

    assert "Not clear yet" in html
    assert "stall_unclear" in html
    assert "growth_se_mm_per_day" in html
    assert "shrimp_needed" in html
    assert "days_needed" in html
    # the page never decides: no growth-versus-threshold comparison in the script
    assert not re.search(r"[<>]=?\s*d\.stall_threshold", html)


def test_page_dashboard_pricing_card_and_ration_setup():
    # The dashboard contains pricing card text and setup form has ration field with parseNumber(
    service = make_test_service()
    app = create_app(service)
    client = TestClient(app)

    html = client.get("/").text

    assert "usually pays about" in html
    assert "Feed alone breaks even above" in html
    assert "default price table" in html

    # Setup form ration field
    assert 'id="setup-ration"' in html
    assert "Feed per day (percent of shrimp weight)" in html
    assert "About 1.5 at 25 g. Used only for the break-even line." in html
    assert "ration_pct" in html

    # parseNumber used for ration
    load_match = re.search(r"async\s+function\s+loadSettings\s*\(\)\s*\{([\s\S]*?)\}", html)
    assert load_match is not None
    assert "ration_pct" in load_match.group(1)

    save_match = re.search(
        r"async\s+function\s+saveSetupHandler[\s\S]*?document\.addEventListener",
        html,
    )
    assert save_match is not None
    save_code = save_match.group(0)
    assert "ration_pct" in save_code
    assert re.search(r"parseNumber\(\s*rationInput\.value", save_code) is not None

