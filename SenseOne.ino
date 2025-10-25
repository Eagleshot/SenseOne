/////////////////////////////////////////////////////////////////
/*
  T-SIMCAM, Upload images anywhere with an 4G LTE modem.
  For More Information: https://youtu.be/kOYJ-4oZ8Ws
  Created by Eric N. (ThatProject)
*/
/////////////////////////////////////////////////////////////////

// Settings:
// ESP32S3 Dev Module
// Tools -> USB CDC on Boot: "Enabled"
// Tools -> PSRAM: "OPI PSRAM"

// /home/eagleshot_drone/uploads/image_1761387750960.jpg
/*Verison*/
//ESP32 Arduino 2.3.3
//TinyGSM 0.12.0

// TODOs:

// Timestamp uploaded images -> different time sources?
// Upload from SD card
// Check GPRS
// Change modem speed - Serial1.println("AT+IPR=230400"); // TODO Change modem speed
// EEPROM for settings etc. - #include <EEPROM.h>
// Deep sleep/modem power down/power measurement
// FastAPI instead of nodejs
// Server to docker?
// Time sync internet/gps
// Domain instead of ip
// Save sensor data
// Remote firmware update

// Config
#include "config.h"

// Camera
#include "esp_camera.h"

// Modem
const char server[] = "34.65.195.210";
const int port = 3000;
const char resource[] = "/upload";

const char apn[] = "gprs.swisscom.ch";
const char gprsUser[] = "";
const char gprsPass[] = "";

#define TINY_GSM_MODEM_SIM7600
#include <HardwareSerial.h>
#include <TinyGsmClient.h>

#define TINY_GSM_USE_GPRS false
#define CHUNK_SIZE        1500

#define uS_TO_S_FACTOR 1000000ULL
#define TIME_TO_SLEEP  20
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
  Serial1.begin(115200, SERIAL_8N1, PCIE_RX_PIN, PCIE_TX_PIN); // Modem serial

  // Initialize camera and snap image
  camera_init();
  camera_fb_t *fb = camera_snap_image();

  // Initialize SD card and test
  bool sd_card_connected = sd_begin();

  // Initialize modem
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

  // Connect to GPRS
  Serial.print("Connecting to ");
  Serial.println(apn);

  const int MAX_GPRS_RETRIES = 5;
  int attempt = 0;
  bool gprs_ok = false;
  while (attempt++ < MAX_GPRS_RETRIES) {
    if (modem.gprsConnect(apn, gprsUser, gprsPass)) {
      gprs_ok = true;
      break;
    }
    Serial.println("GPRS attempt failed, retrying...");
    delay(2000 * attempt); // simple backoff
  }

  if (gprs_ok && modem.isGprsConnected()) {
    Serial.println("GPRS connected - uploading image...");
    // uploadImage(fb);
  } else if (sd_card_connected) {
    Serial.println("GPRS not connected - saving to sd card...");
    sd_write_image("/image.jpg", fb);
    sd_end();
  }
  turn_off_modem();
  camera_fb_return(fb);

  // Go to deep sleep (resets the MCU)
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
  Serial.println("Sleeping for " + String(TIME_TO_SLEEP) + "s");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Do nothing
}
