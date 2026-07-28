import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import sys
import pytest
from fastapi import HTTPException, Request, status
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent))

from api.main import app
from api.rate_limiter import RateLimiter, rate_limit_chat, rate_limit_verify, rate_limit_default


def make_mock_request(client_ip: str, path: str = "/chat") -> Request:
    """Build a mock starlette Request object with specified client IP."""
    scope = {
        "type": "http",
        "client": (client_ip, 50000),
        "headers": [
            (b"x-forwarded-for", client_ip.encode("utf-8")),
        ],
        "path": path,
    }
    # Create request using starlette scope
    req = Request(scope)
    return req


@pytest.fixture(autouse=True)
def clear_rate_limiter_histories():
    """Reset the request histories for all preconfigured rate limiters."""
    rate_limit_chat.history.clear()
    rate_limit_verify.history.clear()
    rate_limit_default.history.clear()


def test_rate_limiter_under_limit():
    """Verify that requests under the threshold pass without raising HTTPExceptions."""
    limiter = RateLimiter("TEST_LIMIT_1", default_times=5, default_seconds=2)
    req = make_mock_request("192.168.1.10")

    # 5 requests should pass
    for _ in range(5):
        limiter(req)


def test_rate_limiter_exceeds_limit():
    """Verify that exceeding the threshold raises an HTTP 429 exception with Retry-After header."""
    limiter = RateLimiter("TEST_LIMIT_2", default_times=3, default_seconds=2)
    req = make_mock_request("192.168.1.11")

    # First 3 succeed
    for _ in range(3):
        limiter(req)

    # 4th exceeds and raises 429
    with pytest.raises(HTTPException) as exc_info:
        limiter(req)

    assert exc_info.value.status_code == status.HTTP_429_TOO_MANY_REQUESTS
    assert "Retry-After" in exc_info.value.headers
    # Retry-After should indicate remaining wait time
    retry_after = int(exc_info.value.headers["Retry-After"])
    assert 0 < retry_after <= 2


def test_rate_limiter_resets_after_timeout():
    """Verify that rate limit records expire and reset access after the window passes."""
    limiter = RateLimiter("TEST_LIMIT_3", default_times=2, default_seconds=1)
    req = make_mock_request("192.168.1.12")

    limiter(req)
    limiter(req)

    # 3rd fails
    with pytest.raises(HTTPException):
        limiter(req)

    # Wait for the sliding window of 1s to pass
    time.sleep(1.1)

    # Next request succeeds
    limiter(req)


def test_rate_limiter_ip_isolation():
    """Verify rate-limit state isolation (different IPs maintain independent counters)."""
    limiter = RateLimiter("TEST_LIMIT_4", default_times=2, default_seconds=10)
    req_ip1 = make_mock_request("1.1.1.1")
    req_ip2 = make_mock_request("2.2.2.2")

    # IP 1 hits limit
    limiter(req_ip1)
    limiter(req_ip1)
    with pytest.raises(HTTPException):
        limiter(req_ip1)

    # IP 2 is unaffected and succeeds
    limiter(req_ip2)
    limiter(req_ip2)
    with pytest.raises(HTTPException):
        limiter(req_ip2)


def test_rate_limiter_thread_safety():
    """Verify concurrent requests do not corrupt the internal dict/deque structures."""
    # We set a large times limit to allow multiple successful concurrent additions
    limiter = RateLimiter("TEST_LIMIT_5", default_times=100, default_seconds=5)
    req = make_mock_request("192.168.1.15")

    def call_limiter():
        limiter(req)

    # Run 50 concurrent requests in a thread pool
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(call_limiter) for _ in range(50)]
        for f in futures:
            f.result()  # Should not raise exception or corrupt state

    # Ensure all 50 entries are recorded in history deque
    assert len(limiter.history["192.168.1.15"]) == 50


def test_health_routes_exempt_from_rate_limiting():
    """Verify that health probes do not trigger rate limiting."""
    client = TestClient(app)

    # Hit /health 30 times (which exceeds the default 15 request limit)
    for _ in range(30):
        response = client.get("/health")
        assert response.status_code == 200

    # Hit /health/live 30 times
    for _ in range(30):
        response = client.get("/health/live")
        assert response.status_code == 200
