#include "FS.h"
#include "SD.h"
#include "config.h"

// Initialize and test SD card. Returns true if successful.
bool sd_begin(void) {
    SPI.begin(SD_SCLK_PIN, SD_MISO_PIN, SD_MOSI_PIN, SD_CS_PIN);
    if (!SD.begin(SD_CS_PIN, SPI)) {
        Serial.println("Card mount failed.");
        return false;
    }
    uint8_t cardType = SD.cardType();
    if (cardType == CARD_NONE) {
        Serial.println("No SD card attached.");
        return false;
    }

    Serial.print("SD card - type: ");
    if (cardType == CARD_MMC)
        Serial.print("MMC");
    else if (cardType == CARD_SD)
        Serial.print("SDSC");
    else if (cardType == CARD_SDHC)
        Serial.print("SDHC");
    else
        Serial.print("UNKNOWN");

    uint64_t cardSize = SD.cardSize() / (1024 * 1024);
    Serial.print(", size: ");
    Serial.print(cardSize);
    Serial.println("MB");
    return true;
}

// Write an image to the SD card. Returns true if successful.
bool sd_write_image(const char* path, camera_fb_t *fb) {
    Serial.printf("Writing file: %s\n", path);
    File file = SD.open(path, FILE_WRITE);
    if (!file) {
        Serial.println("Failed to open file for writing");
        return false;
    }
    size_t written = file.write(fb->buf, fb->len);
    file.close();
    Serial.printf("Wrote %u bytes to %s\n", written, path);
    return written == fb->len;
}

// Deinitialize SD card interface and release resources
void sd_end(void) {
    SD.end();
}
