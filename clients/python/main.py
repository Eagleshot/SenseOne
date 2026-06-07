# Example: Upload data to the Eagleshot dashboard

from datetime import datetime, timedelta, timezone

from eagleshot import EagleshotClient

BASE_URL = "http://localhost:3000"
STATION_ID = "8fdf6d13ad32"
SECRET_B64 = "_BvEeSsUo5PRBExW6Ag5VcGDS0HHsAEJaxHysBtHPJA"

client = EagleshotClient(base_url=BASE_URL, station_id=STATION_ID, secret_b64=SECRET_B64)

# Check the service is up before sending anything.
print(f"Eagleshot API is online: {client.health()}")

# Send a device check-in: a shared envelope plus one or more per-channel readings.
# Pass a list to report several channels in one signed request; resolved channels
# must be unique. A successful POST returns HTTP 204 (empty body).
status, text = client.send_sensor_reading(
    readings=[
        {"channel": "indoor", "temperature": 21.4, "humidity": 55.0, "battery": 90.0, "custom_metric": 42},
        {"channel": "outdoor", "temperature": 5.1, "humidity": 80.0},
    ],
    timestamp=datetime.now(timezone.utc),
    next_start=(datetime.now(timezone.utc) + timedelta(hours=1)),
    wake_reason="manual",
    firmware_version="python-client-1.0",
)
# Single channel (lands on the "default" channel):
# client.send_sensor_reading({"temperature": 12.5, "battery": 90.0})

# Upload an image (point this at your own .jpg/.png/.webp).
with open(r"C:/Users/Noel/Downloads/device-temp.png", "rb") as image_file:
    image_bytes = image_file.read()

status, text = client.upload_image(image_bytes, content_type="image/jpeg")

print(client.get_config())
