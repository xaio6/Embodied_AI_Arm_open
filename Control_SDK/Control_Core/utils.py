# -*- coding: utf-8 -*-
"""
ZDT闭环驱动板SDK工具函数
"""

from typing import List, Union
from .constants import CHECKSUM_BYTE, Parameters
from .exceptions import InvalidParameterException


def bytes_to_int16(data: List[int], start_index: int = 0, signed: bool = False) -> int:
    """
    将字节数组转换为16位整数 (小端序)
    
    Args:
        data: 字节数组
        start_index: 起始索引
        signed: 是否为有符号数
        
    Returns:
        int: 转换后的整数
    """
    if len(data) < start_index + 2:
        raise ValueError("数据长度不足")
    
    low_byte = data[start_index]
    high_byte = data[start_index + 1]
    
    result = (high_byte << 8) | low_byte
    
    if signed and result > 32767:
        result = result - 65536
    
    return result


def bytes_to_int32(data: List[int], start_index: int = 0, signed: bool = False) -> int:
    """
    将字节数组转换为32位整数 (小端序)
    
    Args:
        data: 字节数组
        start_index: 起始索引
        signed: 是否为有符号数
        
    Returns:
        int: 转换后的整数
    """
    if len(data) < start_index + 4:
        raise ValueError("数据长度不足")
    
    byte0 = data[start_index]      # 最低字节 (LSB)
    byte1 = data[start_index + 1]
    byte2 = data[start_index + 2]
    byte3 = data[start_index + 3]  # 最高字节 (MSB)
    
    # 小端序: byte0是最低字节，byte3是最高字节
    result = (byte3 << 24) | (byte2 << 16) | (byte1 << 8) | byte0
    
    if signed and result > 2147483647:
        result = result - 4294967296
    
    return result


def int16_to_bytes(value: int) -> List[int]:
    """
    将16位整数转换为字节数组 (小端序)
    
    Args:
        value: 整数值
        
    Returns:
        List[int]: 字节数组
    """
    if value < -32768 or value > 65535:
        raise ValueError("值超出16位整数范围")
    
    if value < 0:
        value = value + 65536
    
    low_byte = value & 0xFF
    high_byte = (value >> 8) & 0xFF
    
    return [low_byte, high_byte]


def int16_to_bytes_big_endian(value: int) -> List[int]:
    """
    将16位整数转换为字节数组 (大端序)
    
    Args:
        value: 整数值
        
    Returns:
        List[int]: 字节数组 (大端序)
    """
    if value < -32768 or value > 65535:
        raise ValueError("值超出16位整数范围")
    
    if value < 0:
        value = value + 65536
    
    high_byte = (value >> 8) & 0xFF  # 高字节
    low_byte = value & 0xFF          # 低字节
    
    return [high_byte, low_byte]


def int32_to_bytes(value: int) -> List[int]:
    """
    将32位整数转换为字节数组 (大端序)
    
    Args:
        value: 整数值
        
    Returns:
        List[int]: 字节数组 (大端序)
    """
    if value < -2147483648 or value > 4294967295:
        raise ValueError("值超出32位整数范围")
    
    if value < 0:
        value = value + 4294967296
    
    byte3 = (value >> 24) & 0xFF  # 最高字节
    byte2 = (value >> 16) & 0xFF
    byte1 = (value >> 8) & 0xFF
    byte0 = value & 0xFF          # 最低字节
    
    return [byte3, byte2, byte1, byte0]



def rpm_to_motor_speed(rpm: float) -> int:
    """
    将RPM转换为电机速度参数 (放大10倍)
    
    Args:
        rpm: 转速 (RPM)
        
    Returns:
        int: 电机速度参数
    """
    return int(abs(rpm) * Parameters.SPEED_SCALE)


def motor_speed_to_rpm(motor_speed: int) -> float:
    """
    将电机速度参数转换为RPM (缩小10倍)
    
    Args:
        motor_speed: 电机速度参数
        
    Returns:
        float: 转速 (RPM)
    """
    return motor_speed / Parameters.SPEED_SCALE


def degree_to_motor_position(degree: float) -> int:
    """
    将角度转换为电机位置参数 (放大10倍)
    
    Args:
        degree: 角度 (度)
        
    Returns:
        int: 电机位置参数
    """
    return int(abs(degree) * Parameters.POSITION_SCALE)


def motor_position_to_degree(motor_position: int) -> float:
    """
    将电机位置参数转换为角度 (缩小10倍)
    
    Args:
        motor_position: 电机位置参数
        
    Returns:
        float: 角度 (度)
    """
    return motor_position / Parameters.POSITION_SCALE


