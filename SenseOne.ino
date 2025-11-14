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

// /home/eagleshot_drone/uploads/20251031_1529Z.jpg
/*Verison*/
//ESP32 Arduino 2.3.3
//TinyGSM 0.12.0

// TODOs:

// Timestamp uploaded images -> different time sources?
// Upload from SD card
// Check GPRS - at+cops=?
// Change modem speed - Serial1.println("AT+IPR=230400"); // TODO Change modem speed
// EEPROM for settings etc. - #include <EEPROM.h>
// Deep sleep/modem power down/power measurement
// FastAPI instead of nodejs
// Server to docker?
// Time sync internet/gps
// Domain instead of ip
// Save sensor data
// Remote firmware update
// Location and time - GPS und GSM

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

// Time stuff
RTC_DATA_ATTR time_t stored_time; // Store time across deep sleep cycles

const char* weekdayStr(struct tm *t) {
  static const char* names[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
  return names[t->tm_wday];
}

// Get time as a filename-friendly string
String network_time(struct tm timeinfo) {
  char buffer[20];
  sprintf(buffer, "%04d%02d%02d_%02d%02dZ",
          timeinfo.tm_year + 1900,
          timeinfo.tm_mon + 1,
          timeinfo.tm_mday,
          timeinfo.tm_hour,
          timeinfo.tm_min);
  return String(buffer);
}

void printTime(struct tm *tm_info) {
  Serial.println("Time: " + String(ctime(&stored_time)));
}

void setup() {

  // Initialize debug serial
  Serial.begin(115200);
  Serial.setDebugOutput(true);

  // Initialize modem  
  pinMode(PWR_ON_PIN, OUTPUT);
  pinMode(PCIE_PWR_PIN, OUTPUT);
  turn_on_modem();

  // Time
  struct tm timeinfo;  
  struct tm * tm_info = localtime(&stored_time);
  printTime(tm_info);

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
  timeinfo = get_network_time(timeinfo);
  printTime(&timeinfo);
  modem_gprs_connect(gprsApn, gprsUser, gprsPass);

  if (modem_is_gprs_connected()) {
    Serial.println("GPRS connected - uploading image...");
    uploadImage(fb, (network_time(timeinfo) + ".jpg").c_str());
  } else if (sd_card_connected) {
    Serial.println("GPRS not connected - saving to sd card...");
    sd_write_image(("/" + network_time(timeinfo) + ".jpg").c_str(), fb);
    sd_end();
  } else {
    Serial.println("Cannot upload or save image!");
  }

  turn_off_modem();
  camera_fb_return(fb);

  // Save the current time
  stored_time = mktime(&timeinfo);
  Serial.println("Saving time for next wake: " + String(ctime(&stored_time)));

  // Go to deep sleep (resets the MCU)
  esp_sleep_enable_timer_wakeup(TIME_TO_SLEEP * uS_TO_S_FACTOR);
  Serial.println("Sleeping for " + String(TIME_TO_SLEEP) + "s");
  Serial.flush();
  esp_deep_sleep_start();
}

void loop() {
  // Do nothing
}
