# -*- coding: utf-8 -*-
"""
ZDT电机控制可视化界面主程序
"""

import sys
import os
import logging
import signal
import atexit
from PyQt5.QtWidgets import QApplication, QStyleFactory, QMessageBox, QSplashScreen
from PyQt5.QtCore import Qt, QObject, QEvent, QCoreApplication
from PyQt5.QtGui import QFont, QPalette, QColor, QIcon, QPixmap
import threading

# DPI 自适应
from Main_UI.utils.dpi_scaler import apply_dpi_scaling, dpi_scaler

# 添加Control_SDK目录到路径，以便导入Control_Core
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)  # 项目根目录
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

from ui.main_window import MainWindow
from Control_SDK.Control_Core import setup_logging

# 全局变量用于存储主窗口实例，以便在信号处理器中访问
main_window_instance = None

def cleanup_resources():
    """清理系统资源"""
    global main_window_instance
    if main_window_instance:
        try:
            
            # 清理视觉抓取控件的相机资源
            if hasattr(main_window_instance, 'vision_grasp_widget') and main_window_instance.vision_grasp_widget:
                try:
                    if main_window_instance.vision_grasp_widget.camera_running:
                        main_window_instance.vision_grasp_widget.stop_camera()
                except Exception as e:
                    print(f"⚠️ 清理视觉抓取相机资源时出错: {e}")
            
            # 清理具身智能控件的相机资源
            if hasattr(main_window_instance, 'embodied_intelligence_widget') and main_window_instance.embodied_intelligence_widget:
                try:
                    if hasattr(main_window_instance.embodied_intelligence_widget, 'camera_enabled') and main_window_instance.embodied_intelligence_widget.camera_enabled:
                        main_window_instance.embodied_intelligence_widget.stop_camera()
                except Exception as e:
                    print(f"⚠️ 清理具身智能相机资源时出错: {e}")
            
            print("✅ 资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 清理资源时发生错误: {e}")

def signal_handler(signum, frame):
    """信号处理器 - 处理程序被强制终止的情况"""
    print(f"\n🛑 接收到信号 {signum}，正在安全退出...")
    cleanup_resources()
    sys.exit(0)

