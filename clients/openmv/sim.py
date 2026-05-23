# OpenMV N6 SIM7670E modem diagnostic script.
#
# Wiring:
# - OpenMV P4/TX -> SIM7670E RX
# - OpenMV P5/RX -> SIM7670E TX
# - OpenMV GND   -> SIM7670E GND
# - The modem UART logic level must be 3.3V-safe.
#
# The modem is expected to be powered and booted before this script runs.

import time

from pyb import UART


UART_BUS = 3
BAUDRATE = 115200

DEFAULT_TIMEOUT_MS = 2500
SHORT_TIMEOUT_MS = 1200
LONG_TIMEOUT_MS = 5000
HTTP_ACTION_TIMEOUT_MS = 30000

READ_PAUSE_MS = 20
BOOT_SETTLE_MS = 1000

APN = "gprs.swisscom.ch"
HEALTH_HOST = "api.eagleshot.org"
HEALTH_PATH = "/health"
HEALTH_USE_SSL = False
SSL_CONTEXT_ID = 0
SSL_INSECURE = True
SSL_VERSION_CANDIDATES = (4, 3)

HTTP_ACTION_STATUS_TEXT = {
    715: "TLS handshake failed",
}


COMMANDS = (
    ("Basic AT", "AT", SHORT_TIMEOUT_MS),
    ("Modem identity", "ATI", DEFAULT_TIMEOUT_MS),
    ("Model", "AT+CGMM", DEFAULT_TIMEOUT_MS),
    ("Firmware", "AT+CGMR", DEFAULT_TIMEOUT_MS),
    ("IMEI", "AT+CGSN", DEFAULT_TIMEOUT_MS),
    ("SIM ICCID", "AT+CCID", DEFAULT_TIMEOUT_MS),
    ("SIM state", "AT+CPIN?", DEFAULT_TIMEOUT_MS),
    ("Signal quality", "AT+CSQ", DEFAULT_TIMEOUT_MS),
    ("Operator", "AT+COPS?", DEFAULT_TIMEOUT_MS),
    ("Circuit registration", "AT+CREG?", DEFAULT_TIMEOUT_MS),
    ("EPS/LTE registration", "AT+CEREG?", DEFAULT_TIMEOUT_MS),
    ("Serving cell", "AT+CPSI?", LONG_TIMEOUT_MS),
)


def health_url():
    scheme = "https" if HEALTH_USE_SSL else "http"
    return "%s://%s%s" % (scheme, HEALTH_HOST, HEALTH_PATH)


def ticks_elapsed(start):
    return time.ticks_diff(time.ticks_ms(), start)


def bytes_available(uart):
    if hasattr(uart, "any"):
        return uart.any()
    return 0


def flush_uart(uart):
    while bytes_available(uart):
        uart.read()
        time.sleep_ms(READ_PAUSE_MS)


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
    return read_response(uart, timeout_ms)


def print_section(title):
    print("")
    print("== %s ==" % title)


def print_response(command, response):
    print("> %s" % command)
    if response:
        print(response)
    else:
        print("(no response)")


def http_action_data_length(response):
    marker = "+HTTPACTION:"
    pos = response.find(marker)
    if pos < 0:
        return None

    line = response[pos + len(marker) :].strip().split("\n")[0].strip()
    parts = [part.strip() for part in line.split(",")]
    if len(parts) < 3:
        return None

    try:
        return int(parts[2])
    except ValueError:
        return None


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


def print_http_action_summary(response):
    status = http_action_status(response)
    data_length = http_action_data_length(response)

    if status is None:
        return

    text = HTTP_ACTION_STATUS_TEXT.get(status)
    if text:
        print("HTTP action status: %d (%s)" % (status, text))
    else:
        print("HTTP action status: %d" % status)

    if data_length is not None:
        print("HTTP response bytes: %d" % data_length)

    if status == 715:
        print("TLS reached the server but the handshake failed before any HTTP response.")


def perform_http_get(uart):
    print("")
    print("-- HTTP GET --")
    action_response = send_at(uart, "AT+HTTPACTION=0", DEFAULT_TIMEOUT_MS)
    print_response("AT+HTTPACTION=0", action_response)

    if "+HTTPACTION:" in action_response:
        print_http_action_summary(action_response)
        return action_response

    action_result = read_until(uart, "+HTTPACTION:", HTTP_ACTION_TIMEOUT_MS)
    if action_result:
        print(action_result)
    else:
        print("(no +HTTPACTION result)")
    print_http_action_summary(action_result)
    return action_result


def read_http_body(uart, action_result):
    data_length = http_action_data_length(action_result)

    print("")
    print("-- HTTP response body --")
    if data_length is None:
        print_response("AT+HTTPREAD", send_at(uart, "AT+HTTPREAD", LONG_TIMEOUT_MS))
    elif data_length > 0:
        command = "AT+HTTPREAD=0,%d" % data_length
        print_response(command, send_at(uart, command, LONG_TIMEOUT_MS))
    else:
        print("(no response body reported by modem)")


