#include <ESP32Servo.h>

Servo myservo;

void setup() {
  // put your setup code here, to run once:
  Serial.begin(9600);  // 初始化串口通信速率
  myservo.attach(1);
}

void loop() {
  // put your main code here, to run repeatedly:
  if (Serial.available()) {
    int angle = Serial.parseInt();
    // 丢弃后续的换行/回车，避免下一次parseInt等待超时返回0
    while (Serial.peek() == '\n' || Serial.peek() == '\r') {
      Serial.read();
    }
    if (angle >= 0 && angle <= 180) {
      myservo.write(angle);
    }
  }
}
