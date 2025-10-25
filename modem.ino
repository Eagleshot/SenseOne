// Modem
const char server[] = "34.65.195.210";
const int port = 3000;
const char resource[] = "/upload";


#define TINY_GSM_MODEM_SIM7600
#include <HardwareSerial.h>
#include <TinyGsmClient.h>

#define TINY_GSM_USE_GPRS false
#define CHUNK_SIZE        1500

TinyGsm modem(Serial1);
TinyGsmClient client(modem, 0);

void turn_on_modem() {
  digitalWrite(PWR_ON_PIN, HIGH); // Turn on power to the modem

  digitalWrite(PCIE_PWR_PIN, 1); // Reset the modem
  delay(500);
  digitalWrite(PCIE_PWR_PIN, 0);
  delay(3000);
}

// Initialize the modem and print its information
void init_modem() {
  Serial.println("Initializing modem...");
  Serial1.begin(115200, SERIAL_8N1, PCIE_RX_PIN, PCIE_TX_PIN); // Modem serial
  modem.init();

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

void modem_gprs_connect(const char* apn, const char* user, const char* pass) {
  int max_retries = 5;
  for (int attempt = 0; attempt < max_retries; attempt++) {
    if (modem.gprsConnect(apn, user, pass)) {
      return;
    }
    Serial.println("GPRS connection failed, retrying...");
    delay(2000 * attempt); // Simple backoff
  }
}

int modem_is_gprs_connected(void) {
  return modem.isGprsConnected();
}


void uploadImage(camera_fb_t *fb) {
  if (!client.connect(server, port)) {
    Serial.println("Connection to server failed!");
    return;
  }

  unsigned long currentTotalTime = millis();
  client.print(String("POST ") + resource + " HTTP/1.1\r\n");
  client.print(String("Host: ") + server + "\r\n");
  client.print("Content-Length: ");
  client.print(fb->len);
  client.print("\r\n");
  client.print("Content-Type: image/jpeg\r\n");
  client.println();
  client.flush();

  uint8_t tmp[CHUNK_SIZE] = {0};
  size_t blen = sizeof(tmp);
  size_t i = 0;
  size_t len = fb->len;
  int sent_size = 0;

  for (i = 0; i < len / blen; ++i) {
    memcpy(tmp, fb->buf + (i * blen), blen);
    sent_size = client.write(tmp, CHUNK_SIZE);
  }

  if (len % blen) {
    size_t rest = len % blen;
    memcpy(tmp, fb->buf + (len - len % blen), rest);
    sent_size = client.write(tmp, rest);
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
  int read_chars = 0;
  while (client.connected() && millis() - start < 10000L) {
    while (client.available()) {
      logo[read_chars] = client.read();
      logo[read_chars + 1] = '\0';
      read_chars++;
      start = millis();
    }
  }
  Serial.println(logo);
  client.stop();
}

void turn_off_modem() {
  digitalWrite(PWR_ON_PIN, LOW);
}
