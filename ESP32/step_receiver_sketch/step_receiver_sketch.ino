#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

// ==== SETTINGS ====
const int SMOOTHING_WINDOW = 3;  // Steps to average for BPM
const int TIMEOUT_MS = 10000;     // Reset BPM if no steps for 3 seconds

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

  if (messageRecv) {
    messageRecv = false;
    lastStepRecvTime = now;

    // 1. Unpack Data (Only what you have)
    uint32_t interval = currentStep.intervalMS;
    int foot = currentStep.footId;
    float bpm = 0.0;

    // 2. Filter & List Management
    if (interval > 2500 || interval < 100) {
      clearList(); // Reset if stopped
    } 
    else {
      // Add new step to Linked List
      addNode(currentStep);

      // Trim List: If too big, delete the oldest node
      if (stepHistory.listSize > SMOOTHING_WINDOW) {
        deleteLastNode();
      }

      // Calculate BPM using the List Function
      bpm = calculateAverageBPM();
    }

    // 3. Send to PC
    // Format: Timestamp, Foot, Interval, BPM
    Serial.print(now);
    Serial.print(", ");
    Serial.print(foot);
    Serial.print(", ");
    Serial.print(interval);
    Serial.print(", ");
    Serial.println(bpm, 2);

    // 4. LED Blink
    digitalWrite(LED_BUILTIN, HIGH);
    delay(50);
    digitalWrite(LED_BUILTIN, LOW);
  }

  // 5. Timeout Check
  // If we haven't heard a step in 3 seconds, clear list and send 0
  if (stepHistory.listSize > 0 && (now - lastStepRecvTime > TIMEOUT_MS)) {
    clearList(); 
    Serial.println("0,0,0,0.0"); // Zeros matching your format
  }
}
