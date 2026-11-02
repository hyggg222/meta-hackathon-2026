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
