from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent


def _env_int(name: str, default: int, minimum: int = 1) -> int:
    try:
        return max(minimum, int(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_float(name: str, default: float, minimum: float = 0.0) -> float:
    try:
        return max(minimum, float(os.getenv(name, str(default))))
    except ValueError:
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().casefold() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    model_path: Path
    accident_classes: frozenset[str]
    confidence: float
    inference_size: int
    confirm_frames: int
    alert_cooldown_seconds: int
    webhook_url: str
    sms_gateway_url: str
    sms_recipient: str
    sms_gateway_token: str
    smtp_host: str
    smtp_port: int
    smtp_username: str
    smtp_password: str
    email_recipient: str
    data_dir: Path
    host: str
    port: int
    app_username: str
    app_password: str
    public_deployment: bool

    def __post_init__(self) -> None:
        if bool(self.app_username) != bool(self.app_password):
            raise ValueError("Set both APP_USERNAME and APP_PASSWORD, or leave both empty.")
        if self.public_deployment and not self.app_username:
            raise ValueError(
                "Public deployment requires APP_USERNAME and APP_PASSWORD."
            )

    @classmethod
    def from_environment(cls) -> "Settings":
        model_value = os.getenv("MODEL_PATH", "models/accident.pt")
        data_value = os.getenv("DATA_DIR", "data")
        classes = os.getenv("ACCIDENT_CLASSES", "accident,crash,collision")
        return cls(
            model_path=Path(model_value).expanduser()
            if Path(model_value).is_absolute()
            else ROOT_DIR / model_value,
            accident_classes=frozenset(
                item.strip().casefold() for item in classes.split(",") if item.strip()
            ),
            confidence=min(1.0, _env_float("CONFIDENCE_THRESHOLD", 0.45)),
            inference_size=_env_int("INFERENCE_SIZE", 416, 32),
            confirm_frames=_env_int("CONFIRM_FRAMES", 1),
            alert_cooldown_seconds=_env_int("ALERT_COOLDOWN_SECONDS", 60, 0),
            webhook_url=os.getenv("ALERT_WEBHOOK_URL", "").strip(),
            sms_gateway_url=os.getenv("SMS_GATEWAY_URL", "").strip(),
            sms_recipient=os.getenv("SMS_RECIPIENT", "").strip(),
            sms_gateway_token=os.getenv("SMS_GATEWAY_TOKEN", "").strip(),
            smtp_host=os.getenv("SMTP_HOST", "smtp.gmail.com").strip(),
            smtp_port=_env_int("SMTP_PORT", 465),
            smtp_username=os.getenv("SMTP_USERNAME", "").strip(),
            smtp_password=os.getenv("SMTP_PASSWORD", "").strip(),
            email_recipient=os.getenv("ALERT_EMAIL_TO", "").strip(),
            data_dir=Path(data_value).expanduser()
            if Path(data_value).is_absolute()
            else ROOT_DIR / data_value,
            host=os.getenv("HOST", "127.0.0.1"),
            port=_env_int("PORT", 8000),
            app_username=os.getenv("APP_USERNAME", "").strip(),
            app_password=os.getenv("APP_PASSWORD", ""),
            public_deployment=_env_bool("PUBLIC_DEPLOYMENT"),
        )
