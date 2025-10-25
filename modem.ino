void turn_on_modem() {
  digitalWrite(PWR_ON_PIN, HIGH); // Turn on power to the modem

  digitalWrite(PCIE_PWR_PIN, 1); // Reset the modem
  delay(500);
  digitalWrite(PCIE_PWR_PIN, 0);
  delay(3000);
}

void turn_off_modem() {
  digitalWrite(PWR_ON_PIN, LOW);
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
