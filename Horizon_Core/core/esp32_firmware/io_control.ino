
/*
 * ESP32 IO控制固件
 * 用于与上位机进行串口通信，控制数字输入输出
 * 
 * 硬件连接：
 * DI0-DI7: GPIO 23, 22, 17, 16, 21, 19, 18, 5 (前5个启用内部上拉)
 * DO0-DO7: GPIO 2, 4, 25, 26, 27, 32, 33, 13
 * 
 * 通信协议：115200 8N1
 */

 #include <Arduino.h>
 #include <ArduinoJson.h>
 
 // 版本信息
 #define FIRMWARE_VERSION "v1.0.0"
 
// IO引脚定义
const int DI_PINS[8] = {23, 22, 17, 16, 21, 19, 18, 5};  // 数字输入引脚
const int DO_PINS[8] = {2, 4, 25, 26, 27, 32, 33, 13};   // 数字输出引脚（使用可靠的数字IO引脚）
 
 // IO状态
 bool di_states[8] = {false};
 bool do_states[8] = {false};
 // 针对特定GPIO配置上拉电阻：GPIO23、22、17、16、21启用上拉，其他禁用
bool di_pullup_enabled[8] = {true, true, true, true, true, false, false, false};  // DI0-DI4(GPIO23,22,17,16,21)=true, 其他=false
 
 // 中断相关
 volatile bool di_interrupt_flags[8] = {false};
 int di_interrupt_modes[8] = {0};  // 0:NONE, 1:RISING, 2:FALLING, 3:BOTH
 
// DI中断相关（基于固定引脚）
volatile bool di_interrupt_flags_ext[8] = {false};  // 扩展DI中断标志
int di_interrupt_modes_ext[8] = {0};  // 0:NONE, 1:RISING, 2:FALLING, 3:BOTH, 4:LOW_LEVEL
 
// 脉冲输出相关（保留传统DO脉冲功能）
unsigned long pulse_start_time[8] = {0};
unsigned long pulse_duration[8] = {0};
bool pulse_active[8] = {false};
 
 // 串口缓冲区
 String command_buffer = "";
 bool command_ready = false;
 
 // 函数声明
 void setup_io_pins();
 void handle_command(String command);
 void send_response(String response);
 void update_di_states();
 void update_pulse_outputs();
 void setup_interrupts();
 void IRAM_ATTR di_interrupt_handler_0();
 void IRAM_ATTR di_interrupt_handler_1();
 void IRAM_ATTR di_interrupt_handler_2();
 void IRAM_ATTR di_interrupt_handler_3();
 void IRAM_ATTR di_interrupt_handler_4();
 void IRAM_ATTR di_interrupt_handler_5();
 void IRAM_ATTR di_interrupt_handler_6();
 void IRAM_ATTR di_interrupt_handler_7();
 
 void setup() {
   // 初始化串口
   Serial.begin(115200);
   delay(100);  // 等待串口稳定，移除可能导致卡死的while循环
   
   // 初始化IO引脚
   setup_io_pins();
   
   // 设置中断
   setup_interrupts();
   
   // 发送启动信息
   Serial.println("ESP32 IO Controller Ready");
   Serial.println("Firmware Version: " + String(FIRMWARE_VERSION));
 }
 
void loop() {
  // 处理串口命令接收
  while (Serial.available()) {
    char c = Serial.read();
    // 检查是否为命令结束符（换行符）
    if (c == '\n') {
      command_ready = true;  // 标记命令接收完成
    } else if (c != '\r') {  // 忽略回车符，只处理其他字符
      command_buffer += c;   // 将字符添加到命令缓冲区
    }
  }
  
  // 如果命令接收完成，处理命令
  if (command_ready) {
    handle_command(command_buffer);  // 处理接收到的命令
    command_buffer = "";             // 清空命令缓冲区
    command_ready = false;           // 重置命令接收标志
  }
  
  // 更新IO状态和处理各种定时任务
  update_di_states();      // 更新所有DI引脚状态
  update_pulse_outputs();  // 处理DO脉冲输出定时
  update_di_interrupts();  // 检查DI扩展中断条件
  
  delay(1);  // 短暂延时，避免CPU占用过高
}
 
 
void setup_io_pins() {
  // 配置数字输入引脚
  for (int i = 0; i < 8; i++) {
    // 根据上拉电阻配置设置DI引脚模式
    if (di_pullup_enabled[i]) {
      pinMode(DI_PINS[i], INPUT_PULLUP);  // 启用内部上拉电阻
    } else {
      pinMode(DI_PINS[i], INPUT);         // 不使用内部上拉电阻
    }
  }
  
  // 配置数字输出引脚
  for (int i = 0; i < 8; i++) {
    pinMode(DO_PINS[i], OUTPUT);    // 设置为输出模式
    digitalWrite(DO_PINS[i], LOW);  // 初始化为低电平
    do_states[i] = false;           // 更新状态记录
  }
}
 
 void setup_interrupts() {
   // 中断处理函数数组
   void (*interrupt_handlers[8])() = {
     di_interrupt_handler_0, di_interrupt_handler_1,
     di_interrupt_handler_2, di_interrupt_handler_3,
     di_interrupt_handler_4, di_interrupt_handler_5,
     di_interrupt_handler_6, di_interrupt_handler_7
   };
   
   // 为每个DI引脚设置中断（默认不启用）
   for (int i = 0; i < 8; i++) {
     di_interrupt_modes[i] = 0;  // NONE
   }
 }
 
