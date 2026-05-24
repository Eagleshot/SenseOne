# OpenMV N6 cellular image uploader for a SIM7670E/A7670E modem.
#
# Wiring:
# - OpenMV P4/TX -> modem RX
# - OpenMV P5/RX -> modem TX
# - OpenMV GND   -> modem GND
#
# Auth: HMAC-SHA256 request signing (see clients/openmv/eagleshot_signing.py).
# The shared secret never leaves the device — each request is signed with a
# unix timestamp + random nonce, replayed once at the server. Safe over plain
# HTTP because the modem can't reliably do TLS on this network.
#
# Provisioning: in the server admin UI, POST /stations/<id>/rotate-device-secret
# and paste the returned secret into STATION_SECRET_B64 below.

import gc
import json
import sensor
import time

from pyb import UART

import eagleshot_signing

try:
    import machine
except ImportError:
    machine = None


UART_BUS = 3
BAUDRATE = 115200

APN = "gprs.swisscom.ch"
API_HOST = "api.eagleshot.org"
API_SCHEME = "http"
STATION_ID = "silvretta-glacier"
STATION_SECRET_B64 = "REPLACE-WITH-PROVISIONED-DEVICE-SECRET"
CAMERA_NAME = "front"
FIRMWARE_VERSION = "openmv-n6-2026.05"

JPEG_QUALITY = 70
JPEG_MIN_QUALITY = 35
JPEG_QUALITY_STEP = 10

# SIMCom A76XX HTTPDATA supports up to 153600 bytes. Stay below that limit.
MAX_HTTPDATA_BYTES = 150000
HTTPDATA_INPUT_TIMEOUT_MS = 60000

DEFAULT_TIMEOUT_MS = 2500
SHORT_TIMEOUT_MS = 1200
LONG_TIMEOUT_MS = 5000
HTTP_ACTION_TIMEOUT_MS = 120000
READ_PAUSE_MS = 20
BOOT_SETTLE_MS = 1000
UART_WRITE_CHUNK_BYTES = 1024

# AT+HTTPACTION method codes.
HTTP_ACTION_GET = 0
HTTP_ACTION_POST = 1


def ticks_elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)


def bytes_available(uart):
    if hasattr(uart, "any"):
        return uart.any()
    return 0


def normalize_chunk(chunk):
    if chunk is None:
        return b""
    if isinstance(chunk, str):
        return chunk.encode()
    return chunk


def decode_bytes(data):
    try:
        return data.decode("utf-8", "ignore")
    except TypeError:
        return data.decode("utf-8")


def flush_uart(uart):
    while bytes_available(uart):
        uart.read()
        time.sleep_ms(READ_PAUSE_MS)


def write_command(uart, command):
    uart.write((command + "\r\n").encode())


def read_response(uart, timeout_ms):
    start = time.ticks_ms()
    response = b""

    while ticks_elapsed(start) < timeout_ms:
        if bytes_available(uart):
            response += normalize_chunk(uart.read())
            text = decode_bytes(response)
            lines = [line.strip() for line in text.replace("\r", "\n").split("\n")]
            if "OK" in lines or "ERROR" in lines:
                break
        else:
            time.sleep_ms(READ_PAUSE_MS)

    return decode_bytes(response).strip()


def read_until(uart, token, timeout_ms):
    start = time.ticks_ms()
    response = b""

    while ticks_elapsed(start) < timeout_ms:
        if bytes_available(uart):
            response += normalize_chunk(uart.read())
            if token in decode_bytes(response):
                break
        else:
            time.sleep_ms(READ_PAUSE_MS)

    return decode_bytes(response).strip()


def send_at(uart, command, timeout_ms=DEFAULT_TIMEOUT_MS):
    flush_uart(uart)
    write_command(uart, command)
    response = read_response(uart, timeout_ms)
    print(">", command)
    print(response if response else "(no response)")
    return response


def expect_ok(response):
    return "OK" in response and "ERROR" not in response


def upload_path():
    return "/device/stations/%s/images" % STATION_ID


def upload_url():
    return "%s://%s%s" % (API_SCHEME, API_HOST, upload_path())


def sensor_readings_path():
    return "/device/stations/%s/sensor-readings" % STATION_ID


def sensor_readings_url():
    return "%s://%s%s" % (API_SCHEME, API_HOST, sensor_readings_path())


def config_path():
    return "/device/stations/%s/config" % STATION_ID


def config_url():
    return "%s://%s%s" % (API_SCHEME, API_HOST, config_path())


def clock_path():
    return "/clock"


def clock_url():
    return "%s://%s%s" % (API_SCHEME, API_HOST, clock_path())


def payload_size(data):
    if hasattr(data, "size"):
        return data.size()
    return len(data)


