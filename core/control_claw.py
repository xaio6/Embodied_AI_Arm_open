import serial
import time
from typing import Optional


class ClawController:
    """串口夹爪控制器（绝对角度 0–90°）
    
    使用示例：
        claw = ClawController(port='COM9', baudrate=9600)
        claw.connect()
        claw.open(0)     # 完全张开
        claw.close(90)   # 完全闭合
        claw.disconnect()
    """

    def __init__(self, port: str, baudrate: int = 9600, timeout: float = 1.0):
        self.port = port
        self.baudrate = baudrate
        self.timeout = timeout
        self._ser: Optional[serial.Serial] = None

    def connect(self) -> None:
        """连接串口（幂等）"""
        if self._ser and self._ser.is_open:
            return
        self._ser = serial.Serial(
            port=self.port,
            baudrate=self.baudrate,
            timeout=self.timeout,
            write_timeout=1.0,
        )
        # 等待设备稳定
        time.sleep(0.2)

    def disconnect(self) -> None:
        """断开串口连接（幂等）"""
        if self._ser:
            try:
                if self._ser.is_open:
                    self._ser.close()
            finally:
                self._ser = None

    def is_connected(self) -> bool:
        return bool(self._ser and self._ser.is_open)

    def set_angle(self, angle: float) -> None:
        """设置舵机绝对角度（0–90）"""
        if not 0 <= angle <= 90:
            raise ValueError("Angle must be in [0, 90]")
        if not self.is_connected():
            raise RuntimeError("Claw serial is not connected. Call connect() first.")
        value = int(round(angle))
        self._ser.write(f"{value}\n".encode("ascii"))
        self._ser.flush()
        time.sleep(0.1)

    def open(self, open_angle: float) -> None:
        """张开到指定角度（例如 0=完全张开）"""
        self.set_angle(open_angle)

    def close(self, close_angle: float) -> None:
        """闭合到指定角度（例如 90=完全闭合）"""
        self.set_angle(close_angle)

    # 上下文管理器支持
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb):
        self.disconnect()
