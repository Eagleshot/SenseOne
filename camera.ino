void camera_init() {
  Serial.println("Camera init");

  if (!psramFound()) {
    Serial.println("PSRAM is required for maximum image quality. Rebooting.");
    delay(250);
    ESP.restart();
    return;
  }
  Serial.println("PSRAM found");

  camera_config_t config;
  config.ledc_channel = LEDC_CHANNEL_0;
  config.ledc_timer = LEDC_TIMER_0;
  config.pin_d0 = CAM_Y2_PIN;
  config.pin_d1 = CAM_Y3_PIN;
  config.pin_d2 = CAM_Y4_PIN;
  config.pin_d3 = CAM_Y5_PIN;
  config.pin_d4 = CAM_Y6_PIN;
  config.pin_d5 = CAM_Y7_PIN;
  config.pin_d6 = CAM_Y8_PIN;
  config.pin_d7 = CAM_Y9_PIN;
  config.pin_xclk = CAM_XCLK_PIN;
  config.pin_pclk = CAM_PCLK_PIN;
  config.pin_vsync = CAM_VSYNC_PIN;
  config.pin_href = CAM_HREF_PIN;
  config.pin_sccb_sda = CAM_SIOD_PIN;
  config.pin_sccb_scl = CAM_SIOC_PIN;
  config.pin_pwdn = CAM_PWDN_PIN;
  config.pin_reset = CAM_RESET_PIN;
  config.xclk_freq_hz = 20000000;
  config.pixel_format = PIXFORMAT_JPEG; // for upload
  config.frame_size = FRAMESIZE_UXGA; // 1600x1200 (max for OV2640)
  config.jpeg_quality = 0;             // Lowest compression = highest JPEG quality
  config.fb_count = 1;
  config.fb_location = CAMERA_FB_IN_PSRAM;
  config.grab_mode = CAMERA_GRAB_LATEST;

  esp_err_t err = esp_camera_init(&config);
  if (err != ESP_OK) {
    Serial.printf("Camera init failed with error 0x%x", err);
    ESP.restart();
    return;
  }

  // Keep auto controls enabled for outdoor/indoor transitions.
  sensor_t * s = esp_camera_sensor_get();
  s->set_framesize(s, FRAMESIZE_UXGA);
  s->set_quality(s, 10);
  s->set_whitebal(s, 1);       // 0 = disable , 1 = enable
  s->set_awb_gain(s, 1);       // 0 = disable , 1 = enable
  s->set_wb_mode(s, 0);        // 0 = Auto
  s->set_exposure_ctrl(s, 1);  // 0 = disable , 1 = enable
  s->set_gain_ctrl(s, 1);      // 0 = disable , 1 = enable
  s->set_gainceiling(s, GAINCEILING_16X);
  s->set_aec2(s, 1);           // Improve auto-exposure behavior
  s->set_ae_level(s, 0);         // -2..2
  
  s->set_brightness(s, 0);       // -2..2
  s->set_contrast(s, 1);         // -2..2
  s->set_saturation(s, 0);       // -2..2

  s->set_lenc(s, 1);           // 0 = disable , 1 = enable
  s->set_bpc(s, 1);            // Black pixel correction
  s->set_wpc(s, 1);            // White pixel correction

  // Print camera details
  Serial.println("Camera initialized successfully!");
  Serial.print("Camera Model: ");
  switch (s->id.PID) {
    case OV2640_PID:
      Serial.println("OV2640");
      break;
    case OV3660_PID:
      Serial.println("OV3660");
      break;
    default:
      Serial.println("Unknown");
  }
}

// Take a picture and return the framebuffer
camera_fb_t* camera_snap_image() {
  camera_fb_t *fb = esp_camera_fb_get();
  if (!fb) {
    Serial.println("Error taking image!");
    return nullptr;
  }

  Serial.print("Successfully taken image: ");
  Serial.print(fb->len);
  Serial.println(" bytes.");
  return fb; // Return the framebuffer
}

// Return the framebuffer to the driver for reuse
void camera_fb_return(camera_fb_t *fb) {
    esp_camera_fb_return(fb);
  }