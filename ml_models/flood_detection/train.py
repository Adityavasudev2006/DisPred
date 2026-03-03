import os
import cv2
import torch
import numpy as np
from torch import nn
from torch.utils.data import Dataset, DataLoader

class FloodDataset(Dataset):
    def __init__(self, image_dir, mask_dir):
        self.image_dir = image_dir
        self.mask_dir = mask_dir
        all_images = [f for f in os.listdir(image_dir) if f.endswith(".jpg")]
        
        self.images = []
        print(f"Scanning {len(all_images)} files for corruption...")
        
        for img_name in all_images:
            img_path = os.path.join(self.image_dir, img_name)
            base_name = os.path.splitext(img_name)[0]
            mask_name = base_name + ".png"
            mask_path = os.path.join(self.mask_dir, mask_name)

            if not os.path.exists(mask_path):
                continue
            if os.path.getsize(img_path) == 0 or os.path.getsize(mask_path) == 0:
                continue

            img_array = np.fromfile(img_path, np.uint8)
            test_image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            mask_array = np.fromfile(mask_path, np.uint8)
            test_mask = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)

            if test_image is not None and test_mask is not None:
                self.images.append(img_name)
            else:
                print(f"  -> Skipping corrupted file: {img_name}")

        print(f"Data Cleaning Complete: Found {len(self.images)} valid images ready for training.\n")
        
        if len(self.images) == 0:
            raise RuntimeError("CRITICAL: No valid images found. You need to download real image files into your folder!")

    def __len__(self):
        return len(self.images)

    def __getitem__(self, idx):
        img_name = self.images[idx]
        img_path = os.path.join(self.image_dir, img_name)
        mask_path = os.path.join(self.mask_dir, os.path.splitext(img_name)[0] + ".png")

        img_array = np.fromfile(img_path, np.uint8)
        image = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        image = cv2.resize(image, (128,128))
        image = image / 255.0
        image = np.transpose(image, (2,0,1))

        mask_array = np.fromfile(mask_path, np.uint8)
        mask = cv2.imdecode(mask_array, cv2.IMREAD_GRAYSCALE)
        mask = cv2.resize(mask, (128,128))
        mask = mask / 255.0
        mask = np.expand_dims(mask, axis=0)

        return torch.tensor(image, dtype=torch.float32), \
               torch.tensor(mask, dtype=torch.float32)

class DoubleConv(nn.Module):
    def __init__(self, in_c, out_c):
        super().__init__()
        self.conv = nn.Sequential(
            nn.Conv2d(in_c, out_c, 3, padding=1),
            nn.ReLU(),
            nn.Conv2d(out_c, out_c, 3, padding=1),
            nn.ReLU()
        )
    def forward(self, x):
        return self.conv(x)

class UNet(nn.Module):
    def __init__(self):
        super().__init__()
        self.down1 = DoubleConv(3, 32)
        self.pool1 = nn.MaxPool2d(2)
        self.down2 = DoubleConv(32, 64)
        self.pool2 = nn.MaxPool2d(2)

        self.bottleneck = DoubleConv(64, 128)

        self.up1 = nn.ConvTranspose2d(128, 64, 2, 2)
        self.conv1 = DoubleConv(128, 64)
        self.up2 = nn.ConvTranspose2d(64, 32, 2, 2)
        self.conv2 = DoubleConv(64, 32)

        self.final = nn.Conv2d(32, 1, 1)

    def forward(self, x):
        d1 = self.down1(x)
        p1 = self.pool1(d1)
        d2 = self.down2(p1)
        p2 = self.pool2(d2)

        b = self.bottleneck(p2)

        u1 = self.up1(b)
        u1 = torch.cat([u1, d2], dim=1)
        u1 = self.conv1(u1)

        u2 = self.up2(u1)
        u2 = torch.cat([u2, d1], dim=1)
        u2 = self.conv2(u2)

        return torch.sigmoid(self.final(u2))

if __name__ == "__main__":
    device = "cpu"
    BASE_DIR = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", "data", "flood_dataset")
    )

    image_dir = os.path.join(BASE_DIR, "images")
    mask_dir = os.path.join(BASE_DIR, "masks")

    print("Image dir:", image_dir)
    print("Mask dir:", mask_dir)

    dataset = FloodDataset(image_dir, mask_dir)
    
    safe_batch_size = min(4, len(dataset))
    loader = DataLoader(dataset, batch_size=safe_batch_size, shuffle=True)

    model = UNet().to(device)
    optimizer = torch.optim.Adam(model.parameters(), lr=1e-3)
    loss_fn = nn.BCELoss()

    print("Starting training...")
    for epoch in range(15):
        total_loss = 0
        for imgs, masks in loader:
            imgs, masks = imgs.to(device), masks.to(device)
            preds = model(imgs)
            loss = loss_fn(preds, masks)

            optimizer.zero_grad()
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        print(f"Epoch {epoch+1}, Loss: {total_loss}")

    torch.save(model.state_dict(), "flood_unet_cpu.pth")
    print("Model saved successfully as flood_unet_cpu.pth!")


