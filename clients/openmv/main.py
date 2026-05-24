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
import sensor
import time

from pyb import UART

import eagleshot_signing


UART_BUS = 3
BAUDRATE = 115200

APN = "gprs.swisscom.ch"
API_HOST = "api.eagleshot.org"
API_SCHEME = "http"
STATION_ID = "silvretta-glacier"
STATION_SECRET_B64 = "REPLACE-WITH-PROVISIONED-DEVICE-SECRET"

UPLOAD_INTERVAL_MS = 10 * 60 * 1000
SERVER_TIME_REFRESH_MS = 12 * 60 * 60 * 1000  # Re-sync clock every 12h.
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

    def ms_since_sync(self):
        if self._ticks_ms_at_sync is None:
            return None
        return time.ticks_diff(time.ticks_ms(), self._ticks_ms_at_sync)


def upload_image(uart, jpeg, clock):
    """Sign and upload a single image. Returns (success, http_status)."""
    body = bytes(jpeg.bytearray()) if hasattr(jpeg, "bytearray") else bytes(jpeg)
    timestamp = clock.now_unix_seconds()
    headers = eagleshot_signing.sign_request(
        station_id=STATION_ID,
        secret_b64=STATION_SECRET_B64,
        method="POST",
        path=upload_path(),
        body=body,
        timestamp=timestamp,
    )
    headers["X-Filename"] = "%d-capture.jpg" % timestamp
    status, _ = http_request(uart, HTTP_ACTION_POST, upload_url(), headers, "image/jpeg", body)
    success = status is not None and 200 <= status < 300
    return success, status


def main():
    setup_camera()
    uart = init_modem()
    activate_data(uart)
    clock = ServerClock()
    clock.sync(uart)

    while True:
        try:
            if (clock.ms_since_sync() or 0) > SERVER_TIME_REFRESH_MS:
                clock.sync(uart)

            jpeg = capture_jpeg()
            success, status = upload_image(uart, jpeg, clock)
            if success:
                print("Image uploaded successfully.")
            else:
                print("Image upload failed. HTTP status:", status)
                # 401 most likely means our clock drifted past the window.
                if status == 401:
                    print("Re-syncing clock.")
                    clock.sync(uart)
        except Exception as exc:
            print("Upload error:", exc)
            gc.collect()
            try:
                activate_data(uart)
                clock.sync(uart)
            except Exception as reconnect_exc:
                print("Reconnect error:", reconnect_exc)

        time.sleep_ms(UPLOAD_INTERVAL_MS)


main()
