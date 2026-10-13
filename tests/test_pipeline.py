from pathlib import Path
from unittest.mock import Mock

import pytest

from roadguard.pipeline import AlarmGate, DetectionPipeline, parse_source


def test_parse_source_accepts_camera_index_and_paths() -> None:
    assert parse_source("0") == 0
    assert parse_source(" 2 ") == 2
    assert parse_source("C:\\traffic\\clip.mp4") == "C:\\traffic\\clip.mp4"
    assert parse_source("rtsp://127.0.0.1/live") == "rtsp://127.0.0.1/live"


def test_parse_source_rejects_empty_value() -> None:
    with pytest.raises(ValueError, match="required"):
        parse_source(" ")


def test_camera_preview_does_not_initialize_detector(monkeypatch) -> None:
    capture = Mock()
    capture.isOpened.return_value = True
    capture.read.return_value = (False, None)
    capture_factory = Mock(return_value=capture)
    alerts = Mock()
    detector = Mock(side_effect=AssertionError("preview must not load the detector"))
    monkeypatch.setattr("roadguard.pipeline.cv2.VideoCapture", capture_factory)
    monkeypatch.setattr("roadguard.pipeline.AccidentDetector", detector)
    pipeline = DetectionPipeline(settings=Mock(), store=Mock(), alerts=alerts)

    pipeline.start_preview("0")
    worker = pipeline._thread
    if worker is not None:
        worker.join(timeout=2)

    detector.assert_not_called()
    alerts.start.assert_not_called()
    capture_factory.assert_called_once_with(0)
    capture.read.assert_called_once()
    capture.release.assert_called_once()


def test_alarm_gate_requires_consecutive_hits() -> None:
    gate = AlarmGate(confirm_frames=3, cooldown_seconds=10)
    assert not gate.observe(True, now=100)
    assert not gate.observe(True, now=101)
    assert gate.observe(True, now=102)
    assert not gate.observe(False, now=103)


def test_alarm_gate_can_confirm_first_hit() -> None:
    gate = AlarmGate(confirm_frames=1, cooldown_seconds=60)
    assert gate.observe(True, now=100)
    assert not gate.observe(True, now=101)


def test_alarm_gate_applies_cooldown_and_recovers() -> None:
    gate = AlarmGate(confirm_frames=2, cooldown_seconds=10)
    assert not gate.observe(True, now=100)
    assert gate.observe(True, now=101)
    assert not gate.observe(True, now=105)
    assert not gate.observe(True, now=106)
    assert gate.observe(True, now=111)


def test_accident_class_settings_are_explicit() -> None:
    from roadguard.config import Settings

    settings = Settings.from_environment()
    assert settings.accident_classes
    assert Path(settings.model_path).name.endswith(".pt")
