# OpenMV N6 Ethernet image uploader (PoE)
import binascii
import gc
import hashlib
import json
import os
import time

import csi
import network
import requests

# ----- Configuration ---------------------------------------------------------

BASE_URL = "http://api.eagleshot.org"
STATION_ID = "fa2d76110cd8"
STATION_SECRET_B64 = "Yj7DagG5az05ymWc89CEYqz6eNnyminLP5jNonqp-Jw"
STREAM = ""  # optional camera/stream token for multi-camera stations; "" = the single default camera

UPLOAD_PATH = "/v1/ingest/stations/%s/images" % STATION_ID
DATA_PATH = "/v1/ingest/stations/%s/data" % STATION_ID
CONFIG_PATH = "/v1/ingest/stations/%s/config" % STATION_ID
CLOCK_PATH = "/clock"

# Capture cadence comes from the server config (captureIntervalMinutes). This is
# the fallback used when the config can't be fetched or has no usable value.
DEFAULT_INTERVAL_S = 60 * 60   # 60 minutes


# ----- HMAC-SHA256 request signing -------------------------------------------
# Pure-Python HMAC so it runs where MicroPython ships no `hmac` module. Produces
# the v1 signed-request headers the server expects; the wire format must stay
# byte-for-byte identical to backend/station_hmac.py and the CPython client.

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
    """Pure-Python HMAC-SHA256 (MicroPython doesn't ship `hmac` everywhere)."""
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


def sign_request(station_id, secret_b64, method, path, body, timestamp, nonce_hex=None, x_filename=""):
    """Return the signed-request headers; X-Filename, when given, is signed and returned."""
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
        x_filename,
    )).encode("ascii")
    secret = _b64decode_urlsafe_nopad(secret_b64)
    signature_hex = _hexlify(hmac_sha256(secret, canonical))
    headers = {
        "X-Station-Id": station_id,
        "X-Timestamp": str(int(timestamp)),
        "X-Nonce": nonce_hex,
        "X-Signature": "%s=%s" % (SIGNATURE_VERSION, signature_hex),
    }
    if x_filename:
        headers["X-Filename"] = x_filename
    return headers


# ----- Capture-filename format (server contract) -----------------------------
# Pure integer date math so timestamps stay correct regardless of the board's
# RTC / time.gmtime epoch (STM32 OpenMV cams use a 2000-01-01 epoch, not 1970).

def round_down_to_minute(unix_seconds):
    return int(unix_seconds) - (int(unix_seconds) % 60)


def civil_from_days(z):
    """1970-epoch day count -> (year, month, day)."""
    z = int(z) + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097                                            # [0, 146096]
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365   # [0, 399]
    year = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)                   # [0, 365]
    mp = (5 * doy + 2) // 153                                         # [0, 11]
    day = doy - (153 * mp + 2) // 5 + 1                               # [1, 31]
    month = mp + 3 if mp < 10 else mp - 9                             # [1, 12]
    return (year + (1 if month <= 2 else 0), month, day)


def unix_to_components(unix_seconds):
    """1970-epoch seconds -> (year, month, day, hour, minute, second)."""
    unix_seconds = int(unix_seconds)
    days, rem = unix_seconds // 86400, unix_seconds % 86400
    year, month, day = civil_from_days(days)
    return (year, month, day, rem // 3600, (rem % 3600) // 60, rem % 60)


def format_capture_filename(unix_seconds, camera_name):
    year, month, day, hour, minute, _ = unix_to_components(round_down_to_minute(unix_seconds))
    return "%04d%02d%02d_%02d%02dZ_%s.jpg" % (year, month, day, hour, minute, camera_name)


def format_iso_utc(unix_seconds):
    """unix seconds -> ISO 8601 UTC string, e.g. 2026-06-06T12:04:00Z."""
    year, month, day, hour, minute, second = unix_to_components(int(unix_seconds))
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)

# ----- Camera ----------------------------------------------------------------

def setup_camera():
    """Configure the camera and return it."""
    camera = csi.CSI()
    camera.reset()
    camera.pixformat(csi.RGB565)
    camera.framesize(csi.HD)
    camera.snapshot(time=2000)
    return camera


def capture_jpeg(camera) -> bytes:
    """Capture image as JPEG."""
    jpeg = camera.snapshot().compress(quality=100)
    print("Captured JPEG:", jpeg.size(), "bytes")
    return jpeg

# ----- Network + server ------------------------------------------------------

def api_url(path):
    return BASE_URL + path


