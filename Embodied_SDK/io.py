#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
IO / ESP32 控制 SDK 封装
========================

目标：
- 复用 `core.esp32_io_controller.ESP32IOController`，提供简单的 DO/DI 读写接口；
- 让外部（Web / ROS / 脚本）可以方便控制外部执行器、传感器，而不用接触底层串口协议。
"""

from __future__ import annotations

from typing import List, Optional, Dict, Any

from Horizon_Core.core.esp32_io_controller import ESP32IOController


class IOSDK:
    """
    IO / ESP32 控制 SDK。

    - 主要面向 IO 开关量的读写；
    - 作业逻辑（job 管理）仍在 GUI 中，后续如有需要再逐步 SDK 化。
    """

    def __init__(
        self,
        port: str = "COM3",
        baudrate: int = 115200,
        timeout: float = 1.0,
    ) -> None:
        self._controller = ESP32IOController(
            port=port,
            baudrate=baudrate,
            timeout=timeout,
        )

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def connect(self) -> bool:
        """连接 ESP32。"""
        return self._controller.connect()

    def disconnect(self) -> None:
        """断开 ESP32 连接。"""
        self._controller.disconnect()

    # ------------------------------------------------------------------
    # DI 读
    # ------------------------------------------------------------------

    def read_di_states(self) -> Optional[List[bool]]:
        """读取全部 DI 状态（长度 8 的布尔列表）。"""
        return self._controller.read_di_states()

    def read_di(self, pin: int) -> Optional[bool]:
        """读取单个 DI 引脚状态（0-7）。"""
        return self._controller.read_single_di(pin)

    # ------------------------------------------------------------------
    # DO 写 / 读
    # ------------------------------------------------------------------

    def set_do(self, pin: int, state: bool) -> bool:
        """设置单个 DO 引脚状态。"""
        return self._controller.set_do_state(pin, state)

    def set_do_all(self, states: List[bool]) -> bool:
        """一次性设置全部 DO 状态（长度 8）。"""
        return self._controller.set_do_states(states)

    def read_do_states(self) -> Optional[List[bool]]:
        """读取全部 DO 状态。"""
        return self._controller.read_do_states()

    def pulse_do(self, pin: int, duration: float = 0.1) -> bool:
        """对单个 DO 引脚输出一个脉冲。"""
        return self._controller.pulse_do(pin, duration)

    def reset_all_do(self) -> bool:
        """复位全部 DO 输出为低电平（直接转发 ESP32IOController.reset_all_do）。"""
        return self._controller.reset_all_do()

    # ------------------------------------------------------------------
    # 版本 / 状态 / 中断等高级能力
    # ------------------------------------------------------------------

    def get_version(self) -> Optional[str]:
        """获取 ESP32 固件版本（直接转发 ESP32IOController.get_version）。"""
        return self._controller.get_version()

    def get_status(self) -> Optional[Dict[str, Any]]:
        """获取 ESP32 状态信息（直接转发 ESP32IOController.get_status）。"""
        return self._controller.get_status()

    def configure_di_pullup(self, pin: int, enable: bool) -> bool:
        """配置 DI 引脚上拉电阻（直接转发 ESP32IOController.configure_di_pullup）。"""
        return self._controller.configure_di_pullup(pin, enable)

    def configure_di_interrupt(self, pin: int, mode: str) -> bool:
        """
        配置 DI 引脚中断模式（直接转发 ESP32IOController.configure_di_interrupt）。

        mode 可选: "RISING", "FALLING", "BOTH", "NONE"
        """
        return self._controller.configure_di_interrupt(pin, mode)

    def read_interrupt_status(self) -> Optional[List[int]]:
        """读取触发中断的 DI 引脚列表（直接转发 ESP32IOController.read_interrupt_status）。"""
        return self._controller.read_interrupt_status()


