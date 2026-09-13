from pathlib import Path

import torch
from ultralytics import YOLO

from config import Config


def yolo_device_arg():
    forced = str(Config.DEVICE)
    if forced == "cuda" and torch.cuda.is_available():
        return 0
    return "cpu"


def main():
    Config.ensure_workspace()
    print("YOLO TRAINING")
    print(f"Using device: {Config.DEVICE}")

    data_yaml = Config.YOLO_DATA_DIR / "data.yaml"
    if not data_yaml.exists():
        raise FileNotFoundError(f"YOLO data.yaml not found: {data_yaml}")

    model = YOLO("yolov8n.pt")

    project_dir = Config.WORKSPACE / "runs" / "detect"
    project_dir.mkdir(parents=True, exist_ok=True)

    model.train(
        data=str(data_yaml),
        epochs=100,
        imgsz=512,
        batch=16,
        device=yolo_device_arg(),
        project=str(project_dir),
        name="train",
        exist_ok=True,
        optimizer="Adam",
        lr0=0.001,
        augment=True,
        mosaic=1.0,
        save=True,
        plots=True,
    )

    print(f"Saved YOLO model to: {Config.YOLO_PATH}")


if __name__ == "__main__":
    main()
