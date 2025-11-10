# -*- coding: utf-8 -*-
"""
主窗口界面
"""

import sys
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, 
                             QTabWidget, QMenuBar, QMenu, QAction, QStatusBar,
                             QMessageBox, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QIcon, QFont, QPixmap

# 添加Control_SDK目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
control_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "Control_SDK")
sys.path.insert(0, control_sdk_dir)

from widgets.single_motor_widget import SingleMotorWidget
from widgets.multi_motor_widget import MultiMotorWidget
from widgets.connection_widget import ConnectionWidget
from widgets.hand_eye_calibration_widget import HandEyeCalibrationWidget
from widgets.camera_calibration_widget import CameraCalibrationWidget
from widgets.motor_settings_dialog import MotorSettingsDialog
from widgets.dh_parameter_manager import DHSettingsDialog
from widgets.teach_pendant_widget import TeachPendantWidget
from widgets.claw_connection_widget import ClawConnectionWidget
from widgets.vision_grasp_widget import VisionGraspWidget
from widgets.io_control_widget import IOControlWidget

class MainWindow(QMainWindow):
    """主窗口类"""
    
    def __init__(self):
        super().__init__()
        self.hand_eye_calibration_widget = None  # 手眼标定窗口
        self.camera_calibration_widget = None   # 相机标定窗口
        self.motor_settings_dialog = None       # 电机设置对话框
        self.dh_settings_dialog = None          # 机械臂配置设置对话框
        # 注意：teach_pendant_widget现在是标签页，不再是独立窗口变量
        self.init_ui()
        self.setup_menu()
        self.setup_status_bar()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("Horizon 具身智能系统 v1.0.0")
        # 调整窗口尺寸以适应1980*1080分辨率
        self.setGeometry(50, 50, 1600, 1000)  # 增大初始尺寸
        self.setMinimumSize(1400, 900)  # 增大最小尺寸
        
        # 设置窗口图标
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
        
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # 创建中央窗口部件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # 创建主布局 - 增大间距
        main_layout = QVBoxLayout(central_widget)
        main_layout.setContentsMargins(12, 12, 12, 12)  # 增大边距
        main_layout.setSpacing(12)  # 增大间距
        
        # 创建连接控制面板
        self.connection_widget = ConnectionWidget()
        # main_layout.addWidget(self.connection_widget)  # 隐藏连接控制面板显示，只通过菜单操作
        
        # 创建标签页控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.North)
        self.tab_widget.setMovable(True)
        self.tab_widget.setTabsClosable(False)
        
        # 创建单电机和多电机控制窗口（但不添加到标签页）
        self.single_motor_widget = SingleMotorWidget()
        self.multi_motor_widget = MultiMotorWidget()
        
        # 创建机械臂控制标签页
        from widgets.digital_twin_widget import DigitalTwinWidget
        self.digital_twin_widget = DigitalTwinWidget()
        self.tab_widget.addTab(self.digital_twin_widget, "🦾 机械臂")
        
        # 创建示教器标签页
        from widgets.teach_pendant_widget import TeachPendantWidget
        self.teach_pendant_widget = TeachPendantWidget()
        self.tab_widget.addTab(self.teach_pendant_widget, "🎮 示教器")
        
        # 创建IO控制标签页
        self.io_control_widget = IOControlWidget()
        self.tab_widget.addTab(self.io_control_widget, "🔌 IO控制")
        
        # 创建视觉抓取标签页
        self.vision_grasp_widget = VisionGraspWidget()
        self.tab_widget.addTab(self.vision_grasp_widget, "👁️ 视觉抓取")
        
        # 创建具身智能标签页
        from widgets.embodied_intelligence_widget import EmbodiedIntelligenceWidget
        self.embodied_intelligence_widget = EmbodiedIntelligenceWidget()
        self.tab_widget.addTab(self.embodied_intelligence_widget, "🧠 具身智能")
        

        main_layout.addWidget(self.tab_widget)
        
        # 连接信号
        self.connection_widget.connection_changed.connect(self.on_connection_changed)
        
        # 夹爪窗口
        self.claw_connection_widget = None
        
    def setup_menu(self):
        """设置菜单栏"""
        menubar = self.menuBar()
        
        
        # 连接菜单
        connection_menu = menubar.addMenu('连接(&C)')
        
        # 连接电机动作
        connect_action = QAction('连接电机(&E)', self)
        connect_action.setShortcut('Ctrl+E')
        connect_action.setStatusTip('连接电机')
        connect_action.triggered.connect(self.connection_widget.show_connection_dialog)
        connection_menu.addAction(connect_action)
        
        # 断开连接动作
        disconnect_action = QAction('断开连接(&D)', self)
        disconnect_action.setShortcut('Ctrl+D')
        disconnect_action.setStatusTip('断开所有电机连接')
        disconnect_action.triggered.connect(lambda: self.connection_widget.disconnect_all(confirm=True))
        connection_menu.addAction(disconnect_action)
        
        # 连接夹爪
        connect_claw_action = QAction('连接夹爪(&G)', self)
        connect_claw_action.setShortcut('Ctrl+G')
        connect_claw_action.setStatusTip('连接并控制夹爪')
        connect_claw_action.triggered.connect(self.show_claw_connection)
        connection_menu.addAction(connect_claw_action)
        
        # 电机控制菜单
        motor_control_menu = menubar.addMenu('电机控制(&M)')
        
        # 单电机控制动作
        single_motor_action = QAction('单电机控制(&S)', self)
        single_motor_action.setShortcut('Ctrl+1')
        single_motor_action.setStatusTip('打开单电机控制窗口')
        single_motor_action.triggered.connect(self.show_single_motor_control)
        motor_control_menu.addAction(single_motor_action)
        
        # 多电机控制动作
        multi_motor_action = QAction('多电机控制(&M)', self)
        multi_motor_action.setShortcut('Ctrl+2')
        multi_motor_action.setStatusTip('打开多电机控制窗口')
        multi_motor_action.triggered.connect(self.show_multi_motor_control)
        motor_control_menu.addAction(multi_motor_action)
        
        # 工具菜单
        tools_menu = menubar.addMenu('工具(&T)')
        
        # 添加分隔符
        # tools_menu.addSeparator()  # 移除分隔符，因为示教器已移除
        
        # 手眼标定动作
        hand_eye_calibration_action = QAction('手眼标定(&H)', self)
        hand_eye_calibration_action.setStatusTip('打开手眼标定工具')
        hand_eye_calibration_action.triggered.connect(self.show_hand_eye_calibration)
        tools_menu.addAction(hand_eye_calibration_action)
        
        # 相机标定动作
        camera_calibration_action = QAction('相机标定(&C)', self)
        camera_calibration_action.setStatusTip('打开相机标定工具')
        camera_calibration_action.triggered.connect(self.show_camera_calibration)
        tools_menu.addAction(camera_calibration_action)
        
        # 电机参数设置动作
        motor_settings_action = QAction('电机参数设置(&M)', self)
        motor_settings_action.setStatusTip('设置电机减速比和方向参数')
        motor_settings_action.triggered.connect(self.show_motor_settings)
        tools_menu.addAction(motor_settings_action)
        
        # 机械臂配置设置动作
        dh_settings_action = QAction('机械臂配置设置(&A)', self)
        dh_settings_action.setStatusTip('设置机械臂MDH参数、关节角度偏转和运动限制')
        dh_settings_action.triggered.connect(self.show_dh_settings)
        tools_menu.addAction(dh_settings_action)
        
        # 添加分隔符
        tools_menu.addSeparator()
        
        # 帮助菜单
        help_menu = menubar.addMenu('帮助(&H)')
        
        # 关于动作
        about_action = QAction('关于(&A)', self)
        about_action.setStatusTip('关于本程序')
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
        
    def setup_status_bar(self):
        """设置状态栏"""
        self.status_bar = self.statusBar()
        self.status_bar.showMessage('就绪 | 🛑 按空格键执行全局紧急停止')
        
    def on_connection_changed(self, motors_info):
        """连接状态改变时的处理"""
        if motors_info:
            # 更新单电机、多电机、机械臂控制、示教器、具身智能控件的连接信息
            self.single_motor_widget.update_motors(motors_info)
            self.multi_motor_widget.update_motors(motors_info)
            self.digital_twin_widget.update_motors(motors_info)
            self.teach_pendant_widget.update_motors(motors_info)
            self.embodied_intelligence_widget.update_motors(motors_info)
            self.vision_grasp_widget.update_motors(motors_info)
            self.io_control_widget.update_motors(motors_info)
            
            # 更新手眼标定窗口的连接信息
            if self.hand_eye_calibration_widget:
                self.hand_eye_calibration_widget.update_motors(motors_info)
            
            # 注意：不再需要更新示教器窗口，因为现在是标签页
            
            motor_count = len(motors_info)
            self.status_bar.showMessage(f'已连接 {motor_count} 个电机 | 🛑 按空格键执行全局紧急停止')
        else:
            # 清空连接信息
            self.single_motor_widget.clear_motors()
            self.multi_motor_widget.clear_motors()
            self.digital_twin_widget.clear_motors()
            self.teach_pendant_widget.clear_motors()
            self.embodied_intelligence_widget.clear_motors()
            self.vision_grasp_widget.clear_motors()
            self.io_control_widget.clear_motors()
            
            # 清空手眼标定窗口的连接信息
            if self.hand_eye_calibration_widget:
                self.hand_eye_calibration_widget.clear_motors()
            
            # 注意：不再需要清空示教器窗口，因为现在是标签页
                
            self.status_bar.showMessage('未连接电机 | 🛑 按空格键执行全局紧急停止')
    
    def show_claw_connection(self):
        """显示夹爪连接窗口"""
        if self.claw_connection_widget is None:
            self.claw_connection_widget = ClawConnectionWidget()
            # 连接信号：当夹爪控制器状态改变时，更新相关控件
            self.claw_connection_widget.claw_controller_changed.connect(
                self.vision_grasp_widget.update_claw_controller
            )
            # 同时连接具身智能控件
            self.claw_connection_widget.claw_controller_changed.connect(
                self.embodied_intelligence_widget.update_claw_controller
            )
            # 连接IO控制控件
            self.claw_connection_widget.claw_controller_changed.connect(
                self.io_control_widget.update_claw_controller
            )
        self.claw_connection_widget.setGeometry(200, 120, 500, 200)
        self.claw_connection_widget.show()
        self.claw_connection_widget.raise_()
        self.claw_connection_widget.activateWindow()

    def show_single_motor_control(self):
        """显示单电机控制窗口"""
        # 设置窗口属性
        self.single_motor_widget.setWindowTitle("单电机控制")
        self.single_motor_widget.setGeometry(100, 100, 1200, 800)
        
        # 每次显示时都检查并更新电机连接状态
        if hasattr(self.connection_widget, 'motors') and self.connection_widget.motors:
            self.single_motor_widget.update_motors(self.connection_widget.motors)
        
        # 显示窗口
        self.single_motor_widget.show()
        self.single_motor_widget.raise_()
        self.single_motor_widget.activateWindow()
        
        print("✅ 单电机控制窗口已打开")
    
    def show_multi_motor_control(self):
        """显示多电机控制窗口"""
        # 设置窗口属性
        self.multi_motor_widget.setWindowTitle("多电机控制")
        self.multi_motor_widget.setGeometry(150, 150, 1400, 900)
        
        # 每次显示时都检查并更新电机连接状态
        if hasattr(self.connection_widget, 'motors') and self.connection_widget.motors:
            self.multi_motor_widget.update_motors(self.connection_widget.motors)
        
        # 显示窗口
        self.multi_motor_widget.show()
        self.multi_motor_widget.raise_()
        self.multi_motor_widget.activateWindow()
        
        print("✅ 多电机控制窗口已打开")
    
    # show_teach_pendant方法已移除，因为示教器现在是主界面标签页
    
    def show_hand_eye_calibration(self):
        """显示手眼标定工具"""
        if self.hand_eye_calibration_widget is None:
            self.hand_eye_calibration_widget = HandEyeCalibrationWidget()
        
        # 每次显示时都检查并更新电机连接状态
        if hasattr(self.connection_widget, 'motors') and self.connection_widget.motors:
            self.hand_eye_calibration_widget.update_motors(self.connection_widget.motors)
        
        self.hand_eye_calibration_widget.show()
        self.hand_eye_calibration_widget.raise_()
        self.hand_eye_calibration_widget.activateWindow()
    
    def show_camera_calibration(self):
        """显示相机标定工具"""
        if self.camera_calibration_widget is None:
            self.camera_calibration_widget = CameraCalibrationWidget()
        
        self.camera_calibration_widget.show()
        self.camera_calibration_widget.raise_()
        self.camera_calibration_widget.activateWindow()
    
    def show_motor_settings(self):
        """显示电机参数设置对话框"""
        if self.motor_settings_dialog is None:
            self.motor_settings_dialog = MotorSettingsDialog(self)
            # 连接配置变化信号
            self.motor_settings_dialog.config_changed.connect(self.on_motor_config_changed)
        
        # 每次显示时重新加载当前配置
        self.motor_settings_dialog.load_current_config()
        self.motor_settings_dialog.show()
        self.motor_settings_dialog.raise_()
        self.motor_settings_dialog.activateWindow()
    
    def show_dh_settings(self):
        """显示机械臂配置设置对话框"""
        if self.dh_settings_dialog is None:
            self.dh_settings_dialog = DHSettingsDialog(self)
            # 连接配置变化信号
            self.dh_settings_dialog.config_changed.connect(self.on_dh_config_changed)
        
        # 每次显示时重新加载当前配置
        self.dh_settings_dialog.load_current_config()
        self.dh_settings_dialog.show()
        self.dh_settings_dialog.raise_()
        self.dh_settings_dialog.activateWindow()
    
    def on_motor_config_changed(self):
        """当电机配置发生变化时的处理"""
        # 通知所有相关控件配置已更改，让它们重新加载配置
        try:
            # 更新具身智能控件
            if hasattr(self, 'embodied_intelligence_widget'):
                self.embodied_intelligence_widget.reload_motor_config()
            
            # 更新机械臂控制控件  
            if hasattr(self, 'digital_twin_widget'):
                self.digital_twin_widget.reload_motor_config()
            
            # 更新示教器控件
            if hasattr(self, 'teach_pendant_widget'):
                self.teach_pendant_widget.reload_motor_config()
            
            # 更新手眼标定控件
            if self.hand_eye_calibration_widget:
                self.hand_eye_calibration_widget.reload_motor_config()
            
            # 更新视觉抓取控件
            if hasattr(self, 'vision_grasp_widget'):
                self.vision_grasp_widget.reload_motor_config()
            
            # 更新IO控制控件
            if hasattr(self, 'io_control_widget'):
                self.io_control_widget.reload_motor_config()
            
            print("✅ 电机配置已更新到所有相关控件")
            
        except Exception as e:
            print(f"⚠ 更新控件配置时发生错误: {e}")
    
    def on_dh_config_changed(self):
        """当机械臂配置发生变化时的处理"""
        # 通知所有相关控件机械臂配置已更改，让它们重新加载配置参数
        try:
            # 首先重新加载运动学工厂的配置
            from Main_UI.utils.kinematics_factory import KinematicsFactory
            KinematicsFactory.reload_config()
            
            # 更新具身智能控件
            if hasattr(self, 'embodied_intelligence_widget'):
                self.embodied_intelligence_widget.reload_dh_config()
            
            # 更新机械臂控制控件  
            if hasattr(self, 'digital_twin_widget'):
                self.digital_twin_widget.reload_dh_config()
            
            # 更新示教器控件
            if hasattr(self, 'teach_pendant_widget'):
                self.teach_pendant_widget.reload_dh_config()
            
            # 更新手眼标定控件
            if self.hand_eye_calibration_widget:
                self.hand_eye_calibration_widget.reload_dh_config()
            
            # 更新视觉抓取控件
            if hasattr(self, 'vision_grasp_widget'):
                self.vision_grasp_widget.reload_dh_config()
            
            # 更新IO控制控件
            if hasattr(self, 'io_control_widget'):
                self.io_control_widget.reload_dh_config()
            
            
        except Exception as e:
            print(f"⚠ 更新控件DH参数配置时发生错误: {e}")
    
    def show_about(self):
        """显示关于对话框"""
        about_text = """
        <div style="text-align: center; font-family: 'Microsoft YaHei UI', sans-serif;">
        <h2 style="color: #2c3e50; margin-bottom: 5px;">Horizon 具身智能系统</h2>
        <p style="color: #7f8c8d; font-size: 11px; margin: 5px 0;">Embodied Intelligence & Digital Twin Platform</p>
        <p style="background: linear-gradient(45deg, #3498db, #9b59b6); -webkit-background-clip: text; 
           color: transparent; font-weight: bold; font-size: 13px;">版本 v1.0.0 | 虚实孪生 AI 原生设计</p>
        </div>
        
        <hr style="border: none; height: 1px; background: linear-gradient(to right, transparent, #bdc3c7, transparent);">
        
        <h4 style="color: #2980b9; margin-bottom: 8px;">🎯 系统特色</h4>
        <p style="margin: 8px 0; font-size: 12px; line-height: 1.4; color: #34495e;">
        • <b>AI原生架构</b>：深度集成自然语言交互，支持语音交互控制机械臂<br>
        • <b>虚实孪生</b>：MuJoCo物理仿真与真实硬件完美同步<br>
        • <b>分层决策模型</b>：高层任务规划→中层动作解析→底层精确执行<br>
        • <b>外部信号集成</b>：ESP32 IO控制，支持外部设备触发自动化作业<br>
        • <b>工业级可靠</b>：专业电机驱动，多重安全防护机制
        </p>
        
        <h4 style="color: #27ae60; margin: 12px 0 8px 0;">⚡ 核心功能</h4>
        <table style="width: 100%; font-size: 11px; border-collapse: collapse;">
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>🧠 具身智能</b></td><td style="padding: 2px; color: #7f8c8d;">自然语言控制 | 多模态AI决策</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>🦾 虚实孪生</b></td><td style="padding: 2px; color: #7f8c8d;">6DOF精确控制 | 实时仿真联动</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>🎮 智能示教</b></td><td style="padding: 2px; color: #7f8c8d;">三坐标系控制 | 多样插补算法</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>👁️ 视觉抓取</b></td><td style="padding: 2px; color: #7f8c8d;">目标检测定位 | 手眼协调标定</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>🔌 IO控制</b></td><td style="padding: 2px; color: #7f8c8d;">ESP32交互 | 外部信号触发</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>⚙️ 电机系统</b></td><td style="padding: 2px; color: #7f8c8d;">单/多电机控制 | FOC闭环控制</td></tr>
        <tr><td style="padding: 2px 8px; color: #2c3e50;"><b>📊 实时监控</b></td><td style="padding: 2px; color: #7f8c8d;">参数读取调试 | 状态可视化</td></tr>
        </table>
        
        <h4 style="color: #e74c3c; margin: 12px 0 8px 0;">🛡️ 安全保障</h4>
        <div style="background: #fff5f5; border-left: 4px solid #e74c3c; padding: 8px; margin: 8px 0; border-radius: 4px;">
        <p style="margin: 0; font-size: 11px; color: #2c3e50;">
        <b>🛑 全局紧急停止</b>：任意界面按<b>空格键</b>立即停止所有运动<br>
        <b>🔍 智能检测</b>：自动识别输入状态，避免误触发<br>
        <b>📊 状态反馈</b>：实时显示每个电机的安全状态
        </p>
        </div>
        
        <hr style="border: none; height: 1px; background: linear-gradient(to right, transparent, #bdc3c7, transparent); margin: 15px 0 10px 0;">
        
        <div style="text-align: center;">
        <p style="margin: 5px 0; font-size: 11px;">
        📘 <a href="https://ruxue-one.github.io/Horizon_Arm_Docs/user_guide/" 
              style="color: #3498db; text-decoration: none;">用户指南</a> 
        </p>
        <p style="color: #95a5a6; font-size: 10px; margin: 5px 0;">
        © 2025 Horizon 人工智能科技工作室 | 让机器人理解世界
        </p>
        </div>
        """
        
        # 创建自定义消息框以获得更好的显示效果
        msg_box = QMessageBox(self)
        msg_box.setWindowTitle('关于 Horizon Arm V1.0.0')
        msg_box.setText(about_text)
        
        # 设置自定义图标
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
        if os.path.exists(icon_path):
            pixmap = QPixmap(icon_path)
            # 缩放图标到合适大小
            scaled_pixmap = pixmap.scaled(64, 64, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            msg_box.setIconPixmap(scaled_pixmap)
        else:
            msg_box.setIcon(QMessageBox.Information)
        
        msg_box.setStandardButtons(QMessageBox.Ok)
        
        # 设置消息框尺寸
        msg_box.setFixedSize(520, 580)
        
        # 应用样式
        msg_box.setStyleSheet("""
            QMessageBox {
                background-color: #ffffff;
            }
            QMessageBox QLabel {
                color: #2c3e50;
                font-size: 12px;
                padding: 10px;
            }
        """)
        
        msg_box.exec_()
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        # 关闭单电机控制窗口
        if self.single_motor_widget:
            self.single_motor_widget.close()
        # 关闭多电机控制窗口
        if self.multi_motor_widget:
            self.multi_motor_widget.close()
        # 关闭手眼标定窗口
        if self.hand_eye_calibration_widget:
            self.hand_eye_calibration_widget.close()
        # 关闭相机标定窗口
        if self.camera_calibration_widget:
            self.camera_calibration_widget.close()
        # 关闭夹爪连接窗口
        if self.claw_connection_widget:
            self.claw_connection_widget.close()
        # 关闭机械臂配置设置对话框
        if self.dh_settings_dialog:
            self.dh_settings_dialog.close()
        
        # 清理标签页中的控件资源（这些控件不会自动触发closeEvent）
        try:
            # 清理机械臂控件
            if hasattr(self, 'digital_twin_widget') and self.digital_twin_widget:
                if hasattr(self.digital_twin_widget, 'closeEvent'):
                    # 手动触发closeEvent来清理资源
                    from PyQt5.QtGui import QCloseEvent
                    close_event = QCloseEvent()
                    self.digital_twin_widget.closeEvent(close_event)
            
            # 清理示教器控件
            if hasattr(self, 'teach_pendant_widget') and self.teach_pendant_widget:
                if hasattr(self.teach_pendant_widget, 'closeEvent'):
                    from PyQt5.QtGui import QCloseEvent
                    close_event = QCloseEvent()
                    self.teach_pendant_widget.closeEvent(close_event)
            
            # 清理视觉抓取控件
            if hasattr(self, 'vision_grasp_widget') and self.vision_grasp_widget:
                if hasattr(self.vision_grasp_widget, 'closeEvent'):
                    from PyQt5.QtGui import QCloseEvent
                    close_event = QCloseEvent()
                    self.vision_grasp_widget.closeEvent(close_event)
            
            # 清理具身智能控件
            if hasattr(self, 'embodied_intelligence_widget') and self.embodied_intelligence_widget:
                if hasattr(self.embodied_intelligence_widget, 'closeEvent'):
                    from PyQt5.QtGui import QCloseEvent
                    close_event = QCloseEvent()
                    self.embodied_intelligence_widget.closeEvent(close_event)
            
            # 清理IO控制控件
            if hasattr(self, 'io_control_widget') and self.io_control_widget:
                if hasattr(self.io_control_widget, 'closeEvent'):
                    from PyQt5.QtGui import QCloseEvent
                    close_event = QCloseEvent()
                    self.io_control_widget.closeEvent(close_event)
                    
        except Exception as e:
            print(f"⚠️ 清理标签页控件资源时出错: {e}")
        
        # 注意：不再需要关闭示教器窗口，因为现在是标签页
            
        reply = QMessageBox.question(self, '确认退出', 
                                   '确定要退出具身智能系统吗？\n这将断开所有电机连接。',
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            try:
                # 先清理相机资源，避免资源泄漏
                print("🔄 正在清理系统资源...")
                
                # 清理视觉抓取控件的相机资源
                if hasattr(self, 'vision_grasp_widget') and self.vision_grasp_widget:
                    try:
                        if self.vision_grasp_widget.camera_running:
                            self.vision_grasp_widget.stop_camera()
                    except Exception as e:
                        print(f"⚠️ 停止视觉抓取相机时出错: {e}")
                
                # 清理具身智能控件的相机资源
                if hasattr(self, 'embodied_intelligence_widget') and self.embodied_intelligence_widget:
                    try:
                        if hasattr(self.embodied_intelligence_widget, 'camera_enabled') and self.embodied_intelligence_widget.camera_enabled:
                            self.embodied_intelligence_widget.stop_camera()
                    except Exception as e:
                        print(f"⚠️ 停止具身智能相机时出错: {e}")
                
                # 清理相机标定控件的相机资源
                if self.camera_calibration_widget:
                    try:
                        if hasattr(self.camera_calibration_widget, 'stop_camera'):
                            self.camera_calibration_widget.stop_camera()
                    except Exception as e:
                        print(f"⚠️ 停止相机标定相机时出错: {e}")
                
                # 清理手眼标定控件的相机资源
                if self.hand_eye_calibration_widget:
                    try:
                        if hasattr(self.hand_eye_calibration_widget, 'stop_camera'):
                            self.hand_eye_calibration_widget.stop_camera()
                    except Exception as e:
                        print(f"⚠️ 停止手眼标定相机时出错: {e}")
                
                
                # 静默断开电机连接，避免重复确认
                self.connection_widget.disconnect_all(confirm=False)
                
                print("✅ 系统资源清理完成，程序即将退出")
                
            except Exception as e:
                print(f"⚠️ 清理系统资源时发生错误: {e}")
            finally:
                event.accept()
        else:
            event.ignore() 