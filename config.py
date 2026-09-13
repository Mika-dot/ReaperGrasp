import os
from pathlib import Path

import torch


class Config:
    BASE_DIR = Path(__file__).resolve().parent
    WORKSPACE = BASE_DIR / "workspace"

    # Data
    DATA_ROOT = WORKSPACE / "data"
    YOLO_DATA_DIR = DATA_ROOT / "yolo_train"
    NORMAL_DIR = DATA_ROOT / "normal"

    # Model outputs
    YOLO_PATH = WORKSPACE / "runs" / "detect" / "train" / "weights" / "best.pt"
    AE_PATH = WORKSPACE / "autoencoder_model.pth"
    COMPLETE_MODEL_PATH = WORKSPACE / "best_complete_model_fixed.pth"
    HISTORY_PLOT_PATH = WORKSPACE / "training_history_fixed.png"
    AE_LOSS_PLOT_PATH = WORKSPACE / "autoencoder_loss.png"

    # Image sizes
    IMG_SIZE_YOLO = 640
    IMG_SIZE_AE = 224
    SEQ_LENGTH = 16

    # Dimensions
    YOLO_FEATURE_CHANNELS = 256
    AE_EMB_SIZE = 256
    FUSION_SIZE = 512
    LSTM_HIDDEN = 256
    NUM_CLASSES = 5

    # Classes
    YOLO_CLASS_NAMES = ["connection", "foreign object", "garbage", "point"]
    CLASS_NAMES = ["connection", "foreign", "garbage", "point", "normal"]

    # Training
    BATCH_SIZE = 4
    EPOCHS = 50
    LR = 3e-4
    WEIGHT_DECAY = 1e-5
    GRAD_CLIP = 1.0
    CLASS_WEIGHTS = [1.0, 1.0, 1.0, 1.0, 0.3]
    DEFECT_THRESHOLD = 0.5

    @staticmethod
    def resolve_device():
        forced = os.getenv("FORCE_DEVICE", "auto").strip().lower()

        if forced == "cpu":
            return torch.device("cpu")

        if forced in {"cuda", "gpu"}:
            if torch.cuda.is_available():
                return torch.device("cuda")
            return torch.device("cpu")

        return torch.device("cuda" if torch.cuda.is_available() else "cpu")

    DEVICE = resolve_device.__func__()

    @staticmethod
    def ensure_workspace():
        Config.WORKSPACE.mkdir(parents=True, exist_ok=True)
        Config.DATA_ROOT.mkdir(parents=True, exist_ok=True)
        (Config.WORKSPACE / "logs").mkdir(parents=True, exist_ok=True)
        (Config.WORKSPACE / "runs").mkdir(parents=True, exist_ok=True)
        (Config.YOLO_DATA_DIR / "images").mkdir(parents=True, exist_ok=True)
        (Config.YOLO_DATA_DIR / "labels").mkdir(parents=True, exist_ok=True)
        Config.NORMAL_DIR.mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "defect_connection" / "images").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "defect_foreign" / "images").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "defect_garbage" / "images").mkdir(parents=True, exist_ok=True)
        (Config.DATA_ROOT / "defect_point" / "images").mkdir(parents=True, exist_ok=True)