class GlobalEmergencyStopFilter(QObject):
    """全局紧急停止事件过滤器"""
    
    def __init__(self, main_window):
        super().__init__()
        self.main_window = main_window
        self.emergency_stop_active = False  # 防止重复触发
        
    def eventFilter(self, obj, event):
        """事件过滤器 - 监听空格键进行紧急停止"""
        if event.type() == QEvent.KeyPress:
            if event.key() == Qt.Key_Space:
                # 检查是否在输入框中（避免在输入时误触发）
                if hasattr(obj, 'hasFocus') and obj.hasFocus():
                    # 检查是否是输入控件
                    from PyQt5.QtWidgets import QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox
                    if isinstance(obj, (QLineEdit, QTextEdit, QPlainTextEdit, QSpinBox, QDoubleSpinBox)):
                        return False  # 不拦截输入框中的空格键
                
                # 执行全局紧急停止
                self.execute_global_emergency_stop()
                return True  # 拦截事件，防止传递给其他控件
                
        return False  # 不拦截其他事件
    
    def execute_global_emergency_stop(self):
        """执行全局紧急停止"""
        if self.emergency_stop_active:
            return  # 防止重复触发
            
        self.emergency_stop_active = True
        
        try:
            print("🛑 全局紧急停止触发！")
            
            # 先尝试停止示教程序线程（如存在）
            try:
                if hasattr(self.main_window, 'teach_pendant_widget') and self.main_window.teach_pendant_widget:
                    self.main_window.teach_pendant_widget.emergency_stop_teaching_program()
                    print("🛑 示教程序线程已请求停止")
            except Exception as stop_prog_err:
                print(f"⚠ 停止示教程序线程时发生错误: {stop_prog_err}")
            
            # 新增：停止多电机循环控制
            try:
                if hasattr(self.main_window, 'multi_motor_widget') and self.main_window.multi_motor_widget:
                    # 静默停止，避免弹窗阻塞全局紧急停止
                    self.main_window.multi_motor_widget.stop_multi_cycle_motion()
                    print("🛑 多电机循环控制已停止")
            except Exception as stop_cycle_err:
                print(f"⚠ 停止多电机循环控制时发生错误: {stop_cycle_err}")
            
            # 新增：停止具身智能系统任务队列和执行线程
            try:
                if hasattr(self.main_window, 'embodied_intelligence_widget') and self.main_window.embodied_intelligence_widget:
                    self.main_window.embodied_intelligence_widget.emergency_stop()
                    print("🛑 具身智能系统已紧急停止")
            except Exception as stop_embodied_err:
                print(f"⚠ 停止具身智能系统时发生错误: {stop_embodied_err}")
            
            # 获取当前连接的电机
            motors = None
            if hasattr(self.main_window, 'connection_widget') and hasattr(self.main_window.connection_widget, 'motors'):
                motors = self.main_window.connection_widget.motors
            
            if not motors:
                print("⚠ 未检测到已连接的电机")
                # 避免弹框阻塞，使用状态栏提示（若可用）
                try:
                    if hasattr(self.main_window, 'status_bar') and self.main_window.status_bar:
                        self.main_window.status_bar.showMessage('⚠ 未检测到已连接的电机 | 全局紧急停止已触发', 3000)
                    else:
                        print('提示: 未检测到已连接的电机 | 全局紧急停止已触发')
                except Exception:
                    pass
                return
            
            # 执行所有电机的立即停止
            stopped_count = 0
            failed_count = 0
            
            for motor_id, motor in motors.items():
                try:
                    motor.control_actions.stop()
                    stopped_count += 1
                    print(f"✅ 电机 {motor_id} 停止成功")
                except Exception as e:
                    failed_count += 1
                    print(f"❌ 电机 {motor_id} 停止失败: {e}")
            
            # 简洁的反馈信息
            try:
                if stopped_count > 0:
                    msg = f"🛑 全局紧急停止完成！成功停止 {stopped_count} 个电机"
                    if failed_count > 0:
                        msg += f"，{failed_count} 个失败"
                else:
                    msg = "🛑 全局紧急停止触发完成"
                
                if hasattr(self.main_window, 'status_bar') and self.main_window.status_bar:
                    self.main_window.status_bar.showMessage(msg, 5000)
                else:
                    print(msg)
            except Exception:
                pass
                
        except Exception as e:
            print(f"❌ 全局紧急停止执行失败: {e}")
            QMessageBox.critical(None, '错误', f'全局紧急停止执行失败:\n{str(e)}\n\n请手动检查机械臂状态！')
        finally:
            self.emergency_stop_active = False

