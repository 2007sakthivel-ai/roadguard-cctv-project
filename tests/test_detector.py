import pytest

from roadguard.detector import validate_accident_classes


def test_accident_classes_are_matched_case_insensitively() -> None:
    validate_accident_classes(
        {0: "Car", 1: "Accident"},
        frozenset({"accident"}),
    )


def test_missing_accident_class_reports_model_labels() -> None:
    with pytest.raises(RuntimeError, match="Model has no configured accident class") as exc:
        validate_accident_classes(["car", "truck"], frozenset({"accident", "crash"}))

    assert "car, truck" in str(exc.value)
