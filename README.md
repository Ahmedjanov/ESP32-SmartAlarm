# ESP32-SmartAlarm
ESP32 SmartAlarm is a multi-timezone, MQTT-powered alarm clock built with an ESP32,
a Flask web server, and a 16×2 I²C LCD. 
Set alarms and switch zones from your browser or the onboard button.

## Table of Contents
- [Features](#features)
- [Hardware](#hardware)
- [Building](#build)
- [Software](#software)
- [Directory Structure](#directory-structure)


## Features
- 🕑 Multi-timezone display (UTC, CET/CEST, Tashkent, EST/EDT)
- 📱 Web UI for viewing time, cycling zones, and setting alarms
- 🔔 Buzzer alarms tied to specific zones
- 🔄 Local RTC (ESP32Time) with 15-minute MQTT sync
- 🔀 Hardware button for zone switching

## Hardware
- ESP32 DevKit C
- 16×2 I²C LCD (HD44780)
- Pushbutton (GPIO0)
- Buzzer (GPIO15)
- Breadboard and jumper wires

## Build
### Hardware Connections
#### I²C LCD (16×2 w/ PCF8574 backpack)
- **VCC** → ESP32 **5 V**  
- **GND** → ESP32 **GND**  
- **SDA** → ESP32 **GPIO 21**  
- **SCL** → ESP32 **GPIO 22**  
- Adjust the contrast potentiometer on the backpack until you see faint blocks, then back off until only characters show clearly.

#### Pushbutton (zone-cycle)
- One leg → ESP32 **GPIO 0**  
- Other leg → ESP32 **GND**  
- Uses the internal pull-up (`pinMode(BUTTON_PIN, INPUT_PULLUP)`).

#### Buzzer
- **+** (positive) → ESP32 **GPIO 15**  
- **–** (negative) → ESP32 **GND**  
- Uses `tone(BUZZER_PIN, 1000)` / `noTone(BUZZER_PIN)` in code.

#### Power & Ground
- Ensure **all** GNDs are common (ESP32, LCD, buzzer).  
- Power the LCD from the 5 V pin on the ESP32 board (not 3.3 V) if it’s a 5 V module.


1. Plug the LCD backpack into the breadboard, wire its SDA/SCL lines to 21/22 on the ESP32.  
2. Place a pushbutton so it bridges GPIO 0 to GND when pressed.  
3. Connect the buzzer’s positive lead to GPIO 15 and its negative lead to GND.  
4. Power the ESP32 from your USB or a 5 V supply; the LCD and buzzer share its GND.

Once wired, proceed to upload the firmware and start your Flask server—your ESP32 SmartAlarm should spring to life!



## Software
- **Firmware**: PlatformIO with Arduino framework
  - `LiquidCrystal_I2C`, `PubSubClient`, `ArduinoJson`, `ESP32Time`
- **Server**: Python 3.9+, Flask, paho-mqtt
- **MQTT Broker**: e.g. Mosquitto (running on `localhost:1883`)
## Directory Structure
ESP32-SmartAlarm/
├── firmware/
│   ├── src/
│   │   └── main.cpp
│   └── platformio.ini
├── server/
│   ├── time_server.py
│   └── requirements.txt
├── docs/
│   └── architecture.md
├── README.md