def run_health_check(uart):
    url = health_url()
    ssl_auth_mode = 0 if SSL_INSECURE else 1

    print_section("API health check")
    print("URL: %s" % url)
    if HEALTH_USE_SSL and SSL_INSECURE:
        print("TLS mode: insecure, certificate verification disabled")

    steps = (
        ("Verbose modem errors", "AT+CMEE=2", SHORT_TIMEOUT_MS),
        ("Attach packet service", "AT+CGATT=1", LONG_TIMEOUT_MS),
        ("Configure PDP context", 'AT+CGDCONT=1,"IP","%s"' % APN, DEFAULT_TIMEOUT_MS),
        ("Activate PDP context", "AT+CGACT=1,1", LONG_TIMEOUT_MS),
    )

    for title, command, timeout_ms in steps:
        print("")
        print("-- %s --" % title)
        print_response(command, send_at(uart, command, timeout_ms))

    if HEALTH_USE_SSL:
        ssl_steps = (
            (
                "SSL auth mode",
                'AT+CSSLCFG="authmode",%d,%d' % (SSL_CONTEXT_ID, ssl_auth_mode),
                DEFAULT_TIMEOUT_MS,
            ),
            ("SSL ignore local time", 'AT+CSSLCFG="ignorelocaltime",%d,1' % SSL_CONTEXT_ID, DEFAULT_TIMEOUT_MS),
            ("SSL SNI", 'AT+CSSLCFG="enableSNI",%d,1' % SSL_CONTEXT_ID, DEFAULT_TIMEOUT_MS),
        )

        for title, command, timeout_ms in ssl_steps:
            print("")
            print("-- %s --" % title)
            print_response(command, send_at(uart, command, timeout_ms))

        print("")
        print("-- SSL config --")
        print_response("AT+CSSLCFG?", send_at(uart, "AT+CSSLCFG?", LONG_TIMEOUT_MS))

    action_result = ""
    ssl_versions = SSL_VERSION_CANDIDATES if HEALTH_USE_SSL else (None,)
    for ssl_version in ssl_versions:
        print("")
        if HEALTH_USE_SSL:
            print("-- HTTPS attempt, SSL version %d --" % ssl_version)
            print_response(
                'AT+CSSLCFG="sslversion",%d,%d' % (SSL_CONTEXT_ID, ssl_version),
                send_at(
                    uart,
                    'AT+CSSLCFG="sslversion",%d,%d' % (SSL_CONTEXT_ID, ssl_version),
                    DEFAULT_TIMEOUT_MS,
                ),
            )
        else:
            print("-- HTTP attempt --")

        print_response("AT+HTTPTERM", send_at(uart, "AT+HTTPTERM", SHORT_TIMEOUT_MS))
        print_response("AT+HTTPINIT", send_at(uart, "AT+HTTPINIT", DEFAULT_TIMEOUT_MS))

        if HEALTH_USE_SSL:
            print_response(
                'AT+HTTPPARA="SSLCFG",%d' % SSL_CONTEXT_ID,
                send_at(uart, 'AT+HTTPPARA="SSLCFG",%d' % SSL_CONTEXT_ID, DEFAULT_TIMEOUT_MS),
            )

        print_response(
            'AT+HTTPPARA="URL","%s"' % url,
            send_at(uart, 'AT+HTTPPARA="URL","%s"' % url, DEFAULT_TIMEOUT_MS),
        )

        action_result = perform_http_get(uart)
        if http_action_status(action_result) == 200:
            break

        print_response("AT+HTTPTERM", send_at(uart, "AT+HTTPTERM", DEFAULT_TIMEOUT_MS))

    read_http_body(uart, action_result)

    print("")
    print("-- Close HTTP --")
    print_response("AT+HTTPTERM", send_at(uart, "AT+HTTPTERM", DEFAULT_TIMEOUT_MS))


def run_report():
    uart = UART(UART_BUS, BAUDRATE, timeout_char=1000)
    time.sleep_ms(BOOT_SETTLE_MS)

    print("SIM7670E modem diagnostic")
    print("UART%d @ %d baud" % (UART_BUS, BAUDRATE))
    print("OpenMV P4/TX -> modem RX, OpenMV P5/RX -> modem TX")

    print_section("Connection")
    response = send_at(uart, "AT", SHORT_TIMEOUT_MS)
    print_response("AT", response)

    if "OK" not in response:
        print("")
        print("No OK from modem. Check power, RX/TX crossover, GND, and baudrate.")
        return

    for title, command, timeout_ms in COMMANDS[1:]:
        print_section(title)
        print_response(command, send_at(uart, command, timeout_ms))

    run_health_check(uart)

    print("")
    print("Diagnostic complete.")


run_report()
