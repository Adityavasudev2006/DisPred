import socket
import os
import time

HOST = "127.0.0.1"
PORT = 5001

BASE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "flood_dataset", "images")
)

images = sorted(
    [f for f in os.listdir(BASE_DIR) if f.lower().endswith(".jpg")],
    key=lambda x: int(os.path.splitext(x)[0])
)

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((HOST, PORT))

print("Connected to receiver.")

for img_name in images:
    img_path = os.path.join(BASE_DIR, img_name)

    with open(img_path, "rb") as f:
        data = f.read()

    client.sendall(len(img_name).to_bytes(4, "big"))
    client.sendall(img_name.encode())

    client.sendall(len(data).to_bytes(8, "big"))
    client.sendall(data)

    print(f"Sent: {img_name}")
    time.sleep(3)

print("All images sent.")
client.close()