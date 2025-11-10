# -*- coding: utf-8 -*-
"""
DPI自适应缩放工具模块：仅缩放字体，避免布局被强行放大
"""
import sys
from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt, QCoreApplication, QObject
from PyQt5.QtGui import QFont


class DPIScaler(QObject):
    def __init__(self):
        super().__init__()
        self.base_dpi = 96
        self.current_dpi = 96
        self.scale_factor = 1.0
        self.base_font_size = 12

    def calculate_scale_factor(self, app: QApplication = None):
        if app is None:
            app = QApplication.instance()
        if app is None:
            return 1.0
        # 若已启用 Qt High DPI 缩放，则不要再次放大字体，避免双重缩放
        try:
            if QCoreApplication.testAttribute(Qt.AA_EnableHighDpiScaling):
                self.scale_factor = 1.0
                # 打包环境外不打印
                return self.scale_factor
        except Exception:
            pass
        try:
            screen = app.primaryScreen()
            if screen is None:
                return 1.0
            if sys.platform == "win32":
                try:
                    import ctypes
                    user32 = ctypes.windll.user32
                    gdi32 = ctypes.windll.gdi32
                    hdc = user32.GetDC(0)
                    dpi = gdi32.GetDeviceCaps(hdc, 88)  # LOGPIXELSX
                    user32.ReleaseDC(0, hdc)
                    self.current_dpi = dpi
                    self.scale_factor = dpi / self.base_dpi
                    pass
                except Exception as e:
                    pass
                    logical_dpi = screen.logicalDotsPerInch()
                    self.current_dpi = logical_dpi
                    self.scale_factor = logical_dpi / self.base_dpi
                    pass
            else:
                logical_dpi = screen.logicalDotsPerInch()
                self.current_dpi = logical_dpi
                self.scale_factor = logical_dpi / self.base_dpi
                pass

            if abs(self.scale_factor - 1.0) < 0.1:
                self.scale_factor = 1.0
            else:
                self.scale_factor = max(0.75, min(3.0, self.scale_factor))
            # 静默返回
        except Exception as e:
            pass
            self.scale_factor = 1.0
        return self.scale_factor

    def attach_dynamic_listeners(self, app: QApplication, on_scale_changed=None):
        """监听主屏变化/DPI 变化，动态重算缩放并回调更新样式。"""
        if app is None:
            return
        def _recalc():
            old = self.scale_factor
            self.calculate_scale_factor(app)
            if abs(self.scale_factor - old) > 1e-3:
                if callable(on_scale_changed):
                    try:
                        on_scale_changed(self.scale_factor)
                    except Exception:
                        pass
        try:
            app.screenAdded.connect(lambda *_: _recalc())  # type: ignore
        except Exception:
            pass
        try:
            app.screenRemoved.connect(lambda *_: _recalc())  # type: ignore
        except Exception:
            pass
        try:
            for screen in app.screens():
                try:
                    screen.logicalDotsPerInchChanged.connect(lambda *_: _recalc())  # type: ignore
                except Exception:
                    pass
        except Exception:
            pass

    def get_scaled_font_size(self, base_size: int = None) -> int:
        if base_size is None:
            base_size = self.base_font_size
        scaled_size = int(base_size * self.scale_factor)
        return max(8, scaled_size)

    def get_scaled_size(self, base_size: int) -> int:
        return int(base_size * self.scale_factor)

    def create_scaled_font(self, family: str = "Microsoft YaHei UI", base_size: int = None) -> QFont:
        if base_size is None:
            base_size = self.base_font_size
        scaled_size = self.get_scaled_font_size(base_size)
        font = QFont(family, scaled_size)
        font.setStyleHint(QFont.SansSerif)
        return font

    def get_scaled_stylesheet(self, base_stylesheet: str) -> str:
        if self.scale_factor == 1.0:
            return base_stylesheet
        import re
        def scale_font_size(match):
            size = int(match.group(1))
            scaled_size = self.get_scaled_font_size(size)
            return f"font-size: {scaled_size}px"
        scaled_stylesheet = base_stylesheet
        scaled_stylesheet = re.sub(r'font-size:\s*(\d+)px', scale_font_size, scaled_stylesheet)
        # 额外兼容 'font: bold 12px' 或 'font: 12px' 的写法
        def scale_shorthand_font(match):
            prefix = match.group(1) or ''
            size = int(match.group(2))
            scaled_size = self.get_scaled_font_size(size)
            return f"font: {prefix}{scaled_size}px"
        scaled_stylesheet = re.sub(r'font:\s*([a-zA-Z\s]*?)?(\d+)px', scale_shorthand_font, scaled_stylesheet)
        return scaled_stylesheet


dpi_scaler = DPIScaler()


def apply_dpi_scaling(app: QApplication):
    dpi_scaler.calculate_scale_factor(app)
    return dpi_scaler


