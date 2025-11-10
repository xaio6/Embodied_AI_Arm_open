# -*- coding: utf-8 -*-
"""
ZDT闭环驱动板SDK异常定义
"""


class ZDTMotorException(Exception):
    """ZDT电机SDK基础异常类"""
    pass


class CommunicationException(ZDTMotorException):
    """通信异常"""
    pass


class CANInterfaceException(CommunicationException):
    """CAN接口异常"""
    pass


class CommandException(ZDTMotorException):
    """命令执行异常"""
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


class ConditionNotMetException(CommandException):
    """条件不满足异常"""
    pass


class MotorNotEnabledException(ConditionNotMetException):
    """电机未使能异常"""
    def __init__(self):
        super().__init__("电机未使能，请先使能电机")


class StallProtectionException(ConditionNotMetException):
    """堵转保护异常"""
    def __init__(self):
        super().__init__("触发了堵转保护，请检查电机状态")


class HomingInProgressException(ConditionNotMetException):
    """正在回零异常"""
    def __init__(self):
        super().__init__("电机正在回零，无法执行其他操作")


class TimeoutException(CommunicationException):
    """超时异常"""
    def __init__(self, timeout_duration):
        super().__init__(f"通信超时，超时时间: {timeout_duration}秒")
        self.timeout_duration = timeout_duration


class InvalidParameterException(ZDTMotorException):
    """无效参数异常"""
    pass


class DeviceNotFoundException(CANInterfaceException):
    """设备未找到异常"""
    def __init__(self, device_id):
        super().__init__(f"未找到设备ID: {device_id}")
        self.device_id = device_id


class ChecksumException(CommunicationException):
    """校验和异常"""
    def __init__(self):
        super().__init__("数据校验失败，可能存在通信错误")


class InvalidResponseException(CommunicationException):
    """无效响应异常"""
    def __init__(self, expected_length, actual_length):
        super().__init__(f"响应数据长度不正确，期望: {expected_length}, 实际: {actual_length}")
        self.expected_length = expected_length
        self.actual_length = actual_length 