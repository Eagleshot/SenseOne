/////////////////////////////////////////////
// SD card
/////////////////////////////////////////////
// https://randomnerdtutorials.com/esp32-microsd-card-arduino/#datalogging

#include <SD_MMC.h>
#include <SPI.h>
#include <FS.h>

const int SDMMC_CLK = 5;
const int SDMMC_CMD = 4;
const int SDMMC_DATA = 6;
const int SD_CD_PIN = 46;


void setupSDCard() {
    pinMode(SD_CD_PIN, INPUT_PULLUP);
    delay(3000);
    SD_MMC.setPins(SDMMC_CLK, SDMMC_CMD, SDMMC_DATA);

    if (!SD_MMC.begin("/sdcard", true)) {
        Serial.println("Card Mount Failed");
        while(1) {};
    }
}

void printSDCardInfo() {

  uint8_t cardType = SD_MMC.cardType();

  if (cardType == CARD_NONE) {
    Serial.println("No SD_MMC card attached");
  } else {
    Serial.print("SD_MMC Card Type: ");
    if (cardType == CARD_MMC) {
        Serial.println("MMC");
    } else if (cardType == CARD_SD) {
        Serial.println("SDSC");
    } else if (cardType == CARD_SDHC) {
        Serial.println("SDHC");
    } else {
        Serial.println("UNKNOWN");
    }

    // Card size
    uint64_t cardSize = SD_MMC.cardSize() / (1024 * 1024);
    Serial.printf("SD_MMC Card Size: %lluMB\n", cardSize);
    }
}

void writeFileToSD(const char *filename, const char *data) {
    File file = SD_MMC.open(filename, FILE_WRITE);
    if (!file) {
        Serial.println("Failed to open file for writing");
        return;
    }
    if (file.print(data)) {
        Serial.println("File written");
    } else {
        Serial.println("Write failed");
    }
    file.close();
}