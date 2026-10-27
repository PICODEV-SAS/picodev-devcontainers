// Blinks the on-board LED (D13) and says hello on the serial port, 115200 baud.

// Arduino.h is implicit in a sketch; written here so that clangd sees it too.
#include <Arduino.h>

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
  Serial.println("Hello from Picodev");
}

void loop() {
  digitalWrite(LED_BUILTIN, !digitalRead(LED_BUILTIN));
  delay(500);
}
