from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import DataLoader, Dataset
from tqdm import tqdm

from config import Config


class NormalDataset(Dataset):
    def __init__(self, normal_dir=None, img_size=224):
        self.normal_dir = Path(normal_dir or Config.NORMAL_DIR)
        self.images = (
            list(self.normal_dir.glob("*.jpg")) +
            list(self.normal_dir.glob("*.jpeg")) +
            list(self.normal_dir.glob("*.png")) +
            list(self.normal_dir.glob("*.bmp")) +
            list(self.normal_dir.glob("*.webp"))
        )
        self.img_size = img_size

        if len(self.images) == 0:
            raise FileNotFoundError(f"No normal images found in {self.normal_dir}")

        print(f"Loaded normal images: {len(self.images)} from {self.normal_dir}")

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_path = self.images[idx]
        img = cv2.imread(str(img_path))
        if img is None:
            raise ValueError(f"Could not read image: {img_path}")

        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        img = cv2.resize(img, (self.img_size, self.img_size))
        img = img.astype(np.float32) / 255.0
        img = torch.from_numpy(img).permute(2, 0, 1)
        return img, img


class Autoencoder(nn.Module):
    def __init__(self, latent_dim=256):
        super().__init__()

        self.encoder = nn.Sequential(
            nn.Conv2d(3, 32, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(32),

            nn.Conv2d(32, 64, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(64),

            nn.Conv2d(64, 128, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(128),

            nn.Conv2d(128, 256, kernel_size=3, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(256),

            nn.AdaptiveAvgPool2d((1, 1)),
            nn.Flatten(),
            nn.Linear(256, latent_dim),
        )

        self.decoder = nn.Sequential(
            nn.Linear(latent_dim, 14 * 14 * 128),
            nn.ReLU(),
            nn.Unflatten(1, (128, 14, 14)),

            nn.ConvTranspose2d(128, 64, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(64),

            nn.ConvTranspose2d(64, 32, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),
            nn.BatchNorm2d(32),

            nn.ConvTranspose2d(32, 16, kernel_size=4, stride=2, padding=1),
            nn.ReLU(),

            nn.ConvTranspose2d(16, 3, kernel_size=4, stride=2, padding=1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        latent = self.encoder(x)
        reconstructed = self.decoder(latent)
        return reconstructed, latent

    def get_embedding(self, x):
        return self.encoder(x)


def main():
    Config.ensure_workspace()
    print("AUTOENCODER TRAINING")

    device = Config.DEVICE
    print(f"Using device: {device}")

    dataset = NormalDataset(img_size=Config.IMG_SIZE_AE)
    dataloader = DataLoader(dataset, batch_size=32, shuffle=True, num_workers=0)

    model = Autoencoder(latent_dim=Config.AE_EMB_SIZE).to(device)
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    criterion = nn.MSELoss()

    history = {"loss": []}

    for epoch in range(100):
        model.train()
        total_loss = 0.0

        for inputs, targets in tqdm(dataloader, desc=f"AE epoch {epoch + 1}"):
            inputs, targets = inputs.to(device), targets.to(device)

            reconstructed, _ = model(inputs)
            loss = criterion(reconstructed, targets)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()

            total_loss += loss.item()

        avg_loss = total_loss / max(1, len(dataloader))
        history["loss"].append(avg_loss)
        print(f"Epoch {epoch + 1}/100 - loss: {avg_loss:.6f}")

    save_path = Path(Config.AE_PATH)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "latent_dim": Config.AE_EMB_SIZE,
            "history": history,
        },
        save_path,
    )

    plt.figure(figsize=(10, 5))
    plt.plot(history["loss"])
    plt.title("Autoencoder Training Loss")
    plt.xlabel("Epoch")
    plt.ylabel("MSE Loss")
    plt.grid(True)
    plt.tight_layout()
    plt.savefig(Config.AE_LOSS_PLOT_PATH)
    plt.close()

    print("\nAUTOENCODER TRAINED")
    print(f"Saved model to: {save_path}")
    print(f"Saved loss plot to: {Config.AE_LOSS_PLOT_PATH}")


if __name__ == "__main__":
    main()
