# OpenMV N6 cellular image uploader for a SIM7670E / A7670E modem.
#
# Single-file firmware: HMAC signing, modem driver, clock/scheduling, and
# capture cycle are all in this module so only main.py needs to be copied
# to the board.
#
# Wiring:
# - OpenMV P4/TX -> modem RX
# - OpenMV P5/RX -> modem TX
# - OpenMV GND   -> modem GND
#
# Auth: HMAC-SHA256 request signing. The shared secret never leaves the
# device; each request is signed with a unix timestamp + random nonce and
# replayed once at the server. Safe over plain HTTP because the modem
# can't reliably do TLS on this network.
#
# Provisioning: in the server admin UI, POST /stations/<id>/rotate-device-secret
# and paste the returned secret into STATION_SECRET_B64 below.

import binascii
import gc
import hashlib
import json
import machine
import os
import sensor
import time

from pyb import UART


# ----- Station configuration -------------------------------------------------

API_HOST = "api.eagleshot.org"
API_SCHEME = "http"
STATION_ID = "silvretta-glacier"
STATION_SECRET_B64 = "REPLACE-WITH-PROVISIONED-DEVICE-SECRET"
CAMERA_NAME = "front"
FIRMWARE_VERSION = "1.0.0"

UPLOAD_PATH = "/device/stations/%s/images" % STATION_ID
SENSOR_READINGS_PATH = "/device/stations/%s/sensor-readings" % STATION_ID
CONFIG_PATH = "/device/stations/%s/config" % STATION_ID
CLOCK_PATH = "/clock"

JPEG_QUALITY = 100
JPEG_MIN_QUALITY = 35
JPEG_QUALITY_STEP = 10


# ----- Modem configuration ---------------------------------------------------

UART_BUS = 3
BAUDRATE = 115200
APN = "gprs.swisscom.ch"

DEFAULT_TIMEOUT_MS = 2500
SHORT_TIMEOUT_MS = 1200
LONG_TIMEOUT_MS = 5000
HTTP_ACTION_TIMEOUT_MS = 120000
HTTPDATA_INPUT_TIMEOUT_MS = 60000

READ_PAUSE_MS = 20
BOOT_SETTLE_MS = 1000
UART_WRITE_CHUNK_BYTES = 1024

# SIMCom A76XX HTTPDATA caps at 153600 bytes; stay safely below.
MAX_HTTPDATA_BYTES = 150000

# AT+HTTPACTION method codes.
HTTP_ACTION_GET = 0
HTTP_ACTION_POST = 1


# ----- HMAC request signing --------------------------------------------------

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


def sign_request(station_id, secret_b64, method, path, body, timestamp, nonce_hex=None):
    """Return the four headers to attach to a signed device request."""
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


# ----- Modem I/O -------------------------------------------------------------

def _bytes_available(uart):
    if hasattr(uart, "any"):
        return uart.any()
    return 0


def _normalize_chunk(chunk):
    if chunk is None:
        return b""
    if isinstance(chunk, str):
        return chunk.encode()
    return chunk


def _decode_bytes(data):
    try:
        return data.decode("utf-8", "ignore")
    except TypeError:
        return data.decode("utf-8")


def _flush_uart(uart):
    while _bytes_available(uart):
        uart.read()
        time.sleep_ms(READ_PAUSE_MS)


def _read_response(uart, timeout_ms):
    start = time.ticks_ms()
    response = b""
    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        if _bytes_available(uart):
            response += _normalize_chunk(uart.read())
            text = _decode_bytes(response)
            lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
            if "OK" in lines or "ERROR" in lines:
                break
        else:
            time.sleep_ms(READ_PAUSE_MS)
    return _decode_bytes(response).strip()


def _read_until(uart, token, timeout_ms):
    start = time.ticks_ms()
    response = b""
    while time.ticks_diff(time.ticks_ms(), start) < timeout_ms:
        if _bytes_available(uart):
            response += _normalize_chunk(uart.read())
            if token in _decode_bytes(response):
                break
        else:
            time.sleep_ms(READ_PAUSE_MS)
    return _decode_bytes(response).strip()


def send_at(uart, command, timeout_ms=DEFAULT_TIMEOUT_MS):
    _flush_uart(uart)
    uart.write((command + "\r\n").encode())
    response = _read_response(uart, timeout_ms)
    print(">", command)
    print(response if response else "(no response)")
    return response