def http_action_status(response):
    marker = "+HTTPACTION:"
    pos = response.find(marker)
    if pos < 0:
        return None

    line = response[pos + len(marker) :].strip().split("\n")[0].strip()
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 2:
        return None

    try:
        return int(parts[1])
    except ValueError:
        return None


def http_action_data_length(response):
    marker = "+HTTPACTION:"
    pos = response.find(marker)
    if pos < 0:
        return 0

    line = response[pos + len(marker) :].strip().split("\n")[0].strip()
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return 0

    try:
        return int(parts[2])
    except ValueError:
        return 0


def setup_camera():
    sensor.reset()
    sensor.set_pixformat(sensor.RGB565)
    sensor.set_framesize(sensor.VGA)
    sensor.skip_frames(time=2000)
    sensor.set_auto_gain(False)
    sensor.set_auto_whitebal(False)


def capture_jpeg():
    quality = JPEG_QUALITY

    while quality >= JPEG_MIN_QUALITY:
        img = sensor.snapshot()
        jpeg = img.compress(quality=quality)
        size = jpeg.size()
        print("Captured JPEG:", size, "bytes at quality", quality)
        if size <= MAX_HTTPDATA_BYTES:
            return jpeg
        quality -= JPEG_QUALITY_STEP
        gc.collect()

    raise ValueError("JPEG is too large for SIMCom HTTPDATA")


def init_modem():
    uart = UART(UART_BUS, BAUDRATE, timeout_char=1000)
    time.sleep_ms(BOOT_SETTLE_MS)

    response = send_at(uart, "AT", SHORT_TIMEOUT_MS)
    if not expect_ok(response):
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
        response = send_at(uart, command, timeout_ms)
        if not expect_ok(response):
            raise OSError("modem command failed: %s" % command)


def write_uart_buffer(uart, data):
    if hasattr(data, "bytearray"):
        data = data.bytearray()

    size = len(data)
    offset = 0

    while offset < size:
        end = offset + UART_WRITE_CHUNK_BYTES
        if end > size:
            end = size
        uart.write(data[offset:end])
        offset = end


def send_http_data(uart, payload):
    size = payload_size(payload)
    command = "AT+HTTPDATA=%d,%d" % (size, HTTPDATA_INPUT_TIMEOUT_MS)

    flush_uart(uart)
    write_command(uart, command)
    response = read_until(uart, "DOWNLOAD", DEFAULT_TIMEOUT_MS)
    print(">", command)
    print(response if response else "(no response)")
    if "DOWNLOAD" not in response:
        raise OSError("modem did not enter HTTPDATA download mode")

    write_uart_buffer(uart, payload)
    response = read_response(uart, HTTPDATA_INPUT_TIMEOUT_MS + LONG_TIMEOUT_MS)
    print(response if response else "(no response after image data)")
    if not expect_ok(response):
        raise OSError("modem did not accept image data")


def perform_http_action(uart, method_code):
    response = send_at(uart, "AT+HTTPACTION=%d" % method_code, DEFAULT_TIMEOUT_MS)
    if "+HTTPACTION:" not in response:
        action_result = read_until(uart, "+HTTPACTION:", HTTP_ACTION_TIMEOUT_MS)
        print(action_result if action_result else "(no +HTTPACTION result)")
    else:
        action_result = response

    status = http_action_status(action_result)
    data_length = http_action_data_length(action_result)
    print("HTTP status:", status)
    print("Response bytes:", data_length)
    return status, data_length


def read_http_body(uart, data_length):
    if data_length <= 0:
        return ""

    command = "AT+HTTPREAD=0,%d" % data_length
    response = send_at(uart, command, LONG_TIMEOUT_MS)
    return response


def format_user_data_headers(headers):
    """Pack a dict of header name/value pairs into a single USERDATA string."""
    return "\r\n".join("%s: %s" % (k, v) for k, v in headers.items())


def http_request(uart, method_code, url, headers, content_type, payload):
    print("HTTP request:", url)

    send_at(uart, "AT+HTTPTERM", SHORT_TIMEOUT_MS)

    steps = [
        ("AT+HTTPINIT", DEFAULT_TIMEOUT_MS),
        ('AT+HTTPPARA="URL","%s"' % url, DEFAULT_TIMEOUT_MS),
    ]
    if content_type is not None:
        steps.append(('AT+HTTPPARA="CONTENT","%s"' % content_type, DEFAULT_TIMEOUT_MS))

    for command, timeout_ms in steps:
        response = send_at(uart, command, timeout_ms)
        if not expect_ok(response):
            raise OSError("modem command failed: %s" % command)

    if headers:
        user_data = format_user_data_headers(headers)
        command = 'AT+HTTPPARA="USERDATA","%s"' % user_data
        response = send_at(uart, command, DEFAULT_TIMEOUT_MS)
        if not expect_ok(response):
            raise OSError("modem command failed: USERDATA")

    if payload is not None:
        send_http_data(uart, payload)

    status, data_length = perform_http_action(uart, method_code)
    body = read_http_body(uart, data_length)
    send_at(uart, "AT+HTTPTERM", DEFAULT_TIMEOUT_MS)

    if body:
        print("Response body:")
        print(body)

    return status, body


