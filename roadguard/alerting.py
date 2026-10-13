from __future__ import annotations

import json
import logging
import queue
import smtplib
import threading
import urllib.error
import urllib.request
from email.message import EmailMessage
from typing import Any

logger = logging.getLogger(__name__)


class AlertDispatcher:
    def __init__(
        self,
        webhook_url: str,
        *,
        sms_gateway_url: str = "",
        sms_recipient: str = "",
        sms_gateway_token: str = "",
        smtp_host: str = "",
        smtp_port: int = 465,
        smtp_username: str = "",
        smtp_password: str = "",
        email_recipient: str = "",
    ) -> None:
        self.webhook_url = webhook_url
        self.sms_gateway_url = sms_gateway_url
        self.sms_recipient = sms_recipient
        self.sms_gateway_token = sms_gateway_token
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.smtp_username = smtp_username
        self.smtp_password = smtp_password
        self.email_recipient = email_recipient
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue()
        self._thread: threading.Thread | None = None

    @property
    def enabled(self) -> bool:
        return bool(
            self.webhook_url
            or (self.sms_gateway_url and self.sms_recipient)
            or (
                self.smtp_host
                and self.smtp_username
                and self.smtp_password
                and self.email_recipient
            )
        )

    def start(self) -> None:
        if not self.enabled or (self._thread and self._thread.is_alive()):
            return
        self._thread = threading.Thread(
            target=self._run, name="roadguard-alerts", daemon=True
        )
        self._thread.start()

    def send(self, event: dict[str, Any]) -> None:
        if self.enabled:
            self._queue.put(event)
        else:
            logger.warning(
                "Incident %s recorded, but no external alert channel is configured.",
                event.get("id"),
            )

    def close(self) -> None:
        if self._thread and self._thread.is_alive():
            self._queue.put(None)
            self._thread.join(timeout=2)

    def _run(self) -> None:
        while True:
            event = self._queue.get()
            if event is None:
                return
            message = self._message_text(event)
            if self.webhook_url:
                self._post_json(self.webhook_url, event, event, "webhook")
            if self.sms_gateway_url and self.sms_recipient:
                payload = {
                    "to": self.sms_recipient,
                    "message": message,
                    "incident": event,
                }
                headers = {"Content-Type": "application/json"}
                if self.sms_gateway_token:
                    headers["Authorization"] = f"Bearer {self.sms_gateway_token}"
                self._post_json(
                    self.sms_gateway_url, payload, event, "SMS gateway", headers
                )
            if (
                self.smtp_host
                and self.smtp_username
                and self.smtp_password
                and self.email_recipient
            ):
                self._send_email(event, message)

    @staticmethod
    def _message_text(event: dict[str, Any]) -> str:
        return (
            f"RoadGuard accident alert: {event.get('label', 'accident')} detected. "
            f"Confidence: {float(event.get('confidence', 0)):.0%}. "
            f"Source: {event.get('source', 'unknown')}. "
            f"Incident ID: {event.get('id', 'unknown')}."
        )

    @staticmethod
    def _post_json(
        url: str,
        payload: dict[str, Any],
        event: dict[str, Any],
        channel: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        request_headers = {"Content-Type": "application/json"}
        if headers:
            request_headers.update(headers)
        request = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers=request_headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=5) as response:
                if not 200 <= response.status < 300:
                    logger.error(
                        "%s returned HTTP %s for incident %s.",
                        channel,
                        response.status,
                        event.get("id"),
                    )
        except (urllib.error.URLError, TimeoutError, ValueError) as exc:
            logger.error(
                "Could not deliver %s alert for incident %s: %s",
                channel,
                event.get("id"),
                exc,
            )

    def _send_email(self, event: dict[str, Any], message: str) -> None:
        email = EmailMessage()
        email["Subject"] = f"RoadGuard accident alert: {event.get('label', 'accident')}"
        email["From"] = self.smtp_username
        email["To"] = self.email_recipient
        email.set_content(message)
        try:
            with smtplib.SMTP_SSL(self.smtp_host, self.smtp_port, timeout=5) as smtp:
                smtp.login(self.smtp_username, self.smtp_password)
                smtp.send_message(email)
        except (OSError, smtplib.SMTPException, TimeoutError, ValueError) as exc:
            logger.error(
                "Could not deliver email alert for incident %s: %s",
                event.get("id"),
                exc,
            )
