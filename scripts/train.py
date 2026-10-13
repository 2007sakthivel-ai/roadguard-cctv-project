from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Train a YOLO accident detector using an Ultralytics dataset YAML."
    )
    parser.add_argument("--data", required=True, help="Path to dataset YAML.")
    parser.add_argument("--model", default="yolo11n.pt", help="Base YOLO model or weights.")
    parser.add_argument("--epochs", type=int, default=100)
    parser.add_argument("--imgsz", type=int, default=640)
    parser.add_argument("--device", default=None, help="For example: 0, cpu, or mps.")
    parser.add_argument("--project", default="runs/roadguard")
    parser.add_argument("--name", default="accident")
    args = parser.parse_args()

    model = YOLO(args.model)
    options = {
        "data": args.data,
        "epochs": args.epochs,
        "imgsz": args.imgsz,
        "project": args.project,
        "name": args.name,
    }
    if args.device:
        options["device"] = args.device
    model.train(**options)
    best_weights = Path(model.trainer.best)
    if not best_weights.is_file():
        raise FileNotFoundError(f"Training completed but best weights are missing: {best_weights}")
    print(f"Training complete. Best weights: {best_weights}")


if __name__ == "__main__":
    main()
