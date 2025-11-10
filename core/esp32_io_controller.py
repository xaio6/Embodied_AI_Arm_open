
# -*- coding: utf-8 -*-
"""
ESP32 IO控制器
负责与ESP32进行串口通信，控制数字输入输出
"""

import serial
import time
import json
import threading
from typing import List, Dict, Optional, Tuple
import logging


class ESP32IOController:
    """ESP32 IO控制器类"""
    
    def __init__(self, port: str = "COM3", baudrate: int = 115200, timeout: float = 1.0):
        """
        初始化ESP32控制器
        
        Args:
            port: 串口号
            baudrate: 波特率
            timeout: 超时时间
        """
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self.serial_conn = None
        self.is_connected = False
        
        # IO状态
        self.di_states = [False] * 8  # 数字输入状态
        self.do_states = [False] * 8  # 数字输出状态
        
        # 通信锁
        self.comm_lock = threading.Lock()
        
        # 日志
        self.logger = logging.getLogger(__name__)
        
    def connect(self) -> bool:
        """
        连接ESP32
        
        Returns:
            bool: 连接是否成功
        """
        try:
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=self.timeout,
                bytesize=serial.EIGHTBITS,
                parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE
            )
            
            # 等待ESP32启动和串口稳定
            time.sleep(1.0)
            
            # 清空缓冲区
            self.serial_conn.flushInput()
            self.serial_conn.flushOutput()
            
            # 直接发送PING命令进行连接测试（绕过send_command的is_connected检查）
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    # 发送PING命令
                    self.serial_conn.write(b"PING\n")
                    self.serial_conn.flush()
                    
                    # 读取响应
                    response = self.serial_conn.readline().decode('utf-8').strip()
                    
                    if response == "PONG":
                        self.is_connected = True
                        self.logger.info(f"ESP32连接成功: {self.port} @ {self.baudrate}")
                        return True
                    elif response:
                        self.logger.warning(f"ESP32响应异常: {response}, 重试 {attempt + 1}/{max_retries}")
                    else:
                        self.logger.warning(f"ESP32无响应, 重试 {attempt + 1}/{max_retries}")
                    
                    # 等待后重试
                    time.sleep(0.5)
                    
                except Exception as e:
                    self.logger.warning(f"连接测试异常: {e}, 重试 {attempt + 1}/{max_retries}")
                    time.sleep(0.5)
            
            # 所有重试都失败
            self.logger.error("ESP32连接失败: 未收到正确的PONG响应")
            self.serial_conn.close()
            self.serial_conn = None
            return False
                
        except Exception as e:
            self.logger.error(f"ESP32连接失败: {e}")
            if self.serial_conn:
                self.serial_conn.close()
            self.serial_conn = None
            return False
            
    def disconnect(self):
        """断开ESP32连接"""
        try:
            self.is_connected = False
            if self.serial_conn and self.serial_conn.is_open:
                self.serial_conn.close()
            self.serial_conn = None
            self.logger.info("ESP32连接已断开")
        except Exception as e:
            self.logger.error(f"断开ESP32连接时出错: {e}")
            
    def send_command(self, command: str, data: str = "") -> Optional[str]:
        """
        发送命令到ESP32
        
        Args:
            command: 命令字符串
            data: 数据字符串
            
        Returns:
            str: ESP32的响应，如果失败返回None
        """
        if not self.serial_conn or not self.serial_conn.is_open:
            return None
            
        try:
            with self.comm_lock:
                # 构造命令包
                if data:
                    cmd_packet = f"{command}:{data}\n"
                else:
                    cmd_packet = f"{command}\n"
                
                # 发送命令
                self.serial_conn.write(cmd_packet.encode('utf-8'))
                self.serial_conn.flush()
                
                # 读取响应
                response = self.serial_conn.readline().decode('utf-8').strip()
                return response if response else None
                
        except Exception as e:
            self.logger.error(f"发送命令失败: {e}")
            return None
            
    def read_di_states(self) -> Optional[List[bool]]:
        """
        读取所有数字输入状态
        
        Returns:
            List[bool]: DI状态列表，失败返回None
        """
        response = self.send_command("READ_DI")
        if response and response.startswith("DI:"):
            try:
                # 解析响应格式: "DI:01010000"
                di_data = response[3:]
                if len(di_data) == 8:
                    states = [bit == '1' for bit in di_data]
                    self.di_states = states
                    return states
            except Exception as e:
                self.logger.error(f"解析DI状态失败: {e}")
        return None
        
    def read_di_state(self, pin: int) -> Optional[bool]:
        """
        读取单个数字输入状态
        
        Args:
            pin: DI引脚号 (0-7)
            
        Returns:
            bool: DI状态，失败返回None
        """
        if not (0 <= pin <= 7):
            return None
            
        response = self.send_command("READ_DI", str(pin))
        if response and response.startswith(f"DI{pin}:"):
            try:
                state = response.split(':')[1] == '1'
                self.di_states[pin] = state
                return state
            except Exception as e:
                self.logger.error(f"解析DI{pin}状态失败: {e}")
        return None
        
    def set_do_state(self, pin: int, state: bool) -> bool:
        """
        设置数字输出状态
        
        Args:
            pin: DO引脚号 (0-7)
            state: 输出状态
            
        Returns:
            bool: 设置是否成功
        """
        if not (0 <= pin <= 7):
            return False
            
        state_str = "1" if state else "0"
        response = self.send_command("SET_DO", f"{pin},{state_str}")
        
        if response and response == "OK":
            self.do_states[pin] = state
            return True
        return False
        
    def set_do_states(self, states: List[bool]) -> bool:
        """
        设置所有数字输出状态
        
        Args:
            states: DO状态列表 (8个元素)
            
        Returns:
            bool: 设置是否成功
        """
        if len(states) != 8:
            return False
            
        states_str = ''.join('1' if state else '0' for state in states)
        response = self.send_command("SET_DO_ALL", states_str)
        
        if response and response == "OK":
            self.do_states = states.copy()
            return True
        return False
        
    def read_do_states(self) -> Optional[List[bool]]:
        """
        读取所有数字输出状态
        
        Returns:
            List[bool]: DO状态列表，失败返回None
        """
        response = self.send_command("READ_DO")
        if response and response.startswith("DO:"):
            try:
                # 解析响应格式: "DO:01010000"
                do_data = response[3:]
                if len(do_data) == 8:
                    states = [bit == '1' for bit in do_data]
                    self.do_states = states
                    return states
            except Exception as e:
                self.logger.error(f"解析DO状态失败: {e}")
        return None
        
    def pulse_do(self, pin: int, duration: float = 0.1) -> bool:
        """
        DO引脚脉冲输出
        
        Args:
            pin: DO引脚号 (0-7)
            duration: 脉冲持续时间（秒）
            
        Returns:
            bool: 操作是否成功
        """
        if not (0 <= pin <= 7):
            return False
            
        # 发送脉冲命令
        duration_ms = int(duration * 1000)
        response = self.send_command("PULSE_DO", f"{pin},{duration_ms}")
        
        return response == "OK"
        
    def reset_all_do(self) -> bool:
        """
        复位所有数字输出为低电平
        
        Returns:
            bool: 操作是否成功
        """
        response = self.send_command("RESET_DO")
        if response == "OK":
            self.do_states = [False] * 8
            return True
        return False
        
    def get_version(self) -> Optional[str]:
        """
        获取ESP32固件版本
        
        Returns:
            str: 版本信息，失败返回None
        """
        response = self.send_command("VERSION")
        if response and response.startswith("VER:"):
            return response[4:]
        return None
        
    def get_status(self) -> Optional[Dict]:
        """
        获取ESP32状态信息
        
        Returns:
            dict: 状态信息，失败返回None
        """
        response = self.send_command("STATUS")
        if response and response.startswith("STATUS:"):
            try:
                status_json = response[7:]
                return json.loads(status_json)
            except Exception as e:
                self.logger.error(f"解析状态信息失败: {e}")
        return None
        
    def configure_di_pullup(self, pin: int, enable: bool) -> bool:
        """
        配置DI引脚上拉电阻
        
        Args:
            pin: DI引脚号 (0-7)
            enable: 是否启用上拉
            
        Returns:
            bool: 配置是否成功
        """
        if not (0 <= pin <= 7):
            return False
            
        enable_str = "1" if enable else "0"
        response = self.send_command("CONFIG_PULLUP", f"{pin},{enable_str}")
        
        return response == "OK"
        
    def configure_di_interrupt(self, pin: int, mode: str) -> bool:
        """
        配置DI引脚中断模式
        
        Args:
            pin: DI引脚号 (0-7)
            mode: 中断模式 ("RISING", "FALLING", "BOTH", "NONE")
            
        Returns:
            bool: 配置是否成功
        """
        if not (0 <= pin <= 7):
            return False
            
        if mode not in ["RISING", "FALLING", "BOTH", "NONE"]:
            return False
            
        response = self.send_command("CONFIG_INT", f"{pin},{mode}")
        return response == "OK"
        
    def read_interrupt_status(self) -> Optional[List[int]]:
        """
        读取中断状态
        
        Returns:
            List[int]: 触发中断的引脚列表，失败返回None
        """
        response = self.send_command("READ_INT")
        if response and response.startswith("INT:"):
            try:
                int_data = response[4:]
                if int_data == "NONE":
                    return []
                else:
                    # 解析格式: "INT:0,2,5" 表示引脚0,2,5触发了中断
                    pins = [int(pin) for pin in int_data.split(',') if pin.isdigit()]
                    return pins
            except Exception as e:
                self.logger.error(f"解析中断状态失败: {e}")
        return None
        
    def clear_interrupt(self, pin: int = -1) -> bool:
        """
        清除中断状态
        
        Args:
            pin: 要清除的引脚号，-1表示清除所有
            
        Returns:
            bool: 操作是否成功
        """
        if pin == -1:
            response = self.send_command("CLEAR_INT", "ALL")
        elif 0 <= pin <= 7:
            response = self.send_command("CLEAR_INT", str(pin))
        else:
            return False
            
        return response == "OK"
        
    def configure_di_interrupt(self, di_pin: int, mode: str) -> bool:
        """
        配置DI引脚扩展中断模式
        
        Args:
            di_pin: DI引脚号 (0-7)
            mode: 中断模式 ("RISING", "FALLING", "BOTH", "LOW_LEVEL", "NONE")
            
        Returns:
            bool: 配置是否成功
        """
        if not (0 <= di_pin <= 7):
            return False
            
        if mode not in ["RISING", "FALLING", "BOTH", "LOW_LEVEL", "NONE"]:
            return False
            
        response = self.send_command("CONFIG_DI_INT", f"{di_pin},{mode}")
        return response == "OK"
        
    def read_di_interrupt_status(self) -> Optional[List[int]]:
        """
        读取DI扩展中断状态
        
        Returns:
            List[int]: 触发中断的DI引脚列表，失败返回None
        """
        response = self.send_command("READ_DI_INT")
        if response and response.startswith("DI_INT:"):
            try:
                int_data = response[7:]
                if int_data == "NONE":
                    return []
                else:
                    # 解析格式: "DI_INT:0,2,5" 表示DI0,2,5触发了中断
                    pins = [int(pin) for pin in int_data.split(',') if pin.isdigit()]
                    return pins
            except Exception as e:
                self.logger.error(f"解析DI中断状态失败: {e}")
        return None
        
    def clear_di_interrupt(self, di_pin: int = -1) -> bool:
        """
        清除DI扩展中断状态
        
        Args:
            di_pin: 要清除的DI引脚号，-1表示清除所有
            
        Returns:
            bool: 操作是否成功
        """
        if di_pin == -1:
            response = self.send_command("CLEAR_DI_INT", "ALL")
        elif 0 <= di_pin <= 7:
            response = self.send_command("CLEAR_DI_INT", str(di_pin))
        else:
            return False
            
        return response == "OK"
        
    def is_alive(self) -> bool:
        """
        检查ESP32是否响应
        
        Returns:
            bool: ESP32是否正常响应
        """
        if not self.is_connected:
            return False
            
        response = self.send_command("PING")
        return response == "PONG"
        
    def close(self):
        """关闭连接"""
        self.disconnect()
        
    def __enter__(self):
        """上下文管理器入口"""
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()


