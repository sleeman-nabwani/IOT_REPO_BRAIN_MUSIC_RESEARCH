#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

// receiver: sender ESP-> bpm calculation -> USB 
volatile bool messageRecv = false;

// same struct as the sender
typedef struct {
  uint32_t intervalMS;
  uint8_t  footId;
} StepEvent;

StepEvent lastStep;

void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  if (len != sizeof(StepEvent)) {
    
    return;
  }

  memcpy(&lastStep, incomingData, sizeof(StepEvent));
  messageRecv = true;

  // STEP,interval_ms,foot
  Serial.print("STEP,");
  Serial.print(lastStep.intervalMS);
  Serial.print(",");
  Serial.println(lastStep.footId);
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing ESP-NOW");
    return;
  }

  esp_now_register_recv_cb(onDataRecv);

  Serial.println("Step receiver ready");
}

void loop() {
  if (messageRecv) {
    messageRecv = false;

    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }
}

