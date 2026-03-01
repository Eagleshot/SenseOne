/////////////////////////////////////////////
// LED
/////////////////////////////////////////////

#include <Adafruit_NeoPixel.h>

Adafruit_NeoPixel strip = Adafruit_NeoPixel(1, 38, NEO_RGB + NEO_KHZ800);

void setupLED() {
  strip.begin();
  strip.setBrightness(100);
  strip.setPixelColor(0, strip.Color(0, 255, 0)); // Green
  strip.show();
}