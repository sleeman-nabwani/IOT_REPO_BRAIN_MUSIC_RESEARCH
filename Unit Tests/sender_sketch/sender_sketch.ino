#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

// ==== CONFIG – CHANGE THESE TO MATCH YOUR SETUP ====

// FSR pins:
const int RIGHT_FSR_PIN = 33;
const int LEFT_FSR_PIN  = 32;

// Threshold for detecting contact (tune this!):
const int THRESHOLD = 300;
const int RELEASE_THRESHOLD = THRESHOLD * 0.5; // hysteresis

// Receiver MAC address:
uint8_t receiverMac[] = {0xfc, 0xb4, 0x67, 0xf4, 0x58, 0xa8};

// Number of steps to use for cadence window:
const int CADENCE_WINDOW_STEPS = 8;

// ===================================================


// Step event struct (MUST MATCH RECEIVER)
typedef struct {
  uint32_t time_ms;     // touchdown time
  uint8_t  foot_id;     // 1 = right, 2 = left
  uint16_t fsr_peak;    // peak FSR during contact
  uint16_t contact_ms;  // contact duration
  float    cadence_spm; // steps per minute
} StepEvent;


// State per foot
struct FootState {
  bool inContact;
  uint32_t tOn;
  uint16_t fsrPeak;
};

FootState rightFoot = {false, 0, 0};
FootState leftFoot  = {false, 0, 0};

// Cadence state
uint32_t stepTimes[CADENCE_WINDOW_STEPS];
int stepIndex = 0;
int stepsSeen = 0;
float currentCadenceSPM = 0.0f;

// ====== Cadence calculation ======
float updateCadence(uint32_t now_ms) {
  stepTimes[stepIndex] = now_ms;
  stepIndex = (stepIndex + 1) % CADENCE_WINDOW_STEPS;
  if (stepsSeen < CADENCE_WINDOW_STEPS) {
    stepsSeen++;
  }

  if (stepsSeen < 2) {
    // not enough steps yet
    currentCadenceSPM = 0.0f;
    return currentCadenceSPM;
  }

  // Oldest timestamp in window
  int oldestIndex = (stepIndex - stepsSeen + CADENCE_WINDOW_STEPS) % CADENCE_WINDOW_STEPS;
  uint32_t oldest = stepTimes[oldestIndex];
  uint32_t dt_ms = now_ms - oldest;
  if (dt_ms == 0) {
    return currentCadenceSPM; // avoid division by zero
  }

  // (stepsSeen-1) intervals between stepsSeen steps
  float spm = (float)(stepsSeen - 1) * 60000.0f / (float)dt_ms;
  currentCadenceSPM = spm;
  return spm;
}

// ====== Send one step event ======
void sendStep(uint8_t foot_id, uint16_t fsrPeak, uint16_t contact_ms, uint32_t tOn) {
  float cadence = updateCadence(tOn);

  StepEvent step;
  step.time_ms     = tOn;
  step.foot_id     = foot_id;
  step.fsr_peak    = fsrPeak;
  step.contact_ms  = contact_ms;
  step.cadence_spm = cadence;

  esp_err_t result = esp_now_send(receiverMac, (uint8_t *)&step, sizeof(step));
  if (result == ESP_OK) {
    Serial.print("Step sent: foot=");
    Serial.print(foot_id);
    Serial.print(" peak=");
    Serial.print(fsrPeak);
    Serial.print(" contact_ms=");
    Serial.print(contact_ms);
    Serial.print(" cadence=");
    Serial.println(cadence);
  } else {
    Serial.print("Error sending step, code ");
    Serial.println(result);
  }
}

// ====== ESP-NOW send callback (optional debug) ======
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last send status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

// ====== Setup ======
void setup() {
  Serial.begin(115200);

  pinMode(RIGHT_FSR_PIN, INPUT);
  pinMode(LEFT_FSR_PIN, INPUT);

  WiFi.mode(WIFI_STA);

  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing esp_now");
    return;
  }

  esp_now_register_send_cb(onDataSent);

  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr, receiverMac, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("Sender ready (FSR steps with cadence)");
}

// ====== Foot handling helper ======
void handleFoot(FootState &foot, uint8_t foot_id, int val, uint32_t now) {
  if (!foot.inContact && val > THRESHOLD) {
    // Foot just touched down
    foot.inContact = true;
    foot.tOn = now;
    foot.fsrPeak = val;
  } else if (foot.inContact) {
    // Update peak
    if (val > foot.fsrPeak) {
      foot.fsrPeak = val;
    }
    // Foot lifted
    if (val < RELEASE_THRESHOLD) {
      foot.inContact = false;
      uint32_t contact = now - foot.tOn;
      sendStep(foot_id, foot.fsrPeak, (uint16_t)contact, foot.tOn);
    }
  }
}

// ====== Main loop ======
void loop() {
  uint32_t now = millis();

  int rightVal = analogRead(RIGHT_FSR_PIN);
  int leftVal  = analogRead(LEFT_FSR_PIN);

  handleFoot(rightFoot, 1, rightVal, now);
  handleFoot(leftFoot,  2, leftVal,  now);

  delay(5); // small delay for stability
}
