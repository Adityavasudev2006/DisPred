# streaming.py

import os
import sys
import time
import cv2
import torch
import numpy as np
from urllib.parse import urlparse, unquote
from pyspark.sql import SparkSession
from pyspark.sql.functions import input_file_name
from pyspark.sql.types import StructType, StructField, StringType, BinaryType, LongType, TimestampType

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
STREAM_DIR = os.path.join(PROJECT_ROOT, "data", "simulated_stream")
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "spark_checkpoint")

sys.path.insert(0, PROJECT_ROOT)

os.makedirs(STREAM_DIR, exist_ok=True)
os.makedirs(CHECKPOINT_DIR, exist_ok=True)

print(f" Watching directory! : {STREAM_DIR}")


from kafka import KafkaProducer
import json


from ml_models.flood_detection.train import UNet

MODEL_PATH = os.path.join(
    PROJECT_ROOT,
    "ml_models",
    "flood_detection",
    "flood_unet_cpu.pth"
)

model = UNet()
model.load_state_dict(torch.load(MODEL_PATH, map_location="cpu"))
model.eval()

print(" UNet model loaded Succesfully")


spark = SparkSession.builder \
    .appName("FloodImageStreaming") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")


def predict_flood(image_path):
    try:
        image = cv2.imread(image_path)
        if image is None:
            return 0.0

        image = cv2.resize(image, (128, 128))
        image = image / 255.0
        image = np.transpose(image, (2, 0, 1))
        image = torch.tensor(image, dtype=torch.float32).unsqueeze(0)

        with torch.no_grad():
            output = model(image)

        return float(output.mean().item() * 100)

    except Exception as e:
        print(f"Error processing image {image_path}: {e}")
        return 0.0


def get_risk_level(percentage):
    if percentage > 70:
        return "HIGH", "🔴"
    elif percentage > 40:
        return "MEDIUM", "🟡"
    else:
        return "LOW", "🟢"


def process_batch(df, epoch_id, producer):
    rows = df.select("file_path").collect()

    for row in rows:
        raw_path = row["file_path"]

        parsed = urlparse(raw_path)
        path = unquote(parsed.path)

        flood_pct = predict_flood(path)
        filename = os.path.basename(path)
        risk_level, emoji = get_risk_level(flood_pct)

        result = {
            "filename": filename,
            "flood": round(flood_pct, 2),
            "risk": risk_level,
            "emoji": emoji,
            "timestamp": time.strftime("%H:%M:%S"),
            "full_path": path
        }

        print(f"{emoji} {filename} → {flood_pct:.2f}% ({risk_level})")

        producer.send("flood_topic", result)
        producer.flush()


def watch_directory(producer):
    try:
        print("Spark stream started...")

        schema = StructType([
            StructField("path", StringType(), True),
            StructField("modificationTime", TimestampType(), True),
            StructField("length", LongType(), True),
            StructField("content", BinaryType(), True),
        ])

        df = spark.readStream \
            .format("binaryFile") \
            .schema(schema) \
            .option("pathGlobFilter", "*.jpg") \
            .option("recursiveFileLookup", "true") \
            .load(STREAM_DIR) \
            .select(input_file_name().alias("file_path"))

        query = df.writeStream \
            .foreachBatch(lambda df, epoch_id: process_batch(df, epoch_id, producer)) \
            .outputMode("append") \
            .option("checkpointLocation", CHECKPOINT_DIR) \
            .start()

        query.awaitTermination()

    except Exception as e:
        print(" Spark Streaming Error:", e)

        