def setup_app_style(app):
    """设置应用程序样式"""
    # 设置应用程序样式
    app.setStyle(QStyleFactory.create('Fusion'))
    
    # 设置默认字体 - 为高分辨率显示器增大字体
    font = dpi_scaler.create_scaled_font("Microsoft YaHei UI", 12)
    font.setStyleHint(QFont.SansSerif)
    app.setFont(font)
    
    # 设置现代化浅色主题
    palette = QPalette()
    
    # 基础颜色
    palette.setColor(QPalette.Window, QColor(248, 249, 250))          # 主窗口背景
    palette.setColor(QPalette.WindowText, QColor(33, 37, 41))        # 主窗口文字
    palette.setColor(QPalette.Base, QColor(255, 255, 255))           # 输入框背景
    palette.setColor(QPalette.AlternateBase, QColor(248, 249, 250))  # 交替行背景
    palette.setColor(QPalette.ToolTipBase, QColor(255, 255, 255))    # 提示框背景
    palette.setColor(QPalette.ToolTipText, QColor(33, 37, 41))       # 提示框文字
    palette.setColor(QPalette.Text, QColor(33, 37, 41))              # 文本颜色
    palette.setColor(QPalette.Button, QColor(233, 236, 239))         # 按钮背景
    palette.setColor(QPalette.ButtonText, QColor(33, 37, 41))        # 按钮文字
    palette.setColor(QPalette.BrightText, QColor(220, 53, 69))       # 高亮文字
    palette.setColor(QPalette.Link, QColor(0, 123, 255))             # 链接颜色
    palette.setColor(QPalette.Highlight, QColor(0, 123, 255))        # 选中背景
    palette.setColor(QPalette.HighlightedText, QColor(255, 255, 255)) # 选中文字
    
    # 禁用状态颜色
    palette.setColor(QPalette.Disabled, QPalette.WindowText, QColor(108, 117, 125))
    palette.setColor(QPalette.Disabled, QPalette.Text, QColor(108, 117, 125))
    palette.setColor(QPalette.Disabled, QPalette.ButtonText, QColor(108, 117, 125))
    
    app.setPalette(palette)
    
    # 设置全局样式表（应用前对字体大小进行DPI缩放）
    base_stylesheet = """
        /* 主窗口样式 */
        QMainWindow {
            background-color: #f8f9fa;
        }
        
        /* 分组框样式 */
        QGroupBox {
            font-weight: bold;
            font-size: 13px;  /* 从11px改为13px */
            border: 2px solid #dee2e6;
            border-radius: 8px;
            margin-top: 1.5ex;  /* 增大顶部边距 */
            padding-top: 12px;  /* 增大内边距 */
            background-color: white;
        }
        
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 12px;  /* 增大左边距 */
            padding: 0 10px 0 10px;  /* 增大内边距 */
            color: #495057;
            background-color: white;
        }
        
        /* 按钮样式 */
        QPushButton {
            background-color: #007bff;
            border: none;
            color: white;
            padding: 10px 20px;  /* 增大内边距 */
            text-align: center;
            font-size: 12px;  /* 从10px改为12px */
            font-weight: 500;
            border-radius: 6px;
            min-width: 100px;  /* 增大最小宽度 */
            min-height: 40px;  /* 增大最小高度 */
        }
        
        QPushButton:hover {
            background-color: #0056b3;
        }
        
        QPushButton:pressed {
            background-color: #004085;
        }
        
        QPushButton:disabled {
            background-color: #6c757d;
            color: #adb5bd;
        }
        
        /* 特殊按钮颜色 */
        QPushButton[class="success"] {
            background-color: #28a745;
        }
        
        QPushButton[class="success"]:hover {
            background-color: #1e7e34;
        }
        
        QPushButton[class="danger"] {
            background-color: #dc3545;
        }
        
        QPushButton[class="danger"]:hover {
            background-color: #c82333;
        }
        
        QPushButton[class="warning"] {
            background-color: #ffc107;
            color: #212529;
        }
        
        QPushButton[class="warning"]:hover {
            background-color: #e0a800;
        }
        
        /* 输入框样式 */
        QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
            border: 1px solid #ced4da;
            border-radius: 4px;
            padding: 8px 14px;  /* 增大内边距 */
            font-size: 12px;  /* 从10px改为12px */
            background-color: white;
            color: #495057;
            min-height: 28px;  /* 增大最小高度 */
        }
        
        QLineEdit:focus, QSpinBox:focus, QDoubleSpinBox:focus, QComboBox:focus {
            border-color: #80bdff;
            outline: 0;
        }
        
        /* 下拉框样式 */
        QComboBox::drop-down {
            subcontrol-origin: padding;
            subcontrol-position: top right;
            width: 24px;  /* 增大宽度 */
            border-left-width: 1px;
            border-left-color: #ced4da;
            border-left-style: solid;
            border-top-right-radius: 4px;
            border-bottom-right-radius: 4px;
        }
        
        QComboBox::down-arrow {
            image: none;
            border-left: 5px solid transparent;  /* 增大箭头 */
            border-right: 5px solid transparent;
            border-top: 5px solid #495057;
            width: 0;
            height: 0;
        }
        
        /* 标签页样式 */
        QTabWidget::pane {
            border: 1px solid #dee2e6;
            background-color: white;
            border-radius: 8px;
        }
        
        QTabBar::tab {
            background-color: #e9ecef;
            border: 1px solid #dee2e6;
            padding: 12px 22px;  /* 增大内边距 */
            margin-right: 3px;  /* 增大间距 */
            border-top-left-radius: 6px;
            border-top-right-radius: 6px;
            color: #495057;
            font-weight: 500;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QTabBar::tab:selected {
            background-color: white;
            border-bottom-color: white;
            color: #007bff;
        }
        
        QTabBar::tab:hover {
            background-color: #f8f9fa;
        }
        
        /* 表格样式 */
        QTableWidget {
            gridline-color: #dee2e6;
            background-color: white;
            alternate-background-color: #f8f9fa;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QTableWidget::item {
            padding: 10px;  /* 增大内边距 */
            border: none;
            color: #495057;
        }
        
        QTableWidget::item:selected {
            background-color: #007bff;
            color: white;
        }
        
        QHeaderView::section {
            background-color: #e9ecef;
            padding: 10px;  /* 增大内边距 */
            border: none;
            border-right: 1px solid #dee2e6;
            border-bottom: 1px solid #dee2e6;
            font-weight: bold;
            color: #495057;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        /* 列表样式 */
        QListWidget {
            border: 1px solid #dee2e6;
            border-radius: 6px;
            background-color: white;
            alternate-background-color: #f8f9fa;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QListWidget::item {
            padding: 10px 15px;  /* 增大内边距 */
            border-bottom: 1px solid #f1f3f4;
            color: #495057;
        }
        
        QListWidget::item:selected {
            background-color: #007bff;
            color: white;
        }
        
        QListWidget::item:hover {
            background-color: #f8f9fa;
        }
        
        /* 复选框样式 */
        QCheckBox {
            color: #495057;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QCheckBox::indicator {
            width: 18px;  /* 增大尺寸 */
            height: 18px;
            border: 1px solid #ced4da;
            border-radius: 3px;
            background-color: white;
        }
        
        QCheckBox::indicator:checked {
            background-color: #007bff;
            border-color: #007bff;
            image: url(data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMTYiIGhlaWdodD0iMTYiIHZpZXdCb3g9IjAgMCAxNiAxNiIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPHBhdGggZD0iTTEzLjg1NDQgNC4xNDY0NUwxNC4xNDY5IDQuNDM5MzRMMTMuODU0NCA0LjE0NjQ1Wk02LjUgMTEuNUw2LjIwNzExIDExLjc5MjlDNi4zOTQ2NCAxMS45ODA0IDYuNjA1MzYgMTEuOTgwNCA2Ljc5Mjg5IDExLjc5MjlMNi41IDExLjVaTTIuMTQ2NDUgNy4xNDY0NUwxLjg1MzU2IDYuODUzNTZMMi4xNDY0NSA3LjE0NjQ1Wk0xMy41NjA3IDQuNDM5MzRMNi4yMDcxMSAxMS43OTI5TDYuNzkyODkgMTIuMjA3MUwxNC4xNDY5IDQuODUzNTVMMTMuNTYwNyA0LjQzOTM0Wk02Ljc5Mjg5IDExLjc5MjlMMi40MzkzNCA3LjQzOTM0TDEuODUzNTYgNy44NTM1NUw2LjIwNzExIDEyLjIwNzFMNi43OTI4OSAxMS43OTI5WiIgZmlsbD0id2hpdGUiLz4KPHN2Zz4K);
        }
        
        /* 标签样式 */
        QLabel {
            color: #495057;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        /* 表单标签样式 */
        QFormLayout QLabel {
            font-size: 12px;  /* 从10px改为12px */
            color: #495057;
            font-weight: 500;
        }
        
        /* 状态标签样式 */
        QLabel[class="status-connected"] {
            color: #28a745;
            font-weight: bold;
            font-size: 13px;  /* 从11px改为13px */
        }
        
        QLabel[class="status-disconnected"] {
            color: #dc3545;
            font-weight: bold;
            font-size: 13px;  /* 从11px改为13px */
        }
        
        QLabel[class="status-warning"] {
            color: #fd7e14;
            font-weight: bold;
            font-size: 13px;  /* 从11px改为13px */
        }
        
        /* 工具栏样式 */
        QToolBar {
            background-color: #f8f9fa;
            border: none;
            spacing: 6px;  /* 增大间距 */
            padding: 6px;  /* 增大内边距 */
        }
        
        /* 状态栏样式 */
        QStatusBar {
            background-color: #f8f9fa;
            border-top: 1px solid #dee2e6;
            color: #6c757d;
            font-size: 12px;  /* 从10px改为12px */
            padding: 4px;  /* 增大内边距 */
        }
        
        /* 菜单样式 */
        QMenuBar {
            background-color: #f8f9fa;
            border-bottom: 1px solid #dee2e6;
            color: #495057;
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QMenuBar::item {
            background-color: transparent;
            padding: 8px 15px;  /* 增大内边距 */
        }
        
        QMenuBar::item:selected {
            background-color: #e9ecef;
        }
        
        QMenu {
            background-color: white;
            border: 1px solid #dee2e6;
            border-radius: 6px;
            padding: 6px;  /* 增大内边距 */
            font-size: 12px;  /* 从10px改为12px */
        }
        
        QMenu::item {
            padding: 10px 20px;  /* 增大内边距 */
            border-radius: 4px;
        }
        
        QMenu::item:selected {
            background-color: #f8f9fa;
        }
    """
    app.setStyleSheet(dpi_scaler.get_scaled_stylesheet(base_stylesheet))
    return base_stylesheet

