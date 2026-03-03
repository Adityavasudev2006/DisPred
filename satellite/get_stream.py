import socket
import os

HOST = "0.0.0.0"
PORT = 5001

SAVE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "data", "simulated_stream")
)

os.makedirs(SAVE_DIR, exist_ok=True)

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
server.listen(1)

print("Waiting for sender...")
conn, addr = server.accept()
print(f"Connected from {addr}")

def recv_exact(sock, size):
    data = b""
    while len(data) < size:
        packet = sock.recv(size - len(data))
        if not packet:
            return None
        data += packet
    return data

while True:
    name_len_data = recv_exact(conn, 4)
    if not name_len_data:
        break

    name_len = int.from_bytes(name_len_data, "big")

    filename_bytes = recv_exact(conn, name_len)
    if not filename_bytes:
        break
    filename = filename_bytes.decode()

    img_size_data = recv_exact(conn, 8)
    if not img_size_data:
        break
    img_size = int.from_bytes(img_size_data, "big")

    img_data = recv_exact(conn, img_size)
    if not img_data:
        break

    save_path = os.path.join(SAVE_DIR, filename)
    with open(save_path, "wb") as f:
        f.write(img_data)

    print(f"Received and saved: {filename}")

conn.close()
server.close()