def _expect_ok(response):
    return "OK" in response and "ERROR" not in response


def init_modem():
    uart = UART(UART_BUS, BAUDRATE, timeout_char=1000)
    time.sleep_ms(BOOT_SETTLE_MS)

    if not _expect_ok(send_at(uart, "AT", SHORT_TIMEOUT_MS)):
        raise OSError("modem did not respond to AT")

    send_at(uart, "AT+CMEE=2", SHORT_TIMEOUT_MS)
    send_at(uart, "ATE0", SHORT_TIMEOUT_MS)
    return uart


def activate_data(uart):
    steps = (
        ("AT+CGATT=1", LONG_TIMEOUT_MS),
        ('AT+CGDCONT=1,"IP","%s"' % APN, DEFAULT_TIMEOUT_MS),
        ("AT+CGACT=1,1", LONG_TIMEOUT_MS),
    )
    for command, timeout_ms in steps:
        if not _expect_ok(send_at(uart, command, timeout_ms)):
            raise OSError("modem command failed: %s" % command)


def _write_uart_buffer(uart, data):
    if hasattr(data, "bytearray"):
        data = data.bytearray()
    size = len(data)
    offset = 0
    while offset < size:
        end = min(offset + UART_WRITE_CHUNK_BYTES, size)
        uart.write(data[offset:end])
        offset = end


def _send_http_data(uart, payload):
    size = payload.size() if hasattr(payload, "size") else len(payload)
    command = "AT+HTTPDATA=%d,%d" % (size, HTTPDATA_INPUT_TIMEOUT_MS)

    _flush_uart(uart)
    uart.write((command + "\r\n").encode())
    response = _read_until(uart, "DOWNLOAD", DEFAULT_TIMEOUT_MS)
    print(">", command)
    print(response if response else "(no response)")
    if "DOWNLOAD" not in response:
        raise OSError("modem did not enter HTTPDATA download mode")

    _write_uart_buffer(uart, payload)
    response = _read_response(uart, HTTPDATA_INPUT_TIMEOUT_MS + LONG_TIMEOUT_MS)
    print(response if response else "(no response after payload)")
    if not _expect_ok(response):
        raise OSError("modem did not accept payload")


def _parse_http_action_field(response, index):
    marker = "+HTTPACTION:"
    pos = response.find(marker)
    if pos < 0:
        return None
    line = response[pos + len(marker):].strip().split("\n")[0].strip()
    parts = [part.strip() for part in line.split(",")]
    if len(parts) <= index:
        return None
    try:
        return int(parts[index])
    except ValueError:
        return None


def _perform_http_action(uart, method_code):
    response = send_at(uart, "AT+HTTPACTION=%d" % method_code, DEFAULT_TIMEOUT_MS)
    if "+HTTPACTION:" not in response:
        response = _read_until(uart, "+HTTPACTION:", HTTP_ACTION_TIMEOUT_MS)
        print(response if response else "(no +HTTPACTION result)")

    status = _parse_http_action_field(response, 1)
    data_length = _parse_http_action_field(response, 2) or 0
    print("HTTP status:", status)
    print("Response bytes:", data_length)
    return status, data_length


def http_request(uart, method_code, url, headers=None, content_type=None, payload=None):
    print("HTTP request:", url)
    send_at(uart, "AT+HTTPTERM", SHORT_TIMEOUT_MS)

    steps = [
        ("AT+HTTPINIT", DEFAULT_TIMEOUT_MS),
        ('AT+HTTPPARA="URL","%s"' % url, DEFAULT_TIMEOUT_MS),
    ]
    if content_type is not None:
        steps.append(('AT+HTTPPARA="CONTENT","%s"' % content_type, DEFAULT_TIMEOUT_MS))

    for command, timeout_ms in steps:
        if not _expect_ok(send_at(uart, command, timeout_ms)):
            raise OSError("modem command failed: %s" % command)

    if headers:
        user_data = "\r\n".join("%s: %s" % (k, v) for k, v in headers.items())
        if not _expect_ok(send_at(uart, 'AT+HTTPPARA="USERDATA","%s"' % user_data, DEFAULT_TIMEOUT_MS)):
            raise OSError("modem command failed: USERDATA")

    if payload is not None:
        _send_http_data(uart, payload)

    status, data_length = _perform_http_action(uart, method_code)
    body = ""
    if data_length > 0:
        body = send_at(uart, "AT+HTTPREAD=0,%d" % data_length, LONG_TIMEOUT_MS)
    send_at(uart, "AT+HTTPTERM", DEFAULT_TIMEOUT_MS)

    if body:
        print("Response body:")
        print(body)

    return status, body


