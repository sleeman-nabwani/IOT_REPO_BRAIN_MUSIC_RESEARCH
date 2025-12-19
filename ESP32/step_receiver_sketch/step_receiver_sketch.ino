#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

// ==== SETTINGS ====
int smoothingWindow = 3;  // Steps to average for BPM (changeable via serial)
int updateStride = 1; // Update BPM every N steps (changeable via serial)
const int TIMEOUT_MS = 10000;     // Reset BPM if no steps for 3 seconds
bool sessionStarted = false;
bool sessionStarting = true;
uint32_t sessionStartTime = 0;
int stepCounter = 0;
float lastCalculatedBPM = 0.0;
// ==== STRUCTS ====

// 1. The Data Packet
typedef struct {
  uint32_t intervalMS; 
  uint8_t  footId;     
} StepEvent;

// 2. The List Node
typedef struct Node {
  StepEvent step; // Holds the data
  Node* next;     // Points to the next node
};

// 3. The List Manager
typedef struct {
  int listSize;
  Node* first;    // Points to the newest step
} Head;

// ==== BPM & LOGIC VARIABLES ====
// Initialize empty list
Head stepHistory = {0, NULL}; 
StepEvent currentStep;
volatile bool messageRecv = false;
unsigned long lastStepRecvTime = 0;

// ==== LINKED LIST FUNCTIONS ====

// Function to add a new step to the FRONT of the list
void addNode(StepEvent newStep) {
  // 1. Allocate memory for new node
  Node* newNode = (Node*)malloc(sizeof(Node));
  
  // 2. Fill data
  newNode->step = newStep;
  
  // 3. Link it: New node points to current first
  newNode->next = stepHistory.first;
  
  // 4. Update Head: First now points to new node
  stepHistory.first = newNode;
  stepHistory.listSize++;
}

// Function to delete the OLDEST step (the last one)
void deleteLastNode() {
  if (stepHistory.first == NULL) return; // List empty

  Node* current = stepHistory.first;
  Node* previous = NULL;

  // Traverse to the end
  while (current->next != NULL) {
    previous = current;
    current = current->next;
  }

  // 'current' is now the last node. 
  // 'previous' is the second to last.
  
  if (previous != NULL) {
    previous->next = NULL; // Cut the link
  } else {
    stepHistory.first = NULL; // List had only 1 node
  }

  free(current); // Release memory back to ESP32
  stepHistory.listSize--;
}

// Function to calculate BPM from the list
float calculateAverageBPM() {
  if (stepHistory.listSize == 0) return 0.0;

  uint32_t totalInterval = 0;
  Node* current = stepHistory.first;

  // Loop through the list and sum intervals
  while (current != NULL) {
    totalInterval += current->step.intervalMS;
    current = current->next;
  }

  float avgInterval = (float)totalInterval / stepHistory.listSize;
  
  // Calculate BPM (60000ms / avg)
  if (avgInterval == 0) return 0.0;
  return 60000.0 / avgInterval;
}

// Function to clear the entire list
void clearList() {
  while(stepHistory.first != NULL) {
    Node* temp = stepHistory.first;
    stepHistory.first = stepHistory.first->next;
    free(temp);
  }
  stepHistory.listSize = 0;
}

// ==== ESP-NOW CALLBACK ====
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  if (len != sizeof(StepEvent)) return;
  memcpy(&currentStep, incomingData, sizeof(StepEvent));
  messageRecv = true;
}

// ==== SETUP ====
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
}


// ==== LOOP ====
void loop() {
  unsigned long now = millis();
  
  // Process all pending commands from PC
  while (Serial.available()) {
    String command = Serial.readStringUntil('\n');
    command.trim();
    //if the command is RESET(to make the esp listen for starting command):
    if (command == "RESET") {
      sessionStarting = true;
      Serial.println("ACK,RESET");
    //if the command is START(to start a new session):
    } else if (command == "START" && sessionStarting) {
      clearList();
      sessionStarting = false;
      sessionStarted = true;
      sessionStartTime = now;
      stepCounter = 0;
      lastCalculatedBPM = 0.0;
      Serial.println("ACK,START");
    } else if (command.startsWith("SET_WINDOW,")) {
      int commaIndex = command.indexOf(',');
      if (commaIndex != -1) {
        String valStr = command.substring(commaIndex + 1);
        int val = valStr.toInt();
        if (val > 0 && val <= 20) { 
          smoothingWindow = val;
          if (updateStride > smoothingWindow) updateStride = smoothingWindow;
          // Trim immediately if needed
          while (stepHistory.listSize > smoothingWindow) {
             deleteLastNode();
          }
          Serial.print("ACK,WINDOW,");
          Serial.println(smoothingWindow);
        }
      }
    } else if (command.startsWith("SET_STRIDE,")) {
      int commaIndex = command.indexOf(',');
      if (commaIndex != -1) {
        String valStr = command.substring(commaIndex + 1);
        int val = valStr.toInt();
        if (val > 0 && val <= smoothingWindow) {
          updateStride = val;
          Serial.print("ACK,STRIDE,");
          Serial.println(updateStride);
        }
      }
    }
  }
  //if a step is received:
  if (messageRecv) {
    messageRecv = false;
    lastStepRecvTime = now;
    uint32_t interval;
    int foot;
    float bpm;

    if (sessionStarted) {
      // First step after START: signal detection but ignore its timing for BPM
      sessionStarted = false;
      lastStepRecvTime = now;
      interval = 0;
      foot = currentStep.footId;
      bpm = 0.0;
    }
    else {
      //Unpack Data (Only what you have)
      interval = currentStep.intervalMS;
      foot = currentStep.footId;
      bpm = 0.0;

      // Add new step to Linked List
      addNode(currentStep);

      // Trim List: If too big, delete the oldest node
      if (stepHistory.listSize > smoothingWindow) {
        deleteLastNode();
      }

      // Calculate BPM using the List Function
      stepCounter++;
      if (stepCounter % updateStride == 0) {
        bpm = calculateAverageBPM();
        lastCalculatedBPM = bpm;
      } else {
        bpm = lastCalculatedBPM;
      }
    }
    
    //Send to PC
    // Format: Timestamp, Foot, InstantBPM, AverageBPM
    float instantBPM = 0.0;
    if (interval > 0) {
      instantBPM = 60000.0 / interval;
    }

    Serial.print(now);
    Serial.print(", ");
    Serial.print(foot);
    Serial.print(", ");
    Serial.print(instantBPM, 2);
    Serial.print(", ");
    Serial.println(bpm, 2);

    //LED Blink
    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }

  //Timeout check (disabled: keep previous BPM when footfalls pause briefly)
  /*
  if (stepHistory.listSize > 0 && (now - lastStepRecvTime > TIMEOUT_MS)) {
    clearList(); 
    Serial.println("0,0,0,0.0"); // Zeros matching your format
  }
  */
}