import json
import queue
import threading
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, HTTPServer

from roadguard.alerting import AlertDispatcher


def test_dispatcher_posts_incident_as_json() -> None:
    received: queue.Queue[dict] = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.put(json.loads(body))
            self.send_response(204)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    dispatcher = AlertDispatcher(f"http://127.0.0.1:{server.server_port}/alerts")
    try:
        dispatcher.start()
        event = {
            "id": 42,
            "label": "accident",
            "confidence": 0.91,
            "source": "camera-1",
        }
        dispatcher.send(event)

        assert received.get(timeout=5) == event
    finally:
        dispatcher.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_dispatcher_posts_sms_to_gateway() -> None:
    received: queue.Queue[tuple[dict, str | None]] = queue.Queue()

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = self.rfile.read(int(self.headers["Content-Length"]))
            received.put((json.loads(body), self.headers.get("Authorization")))
            self.send_response(204)
            self.end_headers()

        def log_message(self, _format: str, *_args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    server_thread = threading.Thread(target=server.serve_forever, daemon=True)
    server_thread.start()
    dispatcher = AlertDispatcher(
        "",
        sms_gateway_url=f"http://127.0.0.1:{server.server_port}/send",
        sms_recipient="+15551234567",
        sms_gateway_token="test-token",
    )
    try:
        dispatcher.start()
        event = {
            "id": 42,
            "label": "accident",
            "confidence": 0.91,
            "source": "camera-1",
        }
        dispatcher.send(event)

        payload, authorization = received.get(timeout=5)
        assert payload["to"] == "+15551234567"
        assert "accident" in payload["message"]
        assert payload["incident"] == event
        assert authorization == "Bearer test-token"
    finally:
        dispatcher.close()
        server.shutdown()
        server.server_close()
        server_thread.join(timeout=2)


def test_dispatcher_sends_email(monkeypatch) -> None:
    sent: list[EmailMessage] = []

    class FakeSMTP:
        def __enter__(self):
            return self

        def __exit__(self, *_args: object) -> None:
            pass

        def login(self, username: str, password: str) -> None:
            assert username == "sender@example.com"
            assert password == "app-password"

        def send_message(self, message: EmailMessage) -> None:
            sent.append(message)

    monkeypatch.setattr(
        "roadguard.alerting.smtplib.SMTP_SSL",
        lambda *args, **kwargs: FakeSMTP(),
    )
    dispatcher = AlertDispatcher(
        "",
        smtp_host="smtp.example.com",
        smtp_username="sender@example.com",
        smtp_password="app-password",
        email_recipient="recipient@example.com",
    )
    try:
        dispatcher.start()
        dispatcher.send(
            {"id": 7, "label": "accident", "confidence": 0.8, "source": "camera"}
        )
        deadline = time.monotonic() + 5
        while not sent and time.monotonic() < deadline:
            time.sleep(0.01)
        assert sent
        assert sent[0]["To"] == "recipient@example.com"
        assert "accident" in sent[0].get_content()
    finally:
        dispatcher.close()