void handle_command(String command) {
  command.trim();
  
  // 【连接测试命令】处理PING命令，用于测试ESP32是否正常响应
  if (command == "PING") {
    send_response("PONG");
  }
  // 【版本查询命令】返回固件版本信息
  else if (command == "VERSION") {
    send_response("VER:" + String(FIRMWARE_VERSION));
  }
  // 【状态查询命令】返回ESP32运行状态信息（运行时间、内存、芯片型号）
  else if (command == "STATUS") {
    DynamicJsonDocument doc(200);
    doc["uptime"] = millis();
    doc["free_heap"] = ESP.getFreeHeap();
    doc["chip_id"] = ESP.getChipModel();
    
    String status_json;
    serializeJson(doc, status_json);
    send_response("STATUS:" + status_json);
  }
  // 【读取所有DI状态命令】返回DI0-DI7的状态，格式：DI:01010000
  else if (command == "READ_DI") {
    String di_data = "";
    for (int i = 0; i < 8; i++) {
      di_data += di_states[i] ? "1" : "0";
    }
    send_response("DI:" + di_data);
  }
  // 【读取单个DI状态命令】格式：READ_DI:3，返回指定DI引脚的状态
  else if (command.startsWith("READ_DI:")) {
    int pin = command.substring(8).toInt();
    // 检查DI引脚号是否有效（0-7）
    if (pin >= 0 && pin < 8) {
      send_response("DI" + String(pin) + ":" + (di_states[pin] ? "1" : "0"));
    } else {
      // DI引脚号无效，返回错误信息
      send_response("ERROR:Invalid DI pin");
    }
  }
  // 【设置单个DO状态命令】格式：SET_DO:3,1，设置指定DO引脚的状态
  else if (command.startsWith("SET_DO:")) {
    int comma_pos = command.indexOf(',');
    // 检查命令格式是否正确（必须包含逗号分隔符）
    if (comma_pos > 0) {
      int pin = command.substring(7, comma_pos).toInt();
      int state = command.substring(comma_pos + 1).toInt();
      
      // 检查DO引脚号是否有效（0-7）
      if (pin >= 0 && pin < 8) {
        digitalWrite(DO_PINS[pin], state ? HIGH : LOW);
        do_states[pin] = state;
        send_response("OK");
      } else {
        // DO引脚号无效，返回错误信息
        send_response("ERROR:Invalid DO pin");
      }
    } else {
      // 命令格式错误（缺少逗号或格式不正确）
      send_response("ERROR:Invalid SET_DO format");
    }
  }
  // 【设置所有DO状态命令】格式：SET_DO_ALL:01010000，一次性设置所有DO引脚状态
  else if (command.startsWith("SET_DO_ALL:")) {
    String states_str = command.substring(11);
    // 检查状态字符串长度是否为8（对应8个DO引脚）
    if (states_str.length() == 8) {
      for (int i = 0; i < 8; i++) {
        bool state = states_str.charAt(i) == '1';
        digitalWrite(DO_PINS[i], state ? HIGH : LOW);
        do_states[i] = state;
      }
      send_response("OK");
    } else {
      // 状态字符串长度不正确（不是8位）
      send_response("ERROR:Invalid DO states format");
    }
  }
  // 【读取所有DO状态命令】返回DO0-DO7的状态，格式：DO:01010000
  else if (command == "READ_DO") {
    String do_data = "";
    for (int i = 0; i < 8; i++) {
      do_data += do_states[i] ? "1" : "0";
    }
    send_response("DO:" + do_data);
  }
  // 【DO脉冲输出命令】格式：PULSE_DO:3,100，让指定DO引脚输出指定时长的脉冲
  else if (command.startsWith("PULSE_DO:")) {
    int comma_pos = command.indexOf(',');
    // 检查命令格式是否正确（必须包含逗号分隔符）
    if (comma_pos > 0) {
      int pin = command.substring(9, comma_pos).toInt();
      int duration_ms = command.substring(comma_pos + 1).toInt();
      
      // 检查DO引脚号和脉冲时长是否有效
      if (pin >= 0 && pin < 8 && duration_ms > 0) {
        // 启动脉冲输出
        digitalWrite(DO_PINS[pin], HIGH);
        do_states[pin] = true;
        pulse_active[pin] = true;
        pulse_start_time[pin] = millis();
        pulse_duration[pin] = duration_ms;
        
        send_response("OK");
      } else {
        // DO引脚号无效或脉冲时长无效
        send_response("ERROR:Invalid PULSE_DO parameters");
      }
    } else {
      // 命令格式错误（缺少逗号或格式不正确）
      send_response("ERROR:Invalid PULSE_DO format");
    }
  }
  // 【复位所有DO命令】将所有DO引脚设置为低电平并停止所有脉冲输出
  else if (command == "RESET_DO") {
    for (int i = 0; i < 8; i++) {
      digitalWrite(DO_PINS[i], LOW);
      do_states[i] = false;
      pulse_active[i] = false;
    }
    send_response("OK");
  }
  // 【配置DI上拉电阻命令】格式：CONFIG_PULLUP:3,1，配置指定DI引脚的上拉电阻
  else if (command.startsWith("CONFIG_PULLUP:")) {
    int comma_pos = command.indexOf(',');
    // 检查命令格式是否正确（必须包含逗号分隔符）
    if (comma_pos > 0) {
      int pin = command.substring(14, comma_pos).toInt();
      int enable = command.substring(comma_pos + 1).toInt();
      
      // 检查DI引脚号是否有效（0-7）
      if (pin >= 0 && pin < 8) {
        di_pullup_enabled[pin] = enable;
        // 根据enable参数设置引脚模式
        if (enable) {
          pinMode(DI_PINS[pin], INPUT_PULLUP);  // 启用上拉电阻
        } else {
          pinMode(DI_PINS[pin], INPUT);         // 禁用上拉电阻
        }
        send_response("OK");
      } else {
        // DI引脚号无效，返回错误信息
        send_response("ERROR:Invalid DI pin");
      }
    } else {
      // 命令格式错误（缺少逗号或格式不正确）
      send_response("ERROR:Invalid CONFIG_PULLUP format");
    }
  }
  // 【配置DI硬件中断命令】格式：CONFIG_INT:3,RISING，配置指定DI引脚的硬件中断模式
  else if (command.startsWith("CONFIG_INT:")) {
    int comma_pos = command.indexOf(',');
    // 检查命令格式是否正确（必须包含逗号分隔符）
    if (comma_pos > 0) {
      int pin = command.substring(11, comma_pos).toInt();
      String mode = command.substring(comma_pos + 1);
      
      // 检查DI引脚号是否有效（0-7）
      if (pin >= 0 && pin < 8) {
        // 先分离现有中断
        detachInterrupt(digitalPinToInterrupt(DI_PINS[pin]));
        
        // 配置新的中断模式
        void (*interrupt_handlers[8])() = {
          di_interrupt_handler_0, di_interrupt_handler_1,
          di_interrupt_handler_2, di_interrupt_handler_3,
          di_interrupt_handler_4, di_interrupt_handler_5,
          di_interrupt_handler_6, di_interrupt_handler_7
        };
        
        // 根据中断模式字符串配置相应的硬件中断
        if (mode == "RISING") {
          di_interrupt_modes[pin] = 1;  // 上升沿中断
          attachInterrupt(digitalPinToInterrupt(DI_PINS[pin]), interrupt_handlers[pin], RISING);
        } else if (mode == "FALLING") {
          di_interrupt_modes[pin] = 2;  // 下降沿中断
          attachInterrupt(digitalPinToInterrupt(DI_PINS[pin]), interrupt_handlers[pin], FALLING);
        } else if (mode == "BOTH") {
          di_interrupt_modes[pin] = 3;  // 双边沿中断
          attachInterrupt(digitalPinToInterrupt(DI_PINS[pin]), interrupt_handlers[pin], CHANGE);
        } else if (mode == "NONE") {
          di_interrupt_modes[pin] = 0;  // 禁用中断
          // 中断已分离
        } else {
          // 中断模式无效，返回错误信息
          send_response("ERROR:Invalid interrupt mode");
          return;
        }
        
        send_response("OK");
      } else {
        // DI引脚号无效，返回错误信息
        send_response("ERROR:Invalid DI pin");
      }
    } else {
      // 命令格式错误（缺少逗号或格式不正确）
      send_response("ERROR:Invalid CONFIG_INT format");
    }
  }
  // 【读取DI硬件中断状态命令】返回触发了硬件中断的DI引脚列表
  else if (command == "READ_INT") {
    String int_pins = "";
    bool has_interrupt = false;
    
    // 遍历所有DI引脚，检查中断标志
    for (int i = 0; i < 8; i++) {
      if (di_interrupt_flags[i]) {
        // 如果已有中断引脚，添加逗号分隔符
        if (has_interrupt) {
          int_pins += ",";
        }
        int_pins += String(i);
        has_interrupt = true;
      }
    }
    
    // 根据是否有中断返回相应结果
    if (has_interrupt) {
      send_response("INT:" + int_pins);  // 返回触发中断的引脚列表
    } else {
      send_response("INT:NONE");         // 没有中断触发
    }
  }
  // 【清除DI硬件中断标志命令】格式：CLEAR_INT:3 或 CLEAR_INT:ALL
  else if (command.startsWith("CLEAR_INT:")) {
    String pin_str = command.substring(10);
    
    // 检查是否清除所有中断标志
    if (pin_str == "ALL") {
      for (int i = 0; i < 8; i++) {
        di_interrupt_flags[i] = false;
      }
      send_response("OK");
    } else {
      // 清除指定引脚的中断标志
      int pin = pin_str.toInt();
      // 检查DI引脚号是否有效（0-7）
      if (pin >= 0 && pin < 8) {
        di_interrupt_flags[pin] = false;
        send_response("OK");
      } else {
        // DI引脚号无效，返回错误信息
        send_response("ERROR:Invalid DI pin");
      }
    }
  }
  // 【配置DI扩展中断命令】格式：CONFIG_DI_INT:3,RISING，配置DI引脚的软件轮询中断模式
  else if (command.startsWith("CONFIG_DI_INT:")) {
    int comma_pos = command.indexOf(',');
    // 检查命令格式是否正确（必须包含逗号分隔符）
    if (comma_pos > 0) {
      int di_pin = command.substring(14, comma_pos).toInt();
      String mode = command.substring(comma_pos + 1);
      
      // 检查DI引脚号是否有效（0-7）
      if (di_pin >= 0 && di_pin < 8) {
        // 根据中断模式字符串设置扩展中断模式
        if (mode == "RISING") {
          di_interrupt_modes_ext[di_pin] = 1;      // 上升沿触发
        } else if (mode == "FALLING") {
          di_interrupt_modes_ext[di_pin] = 2;      // 下降沿触发
        } else if (mode == "BOTH") {
          di_interrupt_modes_ext[di_pin] = 3;      // 双边沿触发
        } else if (mode == "LOW_LEVEL") {
          di_interrupt_modes_ext[di_pin] = 4;      // 低电平触发
        } else if (mode == "NONE") {
          di_interrupt_modes_ext[di_pin] = 0;      // 禁用扩展中断
        } else {
          // 扩展中断模式无效，返回错误信息
          send_response("ERROR:Invalid DI interrupt mode");
          return;
        }
        send_response("OK");
      } else {
        // DI引脚号无效，返回错误信息
        send_response("ERROR:Invalid DI pin");
      }
    } else {
      // 命令格式错误（缺少逗号或格式不正确）
      send_response("ERROR:Invalid CONFIG_DI_INT format");
    }
  }
  // 【读取DI扩展中断状态命令】返回触发了扩展中断的DI引脚列表
  else if (command == "READ_DI_INT") {
    String int_pins = "";
    bool has_interrupt = false;
    
    // 遍历所有DI引脚，检查扩展中断标志
    for (int i = 0; i < 8; i++) {
      if (di_interrupt_flags_ext[i]) {
        // 如果已有中断引脚，添加逗号分隔符
        if (has_interrupt) {
          int_pins += ",";
        }
        int_pins += String(i);
        has_interrupt = true;
      }
    }
    
    // 根据是否有扩展中断返回相应结果
    if (has_interrupt) {
      send_response("DI_INT:" + int_pins);  // 返回触发扩展中断的引脚列表
    } else {
      send_response("DI_INT:NONE");         // 没有扩展中断触发
    }
  }
  // 【清除DI扩展中断标志命令】格式：CLEAR_DI_INT:3 或 CLEAR_DI_INT:ALL
  else if (command.startsWith("CLEAR_DI_INT:")) {
    String pin_str = command.substring(13);
    
    // 检查是否清除所有扩展中断标志
    if (pin_str == "ALL") {
      for (int i = 0; i < 8; i++) {
        di_interrupt_flags_ext[i] = false;
      }
      send_response("OK");
    } else {
      // 清除指定引脚的扩展中断标志
      int di_pin = pin_str.toInt();
      // 检查DI引脚号是否有效（0-7）
      if (di_pin >= 0 && di_pin < 8) {
        di_interrupt_flags_ext[di_pin] = false;
        send_response("OK");
      } else {
        // DI引脚号无效，返回错误信息
        send_response("ERROR:Invalid DI pin");
      }
    }
  }
  // 【未知命令处理】如果命令不匹配任何已知命令，返回UNKNOWN
  else {
    send_response("UNKNOWN");
  }
 }
 
 void send_response(String response) {
   Serial.println(response);
 }
 
 void update_di_states() {
   for (int i = 0; i < 8; i++) {
     di_states[i] = digitalRead(DI_PINS[i]) == HIGH;
   }
 }
 
