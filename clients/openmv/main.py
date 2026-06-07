import binascii
import gc
import hashlib
import os
import sensor
import time
import network
from machine import WDT
try:
    import requests
except ImportError:
    import urequests as requests
BASE_URL = "http://192.168.0.123:3000"
STATION_ID = "8fdf6d13ad32"
STATION_SECRET_B64 = "_BvEeSsUo5PRBExW6Ag5VcGDS0HHsAEJaxHysBtHPJA"
STREAM = ""  # optional camera/stream token for multi-camera stations; "" = the single default camera
UPLOAD_PATH = "/v1/ingest/stations/%s/images" % STATION_ID
CONFIG_PATH = "/v1/ingest/stations/%s/config" % STATION_ID
CLOCK_PATH = "/clock"
CAPTURE_INTERVAL_S = 60
JPEG_QUALITY = 100
WDT_TIMEOUT_MS = 30000
SIGNATURE_VERSION = "v1"
NONCE_BYTES = 16
SHA256_BLOCK_SIZE = 64
def _sha256(data):
    return hashlib.sha256(data).digest()
def _xor_bytes(data, pad):
    result = bytearray(len(data))
    for i in range(len(data)):
        result[i] = data[i] ^ pad
    return bytes(result)
def hmac_sha256(key, msg):
    if len(key) > SHA256_BLOCK_SIZE:
        key = _sha256(key)
    if len(key) < SHA256_BLOCK_SIZE:
        key = key + b"\x00" * (SHA256_BLOCK_SIZE - len(key))
    inner = _sha256(_xor_bytes(key, 0x36) + msg)
    return _sha256(_xor_bytes(key, 0x5c) + inner)
def _b64decode_urlsafe_nopad(value):
    s = value.replace("-", "+").replace("_", "/")
    pad = (-len(s)) % 4
    return binascii.a2b_base64(s + ("=" * pad))
def _hexlify(data):
    return binascii.hexlify(data).decode("ascii")
def sign_request(station_id, secret_b64, method, path, body, timestamp, nonce_hex=None):
    if nonce_hex is None:
        nonce_hex = _hexlify(os.urandom(NONCE_BYTES))
    canonical = "\n".join((
        SIGNATURE_VERSION,
        station_id,
        str(int(timestamp)),
        nonce_hex,
        method.upper(),
        path,
        _hexlify(_sha256(body)),
    )).encode("ascii")
    secret = _b64decode_urlsafe_nopad(secret_b64)
    signature_hex = _hexlify(hmac_sha256(secret, canonical))
    return {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": "%s=%s" % (SIGNATURE_VERSION, signature_hex),
    }
def round_down_to_minute(unix_seconds):
    return int(unix_seconds) - (int(unix_seconds) % 60)
def civil_from_days(z):
    z = int(z) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    year = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    day = doy - (153 * mp + 2) // 5 + 1
    month = mp + 3 if mp < 10 else mp - 9
    return (year + (1 if month <= 2 else 0), month, day)
def unix_to_components(unix_seconds):
    unix_seconds = int(unix_seconds)
    days, rem = unix_seconds // 86400, unix_seconds % 86400
    year, month, day = civil_from_days(days)
    return (year, month, day, rem // 3600, (rem % 3600) // 60, rem % 60)
def format_capture_filename(unix_seconds, camera_name):
    year, month, day, hour, minute, _ = unix_to_components(round_down_to_minute(unix_seconds))
    return "%04d%02d%02d_%02d%02dZ_%s.jpg" % (year, month, day, hour, minute, camera_name)
def sanitize_camera_name(value):
    safe = []
    for char in value.strip():
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "camera"
def setup_camera() -> None:
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.HD)
    sensor.skip_frames(time=2000)
def capture_jpeg() -> bytes:
    jpeg = sensor.snapshot().compress(quality=JPEG_QUALITY)
    print("Captured JPEG:", jpeg.size(), "bytes")
    return jpeg
def api_url(path):
    return BASE_URL + path
def connect_ethernet(wdt):
    lan = network.LAN()
    lan.active(True)
    print("Ethernet: waiting for link + DHCP...")
    while not lan.isconnected():
        wdt.feed()
        time.sleep_ms(500)
    print("Ethernet up, IP:", lan.ipconfig("addr4"))
    return lan
def server_unix_seconds():
    response = requests.get(api_url(CLOCK_PATH))
    try:
        return int(response.json()["unixSeconds"])
    finally:
        try:
            response.close()
        except Exception:
            pass
def get_station_config(timestamp):
    headers = sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="GET",
        path=CONFIG_PATH,
        body=b"",
        timestamp=timestamp,
    )
    response = requests.get(api_url(CONFIG_PATH), headers=headers)
    try:
        if not 200 <= response.status_code < 300:
            raise OSError("config fetch failed: HTTP %s" % response.status_code)
        return response.json()
    finally:
        try:
            response.close()
        except Exception:
            pass
def fetch_config(timestamp):
    """Signed config dict from the server, or {} on any failure."""
    try:
        return get_station_config(timestamp)
    except Exception as exc:
        print("Config fetch failed:", exc)
        return {}
def capture_name_token(config):
    """Filename token: the server's frozen name token plus the optional STREAM.

    Keeps the device's capture file in sync with the dashboard download. Falls back
    to the station id when the config has no name (e.g. the fetch failed).
    """
    name = config.get("name") or STATION_ID
    if not STREAM:
        return name
    return "%s_%s" % (name, sanitize_camera_name(STREAM))
def upload_image(jpeg, filename, timestamp):
    body = bytes(jpeg.bytearray()) if hasattr(jpeg, "bytearray") else bytes(jpeg)
    headers = sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=UPLOAD_PATH,
        body=body,
        timestamp=timestamp,
    )
    headers["Content-Type"] = "image/jpeg"
    headers["X-Filename"] = filename
    response = requests.post(api_url(UPLOAD_PATH), data=body, headers=headers)
    try:
        if not 200 <= response.status_code < 300:
            raise OSError("image upload failed: HTTP %s" % response.status_code)
    finally:
        try:
            response.close()
        except Exception:
            pass
def main():
    print("Starting:")
    wdt = WDT(timeout=WDT_TIMEOUT_MS)
    setup_camera()
    print("CAM SETUP")
    wdt.feed()
    lan = connect_ethernet(wdt)
    while True:
        cycle_start = time.ticks_ms()
        try:
            now = server_unix_seconds()
            config = fetch_config(now)
            jpeg = capture_jpeg()
            filename = format_capture_filename(now, capture_name_token(config))
            upload_image(jpeg, filename, now)
            print("Uploaded", filename)
        except Exception as exc:
            print("Cycle failed:", exc)
            if not lan.isconnected():
                print("Ethernet down, reconnecting...")
                try:
                    lan = connect_ethernet(wdt)
                except Exception as reconnect_exc:
                    print("Reconnect failed:", reconnect_exc)
        gc.collect()
        wdt.feed()
        elapsed_s = time.ticks_diff(time.ticks_ms(), cycle_start) // 1000
        for _ in range(int(max(0, CAPTURE_INTERVAL_S - elapsed_s))):
            wdt.feed()
            time.sleep(1)
if __name__ == "__main__":
    main()
