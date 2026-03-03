# weather_stream.py

import time
import random
from kafka import KafkaProducer
import json

def calculate_weather_risk(rain_1h, rain_24h, forecast_6h, humidity):

    intensity_score = min(rain_1h, 100)
    accumulation_score = min(rain_24h / 3, 100)
    forecast_score = min(forecast_6h / 1.5, 100)
    humidity_score = humidity

    weather_risk = (
        0.35 * intensity_score +
        0.30 * forecast_score +
        0.20 * accumulation_score +
        0.15 * humidity_score
    )

    return round(min(weather_risk, 100), 2)


def get_risk_level(score):
    if score > 70:
        return "HIGH", "🔴"
    elif score > 50:
        return "MEDIUM", "🟡"
    else:
        return "LOW", "🟢"


def weather_stream(producer):

    rain_1h = random.uniform(80, 110)
    rain_24h = random.uniform(220, 300)
    forecast_6h = random.uniform(100, 160)
    humidity = random.uniform(90, 100)

    while True:
        try:
            if random.random() < 0.9:

                rain_1h += random.uniform(-5, 5)
                rain_24h += random.uniform(-3, 5)
                forecast_6h += random.uniform(-5, 5)
                humidity += random.uniform(-2, 2)

            else:
                rain_1h -= random.uniform(5, 10)
                forecast_6h -= random.uniform(5, 10)
                humidity -= random.uniform(3, 6)

            rain_1h = max(60, min(rain_1h, 130))
            rain_24h = max(180, min(rain_24h, 350))
            forecast_6h = max(70, min(forecast_6h, 180))
            humidity = max(80, min(humidity, 100))

            weather_score = calculate_weather_risk(
                rain_1h,
                rain_24h,
                forecast_6h,
                humidity
            )

            risk, emoji = get_risk_level(weather_score)

            result = {
                "rainfall_last_1h": round(rain_1h, 2),
                "rainfall_last_24h": round(rain_24h, 2),
                "forecast_rain_6h": round(forecast_6h, 2),
                "humidity": round(humidity, 2),
                "weather_score": weather_score,
                "risk": risk,
                "emoji": emoji,
                "timestamp": time.strftime("%H:%M:%S")
            }

            print(f"{emoji} Weather Risk → {weather_score}% ({risk})")

            producer.send("weather_topic", result)
            producer.flush()

            time.sleep(5)

        except Exception as e:
            print("Weather Stream Error:", e)
            time.sleep(5)