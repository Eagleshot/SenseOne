// Modem
#define TINY_GSM_MODEM_SIM7600
#include <HardwareSerial.h>
#include <TinyGsmClient.h>

#define MODEM_TX 18
#define MODEM_RX 17

#define TINY_GSM_USE_GPRS false
#define CHUNK_SIZE        1500

TinyGsm modem(Serial1);
TinyGsmClient client(modem, 0);

void turn_on_modem() {
}

// Initialize the modem and print its information
void init_modem() {
  Serial.println("Initializing modem...");
  Serial1.begin(115200, SERIAL_8N1, MODEM_RX, MODEM_TX, false); // Modem serial
  // modem.init();

  delay(10000);

  String modemInfo = modem.getModemInfo();
  Serial.print("Modem - ");
  Serial.println(modemInfo);
}

// Set Network Mode
// 2 Automatic , 13 GSM only , 38 LTE only , 51 GSM and LTE only  
void set_network_mode() {
  int mode = 38;
  int res;
  do {
    res = modem.setNetworkMode(mode);
    Serial.print("Modem Set LTE: ");
    Serial.println(res);
    if (res != 1) {
      delay(500);
    }
  } while (res != 1);
}

// Get connection type and band
void print_connection_info() {
  Serial1.println("AT+CPSI?"); 
  delay(500);
  if (Serial1.available()) {
    String r = Serial1.readString();
    Serial.println(r);
  }
}

void wait_for_network() {
Serial.print("Waiting for network...");
  if (!modem.waitForNetwork()) {
    Serial.println("Modem Fail");
    return;
  }
  Serial.println(" success");

  if (modem.isNetworkConnected()) {
    Serial.println("Network connected");
  }
}

void modem_gprs_connect() {
  int max_retries = 5;
  for (int attempt = 0; attempt < max_retries; attempt++) {
    if (modem.gprsConnect(gprsApn, gprsUser, gprsPass)) {
      return;
    }
    Serial.println("GPRS connection failed, retrying...");
    delay(2000 * attempt); // Simple backoff
  }
}

int modem_is_gprs_connected(void) {
  return modem.isGprsConnected();
}

bool server_health_check() {
  bool health_ok = false;

  if (client.connect(server_ip, server_port)) {
    client.print("GET /health HTTP/1.1\r\n");
    client.print("Host: ");
    client.print(server_ip);
    client.print("\r\n");
    client.print("Connection: close\r\n\r\n");

    uint32_t start = millis();
    while (!client.available() && client.connected() && (millis() - start < 3000)) {
      delay(10);
    }

    if (client.available()) {
      String status_line = client.readStringUntil('\n');
      status_line.trim();
      health_ok = status_line.indexOf("200") >= 0;
      Serial.println("Health check response: " + status_line);
    } else {
      Serial.println("Health check timed out");
    }
  } else {
    Serial.println("Health check connection failed");
  }

  client.stop();
  return health_ok;
}


void uploadImage(camera_fb_t *fb, const char* filename) {
  if (!fb || !fb->buf || fb->len == 0) {
    Serial.println("No valid framebuffer, skipping upload.");
    return;
  }

  if (!client.connect(server_ip, server_port)) {
    Serial.println("Connection to server failed!");
    return;
  }

  unsigned long currentTotalTime = millis();
  client.print(String("POST ") + resource + " HTTP/1.1\r\n");
  client.print(String("Host: ") + server_ip + "\r\n");
  client.print("Content-Length: ");
  client.print(fb->len);
  client.print("\r\n");
  client.print("Content-Type: image/jpeg\r\n");
  client.print("X-Filename: ");
  client.print(filename);
  client.print("\r\n");
  client.println();
  client.flush();

  uint8_t tmp[CHUNK_SIZE] = {0};
  size_t blen = sizeof(tmp);
  size_t i = 0;
  size_t len = fb->len;
  size_t sent_size = 0;

  for (i = 0; i < len / blen; ++i) {
    memcpy(tmp, fb->buf + (i * blen), blen);
    sent_size = client.write(tmp, CHUNK_SIZE);
    if (sent_size != CHUNK_SIZE) {
      Serial.println("Upload interrupted while sending image body.");
      client.stop();
      return;
    }
  }

  if (len % blen) {
    size_t rest = len % blen;
    memcpy(tmp, fb->buf + (len - len % blen), rest);
    sent_size = client.write(tmp, rest);
    if (sent_size != rest) {
      Serial.println("Upload interrupted while sending final image chunk.");
      client.stop();
      return;
    }
  }
  Serial.print("Time taken to upload image: ");
  Serial.print(millis() - currentTotalTime);
  Serial.println(" ms");

  // Wait for data to arrive
  uint32_t start = millis();
  while (client.connected() && !client.available() && millis() - start < 30000L) {
    delay(100);
  };

  // Read data
  start = millis();
  char logo[640] = {
      '\0',
  };
  size_t read_chars = 0;
  bool response_truncated = false;
  while (client.connected() && millis() - start < 10000L) {
    while (client.available()) {
      int c = client.read();
      if (read_chars < sizeof(logo) - 1) {
        logo[read_chars++] = (char)c;
      } else {
        response_truncated = true;
      }
      start = millis();
    }
  }
  logo[read_chars] = '\0';
  if (response_truncated) {
    Serial.println("Server response was truncated in log output.");
  }
  Serial.println(logo);
  client.stop();
}

struct tm get_network_time(struct tm timeinfo) {
  Serial.println("Requesting current network time");
  int year = 0, month = 0, day = 0, hour = 0, min = 0, sec = 0;
  float timezone = 0;
  for (int i = 0; i < 5; i++) {
    if (modem.getNetworkTime(&year, &month, &day, &hour, &min, &sec, &timezone)) {
      Serial.println("Network time obtained.");
      timeinfo.tm_year = year - 1900;
      timeinfo.tm_mon = month - 1;
      timeinfo.tm_mday = day;
      timeinfo.tm_hour = hour;
      timeinfo.tm_min = min;
      timeinfo.tm_sec = sec;
      timeinfo.tm_isdst = 0;
      return timeinfo;
    } else {
      Serial.println("Couldn't get network time, retrying in 5s.");
      delay(5000);
    }
  }
  return timeinfo;
}

void turn_off_modem() {
  digitalWrite(PWR_ON_PIN, LOW);
}