def extract_json_payload(raw_body):
    """Crudely pull a JSON object out of the AT+HTTPREAD output."""
    start = raw_body.find("{")
    end = raw_body.rfind("}")
    if start < 0 or end < 0 or end < start:
        raise ValueError("response did not contain a JSON object")
    return raw_body[start : end + 1]


def sanitize_camera_name(value):
    safe = []
    for char in value.strip():
        if char.isalnum() or char in ("-", "_", "."):
            safe.append(char)
        else:
            safe.append("_")
    return "".join(safe) or "camera"


def round_down_to_minute(unix_seconds):
    return int(unix_seconds) - (int(unix_seconds) % 60)


def format_iso_utc(unix_seconds):
    parts = time.gmtime(int(unix_seconds))
    year, month, day, hour, minute, second = parts[0], parts[1], parts[2], parts[3], parts[4], parts[5]
    return "%04d-%02d-%02dT%02d:%02d:%02dZ" % (year, month, day, hour, minute, second)


def format_capture_filename(unix_seconds, camera_name):
    parts = time.gmtime(round_down_to_minute(unix_seconds))
    year, month, day, hour, minute = parts[0], parts[1], parts[2], parts[3], parts[4]
    return "%04d%02d%02d_%02d%02dZ_%s.jpg" % (
        year,
        month,
        day,
        hour,
        minute,
        sanitize_camera_name(camera_name),
    )


def parse_hhmm(value, fallback):
    if not value:
        value = fallback
    parts = value.split(":")
    if len(parts) != 2:
        raise ValueError("invalid schedule time: %s" % value)
    hour = int(parts[0])
    minute = int(parts[1])
    if hour < 0 or hour > 23 or minute < 0 or minute > 59:
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
    days = days_from_civil(year, month, day)
    return days * 86400 + hour * 3600 + minute * 60 + second


def daily_time_epoch(reference_seconds, hhmm):
    parts = time.gmtime(int(reference_seconds))
    year, month, day = parts[0], parts[1], parts[2]
    hour, minute = hhmm
    return utc_epoch_seconds(year, month, day, hour, minute)


def compute_next_start(config, now_seconds):
    interval_minutes = int(config.get("captureIntervalMinutes") or 30)
    if interval_minutes < 1:
        interval_minutes = 1

    # When useSunriseSunset is true, the backend-provided start/stop values
    # are treated as the effective active window for this firmware.
    start_hhmm = parse_hhmm(config.get("stationStartTime"), "06:00")
    stop_hhmm = parse_hhmm(config.get("stationStopTime"), "20:00")
    today_start = daily_time_epoch(now_seconds, start_hhmm)
    today_stop = daily_time_epoch(now_seconds, stop_hhmm)
    tomorrow_start = today_start + 86400

    now_minute = round_down_to_minute(now_seconds)
    interval_seconds = interval_minutes * 60

    if now_seconds < today_start:
        return today_start
    if now_seconds >= today_stop:
        return tomorrow_start

    candidate = now_minute + interval_seconds
    if candidate <= today_stop:
        return candidate
    return tomorrow_start


def read_voltage():
    """Override with board-specific voltage sensing when available."""
    return None


def read_device_temperature():
    """Override with board-specific device temperature sensing when available."""
    return None


def read_sensor_data():
    """Hook for local telemetry captured immediately after the image."""
    data = {}
    voltage = read_voltage()
    if voltage is not None:
        data["voltage"] = voltage
    device_temperature = read_device_temperature()
    if device_temperature is not None:
        data["deviceTemperature"] = device_temperature
    if machine is not None and hasattr(machine, "reset_cause"):
        try:
            data["wakeReason"] = str(machine.reset_cause())
        except Exception:
            pass
    return data


def fetch_clock(uart):
    """Fetch the server clock as a unix timestamp."""
    import json

    status, body = http_request(uart, HTTP_ACTION_GET, clock_url(), None, None, None)
    if status is None or not 200 <= status < 300:
        raise OSError("clock fetch failed with HTTP status %s" % status)

    payload = json.loads(extract_json_payload(body))
    return int(payload["unixSeconds"])


