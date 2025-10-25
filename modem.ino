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