//unit testing the sender part of the esp_now protocol
#include<WiFi.h>
#include<esp_wifi.h>
#include<esp_now.h>

//setting up the receiver MAC address
uint8_t receiverMac[] = {0xfc, 0xb4, 0x67, 0xf4, 0x58, 0xa8};

//defining the foot pins:
const int RIGHT_PIN = 33;
const int LEFT_PIN = 32;

//defining foot id's:
const uint8_t RIGHT = 1;
const uint8_t LEFT = 2;

//defining a step event:
typedef struct {
  uint32_t intervalMS;
  uint8_t footId;
} StepEvent;

StepEvent stepEvent;

//pressure threshold along with buffer for consistency:
const int THRESHOLD = 900; // Lowered from 700 to catch lighter steps
const int pressureBuffer = 200; // Lowered to ensure reset happens even with light contact

uint32_t lastStepTime = 0;


//foot pressure:
bool leftFlag = false;
bool rightFlag = false;
void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last send status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);
  pinMode(RIGHT_PIN, INPUT);
  pinMode(LEFT_PIN, INPUT);
  WiFi.mode(WIFI_STA);

  //initializing esp_now:
  if (esp_now_init() != ESP_OK) {
    Serial.println("Error initializing esp_now");
    return;
  }

  //configuring the sending protocol:
  esp_now_register_send_cb(onDataSent);
  esp_now_peer_info_t peerInfo = {};
  memcpy(peerInfo.peer_addr,receiverMac, 6);
  peerInfo.channel = 0;
  peerInfo.encrypt = false;

  if (esp_now_add_peer(&peerInfo) != ESP_OK) {
    Serial.println("Failed to add peer");
    return;
  }

  Serial.println("ready to send");
}

// --- FILTERING FUNCTION ---
// Reads the pin multiple times and returns the average to remove noise.
int readFiltered(int pin) {
  long sum = 0;
  const int SAMPLES = 20; // Take 20 readings fast
  for (int i=0; i<SAMPLES; i++) {
    sum += analogRead(pin);
  }
  return sum / SAMPLES;
}

void loop() {
  //getting the current time:
  uint32_t now =  millis();
  bool stepDetected = false;
  int stepFootId = 0;
  
  //getting the FILTERED fsr reading of the sensors:
  int rightFsr = readFiltered(RIGHT_PIN);
  int leftFsr = readFiltered(LEFT_PIN);
  Serial.println("pressure:");
  Serial.println(rightFsr);
  //resetting the flags:
  if(rightFsr <= THRESHOLD - pressureBuffer)
    rightFlag = false;
  if(leftFsr <= THRESHOLD - pressureBuffer)
    leftFlag = false;

  //checking if there is pressure on the sensors
  if(!rightFlag && rightFsr > THRESHOLD){
    rightFlag = true;
    stepDetected = true;
    stepFootId = 1;
  }
  if(!leftFlag && leftFsr > THRESHOLD){
    leftFlag = true;
    stepDetected = true;
    stepFootId = 2;
  }

  if(stepDetected){
    
    //sending step event using esp_now:
    Serial.println(rightFsr);
    stepEvent.intervalMS = now - lastStepTime;
    lastStepTime = now;
    stepEvent.footId = stepFootId;
    esp_err_t result = esp_now_send(receiverMac, (uint8_t*)&stepEvent, sizeof(StepEvent));
    if(result == ESP_OK){
      Serial.println("sent");
    }
    else{
      Serial.println("error sending the message");
      Serial.println(result);
    }
  }
}
