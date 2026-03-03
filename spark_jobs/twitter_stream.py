# twitter_stream.py

import os
import sys
import time
import torch
from transformers import AutoTokenizer, AutoModelForSequenceClassification

from pyspark.sql import SparkSession
from pyspark.sql.types import StructType, StructField, StringType
from pyspark.sql.functions import col


PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
DATASET_PATH = os.path.join(
    PROJECT_ROOT,
    "data",
    "twitter_data"
)
CHECKPOINT_DIR = os.path.join(PROJECT_ROOT, "twitter_checkpoint")
MODEL_PATH = os.path.join(PROJECT_ROOT, "ml_models", "twitter_model")

sys.path.insert(0, PROJECT_ROOT)

os.makedirs(CHECKPOINT_DIR, exist_ok=True)

print(f"Twitter Spark streaming from: {DATASET_PATH}")


from kafka import KafkaProducer
import json

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
model = AutoModelForSequenceClassification.from_pretrained(MODEL_PATH)

model.to(DEVICE)
model.eval()

print("Twitter model loaded succesfully!!")

spark = SparkSession.builder \
    .appName("TwitterStreaming") \
    .master("local[*]") \
    .getOrCreate()

spark.sparkContext.setLogLevel("ERROR")

def predict(text):
    inputs = tokenizer(
        text,
        return_tensors="pt",
        truncation=True,
        padding=True,
        max_length=128
    )

    inputs = {k: v.to(DEVICE) for k, v in inputs.items()}

    with torch.no_grad():
        outputs = model(**inputs)
        score = outputs.logits.squeeze().item()

    score = max(0, min(score, 1))
    return round(score * 100, 2)


def get_risk_level(score):
    if score > 70:
        return "HIGH", "🔴"
    elif score > 40:
        return "MEDIUM", "🟡"
    else:
        return "LOW", "🟢"

def twitter_stream(producer):
    try:
        print("Twitter Spark simulated real-time stream started...")

        static_df = spark.read \
            .option("header", "true") \
            .csv(os.path.join(DATASET_PATH, "flood_dataset.csv")) \
            .select("Comments")

        comments = [row["Comments"] for row in static_df.collect() if row["Comments"]]
        total = len(comments)

        rate_df = spark.readStream \
            .format("rate") \
            .option("rowsPerSecond", 1) \
            .load()

        def process_batch(df, epoch_id):
            rows = df.collect()

            if rows:
                row = rows[0]
                index = row["value"] % total
                text = comments[index]

                score = predict(text)
                risk, emoji = get_risk_level(score)

                result = {
                    "text": text,
                    "twitter_score": score,
                    "risk": risk,
                    "emoji": emoji,
                    "timestamp": time.strftime("%H:%M:%S")
                }

                print(f"{emoji} Twitter → {score}% ({risk})")
                producer.send("twitter_topic", result)
                producer.flush()

        query = rate_df.writeStream \
            .foreachBatch(process_batch) \
            .outputMode("append") \
            .option("checkpointLocation", CHECKPOINT_DIR) \
            .trigger(processingTime="5 seconds") \
            .start()

        query.awaitTermination()

    except Exception as e:
        print("Twitter Spark Streaming Error:", e)