def extract_json_payload(raw_body):
    """Pull a JSON object out of an AT+HTTPREAD response."""
    start = raw_body.find("{")
    end = raw_body.rfind("}")
    if start < 0 or end < 0 or end < start:
        raise ValueError("response did not contain a JSON object")
    return raw_body[start:end + 1]


# ----- Date math / scheduling ------------------------------------------------

def round_down_to_minute(unix_seconds):
    return int(unix_seconds) - (int(unix_seconds) % 60)


def format_iso_utc(unix_seconds):
    parts = time.gmtime(int(unix_seconds))
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (
        parts[0], parts[1], parts[2], parts[3], parts[4], parts[5],
    )


def format_capture_filename(unix_seconds, camera_name):
    parts = time.gmtime(round_down_to_minute(unix_seconds))
    return "%04d%02d%02d_%02d%02dZ_%s.jpg" % (
        parts[0], parts[1], parts[2], parts[3], parts[4], camera_name,
    )


def parse_hhmm(value, fallback):
    if not value:
        value = fallback
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("invalid schedule time: %s" % value)
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError("invalid schedule time: %s" % value)
    return hour, minute


def days_from_civil(year, month, day):
    year -= 1 if month <= 2 else 0
    era = (year if year >= 0 else year - 399) // 400
    yoe = year - era * 400
    month_offset = month - 3 if month > 2 else month + 9
    doy = (153 * month_offset + 2) // 5 + day - 1
    doe = yoe * 365 + yoe // 4 - yoe // 100 + doy
    return era * 146097 + doe - 719468


def utc_epoch_seconds(year, month, day, hour, minute, second=0):
    return days_from_civil(year, month, day) * 86400 + hour * 3600 + minute * 60 + second


def daily_time_epoch(reference_seconds, hhmm):
    parts = time.gmtime(int(reference_seconds))
    hour, minute = hhmm
    return utc_epoch_seconds(parts[0], parts[1], parts[2], hour, minute)


def compute_next_start(config, now_seconds):
    interval_seconds = max(1, int(config.get("captureIntervalMinutes") or 30)) * 60

    # When useSunriseSunset is true, the backend-provided start/stop values
    # already encode today's effective active window.
    start_hhmm = parse_hhmm(config.get("stationStartTime"), "06:00")
    stop_hhmm = parse_hhmm(config.get("stationStopTime"), "20:00")
    today_start = daily_time_epoch(now_seconds, start_hhmm)
    today_stop = daily_time_epoch(now_seconds, stop_hhmm)
    tomorrow_start = today_start + 86400

    if now_seconds < today_start:
        return today_start
    if now_seconds >= today_stop:
        return tomorrow_start

    candidate = round_down_to_minute(now_seconds) + interval_seconds
    return candidate if candidate <= today_stop else tomorrow_start


class ServerClock:
    """Tracks wall-clock time via a server-fetched offset + ticks_ms()."""

    def __init__(self):
        self._server_seconds_at_sync = None
        self._ticks_ms_at_sync = None

    def sync(self, uart, clock_url):
        status, body = http_request(uart, HTTP_ACTION_GET, clock_url)
        if status is None or not 200 <= status < 300:
            raise OSError("clock fetch failed with HTTP status %s" % status)
        payload = json.loads(extract_json_payload(body))
        self._server_seconds_at_sync = int(payload["unixSeconds"])
        self._ticks_ms_at_sync = time.ticks_ms()
        print("Clock synced:", format_iso_utc(self._server_seconds_at_sync),
              "(unix=%d)" % self._server_seconds_at_sync)

    def _seconds_at(self, ticks_ms):
        if self._server_seconds_at_sync is None:
            raise OSError("clock has never been synced")
        elapsed_ms = time.ticks_diff(ticks_ms, self._ticks_ms_at_sync)
        return self._server_seconds_at_sync + (elapsed_ms // 1000)

    def now_unix_seconds(self):
        return self._seconds_at(time.ticks_ms())

    def unix_seconds_at_ticks(self, ticks_ms):
        return self._seconds_at(ticks_ms)


# ----- Application -----------------------------------------------------------

def api_url(path):
    return "%s://%s%s" % (API_SCHEME, API_HOST, path)


def setup_camera():
    """Initialize the camera sensor."""
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.VGA)
    sensor.skip_frames(time=2000)