def main():
    """主函数"""
    # 在创建应用程序之前启用 Qt 原生 HighDPI（控件与字体等比缩放）
    try:
        QCoreApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
        QCoreApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    except Exception:
        pass

    # Qt HighDPI 已启用；无需额外进程级 DPI 感知设置

    # 创建应用程序
    app = QApplication(sys.argv)
    app.setApplicationName("ZDT电机控制界面")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("ZDT")

    # 应用 DPI 缩放（仅字体与像素映射）
    apply_dpi_scaling(app)
    
    # 设置应用程序图标
    # 获取logo.png的正确路径（在项目根目录）
    current_dir = os.path.dirname(os.path.abspath(__file__))
    icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
    
    if os.path.exists(icon_path):
        app.setWindowIcon(QIcon(icon_path))
    
    
    # 设置应用程序样式
    base_stylesheet = setup_app_style(app)
    
    # 设置日志
    setup_logging(logging.INFO)
    
    # 创建主窗口
    main_window = MainWindow()
    
    # 设置全局主窗口实例
    global main_window_instance
    main_window_instance = main_window
    
    # 注册信号处理器
    signal.signal(signal.SIGINT, signal_handler)  # Ctrl+C
    signal.signal(signal.SIGTERM, signal_handler)  # 终止信号
    
    # 注册退出时的清理函数
    atexit.register(cleanup_resources)
    
    # 创建并安装全局紧急停止事件过滤器
    emergency_stop_filter = GlobalEmergencyStopFilter(main_window)
    app.installEventFilter(emergency_stop_filter)
    
    # 显示启动提示
    print("🛑 安全提示: 按下空格键可在任何界面执行全局紧急停止")
    
    # 启动闪屏（覆盖白屏），同时后台准备主窗口
    splash = None
    try:
        splash_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "await2.png")
        if os.path.exists(splash_path):
            pix = QPixmap(splash_path)
            if not pix.isNull():
                splash = QSplashScreen(pix)
                splash.setWindowFlag(Qt.FramelessWindowHint)
                splash.setEnabled(False)
                splash.show()
                app.processEvents()
    except Exception:
        splash = None

    # 动态监听屏幕DPI/切屏变化，实时更新字体与样式
    def _apply_dynamic_scaling(_sf: float):
        try:
            # 更新应用字体
            font = dpi_scaler.create_scaled_font("Microsoft YaHei UI", 12)
            font.setStyleHint(QFont.SansSerif)
            app.setFont(font)
            # 重应用样式表
            app.setStyleSheet(dpi_scaler.get_scaled_stylesheet(base_stylesheet))
            # 可选：重算主窗口布局
            try:
                main_window.adjustSize()
            except Exception:
                pass
            # 静默
        except Exception as _e:
            pass

    try:
        dpi_scaler.attach_dynamic_listeners(app, _apply_dynamic_scaling)
    except Exception:
        pass

    # 显示主窗口并关闭闪屏
    main_window.show()
    if splash is not None:
        try:
            splash.finish(main_window)
        except Exception:
            try:
                splash.close()
            except Exception:
                pass
    
    # 运行应用程序
    sys.exit(app.exec_())

if __name__ == "__main__":
    main() 