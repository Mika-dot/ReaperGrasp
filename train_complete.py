import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import torch
import torch.nn as nn
import torch.optim as optim
from tqdm import tqdm

from config import Config
from complete_model import CompleteDefectDetector
from dataset import create_dataloaders


class Trainer:
    def __init__(self):
        self.device = Config.DEVICE
        self.model = CompleteDefectDetector().to(self.device)

        class_weights = torch.tensor(
            Config.CLASS_WEIGHTS,
            dtype=torch.float32,
            device=self.device,
        )
        self.criterion = nn.NLLLoss(weight=class_weights)

        trainable_params = [p for p in self.model.parameters() if p.requires_grad]
        self.optimizer = optim.Adam(
            trainable_params,
            lr=Config.LR,
            weight_decay=Config.WEIGHT_DECAY,
        )

        self.scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            self.optimizer,
            mode="min",
            patience=4,
            factor=0.5,
        )

        self.history = {
            "train_loss": [],
            "val_loss": [],
            "train_acc": [],
            "val_acc": [],
        }

        print(f"\nComplete model training on: {self.device}")
        self._count_parameters()

    def _count_parameters(self):
        total = sum(p.numel() for p in self.model.parameters())
        trainable = sum(p.numel() for p in self.model.parameters() if p.requires_grad)
        print(f"Total parameters: {total:,}")
        print(f"Trainable parameters: {trainable:,}")

    def train_one_epoch(self, loader):
        self.model.train()
        total_loss = 0.0
        correct = 0
        total = 0

        for sequences, labels in tqdm(loader, desc="Train"):
            sequences = sequences.to(self.device)
            labels = labels.to(self.device)

            self.optimizer.zero_grad(set_to_none=True)
            output = self.model(sequences)
            loss = self.criterion(output["log_probs"], labels)

            loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), Config.GRAD_CLIP)
            self.optimizer.step()

            total_loss += loss.item()
            preds = torch.argmax(output["log_probs"], dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

        return total_loss / max(1, len(loader)), correct / max(1, total)

    @torch.no_grad()
    def validate(self, loader):
        self.model.eval()
        total_loss = 0.0
        correct = 0
        total = 0

        for sequences, labels in tqdm(loader, desc="Val"):
            sequences = sequences.to(self.device)
            labels = labels.to(self.device)

            output = self.model(sequences)
            loss = self.criterion(output["log_probs"], labels)

            total_loss += loss.item()
            preds = torch.argmax(output["log_probs"], dim=1)
            correct += (preds == labels).sum().item()
            total += labels.size(0)

        return total_loss / max(1, len(loader)), correct / max(1, total)

    def train(self):
        train_loader, val_loader = create_dataloaders()
        best_val_loss = float("inf")

        for epoch in range(Config.EPOCHS):
            print(f"\n{'=' * 60}")
            print(f"Epoch {epoch + 1}/{Config.EPOCHS}")

            train_loss, train_acc = self.train_one_epoch(train_loader)
            val_loss, val_acc = self.validate(val_loader)

            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_acc"].append(val_acc)

            self.scheduler.step(val_loss)

            print(f"Train Loss: {train_loss:.4f} | Acc: {train_acc:.4f}")
            print(f"Val   Loss: {val_loss:.4f} | Acc: {val_acc:.4f}")

            if val_loss < best_val_loss:
                best_val_loss = val_loss
                torch.save(
                    {
                        "model_state_dict": self.model.state_dict(),
                        "history": self.history,
                    },
                    Config.COMPLETE_MODEL_PATH,
                )
                print(f"Saved best complete model to: {Config.COMPLETE_MODEL_PATH}")

        self.plot_history()

    def plot_history(self):
        fig, axes = plt.subplots(1, 2, figsize=(12, 4))

        axes[0].plot(self.history["train_loss"], label="Train")
        axes[0].plot(self.history["val_loss"], label="Val")
        axes[0].set_title("Loss")
        axes[0].legend()
        axes[0].grid(True)

        axes[1].plot(self.history["train_acc"], label="Train")
        axes[1].plot(self.history["val_acc"], label="Val")
        axes[1].set_title("Accuracy")
        axes[1].legend()
        axes[1].grid(True)

        plt.tight_layout()
        plt.savefig(Config.HISTORY_PLOT_PATH)
        plt.close()
        print(f"Saved training history plot to: {Config.HISTORY_PLOT_PATH}")


def main():
    Config.ensure_workspace()
    print("COMPLETE MODEL TRAINING")
    print(f"Using device: {Config.DEVICE}")
    print(f"YOLO weights path: {Config.YOLO_PATH}")
    print(f"Autoencoder weights path: {Config.AE_PATH}")
    print(f"Complete model output: {Config.COMPLETE_MODEL_PATH}")

    trainer = Trainer()
    trainer.train()


if __name__ == "__main__":
    main()