def capture_jpeg():
    quality = JPEG_QUALITY
    while quality >= JPEG_MIN_QUALITY:
        jpeg = sensor.snapshot().compress(quality=quality)
        size = jpeg.size()
        print("Captured JPEG:", size, "bytes at quality", quality)
        if size <= MAX_HTTPDATA_BYTES:
            return jpeg
        quality -= JPEG_QUALITY_STEP
        gc.collect()
    raise ValueError("JPEG is too large for SIMCom HTTPDATA")


def sanitize_camera_name(value):
    safe = []
    for char in value.strip():
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "camera"


def read_sensor_data():
    """Optional hook for board-specific telemetry merged into the upload payload."""
    data = {}
    if hasattr(machine, "reset_cause"):
        try:
            data["wakeReason"] = str(machine.reset_cause())
        except Exception:
            pass
    return data


def signed_request(uart, clock, method_code, http_method, path,
                   body=None, content_type=None, extra_headers=None):
    headers = sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method=http_method,
        path=path,
        body=body if body is not None else b"",
        timestamp=clock.now_unix_seconds(),
    )
    if content_type is not None:
        headers["Content-Type"] = content_type
    if extra_headers:
        headers.update(extra_headers)

    status, response_body = http_request(
        uart, method_code, api_url(path), headers, content_type, body,
    )
    if status is None or not 200 <= status < 300:
        raise OSError("%s %s failed with HTTP status %s" % (http_method, path, status))
    return response_body


def fetch_station_config(uart, clock):
    body = signed_request(uart, clock, HTTP_ACTION_GET, "GET", CONFIG_PATH)
    return json.loads(extract_json_payload(body))


def upload_sensor_reading(uart, clock, payload):
    signed_request(
        uart, clock, HTTP_ACTION_POST, "POST", SENSOR_READINGS_PATH,
        body=json.dumps(payload).encode("utf-8"),
        content_type="application/json",
    )


def upload_image(uart, clock, jpeg, filename, next_start_iso):
    body = bytes(jpeg.bytearray()) if hasattr(jpeg, "bytearray") else bytes(jpeg)
    signed_request(
        uart, clock, HTTP_ACTION_POST, "POST", UPLOAD_PATH,
        body=body, content_type="image/jpeg",
        extra_headers={"X-Filename": filename, "X-Next-Online": next_start_iso},
    )


def deep_sleep_until(clock, next_start_seconds):
    sleep_ms = max(0, (int(next_start_seconds) - int(clock.now_unix_seconds())) * 1000)
    machine.deepsleep(sleep_ms)


def main():
    setup_camera()
    capture_ticks_ms = time.ticks_ms()
    jpeg = capture_jpeg()
    telemetry = read_sensor_data()

    uart = init_modem()
    activate_data(uart)
    clock = ServerClock()
    clock.sync(uart, api_url(CLOCK_PATH))

    config = fetch_station_config(uart, clock)
    capture_seconds = round_down_to_minute(clock.unix_seconds_at_ticks(capture_ticks_ms))
    next_start_seconds = compute_next_start(config, clock.now_unix_seconds())
    next_start_iso = format_iso_utc(next_start_seconds)
    camera_name = sanitize_camera_name(CAMERA_NAME)

    payload = {
        "timestamp": format_iso_utc(capture_seconds),
        "firmwareVersion": FIRMWARE_VERSION,
        "nextStart": next_start_iso,
        "cameraName": camera_name,
    }
    payload.update(telemetry)
    upload_sensor_reading(uart, clock, payload)

    filename = format_capture_filename(capture_seconds, camera_name)
    upload_image(uart, clock, jpeg, filename, next_start_iso)

    print("Capture cycle uploaded:", filename)
    gc.collect()
    deep_sleep_until(clock, next_start_seconds)


if __name__ == "__main__":
    main()
