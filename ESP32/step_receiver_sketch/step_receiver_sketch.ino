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

// ---------------- STRUCTS ----------------

// Data Packet:
typedef struct __attribute__((packed)) {
  uint32_t intervalMS;
  uint8_t  footId;
} StepEvent;

// Identifying packet type enum:
enum MsgType : uint8_t { MSG_STEP = 1, MSG_BPM_DELTA = 2 };

// Unified packet (step + button delta):
typedef struct __attribute__((packed)) {
  uint8_t type;
  union {
    struct __attribute__((packed)) {
      uint32_t intervalMS;
      uint8_t footId;
    } step;
    struct __attribute__((packed)) { 
      int8_t delta;
    } bpm;
  };
} Packet;

// ---------------- CIRCULAR BUFFER CLASS ----------------
#define MAX_WINDOW_SIZE 20

class StepBuffer {
  private:
    StepEvent history[MAX_WINDOW_SIZE];
    int count = 0;
    int head = 0;

  public:
    void add(StepEvent s) {
      history[head] = s;
      head = (head + 1) % MAX_WINDOW_SIZE;
      if (count < MAX_WINDOW_SIZE) count++;
    }

    // Calculate BPM of the last 'n' steps
    float getAverageBPM(int n) {
      if (count == 0) return 0.0;
      
      // If we have less steps than requested, use all available steps
      int effectiveN = (n < count) ? n : count;
      if (effectiveN == 0) 
        return 0.0;
      
      uint32_t totalInterval = 0;
      
      // Start from the newest item and go backwards 'effectiveN' times
      // Newest item is at (head - 1)
      int currentIdx = head; 
      
      for (int i = 0; i < effectiveN; i++) {
        // Move back 1 index, handling wrap-around
        currentIdx = (currentIdx - 1 + MAX_WINDOW_SIZE) % MAX_WINDOW_SIZE;
        totalInterval += history[currentIdx].intervalMS;
      }
      
      float avg = (float)totalInterval / effectiveN;
      if (avg == 0) return 0.0;
      return 60000.0 / avg;
    }

    void clear() {
      count = 0;
      head = 0;
    }

    int size() {
      return count;
    }
    
    // Resize "virtual" window (cannot exceed MAX_WINDOW_SIZE)
    void trimToSize(int newSize) {
       if (newSize < count) 
         count = newSize;
    }
};

StepBuffer stepHistory;

/*
// --- LEGACY LINKED LIST  ---
// Linked list Node:
typedef struct Node {
  StepEvent step; // Holds the data
  Node* next;     // Points to the next node
};

// Linked list Manager
typedef struct {
  int listSize;
  Node* first;    // Points to the newest step
} Head;

// ---------------- BPM & LOGIC VARIABLES ----------------
// Initialize empty list:
Head stepHistoryLink = {0, NULL};
*/

// initialize stepEvent:
StepEvent currentStep;

// Step variables: 
volatile bool messageRecv = false;
volatile uint8_t lastMsgType = 0; // Added definition
unsigned long lastStepRecvTime = 0;

// Button variables:
volatile int8_t lastDelta = 0;

// ---------------- LINKED LIST FUNCTIONS ----------------

/*
// Function to add a new step to the FRONT of the list
void addNode(StepEvent newStep) {
  // 1. Allocate memory for new node
  Node* newNode = (Node*)malloc(sizeof(Node));
  if(!newNode)
    return;
  
  // 2. Fill data
  newNode->step = newStep;
  
  // 3. Link it: New node points to current first
  newNode->next = stepHistoryLink.first;
  
  // 4. Update Head: First now points to new node
  stepHistoryLink.first = newNode;
  stepHistoryLink.listSize++;
}

// Function to delete the OLDEST step (the last one)
void deleteLastNode() {
  if (stepHistoryLink.first == NULL) return; // List empty

  Node* current = stepHistoryLink.first;
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
    stepHistoryLink.first = NULL; // List had only 1 node
  }

  free(current); // Release memory back to ESP32
  stepHistoryLink.listSize--;
}

// Function to calculate BPM from the list
float calculateAverageBPM() {
  if (stepHistoryLink.listSize == 0) return 0.0;

  uint32_t totalInterval = 0;
  Node* current = stepHistoryLink.first;

  // Loop through the list and sum intervals
  while (current != NULL) {
    totalInterval += current->step.intervalMS;
    current = current->next;
  }

  float avgInterval = (float)totalInterval / stepHistoryLink.listSize;
  
  // Calculate BPM (60000ms / avg)
  if (avgInterval == 0) return 0.0;
  return 60000.0 / avgInterval;
}

// Function to clear the entire list
void clearList() {
  while(stepHistoryLink.first != NULL) {
    Node* temp = stepHistoryLink.first;
    stepHistoryLink.first = stepHistoryLink.first->next;
    free(temp);
  }
  stepHistoryLink.listSize = 0;
}
*/

// ---------------- ESP-NOW CALLBACK ----------------
void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len) {
  if (len == (int)sizeof(Packet)){
    Packet p;
    memcpy(&p, incomingData, sizeof(Packet));

    if(p.type == MSG_STEP){
      currentStep.intervalMS = p.step.intervalMS;
      currentStep.footId = p.step.footId;
      lastMsgType  = MSG_STEP;
      messageRecv = true;
    }
    else if(p.type == MSG_BPM_DELTA){
      lastDelta = p.bpm.delta;
      lastMsgType = MSG_BPM_DELTA;
      messageRecv = true;
    }
    return;
  }
  // Fallback for raw StepEvent (legacy support if needed, but risky if size matches Packet)
  if(len == (int)sizeof(StepEvent)){
    memcpy(&currentStep, incomingData, sizeof(StepEvent)); 
    lastMsgType = MSG_STEP;
    messageRecv = true;
  }
  
}

// ---------------- SETUP ----------------  
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


// ---------------- LOOP ---------------- 
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
      stepHistory.clear();
      // clearList(); // Legacy
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
          if (updateStride > smoothingWindow) 
            updateStride = smoothingWindow;
           // Trim immediately if needed
           stepHistory.trimToSize(smoothingWindow);
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
  // If a step is received:
  if (messageRecv) {
    
    noInterrupts();
    uint8_t type = lastMsgType;
    StepEvent stepCopy = currentStep;
    int8_t deltaCopy = lastDelta;
    messageRecv = false;
    interrupts();

    // BUTTON MESSAGE → forward to PC ONLY:
    if (type == MSG_BPM_DELTA) {
      Serial.print("BTN,");
      Serial.println((int)deltaCopy);
      return;
    }

    // STEP MESSAGE:
    lastStepRecvTime = now;
    uint32_t interval;
    int foot;
    float bpm;

    if (sessionStarted) {
      // First step after START: signal detection but ignore its timing for BPM
      sessionStarted = false;
      lastStepRecvTime = now;
      interval = 0;
      foot = stepCopy.footId;
      bpm = 0.0;
    }
    else {
      //Unpack Data (Only what you have)
      interval = stepCopy.intervalMS;
      foot = stepCopy.footId;
      bpm = 0.0;

      // Add new step to Circular Buffer
      stepHistory.add(stepCopy);

      /*
      // --- LEGACY ---
      addNode(stepCopy);
      if (linkedListHead.listSize > smoothingWindow) {
        deleteLastNode();
      }
      */

      // Calculate BPM using the Class Function
      stepCounter++;
      if (stepCounter % updateStride == 0) {
        bpm = stepHistory.getAverageBPM(smoothingWindow);
        // bpm = calculateAverageBPM(); // Legacy
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
}