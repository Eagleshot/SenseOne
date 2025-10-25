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

// /home/eagleshot_drone/uploads/image_1761423114435.jpg
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
#include "time.h"

// Camera
#include "esp_camera.h"

#define uS_TO_S_FACTOR 1000000ULL
#define TIME_TO_SLEEP  20

const char gprsApn[] = "gprs.swisscom.ch";
const char gprsUser[] = "";
const char gprsPass[] = "";

void setup() {

  // Initialize debug serial
  Serial.begin(115200);
  Serial.setDebugOutput(true);

  // Initialize modem  
  pinMode(PWR_ON_PIN, OUTPUT);
  pinMode(PCIE_PWR_PIN, OUTPUT);
  turn_on_modem();

  // Initialize camera and snap image
  camera_init();
  camera_fb_t *fb = camera_snap_image();

  // Initialize SD card and test
  bool sd_card_connected = sd_begin();

  // Initialize modem
  init_modem();
  set_network_mode();
  print_connection_info();
  wait_for_network();
  modem_gprs_connect(gprsApn, gprsUser, gprsPass);

  if (modem_is_gprs_connected()) {
    Serial.println("GPRS connected - uploading image...");
    uploadImage(fb);
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
