# frontend.py

from kafka import KafkaConsumer
import json
import os
from flask import Flask, jsonify, send_from_directory
from flask_socketio import SocketIO
from threading import Lock

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")

app = Flask(__name__, static_folder=FRONTEND_DIR, static_url_path="")
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")

results = []
weather_results = []
twitter_results = []
results_lock = Lock()


def listen_flood():
    consumer = KafkaConsumer(
        'flood_topic',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='latest',
        group_id='frontend_flood_group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for msg in consumer:
        data = msg.value
        with results_lock:
            results.append(data)
        socketio.emit("new_prediction", data)


def listen_weather():
    consumer = KafkaConsumer(
        'weather_topic',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='latest',
        group_id='frontend_weather_group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for msg in consumer:
        data = msg.value
        weather_results.append(data)
        socketio.emit("new_weather_prediction", data)


def listen_twitter():
    consumer = KafkaConsumer(
        'twitter_topic',
        bootstrap_servers='localhost:9092',
        auto_offset_reset='latest',
        group_id='frontend_twitter_group',
        value_deserializer=lambda x: json.loads(x.decode('utf-8'))
    )

    for msg in consumer:
        data = msg.value
        twitter_results.append(data)
        socketio.emit("new_twitter_prediction", data)


@app.route("/")
def index():
    return send_from_directory(FRONTEND_DIR, "index.html")

@app.route("/api/results")
def get_results():
    with results_lock:
        return jsonify(results[-50:])


if __name__ == "__main__":
    print("Flask Server Running → http://localhost:5000")

    socketio.start_background_task(listen_flood)
    socketio.start_background_task(listen_weather)
    socketio.start_background_task(listen_twitter)

    socketio.run(app, host="0.0.0.0", port=5000, debug=False)