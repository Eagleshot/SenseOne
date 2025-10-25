/////////////////////////////////////////////////////////////////
/*
  T-SIMCAM, Upload images anywhere with an 4G LTE modem.
  For More Information: https://youtu.be/kOYJ-4oZ8Ws
  Created by Eric N. (ThatProject)
*/
/////////////////////////////////////////////////////////////////

// Enable USB CDC on boot for serial output over USB!!!
// Tools -> PSRAM:"OPI PSRAM"
// /home/eagleshot_drone/uploads/image_1761385422652.jpg
/*Verison*/
//ESP32 Arduino 2.3.3
//TinyGSM 0.12.0

// Make code more readable
// Check GPRS
// Deep sleep/modem power down/power measurement
// Server to docker?
// Save to sd card/backup
// Time sync internet/gps
// Domain instead of ip
// Save sensor data
// Remote firmware update

#define TINY_GSM_MODEM_SIM7600
#include "config.h"
#include "esp_camera.h"
#include <HardwareSerial.h>
#include <TinyGsmClient.h>

const char server[] = "34.65.195.210";
const int port = 3000;
const char resource[] = "/upload";

const char apn[] = "gprs.swisscom.ch";
const char gprsUser[] = "";
const char gprsPass[] = "";

#define TINY_GSM_USE_GPRS false
#define CHUNK_SIZE        1500

#define uS_TO_S_FACTOR 1000000ULL
#define TIME_TO_SLEEP  60
TinyGsm modem(Serial1);
TinyGsmClient client(modem, 0);

void setup() {

  // Initialize debug serial
  Serial.begin(115200);
  Serial.setDebugOutput(true);

  // Initialize modem power  
  pinMode(PWR_ON_PIN, OUTPUT);
  pinMode(PCIE_PWR_PIN, OUTPUT);
  turn_on_modem();

  // Initialize camera
  if (!psramFound()) {
    Serial.println("No PSRAM found!");
  }
  camera_init();

  // Initialize modem serial (AT commands)
  Serial1.begin(115200, SERIAL_8N1, PCIE_RX_PIN, PCIE_TX_PIN);
  // Serial1.println("AT+IPR=230400"); // TODO Change modem speed

  Serial.println("Initializing modem...");
  modem.init();

  String modemInfo = modem.getModemInfo();
  Serial.print("Modem - ");
  Serial.println(modemInfo);

  // Set Network Mode
  // 2 Automatic , 13 GSM only , 38 LTE only , 51 GSM and LTE only
  int res;
  do {
    res = modem.setNetworkMode(38);
    Serial.print("Modem Set LTE: ");
    Serial.println(res);
    if (res != 1) {
      delay(500);
    }
  } while (res != 1);

  Serial1.println("AT+CPSI?"); // Get connection type and band
  delay(500);
  if (Serial1.available()) {
    String r = Serial1.readString();
    Serial.println(r);
  }

  Serial.println("---End of GPRS TEST---");

  Serial.print("Waiting for network...");
  if (!modem.waitForNetwork()) {
    Serial.println("Modem Fail");
    delay(750);
    return;
  }
  Serial.println(" success");

  if (modem.isNetworkConnected()) {
    Serial.println("Network connected");
  }

  Serial.print("Connecting to ");
  Serial.println(apn);
  if (!modem.gprsConnect(apn, gprsUser, gprsPass)) {
    Serial.println("GPRS fail");
    delay(10000);
    return;
  }

  if (modem.isGprsConnected()) {
    Serial.println("GPRS connected");
    takeShot();
  }

  turn_off_modem();

  // Go to deep sleep
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
  Serial.println("Sleeping for " + String(TIME_TO_SLEEP) + "s");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Do nothing
}

void takeShot() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Error taking image!");
    return;
  }

  Serial.print("Successfully taken image: ");
  Serial.print(fb->len);
  Serial.println(" bytes.");

  if (!client.connect(server, port)) {
    Serial.println("Connection to server failed!");
  } else {
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

  esp_camera_fb_return(fb);
}

