# OpenMV N6 cellular image uploader for a SIM7670E / A7670E modem.
#
# This module holds the modem driver, clock/scheduling, and capture cycle.
# HMAC request signing lives in eagleshot_signing.py (shared with the other
# clients); copy BOTH files to the board root.
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
# Provisioning: in the server admin UI, rotate the station's device secret
# (POST /v1/stations/<public_id>/rotate-device-secret). Set STATION_ID below to the
# station's stable opaque id (its `id` in the API / admin UI, NOT the display
# name or pretty URL slug), and paste the returned secret into STATION_SECRET_B64.

import gc
import json
import machine
import sensor
import time

from pyb import UART

from eagleshot_signing import sign_request


# ----- Station configuration -------------------------------------------------

API_HOST = "api.eagleshot.org"
API_SCHEME = "http"
STATION_ID = "REPLACE-WITH-STATION-PUBLIC-ID"  # the station's stable opaque id
STATION_SECRET_B64 = "REPLACE-WITH-PROVISIONED-DEVICE-SECRET"
CAMERA_NAME = "front"
FIRMWARE_VERSION = "1.0.0"

UPLOAD_PATH = "/v1/ingest/stations/%s/images" % STATION_ID
SENSOR_READINGS_PATH = "/v1/ingest/stations/%s/sensor-readings" % STATION_ID
CONFIG_PATH = "/v1/ingest/stations/%s/config" % STATION_ID
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
    year, month, day, hour, minute, second = unix_to_components(unix_seconds)
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)


def format_capture_filename(unix_seconds, camera_name):
    year, month, day, hour, minute, _ = unix_to_components(round_down_to_minute(unix_seconds))
    return "%04d%02d%02d_%02d%02dZ_%s.jpg" % (year, month, day, hour, minute, camera_name)


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


def civil_from_days(z):
    """Inverse of days_from_civil: 1970-epoch day count -> (year, month, day)."""
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
    """1970-epoch seconds -> (year, month, day, hour, minute, second).

    Pure integer math so it stays correct regardless of the board's time.gmtime
    epoch -- STM32 OpenMV cams use a 2000-01-01 epoch, not POSIX 1970, which would
    otherwise shift every timestamp by ~30 years.
    """
    unix_seconds = int(unix_seconds)
    days, rem = unix_seconds // 86400, unix_seconds % 86400
    year, month, day = civil_from_days(days)
    return (year, month, day, rem // 3600, (rem % 3600) // 60, rem % 60)


def daily_time_epoch(reference_seconds, hhmm):
    year, month, day = unix_to_components(reference_seconds)[:3]
    hour, minute = hhmm
    return utc_epoch_seconds(year, month, day, hour, minute)


def compute_next_start(config, now_seconds):
    interval_seconds = max(1, int(config.get("captureIntervalMinutes") or 30)) * 60

    # When useSunriseSunset is true, the backend-provided start/stop values
    # already encode today's effective active window.
    start_minute = int(config.get("stationStartMinute") or 360)  # 06:00
    stop_minute = int(config.get("stationStopMinute") or 1200)  # 20:00
    today_start = daily_time_epoch(now_seconds, divmod(start_minute, 60))
    today_stop = daily_time_epoch(now_seconds, divmod(stop_minute, 60))
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
