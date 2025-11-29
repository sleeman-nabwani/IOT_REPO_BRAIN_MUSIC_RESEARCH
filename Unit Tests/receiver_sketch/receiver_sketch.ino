// Receiver: ESP-NOW -> USB serial
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

volatile bool messageRecv = false;

// MUST match sender struct
typedef struct {
  uint32_t time_ms;
  uint8_t  foot_id;
  uint16_t fsr_peak;
  uint16_t contact_ms;
  float    cadence_spm;
} StepEvent;

StepEvent lastStep;

void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len){
  if (len != sizeof(StepEvent)) {
    // unexpected packet, ignore
    return;
  }

  memcpy(&lastStep, incomingData, sizeof(StepEvent));
  messageRecv = true;

  // One clean line for PC:
  // STEP,time_ms,foot,fsr_peak,contact_ms,cadence_spm
  Serial.print("STEP,");
  Serial.print(lastStep.time_ms);
  Serial.print(",");
  Serial.print(lastStep.foot_id);
  Serial.print(",");
  Serial.print(lastStep.fsr_peak);
  Serial.print(",");
  Serial.print(lastStep.contact_ms);
  Serial.print(",");
  Serial.println(lastStep.cadence_spm, 2); // 2 decimals
}

void setup() {
  Serial.begin(115200);

  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing esp_now");
    return;
  }

  esp_now_register_recv_cb(onDataRecv);

  Serial.println("Receiver ready");
}

void loop() {
  if (messageRecv) {
    messageRecv = false;

    // Blink LED on each received step
    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }
}
