/////////////////////////////////////////////////////////////////
/*
  T-SIMCAM, Upload images anywhere with an 4G LTE modem.
  For More Information: https://youtu.be/kOYJ-4oZ8Ws
  Created by Eric N. (ThatProject)
*/
/////////////////////////////////////////////////////////////////

// Config
#include "config.h"

// Camera
#include "esp_camera.h"

#define uS_TO_S_FACTOR 1000000ULL
#define TIME_TO_SLEEP  20

// Time stuff
RTC_DATA_ATTR time_t stored_time; // Store time across deep sleep cycles

const char* weekdayStr(struct tm *t) {
  static const char* names[] = {"Sun","Mon","Tue","Wed","Thu","Fri","Sat"};
  return names[t->tm_wday];
}

// Get time as a filename-friendly string
String time_string(struct tm timeinfo) {
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
  if (tm_info == nullptr) {
    Serial.println("Time: (null)");
    return;
  }

  char buffer[32];
  if (strftime(buffer, sizeof(buffer), "%Y-%m-%d %H:%M:%S", tm_info) > 0) {
    Serial.println("Time: " + String(buffer));
  } else {
    Serial.println("Time: (invalid)");
  }
}

void setup() {

  pinMode(33, OUTPUT); // TODO
  digitalWrite(33, HIGH);

  // Initialize debug serial
  Serial.begin(115200);
  Serial.setDebugOutput(true);


  // Initialize modem  
  turn_on_modem(); // TODO

  // Time
  struct tm timeinfo = {};
  struct tm * tm_info = localtime(&stored_time);
  printTime(tm_info);

  // Initialize camera and snap image
  camera_init();
  camera_fb_t *fb = camera_snap_image();

  
  // Initialize LED
  setupLED();

  // Initialize SD card and test
  // setupSDCard();
  // printSDCardInfo();
  // bool sd_card_connected = sd_begin();

  // Initialize modem
  init_modem();
  modem_gprs_connect();
  // set_network_mode();
  print_connection_info();
  // wait_for_network();
  timeinfo = get_network_time(timeinfo);
  printTime(&timeinfo);

  bool server_connected = server_health_check();
  Serial.println(server_connected ? "Server connected" : "Server not connected");

  if (modem_is_gprs_connected()) {
    if (fb) {
      Serial.println("GPRS connected - uploading image...");
      uploadImage(fb, (time_string(timeinfo) + ".jpg").c_str());
    } else {
      Serial.println("GPRS connected, but no image captured; skipping upload.");
    }
  } else {
    Serial.println("Cannot upload or save image!");
  }
  
  /*else if (sd_card_connected) {
    Serial.println("GPRS not connected - saving to sd card...");
    sd_write_image(("/" + time_string(timeinfo) + ".jpg").c_str(), fb);
    sd_end();
  } */


  turn_off_modem();
  if (fb) {
    camera_fb_return(fb);
  }

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
