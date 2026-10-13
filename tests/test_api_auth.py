from dataclasses import replace

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPBasicCredentials

from roadguard import api


def test_public_dashboard_requires_login(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "settings",
        replace(
            api.settings,
            app_username="operator",
            app_password="strong-password",
            public_deployment=True,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        api.require_auth(None)

    assert exc.value.status_code == 401
    assert exc.value.headers == {"WWW-Authenticate": "Basic"}


def test_public_dashboard_accepts_configured_login(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "settings",
        replace(
            api.settings,
            app_username="operator",
            app_password="strong-password",
            public_deployment=True,
        ),
    )

    api.require_auth(
        HTTPBasicCredentials(username="operator", password="strong-password")
    )


def test_public_dashboard_rejects_wrong_password(monkeypatch) -> None:
    monkeypatch.setattr(
        api,
        "settings",
        replace(
            api.settings,
            app_username="operator",
            app_password="strong-password",
            public_deployment=True,
        ),
    )

    with pytest.raises(HTTPException) as exc:
        api.require_auth(
            HTTPBasicCredentials(username="operator", password="wrong-password")
        )

    assert exc.value.status_code == 401