def setup_ethernet():
    """Create and activate onboard Ethernet once, at startup.

    Done a single time so we never re-init/toggle the MAC: on the N6 a re-init or
    a warm reset wedges the PHY until a power cycle, so we bring it up once on a
    clean (cold) boot and then leave it alone.
    """
    lan = network.LAN()
    lan.active(True)
    return lan


def wait_for_link(lan):
    """Block until link + DHCP are up, reusing the interface (no tear-down/toggle).

    On a link drop we just wait here for it to come back, so a network outage
    self-heals when connectivity returns -- no reset needed (and none would help,
    since only a power cycle resets the N6 MAC).
    """
    while not lan.isconnected():
        time.sleep_ms(500)
    print("Ethernet up, IP:", lan.ipconfig("addr4"))


def server_unix_seconds():
    """Fetch trusted UTC time from the server's unauthenticated /clock endpoint."""
    response = requests.get(api_url(CLOCK_PATH))
    try:
        return int(response.json()["unixSeconds"])
    finally:
        try:
            response.close()
        except Exception:
            pass


def upload_image(jpeg, filename, timestamp):
    """POST one JPEG as a signed image/jpeg upload. Raises on a non-2xx response."""
    body = bytes(jpeg.bytearray()) if hasattr(jpeg, "bytearray") else bytes(jpeg)
    headers = sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=UPLOAD_PATH,
        body=body,
        timestamp=timestamp,
        x_filename=filename,
    )
    headers["Content-Type"] = "image/jpeg"
    response = requests.post(api_url(UPLOAD_PATH), data=body, headers=headers)
    try:
        if not 200 <= response.status_code < 300:
            raise OSError("image upload failed: HTTP %s" % response.status_code)
    finally:
        try:
            response.close()
        except Exception:
            pass


def upload_sensor_reading(metrics, timestamp):
    """POST signed JSON metrics to the /data endpoint. Raises on a non-2xx response."""
    body = json.dumps(metrics).encode("utf-8")
    headers = sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=DATA_PATH,
        body=body,
        timestamp=timestamp,
    )
    headers["Content-Type"] = "application/json"
    response = requests.post(api_url(DATA_PATH), data=body, headers=headers)
    try:
        if not 200 <= response.status_code < 300:
            raise OSError("sensor upload failed: HTTP %s" % response.status_code)
    finally:
        try:
            response.close()
        except Exception:
            pass


def get_station_config(timestamp):
    """GET the device's signed config. Returns the parsed JSON dict; raises on error."""
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


def capture_interval_from_config(config):
    """Capture interval in seconds from a config dict, or DEFAULT_INTERVAL_S."""
    try:
        minutes = int(config.get("captureIntervalMinutes"))
        if minutes > 0:
            return minutes * 60
    except (TypeError, ValueError):
        pass
    return DEFAULT_INTERVAL_S


def capture_name_token(config):
    """Filename token: the server's frozen name token plus the optional STREAM.

    Keeps the device's capture file in sync with the dashboard download (both are
    '<utc>_<name>[_<stream>]'). Falls back to the station id when the config has no
    name (e.g. the fetch failed).
    """
    name = config.get("name") or STATION_ID
    return name if not STREAM else "%s_%s" % (name, STREAM)


# ----- Application -----------------------------------------------------------

print("Starting:")
camera = setup_camera()
print("* Camera initialized")

lan = setup_ethernet()
print("Ethernet: waiting for link + DHCP...")
wait_for_link(lan)

interval_s = DEFAULT_INTERVAL_S

while True:
    cycle_start = time.ticks_ms()
    try:
        if not lan.isconnected():
            print("Link down, waiting for it to return...")
            wait_for_link(lan)
        now = server_unix_seconds()
        config = fetch_config(now)
        interval_s = capture_interval_from_config(config)
        print("Capture interval: %ds (%d min)" % (interval_s, interval_s // 60))
        jpeg = capture_jpeg(camera)
        filename = format_capture_filename(now, capture_name_token(config))
        upload_image(jpeg, filename, now)
        print("Uploaded", filename)
        # Report online status: timestamp -> last online, nextStart -> next online.
        upload_sensor_reading(
            {"timestamp": format_iso_utc(now),
             "nextStart": format_iso_utc(now + interval_s)},
            now,
        )
    except Exception as exc:
        print("Cycle failed:", exc)
    gc.collect()
    elapsed_s = time.ticks_diff(time.ticks_ms(), cycle_start) // 1000
    time.sleep(max(0, interval_s - elapsed_s))

