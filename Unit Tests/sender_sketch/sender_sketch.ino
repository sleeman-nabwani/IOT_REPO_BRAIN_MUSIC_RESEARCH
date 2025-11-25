//unit testing the sender part of the esp_now protocol
#include<WiFi.h>
#include<esp_wifi.h>
#include<esp_now.h>

//setting up the receiver MAC address

uint8_t receiverMac[] = {0xfc, 0xb4, 0x67, 0xf4, 0x58, 0xa8};

void onDataSent(const uint8_t *mac_addr, esp_now_send_status_t status) {
  Serial.print("Last send status: ");
  Serial.println(status == ESP_NOW_SEND_SUCCESS ? "Success" : "Fail");
}

void setup() {
  Serial.begin(115200);
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

void loop() {
  const char msg[] = "ding-dong";
  
  esp_err_t result = esp_now_send(receiverMac, (uint8_t*)msg, sizeof(msg));
  if(result == ESP_OK){
    Serial.println("sent");
  }
  else{
    Serial.println("error sending the message");
    Serial.println(result);
  }

  delay(1000);
}
