# analysis.py
import subprocess
import time
import signal
import socket
import os
import shutil
import json
from threading import Thread
from kafka import KafkaProducer
from frontend import app, socketio, listen_flood, listen_weather, listen_twitter
from streaming import watch_directory
from weather_stream import weather_stream
from twitter_stream import twitter_stream


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

STREAM_DIR = os.path.join(PROJECT_ROOT, "data", "simulated_stream")
SPARK_CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "spark_checkpoint")
TWITTER_CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "twitter_checkpoint")

def kill_process_on_port(port):
    try:
        result = subprocess.run(
            ["lsof", "-t", f"-i:{port}"],
            capture_output=True,
            text=True
        )

        if result.stdout:
            pids = result.stdout.strip().split("\n")
            for pid in pids:
                os.kill(int(pid), signal.SIGKILL)
            print(f"Killed process(es) on port {port}")
    except Exception as e:
        print(f"Error killing port {port}: {e}")


def wait_until_port_free(port, timeout=10):
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) != 0:
                return
        time.sleep(0.5)
    raise RuntimeError(f"Port {port} is still in use.")


def clean_start():
    if os.path.exists(STREAM_DIR):
        for file in os.listdir(STREAM_DIR):
            file_path = os.path.join(STREAM_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)

    if os.path.exists(SPARK_CHECKPOINT_DIR):
        shutil.rmtree(SPARK_CHECKPOINT_DIR)

    if os.path.exists(TWITTER_CHECKPOINT_DIR):
        shutil.rmtree(TWITTER_CHECKPOINT_DIR)

    os.makedirs(STREAM_DIR, exist_ok=True)
    os.makedirs(SPARK_CHECKPOINT_DIR, exist_ok=True)
    os.makedirs(TWITTER_CHECKPOINT_DIR, exist_ok=True)

    print("Clean start completed :")

def wait_until_port_open(port, timeout=30):
    start = time.time()
    while time.time() - start < timeout:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("localhost", port)) == 0:
                return
        time.sleep(0.5)
    raise RuntimeError(f"Port {port} did not open in time.")


if __name__ == "__main__":

    print("Cleaning existing processes...")

    kill_process_on_port(2181)
    kill_process_on_port(9092)
    kill_process_on_port(5000)

    wait_until_port_free(2181)
    wait_until_port_free(9092)
    wait_until_port_free(5000)

    ZOOKEEPER_DIR = "/tmp/zookeeper"
    KAFKA_LOG_DIR = "/tmp/kafka-logs"

    if os.path.exists(ZOOKEEPER_DIR):
        shutil.rmtree(ZOOKEEPER_DIR)

    if os.path.exists(KAFKA_LOG_DIR):
        shutil.rmtree(KAFKA_LOG_DIR)

    clean_start()

    KAFKA_DIR = os.path.join(PROJECT_ROOT, "kafka")

    def shutdown(signum, frame):
        print("\nGracefully shutting down...")
        try:
            zk_process.terminate()
            kafka_process.terminate()
        except:
            pass
        exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    print("Starting ZooKeeper...")
    zk_process = subprocess.Popen(
        ["bin/zookeeper-server-start.sh", "config/zookeeper.properties"],
        cwd=KAFKA_DIR
    )

    wait_until_port_open(2181)

    print("Starting Kafka Broker...")
    kafka_process = subprocess.Popen(
        ["bin/kafka-server-start.sh", "config/server.properties"],
        cwd=KAFKA_DIR
    )

    wait_until_port_open(9092)

    print("Kafka started successfully.")

    # ---- Start Producer ----
    producer = KafkaProducer(
        bootstrap_servers="localhost:9092",
        value_serializer=lambda v: json.dumps(v).encode("utf-8")
    )

    Thread(target=watch_directory, args=(producer,), daemon=True).start()
    Thread(target=weather_stream, args=(producer,), daemon=True).start()
    Thread(target=twitter_stream, args=(producer,), daemon=True).start()

    print("Kafka Producers Running...")

    socketio.start_background_task(listen_flood)
    socketio.start_background_task(listen_weather)
    socketio.start_background_task(listen_twitter)

    print("Starting Flask Server → http://localhost:5000")

    socketio.run(app, host="0.0.0.0", port=5000, debug=False)