# ESP32固件通信协议说明
"""
ESP32固件需要实现以下命令协议：

1. 基础命令：
   - PING -> PONG (连接测试)
   - VERSION -> VER:v1.0.0 (版本查询)
   - STATUS -> STATUS:{"uptime":12345,"free_heap":50000} (状态查询)

2. 数字输入命令：
   - READ_DI -> DI:01010000 (读取所有DI状态)
   - READ_DI:3 -> DI3:1 (读取DI3状态)

3. 数字输出命令：
   - SET_DO:3,1 -> OK (设置DO3为高电平)
   - SET_DO_ALL:01010000 -> OK (设置所有DO状态)
   - READ_DO -> DO:01010000 (读取所有DO状态)
   - PULSE_DO:3,100 -> OK (DO3脉冲100ms)
   - RESET_DO -> OK (复位所有DO)

4. DI扩展中断命令：
   - CONFIG_DI_INT:3,RISING -> OK (配置DI3上升沿中断)
   - CONFIG_DI_INT:3,LOW_LEVEL -> OK (配置DI3低电平中断)
   - READ_DI_INT -> DI_INT:0,2,5 或 DI_INT:NONE (读取DI中断状态)
   - CLEAR_DI_INT:3 -> OK (清除DI3中断)
   - CLEAR_DI_INT:ALL -> OK (清除所有DI中断)

命令格式：
- 发送：COMMAND[:DATA]\n
- 响应：RESPONSE\n

错误响应：
- ERROR:message (命令执行失败)
- UNKNOWN (未知命令)

GPIO模式：
- INPUT: 输入模式
- INPUT_PULLUP: 输入上拉模式
- OUTPUT: 输出模式

中断模式：
- RISING: 上升沿触发
- FALLING: 下降沿触发
- BOTH: 双边沿触发
- NONE: 禁用中断
"""