void update_pulse_outputs() {
  unsigned long current_time = millis();
  
  // 检查所有DO引脚的脉冲输出状态
  for (int i = 0; i < 8; i++) {
    // 如果该引脚正在进行脉冲输出
    if (pulse_active[i]) {
      // 检查脉冲持续时间是否已到
      if (current_time - pulse_start_time[i] >= pulse_duration[i]) {
        // 脉冲时间到，结束脉冲输出
        digitalWrite(DO_PINS[i], LOW);  // 设置为低电平
        do_states[i] = false;           // 更新状态记录
        pulse_active[i] = false;        // 标记脉冲结束
      }
    }
  }
}

void update_di_interrupts() {
  // 轮询检查DI扩展中断条件（软件实现的中断检测）
  static bool previous_di_states[8] = {false};
  
  // 遍历所有DI引脚
  for (int i = 0; i < 8; i++) {
    // 如果该引脚配置了扩展中断模式
    if (di_interrupt_modes_ext[i] > 0) {
      bool current_state = di_states[i];
      bool previous_state = previous_di_states[i];
      
      // 检查中断触发条件
      bool trigger = false;
      switch (di_interrupt_modes_ext[i]) {
        case 1: // 上升沿触发：从低电平变为高电平
          trigger = current_state && !previous_state;
          break;
        case 2: // 下降沿触发：从高电平变为低电平
          trigger = !current_state && previous_state;
          break;
        case 3: // 双边沿触发：电平发生任何变化
          trigger = current_state != previous_state;
          break;
        case 4: // 低电平触发：当前为低电平
          trigger = !current_state;
          break;
      }
      
      // 如果满足触发条件，设置中断标志
      if (trigger) {
        di_interrupt_flags_ext[i] = true;
      }
      
      // 更新前一次状态记录
      previous_di_states[i] = current_state;
    }
  }
}
 
 
 // 中断处理函数
 void IRAM_ATTR di_interrupt_handler_0() { di_interrupt_flags[0] = true; }
 void IRAM_ATTR di_interrupt_handler_1() { di_interrupt_flags[1] = true; }
 void IRAM_ATTR di_interrupt_handler_2() { di_interrupt_flags[2] = true; }
 void IRAM_ATTR di_interrupt_handler_3() { di_interrupt_flags[3] = true; }
 void IRAM_ATTR di_interrupt_handler_4() { di_interrupt_flags[4] = true; }
 void IRAM_ATTR di_interrupt_handler_5() { di_interrupt_flags[5] = true; }
 void IRAM_ATTR di_interrupt_handler_6() { di_interrupt_flags[6] = true; }
 void IRAM_ATTR di_interrupt_handler_7() { di_interrupt_flags[7] = true; }
 