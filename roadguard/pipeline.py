from __future__ import annotations

import logging
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import cv2

from roadguard.alerting import AlertDispatcher
from roadguard.config import Settings
from roadguard.detector import AccidentDetector, Detection
from roadguard.storage import IncidentStore

logger = logging.getLogger(__name__)


def parse_source(source: str) -> int | str:
    value = source.strip()
    if not value:
        raise ValueError("A camera index, video file, or RTSP URL is required.")
    if value.isdecimal():
        return int(value)
    return value


class AlarmGate:
    def __init__(self, confirm_frames: int, cooldown_seconds: int) -> None:
        self.confirm_frames = confirm_frames
        self.cooldown_seconds = cooldown_seconds
        self.consecutive_frames = 0
        self.last_alarm_at = 0.0

    def observe(self, detected: bool, now: float | None = None) -> bool:
        current_time = time.monotonic() if now is None else now
        self.consecutive_frames = self.consecutive_frames + 1 if detected else 0
        if self.consecutive_frames < self.confirm_frames:
            return False
        if current_time - self.last_alarm_at < self.cooldown_seconds:
            return False
        self.last_alarm_at = current_time
        self.consecutive_frames = 0
        return True


def draw_detections(frame: Any, detections: list[Detection]) -> Any:
    for detection in detections:
        x1, y1, x2, y2 = detection.box
        color = (0, 0, 255) if detection.is_accident else (0, 210, 90)
        label = f"{detection.label} {detection.confidence:.0%}"
        cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
        cv2.putText(
            frame,
            label,
            (x1, max(22, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.6,
            color,
            2,
            cv2.LINE_AA,
        )
    if any(item.is_accident for item in detections):
        cv2.rectangle(frame, (0, 0), (frame.shape[1], 42), (0, 0, 210), -1)
        cv2.putText(
            frame,
            "ACCIDENT DETECTED - VERIFY AND RESPOND",
            (14, 29),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
            cv2.LINE_AA,
        )
    return frame


class DetectionPipeline:
    def __init__(
        self,
        settings: Settings,
        store: IncidentStore,
        alerts: AlertDispatcher,
    ) -> None:
        self.settings = settings
        self.store = store
        self.alerts = alerts
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._capture: cv2.VideoCapture | None = None
        self._latest_jpeg: bytes | None = None
        self._source = ""
        self._state = "stopped"
        self._last_error: str | None = None
        self._fps = 0.0
        self._last_incident: dict[str, Any] | None = None

    def start(self, source_text: str) -> None:
        with self._lock:
            if self._state in {"starting", "running", "previewing"}:
                raise ValueError("Detection is already running.")
            self._state = "starting"
            self._last_error = None
        try:
            source = parse_source(source_text)
            detector = AccidentDetector(
                self.settings.model_path,
                self.settings.accident_classes,
                self.settings.confidence,
                self.settings.inference_size,
            )
            capture = cv2.VideoCapture(source)
            if not capture.isOpened():
                capture.release()
                raise ValueError(
                    f"Could not open video source '{source_text}'. Check the camera, "
                    "file path, or RTSP URL."
                )
        except Exception as exc:
            with self._lock:
                self._state = "error"
                self._last_error = str(exc)
            raise

        self.alerts.start()
        with self._lock:
            self._source = source_text.strip()
            self._capture = capture
            self._stop.clear()
            self._state = "running"
            self._thread = threading.Thread(
                target=self._run, args=(detector,), name="roadguard-video", daemon=True
            )
            self._thread.start()

    def start_preview(self, source_text: str) -> None:
        with self._lock:
            if self._state in {"starting", "running", "previewing"}:
                raise ValueError("A camera source is already running.")
            self._state = "starting"
            self._last_error = None
        try:
            source = parse_source(source_text)
            capture = cv2.VideoCapture(source)
            if not capture.isOpened():
                capture.release()
                raise ValueError(
                    f"Could not open video source '{source_text}'. Check the camera, "
                    "file path, or RTSP URL."
                )
        except Exception as exc:
            with self._lock:
                self._state = "error"
                self._last_error = str(exc)
            raise

        with self._lock:
            self._source = source_text.strip()
            self._capture = capture
            self._latest_jpeg = None
            self._stop.clear()
            self._state = "previewing"
            self._thread = threading.Thread(
                target=self._run_preview, name="roadguard-camera-preview", daemon=True
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            thread = self._thread
            self._stop.set()
        if thread and thread.is_alive():
            thread.join(timeout=5)
        with self._lock:
            if thread and thread.is_alive():
                self._state = "error"
                self._last_error = "Video worker did not stop within five seconds."
                return
            self._state = "stopped"
            self._thread = None
            self._capture = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state": self._state,
                "source": self._source or None,
                "fps": round(self._fps, 1),
                "last_error": self._last_error,
                "last_incident": self._last_incident,
                "alerts_enabled": self.alerts.enabled,
                "model_path": str(self.settings.model_path),
            }

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._latest_jpeg

    def _run(self, detector: AccidentDetector) -> None:
        gate = AlarmGate(
            self.settings.confirm_frames, self.settings.alert_cooldown_seconds
        )
        frame_count = 0
        started_at = time.monotonic()
        capture = self._capture
        if capture is None:
            return
        while not self._stop.is_set():
            ok, frame = capture.read()
            if not ok:
                break
            try:
                detections = detector.detect(frame)
                accident_detections = [item for item in detections if item.is_accident]
                if gate.observe(bool(accident_detections)):
                    self._record_incident(frame, accident_detections)
                annotated = draw_detections(frame, detections)
                encoded, jpeg = cv2.imencode(".jpg", annotated)
                if encoded:
                    with self._lock:
                        self._latest_jpeg = jpeg.tobytes()
                frame_count += 1
                elapsed = time.monotonic() - started_at
                if elapsed >= 1:
                    with self._lock:
                        self._fps = frame_count / elapsed
                    frame_count = 0
                    started_at = time.monotonic()
            except Exception as exc:
                logger.exception("Frame processing failed.")
                with self._lock:
                    self._last_error = f"Frame processing failed: {exc}"
                time.sleep(0.1)

        capture.release()
        with self._lock:
            self._capture = None
            if self._state != "error":
                self._state = "stopped"
            self._thread = None

    def _run_preview(self) -> None:
        capture = self._capture
        if capture is None:
            return
        try:
            while not self._stop.is_set():
                ok, frame = capture.read()
                if not ok:
                    break
                encoded, jpeg = cv2.imencode(".jpg", frame)
                if encoded:
                    with self._lock:
                        self._latest_jpeg = jpeg.tobytes()
        except Exception as exc:
            logger.exception("Camera preview failed.")
            with self._lock:
                self._last_error = f"Camera preview failed: {exc}"
                self._state = "error"
        finally:
            capture.release()
            with self._lock:
                self._capture = None
                if self._state != "error":
                    self._state = "stopped"
                self._thread = None

    def _record_incident(self, frame: Any, detections: list[Detection]) -> None:
        strongest = max(detections, key=lambda item: item.confidence)
        timestamp = time.strftime("%Y%m%d-%H%M%S", time.gmtime())
        snapshot = self.store.snapshot_dir / f"incident-{timestamp}-{uuid.uuid4().hex[:8]}.jpg"
        saved_path: str | None = None
        if cv2.imwrite(str(snapshot), frame):
            saved_path = str(Path("snapshots") / snapshot.name)
        incident = self.store.create(
            source=self._source,
            label=strongest.label,
            confidence=strongest.confidence,
            snapshot_path=saved_path,
        )
        with self._lock:
            self._last_incident = incident
        self.alerts.send(incident)