def motor_position_error_to_degree(motor_position_error: int) -> float:
    """
    将电机位置误差参数转换为角度 (缩小100倍)
    
    Args:
        motor_position_error: 电机位置误差参数
        
    Returns:
        float: 角度误差 (度)
    """
    return motor_position_error / Parameters.POSITION_ERROR_SCALE


def encoder_raw_to_degree(encoder_raw: int) -> float:
    """
    将编码器原始值转换为角度
    
    Args:
        encoder_raw: 编码器原始值 (0-16383)
        
    Returns:
        float: 角度 (度)
    """
    return (encoder_raw / Parameters.ENCODER_RAW_MAX) * 360.0


def encoder_calibrated_to_degree(encoder_calibrated: int) -> float:
    """
    将校准后编码器值转换为角度
    
    Args:
        encoder_calibrated: 校准后编码器值 (0-65535)
        
    Returns:
        float: 角度 (度)
    """
    return (encoder_calibrated / Parameters.ENCODER_CALIBRATED_MAX) * 360.0


def parse_signed_value(data: List[int], start_index: int) -> tuple:
    """
    解析带符号的值 (第一个字节是符号位)
    
    Args:
        data: 字节数组
        start_index: 起始索引
        
    Returns:
        tuple: (符号, 无符号值)
    """
    if len(data) < start_index + 1:
        raise ValueError("数据长度不足")
    
    sign = data[start_index]  # 0为正，1为负
    return sign, data[start_index + 1:]


def create_signed_command_data(value: float, conversion_func) -> tuple:
    """
    创建带符号的命令数据
    
    Args:
        value: 值 (可以是负数)
        conversion_func: 转换函数
        
    Returns:
        tuple: (符号位, 转换后的绝对值)
    """
    sign = Parameters.DIRECTION_NEGATIVE if value < 0 else Parameters.DIRECTION_POSITIVE
    abs_value = conversion_func(abs(value))
    return sign, abs_value


def validate_motor_id(motor_id: int) -> None:
    """
    验证电机ID是否有效
    
    Args:
        motor_id: 电机ID
        
    Raises:
        InvalidParameterException: 当ID无效时抛出
    """
    if not (0 <= motor_id <= 255):
        raise InvalidParameterException(f"电机ID必须在0-255范围内，当前值: {motor_id}")


def validate_speed(speed: float) -> None:
    """
    验证速度参数是否有效
    
    Args:
        speed: 速度 (RPM)
        
    Raises:
        InvalidParameterException: 当速度无效时抛出
    """
    if abs(speed) > 6553.5:  # 考虑到10倍放大，最大值是65535/10
        raise InvalidParameterException(f"速度超出范围，最大值: ±6553.5 RPM，当前值: {speed}")


def validate_position(position: float) -> None:
    """
    验证位置参数是否有效
    
    Args:
        position: 位置 (度)
        
    Raises:
        InvalidParameterException: 当位置无效时抛出
    """
    if abs(position) > 429496729.5:  # 考虑到10倍放大，最大值是2^32/2/10
        raise InvalidParameterException(f"位置超出范围，最大值: ±429496729.5 度，当前值: {position}")


def validate_current(current: int) -> None:
    """
    验证电流参数是否有效
    
    Args:
        current: 电流 (mA)
        
    Raises:
        InvalidParameterException: 当电流无效时抛出
    """
    if not (0 <= current <= 65535):
        raise InvalidParameterException(f"电流必须在0-65535mA范围内，当前值: {current}")


def validate_acceleration(acceleration: int) -> None:
    """
    验证加速度参数是否有效
    
    Args:
        acceleration: 加速度 (RPM/s)
        
    Raises:
        InvalidParameterException: 当加速度无效时抛出
    """
    if not (0 <= acceleration <= 65535):
        raise InvalidParameterException(f"加速度必须在0-65535 RPM/s范围内，当前值: {acceleration}")


def format_hex_data(data: Union[List[int], bytes]) -> str:
    """
    格式化字节数据为十六进制字符串
    
    Args:
        data: 字节数据
        
    Returns:
        str: 格式化的十六进制字符串
    """
    if isinstance(data, bytes):
        data = list(data)
    
    return ' '.join([f'{byte:02X}' for byte in data])


def calculate_can_frame_id(motor_id: int, packet_index: int = 0) -> int:
    """
    计算CAN帧ID
    
    Args:
        motor_id: 电机ID
        packet_index: 包索引 (用于大于8字节的命令)
        
    Returns:
        int: CAN帧ID
    """
    return (motor_id << 8) + packet_index 