from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


def validate_accident_classes(
    model_names: dict[int, str] | list[str], accident_classes: frozenset[str]
) -> None:
    names = model_names.values() if isinstance(model_names, dict) else model_names
    available = {str(name).casefold() for name in names}
    if not available.intersection(accident_classes):
        configured = ", ".join(sorted(accident_classes)) or "(none)"
        model_classes = ", ".join(sorted(str(name) for name in names))
        raise RuntimeError(
            f"Model has no configured accident class. ACCIDENT_CLASSES={configured}. "
            f"Model classes: {model_classes}"
        )


@dataclass(frozen=True)
class Detection:
    label: str
    confidence: float
    box: tuple[int, int, int, int]
    is_accident: bool


class AccidentDetector:
    def __init__(
        self,
        model_path: Path,
        accident_classes: frozenset[str],
        confidence: float,
        inference_size: int,
    ) -> None:
        if not model_path.is_file():
            raise FileNotFoundError(
                f"YOLO weights not found: {model_path}. Set MODEL_PATH to your "
                "trained accident-detection .pt file."
            )
        try:
            from ultralytics import YOLO
        except ImportError as exc:
            raise RuntimeError(
                "Ultralytics is not installed. Install dependencies with "
                "'pip install -r requirements.txt'."
            ) from exc

        self.model = YOLO(str(model_path))
        self.accident_classes = accident_classes
        validate_accident_classes(self.model.names, accident_classes)
        self.confidence = confidence
        self.inference_size = inference_size

    def detect(self, frame: Any) -> list[Detection]:
        results = self.model.predict(
            source=frame,
            conf=self.confidence,
            imgsz=self.inference_size,
            verbose=False,
        )
        detections: list[Detection] = []
        for result in results:
            boxes = result.boxes
            if boxes is None:
                continue
            for box in boxes:
                class_id = int(box.cls[0].item())
                names = result.names
                label = str(names[class_id] if isinstance(names, dict) else names[class_id])
                coordinates = tuple(
                    int(round(value)) for value in box.xyxy[0].tolist()
                )
                detections.append(
                    Detection(
                        label=label,
                        confidence=float(box.conf[0].item()),
                        box=coordinates,  # type: ignore[arg-type]
                        is_accident=label.casefold() in self.accident_classes,
                    )
                )
        return detections
