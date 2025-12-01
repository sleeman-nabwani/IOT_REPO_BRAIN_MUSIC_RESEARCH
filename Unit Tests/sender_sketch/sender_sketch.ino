#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

// ==== CONFIGURATION ====
// Setting up the receiver MAC address
uint8_t receiverMac[] = {0xfc, 0xb4, 0x67, 0xf4, 0x58, 0xa8};


// Defining foot pins
const int RIGHT_PIN = 33;
const int LEFT_PIN  = 32;

// Variables to track state
const uint8_t rightLeg = 1;
const uint8_t leftLeg = 2;

// Thresholds to detect a step
const int THRESHOLD = 700;
const int PRESSURE_BUFFER = 300;

// ==== DATA PACKET ====
// Must match the Receiver exactly
typedef struct {
  uint32_t time;    // Timestamp
  uint8_t footId;   // 1=Right, 2=Left
  int pressure;     // Force of the step
} StepEvent;

StepEvent stepEvent;

// Optional: Callback to see if message left the board
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  // You can leave this empty
}

void setup() {
  Serial.begin(115200);
  pinMode(RIGHT_PIN, INPUT);
  pinMode(LEFT_PIN, INPUT);

  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  esp_now_register_send_cb(onDataSent);

  // Register the Receiver
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, receiverMac, 6);
  peerInfo.channel = 0;  
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }
}

void loop() {
  unsigned long now = millis();
  bool stepDetected = false;
  int currentFootId = 0;

  // 1. Read Sensors
  int rightVal = analogRead(RIGHT_PIN);
  int leftVal  = analogRead(LEFT_PIN);

  // 2. Reset Flags (Hysteresis)
  // If pressure drops, we are ready for a new step
  if(rightVal <= THRESHOLD - PRESSURE_BUFFER) rightFlag = false;
  if(leftVal  <= THRESHOLD - PRESSURE_BUFFER) leftFlag  = false;

  // 3. Detect Right Step
  if(!rightFlag && rightVal > THRESHOLD) {
    rightFlag = true;
    stepDetected = true;
    currentFootId = 1;
    stepEvent.pressure = rightVal; // Store pressure
  }
  
  // 4. Detect Left Step
  if(!leftFlag && leftVal > THRESHOLD) {
    leftFlag = true;
    stepDetected = true;
    currentFootId = 2;
    stepEvent.pressure = leftVal;  // Store pressure
  }

  // 5. Send Data Wireless
  if(stepDetected) {
    stepEvent.time = now;
    stepEvent.footId = currentFootId;

    // Send struct to Receiver
    esp_now_send(receiverMac, (uint8_t*)&stepEvent, sizeof(StepEvent));
    
    // Small delay to prevent double-sending
    delay(20); 
  }
}