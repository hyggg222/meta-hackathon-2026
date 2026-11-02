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

    api_paths = set(re.findall(r"/api/[a-zA-Z0-9_\-/]+", html))
    assert len(api_paths) > 0

    for path in api_paths:
        assert path in route_methods, f"Unknown API path: {path}"

    fetch_calls = re.findall(
        r'fetch\(\s*["\'](/api/[^"\']+)["\'](?:\s*,\s*\{[^}]*method:\s*["\']([A-Z]+)["\'])?',
        html,
    )
    assert len(fetch_calls) > 0
    for path, method in fetch_calls:
        effective_method = method if method else "GET"
        assert path in route_methods, f"Unknown path in fetch: {path}"
        assert effective_method in route_methods[path], (
            f"Method {effective_method} not allowed for {path}"
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


