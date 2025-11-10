# -*- coding: utf-8 -*-
"""
ZDT电机CAN通信接口
支持SLCAN协议通信
"""

import time
import serial
import logging
from typing import List, Optional
from .exceptions import CANInterfaceException, TimeoutException
from .utils import format_hex_data

# 默认超时时间
DEFAULT_TIMEOUT = 1.0


class SLCANInterface:
    """SLCAN接口实现"""
    
    def __init__(self, port: str = 'COM18', baudrate: int = 500000):
        """
        初始化SLCAN接口
        
        Args:
            port: 串口号
            baudrate: 波特率
        """
        self.port = port
        self.baudrate = baudrate
        self.ser: Optional[serial.Serial] = None
        self.logger = logging.getLogger(__name__)
        
        self.logger.info(f"初始化SLCAN接口: {port}, 波特率: {baudrate}")
    
    def connect(self) -> None:
        """连接SLCAN设备"""
        try:
            self.ser = serial.Serial(
                port=self.port,
                baudrate=self.baudrate,
                timeout=1.0,
                write_timeout=1.0
            )
            
            # 等待设备稳定
            time.sleep(0.5)
            
            # 初始化SLCAN
            self._send_slcan_cmd("C\r")  # 关闭CAN通道
            time.sleep(0.1)
            self._send_slcan_cmd("S6\r")  # 设置500K波特率
            time.sleep(0.1)
            self._send_slcan_cmd("O\r")  # 打开CAN通道
            time.sleep(0.1)
            
            self.logger.info(f"SLCAN连接成功: {self.port}")
            
        except Exception as e:
            self.logger.error(f"SLCAN连接失败: {e}")
            raise CANInterfaceException(f"SLCAN连接失败: {e}")
    
    def disconnect(self) -> None:
        """断开SLCAN连接"""
        if self.ser:
            try:
                # 关闭CAN通道
                self._send_slcan_cmd("C\r")
                time.sleep(0.1)
                
                self.ser.close()
                self.ser = None
                self.logger.info("SLCAN连接已断开")
                
            except Exception as e:
                self.logger.warning(f"断开SLCAN连接时出现警告: {e}")
    
    def __enter__(self):
        """上下文管理器入口"""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.disconnect()
    
    def _send_slcan_cmd(self, cmd: str) -> Optional[bytes]:
        """发送SLCAN命令"""
        if not self.ser:
            return None
            
        try:
            self.ser.write(cmd.encode('ascii'))
            self.ser.flush()
            time.sleep(0.1)
            
            response = None
            if self.ser.in_waiting > 0:
                response = self.ser.read(self.ser.in_waiting)
            
            return response
            
        except Exception as e:
            self.logger.error(f"SLCAN命令发送失败: {e}")
            return None
    
    def send_message(self, frame_id: int, data: List[int]) -> None:
        """
        发送CAN消息 (通过SLCAN)
        
        Args:
            frame_id: CAN帧ID
            data: 数据字节列表
        """
        if not self.ser:
            raise CANInterfaceException("SLCAN未连接")
        
        if len(data) > 8:
            raise CANInterfaceException(f"CAN数据长度不能超过8字节，当前: {len(data)}")
        
        try:
            # 构建SLCAN扩展帧命令: T<8位ID><长度><数据>\r
            data_len = len(data)
            data_hex = ''.join(f'{b:02X}' for b in data)
            slcan_cmd = f"T{frame_id:08X}{data_len}{data_hex}\r"
            
            self.logger.debug(f"发送SLCAN命令: {slcan_cmd.strip()}")
            self.logger.debug(f"CAN帧 - ID: 0x{frame_id:04X}, 数据: {format_hex_data(data)}")
            
            # 清空接收缓冲区
            self.ser.flushInput()
            
            # 发送命令
            self.ser.write(slcan_cmd.encode('ascii'))
            self.ser.flush()
            
        except Exception as e:
            raise CANInterfaceException(f"发送SLCAN消息失败: {e}")
    
    def receive_message(self, expected_frame_id: int, timeout: float = DEFAULT_TIMEOUT) -> List[int]:
        """
        接收CAN消息 (通过SLCAN)
        
        Args:
            expected_frame_id: 期望的CAN帧ID
            timeout: 超时时间(秒)
            
        Returns:
            List[int]: 接收到的数据
        """
        if not self.ser:
            raise CANInterfaceException("SLCAN未连接")
        
        try:
            start_time = time.time()
            response_data = b''
            
            while time.time() - start_time < timeout:
                if self.ser.in_waiting > 0:
                    new_data = self.ser.read(self.ser.in_waiting)
                    response_data += new_data
                    
                    # 检查是否收到完整响应
                    if b'\r' in response_data:
                        break
                        
                time.sleep(0.01)
            
            if not response_data:
                raise TimeoutException(timeout)
            
            # 解析SLCAN响应
            response_str = response_data.decode('ascii', errors='ignore')
            self.logger.debug(f"收到SLCAN响应: {repr(response_str)}")
            
            lines = response_str.strip().split('\r')
            
            for line in lines:
                line = line.strip()
                if line.startswith('T') and len(line) > 9:
                    try:
                        # 解析: T<8位ID><长度><数据>
                        resp_id = int(line[1:9], 16)
                        resp_len = int(line[9], 16)
                        resp_data = []
                        
                        for i in range(resp_len):
                            byte_pos = 10 + i * 2
                            if byte_pos + 1 < len(line):
                                resp_data.append(int(line[byte_pos:byte_pos+2], 16))
                        
                        self.logger.debug(f"解析CAN响应: ID=0x{resp_id:X}, 数据={format_hex_data(resp_data)}")
                        
                        if resp_id == expected_frame_id:
                            return resp_data
                            
                    except Exception as e:
                        self.logger.error(f"解析响应失败: {e}, 原始数据: {line}")
            
            raise TimeoutException(timeout)
            
        except serial.SerialTimeoutException:
            raise TimeoutException(timeout)
        except Exception as e:
            self.logger.error(f"接收SLCAN消息时发生错误: {e}")
            raise CANInterfaceException(f"接收SLCAN消息失败: {e}")
    
    def send_command_and_receive_response(self, motor_id: int, command_data: List[int], 
                                         timeout: float = DEFAULT_TIMEOUT) -> List[int]:
        """
        发送命令并接收响应 - 正确的ZDT协议实现
        
        Args:
            motor_id: 电机ID
            command_data: 命令数据 (不包含地址，只有功能码+参数+校验)
            timeout: 超时时间(秒)
            
        Returns:
            List[int]: 响应数据
        """
        # 计算CAN帧ID: (ID_Addr << 8)
        base_frame_id = motor_id << 8  # 例如: motor_id=1 -> 0x0100
        
        if len(command_data) <= 8:
            # 小于等于8字节的命令，直接发送
            self.send_message(base_frame_id, command_data)
            return self.receive_message(base_frame_id, timeout)
        else:
            # 大于8字节的命令，分包发送
            return self._send_multi_packet_command(motor_id, command_data, timeout)
 
    def send_command_no_response(self, motor_id: int, command_data: List[int]) -> None:
        """
        发送命令但不等待响应（用于多电机命令在Response=None/Reached时不返回确认的场景）。
        会自动处理分包发送。
        """
        base_frame_id = motor_id << 8
        if len(command_data) <= 8:
            self.send_message(base_frame_id, command_data)
        else:
            # 分包发送（与 _send_multi_packet_command 一致，但不接收）
            function_code = command_data[0]
            packets = []
            packets.append(command_data[:8])
            remaining = command_data[8:]
            while remaining:
                packets.append([function_code] + remaining[:7])
                remaining = remaining[7:]
            for i, packet in enumerate(packets):
                frame_id = base_frame_id + i
                self.send_message(frame_id, packet)
    
    def send_command_and_receive_response_from(self, motor_id: int, command_data: List[int],
                                               expected_response_motor_id: int,
                                               timeout: float = DEFAULT_TIMEOUT) -> List[int]:
        """
        发送命令并从特定的期望响应电机ID接收响应。
        适用于Y42多电机命令：发送到0号(广播)，但仅1号电机回复确认。
        
        Args:
            motor_id: 发送命令的电机ID（例如0号广播）
            command_data: 命令数据 (不包含地址，只有功能码+参数+校验)
            expected_response_motor_id: 期望接收回复的电机ID（例如1）
            timeout: 超时时间(秒)
        """
        send_frame_id = motor_id << 8
        expected_frame_id = expected_response_motor_id << 8
        
        if len(command_data) <= 8:
            self.send_message(send_frame_id, command_data)
            return self.receive_message(expected_frame_id, timeout)
        else:
            # 分包发送（使用发送ID的分包帧ID），接收时按期望ID
            base_frame_id = send_frame_id
            function_code = command_data[0]
            # 分包
            packets = []
            first_packet = command_data[:8]
            packets.append(first_packet)
            remaining_data = command_data[8:]
            packet_index = 1
            while remaining_data:
                packet_data = [function_code] + remaining_data[:7]
                packets.append(packet_data)
                remaining_data = remaining_data[7:]
                packet_index += 1
            # 发送所有包
            for i, packet in enumerate(packets):
                frame_id = base_frame_id + i
                self.send_message(frame_id, packet)

            # 接收来自期望ID的响应
            return self.receive_message(expected_frame_id, timeout)
    
    def _send_multi_packet_command(self, motor_id: int, command_data: List[int], 
                                 timeout: float) -> List[int]:
        """
        发送多包命令 - 正确的ZDT协议实现
        
        根据官方协议文档："并且每包数据的首个字节都为功能码"
        对于19字节的回零参数修改命令，需要分成3包发送：
        - 第一包(8字节): 4C AE 01 00 00 00 1E 00
        - 第二包(8字节): 4C 00 27 10 0F A0 03 20  
        - 第三包(4字节): 4C 00 3C 00 6B
        
        Args:
            motor_id: 电机ID
            command_data: 命令数据
            timeout: 超时时间(秒)
            
        Returns:
            List[int]: 响应数据
        """
        base_frame_id = motor_id << 8
        function_code = command_data[0]
        
        # 将数据分成8字节的包，每包都以功能码开头
        packets = []
        
        # 第一包：直接取前8字节
        first_packet = command_data[:8]
        packets.append(first_packet)
        
        # 处理剩余数据
        remaining_data = command_data[8:]
        packet_index = 1
        
        while remaining_data:
            # 每个后续包：功能码 + 最多7字节剩余数据
            packet_data = [function_code] + remaining_data[:7]
            packets.append(packet_data)
            self.logger.debug(f"第{packet_index + 1}包: {' '.join([f'{x:02X}' for x in packet_data])}")
            
            remaining_data = remaining_data[7:]
            packet_index += 1
        
        # 发送所有包
        for i, packet in enumerate(packets):
            frame_id = base_frame_id + i  # 0x0100, 0x0101, 0x0102, ...
            self.logger.debug(f"发送包{i + 1}, 帧ID: 0x{frame_id:04X}, 数据: {' '.join([f'{x:02X}' for x in packet])}")
            self.send_message(frame_id, packet)
            time.sleep(0.05)  # 包间延时
        
        # 接收响应 (从第一包的帧ID接收)
        return self.receive_message(base_frame_id, timeout)


def create_can_interface(interface_type: str = "slcan", **kwargs) -> SLCANInterface:
    """
    创建CAN接口实例的工厂函数
    
    Args:
        interface_type: 接口类型 (默认为"slcan")
        **kwargs: 其他参数
        
    Returns:
        SLCANInterface: SLCAN接口实例
    """
    # 现在统一使用SLCAN接口
    return SLCANInterface(**kwargs) 