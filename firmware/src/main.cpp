// File: firmware/src/main.cpp
// Project: ESP32 SmartAlarm
// Description: ESP32 firmware for multi-timezone, MQTT-synced alarm clock

#include <Wire.h>                // I2C communication
#include <LiquidCrystal_I2C.h>  // I2C LCD library
#include <WiFi.h>                // Wi-Fi connectivity for ESP32
#include <PubSubClient.h>       // MQTT client library
#include <ArduinoJson.h>        // JSON parsing library
#include <ESP32Time.h>          // On-chip RTC library
#include <vector>               // C++ dynamic array

// === Wi-Fi credentials ===
const char* ssid     = "DESKTOP-3FR5V9E 5170";  // Your hotspot SSID
const char* password = "1L6d63{6";              // Your hotspot password

// === LCD Setup ===
#define LCD_ADDR 0x27         // I2C address (scan if unsure)
LiquidCrystal_I2C lcd(LCD_ADDR, 16, 2);  // 16x2 LCD

// === MQTT Setup ===
const char* mqttServer   = "34.118.86.6";  // MQTT broker IP
const uint16_t mqttPort  = 1883;            // MQTT port
const char* mqttUser     = "new_user";     // MQTT username
const char* mqttPassword = "first";        // MQTT password
WiFiClient    espClient;                     // Network client
PubSubClient  mqttClient(espClient);         // MQTT client

// === Timezone Definitions ===
struct TZ { long offset; const char* name; };
// offsets in seconds east of UTC
TZ zones[] = {
  {   0 * 3600, "UTC"      },  // UTC
  {   2 * 3600, "CET"      },  // CEST UTC+2
  {   5 * 3600, "Tashkent" },  // Tashkent UTC+5
  {  -4 * 3600, "EST"      }   // EDT UTC-4
};
const uint8_t ZONE_COUNT = sizeof(zones) / sizeof(zones[0]);
volatile uint8_t currentZone = 2;  // default index: Tashkent

// === Button Setup (active-low) ===
const uint8_t BUTTON_PIN = 0;          // GPIO0
const unsigned long DEBOUNCE = 200;    // ms debounce
volatile bool buttonPressed = false;   // ISR flag
unsigned long lastDebounceTime = 0;    // Last debounce timestamp
void IRAM_ATTR onButton() { buttonPressed = true; } // ISR

// === Buzzer Setup ===
const uint8_t BUZZER_PIN = 15;         // GPIO15 for tone()

// === Alarm Storage ===
// Each alarm has hour, minute, and zone name
struct Alarm { uint8_t h, m; String zone; };
std::vector<Alarm> alarms;

// === Real-Time Clock ===
ESP32Time rtc;  // Uses ESP32’s internal timer

// === MQTT Message Handler ===
void mqttCallback(char* topic, byte* payload, unsigned int len) {
  // Build message string from payload bytes
  String msg;
  for (unsigned int i = 0; i < len; i++) msg += (char)payload[i];

  if (String(topic) == "clock/sync") {
    // Sync message: JSON {"epoch": 1625074800}
    StaticJsonDocument<64> doc;
    deserializeJson(doc, msg);
    uint32_t epoch = doc["epoch"];
    rtc.setTime(epoch);  // Reset internal RTC to UTC epoch
  }
  else if (String(topic) == "clock/zone") {
    // Zone change: payload is zone name
    for (uint8_t i = 0; i < ZONE_COUNT; i++) {
      if (msg == zones[i].name) {
        currentZone = i;  // Update displayed & used zone
        break;
      }
    }
  }
  else if (String(topic) == "clock/alarms") {
    // Alarms update: JSON array of {"time":"HH:MM","zone":"XX"}
    alarms.clear();
    StaticJsonDocument<512> doc;
    deserializeJson(doc, msg);
    for (JsonObject obj : doc.as<JsonArray>()) {
      const char* t = obj["time"];
      String z = obj["zone"].as<const char*>();
      // Parse HH and MM
      uint8_t hh = (t[0] - '0') * 10 + (t[1] - '0');
      uint8_t mm = (t[3] - '0') * 10 + (t[4] - '0');
      alarms.push_back({hh, mm, z});
    }
  }
}

// === Ensure MQTT Connection ===
void ensureMqtt() {
  if (!mqttClient.connected()) {
    // Attempt to connect with client ID 'esp32-clock'
    if (mqttClient.connect("esp32-clock", mqttUser, mqttPassword)) {
      // Subscribe to topics on successful connect
      mqttClient.subscribe("clock/sync");
      mqttClient.subscribe("clock/zone");
      mqttClient.subscribe("clock/alarms");
    }
  }
}

// === Arduino setup() ===
void setup() {
  // Optional serial debug output
  Serial.begin(115200);

  // Initialize I2C and LCD
  Wire.begin(21, 22);
  lcd.init();
  lcd.backlight();
  lcd.clear();

  // Configure button input with pull-up and ISR
  pinMode(BUTTON_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(BUTTON_PIN), onButton, FALLING);

  // Configure buzzer pin as output
  pinMode(BUZZER_PIN, OUTPUT);
  digitalWrite(BUZZER_PIN, LOW);

  // Connect Wi-Fi
  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);
  while (WiFi.status() != WL_CONNECTED) {
    delay(500); // Wait until connected
  }

  // Initialize MQTT client
  mqttClient.setServer(mqttServer, mqttPort);
  mqttClient.setCallback(mqttCallback);
}

// === Arduino loop() ===
void loop() {
  // Reconnect/loop MQTT
  ensureMqtt();
  mqttClient.loop();

  // Handle button press to cycle zone
  if (buttonPressed && (millis() - lastDebounceTime) > DEBOUNCE) {
    buttonPressed = false;
    lastDebounceTime = millis();
    currentZone = (currentZone + 1) % ZONE_COUNT;
    mqttClient.publish("clock/zone", zones[currentZone].name);
  }

  // Compute local time: get RTC epoch, mod 24h, add offset, wrap
  uint32_t epoch = rtc.getEpoch();
  long secs = (long)(epoch % 86400) + zones[currentZone].offset;
  secs = (secs % 86400 + 86400) % 86400;
  uint8_t Dh = secs / 3600;
  uint8_t Dm = (secs % 3600) / 60;
  uint8_t Ds = secs % 60;

  // Update LCD display
  lcd.clear();
  lcd.setCursor(0, 0);
  char buf[17];
  snprintf(buf, sizeof(buf), "%02u:%02u:%02u", Dh, Dm, Ds);
  lcd.print(buf);
  lcd.setCursor(0, 1);
  lcd.print(zones[currentZone].name);

  // Check alarms: if any match current time & zone, beep
  for (auto &a : alarms) {
    if (a.zone == zones[currentZone].name && a.h == Dh && a.m == Dm) {
      tone(BUZZER_PIN, 1000);  // 1 kHz beep
      delay(3000);             // for 3 seconds
      noTone(BUZZER_PIN);
      break;                   // only one alarm per minute
    }
  }

  delay(200); // 0.2s between updates
}