class ServerClock:
    """Tracks wall-clock time via a server-fetched offset + ticks_ms()."""

    def __init__(self):
        self._server_seconds_at_sync = None
        self._ticks_ms_at_sync = None

    def sync(self, uart):
        self._server_seconds_at_sync = fetch_clock(uart)
        self._ticks_ms_at_sync = time.ticks_ms()
        print("Clock synced. Unix seconds =", self._server_seconds_at_sync)

    def now_unix_seconds(self):
        if self._server_seconds_at_sync is None:
            raise OSError("clock has never been synced")
        elapsed_ms = time.ticks_diff(time.ticks_ms(), self._ticks_ms_at_sync)
        return self._server_seconds_at_sync + (elapsed_ms // 1000)

    def unix_seconds_at_ticks(self, ticks_ms):
        if self._server_seconds_at_sync is None:
            raise OSError("clock has never been synced")
        elapsed_ms = time.ticks_diff(ticks_ms, self._ticks_ms_at_sync)
        return self._server_seconds_at_sync + (elapsed_ms // 1000)

    def ms_since_sync(self):
        if self._ticks_ms_at_sync is None:
            return None
        return time.ticks_diff(time.ticks_ms(), self._ticks_ms_at_sync)


def fetch_station_config(uart, clock):
    body = b""
    headers = eagleshot_signing.sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="GET",
        path=config_path(),
        body=body,
        timestamp=clock.now_unix_seconds(),
    )
    status, raw_body = http_request(uart, HTTP_ACTION_GET, config_url(), headers, None, None)
    if status is None or not 200 <= status < 300:
        raise OSError("config fetch failed with HTTP status %s" % status)
    return json.loads(extract_json_payload(raw_body))


def upload_sensor_reading(uart, payload, clock):
    body = json.dumps(payload).encode("utf-8")
    headers = eagleshot_signing.sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=sensor_readings_path(),
        body=body,
        timestamp=clock.now_unix_seconds(),
    )
    headers["Content-Type"] = "application/json"
    status, _ = http_request(uart, HTTP_ACTION_POST, sensor_readings_url(), headers, "application/json", body)
    return status is not None and 200 <= status < 300, status


def upload_image(uart, jpeg, clock, filename, next_start_iso):
    """Sign and upload a single image. Returns (success, http_status)."""
    body = bytes(jpeg.bytearray()) if hasattr(jpeg, "bytearray") else bytes(jpeg)
    headers = eagleshot_signing.sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=upload_path(),
        body=body,
        timestamp=clock.now_unix_seconds(),
    )
    headers["X-Filename"] = filename
    headers["X-Next-Online"] = next_start_iso
    status, _ = http_request(uart, HTTP_ACTION_POST, upload_url(), headers, "image/jpeg", body)
    success = status is not None and 200 <= status < 300
    return success, status


def deep_sleep_ms(duration_ms):
    if machine is None or not hasattr(machine, "deepsleep"):
        raise OSError("timed deep sleep API is unavailable")
    machine.deepsleep(max(0, int(duration_ms)))


def deep_sleep_until(clock, next_start_seconds):
    sleep_seconds = int(next_start_seconds) - int(clock.now_unix_seconds())
    deep_sleep_ms(max(0, sleep_seconds * 1000))


def main():
    setup_camera()
    capture_ticks_ms = time.ticks_ms()
    jpeg = capture_jpeg()
    telemetry = read_sensor_data()

    uart = init_modem()
    activate_data(uart)
    clock = ServerClock()
    clock.sync(uart)

    config = fetch_station_config(uart, clock)
    capture_seconds = round_down_to_minute(clock.unix_seconds_at_ticks(capture_ticks_ms))
    capture_iso = format_iso_utc(capture_seconds)
    next_start_seconds = compute_next_start(config, clock.now_unix_seconds())
    next_start_iso = format_iso_utc(next_start_seconds)
    camera_name = sanitize_camera_name(CAMERA_NAME)

    payload = {
        "timestamp": capture_iso,
        "firmwareVersion": FIRMWARE_VERSION,
        "nextStart": next_start_iso,
        "cameraName": camera_name,
    }
    payload.update(telemetry)

    success, status = upload_sensor_reading(uart, payload, clock)
    if not success:
        raise OSError("sensor/log upload failed with HTTP status %s" % status)

    filename = format_capture_filename(capture_seconds, camera_name)
    success, status = upload_image(uart, jpeg, clock, filename, next_start_iso)
    if not success:
        raise OSError("image upload failed with HTTP status %s" % status)

    print("Capture cycle uploaded:", filename)
    gc.collect()
    deep_sleep_until(clock, next_start_seconds)


if __name__ == "__main__":
    main()
