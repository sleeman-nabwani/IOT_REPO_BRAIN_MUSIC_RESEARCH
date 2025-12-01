//unit testing the transmission ability of the esp's
#include <WiFi.h>
#include <esp_wifi.h>
#include <esp_now.h>

volatile bool messageRecv = false;
char msgBuffer[250];

void onDataRecv(const uint8_t * mac, const uint8_t *incomingData, int len){
  messageRecv = true;
  Serial.println("message recived");

  //receving the message sent and printing it:
  memcpy(msgBuffer, incomingData, len);
  msgBuffer[len] = '\0';
  Serial.println(msgBuffer);
}

void setup() {
  Serial.begin(115200);
  //led settings:
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);

  WiFi.mode(WIFI_STA);
  
  //initiallizing esp_now:
  if(esp_now_init() !=ESP_OK){
    Serial.println("Error initializing esp_now");
    return;
  }

  //registering the function to work upon receving data
  esp_now_register_recv_cb(onDataRecv);

  Serial.println("ready to recive");
}

void loop() {
  if(messageRecv){
    messageRecv = false;

    //turning on the led:
    digitalWrite(LED_BUILTIN, HIGH);
    delay(100);
    digitalWrite(LED_BUILTIN, LOW);
  }
}