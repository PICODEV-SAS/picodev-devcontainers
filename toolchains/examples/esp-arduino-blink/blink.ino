// Arduino core for ESP32: blink and say hello on the serial port.
#ifndef LED_BUILTIN
#define LED_BUILTIN 2
#endif

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  Serial.begin(115200);
}

void loop() {
  static bool on;
  on = !on;
  digitalWrite(LED_BUILTIN, on);
  Serial.println("hello");
  delay(500);
}
