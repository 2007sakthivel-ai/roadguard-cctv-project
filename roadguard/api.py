from __future__ import annotations

import logging
import secrets
from contextlib import asynccontextmanager
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Query
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from roadguard.alerting import AlertDispatcher
from roadguard.config import ROOT_DIR, Settings
from roadguard.pipeline import DetectionPipeline
from roadguard.storage import IncidentStore

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
)

settings = Settings.from_environment()
store = IncidentStore(settings.data_dir)
alerts = AlertDispatcher(
    settings.webhook_url,
    sms_gateway_url=settings.sms_gateway_url,
    sms_recipient=settings.sms_recipient,
    sms_gateway_token=settings.sms_gateway_token,
    smtp_host=settings.smtp_host,
    smtp_port=settings.smtp_port,
    smtp_username=settings.smtp_username,
    smtp_password=settings.smtp_password,
    email_recipient=settings.email_recipient,
)
pipeline = DetectionPipeline(settings, store, alerts)
basic_auth = HTTPBasic(auto_error=False)


def require_auth(
    credentials: Annotated[HTTPBasicCredentials | None, Depends(basic_auth)],
) -> None:
    auth_enabled = settings.public_deployment or bool(settings.app_username)
    if not auth_enabled:
        return
    if credentials is None or not (
        secrets.compare_digest(credentials.username, settings.app_username)
        and secrets.compare_digest(credentials.password, settings.app_password)
    ):
        raise HTTPException(
            status_code=401,
            detail="Authentication required.",
            headers={"WWW-Authenticate": "Basic"},
        )


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    pipeline.stop()
    alerts.close()


app = FastAPI(
    title="RoadGuard",
    description="Real-time road accident detection and emergency alert system.",
    version="1.0.0",
    lifespan=lifespan,
    dependencies=[Depends(require_auth)],
)


class StartRequest(BaseModel):
    source: str = Field(min_length=1, max_length=2048)


@app.get("/", include_in_schema=False)
def dashboard() -> FileResponse:
    return FileResponse(ROOT_DIR / "roadguard" / "static" / "index.html")


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/status")
def get_status() -> dict[str, Any]:
    return pipeline.status()


@app.post("/api/start", status_code=202)
def start_detection(request: StartRequest) -> dict[str, Any]:
    try:
        pipeline.start(request.source)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return pipeline.status()


@app.post("/api/preview", status_code=202)
def start_camera_preview(request: StartRequest) -> dict[str, Any]:
    try:
        pipeline.start_preview(request.source)
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return pipeline.status()


@app.post("/api/stop")
def stop_detection() -> dict[str, Any]:
    pipeline.stop()
    return pipeline.status()


@app.get("/api/events")
def get_events(limit: int = Query(default=50, ge=1, le=200)) -> list[dict[str, Any]]:
    return store.list_recent(limit)


@app.get("/api/events/{incident_id}/snapshot")
def get_snapshot(incident_id: int) -> FileResponse:
    incident = store.get(incident_id)
    if not incident or not incident["snapshot_path"]:
        raise HTTPException(status_code=404, detail="Incident snapshot not found.")
    path = settings.data_dir / incident["snapshot_path"]
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Incident snapshot file is missing.")
    return FileResponse(path, media_type="image/jpeg")


def _mjpeg_frames():
    while True:
        image = pipeline.latest_jpeg()
        if image is None:
            import time

            time.sleep(0.1)
            continue
        yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + image + b"\r\n"
        import time

        time.sleep(0.03)


@app.get("/video_feed")
def video_feed() -> StreamingResponse:
    return StreamingResponse(
        _mjpeg_frames(),
        media_type="multipart/x-mixed-replace; boundary=frame",
        headers={"Cache-Control": "no-store"},
    )
