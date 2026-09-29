"""Unit tests for attacker safety stop and demo runner no-retry behavior.

Verifies:
- is_safety_stop_status identifies 429 and 5xx correctly
- ordinary_bot bounded batch scheduling halts on 429/5xx with exit code 3,
  dispatches no further batches, and outputs stderr diagnostic + partial summary
- runner does not retry a SafetyStop step while preserving one retry for ordinary failures
"""
from __future__ import annotations

import http.server
import json
import subprocess
import sys
import threading
from pathlib import Path

from sb.demo.runner import Runner, SafetyStop, StepFailed, fresh_status

REPO = Path(__file__).resolve().parents[4]
ATTACKS_DIR = REPO / "attacks"
if str(ATTACKS_DIR) not in sys.path:
    sys.path.insert(0, str(ATTACKS_DIR))

from common import SAFETY_STOP_EXIT_CODE, is_safety_stop_status  # noqa: E402


class DummyStatusHandler(http.server.BaseHTTPRequestHandler):
    status_to_return = 429
    request_count = 0

    def do_GET(self):
        DummyStatusHandler.request_count += 1
        self.send_response(self.status_to_return)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"status response")

    def log_message(self, format, *args):
        pass  # suppress server log spam


def test_is_safety_stop_status():
    assert is_safety_stop_status(429) is True
    assert is_safety_stop_status("429") is True
    assert is_safety_stop_status(500) is True
    assert is_safety_stop_status(502) is True
    assert is_safety_stop_status(503) is True
    assert is_safety_stop_status(504) is True
    assert is_safety_stop_status("599") is True

    # Non-safety stop statuses
    assert is_safety_stop_status(200) is False
    assert is_safety_stop_status("200") is False
    assert is_safety_stop_status(403) is False
    assert is_safety_stop_status(404) is False
    assert is_safety_stop_status(None) is False
    assert is_safety_stop_status("ERR:RequestException") is False
    assert is_safety_stop_status("") is False


def test_ordinary_bot_safety_stop_and_batch_bounding():
    """Verify ordinary_bot batches at most --threads requests and stops immediately on 429."""
    DummyStatusHandler.status_to_return = 429
    DummyStatusHandler.request_count = 0

    server = http.server.HTTPServer(("127.0.0.1", 0), DummyStatusHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        # Request 10 total requests with threads=2.
        # Without bounded batching, all 10 would be dispatched.
        # With bounded batching, batch 1 (2 requests) finishes, sees 429, and halts.
        proc = subprocess.run(
            [
                sys.executable,
                str(ATTACKS_DIR / "ordinary_bot.py"),
                "--base",
                f"http://127.0.0.1:{port}",
                "--requests",
                "10",
                "--threads",
                "2",
            ],
            cwd=REPO,
            capture_output=True,
            text=True,
            timeout=15,
        )

        assert proc.returncode == SAFETY_STOP_EXIT_CODE, f"expected {SAFETY_STOP_EXIT_CODE}, got {proc.returncode}"
        assert "SAFETY STOP: observed HTTP 429" in proc.stderr
        assert "Phase 10 tradeoff" in proc.stderr

        # Observable stop: only 1 batch (2 requests) dispatched, not all 10
        assert DummyStatusHandler.request_count == 2

        # Partial summary emitted on stdout
        lines = [line for line in proc.stdout.splitlines() if line.startswith("{")]
        assert lines, f"expected JSON summary on stdout, got:\n{proc.stdout}"
        summary = json.loads(lines[-1])
        assert summary["requests"] == 2
        assert summary["status_histogram"].get("429") == 2
    finally:
        server.shutdown()
        server.server_close()


def test_runner_no_retry_on_safety_stop(monkeypatch):
    """Verify Runner.run_step does NOT retry when an attacker encounters a safety stop."""
    status = fresh_status("RUN-test")
    runner = Runner(status)

    call_count = 0

    def mock_safety_stop_handler(deadline: float) -> str:
        nonlocal call_count
        call_count += 1
        raise SafetyStop("ordinary_bot.py safety stop (exit 3): SAFETY STOP: observed HTTP 429")

    monkeypatch.setitem(runner.handlers, 1, mock_safety_stop_handler)

    ok = runner.run_step(1)
    assert ok is False
    # Crucial: exactly 1 attempt made, NO RETRY
    assert call_count == 1
    step = status["steps"][0]
    assert step["status"] == "FAIL"
    assert "safety stop (no retry)" in step["detail"]


def test_runner_retries_on_ordinary_failure(monkeypatch):
    """Verify Runner.run_step still performs one logged retry on ordinary non-safety failures."""
    status = fresh_status("RUN-test")
    runner = Runner(status)

    call_count = 0

    def mock_ordinary_failure_handler(deadline: float) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise StepFailed("ordinary failure on first attempt")
        return "recovered on attempt 2"

    monkeypatch.setitem(runner.handlers, 1, mock_ordinary_failure_handler)

    ok = runner.run_step(1)
    assert ok is True
    # Two attempts made: 1st failed, 2nd passed
    assert call_count == 2
    step = status["steps"][0]
    assert step["status"] == "PASS"
    assert "retrying once" in step["detail"]
    assert "attempt 2 PASS" in step["detail"]


def test_crawler_ignores_absolute_robots_disallow(tmp_path):
    """A robots rule cannot redirect the crawler to another host or port."""
    class RobotsHandler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == "/robots.txt":
                body = b"User-agent: *\nDisallow: http://127.0.0.1:9/internal/\n"
                content_type = "text/plain"
            else:
                body = b"<html><head><title>fixture</title></head><body>local edge fixture</body></html>"
                content_type = "text/html"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), RobotsHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        proc = subprocess.run(
            [
                sys.executable, str(ATTACKS_DIR / "sophisticated_scraper.py"),
                "--base", f"http://127.0.0.1:{server.server_address[1]}",
                "--headless", "--out", str(tmp_path / "scraper.jsonl"),
            ],
            cwd=REPO, capture_output=True, text=True, timeout=90, check=False,
        )
        assert proc.returncode == 0, proc.stderr
        result = json.loads([line for line in proc.stdout.splitlines() if line.startswith("{")][-1])
        assert result["pages"] == 1
        assert all(item["url"].startswith(f"http://127.0.0.1:{server.server_address[1]}/")
                   for item in result["visited"])
    finally:
        server.shutdown()
        server.server_close()
