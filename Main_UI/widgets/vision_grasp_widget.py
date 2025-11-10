# -*- coding: utf-8 -*-
"""
视觉抓取控件
实现右相机显示、深度图显示、鼠标点击坐标转换和机械臂抓取功能
集成双目深度估计，提供精确的深度信息
"""

import sys
import os
import cv2
import numpy as np
import json
import threading
import time
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QScrollArea, QSplitter, QFrame, QHeaderView,
                             QComboBox, QDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QImage
import numpy as np

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 导入配置管理器
try:
    from core.config_manager import config_manager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError as e:
    CONFIG_MANAGER_AVAILABLE = False
    print(f"❌ 配置管理器加载失败: {e}")

# 导入视觉检测模块
try:
    from core.arm_core.vision_detection import VisionDetector
    VISION_DETECTION_AVAILABLE = True

except ImportError as e:
    VISION_DETECTION_AVAILABLE = False
    print(f"❌ 视觉检测模块加载失败: {e}")

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

from .motor_config_manager import motor_config_manager

# 添加运动学模块导入
try:
    from Main_UI.utils.kinematics_factory import create_configured_kinematics
    KINEMATICS_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入运动学工厂模块: {e}")
    KINEMATICS_AVAILABLE = False

# 添加深度估计模块导入
try:
    from core.arm_core.Depth_Estimation import StereoDepthEstimator
    DEPTH_ESTIMATION_AVAILABLE = True
except ImportError as e:
    print(f"警告: 无法导入深度估计模块: {e}")
    DEPTH_ESTIMATION_AVAILABLE = False

class CameraDisplayLabel(QLabel):
    """自定义相机显示标签，支持鼠标点击获取坐标"""
    
    clicked = pyqtSignal(int, int)  # 发送点击坐标信号
    
    def __init__(self):
        super().__init__()
        # 🔥 关键设置：固定显示尺寸为640x480，确保抓取精度
        self.setFixedSize(640, 480)
        self.setMinimumSize(640, 480)
        self.setMaximumSize(640, 480)
        self.setStyleSheet("border: 2px solid #27ae60; background-color: #f0f8f0;")
        self.setAlignment(Qt.AlignCenter)
        self.setText("右相机（原始图像）\n点击获取目标坐标")
        self.setScaledContents(True)
        self.camera_active = False  # 添加相机状态标志
        
    def set_camera_active(self, active):
        """设置相机激活状态"""
        self.camera_active = active
        if active:
            self.setStyleSheet("border: 2px solid #27ae60; background-color: #f0f8f0;")
            self.setCursor(Qt.CrossCursor)  # 十字光标表示可点击
        else:
            self.setStyleSheet("border: 2px solid #95a5a6; background-color: #ecf0f1;")
            self.setCursor(Qt.ArrowCursor)  # 普通光标
        
    def mousePressEvent(self, event):
        """鼠标点击事件"""
        if event.button() == Qt.LeftButton:
            if self.camera_active:
                # 获取点击坐标
                x = event.x()
                y = event.y()
                self.clicked.emit(x, y)
            else:
                # 相机未启动时的提示
                from PyQt5.QtWidgets import QToolTip
                QToolTip.showText(event.globalPos(), "请先启动相机才能点击获取坐标", self)
        super().mousePressEvent(event)


class GraspParametersDialog(QDialog):
    """抓取参数设置对话框"""
    
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        
        self.setWindowTitle("🤖 抓取参数设置")
        self.setFixedSize(650, 730)
        self.setModal(True)
        
        # 初始化参数
        self.init_parameters()
        
        # 初始化UI
        self.init_ui()
        
        # 加载父组件的参数
        if parent_widget:
            self.load_parameters_from_parent()
    
    def init_parameters(self):
        """初始化参数默认值"""
        # 如果有父组件，从父组件获取已加载的参数，否则使用默认值
        if self.parent_widget:
            # 姿态参数
            self.euler_yaw = getattr(self.parent_widget, 'euler_yaw', 0.0)
            self.euler_pitch = getattr(self.parent_widget, 'euler_pitch', 0.0)
            self.euler_roll = getattr(self.parent_widget, 'euler_roll', 180.0)
            # 姿态模式
            self.use_dynamic_pose = getattr(self.parent_widget, 'use_dynamic_pose', False)
            
            # 运动参数
            self.motion_speed = getattr(self.parent_widget, 'motion_speed', 100)
            self.motion_acceleration = getattr(self.parent_widget, 'motion_acceleration', 200)
            
            # TCP修正参数（毫米）
            self.tcp_offset_x = getattr(self.parent_widget, 'tcp_offset_x', 0.0)
            self.tcp_offset_y = getattr(self.parent_widget, 'tcp_offset_y', 0.0)
            self.tcp_offset_z = getattr(self.parent_widget, 'tcp_offset_z', 0.0)
            
            # 夹爪角度参数
            self.claw_open_angle = getattr(self.parent_widget, 'claw_open_angle', 0.0)
            self.claw_close_angle = getattr(self.parent_widget, 'claw_close_angle', 90.0)
        else:
            # 默认参数
            self.euler_yaw = 0.0
            self.euler_pitch = 0.0
            self.euler_roll = 180.0
            self.use_dynamic_pose = False
            
            self.motion_speed = 100
            self.motion_acceleration = 200
            
            self.tcp_offset_x = 0.0
            self.tcp_offset_y = 0.0
            self.tcp_offset_z = 0.0
            
            self.claw_open_angle = 0.0   # 张开角度（默认0度）
            self.claw_close_angle = 90.0 # 闭合角度（默认90度）
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 使用滚动区域以防内容过多
        scroll_area = QScrollArea()
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(10)
        
        # 姿态设置组
        self.create_pose_settings_group(scroll_layout)
        
        # 运动参数设置组
        self.create_motion_settings_group(scroll_layout)
        
        # TCP修正设置组
        self.create_tcp_correction_group(scroll_layout)
        
        # 夹爪设置组
        self.create_claw_settings_group(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # 按钮组
        self.create_button_group(layout)
    
    def create_pose_settings_group(self, parent_layout):
        """创建姿态设置组"""
        group = QGroupBox("末端姿态设置 (欧拉角)")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加姿态模式选择
        mode_group = QGroupBox("姿态控制模式")
        mode_layout = QHBoxLayout(mode_group)
        mode_layout.setContentsMargins(15, 15, 15, 15)
        mode_layout.setSpacing(15)
        
        mode_layout.addWidget(QLabel("控制模式:"))
        
        self.pose_mode_combo = QComboBox()
        self.pose_mode_combo.addItems(["固定姿态", "动态姿态 (跟随目标)"])
        self.pose_mode_combo.setCurrentIndex(0)  # 默认选择固定姿态
        self.pose_mode_combo.setMinimumWidth(180)
        self.pose_mode_combo.setToolTip("固定姿态: 使用设定的固定欧拉角\n动态姿态: Yaw角跟随目标旋转，Pitch/Roll使用设定值")
        self.pose_mode_combo.currentIndexChanged.connect(self.on_pose_mode_changed)
        mode_layout.addWidget(self.pose_mode_combo)
        
        mode_layout.addStretch()
        
        main_layout.addWidget(mode_group)
        
        # 欧拉角设置区域
        angles_layout = QHBoxLayout()
        angles_layout.setSpacing(15)
        
        # Yaw角设置
        yaw_layout = QVBoxLayout()
        self.yaw_label = QLabel("Yaw角:")
        yaw_layout.addWidget(self.yaw_label)
        self.yaw_spin = QDoubleSpinBox()
        self.yaw_spin.setRange(-180, 180)
        self.yaw_spin.setValue(self.euler_yaw)
        self.yaw_spin.setSuffix("°")
        self.yaw_spin.setMaximumWidth(120)
        self.yaw_spin.setToolTip("绕Z轴旋转角度（航向角）")
        yaw_layout.addWidget(self.yaw_spin)
        angles_layout.addLayout(yaw_layout)
        
        # Pitch角设置
        pitch_layout = QVBoxLayout()
        pitch_layout.addWidget(QLabel("Pitch角:"))
        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(-180, 180)
        self.pitch_spin.setValue(self.euler_pitch)
        self.pitch_spin.setSuffix("°")
        self.pitch_spin.setMaximumWidth(120)
        self.pitch_spin.setToolTip("绕Y轴旋转角度（俯仰角）")
        pitch_layout.addWidget(self.pitch_spin)
        angles_layout.addLayout(pitch_layout)
        
        # Roll角设置
        roll_layout = QVBoxLayout()
        roll_layout.addWidget(QLabel("Roll角:"))
        self.roll_spin = QDoubleSpinBox()
        self.roll_spin.setRange(-180, 180)
        self.roll_spin.setValue(self.euler_roll)
        self.roll_spin.setSuffix("°")
        self.roll_spin.setMaximumWidth(120)
        self.roll_spin.setToolTip("绕X轴旋转角度（翻滚角）")
        roll_layout.addWidget(self.roll_spin)
        angles_layout.addLayout(roll_layout)
        
        # 将角度设置布局添加到主布局
        main_layout.addLayout(angles_layout)
        
        parent_layout.addWidget(group)
        
        # 初始化时触发一次模式切换处理，设置正确的Yaw角状态
        self.on_pose_mode_changed()
        
    def on_pose_mode_changed(self):
        """姿态模式切换处理"""
        is_dynamic = self.pose_mode_combo.currentIndex() == 1  # 1表示动态姿态
        
        # 根据模式启用/禁用Yaw角输入框
        self.yaw_spin.setEnabled(not is_dynamic)
        
        # 更新Yaw角标签和样式
        if is_dynamic:
            self.yaw_label.setText("Yaw角: 🎯 (自动)")
            self.yaw_label.setStyleSheet("color: #007ACC; font-weight: bold;")
            self.yaw_spin.setStyleSheet("color: #888888; background-color: #f5f5f5;")
            self.yaw_spin.setToolTip("动态模式下Yaw角由视觉识别自动控制，无需手动设置")
        else:
            self.yaw_label.setText("Yaw角:")
            self.yaw_label.setStyleSheet("")
            self.yaw_spin.setStyleSheet("")
            self.yaw_spin.setToolTip("绕Z轴旋转角度（航向角）")
        
    
    def create_motion_settings_group(self, parent_layout):
        """创建运动参数设置组"""
        group = QGroupBox("运动控制参数")
        layout = QHBoxLayout(group)  # 改为横向布局
        layout.setSpacing(20)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # 运动速度设置
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("运动速度:"))
        self.motion_speed_spin = QSpinBox()
        self.motion_speed_spin.setRange(1, 1000)
        self.motion_speed_spin.setValue(self.motion_speed)
        self.motion_speed_spin.setSuffix(" RPM")
        self.motion_speed_spin.setMaximumWidth(150)
        self.motion_speed_spin.setToolTip("电机运动速度（转每分钟）")
        speed_layout.addWidget(self.motion_speed_spin)
        layout.addLayout(speed_layout)
        
        # 加速度设置
        acc_layout = QVBoxLayout()
        acc_layout.addWidget(QLabel("加速度:"))
        self.motion_acc_spin = QSpinBox()
        self.motion_acc_spin.setRange(1, 5000)
        self.motion_acc_spin.setValue(self.motion_acceleration)
        self.motion_acc_spin.setSuffix(" RPM/s")
        self.motion_acc_spin.setMaximumWidth(150)
        self.motion_acc_spin.setToolTip("电机加速度（转每分钟每秒）")
        acc_layout.addWidget(self.motion_acc_spin)
        layout.addLayout(acc_layout)
        
        parent_layout.addWidget(group)
    
    def create_tcp_correction_group(self, parent_layout):
        """创建TCP修正设置组"""
        group = QGroupBox("TCP修正 (工具中心点偏移)")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加说明标签
        info_label = QLabel("💡 TCP偏移量（在基底坐标系中应用，毫米）:")
        info_label.setStyleSheet("color: #666; font-style: italic; font-size: 12px;")
        main_layout.addWidget(info_label)
        
        # 横向布局的TCP偏移参数
        tcp_layout = QHBoxLayout()
        tcp_layout.setSpacing(15)
        
        # TCP X偏移
        x_layout = QVBoxLayout()
        x_layout.addWidget(QLabel("X偏移:"))
        self.tcp_offset_x_spin = QDoubleSpinBox()
        self.tcp_offset_x_spin.setRange(-500.0, 500.0)
        self.tcp_offset_x_spin.setValue(self.tcp_offset_x)
        self.tcp_offset_x_spin.setDecimals(2)
        self.tcp_offset_x_spin.setSuffix(" mm")
        self.tcp_offset_x_spin.setToolTip("在基底坐标系X轴方向的TCP偏移量")
        self.tcp_offset_x_spin.setMaximumWidth(120)
        x_layout.addWidget(self.tcp_offset_x_spin)
        tcp_layout.addLayout(x_layout)
        
        # TCP Y偏移
        y_layout = QVBoxLayout()
        y_layout.addWidget(QLabel("Y偏移:"))
        self.tcp_offset_y_spin = QDoubleSpinBox()
        self.tcp_offset_y_spin.setRange(-500.0, 500.0)
        self.tcp_offset_y_spin.setValue(self.tcp_offset_y)
        self.tcp_offset_y_spin.setDecimals(2)
        self.tcp_offset_y_spin.setSuffix(" mm")
        self.tcp_offset_y_spin.setToolTip("在基底坐标系Y轴方向的TCP偏移量")
        self.tcp_offset_y_spin.setMaximumWidth(120)
        y_layout.addWidget(self.tcp_offset_y_spin)
        tcp_layout.addLayout(y_layout)
        
        # TCP Z偏移
        z_layout = QVBoxLayout()
        z_layout.addWidget(QLabel("Z偏移:"))
        self.tcp_offset_z_spin = QDoubleSpinBox()
        self.tcp_offset_z_spin.setRange(-500.0, 500.0)
        self.tcp_offset_z_spin.setValue(self.tcp_offset_z)
        self.tcp_offset_z_spin.setDecimals(2)
        self.tcp_offset_z_spin.setSuffix(" mm")
        self.tcp_offset_z_spin.setToolTip("在基底坐标系Z轴方向的TCP偏移量")
        self.tcp_offset_z_spin.setMaximumWidth(120)
        z_layout.addWidget(self.tcp_offset_z_spin)
        tcp_layout.addLayout(z_layout)
        
        # 重置TCP按钮
        reset_layout = QVBoxLayout()
        reset_layout.addWidget(QLabel(""))  # 占位，与上面的标签对齐
        reset_tcp_btn = QPushButton("🔄 重置TCP")
        reset_tcp_btn.clicked.connect(self.reset_tcp_offset)
        reset_tcp_btn.setMaximumWidth(120)
        reset_tcp_btn.setToolTip("将TCP偏移重置为零")
        reset_layout.addWidget(reset_tcp_btn)
        tcp_layout.addLayout(reset_layout)
        
        main_layout.addLayout(tcp_layout)
        
        # 应用说明
        note_label = QLabel("⚠️ 注意: TCP修正在基底坐标系中应用到最终抓取坐标")
        note_label.setStyleSheet("color: #f39c12; font-size: 11px;")
        main_layout.addWidget(note_label)
        
        parent_layout.addWidget(group)
    
    def create_claw_settings_group(self, parent_layout):
        """创建夹爪设置组"""
        group = QGroupBox("夹爪角度设置")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加说明标签
        info_label = QLabel("🤏 夹爪角度设置（0°=完全张开，90°=完全闭合）:")
        info_label.setStyleSheet("color: #666; font-style: italic; font-size: 12px;")
        main_layout.addWidget(info_label)
        
        # 横向布局的夹爪角度参数
        claw_layout = QHBoxLayout()
        claw_layout.setSpacing(15)
        
        # 张开角度
        open_layout = QVBoxLayout()
        open_layout.addWidget(QLabel("张开角度:"))
        self.claw_open_angle_spin = QDoubleSpinBox()
        self.claw_open_angle_spin.setRange(0.0, 90.0)
        self.claw_open_angle_spin.setValue(self.claw_open_angle)
        self.claw_open_angle_spin.setDecimals(1)
        self.claw_open_angle_spin.setSuffix("°")
        self.claw_open_angle_spin.setToolTip("夹爪张开时的角度（0°为完全张开）")
        self.claw_open_angle_spin.setMaximumWidth(120)
        open_layout.addWidget(self.claw_open_angle_spin)
        claw_layout.addLayout(open_layout)
        
        # 闭合角度
        close_layout = QVBoxLayout()
        close_layout.addWidget(QLabel("闭合角度:"))
        self.claw_close_angle_spin = QDoubleSpinBox()
        self.claw_close_angle_spin.setRange(0.0, 90.0)
        self.claw_close_angle_spin.setValue(self.claw_close_angle)
        self.claw_close_angle_spin.setDecimals(1)
        self.claw_close_angle_spin.setSuffix("°")
        self.claw_close_angle_spin.setToolTip("夹爪闭合时的角度（90°为完全闭合）")
        self.claw_close_angle_spin.setMaximumWidth(120)
        close_layout.addWidget(self.claw_close_angle_spin)
        claw_layout.addLayout(close_layout)
        
        # 重置夹爪按钮
        reset_layout = QVBoxLayout()
        reset_layout.addWidget(QLabel(""))  # 占位，与上面的标签对齐
        reset_claw_btn = QPushButton("🔄 重置夹爪")
        reset_claw_btn.clicked.connect(self.reset_claw_angles)
        reset_claw_btn.setMaximumWidth(120)
        reset_claw_btn.setToolTip("将夹爪角度重置为默认值")
        reset_layout.addWidget(reset_claw_btn)
        claw_layout.addLayout(reset_layout)
        
        main_layout.addLayout(claw_layout)
        
        parent_layout.addWidget(group)
    
    def reset_tcp_offset(self):
        """重置TCP偏移为零"""
        self.tcp_offset_x_spin.setValue(0.0)
        self.tcp_offset_y_spin.setValue(0.0)
        self.tcp_offset_z_spin.setValue(0.0)
        print("✅ TCP偏移已重置为零")
    
    def reset_claw_angles(self):
        """重置夹爪角度为默认值"""
        self.claw_open_angle_spin.setValue(0.0)
        self.claw_close_angle_spin.setValue(90.0)
        print("✅ 夹爪角度已重置为默认值")
    
    def create_button_group(self, parent_layout):
        """创建按钮组"""
        button_layout = QHBoxLayout()
        button_layout.setSpacing(10)
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置所有")
        reset_btn.clicked.connect(self.reset_all_parameters)
        reset_btn.setMinimumHeight(35)
        reset_btn.setMinimumWidth(120)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        
        # 应用按钮
        apply_btn = QPushButton("✅ 应用")
        apply_btn.clicked.connect(self.apply_settings)
        apply_btn.setMinimumHeight(35)
        apply_btn.setMinimumWidth(100)
        button_layout.addWidget(apply_btn)
        
        parent_layout.addLayout(button_layout)
    
    def load_parameters_from_parent(self):
        """从父组件加载参数"""
        if not self.parent_widget:
            return
        
        try:
            # 加载姿态参数
            if hasattr(self.parent_widget, 'euler_yaw'):
                self.yaw_spin.setValue(self.parent_widget.euler_yaw)
                self.pitch_spin.setValue(self.parent_widget.euler_pitch)
                self.roll_spin.setValue(self.parent_widget.euler_roll)
            
            # 加载姿态模式
            if hasattr(self.parent_widget, 'use_dynamic_pose'):
                mode_index = 1 if self.parent_widget.use_dynamic_pose else 0
                self.pose_mode_combo.setCurrentIndex(mode_index)
                # 触发模式切换处理，更新Yaw角输入框状态
                self.on_pose_mode_changed()
            
            # 加载运动参数
            if hasattr(self.parent_widget, 'motion_speed'):
                self.motion_speed_spin.setValue(self.parent_widget.motion_speed)
                self.motion_acc_spin.setValue(self.parent_widget.motion_acceleration)
            
            # 加载TCP修正参数
            if hasattr(self.parent_widget, 'tcp_offset_x'):
                self.tcp_offset_x_spin.setValue(self.parent_widget.tcp_offset_x)
                self.tcp_offset_y_spin.setValue(self.parent_widget.tcp_offset_y)
                self.tcp_offset_z_spin.setValue(self.parent_widget.tcp_offset_z)
            
            # 加载夹爪角度参数
            if hasattr(self.parent_widget, 'claw_open_angle'):
                self.claw_open_angle_spin.setValue(self.parent_widget.claw_open_angle)
                self.claw_close_angle_spin.setValue(self.parent_widget.claw_close_angle)
        except Exception as e:
            print(f"⚠️ 加载参数时出错: {e}")
    
    def apply_settings(self):
        """应用设置"""
        try:
            # 应用姿态参数
            self.parent_widget.euler_yaw = self.yaw_spin.value()
            self.parent_widget.euler_pitch = self.pitch_spin.value()
            self.parent_widget.euler_roll = self.roll_spin.value()
            
            # 应用姿态模式设置
            self.parent_widget.use_dynamic_pose = (self.pose_mode_combo.currentIndex() == 1)
            
            # 应用运动参数
            self.parent_widget.motion_speed = self.motion_speed_spin.value()
            self.parent_widget.motion_acceleration = self.motion_acc_spin.value()
            
            # 应用TCP修正参数
            self.parent_widget.tcp_offset_x = self.tcp_offset_x_spin.value()
            self.parent_widget.tcp_offset_y = self.tcp_offset_y_spin.value()
            self.parent_widget.tcp_offset_z = self.tcp_offset_z_spin.value()
            
            # 应用夹爪角度参数
            self.parent_widget.claw_open_angle = self.claw_open_angle_spin.value()
            self.parent_widget.claw_close_angle = self.claw_close_angle_spin.value()
            
            # 同步隐藏的参数控件
            if hasattr(self.parent_widget, 'yaw_spin'):
                self.parent_widget.yaw_spin.setValue(self.yaw_spin.value())
                self.parent_widget.pitch_spin.setValue(self.pitch_spin.value())
                self.parent_widget.roll_spin.setValue(self.roll_spin.value())
            
            if hasattr(self.parent_widget, 'motion_speed_spin'):
                self.parent_widget.motion_speed_spin.setValue(self.motion_speed_spin.value())
                self.parent_widget.motion_acc_spin.setValue(self.motion_acc_spin.value())
            
            if hasattr(self.parent_widget, 'tcp_offset_x_spin'):
                self.parent_widget.tcp_offset_x_spin.setValue(self.tcp_offset_x_spin.value())
                self.parent_widget.tcp_offset_y_spin.setValue(self.tcp_offset_y_spin.value())
                self.parent_widget.tcp_offset_z_spin.setValue(self.tcp_offset_z_spin.value())
            
            # 保存抓取参数到配置文件
            self.save_grasp_parameters_to_config()
            
            print("✅ 抓取参数已成功应用")
            self.accept()
        
        except Exception as e:
            QMessageBox.warning(self, "错误", f"应用设置时出错: {str(e)}")
    
    def save_grasp_parameters_to_config(self):
        """保存抓取参数到配置文件"""
        try:
            if not self.parent_widget or not self.parent_widget.config_manager:
                print("⚠️ 无法保存抓取参数：配置管理器不可用")
                return
            
            # 构建抓取参数配置
            grasp_config = {
                "euler_angles": [
                    self.parent_widget.euler_yaw,
                    self.parent_widget.euler_pitch,
                    self.parent_widget.euler_roll
                ],
                "use_dynamic_pose": self.parent_widget.use_dynamic_pose,
                "motion_speed": self.parent_widget.motion_speed,
                "motion_acceleration": self.parent_widget.motion_acceleration,
                "tcp_offset": [
                    self.parent_widget.tcp_offset_x,
                    self.parent_widget.tcp_offset_y,
                    self.parent_widget.tcp_offset_z
                ],
                "claw_angles": [
                    self.parent_widget.claw_open_angle,
                    self.parent_widget.claw_close_angle
                ]
            }
            
            # 获取现有配置
            vision_config = self.parent_widget.config_manager.get_module_config("vision_grasp")
            
            # 更新抓取参数
            vision_config["grasp_params"] = grasp_config
            
            # 保存到配置文件
            success = self.parent_widget.config_manager.save_module_config("vision_grasp", vision_config)
            

            
        except Exception as e:
            print(f"❌ 保存抓取参数失败: {e}")
    
    def reset_all_parameters(self):
        """重置所有参数"""
        # 重置姿态参数
        self.yaw_spin.setValue(0.0)
        self.pitch_spin.setValue(0.0)
        self.roll_spin.setValue(180.0)
        
        # 重置运动参数
        self.motion_speed_spin.setValue(100)
        self.motion_acc_spin.setValue(200)
        
        # 重置TCP偏移
        self.reset_tcp_offset()
        
        # 重置夹爪角度
        self.reset_claw_angles()
        
        # 应用重置的参数到父组件并保存
        if self.parent_widget:
            # 应用重置的参数
            self.parent_widget.euler_yaw = 0.0
            self.parent_widget.euler_pitch = 0.0
            self.parent_widget.euler_roll = 180.0
            self.parent_widget.fixed_euler_angles = [0.0, 0.0, 180.0]
            
            self.parent_widget.motion_speed = 100
            self.parent_widget.motion_acceleration = 200
            
            self.parent_widget.tcp_offset_x = 0.0
            self.parent_widget.tcp_offset_y = 0.0
            self.parent_widget.tcp_offset_z = 0.0
            
            self.parent_widget.claw_open_angle = 0.0
            self.parent_widget.claw_close_angle = 90.0
            
            # 保存重置后的参数到配置文件
            self.save_grasp_parameters_to_config()
        
        print("✅ 所有抓取参数已重置为默认值并保存")


class VisionParametersDialog(QDialog):
    """视觉检测参数设置对话框"""
    
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        
        self.setWindowTitle("🎯 视觉检测参数设置")
        self.setFixedSize(700, 700)
        self.setModal(True)
        
        self.init_ui()
        self.load_parameters()
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)
        
        # 检测类型选择组
        type_group = QGroupBox("检测类型选择")
        type_layout = QHBoxLayout(type_group)
        type_layout.setSpacing(15)
        
        self.detection_type_combo = QComboBox()
        self.detection_type_combo.addItems(["颜色检测", "圆形检测", "二维码检测"])
        self.detection_type_combo.currentTextChanged.connect(self.on_detection_type_changed)
        type_layout.addWidget(QLabel("检测类型:"))
        type_layout.addWidget(self.detection_type_combo)
        type_layout.addStretch()
        
        layout.addWidget(type_group)
        
        # 创建滚动区域用于参数设置
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_widget = QWidget()
        self.scroll_layout = QVBoxLayout(scroll_widget)
        self.scroll_layout.setSpacing(10)
        
        # 颜色检测参数组
        self.create_color_params_group()
        
        # 圆形检测参数组
        self.create_circle_params_group()
        
        # 二维码检测参数组
        self.create_qrcode_params_group()
        
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # 按钮组
        button_layout = QHBoxLayout()
        
        reset_btn = QPushButton("🔄 重置默认")
        reset_btn.clicked.connect(self.reset_parameters)
        button_layout.addWidget(reset_btn)
        
        button_layout.addStretch()
        
        
        apply_btn = QPushButton("✅ 应用")
        apply_btn.clicked.connect(self.apply_parameters)
        button_layout.addWidget(apply_btn)
        
        layout.addLayout(button_layout)
        
        # 初始显示颜色检测参数
        self.on_detection_type_changed("颜色检测")
    
    def create_color_params_group(self):
        """创建颜色检测参数组"""
        self.color_group = QGroupBox("🎨 颜色检测参数")
        color_layout = QVBoxLayout(self.color_group)
        
        # HSV颜色阈值设置
        hsv_group = QGroupBox("HSV颜色阈值设置")
        hsv_layout = QGridLayout(hsv_group)
        hsv_layout.setSpacing(8)
        
        # HSV下限
        hsv_layout.addWidget(QLabel("HSV下限:"), 0, 0)
        
        hsv_layout.addWidget(QLabel("H:"), 0, 1)
        self.h_lower_spin = QSpinBox()
        self.h_lower_spin.setRange(0, 179)
        self.h_lower_spin.setValue(0)
        self.h_lower_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.h_lower_spin, 0, 2)
        
        hsv_layout.addWidget(QLabel("S:"), 0, 3)
        self.s_lower_spin = QSpinBox()
        self.s_lower_spin.setRange(0, 255)
        self.s_lower_spin.setValue(100)
        self.s_lower_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.s_lower_spin, 0, 4)
        
        hsv_layout.addWidget(QLabel("V:"), 0, 5)
        self.v_lower_spin = QSpinBox()
        self.v_lower_spin.setRange(0, 255)
        self.v_lower_spin.setValue(100)
        self.v_lower_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.v_lower_spin, 0, 6)
        
        # HSV上限
        hsv_layout.addWidget(QLabel("HSV上限:"), 1, 0)
        
        hsv_layout.addWidget(QLabel("H:"), 1, 1)
        self.h_upper_spin = QSpinBox()
        self.h_upper_spin.setRange(0, 179)
        self.h_upper_spin.setValue(10)
        self.h_upper_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.h_upper_spin, 1, 2)
        
        hsv_layout.addWidget(QLabel("S:"), 1, 3)
        self.s_upper_spin = QSpinBox()
        self.s_upper_spin.setRange(0, 255)
        self.s_upper_spin.setValue(255)
        self.s_upper_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.s_upper_spin, 1, 4)
        
        hsv_layout.addWidget(QLabel("V:"), 1, 5)
        self.v_upper_spin = QSpinBox()
        self.v_upper_spin.setRange(0, 255)
        self.v_upper_spin.setValue(255)
        self.v_upper_spin.setMaximumWidth(80)
        hsv_layout.addWidget(self.v_upper_spin, 1, 6)
        
        color_layout.addWidget(hsv_group)
        
        # 最小面积设置
        area_group = QGroupBox("面积过滤")
        area_layout = QHBoxLayout(area_group)
        area_layout.addWidget(QLabel("最小检测面积:"))
        self.min_area_spin = QSpinBox()
        self.min_area_spin.setRange(10, 10000)
        self.min_area_spin.setValue(500)
        self.min_area_spin.setSuffix(" 像素²")
        self.min_area_spin.setMaximumWidth(120)
        area_layout.addWidget(self.min_area_spin)
        area_layout.addStretch()
        color_layout.addWidget(area_group)
        
        # 预设颜色按钮
        preset_group = QGroupBox("颜色预设")
        preset_layout = QHBoxLayout(preset_group)
        
        red_btn = QPushButton("🔴 红色")
        red_btn.clicked.connect(lambda: self.set_color_preset("red"))
        preset_layout.addWidget(red_btn)
        
        blue_btn = QPushButton("🟡 黄色")
        blue_btn.clicked.connect(lambda: self.set_color_preset("yellow"))
        preset_layout.addWidget(blue_btn)
        
        # green_btn = QPushButton("🟢 绿色")
        # green_btn.clicked.connect(lambda: self.set_color_preset("green"))
        # preset_layout.addWidget(green_btn)

        white_btn = QPushButton("⚪ 白色")
        white_btn.clicked.connect(lambda: self.set_color_preset("white"))
        preset_layout.addWidget(white_btn)
        
        black_btn = QPushButton("⚫ 黑色")
        black_btn.clicked.connect(lambda: self.set_color_preset("black"))
        preset_layout.addWidget(black_btn)

        
        color_layout.addWidget(preset_group)
        
        self.scroll_layout.addWidget(self.color_group)
    
    def create_circle_params_group(self):
        """创建圆形检测参数组"""
        self.circle_group = QGroupBox("⭕ 圆形检测参数")
        circle_layout = QGridLayout(self.circle_group)
        circle_layout.setSpacing(10)
        
        # HoughCircles 参数
        circle_layout.addWidget(QLabel("累加器分辨率 (dp):"), 0, 0)
        self.circle_dp_spin = QDoubleSpinBox()
        self.circle_dp_spin.setRange(0.1, 5.0)
        self.circle_dp_spin.setSingleStep(0.1)
        self.circle_dp_spin.setValue(1.2)
        self.circle_dp_spin.setMaximumWidth(100)
        self.circle_dp_spin.setToolTip("累加器分辨率，值越小检测精度越高但速度越慢")
        circle_layout.addWidget(self.circle_dp_spin, 0, 1)
        
        circle_layout.addWidget(QLabel("圆心最小距离:"), 0, 2)
        self.circle_min_dist_spin = QSpinBox()
        self.circle_min_dist_spin.setRange(1, 200)
        self.circle_min_dist_spin.setValue(20)
        self.circle_min_dist_spin.setSuffix(" 像素")
        self.circle_min_dist_spin.setMaximumWidth(100)
        self.circle_min_dist_spin.setToolTip("两个圆心之间的最小距离")
        circle_layout.addWidget(self.circle_min_dist_spin, 0, 3)
        
        circle_layout.addWidget(QLabel("Canny高阈值:"), 1, 0)
        self.circle_param1_spin = QSpinBox()
        self.circle_param1_spin.setRange(10, 500)
        self.circle_param1_spin.setValue(100)
        self.circle_param1_spin.setMaximumWidth(100)
        self.circle_param1_spin.setToolTip("Canny边缘检测的高阈值")
        circle_layout.addWidget(self.circle_param1_spin, 1, 1)
        
        circle_layout.addWidget(QLabel("累加器阈值:"), 1, 2)
        self.circle_param2_spin = QSpinBox()
        self.circle_param2_spin.setRange(10, 200)
        self.circle_param2_spin.setValue(30)
        self.circle_param2_spin.setMaximumWidth(100)
        self.circle_param2_spin.setToolTip("累加器阈值，值越小检测到的圆越多")
        circle_layout.addWidget(self.circle_param2_spin, 1, 3)
        
        circle_layout.addWidget(QLabel("最小半径:"), 2, 0)
        self.circle_min_radius_spin = QSpinBox()
        self.circle_min_radius_spin.setRange(1, 1000)
        self.circle_min_radius_spin.setValue(5)
        self.circle_min_radius_spin.setSuffix(" 像素")
        self.circle_min_radius_spin.setMaximumWidth(100)
        circle_layout.addWidget(self.circle_min_radius_spin, 2, 1)
        
        circle_layout.addWidget(QLabel("最大半径:"), 2, 2)
        self.circle_max_radius_spin = QSpinBox()
        self.circle_max_radius_spin.setRange(1, 1000)
        self.circle_max_radius_spin.setValue(200)
        self.circle_max_radius_spin.setSuffix(" 像素")
        self.circle_max_radius_spin.setMaximumWidth(100)
        circle_layout.addWidget(self.circle_max_radius_spin, 2, 3)
        
        self.scroll_layout.addWidget(self.circle_group)
    
    def create_qrcode_params_group(self):
        """创建二维码检测参数组"""
        self.qrcode_group = QGroupBox("📱 二维码检测参数")
        qrcode_layout = QVBoxLayout(self.qrcode_group)
        
        info_label = QLabel("二维码检测使用OpenCV内置检测器，无需额外参数设置。\n检测支持多种二维码标准，包括QR码、Data Matrix等。")
        info_label.setStyleSheet("color: #7f8c8d; font-size: 12px; background-color: #ecf0f1; padding: 10px; border-radius: 5px;")
        info_label.setWordWrap(True)
        qrcode_layout.addWidget(info_label)
        
        # 添加一些提示信息
        tips_label = QLabel("💡 检测提示:\n• 确保二维码清晰可见\n• 避免强烈光照和反射\n• 二维码与相机保持合适距离")
        tips_label.setStyleSheet("color: #2c3e50; font-size: 12px; background-color: #e8f5e8; padding: 10px; border-radius: 5px;")
        tips_label.setWordWrap(True)
        qrcode_layout.addWidget(tips_label)
        
        self.scroll_layout.addWidget(self.qrcode_group)
    
    def on_detection_type_changed(self, detection_type):
        """检测类型改变时的处理"""
        # 隐藏所有参数组
        self.color_group.setVisible(False)
        self.circle_group.setVisible(False)
        self.qrcode_group.setVisible(False)
        
        # 显示对应的参数组
        if detection_type == "颜色检测":
            self.color_group.setVisible(True)
        elif detection_type == "圆形检测":
            self.circle_group.setVisible(True)
        elif detection_type == "二维码检测":
            self.qrcode_group.setVisible(True)
    
    def load_parameters(self):
        """加载父组件的参数"""
        if self.parent_widget:
            # 设置检测类型（从配置文件加载的参数）
            type_map = {"color": "颜色检测", "circle": "圆形检测", "qrcode": "二维码检测"}
            detection_type_text = type_map.get(self.parent_widget.detection_type, "颜色检测")
            self.detection_type_combo.setCurrentText(detection_type_text)
            
            # 加载颜色检测参数（从配置文件加载的参数）
            h_lower, s_lower, v_lower = self.parent_widget.hsv_lower
            h_upper, s_upper, v_upper = self.parent_widget.hsv_upper
            
            self.h_lower_spin.setValue(h_lower)
            self.s_lower_spin.setValue(s_lower)
            self.v_lower_spin.setValue(v_lower)
            
            self.h_upper_spin.setValue(h_upper)
            self.s_upper_spin.setValue(s_upper)
            self.v_upper_spin.setValue(v_upper)
            
            self.min_area_spin.setValue(self.parent_widget.min_area)
            
            # 加载圆形检测参数（从配置文件加载的参数）
            self.circle_dp_spin.setValue(self.parent_widget.circle_dp)
            self.circle_min_dist_spin.setValue(int(self.parent_widget.circle_min_dist))
            self.circle_param1_spin.setValue(int(self.parent_widget.circle_param1))
            self.circle_param2_spin.setValue(int(self.parent_widget.circle_param2))
            self.circle_min_radius_spin.setValue(self.parent_widget.circle_min_radius)
            self.circle_max_radius_spin.setValue(self.parent_widget.circle_max_radius)
            
    
    def set_color_preset(self, color):
        """设置颜色预设"""
        presets = {
            "red": {"lower": (0, 50, 80), "upper": (10, 250, 255)},
            "yellow": {"lower": (0, 60, 80), "upper": (50, 250, 255)},
            # "green": {"lower": (35, 45, 80), "upper": (85, 255, 255)},
            "white": {"lower": (0, 20, 200), "upper": (179, 45, 255)},
            "black": {"lower": (0, 0, 0), "upper": (179, 255, 50)}
            
        }
        
        if color in presets:
            preset = presets[color]
            h_lower, s_lower, v_lower = preset["lower"]
            h_upper, s_upper, v_upper = preset["upper"]
            
            self.h_lower_spin.setValue(h_lower)
            self.s_lower_spin.setValue(s_lower)
            self.v_lower_spin.setValue(v_lower)
            
            self.h_upper_spin.setValue(h_upper)
            self.s_upper_spin.setValue(s_upper)
            self.v_upper_spin.setValue(v_upper)
    
    def reset_parameters(self):
        """重置为默认参数"""
        # 重置检测类型
        self.detection_type_combo.setCurrentText("颜色检测")
        
        # 重置颜色参数
        self.h_lower_spin.setValue(0)
        self.s_lower_spin.setValue(100)
        self.v_lower_spin.setValue(100)
        
        self.h_upper_spin.setValue(10)
        self.s_upper_spin.setValue(255)
        self.v_upper_spin.setValue(255)
        
        self.min_area_spin.setValue(500)
        
        # 重置圆形参数
        self.circle_dp_spin.setValue(1.2)
        self.circle_min_dist_spin.setValue(20)
        self.circle_param1_spin.setValue(100)
        self.circle_param2_spin.setValue(30)
        self.circle_min_radius_spin.setValue(5)
        self.circle_max_radius_spin.setValue(200)
        
        # 应用重置的参数到父组件并保存
        if self.parent_widget:
            # 设置检测类型
            self.parent_widget.detection_type = "color"
            
            # 应用重置的参数
            self.parent_widget.hsv_lower = (0, 100, 100)
            self.parent_widget.hsv_upper = (10, 255, 255)
            self.parent_widget.min_area = 500
            
            self.parent_widget.circle_dp = 1.2
            self.parent_widget.circle_min_dist = 20
            self.parent_widget.circle_param1 = 100
            self.parent_widget.circle_param2 = 30
            self.parent_widget.circle_min_radius = 5
            self.parent_widget.circle_max_radius = 200
            
            # 保存重置后的参数到配置文件
            self.save_vision_detection_parameters_to_config()
    
    def apply_parameters(self):
        """应用参数设置"""
        if self.parent_widget:
            # 设置检测类型
            type_map = {"颜色检测": "color", "圆形检测": "circle", "二维码检测": "qrcode"}
            self.parent_widget.detection_type = type_map.get(self.detection_type_combo.currentText(), "color")
            
            # 应用颜色检测参数
            self.parent_widget.hsv_lower = (
                self.h_lower_spin.value(),
                self.s_lower_spin.value(),
                self.v_lower_spin.value()
            )
            self.parent_widget.hsv_upper = (
                self.h_upper_spin.value(),
                self.s_upper_spin.value(),
                self.v_upper_spin.value()
            )
            self.parent_widget.min_area = self.min_area_spin.value()
            
            # 应用圆形检测参数
            self.parent_widget.circle_dp = self.circle_dp_spin.value()
            self.parent_widget.circle_min_dist = self.circle_min_dist_spin.value()
            self.parent_widget.circle_param1 = self.circle_param1_spin.value()
            self.parent_widget.circle_param2 = self.circle_param2_spin.value()
            self.parent_widget.circle_min_radius = self.circle_min_radius_spin.value()
            self.parent_widget.circle_max_radius = self.circle_max_radius_spin.value()
            
            # 保存检测参数到配置文件
            self.save_vision_detection_parameters_to_config()
            
            # 更新阈值图显示标题
            threshold_titles = {
                "color": "🎨 颜色检测阈值图",
                "circle": "⭕ 圆形检测边缘图",
                "qrcode": "📱 二维码检测灰度图"
            }
            if hasattr(self.parent_widget, 'threshold_title'):
                self.parent_widget.threshold_title.setText(
                    threshold_titles.get(self.parent_widget.detection_type, "🎯 视觉检测图")
                )
        
        self.accept()
    
    def save_vision_detection_parameters_to_config(self):
        """保存视觉检测参数到配置文件"""
        try:
            if not self.parent_widget or not self.parent_widget.config_manager:
                print("⚠️ 无法保存视觉检测参数：配置管理器不可用")
                return
            
            # 构建视觉检测参数配置
            detection_config = {
                "detection_type": self.parent_widget.detection_type,
                "hsv_lower": list(self.parent_widget.hsv_lower),
                "hsv_upper": list(self.parent_widget.hsv_upper),
                "min_area": self.parent_widget.min_area,
                "circle_dp": self.parent_widget.circle_dp,
                "circle_min_dist": self.parent_widget.circle_min_dist,
                "circle_param1": self.parent_widget.circle_param1,
                "circle_param2": self.parent_widget.circle_param2,
                "circle_min_radius": self.parent_widget.circle_min_radius,
                "circle_max_radius": self.parent_widget.circle_max_radius
            }
            
            # 获取现有配置
            vision_config = self.parent_widget.config_manager.get_module_config("vision_grasp")
            
            # 更新检测参数
            vision_config["vision_detection"] = detection_config
            
            # 保存到配置文件
            success = self.parent_widget.config_manager.save_module_config("vision_grasp", vision_config)
            
            if success:
                print("✅ 视觉检测参数已保存到配置文件")
            else:
                print("❌ 视觉检测参数保存失败")
            
        except Exception as e:
            print(f"❌ 保存视觉检测参数失败: {e}")


class VisionGraspParametersDialog(QDialog):
    """视觉抓取参数设置对话框"""
    
    def __init__(self, parent=None, depth_estimator=None):
        super().__init__(parent)
        self.parent_widget = parent
        self.depth_estimator = depth_estimator
        # 默认使用双目深度估计模式，让用户可以看到所有参数设置
        self.use_depth_estimation = True
        
        # 设置对话框属性
        self.setWindowTitle("📷 相机参数设置")
        self.setFixedSize(500, 600)
        self.setModal(True)
        
        # 初始化参数
        self.init_parameters()
        
        # 初始化UI
        self.init_ui()
        
        # 加载父组件的参数
        if parent:
            self.load_parameters_from_parent()
    
    def init_parameters(self):
        """初始化参数默认值"""
        # 深度参数 - 如果有父组件，从父组件获取，否则使用默认值
        if self.parent_widget:
            self.fixed_depth_value = getattr(self.parent_widget, 'fixed_depth_value', 300.0)
            self.sgbm_min_disparity = getattr(self.parent_widget, 'sgbm_min_disparity', 0)
            self.sgbm_num_disparities = getattr(self.parent_widget, 'sgbm_num_disparities', 128)
            self.sgbm_block_size = getattr(self.parent_widget, 'sgbm_block_size', 5)
            self.sgbm_uniqueness = getattr(self.parent_widget, 'sgbm_uniqueness', 10)
            self.camera_device_id = getattr(self.parent_widget, 'camera_device_id', 0)
        else:
            # 默认参数
            self.fixed_depth_value = 300.0
            self.sgbm_min_disparity = 0
            self.sgbm_num_disparities = 128
            self.sgbm_block_size = 5
            self.sgbm_uniqueness = 10
            self.camera_device_id = 0
    
    def init_ui(self):
        """初始化用户界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(5)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(12)
        scroll_layout.setContentsMargins(15, 15, 15, 15)
        
        # 相机设置组
        self.create_camera_settings_group(scroll_layout)
        
        # 深度设置组
        self.create_depth_settings_group(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # 按钮组直接添加到主布局（不滚动）
        self.create_button_group(main_layout)
        
        # 在所有UI组件创建完成后，设置正确的初始状态
        self.on_depth_mode_changed("双目深度估计")
    
    def create_camera_settings_group(self, parent_layout):
        """创建相机设置组"""
        group = QGroupBox("相机设置")
        layout = QGridLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 相机设备选择
        layout.addWidget(QLabel("相机设备ID:"), 0, 0)
        self.camera_device_combo = QComboBox()
        self.camera_device_combo.addItems(["0", "1", "2", "3", "4", "5"])
        self.camera_device_combo.setCurrentText(str(self.camera_device_id))
        self.camera_device_combo.setToolTip("选择要使用的相机设备ID\n通常双目相机使用设备ID 0")
        self.camera_device_combo.setMaximumWidth(80)
        layout.addWidget(self.camera_device_combo, 0, 1)
        
        # 说明文字
        info_label = QLabel("💡 提示: 双目相机通常使用设备ID 0，如果无法启动请尝试其他ID")
        info_label.setStyleSheet("color: #7f8c8d; font-size: 11px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label, 1, 0, 1, 2)
        
        parent_layout.addWidget(group)
    
    def create_depth_settings_group(self, parent_layout):
        """创建深度设置组"""
        group = QGroupBox("深度设置")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # 深度模式选择
        mode_layout = QHBoxLayout()
        mode_layout.addWidget(QLabel("深度模式:"))
        
        self.depth_mode_combo = QComboBox()
        self.depth_mode_combo.addItems(["固定深度", "双目深度估计"])
        # 默认选择双目深度估计，让用户可以看到SGBM参数
        self.depth_mode_combo.setCurrentIndex(0)
        self.depth_mode_combo.currentTextChanged.connect(self.on_depth_mode_changed)
        self.depth_mode_combo.setMaximumWidth(120)
        mode_layout.addWidget(self.depth_mode_combo)
        
        # 先创建所有控件，然后再触发模式切换
        
        mode_layout.addSpacing(20)
        mode_layout.addWidget(QLabel("固定深度:"))
        
        self.depth_spin = QDoubleSpinBox()
        self.depth_spin.setRange(10.0, 1000.0)
        self.depth_spin.setValue(self.fixed_depth_value)
        self.depth_spin.setDecimals(1)
        self.depth_spin.setSuffix(" mm")
        self.depth_spin.setMaximumWidth(100)
        # 固定深度在选择"固定深度"模式时启用（当前默认为False，所以禁用）
        self.depth_spin.setEnabled(not self.use_depth_estimation)
        mode_layout.addWidget(self.depth_spin)
        
        mode_layout.addStretch()
        layout.addLayout(mode_layout)
        
        # 深度状态
        status_text = "深度估计可用" if self.depth_estimator else "深度估计不可用"
        self.depth_status_label = QLabel(status_text)
        style = "color: green; font-weight: bold;" if self.depth_estimator else "color: red; font-weight: bold;"
        self.depth_status_label.setStyleSheet(style)
        layout.addWidget(self.depth_status_label)
        
        # SGBM参数设置
        self.sgbm_group = QGroupBox("SGBM深度参数")
        sgbm_layout = QGridLayout(self.sgbm_group)
        sgbm_layout.setSpacing(6)
        sgbm_layout.setContentsMargins(10, 10, 10, 10)
        
        # 第一行
        sgbm_layout.addWidget(QLabel("最小视差:"), 0, 0)
        self.min_disparity_spin = QSpinBox()
        self.min_disparity_spin.setRange(-64, 64)
        self.min_disparity_spin.setValue(self.sgbm_min_disparity)
        self.min_disparity_spin.valueChanged.connect(self.on_sgbm_params_changed)
        self.min_disparity_spin.setMaximumWidth(80)
        sgbm_layout.addWidget(self.min_disparity_spin, 0, 1)
        
        sgbm_layout.addWidget(QLabel("视差范围:"), 0, 2)
        self.num_disparities_spin = QSpinBox()
        self.num_disparities_spin.setRange(16, 256)
        self.num_disparities_spin.setSingleStep(16)
        self.num_disparities_spin.setValue(self.sgbm_num_disparities)
        self.num_disparities_spin.valueChanged.connect(self.on_sgbm_params_changed)
        self.num_disparities_spin.setMaximumWidth(80)
        sgbm_layout.addWidget(self.num_disparities_spin, 0, 3)
        
        # 第二行
        sgbm_layout.addWidget(QLabel("块大小:"), 1, 0)
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(3, 21)
        self.block_size_spin.setSingleStep(2)
        self.block_size_spin.setValue(self.sgbm_block_size)
        self.block_size_spin.valueChanged.connect(self.on_sgbm_params_changed)
        self.block_size_spin.setMaximumWidth(80)
        sgbm_layout.addWidget(self.block_size_spin, 1, 1)
        
        sgbm_layout.addWidget(QLabel("唯一性:"), 1, 2)
        self.uniqueness_spin = QSpinBox()
        self.uniqueness_spin.setRange(1, 50)
        self.uniqueness_spin.setValue(self.sgbm_uniqueness)
        self.uniqueness_spin.valueChanged.connect(self.on_sgbm_params_changed)
        self.uniqueness_spin.setMaximumWidth(80)
        sgbm_layout.addWidget(self.uniqueness_spin, 1, 3)
        
        # 重置按钮（放在第三行）
        self.reset_sgbm_btn = QPushButton("🔄 重置SGBM")
        self.reset_sgbm_btn.clicked.connect(self.reset_sgbm_params)
        self.reset_sgbm_btn.setMaximumWidth(120)
        sgbm_layout.addWidget(self.reset_sgbm_btn, 2, 0, 1, 2)
        
        # 工具提示
        self.min_disparity_spin.setToolTip("最小视差值，通常为0。负值用于处理会聚相机")
        self.num_disparities_spin.setToolTip("视差搜索范围，必须是16的倍数。值越大适合越近的物体")
        self.block_size_spin.setToolTip("匹配块大小，必须是奇数。小值=细节多但噪声大，大值=平滑但细节少")
        self.uniqueness_spin.setToolTip("唯一性阈值。值越大质量越好但匹配点越少")
        
        layout.addWidget(self.sgbm_group)
        
        # SGBM组始终显示，但根据深度模式启用/禁用参数编辑
        self.sgbm_group.setVisible(True)
        
        parent_layout.addWidget(group)
    
    def set_sgbm_widgets_enabled(self, enabled):
        """设置SGBM参数控件的启用/禁用状态"""
        self.min_disparity_spin.setEnabled(enabled)
        self.num_disparities_spin.setEnabled(enabled)
        self.block_size_spin.setEnabled(enabled)
        self.uniqueness_spin.setEnabled(enabled)
        self.reset_sgbm_btn.setEnabled(enabled)
        
        # 更新SGBM组的标题以反映状态
        if enabled:
            self.sgbm_group.setTitle("SGBM深度参数")
        else:
            self.sgbm_group.setTitle("SGBM深度参数 (仅双目深度估计可用)")
    

    
    def create_button_group(self, parent_layout):
        """创建按钮组"""
        button_box = QDialogButtonBox()
        
        # 应用按钮
        apply_btn = QPushButton("✅ 应用设置")
        apply_btn.clicked.connect(self.apply_settings)
        button_box.addButton(apply_btn, QDialogButtonBox.ApplyRole)
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置所有")
        reset_btn.clicked.connect(self.reset_all_parameters)
        button_box.addButton(reset_btn, QDialogButtonBox.ResetRole)
        
        
        parent_layout.addWidget(button_box)
    
    def load_parameters_from_parent(self):
        """从父组件加载参数"""
        if not self.parent_widget:
            return
        
        try:
            # 加载深度参数 - 使用父组件的实际值（已从配置文件加载）
            if hasattr(self.parent_widget, 'fixed_depth_value') and hasattr(self, 'depth_spin'):
                self.depth_spin.setValue(self.parent_widget.fixed_depth_value)
            elif hasattr(self.parent_widget, 'depth_spin') and hasattr(self, 'depth_spin'):
                self.depth_spin.setValue(self.parent_widget.depth_spin.value())
            
            if hasattr(self.parent_widget, 'use_depth_estimation'):
                self.use_depth_estimation = self.parent_widget.use_depth_estimation
                mode = "双目深度估计" if self.use_depth_estimation else "固定深度"
                self.depth_mode_combo.setCurrentText(mode)
                if hasattr(self, 'depth_spin'):
                    self.depth_spin.setEnabled(not self.use_depth_estimation)
            
            # 加载SGBM参数 - 优先使用父组件的实际值（已从配置文件加载）
            if hasattr(self.parent_widget, 'sgbm_min_disparity') and hasattr(self, 'min_disparity_spin'):
                self.min_disparity_spin.setValue(self.parent_widget.sgbm_min_disparity)
                self.num_disparities_spin.setValue(self.parent_widget.sgbm_num_disparities)
                self.block_size_spin.setValue(self.parent_widget.sgbm_block_size)
                self.uniqueness_spin.setValue(self.parent_widget.sgbm_uniqueness)
            elif (hasattr(self.parent_widget, 'min_disparity_spin') and 
                hasattr(self, 'min_disparity_spin')):
                self.min_disparity_spin.setValue(self.parent_widget.min_disparity_spin.value())
                self.num_disparities_spin.setValue(self.parent_widget.num_disparities_spin.value())
                self.block_size_spin.setValue(self.parent_widget.block_size_spin.value())
                self.uniqueness_spin.setValue(self.parent_widget.uniqueness_spin.value())
            
            # 加载相机设备ID
            if (hasattr(self.parent_widget, 'camera_device_id') and 
                hasattr(self, 'camera_device_combo')):
                self.camera_device_combo.setCurrentText(str(getattr(self.parent_widget, 'camera_device_id', 0)))
                
        except Exception as e:
            print(f"加载参数失败: {e}")
    
    def apply_settings(self):
        """应用设置到父组件"""
        if not self.parent_widget:
            return
        
        try:
            # 应用深度参数
            if hasattr(self.parent_widget, 'depth_spin') and hasattr(self, 'depth_spin'):
                self.parent_widget.depth_spin.setValue(self.depth_spin.value())
                self.parent_widget.fixed_depth_value = self.depth_spin.value()
            
            if hasattr(self.parent_widget, 'depth_mode_combo'):
                self.parent_widget.depth_mode_combo.setCurrentText(self.depth_mode_combo.currentText())
                self.parent_widget.on_depth_mode_changed(self.depth_mode_combo.currentText())
            
            # 应用SGBM参数
            if (hasattr(self.parent_widget, 'min_disparity_spin') and 
                hasattr(self, 'min_disparity_spin')):
                self.parent_widget.min_disparity_spin.setValue(self.min_disparity_spin.value())
                self.parent_widget.num_disparities_spin.setValue(self.num_disparities_spin.value())
                self.parent_widget.block_size_spin.setValue(self.block_size_spin.value())
                self.parent_widget.uniqueness_spin.setValue(self.uniqueness_spin.value())
                
                # 同时更新父组件的参数变量
                self.parent_widget.sgbm_min_disparity = self.min_disparity_spin.value()
                self.parent_widget.sgbm_num_disparities = self.num_disparities_spin.value()
                self.parent_widget.sgbm_block_size = self.block_size_spin.value()
                self.parent_widget.sgbm_uniqueness = self.uniqueness_spin.value()
                
                self.parent_widget.on_sgbm_params_changed()
            
            # 应用相机设备ID
            if hasattr(self, 'camera_device_combo'):
                self.parent_widget.camera_device_id = int(self.camera_device_combo.currentText())
                print(f"相机设备ID已更新: {self.parent_widget.camera_device_id}")
            
            # 保存参数到配置文件
            self.save_parameters_to_config()
            
            # 标记参数已配置并更新状态显示
            self.parent_widget.parameters_configured = True
            self.parent_widget.update_parameter_status()
            
            QMessageBox.information(self, "成功", "参数设置已应用并保存！现在可以启动相机了。")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"应用参数设置失败: {str(e)}")
    
    def save_parameters_to_config(self):
        """保存参数到配置文件"""
        try:
            # 构建配置数据
            vision_config = {
                "camera": {
                    "device_id": int(self.camera_device_combo.currentText()),
                    "fixed_depth_value": self.depth_spin.value()  # 现在是毫米单位
                },
                "sgbm": {
                    "min_disparity": self.min_disparity_spin.value(),
                    "num_disparities": self.num_disparities_spin.value(),
                    "block_size": self.block_size_spin.value(),
                    "uniqueness": self.uniqueness_spin.value()
                },
                "depth_mode": self.depth_mode_combo.currentText()
            }
            
            # 调用父组件的保存方法
            success = self.parent_widget.save_camera_config_to_file(vision_config)
            
        except Exception as e:
            print(f"❌ 保存相机参数到配置文件失败: {e}")
            QMessageBox.warning(self, "警告", f"保存参数到配置文件失败: {str(e)}\n参数仍已应用到当前会话。")
    
    def on_depth_mode_changed(self, mode):
        """深度模式切换处理"""
        self.use_depth_estimation = (mode == "双目深度估计")
        self.depth_spin.setEnabled(not self.use_depth_estimation)
        
        # 控制SGBM参数组的启用/禁用状态 - 只有双目深度估计模式才能编辑
        self.set_sgbm_widgets_enabled(self.use_depth_estimation)
        
        # 允许用户设置SGBM参数，即使深度估计器不可用
        # 在实际执行时会有相应的处理逻辑
        if self.use_depth_estimation and not self.depth_estimator:
            # 不强制切换模式，只给出提示
            print("⚠️ 深度估计器不可用，但允许用户预设SGBM参数")
    
    def on_sgbm_params_changed(self):
        """SGBM参数改变时更新深度估计器"""
        if not self.depth_estimator:
            return
        
        # 确保num_disparities是16的倍数
        num_disp = self.num_disparities_spin.value()
        if num_disp % 16 != 0:
            num_disp = (num_disp // 16) * 16
            self.num_disparities_spin.setValue(num_disp)
        
        # 确保block_size是奇数
        block_size = self.block_size_spin.value()
        if block_size % 2 == 0:
            block_size += 1
            self.block_size_spin.setValue(block_size)
    
    def reset_sgbm_params(self):
        """重置SGBM参数为默认值"""
        self.min_disparity_spin.setValue(0)
        self.num_disparities_spin.setValue(128)
        self.block_size_spin.setValue(5)
        self.uniqueness_spin.setValue(10)
        print("✅ SGBM参数已重置为默认值")
    
    def reset_all_parameters(self):
        """重置所有参数为默认值"""
        # 重置深度参数
        self.depth_mode_combo.setCurrentIndex(0 if self.depth_estimator else 1)
        self.depth_spin.setValue(300.0)
        
        # 重置相机设备ID
        self.camera_device_combo.setCurrentText("0")
        
        # 重置SGBM参数
        self.reset_sgbm_params()
        
        # 保存重置后的参数到配置文件
        try:
            self.save_parameters_to_config()
        except Exception as e:
            print(f"保存重置参数失败: {e}")
        
        QMessageBox.information(self, "重置完成", "所有相机参数已重置为默认值并保存！")

class VisionGraspWidget(QWidget):
    """视觉抓取控件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        self.motor_config_manager = motor_config_manager
        
        # 配置管理器
        self.config_manager = config_manager if CONFIG_MANAGER_AVAILABLE else None
        
        # 相机相关
        self.camera = None # 单个相机实例
        self.camera_timer = None
        self.camera_running = False
        self.current_left_frame = None  # 存储当前左相机帧
        self.current_right_frame = None  # 存储当前右相机帧
        
        # 标定参数
        self.calibration_params = self.load_calibration_params()
        
        # 深度估计器
        if DEPTH_ESTIMATION_AVAILABLE:
            try:
                # 解析打包(_MEIPASS)与源码两种环境下的标定文件绝对路径
                base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
                calib_path = os.path.join(base_dir, 'config', 'calibration_parameter.json')
                self.depth_estimator = StereoDepthEstimator(config_path=calib_path)
            except Exception as e:
                print(f"⚠️ 深度估计器初始化失败: {e}")
                self.depth_estimator = None
        else:
            self.depth_estimator = None
        
        # 预处理相机参数用于去畸变
        self.camera_matrix = None
        self.dist_coeffs = None
        self.camera_model = 'pinhole'
        self.undistort_maps = None  # 预计算的去畸变映射
        self.setup_camera_params()
        
        
        
        # 参数设置状态标志
        self.parameters_configured = False
        
        # 从配置文件加载相机参数
        self.load_camera_parameters_from_config()
        
        # 视觉识别相关
        self.vision_detector = None
        self.vision_detection_enabled = False
        self.detected_objects = []  # 存储检测到的对象（包含旋转矩形信息）
        
        # 从配置文件加载视觉检测参数
        self.load_vision_detection_parameters_from_config()
        
        # 从配置文件加载抓取参数
        self.load_grasp_parameters_from_config()
        
        # 识别位置相关
        self.detected_center_point = None  # 存储识别到的中心点坐标 (x, y)
        self.use_detected_position = False  # 是否使用识别位置进行抓取
        
        # 夹爪控制器相关
        self.claw_controller = None  # 夹爪控制器实例
        self.claw_connected = False  # 夹爪连接状态
        
        # 初始化运动学控制器
        if KINEMATICS_AVAILABLE:
            try:
                self.kinematics = create_configured_kinematics()
            except Exception as e:
                print(f"⚠️ 运动学控制器初始化失败: {e}")
                self.kinematics = None
        else:
            self.kinematics = None
        
        self.init_ui()
        
        # 初始化SGBM参数（在UI创建后）
        if self.depth_estimator:
            self.update_depth_estimator_params()
        
        # 初始化相机状态（相机未启动时不可点击）
        if hasattr(self, 'right_camera_label'):
            self.right_camera_label.set_camera_active(False)
        
        # 初始化参数状态显示
        if hasattr(self, 'params_status_label'):
            self.update_parameter_status()
    
    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            
            # 停止相机
            if self.camera_running:
                print("📷 停止相机...")
                self.stop_camera()
            
            # 清理定时器
            if self.camera_timer:
                self.camera_timer.stop()
                self.camera_timer = None
            
            # 释放相机资源
            if self.camera:
                self.camera.release()
                self.camera = None
            
            # 清理深度估计器
            if self.depth_estimator:
                self.depth_estimator = None
            
            # 清理视觉检测器
            if self.vision_detector:
                self.vision_detector = None
            
            print("✅ 视觉抓取控件资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 视觉抓取控件清理资源时发生错误: {e}")
        finally:
            event.accept()
    
    def __del__(self):
        """析构函数 - 确保资源被释放"""
        try:
            if hasattr(self, 'camera_running') and self.camera_running:
                self.stop_camera()
            if hasattr(self, 'camera') and self.camera:
                self.camera.release()
        except Exception:
            pass  # 析构函数中不抛出异常
    
    def load_camera_parameters_from_config(self):
        """从配置文件加载相机参数并设置到实例变量"""
        try:
            if not self.config_manager:
                print("⚠️ 配置管理器不可用，使用默认参数")
                self._set_default_camera_parameters()
                return
            
            vision_config = self.config_manager.get_module_config("vision_grasp")
            
            if not vision_config:
                print("📋 配置文件为空，使用默认相机参数")
                self._set_default_camera_parameters()
                return
            
            # 加载相机参数
            self.camera_device_id = self.config_manager.get_config_value(
                "vision_grasp", "camera.device_id", 0
            )
            self.fixed_depth_value = self.config_manager.get_config_value(
                "vision_grasp", "camera.fixed_depth_value", 300.0
            )
            
            # 加载SGBM参数
            self.sgbm_min_disparity = self.config_manager.get_config_value(
                "vision_grasp", "sgbm.min_disparity", 0
            )
            self.sgbm_num_disparities = self.config_manager.get_config_value(
                "vision_grasp", "sgbm.num_disparities", 128
            )
            self.sgbm_block_size = self.config_manager.get_config_value(
                "vision_grasp", "sgbm.block_size", 5
            )
            self.sgbm_uniqueness = self.config_manager.get_config_value(
                "vision_grasp", "sgbm.uniqueness", 10
            )
            
            # 加载深度模式
            depth_mode = self.config_manager.get_config_value(
                "vision_grasp", "depth_mode", "双目深度估计"
            )
            self.use_depth_estimation = (depth_mode == "双目深度估计")
            if not self.depth_estimator:
                # 如果深度估计器不可用，强制使用固定深度
                self.use_depth_estimation = False
    
            
        except Exception as e:
            print(f"❌ 加载相机参数失败，使用默认值: {e}")
            self._set_default_camera_parameters()
    
    def _set_default_camera_parameters(self):
        """设置默认相机参数"""
        self.use_depth_estimation = True if self.depth_estimator else False
        self.camera_device_id = 0
        self.fixed_depth_value = 300.0
        self.sgbm_min_disparity = 0
        self.sgbm_num_disparities = 128
        self.sgbm_block_size = 5
        self.sgbm_uniqueness = 10
        print("📋 已设置默认相机参数")
    
    def load_vision_detection_parameters_from_config(self):
        """从配置文件加载视觉检测参数并设置到实例变量"""
        try:
            if not self.config_manager:
                print("⚠️ 配置管理器不可用，使用默认检测参数")
                self._set_default_vision_detection_parameters()
                return
            
            # 加载检测类型
            self.detection_type = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.detection_type", "color"
            )
            
            # 加载颜色检测参数
            self.hsv_lower = tuple(self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.hsv_lower", [0, 100, 100]
            ))
            self.hsv_upper = tuple(self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.hsv_upper", [10, 255, 255]
            ))
            self.min_area = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.min_area", 500
            )
            
            # 加载圆形检测参数
            self.circle_dp = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_dp", 1.2
            )
            self.circle_min_dist = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_min_dist", 20
            )
            self.circle_param1 = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_param1", 100
            )
            self.circle_param2 = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_param2", 30
            )
            self.circle_min_radius = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_min_radius", 5
            )
            self.circle_max_radius = self.config_manager.get_config_value(
                "vision_grasp", "vision_detection.circle_max_radius", 200
            )
            
            
        except Exception as e:
            print(f"❌ 加载视觉检测参数失败，使用默认值: {e}")
            self._set_default_vision_detection_parameters()
    
    def _set_default_vision_detection_parameters(self):
        """设置默认视觉检测参数"""
        # 检测类型和参数
        self.detection_type = "color"  # 检测类型: color, circle, qrcode
        
        # 颜色检测参数
        self.hsv_lower = (0, 100, 100)  # HSV下限阈值
        self.hsv_upper = (10, 255, 255)  # HSV上限阈值
        self.min_area = 500  # 最小检测面积
        
        # 圆形检测参数
        self.circle_dp = 1.2  # 累加器分辨率
        self.circle_min_dist = 20  # 圆心之间最小距离
        self.circle_param1 = 100  # Canny边缘检测高阈值
        self.circle_param2 = 30  # 累加器阈值
        self.circle_min_radius = 5  # 最小半径
        self.circle_max_radius = 200  # 最大半径
        
        print("📋 已设置默认视觉检测参数")
    
    def load_grasp_parameters_from_config(self):
        """从配置文件加载抓取参数并设置到实例变量"""
        try:
            if not self.config_manager:
                print("⚠️ 配置管理器不可用，使用默认抓取参数")
                self._set_default_grasp_parameters()
                return
            
            # 加载姿态参数（欧拉角）
            euler_angles = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.euler_angles", [0.0, 0.0, 180.0]
            )
            if len(euler_angles) >= 3:
                self.euler_yaw = euler_angles[0]
                self.euler_pitch = euler_angles[1] 
                self.euler_roll = euler_angles[2]
                self.fixed_euler_angles = euler_angles.copy()
            
            # 加载姿态模式
            self.use_dynamic_pose = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.use_dynamic_pose", False
            )
            
            # 加载运动参数
            self.motion_speed = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.motion_speed", 100
            )
            self.motion_acceleration = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.motion_acceleration", 200
            )
            
            # 加载TCP修正参数
            tcp_offset = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.tcp_offset", [0.0, 0.0, 0.0]
            )
            if len(tcp_offset) >= 3:
                self.tcp_offset_x = tcp_offset[0]
                self.tcp_offset_y = tcp_offset[1]
                self.tcp_offset_z = tcp_offset[2]
            
            # 加载夹爪角度参数
            claw_angles = self.config_manager.get_config_value(
                "vision_grasp", "grasp_params.claw_angles", [0.0, 90.0]
            )
            if len(claw_angles) >= 2:
                self.claw_open_angle = claw_angles[0]
                self.claw_close_angle = claw_angles[1]
            
            
        except Exception as e:
            print(f"❌ 加载抓取参数失败，使用默认值: {e}")
            self._set_default_grasp_parameters()
    
    def _set_default_grasp_parameters(self):
        """设置默认抓取参数"""
        # 姿态参数（欧拉角）
        self.euler_yaw = 0.0
        self.euler_pitch = 0.0
        self.euler_roll = 180.0
        self.fixed_euler_angles = [0.0, 0.0, 180.0]
        
        # 姿态控制模式
        self.use_dynamic_pose = False  # 默认使用固定姿态
        
        # 运动参数
        self.motion_speed = 100
        self.motion_acceleration = 200
        
        # TCP修正参数（毫米）
        self.tcp_offset_x = 0.0
        self.tcp_offset_y = 0.0
        self.tcp_offset_z = 0.0
        
        # 夹爪角度参数
        self.claw_open_angle = 0.0    # 张开角度（默认0度 - 完全张开）
        self.claw_close_angle = 90.0  # 闭合角度（默认90度 - 完全闭合）
        
        print("📋 已设置默认抓取参数")

    def save_camera_config_to_file(self, camera_config):
        """保存相机参数到配置文件（保留其他配置不变）"""
        try:
            if not self.config_manager:
                print("⚠️ 配置管理器不可用，无法保存配置")
                QMessageBox.warning(None, "保存失败", "配置管理器不可用")
                return False
            
            # 获取现有的完整配置
            existing_config = self.config_manager.get_module_config("vision_grasp")
            
            # 更新相机相关的配置，保留其他配置不变
            if "camera" in camera_config:
                existing_config["camera"] = camera_config["camera"]
            if "sgbm" in camera_config:
                existing_config["sgbm"] = camera_config["sgbm"]
            if "depth_mode" in camera_config:
                existing_config["depth_mode"] = camera_config["depth_mode"]
            
            # 保存更新后的完整配置
            success = self.config_manager.save_module_config("vision_grasp", existing_config)
            
            if success:
                print("✅ 相机参数已保存到配置文件（其他参数保持不变）")
            else:
                print("❌ 相机参数保存失败")

            return success
            
        except Exception as e:
            print(f"❌ 保存配置文件失败: {e}")
            QMessageBox.warning(None, "保存失败", f"保存配置文件失败: {str(e)}")
            return False

    def setup_camera_params(self):
        """设置相机参数用于去畸变"""
        try:
            one_config = self.calibration_params.get("one", {})
            if not one_config:
                print("⚠️ 未找到单相机参数，将显示原始图像")
                return
            
            self.camera_matrix = np.array(one_config.get("camera_matrix", []), dtype=np.float64)
            self.camera_model = one_config.get("model", "pinhole")
            
            # 处理畸变系数
            camera_distortion = one_config.get("camera_distortion", [])
            if camera_distortion:
                if len(camera_distortion) > 0:
                    if isinstance(camera_distortion[0], list):
                        if len(camera_distortion[0]) > 1:
                            # 旧格式：[[-0.04169075, -0.10853007, ...]]
                            self.dist_coeffs = np.array(camera_distortion[0], dtype=np.float64)
                        else:
                            # 新格式：[[0.281...], [0.074...], ...]
                            self.dist_coeffs = np.array([row[0] for row in camera_distortion if len(row) > 0], dtype=np.float64)
                    else:
                        # 直接是数值列表
                        self.dist_coeffs = np.array(camera_distortion, dtype=np.float64)
                else:
                    self.dist_coeffs = np.zeros(4 if self.camera_model == 'fisheye' else 5, dtype=np.float64)
            else:
                self.dist_coeffs = np.zeros(4 if self.camera_model == 'fisheye' else 5, dtype=np.float64)
            
            
        except Exception as e:
            print(f"⚠️ 设置相机参数失败: {e}")

    def load_calibration_params(self):
        """加载标定参数"""
        try:
            config_path = os.path.join(project_root, "config", "calibration_parameter.json")
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            print(f"加载标定参数失败: {e}")
            return {}
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        
        # 创建相机控制区域（固定在顶部，不滚动）
        self.create_camera_control_group(layout)
        
        # 创建滚动区域包含其他内容
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)  # 去掉边框
        
        # 创建滚动内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # 创建双目相机显示区域
        self.create_camera_display_group(scroll_layout)
        
        # 创建抓取控制区域（包含坐标信息显示）
        self.create_grasp_control_group(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def create_camera_control_group(self, parent_layout):
        """创建相机控制组"""
        group = QGroupBox("双目相机控制")
        group.setMaximumHeight(130)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # 单行布局：参数设置 + 相机控制按钮
        control_layout = QHBoxLayout()
        
        # 参数设置按钮
        self.parameters_btn = QPushButton("⚙️ 相机参数")
        self.parameters_btn.setProperty("class", "primary")
        self.parameters_btn.clicked.connect(self.open_parameters_dialog)
        self.parameters_btn.setMinimumHeight(35)
        self.parameters_btn.setMinimumWidth(120)
        self.parameters_btn.setToolTip("设置相机设备和深度估计参数（启动相机前必须设置）")
        control_layout.addWidget(self.parameters_btn)
        
        # 视觉检测参数设置按钮（从阈值图区域移到这里）
        self.vision_params_btn = QPushButton("⚙️ 检测参数")
        self.vision_params_btn.clicked.connect(self.open_vision_params_dialog)
        self.vision_params_btn.setEnabled(False)  # 相机启动后启用
        self.vision_params_btn.setMinimumHeight(35)
        self.vision_params_btn.setMinimumWidth(120)
        self.vision_params_btn.setToolTip("设置HSV阈值和检测参数")
        control_layout.addWidget(self.vision_params_btn)
        
        # 抓取参数设置按钮
        self.grasp_params_btn = QPushButton("⚙️ 抓取参数")
        self.grasp_params_btn.clicked.connect(self.open_grasp_params_dialog)
        self.grasp_params_btn.setMinimumHeight(35)
        self.grasp_params_btn.setMinimumWidth(120)
        self.grasp_params_btn.setToolTip("设置末端姿态、运动参数和TCP修正")
        control_layout.addWidget(self.grasp_params_btn)
        
        control_layout.addSpacing(30)
        
        # 启动相机按钮
        self.start_camera_btn = QPushButton("📷 启动相机")
        self.start_camera_btn.setProperty("class", "success")
        self.start_camera_btn.clicked.connect(self.start_camera)
        self.start_camera_btn.setMinimumHeight(35)
        self.start_camera_btn.setMinimumWidth(120)
        self.start_camera_btn.setEnabled(False)  # 初始禁用，需要先设置参数
        control_layout.addWidget(self.start_camera_btn)
        
        # 停止相机按钮
        self.stop_camera_btn = QPushButton("⏹️ 停止相机")
        self.stop_camera_btn.setProperty("class", "danger")
        self.stop_camera_btn.clicked.connect(self.stop_camera)
        self.stop_camera_btn.setEnabled(False)
        self.stop_camera_btn.setMinimumHeight(35)
        self.stop_camera_btn.setMinimumWidth(120)
        control_layout.addWidget(self.stop_camera_btn)
        
        control_layout.addSpacing(15)
        

        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 第二行：状态显示
        status_layout = QHBoxLayout()
        
        # 参数状态显示
        self.params_status_label = QLabel("❌ 参数未设置")
        self.params_status_label.setStyleSheet("color: red; font-weight: bold; font-size: 12px;")
        status_layout.addWidget(self.params_status_label)
        
        status_layout.addSpacing(20)
        
        # 相机状态显示
        self.camera_status_label = QLabel("相机未启动")
        self.camera_status_label.setProperty("class", "status-disconnected")
        self.camera_status_label.setStyleSheet("font-size: 12px;")
        status_layout.addWidget(self.camera_status_label)
        
        status_layout.addSpacing(20)
        
        # 深度估计状态
        depth_status = "深度估计可用" if self.depth_estimator else "深度估计不可用"
        self.depth_estimation_status = QLabel(depth_status)
        self.depth_estimation_status.setStyleSheet(
            "color: green; font-weight: bold; font-size: 12px;" if self.depth_estimator else "color: red; font-weight: bold; font-size: 12px;"
        )
        status_layout.addWidget(self.depth_estimation_status)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        parent_layout.addWidget(group)
    
    def create_camera_display_group(self, parent_layout):
        """创建相机显示组"""
        group = QGroupBox("右相机 + 深度图显示 - 点击右相机获取目标坐标")
        layout = QHBoxLayout(group)
        layout.setSpacing(20)
        
        # 右相机显示（原始图像，与原始内参对应）
        right_layout = QVBoxLayout()
        right_title = QLabel("右相机（原始图像，点击获取坐标）")
        right_title.setAlignment(Qt.AlignCenter)
        right_title.setStyleSheet("font-weight: bold; color: #27ae60; font-size: 14px;")
        right_layout.addWidget(right_title)
        
        self.right_camera_label = CameraDisplayLabel()
        self.right_camera_label.setText("右相机（原始图像）")
        self.right_camera_label.clicked.connect(lambda x, y: self.on_camera_clicked(x, y, "right"))
        right_layout.addWidget(self.right_camera_label)
        layout.addLayout(right_layout)
        
        # 深度图显示
        depth_layout = QVBoxLayout()
        depth_title = QLabel("深度图（实时计算）")
        depth_title.setAlignment(Qt.AlignCenter)
        depth_title.setStyleSheet("font-weight: bold; color: #e74c3c; font-size: 14px;")
        depth_layout.addWidget(depth_title)
        
        self.depth_map_label = QLabel()
        # 🔥 关键设置：深度图也固定为640x480，与右相机保持一致
        self.depth_map_label.setFixedSize(640, 480)
        self.depth_map_label.setMinimumSize(640, 480)
        self.depth_map_label.setMaximumSize(640, 480)
        self.depth_map_label.setStyleSheet("border: 2px solid #e74c3c; background-color: #fdf2f2;")
        self.depth_map_label.setAlignment(Qt.AlignCenter)
        self.depth_map_label.setText("深度图\n（需要双目相机）")
        self.depth_map_label.setScaledContents(True)
        depth_layout.addWidget(self.depth_map_label)
        layout.addLayout(depth_layout)
        
        parent_layout.addWidget(group)
    
    def create_grasp_control_group(self, parent_layout):
        """创建抓取控制组 - 三列布局：阈值图 + 坐标信息 + 控制按钮"""
        group = QGroupBox("抓取控制")
        main_layout = QHBoxLayout(group)
        main_layout.setSpacing(20)  # 增加间距使布局更清晰
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # === 左侧：阈值图显示区域 ===
        threshold_frame = QFrame()
        threshold_frame.setFrameStyle(QFrame.StyledPanel)
        threshold_layout = QVBoxLayout(threshold_frame)
        threshold_layout.setContentsMargins(5, 5, 5, 5)
        threshold_layout.setSpacing(5)
        
        # 阈值图标题
        self.threshold_title = QLabel("🎯 视觉检测阈值图")
        self.threshold_title.setStyleSheet("font-weight: bold; color: #2c3e50;")
        self.threshold_title.setAlignment(Qt.AlignCenter)
        threshold_layout.addWidget(self.threshold_title)
        
        # 阈值图显示标签
        self.threshold_display_label = QLabel()
        self.threshold_display_label.setFixedSize(310, 225)  # 增大尺寸：从200x150改为300x225
        self.threshold_display_label.setStyleSheet("border: 1px solid #bdc3c7; background-color: #ecf0f1;")
        self.threshold_display_label.setAlignment(Qt.AlignCenter)
        self.threshold_display_label.setText("视觉检测未启用\n启动相机和视觉识别\n以查看阈值图\n(只显示最大目标)")
        self.threshold_display_label.setWordWrap(True)
        threshold_layout.addWidget(self.threshold_display_label)
        
        # 视觉识别按钮（从双目相机控制区域移到这里）
        self.vision_detection_btn = QPushButton("👁️ 视觉识别")
        self.vision_detection_btn.setProperty("class", "info")
        self.vision_detection_btn.clicked.connect(self.toggle_vision_detection)
        self.vision_detection_btn.setMinimumHeight(35)
        self.vision_detection_btn.setEnabled(False)  # 相机启动后才启用
        self.vision_detection_btn.setToolTip("开启/关闭视觉目标检测")
        threshold_layout.addWidget(self.vision_detection_btn)
        
        threshold_frame.setFixedWidth(320)  # 相应增大框架宽度：从220改为320
        main_layout.addWidget(threshold_frame)
        
        # === 中间：坐标信息显示区域 ===
        coord_frame = QFrame()
        coord_frame.setFrameStyle(QFrame.StyledPanel)
        coord_layout = QVBoxLayout(coord_frame)
        coord_layout.setContentsMargins(10, 10, 10, 10)
        coord_layout.setSpacing(8)
        
        # 坐标信息标题
        coord_title = QLabel("📊 坐标信息")
        coord_title.setAlignment(Qt.AlignCenter)
        coord_title.setStyleSheet("font-weight: bold; color: #3498db; font-size: 14px;")
        coord_layout.addWidget(coord_title)
        
        # 创建信息显示表格
        self.coord_table = QTableWidget()
        self.coord_table.setRowCount(7)  # 增加一行用于显示旋转角度
        self.coord_table.setColumnCount(2)
        self.coord_table.setHorizontalHeaderLabels(["参数", "值"])
        self.coord_table.verticalHeader().setVisible(False)
        self.coord_table.setEditTriggers(QTableWidget.NoEditTriggers)
        
        # 初始化表格内容
        self.coord_table.setItem(0, 0, QTableWidgetItem("像素坐标"))
        self.coord_table.setItem(0, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(1, 0, QTableWidgetItem("旋转角度"))
        self.coord_table.setItem(1, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(2, 0, QTableWidgetItem("深度信息"))
        self.coord_table.setItem(2, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(3, 0, QTableWidgetItem("相机坐标"))
        self.coord_table.setItem(3, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(4, 0, QTableWidgetItem("末端坐标"))
        self.coord_table.setItem(4, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(5, 0, QTableWidgetItem("基底坐标"))
        self.coord_table.setItem(5, 1, QTableWidgetItem("--"))
        self.coord_table.setItem(6, 0, QTableWidgetItem("关节角度"))
        self.coord_table.setItem(6, 1, QTableWidgetItem("--"))
        
        # 设置表格属性
        self.coord_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.coord_table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self.coord_table.setFixedSize(450, 315)  # 增加高度以适应新的行数
        
        # 设置行高以优化显示效果
        for i in range(7):  # 现在有7行
            self.coord_table.setRowHeight(i, 35)  # 设置每行高度为35像素
        
        # 设置表格样式
        self.coord_table.setStyleSheet("""
            QTableWidget {
                border: 2px solid #3498db;
                background-color: #f8f9fa;
                alternate-background-color: #e9ecef;
                selection-background-color: #3498db;
            }
            QHeaderView::section {
                background-color: #3498db;
                color: white;
                font-weight: bold;
                border: none;
                padding: 6px;
            }
        """)
        
        coord_layout.addWidget(self.coord_table)
        coord_frame.setFixedWidth(470)  # 增大宽度从370到470，匹配表格宽度
        main_layout.addWidget(coord_frame)
        
        # === 右侧：控制按钮区域 ===
        control_frame = QFrame()
        control_frame.setFrameStyle(QFrame.StyledPanel)
        control_layout = QVBoxLayout(control_frame)
        control_layout.setContentsMargins(30, 15, 15, 15)  # 增加左边距，使按钮向右偏移
        control_layout.setSpacing(15)
        
        # 添加顶部间距，使按钮更靠右侧中央
        control_layout.addStretch(1)
        
        # 第一行按钮
        control_row1 = QHBoxLayout()
        control_row1.setSpacing(15)
        control_row1.addStretch(1)  # 增加左侧弹性空间，进一步向右偏移
        
        self.photo_position_btn = QPushButton("📸 运动到拍照位置")
        self.photo_position_btn.setProperty("class", "warning")
        self.photo_position_btn.clicked.connect(self.move_to_photo_position)
        self.photo_position_btn.setEnabled(False)
        self.photo_position_btn.setMinimumHeight(50)
        self.photo_position_btn.setMinimumWidth(180)
        self.photo_position_btn.setToolTip("运动到标准拍照位置 [0°, 0°, 0°, 0°, 90°, 0°]")
        control_row1.addWidget(self.photo_position_btn)
        
        self.grasp_btn = QPushButton("🤖 执行抓取")
        self.grasp_btn.setProperty("class", "success")
        self.grasp_btn.clicked.connect(self.execute_grasp)
        self.grasp_btn.setEnabled(False)
        self.grasp_btn.setMinimumHeight(50)
        self.grasp_btn.setMinimumWidth(150)
        self.grasp_btn.setToolTip("根据当前参数执行抓取动作")
        control_row1.addWidget(self.grasp_btn)
        
        control_row1.addStretch(1)  # 右侧添加弹性空间
        control_layout.addLayout(control_row1)
        
        # 第二行按钮
        control_row2 = QHBoxLayout()
        control_row2.setSpacing(15)
        control_row2.addStretch(1)  # 增加左侧弹性空间，与第一行保持一致
        
        # 获取识别位置按钮
        self.get_detection_pos_btn = QPushButton("🎯 获取识别位置")
        self.get_detection_pos_btn.setProperty("class", "info")
        self.get_detection_pos_btn.clicked.connect(self.get_detection_position)
        self.get_detection_pos_btn.setEnabled(False)  # 启动视觉识别后启用
        self.get_detection_pos_btn.setMinimumHeight(45)
        self.get_detection_pos_btn.setMinimumWidth(160)
        self.get_detection_pos_btn.setToolTip("获取当前检测到的目标中心位置，用于自动抓取")
        control_row2.addWidget(self.get_detection_pos_btn)
        
        self.stop_motion_btn = QPushButton("⏹️ 停止运动")
        self.stop_motion_btn.setProperty("class", "danger")
        self.stop_motion_btn.clicked.connect(self.stop_motion)
        self.stop_motion_btn.setEnabled(False)
        self.stop_motion_btn.setMinimumHeight(45)
        self.stop_motion_btn.setMinimumWidth(140)
        self.stop_motion_btn.setToolTip("立即停止所有电机运动")
        control_row2.addWidget(self.stop_motion_btn)
        
        control_row2.addStretch(1)  # 右侧添加弹性空间
        control_layout.addLayout(control_row2)
        
        # 第三行按钮 - 夹爪控制
        control_row3 = QHBoxLayout()
        control_row3.setSpacing(15)
        control_row3.addStretch(1)  # 增加左侧弹性空间，与其他行保持一致
        
        # 夹爪张开按钮
        self.claw_open_btn = QPushButton("🤏 夹爪张开")
        self.claw_open_btn.setProperty("class", "info")
        self.claw_open_btn.clicked.connect(self.open_claw)
        self.claw_open_btn.setEnabled(False)  # 初始禁用，连接夹爪后启用
        self.claw_open_btn.setMinimumHeight(45)
        self.claw_open_btn.setMinimumWidth(140)
        self.claw_open_btn.setToolTip("张开夹爪（需要先连接夹爪）")
        control_row3.addWidget(self.claw_open_btn)
        
        # 夹爪闭合按钮
        self.claw_close_btn = QPushButton("✋ 夹爪闭合")
        self.claw_close_btn.setProperty("class", "info")  # 改为与张开按钮相同的颜色
        self.claw_close_btn.clicked.connect(self.close_claw)
        self.claw_close_btn.setEnabled(False)  # 初始禁用，连接夹爪后启用
        self.claw_close_btn.setMinimumHeight(45)
        self.claw_close_btn.setMinimumWidth(140)
        self.claw_close_btn.setToolTip("闭合夹爪（需要先连接夹爪）")
        control_row3.addWidget(self.claw_close_btn)
        
        control_row3.addStretch(1)  # 右侧添加弹性空间
        control_layout.addLayout(control_row3)
        
        # 添加底部间距
        control_layout.addStretch(1)
        
        main_layout.addWidget(control_frame)
        
        parent_layout.addWidget(group)
        
        # 创建隐藏的参数控件（用于内部逻辑，但不显示在界面上）
        self.create_hidden_parameter_widgets()
    
    def create_hidden_parameter_widgets(self):
        """创建隐藏的参数控件（用于内部逻辑）"""
        # 深度参数 - 使用从配置文件加载的值
        self.depth_mode_combo = QComboBox()
        self.depth_mode_combo.addItems(["双目深度估计", "固定深度"])
        # 根据加载的参数设置当前模式
        if self.use_depth_estimation:
            self.depth_mode_combo.setCurrentIndex(0)
        else:
            self.depth_mode_combo.setCurrentIndex(1)
        self.depth_mode_combo.currentTextChanged.connect(self.on_depth_mode_changed)
        
        self.depth_spin = QDoubleSpinBox()
        self.depth_spin.setRange(1.0, 1000.0)
        self.depth_spin.setValue(self.fixed_depth_value)  # 使用加载的固定深度值
        self.depth_spin.setDecimals(1)
        self.depth_spin.setEnabled(not self.use_depth_estimation)
        
        # SGBM参数 - 使用从配置文件加载的值
        self.min_disparity_spin = QSpinBox()
        self.min_disparity_spin.setRange(-64, 64)
        self.min_disparity_spin.setValue(self.sgbm_min_disparity)
        self.min_disparity_spin.valueChanged.connect(self.on_sgbm_params_changed)
        
        self.num_disparities_spin = QSpinBox()
        self.num_disparities_spin.setRange(16, 256)
        self.num_disparities_spin.setSingleStep(16)
        self.num_disparities_spin.setValue(self.sgbm_num_disparities)
        self.num_disparities_spin.valueChanged.connect(self.on_sgbm_params_changed)
        
        self.block_size_spin = QSpinBox()
        self.block_size_spin.setRange(3, 21)
        self.block_size_spin.setSingleStep(2)
        self.block_size_spin.setValue(self.sgbm_block_size)
        self.block_size_spin.valueChanged.connect(self.on_sgbm_params_changed)
        
        self.uniqueness_spin = QSpinBox()
        self.uniqueness_spin.setRange(1, 50)
        self.uniqueness_spin.setValue(self.sgbm_uniqueness)
        self.uniqueness_spin.valueChanged.connect(self.on_sgbm_params_changed)
        
        # 姿态参数
        self.yaw_spin = QDoubleSpinBox()
        self.yaw_spin.setRange(-180, 180)
        self.yaw_spin.setValue(self.fixed_euler_angles[0])
        
        self.pitch_spin = QDoubleSpinBox()
        self.pitch_spin.setRange(-180, 180)
        self.pitch_spin.setValue(self.fixed_euler_angles[1])
        
        self.roll_spin = QDoubleSpinBox()
        self.roll_spin.setRange(-180, 180)
        self.roll_spin.setValue(self.fixed_euler_angles[2])
        
        # 运动参数
        self.motion_speed_spin = QSpinBox()
        self.motion_speed_spin.setRange(1, 1000)
        self.motion_speed_spin.setValue(100)
        
        self.motion_acc_spin = QSpinBox()
        self.motion_acc_spin.setRange(1, 5000)
        self.motion_acc_spin.setValue(200)
    
    def set_sgbm_widgets_enabled(self, enabled):
        """设置SGBM参数控件的启用/禁用状态"""
        if hasattr(self, 'min_disparity_spin'):
            self.min_disparity_spin.setEnabled(enabled)
        if hasattr(self, 'num_disparities_spin'):
            self.num_disparities_spin.setEnabled(enabled)
        if hasattr(self, 'block_size_spin'):
            self.block_size_spin.setEnabled(enabled)
        if hasattr(self, 'uniqueness_spin'):
            self.uniqueness_spin.setEnabled(enabled)
        
        # 主界面没有重置按钮，所以不需要控制它
    
    def update_parameter_status(self):
        """更新参数配置状态显示"""
        if self.parameters_configured:
            self.params_status_label.setText(f"✅ 参数已设置 (设备ID: {self.camera_device_id})")
            self.params_status_label.setStyleSheet("color: green; font-weight: bold;")
            self.start_camera_btn.setEnabled(True)
            self.start_camera_btn.setToolTip(f"启动相机设备 {self.camera_device_id}")
        else:
            self.params_status_label.setText("❌ 参数未设置")
            self.params_status_label.setStyleSheet("color: red; font-weight: bold;")
            self.start_camera_btn.setEnabled(False)
            self.start_camera_btn.setToolTip("请先设置参数才能启动相机")
    
    
    def open_parameters_dialog(self):
        """打开参数设置对话框"""
        try:
            # 创建参数设置对话框
            dialog = VisionGraspParametersDialog(self, self.depth_estimator)
            
            # 显示对话框
            result = dialog.exec_()
            
            if result == QDialog.Accepted:
                print("✅ 参数设置对话框已关闭")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开参数设置失败: {str(e)}")
            print(f"参数设置对话框错误: {e}")
    

    
    def start_camera(self):
        """启动双目相机"""
        # 检查参数是否已设置
        if not self.parameters_configured:
            QMessageBox.warning(
                self, 
                "参数未设置", 
                "请先进行参数设置才能启动相机！\n\n点击上方的 '⚙️ 参数设置' 按钮配置抓取参数。"
            )
            return
        
        try:
            camera_device = self.camera_device_id
            
            # 初始化相机
            self.camera = cv2.VideoCapture(camera_device)
            
            if not self.camera.isOpened():
                QMessageBox.warning(self, "错误", f"无法打开相机设备 {camera_device}")
                return
            
            # 设置相机分辨率为1280x480（左右各640x480）
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # 启动相机显示定时器
            self.camera_timer = QTimer()
            self.camera_timer.timeout.connect(self.update_camera_display)
            self.camera_timer.start(33)  # 约30FPS
            
            self.camera_running = True
            self.camera_status_label.setText("双目相机运行中")
            self.camera_status_label.setProperty("class", "status-connected")
            self.start_camera_btn.setEnabled(False)
            self.stop_camera_btn.setEnabled(True)
            
            # 启用视觉识别按钮和检测参数按钮
            self.vision_detection_btn.setEnabled(True)
            self.vision_params_btn.setEnabled(True)
            
            # 启用右相机点击
            self.right_camera_label.set_camera_active(True)
            
            # 初始化视觉检测器
            self.initialize_vision_detector()
            
            QMessageBox.information(self, "成功", f"双目相机启动成功！\n设备ID: {camera_device}\n右相机现在可以点击获取坐标")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动相机失败: {str(e)}")

    def stop_camera(self):
        """停止双目相机"""
        try:
            self.camera_running = False
            
            # 停止并清理定时器
            if self.camera_timer:
                self.camera_timer.stop()
                self.camera_timer.deleteLater()  # 确保定时器被正确删除
                self.camera_timer = None
            
            # 释放相机资源
            if self.camera:
                try:
                    self.camera.release()
                except Exception as e:
                    print(f"⚠️ 释放相机资源时出错: {e}")
                finally:
                    self.camera = None
            
            # 重置去畸变映射
            self.undistort_maps = None
            
            # 清空当前帧
            self.current_left_frame = None
            self.current_right_frame = None
            
            # 禁用右相机点击
            if hasattr(self, 'right_camera_label'):
                self.right_camera_label.set_camera_active(False)
            
            # 清空显示
            if hasattr(self, 'right_camera_label'):
                self.right_camera_label.clear()
                self.right_camera_label.setText("右相机（原始图像）\n请先启动相机")
            if hasattr(self, 'depth_map_label'):
                self.depth_map_label.clear()
                self.depth_map_label.setText("深度图\n（需要双目相机）")
            
            # 更新状态标签
            if hasattr(self, 'camera_status_label'):
                self.camera_status_label.setText("相机已停止")
                self.camera_status_label.setProperty("class", "status-disconnected")
            
            # 更新按钮状态
            if hasattr(self, 'start_camera_btn'):
                # 只有在参数已配置时才启用启动按钮
                self.start_camera_btn.setEnabled(self.parameters_configured)
            if hasattr(self, 'stop_camera_btn'):
                self.stop_camera_btn.setEnabled(False)
            
            # 禁用视觉识别相关功能
            if hasattr(self, 'vision_detection_btn'):
                self.vision_detection_btn.setEnabled(False)
            self.vision_detection_enabled = False
            if hasattr(self, 'vision_params_btn'):
                self.vision_params_btn.setEnabled(False)
            self.detected_objects = []
            
            # 重置获取识别位置功能
            if hasattr(self, 'get_detection_pos_btn'):
                self.get_detection_pos_btn.setEnabled(False)
                self.get_detection_pos_btn.setText("🎯 获取识别位置")
                self.get_detection_pos_btn.setProperty("class", "info")
                self.get_detection_pos_btn.style().unpolish(self.get_detection_pos_btn)
                self.get_detection_pos_btn.style().polish(self.get_detection_pos_btn)
            self.detected_center_point = None
            self.use_detected_position = False
            
            # 重置抓取按钮
            if hasattr(self, 'grasp_btn'):
                self.grasp_btn.setText("🤖 执行抓取")
                self.grasp_btn.setToolTip("根据当前参数执行抓取动作")
            
            # 清空阈值图显示
            if hasattr(self, 'threshold_display_label'):
                self.threshold_display_label.clear()
                self.threshold_display_label.setText("视觉检测未启用\n启动相机和视觉识别\n以查看阈值图\n(只显示最大目标)")
            
            print("✅ 相机已成功停止")
            
        except Exception as e:
            print(f"❌ 停止相机时发生错误: {e}")
            if hasattr(self, 'parent') and self.parent():
                QMessageBox.warning(self, "错误", f"停止相机失败: {str(e)}")

    def update_camera_display(self):
        """更新相机显示"""
        if not self.camera_running or not self.camera:
            return
        
        try:
            ret, frame = self.camera.read()
            if not ret:
                print("无法读取摄像头画面")
                return
            
            # 分离左右摄像头画面（左右并排排列）
            frame_L = frame[:, 0:640]  # 左侧画面
            frame_R = frame[:, 640:1280]  # 右侧画面
            
            # 存储当前帧用于深度计算
            self.current_left_frame = frame_L.copy()
            self.current_right_frame = frame_R.copy()
            
            # 处理视觉检测
            detected_frame_R = frame_R.copy()
            threshold_image = None
            
            if self.vision_detection_enabled and self.vision_detector:
                try:
                    detection_result = None
                    threshold_image = None
                    
                    # 根据检测类型执行相应的检测方法
                    if self.detection_type == "color":
                        # 颜色检测
                        detection_result = self.vision_detector.detect_color(
                            frame_R, 
                            self.hsv_lower, 
                            self.hsv_upper, 
                            min_area=self.min_area,
                            undistort=False  # 已经是校正后的图像
                        )
                        
                        # 生成颜色阈值图用于显示
                        hsv_frame = cv2.cvtColor(frame_R, cv2.COLOR_BGR2HSV)
                        threshold_mask = cv2.inRange(hsv_frame, 
                                                   np.array(self.hsv_lower, dtype=np.uint8), 
                                                   np.array(self.hsv_upper, dtype=np.uint8))
                        # 应用中值滤波减少噪点
                        threshold_mask = cv2.medianBlur(threshold_mask, 5)
                        # 转换为3通道用于显示
                        threshold_image = cv2.cvtColor(threshold_mask, cv2.COLOR_GRAY2BGR)
                        
                    elif self.detection_type == "circle":
                        # 圆形检测
                        detection_result = self.vision_detector.detect_circles(
                            frame_R,
                            dp=self.circle_dp,
                            minDist=self.circle_min_dist,
                            param1=self.circle_param1,
                            param2=self.circle_param2,
                            minRadius=self.circle_min_radius,
                            maxRadius=self.circle_max_radius,
                            undistort=False
                        )
                        
                        # 生成边缘检测图用于显示
                        gray = cv2.cvtColor(frame_R, cv2.COLOR_BGR2GRAY)
                        edges = cv2.Canny(gray, 50, 150)
                        threshold_image = cv2.cvtColor(edges, cv2.COLOR_GRAY2BGR)
                        
                    elif self.detection_type == "qrcode":
                        # 二维码检测
                        detection_result = self.vision_detector.detect_qrcode(
                            frame_R,
                            undistort=False
                        )
                        
                        # 生成灰度图用于显示
                        gray = cv2.cvtColor(frame_R, cv2.COLOR_BGR2GRAY)
                        threshold_image = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                    
                    # 更新检测结果
                    if detection_result:
                        all_objects = detection_result['objects']
                        
                        # 只保留面积最大的对象
                        if all_objects and detection_result['success']:
                            # 按面积排序，面积 = size[0] * size[1]
                            sorted_objects = sorted(all_objects, key=lambda obj: obj['size'][0] * obj['size'][1], reverse=True)
                            # 只取面积最大的一个
                            self.detected_objects = [sorted_objects[0]]
                        else:
                            self.detected_objects = []
                        
                        # 在右相机画面上绘制检测结果
                        if detection_result['success'] and self.detected_objects:
                            for i, obj in enumerate(self.detected_objects):
                                # 获取对象信息
                                center = obj['center']
                                size = obj['size']
                                angle = obj['angle']  # 原始角度
                                short_edge_angle = obj.get('short_edge_angle', angle)  # 短边角度
                                box_points = obj['box_points']
                                
                                # 根据检测类型选择不同颜色
                                if self.detection_type == "color":
                                    color = (0, 255, 0)  # 绿色
                                    label_prefix = "Color"
                                elif self.detection_type == "circle":
                                    color = (255, 165, 0)  # 橙色
                                    label_prefix = "Circle"
                                elif self.detection_type == "qrcode":
                                    color = (255, 0, 255)  # 紫色
                                    label_prefix = "QR"
                                
                                # 绘制旋转矩形（使用四个角点）
                                box_points_array = np.array(box_points, dtype=np.int32)
                                cv2.drawContours(detected_frame_R, [box_points_array], 0, color, 2)
                                
                                # 绘制标签（显示短边角度，这是抓取时实际使用的角度）
                                label_text = f"{label_prefix}#MAX ({short_edge_angle:.1f}°)"
                                cv2.putText(detected_frame_R, label_text, (center[0]-50, center[1]-20), 
                                          cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
                                
                                # 绘制中心点
                                cv2.circle(detected_frame_R, center, 3, (0, 0, 255), -1)
                                
                                # 绘制方向指示线（从中心指向矩形的一个角）
                                if box_points:
                                    direction_point = box_points[0]  # 使用第一个角点作为方向指示
                                    cv2.line(detected_frame_R, center, direction_point, (255, 255, 0), 1)
                    
                except Exception as e:
                    print(f"视觉检测失败: {e}")
            
            # 右画面：显示原始图像或带检测结果的图像（与原始内参对应，确保2D转3D计算准确）
            self.display_frame(detected_frame_R, self.right_camera_label)
            
            # 更新阈值图显示
            if threshold_image is not None:
                self.display_threshold_image(threshold_image)
            
            # 深度图：使用双目深度估计
            if self.depth_estimator and self.use_depth_estimation:
                try:
                    depth_map, disparity_map = self.depth_estimator.create_depth_map(frame_L, frame_R)
                    depth_vis = self.depth_estimator.visualize_depth(depth_map, disparity_map)
                    self.display_frame(depth_vis, self.depth_map_label)
                except Exception as e:
                    print(f"深度图计算失败: {e}")
                    self.depth_map_label.setText("深度图计算失败")
            else:
                self.depth_map_label.setText("深度图\n（需要双目深度估计）")
                
        except Exception as e:
            print(f"更新相机显示失败: {e}")
    
    def display_frame(self, frame, label):
        """显示帧到标签"""
        try:
            # 复制帧以避免修改原始数据
            display_frame = frame.copy()
            
            # 在右相机标签上画中心点
            if label == self.right_camera_label:
                # 获取图像中心坐标（使用相机主点）
                if self.camera_matrix is not None:
                    cx = int(self.camera_matrix[0, 2])  # 主点x坐标
                    cy = int(self.camera_matrix[1, 2])  # 主点y坐标
                else:
                    # 如果没有标定参数，使用图像中心
                    h, w = display_frame.shape[:2]
                    cx = w // 2
                    cy = h // 2
                
                # 画红色十字和圆圈标记中心点
                # 画圆圈（外圈）
                cv2.circle(display_frame, (cx, cy), 10, (0, 0, 255), 2)  # 红色圆圈
                # 画实心小圆（中心点）
                cv2.circle(display_frame, (cx, cy), 3, (0, 0, 255), -1)  # 红色实心圆
                # 画十字线
                cv2.line(display_frame, (cx - 15, cy), (cx + 15, cy), (0, 0, 255), 1)  # 水平线
                cv2.line(display_frame, (cx, cy - 15), (cx, cy + 15), (0, 0, 255), 1)  # 垂直线
                
            
            # 转换颜色格式
            rgb_frame = cv2.cvtColor(display_frame, cv2.COLOR_BGR2RGB)
            h, w, ch = rgb_frame.shape
            bytes_per_line = ch * w
            
            # 创建QImage
            qt_image = QImage(rgb_frame.data, w, h, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap并显示
            pixmap = QPixmap.fromImage(qt_image)
            label.setPixmap(pixmap)
            
        except Exception as e:
            print(f"显示帧失败: {e}")
    
    def on_depth_mode_changed(self, mode):
        """深度模式切换处理"""
        self.use_depth_estimation = (mode == "双目深度估计")
        self.depth_spin.setEnabled(not self.use_depth_estimation)
        
        # 控制SGBM参数组的启用/禁用状态
        if hasattr(self, 'sgbm_group'):
            self.set_sgbm_widgets_enabled(self.use_depth_estimation)
        
        # 允许用户设置SGBM参数，即使深度估计器不可用
        if self.use_depth_estimation and not self.depth_estimator:
            print("⚠️ 深度估计器不可用，但允许用户预设SGBM参数")

    def on_sgbm_params_changed(self):
        """SGBM参数改变时更新深度估计器"""
        if not self.depth_estimator:
            return
        
        try:
            # 确保num_disparities是16的倍数
            num_disp = self.num_disparities_spin.value()
            if num_disp % 16 != 0:
                num_disp = (num_disp // 16) * 16
                self.num_disparities_spin.setValue(num_disp)
            
            # 确保block_size是奇数
            block_size = self.block_size_spin.value()
            if block_size % 2 == 0:
                block_size += 1
                self.block_size_spin.setValue(block_size)
            
            # 更新深度估计器的SGBM参数
            self.update_depth_estimator_params()
            
            print(f"SGBM参数更新: 最小视差={self.min_disparity_spin.value()}, "
                  f"视差范围={num_disp}, 块大小={block_size}, 唯一性={self.uniqueness_spin.value()}")
            
        except Exception as e:
            print(f"更新SGBM参数失败: {e}")

    def reset_sgbm_params(self):
        """重置SGBM参数为默认值"""
        self.min_disparity_spin.setValue(0)
        self.num_disparities_spin.setValue(128)
        self.block_size_spin.setValue(5)
        self.uniqueness_spin.setValue(10)
        self.update_depth_estimator_params()
        print("✅ SGBM参数已重置为默认值")

    def update_depth_estimator_params(self):
        """更新深度估计器的SGBM参数"""
        if not self.depth_estimator:
            return
        
        try:
            min_disparity = self.min_disparity_spin.value()
            num_disparities = self.num_disparities_spin.value()
            block_size = self.block_size_spin.value()
            uniqueness_ratio = self.uniqueness_spin.value()
            
            # 计算P1和P2参数
            P1 = 8 * 3 * block_size ** 2
            P2 = 32 * 3 * block_size ** 2
            
            # 重新创建立体匹配器
            self.depth_estimator.stereo_matcher = cv2.StereoSGBM_create(
                minDisparity=min_disparity,
                numDisparities=num_disparities,
                blockSize=block_size,
                P1=P1,
                P2=P2,
                disp12MaxDiff=1,
                uniquenessRatio=uniqueness_ratio,
                speckleWindowSize=200,
                speckleRange=32,
                preFilterCap=63,
                mode=cv2.STEREO_SGBM_MODE_SGBM_3WAY
            )
            
        except Exception as e:
            print(f"❌ 更新深度估计器参数失败: {e}")

    def on_camera_clicked(self, x, y, camera_side):
        """相机点击事件处理"""
        try:
            # 检查相机是否运行
            if not self.camera_running:
                QMessageBox.warning(self, "提示", "请先启动相机才能点击获取坐标")
                return
            
            # 只处理右相机点击
            if camera_side != "right":
                return
            
            # 显示尺寸固定为640x480，直接使用原始坐标
            actual_x = int(x)
            actual_y = int(y)
            
            
            # 重置识别位置状态（使用手动点击时）
            if self.use_detected_position:
                self.use_detected_position = False
                self.detected_center_point = None
                # 重置获取识别位置按钮状态
                self.get_detection_pos_btn.setText("🎯 获取识别位置")
                self.get_detection_pos_btn.setProperty("class", "info")
                self.get_detection_pos_btn.style().unpolish(self.get_detection_pos_btn)
                self.get_detection_pos_btn.style().polish(self.get_detection_pos_btn)
                print("🖱️ 已切换到手动点击模式，重置识别位置状态")
            
            # 更新像素坐标显示（手动点击时没有旋转角度信息）
            self.coord_table.setItem(0, 1, QTableWidgetItem(f"({actual_x}, {actual_y}) - 右相机"))
            
            # 显示手动点击状态和当前姿态模式
            mode_text = f"当前: {'动态' if self.use_dynamic_pose else '固定'}姿态模式"
            self.coord_table.setItem(1, 1, QTableWidgetItem(f"手动点击 - 无角度信息 ({mode_text})"))
            
            # 执行坐标转换
            self.convert_coordinates(actual_x, actual_y, camera_side)
            
            # 启用抓取按钮
            if self.motors:
                self.grasp_btn.setEnabled(True)
                self.grasp_btn.setText("🤖 执行抓取")  # 重置为手动抓取文本
                pose_mode_desc = "动态姿态" if self.use_dynamic_pose else "固定姿态"
                self.grasp_btn.setToolTip(f"使用手动点击位置执行抓取\n姿态模式: {pose_mode_desc} (手动点击无旋转信息)")
                self.stop_motion_btn.setEnabled(True)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"处理点击事件失败: {str(e)}")

    def convert_coordinates(self, u, v, camera_side):
        """坐标转换：像素坐标 -> 基底坐标（使用深度估计或固定深度）"""
        try:
            # 只处理右相机的点击
            if camera_side != "right":
                QMessageBox.warning(self, "提示", "只有右相机支持点击获取坐标")
                return
            
            # 使用单相机参数（右相机的鱼眼参数）
            one_config = self.calibration_params.get("one", {})
            if not one_config:
                QMessageBox.warning(self, "错误", "未找到单相机标定参数")
                return
            
            if self.camera_matrix is None or self.dist_coeffs is None:
                QMessageBox.warning(self, "错误", "相机参数未正确加载")
                return
            
            
            # 获取深度值（统一使用毫米）
            if self.use_depth_estimation and self.depth_estimator and \
               self.current_left_frame is not None and self.current_right_frame is not None:
                # 使用双目深度估计
                try:
                    # 显示尺寸固定为640x480，直接使用原始坐标
                    actual_u = int(u)
                    actual_v = int(v)
                    
                    # 计算真实深度（米）
                    disparity_map = self.depth_estimator.compute_disparity(
                        self.current_left_frame, self.current_right_frame
                    )
                    Z_meters = self.depth_estimator.estimate_depth_region(actual_u, actual_v, disparity_map)
                    
                    if Z_meters is None:
                        QMessageBox.warning(self, "警告", "无法获取该点的深度，使用固定深度")
                        Z_mm = self.depth_spin.value()  # 现在是毫米单位，无需转换
                        depth_info = f"固定深度: {Z_mm:.1f}mm"
                    else:
                        Z_mm = Z_meters * 1000.0  # 双目估计结果从米转换为毫米
                        print(f"✅ 双目深度估计: {Z_mm:.1f}mm")
                        depth_info = f"双目估计: {Z_mm:.1f}mm"
                        
                except Exception as e:
                    print(f"深度估计失败: {e}")
                    Z_mm = self.depth_spin.value()  # 固定深度是毫米，加100毫米作为误差补偿
                    depth_info = f"固定深度: {Z_mm:.1f}mm (估计失败)"
                    QMessageBox.warning(self, "警告", f"深度估计失败，使用固定深度: {Z_mm:.1f}mm")
            else:
                # 使用固定深度
                Z_mm = self.depth_spin.value()  # 现在是毫米单位，无需转换
                depth_info = f"固定深度: {Z_mm:.1f}mm"
                print(f"使用固定深度: {Z_mm:.1f}mm")
            
            # 更新深度信息显示（现在是第2行，索引为2）
            self.coord_table.setItem(2, 1, QTableWidgetItem(depth_info))
            
            # 计算相机坐标（毫米）- 使用原始内参K与原始图像像素坐标对应
            fx = self.camera_matrix[0, 0]
            fy = self.camera_matrix[1, 1]
            cx = self.camera_matrix[0, 2]
            cy = self.camera_matrix[1, 2]
            
            # 计算相机坐标（毫米）- 原始图像像素直接用原始内参转换
            X_mm = (u - cx) * Z_mm / fx
            Y_mm = (v - cy) * Z_mm / fy
            
            # 相机坐标（齐次，毫米单位）
            P_camera_homogeneous = np.array([X_mm, Y_mm, Z_mm, 1.0], dtype=np.float64).reshape(4, 1)
            
            # 更新相机坐标显示（现在是第3行，索引为3）
            self.coord_table.setItem(3, 1, QTableWidgetItem(f"({X_mm:.1f}, {Y_mm:.1f}, {Z_mm:.1f}) mm"))
            
            # 获取手眼标定矩阵
            RT_camera2end = np.array(self.calibration_params.get("eyeinhand", {}).get("RT_camera2end", []), dtype=np.float64)
            if RT_camera2end.size == 0:
                QMessageBox.warning(self, "错误", "未找到手眼标定参数")
                return
            RT_camera2end = RT_camera2end.reshape(4, 4)
            RT_camera2end[0:3, 3] = RT_camera2end[0:3, 3] * 1000.0   #转成毫米
            
            # 相机坐标 -> 末端坐标（毫米）
            P_end_homogeneous = RT_camera2end @ P_camera_homogeneous
            
            self.coord_table.setItem(4, 1, QTableWidgetItem(
                f"({P_end_homogeneous[0,0]:.1f}, {P_end_homogeneous[1,0]:.1f}, {P_end_homogeneous[2,0]:.1f}) mm (法兰中心)"
            ))
            
            # 获取当前机械臂末端位姿
            current_pose = self.get_current_arm_pose()
            if current_pose is None:
                QMessageBox.warning(self, "错误", "无法获取当前机械臂位姿，请确保机械臂已连接")
                return
            
            # 末端到基底
            RT_end2base = self.pose_to_homogeneous_matrix(current_pose)
            
            # 末端坐标转基底坐标
            P_base_homogeneous = RT_end2base @ P_end_homogeneous
            
            # 坐标系转换调整 - 统一使用毫米作为单位
            x_base_mm = P_base_homogeneous[0, 0]  # 毫米单位
            y_base_mm = P_base_homogeneous[1, 0]  
            z_base_mm = -P_base_homogeneous[2, 0]   # Z轴取反,机朝向与基底 Z 轴相反,所以要加负号
            
            # 应用TCP修正 - 在基底坐标系中应用偏移量
            tcp_corrected_x = x_base_mm + self.tcp_offset_x  # 基底坐标系X轴偏移
            tcp_corrected_y = y_base_mm + self.tcp_offset_y  # 基底坐标系Y轴偏移
            tcp_corrected_z = z_base_mm + self.tcp_offset_z  # 基底坐标系Z轴偏移
            
            # 存储目标坐标用于抓取（毫米，含TCP修正）
            self.target_coords = [tcp_corrected_x, tcp_corrected_y, tcp_corrected_z]
            
            # 更新基底坐标显示（毫米）（现在是第5行，索引为5）
            if abs(self.tcp_offset_x) > 0.01 or abs(self.tcp_offset_y) > 0.01 or abs(self.tcp_offset_z) > 0.01:
                # 显示TCP修正后的坐标
                self.coord_table.setItem(5, 1, QTableWidgetItem(
                    f"({tcp_corrected_x:.1f}, {tcp_corrected_y:.1f}, {tcp_corrected_z:.1f}) mm (含TCP修正)"
                ))

            else:
                # 没有TCP修正时显示原始基底坐标
                self.coord_table.setItem(5, 1, QTableWidgetItem(
                    f"({x_base_mm:.1f}, {y_base_mm:.1f}, {z_base_mm:.1f}) mm (法兰中心)"
                ))
                print(f"坐标转换完成: 基底坐标({x_base_mm:.1f}, {y_base_mm:.1f}, {z_base_mm:.1f}) mm")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"坐标转换失败: {str(e)}")
            print(f"坐标转换错误详情: {e}")
    
    def pose_to_homogeneous_matrix(self, pose):
        """将位姿转换为齐次变换矩阵（统一使用毫米单位）"""
        x, y, z, yaw, pitch, roll = pose
        
        # 位置保持毫米单位
        x_mm, y_mm, z_mm = x, y, z
        
        # 角度转换为弧度
        yaw_rad = np.deg2rad(yaw)
        pitch_rad = np.deg2rad(pitch)
        roll_rad = np.deg2rad(roll)
        
        # 构建旋转矩阵 (ZYX顺序)
        cos_yaw, sin_yaw = np.cos(yaw_rad), np.sin(yaw_rad)
        cos_pitch, sin_pitch = np.cos(pitch_rad), np.sin(pitch_rad)
        cos_roll, sin_roll = np.cos(roll_rad), np.sin(roll_rad)
        
        R_z = np.array([[cos_yaw, -sin_yaw, 0],
                        [sin_yaw, cos_yaw, 0],
                        [0, 0, 1]])
        
        R_y = np.array([[cos_pitch, 0, sin_pitch],
                        [0, 1, 0],
                        [-sin_pitch, 0, cos_pitch]])
        
        R_x = np.array([[1, 0, 0],
                        [0, cos_roll, -sin_roll],
                        [0, sin_roll, cos_roll]])
        
        R = R_z @ R_y @ R_x
        
        # 构建齐次变换矩阵（位置使用毫米）
        T = np.eye(4)
        T[0:3, 0:3] = R
        T[0:3, 3] = [x_mm, y_mm, z_mm]
        
        return T
    
    def execute_grasp(self):
        """执行抓取"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接电机")
            return
        
        # 检查是否有可用的抓取目标（识别位置或手动点击位置）
        if self.use_detected_position and self.detected_center_point:
            # 使用识别到的位置进行抓取
            pixel_x, pixel_y = self.detected_center_point
            print(f"🎯 使用识别位置进行抓取: 像素坐标 ({pixel_x}, {pixel_y})")
            
            # 检查是否已经有转换好的坐标
        if not hasattr(self, 'target_coords'):
                QMessageBox.warning(self, "错误", "识别位置尚未转换为世界坐标！\n请重新点击'获取识别位置'。")
                return
                
        elif hasattr(self, 'target_coords'):
            # 使用手动点击的位置进行抓取
            print("🖱️ 使用手动点击位置进行抓取")
        else:
            QMessageBox.warning(
                self, 
                "警告", 
                "请先选择抓取目标：\n\n"
                "1. 启动视觉识别并点击'获取识别位置'\n"
                "2. 或者在右相机图像上手动点击目标点"
            )
            return
        
        try:
            # 获取目标坐标和欧拉角
            target_x, target_y, target_z = self.target_coords
            
            # 根据姿态模式选择Yaw角
            if self.use_dynamic_pose and hasattr(self, 'detected_rotation_angle'):
                # 动态模式：使用视觉识别的旋转角度作为Yaw角
                target_yaw = self.detected_rotation_angle
            else:
                # 固定模式：使用设定的固定Yaw角
                target_yaw = self.yaw_spin.value()
                print(f"🔒 使用固定姿态: Yaw角 = {target_yaw:.1f}° (固定设置)")
            
            target_pitch = self.pitch_spin.value()
            target_roll = self.roll_spin.value()
            
            # 获取运动参数
            max_speed = self.motion_speed_spin.value()
            acceleration = self.motion_acc_spin.value()
            
            print(f"执行抓取: 目标位置 ({target_x:.1f}, {target_y:.1f}, {target_z:.1f}) mm")
            print(f"目标姿态: Yaw={target_yaw:.1f}°, Pitch={target_pitch:.1f}°, Roll={target_roll:.1f}°")
            
            # 使用逆运动学计算关节角度
            if self.kinematics:
                try:
                    # 构建目标变换矩阵
                    target_transform = self.build_target_transform(target_x, target_y, target_z, 
                                                                 target_yaw, target_pitch, target_roll)
                    # 计算逆运动学
                    joint_solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
                    
                    if isinstance(joint_solutions, list) and len(joint_solutions) > 0:
                        # 选择最优解：2轴在90到0之间
                        target_joint_angles = self.select_best_solution(joint_solutions)
                        if target_joint_angles is not None:
                            print(f"逆运动学解: {[f'{angle:.2f}°' for angle in target_joint_angles]}")
                            # 更新关节角度显示（现在是第6行，索引为6）
                            joint_angles_str = ", ".join([f"{angle:.2f}°" for angle in target_joint_angles])
                            self.coord_table.setItem(6, 1, QTableWidgetItem(joint_angles_str))
                        else:
                            QMessageBox.warning(self, "警告", "逆运动学无合适解（2轴不在90°到0°范围内）")
                            return  # 直接返回，不执行抓取
                    elif isinstance(joint_solutions, np.ndarray):
                        # 单个解的情况
                        candidate_angles = joint_solutions.tolist()
                        if self.is_valid_solution(candidate_angles):
                            target_joint_angles = candidate_angles
                            print(f"逆运动学解: {[f'{angle:.2f}°' for angle in target_joint_angles]}")
                            # 更新关节角度显示（现在是第6行，索引为6）
                            joint_angles_str = ", ".join([f"{angle:.2f}°" for angle in target_joint_angles])
                            self.coord_table.setItem(6, 1, QTableWidgetItem(joint_angles_str))
                        else:
                            QMessageBox.warning(self, "警告", "逆运动学解不满足约束条件（2轴不在90°到0°范围内）")
                            return  # 直接返回，不执行抓取
                    else:
                        QMessageBox.warning(self, "警告", "逆运动学无解")
                        return  # 直接返回，不执行抓取
                        
                except Exception as ik_error:
                    print(f"逆运动学计算失败: {ik_error}")
                    QMessageBox.warning(self, "警告", f"逆运动学计算失败: {str(ik_error)}")
                    return  # 直接返回，不执行抓取
            else:
                # 如果没有运动学模块，无法执行抓取
                QMessageBox.warning(self, "错误", "运动学模块不可用，无法执行抓取")
                return  # 直接返回，不执行抓取
            
            # 获取选中的电机（使用所有连接的电机）
            selected_motors = [(motor_id, self.motors[motor_id]) for motor_id in sorted(self.motors.keys())[:6]]
            
            if not selected_motors:
                QMessageBox.warning(self, "警告", "未找到可用电机")
                return
            
            # 执行机械臂运动（参考digital_twin_widget的实现）
            self.move_arm_to_position(selected_motors, target_joint_angles, max_speed, acceleration)
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"执行抓取失败: {str(e)}")
    
    def build_target_transform(self, x, y, z, yaw, pitch, roll):
        """构建目标变换矩阵（统一使用毫米单位）"""
        # 位置统一使用毫米单位
        x_mm, y_mm, z_mm = x, y, z  # 毫米单位
        
        # 角度转换为弧度
        yaw_rad = np.deg2rad(yaw)
        pitch_rad = np.deg2rad(pitch)
        roll_rad = np.deg2rad(roll)
        
        # 构建旋转矩阵 (ZYX顺序)
        cos_yaw, sin_yaw = np.cos(yaw_rad), np.sin(yaw_rad)
        cos_pitch, sin_pitch = np.cos(pitch_rad), np.sin(pitch_rad)
        cos_roll, sin_roll = np.cos(roll_rad), np.sin(roll_rad)
        
        R_z = np.array([[cos_yaw, -sin_yaw, 0],
                        [sin_yaw, cos_yaw, 0],
                        [0, 0, 1]])
        
        R_y = np.array([[cos_pitch, 0, sin_pitch],
                        [0, 1, 0],
                        [-sin_pitch, 0, cos_pitch]])
        
        R_x = np.array([[1, 0, 0],
                        [0, cos_roll, -sin_roll],
                        [0, sin_roll, cos_roll]])
        
        R = R_z @ R_y @ R_x
        
        # 构建齐次变换矩阵（位置使用毫米）
        T = np.eye(4)
        T[0:3, 0:3] = R
        T[0:3, 3] = [x_mm, y_mm, z_mm]
        
        return T
    
    def move_arm_to_position(self, selected_motors, target_angles, max_speed, acceleration):
        """控制机械臂移动到指定位置"""
        try:
            # 解析位置值
            positions = {}
            for i, (motor_id, motor) in enumerate(selected_motors):
                if i < len(target_angles):
                    positions[motor_id] = target_angles[i]
                else:
                    positions[motor_id] = 0.0
            
            deceleration = acceleration  # 使用相同的减速度
            is_absolute = True
            
            # 判断是否为Y板
            if self._is_y_board():
                # Y板：使用多电机命令一次性下发
                commands = []
                for motor_id, motor in selected_motors:
                    if motor_id in positions:
                        input_position = positions[motor_id]
                        actual_position = self.get_actual_angle(input_position, motor_id)
                        func = motor.command_builder.position_mode_trapezoid(
                            position=actual_position,
                            max_speed=max_speed,
                            acceleration=acceleration,
                            deceleration=deceleration,
                            is_absolute=is_absolute,
                            multi_sync=False
                        )
                        commands.append(self._build_single_command_for_y42(motor_id, func))
                
                if commands:
                    first_motor = selected_motors[0][1]
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')

            else:
                # X板：多机同步标志 + 广播同步
                success_count = 0
                for motor_id, motor in selected_motors:
                    if motor_id in positions:
                        try:
                            input_position = positions[motor_id]
                            actual_position = self.get_actual_angle(input_position, motor_id)
                            
                            motor.control_actions.move_to_position_trapezoid(
                                position=actual_position,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=is_absolute,
                                multi_sync=True
                            )
                            success_count += 1
                        except Exception as motor_error:
                            print(f"电机 {motor_id} 设置失败: {motor_error}")
                            continue
                
                if success_count > 0:
                    # 发送同步运动命令
                    first_motor = selected_motors[0][1]
                    try:
                        interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                        broadcast_motor = first_motor.__class__(
                            motor_id=0,
                            interface_type=first_motor.interface_type,
                            shared_interface=True,
                            **interface_kwargs
                        )
                    except Exception:
                        broadcast_motor = first_motor.__class__(
                            motor_id=0,
                            interface_type=first_motor.interface_type,
                            shared_interface=True
                        )
                    
                    broadcast_motor.can_interface = first_motor.can_interface
                    broadcast_motor.control_actions.sync_motion()
                    
                else:
                    QMessageBox.warning(self, "失败", "没有电机成功设置运动参数")
                    
        except Exception as e:
            QMessageBox.warning(self, "失败", f"机械臂运动控制失败: {str(e)}")
    
    def get_actual_angle(self, input_angle, motor_id):
        """根据减速比和方向设置计算实际发送给电机的角度"""
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
        direction = self.motor_config_manager.get_motor_direction(motor_id)
        motor_angle = input_angle * reducer_ratio * direction
        return motor_angle
    
    def _is_y_board(self):
        """判断是否全为Y版驱动板"""
        if not self.motors:
            return False
        versions = set()
        for m in self.motors.values():
            versions.add(str(getattr(m, 'drive_version', 'X')).upper())
        return versions == {"Y"}
    
    def _build_single_command_for_y42(self, motor_id, function_body):
        """将功能体前置地址，构造单条Y42子命令"""
        try:
            from Control_SDK.Control_Core import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, function_body)
        except Exception:
            return [motor_id] + function_body
    
    def stop_motion(self):
        """停止运动"""
        if not self.motors:
            return
        
        try:
            selected_motors = [(motor_id, self.motors[motor_id]) for motor_id in sorted(self.motors.keys())[:6]]
            success_count = 0
            
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.stop()
                    success_count += 1
                except Exception as e:
                    print(f"电机 {motor_id} 停止失败: {e}")
            
            QMessageBox.information(self, "完成", f"成功停止 {success_count}/{len(selected_motors)} 个电机")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止运动失败: {str(e)}")
    
    def update_motors(self, motors):
        """更新电机列表"""
        self.motors = motors
        
        # 根据电机连接状态启用/禁用控制按钮
        if motors:
            self.photo_position_btn.setEnabled(True)  # 启用拍照位置按钮
            # 如果已经有目标坐标，启用抓取按钮
            if hasattr(self, 'target_coords'):
                self.grasp_btn.setEnabled(True)
            self.stop_motion_btn.setEnabled(True)
        else:
            self.photo_position_btn.setEnabled(False)
            self.grasp_btn.setEnabled(False)
            self.stop_motion_btn.setEnabled(False)
    
    def clear_motors(self):
        """清空电机列表"""
        self.motors = {}
        self.photo_position_btn.setEnabled(False)
        self.grasp_btn.setEnabled(False)
        self.stop_motion_btn.setEnabled(False)
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            self.motor_config_manager.config = self.motor_config_manager.load_config()
            print("✅ 视觉抓取控件：电机配置已重新加载")
        except Exception as e:
            print(f"⚠ 视觉抓取控件：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            if KINEMATICS_AVAILABLE:
                # 重新创建运动学实例，使用最新的DH参数配置
                self.kinematics = create_configured_kinematics()
            else:
                print("⚠️ 运动学模块不可用，无法重新加载DH参数配置")
        except Exception as e:
            print(f"⚠ 视觉抓取控件：重新加载DH参数配置失败: {e}")
            self.kinematics = None 

    def get_current_arm_pose(self):
        """获取当前机械臂末端位姿"""
        if not self.motors:
            return None
            
        try:
            # 获取当前所有关节角度
            current_joint_angles = []
            for i in range(6):
                motor_id = i + 1
                if motor_id in self.motors:
                    motor = self.motors[motor_id]
                    # 读取当前位置
                    position = motor.read_parameters.get_position()
                    # 考虑减速比和方向，转换为输出端角度
                    ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                    direction = self.motor_config_manager.get_motor_direction(motor_id)
                    output_position = (position * direction) / ratio
                    current_joint_angles.append(output_position)
                else:
                    # 如果电机未连接，使用0度
                    current_joint_angles.append(0.0)
            
            print(f"当前关节角度: {[f'{angle:.2f}°' for angle in current_joint_angles]}")
            
            # 使用正运动学计算当前末端位姿
            if self.kinematics:
                try:
                    # 计算正运动学
                    transform_matrix = self.kinematics.forward_kinematics(current_joint_angles)
                    
                    # 从变换矩阵提取位置和姿态
                    position = transform_matrix[:3, 3]  # 位置 (mm)
                    rotation_matrix = transform_matrix[:3, :3]  # 旋转矩阵
                    
                    # 将旋转矩阵转换为欧拉角 (ZYX顺序)
                    euler_angles = self.rotation_matrix_to_euler(rotation_matrix)
                    
                    # 构建位姿 [x(mm), y(mm), z(mm), yaw(deg), pitch(deg), roll(deg)]
                    current_pose = [
                        position[0], position[1], position[2],  # 位置
                        euler_angles[0], euler_angles[1], euler_angles[2]  # 姿态
                    ]
                    
                    print(f"当前末端位姿: 位置({position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f})mm, "
                          f"姿态({euler_angles[0]:.1f}, {euler_angles[1]:.1f}, {euler_angles[2]:.1f})°")
                    
                    return current_pose
                    
                except Exception as e:
                    print(f"正运动学计算失败: {e}")
                    return None
            else:
                print("运动学模块不可用")
                return None
                
        except Exception as e:
            print(f"获取机械臂位姿失败: {e}")
            return None
    
    def rotation_matrix_to_euler(self, R):
        """将旋转矩阵转换为欧拉角 (ZYX顺序)"""
        # ZYX欧拉角提取
        sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
        
        singular = sy < 1e-6
        
        if not singular:
            x = np.arctan2(R[2, 1], R[2, 2])  # Roll
            y = np.arctan2(-R[2, 0], sy)      # Pitch
            z = np.arctan2(R[1, 0], R[0, 0])  # Yaw
        else:
            x = np.arctan2(-R[1, 2], R[1, 1])  # Roll
            y = np.arctan2(-R[2, 0], sy)       # Pitch
            z = 0                              # Yaw
        
        # 转换为度
        return [np.rad2deg(z), np.rad2deg(y), np.rad2deg(x)]  # [yaw, pitch, roll] 

    def select_best_solution(self, solutions):
        """选择最优的逆运动学解：2轴在90到0之间"""
        valid_solutions = []
        
        for solution in solutions:
            if isinstance(solution, np.ndarray):
                angles = solution.tolist()
            else:
                angles = solution
                
            if self.is_valid_solution(angles):
                valid_solutions.append(angles)
        
        if not valid_solutions:
            return None
        
        # 如果有多个有效解，选择2轴最接近45度的解（中间值）
        best_solution = None
        best_score = float('inf')
        
        for solution in valid_solutions:
            # 计算2轴与45度的距离作为评分标准
            joint2_angle = solution[1]  # 第二个关节（索引1）
            score = abs(joint2_angle - 45.0)  # 距离45度的差值
            
            if score < best_score:
                best_score = score
                best_solution = solution
        
        return best_solution
    
    def initialize_vision_detector(self):
        """初始化视觉检测器"""
        if not VISION_DETECTION_AVAILABLE:
            print("❌ 视觉检测模块不可用")
            return
        
        try:
            # 获取相机参数
            if hasattr(self, 'calibration_params') and self.calibration_params:
                one_config = self.calibration_params.get("one", {})
                if one_config:
                    camera_matrix = np.array(one_config.get("camera_matrix", []))
                    
                    # 正确获取畸变参数 - 使用 camera_distortion 而不是 dist_coeffs
                    camera_distortion = one_config.get("camera_distortion", [])
                    dist_coeffs = np.array([])
                    
                    if camera_distortion:
                        if len(camera_distortion) > 0:
                            if isinstance(camera_distortion[0], list):
                                if len(camera_distortion[0]) > 1:
                                    # 旧格式：[[-0.04169075, -0.10853007, ...]]
                                    dist_coeffs = np.array(camera_distortion[0], dtype=np.float64)
                                else:
                                    # 新格式：[[0.281...], [0.074...], ...]
                                    dist_coeffs = np.array([row[0] for row in camera_distortion if len(row) > 0], dtype=np.float64)
                            else:
                                # 直接是数值列表
                                dist_coeffs = np.array(camera_distortion, dtype=np.float64)
                    
                    if camera_matrix.size > 0 and dist_coeffs.size > 0:
                        # 使用针孔模型初始化视觉检测器
                        self.vision_detector = VisionDetector(camera_matrix, dist_coeffs, model='pinhole')
                        print("✅ 视觉检测器初始化成功")
                    else:
                        print("⚠️ 相机标定参数不完整，使用默认参数")
                        # 创建默认相机参数
                        default_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
                        default_dist_coeffs = np.zeros(4, dtype=np.float32)
                        self.vision_detector = VisionDetector(default_camera_matrix, default_dist_coeffs, model='pinhole')
                else:
                    print("⚠️ 未找到单目标定参数，使用默认参数")
                    default_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
                    default_dist_coeffs = np.zeros(4, dtype=np.float32)
                    self.vision_detector = VisionDetector(default_camera_matrix, default_dist_coeffs, model='pinhole')
            else:
                print("⚠️ 未加载标定参数，使用默认参数")
                default_camera_matrix = np.array([[800, 0, 320], [0, 800, 240], [0, 0, 1]], dtype=np.float32)
                default_dist_coeffs = np.zeros(4, dtype=np.float32)
                self.vision_detector = VisionDetector(default_camera_matrix, default_dist_coeffs, model='pinhole')
        except Exception as e:
            print(f"❌ 视觉检测器初始化失败: {e}")
            self.vision_detector = None
    
    def toggle_vision_detection(self):
        """切换视觉识别开关"""
        if not self.vision_detector:
            QMessageBox.warning(self, "警告", "视觉检测器未初始化！")
            return
        
        self.vision_detection_enabled = not self.vision_detection_enabled
        
        if self.vision_detection_enabled:
            self.vision_detection_btn.setText("🔍 停止识别")
            self.vision_detection_btn.setProperty("class", "warning")
            self.get_detection_pos_btn.setEnabled(True)  # 启用获取识别位置按钮
        else:
            self.vision_detection_btn.setText("👁️ 视觉识别")
            self.vision_detection_btn.setProperty("class", "info")
            self.detected_objects = []  # 清空检测结果
            self.detected_center_point = None  # 清空识别位置
            self.use_detected_position = False  # 禁用识别位置抓取
            self.get_detection_pos_btn.setEnabled(False)  # 禁用获取识别位置按钮
            # 清空阈值图显示
            if hasattr(self, 'threshold_display_label'):
                self.threshold_display_label.clear()
                self.threshold_display_label.setText("视觉检测已停用\n点击'视觉识别'按钮\n重新启用检测\n(只显示最大目标)")
            print("⏹️ 视觉识别已停用")
        
        # 刷新按钮样式
        self.vision_detection_btn.style().unpolish(self.vision_detection_btn)
        self.vision_detection_btn.style().polish(self.vision_detection_btn)
    
    def get_detection_position(self):
        """获取检测到的目标中心位置"""
        if not self.vision_detection_enabled:
            QMessageBox.warning(self, "警告", "请先启动视觉识别！")
            return
        
        if not self.detected_objects or len(self.detected_objects) == 0:
            QMessageBox.warning(self, "警告", "当前没有检测到任何目标！\n请确保目标在相机视野范围内。")
            return
        
        # 获取最大的检测对象（已经是排序后的第一个）
        obj = self.detected_objects[0]  # detected_objects已经只包含最大的对象
        center = obj['center']
        size = obj['size']  
        angle = obj['angle']  # 原始角度（长边或宽边的角度）
        short_edge_angle = obj.get('short_edge_angle', angle)  # 短边角度，兼容旧版本
        
        # 获取中心点坐标（直接从对象信息中获取）
        center_x, center_y = center
        
        # 保存识别位置和旋转角度（使用短边角度）
        self.detected_center_point = (center_x, center_y)
        self.detected_rotation_angle = short_edge_angle  # 保存短边角度用于抓取
        self.use_detected_position = True
        
        
        # 显示像素坐标到坐标表格并执行坐标转换
        try:
            # 更新像素坐标和旋转角度显示
            self.coord_table.setItem(0, 1, QTableWidgetItem(f"({center_x}, {center_y}) - 右相机 (识别)"))
            
            # 显示短边旋转角度和姿态模式状态
            mode_text = "动态模式 - 将用于Yaw角" if self.use_dynamic_pose else "固定模式 - 仅供参考"
            self.coord_table.setItem(1, 1, QTableWidgetItem(f"{short_edge_angle:.1f}° 短边角度 ({mode_text})"))
            
            # 执行坐标转换，计算所有相关坐标信息
            self.convert_coordinates(center_x, center_y, "right")
            
            # 显示转换后的详细信息
            if hasattr(self, 'target_coords'):
                target_x, target_y, target_z = self.target_coords
                print(f"📊 坐标转换完成:")
                print(f"   ├─ 像素坐标: ({center_x}, {center_y})")
                print(f"   ├─ 世界坐标: ({target_x:.1f}, {target_y:.1f}, {target_z:.1f}) mm")
                print(f"   └─ 详细信息已更新到坐标表格")
            
        except Exception as e:
            print(f"❌ 坐标转换失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"坐标转换失败: {str(e)}")
            return
        
        # 更新按钮样式和文本，表示已获取位置（包含短边角度信息）
        self.get_detection_pos_btn.setText(f"✅ 已获取位置 ({center_x}, {center_y}) {short_edge_angle:.1f}°")
        self.get_detection_pos_btn.setProperty("class", "success")
        self.get_detection_pos_btn.style().unpolish(self.get_detection_pos_btn)
        self.get_detection_pos_btn.style().polish(self.get_detection_pos_btn)
        
        # 启用执行抓取按钮
        if self.motors:
            self.grasp_btn.setEnabled(True)
            self.grasp_btn.setText("🎯 执行自动抓取")
            pose_mode_desc = "动态姿态 (Yaw角跟随目标)" if self.use_dynamic_pose else "固定姿态 (使用设定角度)"
            self.grasp_btn.setToolTip(f"使用识别位置 ({center_x}, {center_y}) 短边角度 {short_edge_angle:.1f}° 执行抓取\n姿态模式: {pose_mode_desc}")
            self.stop_motion_btn.setEnabled(True)
        
        # 获取转换后的坐标信息用于显示
        coord_info = ""
        if hasattr(self, 'target_coords'):
            target_x, target_y, target_z = self.target_coords
            coord_info = f"\n🌍 世界坐标: ({target_x:.1f}, {target_y:.1f}, {target_z:.1f}) mm"
        
        
        # 提示用户（包含旋转角度和尺寸信息）
        pose_mode_info = "🎯 动态模式 (Yaw角将跟随目标旋转)" if self.use_dynamic_pose else "🔒 固定模式 (使用设定的姿态角度)"
        QMessageBox.information(
            self, 
            "🎯 识别位置获取成功", 
            f"已成功获取并转换目标位置：\n\n"
            f"🎯 像素坐标: ({center_x}, {center_y})\n"
            f"📏 目标尺寸: {size[0]} × {size[1]} 像素\n"
            f"🔄 短边角度: {short_edge_angle:.1f}° (抓取角度)\n"
            f"📐 原始角度: {angle:.1f}° (检测角度)\n"
            f"⚙️ 姿态模式: {pose_mode_info}\n"
            f"{coord_info}\n\n"
            f"✅ 现在可以点击'🎯 执行抓取' 进行抓取操作。"
        )
    
    def open_vision_params_dialog(self):
        """打开视觉检测参数设置对话框"""
        dialog = VisionParametersDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            print("✅ 视觉检测参数已更新")
    
    def open_grasp_params_dialog(self):
        """打开抓取参数设置对话框"""
        dialog = GraspParametersDialog(self)
        if dialog.exec_() == QDialog.Accepted:
            print("✅ 抓取参数已更新")
    
    def display_threshold_image(self, threshold_image):
        """显示阈值图到阈值显示标签"""
        try:
            # 调整图像大小以适应显示标签
            display_size = (300, 225)  # 更新显示尺寸以匹配新的标签大小
            resized_threshold = cv2.resize(threshold_image, display_size)
            
            # 转换为Qt可显示的格式
            height, width, channel = resized_threshold.shape
            bytes_per_line = 3 * width
            q_image = QImage(resized_threshold.data, width, height, bytes_per_line, QImage.Format_RGB888).rgbSwapped()
            
            # 创建QPixmap并设置到标签
            pixmap = QPixmap.fromImage(q_image)
            self.threshold_display_label.setPixmap(pixmap)
            
        except Exception as e:
            print(f"显示阈值图失败: {e}")
            self.threshold_display_label.setText("阈值图显示失败")
    
    def is_valid_solution(self, angles):
        """检查解是否有效：2轴在90到0之间"""
        if len(angles) < 2:
            return False
        
        joint2_angle = angles[1]  # 第二个关节（索引1）
        
        # 检查2轴是否在90到0度范围内
        if 0.0 <= joint2_angle <= 90.0:
            print(f"有效解：关节2角度 = {joint2_angle:.2f}° (在0°-90°范围内)")
            return True
        else:
            print(f"无效解：关节2角度 = {joint2_angle:.2f}° (不在0°-90°范围内)")
            return False 

    def move_to_photo_position(self):
        """运动到拍照位置（固定位置[0,0,0,0,90,0]）"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接电机")
            return
        
        try:
            # 获取当前所有关节角度（用于显示）
            current_joint_angles = []
            for i in range(6):
                motor_id = i + 1
                if motor_id in self.motors:
                    motor = self.motors[motor_id]
                    # 读取当前位置
                    position = motor.read_parameters.get_position()
                    # 考虑减速比和方向，转换为输出端角度
                    ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                    direction = self.motor_config_manager.get_motor_direction(motor_id)
                    output_position = (position * direction) / ratio
                    current_joint_angles.append(output_position)
                else:
                    # 如果电机未连接，使用0度
                    current_joint_angles.append(0.0)
            
            # 设置目标角度：固定拍照位置 [0,0,0,0,90,0]
            target_angles = [0.0, 0.0, 0.0, 0.0, 90.0, 0.0]
            
            print(f"当前关节角度: {[f'{angle:.1f}°' for angle in current_joint_angles]}")
            print(f"拍照位置目标: {[f'{angle:.1f}°' for angle in target_angles]}")
            print(f"📸 运动到标准拍照位置 [0°, 0°, 0°, 0°, 90°, 0°]")
            
            # 获取运动参数
            max_speed = self.motion_speed_spin.value()
            acceleration = self.motion_acc_spin.value()
            deceleration = acceleration
            
            # 暂时禁用按钮
            self.photo_position_btn.setEnabled(False)
            self.grasp_btn.setEnabled(False)
            
            # 获取选中的电机（使用所有连接的电机）
            selected_motors = [(motor_id, self.motors[motor_id]) for motor_id in sorted(self.motors.keys())[:6]]
            
            if not selected_motors:
                QMessageBox.warning(self, "警告", "未找到可用电机")
                return
            
            # 执行机械臂运动
            self.move_arm_to_position(selected_motors, target_angles, max_speed, acceleration)
            
            # 延迟恢复按钮状态
            QTimer.singleShot(5000, self._on_photo_position_finished)  # 5秒后恢复（因为运动幅度更大）
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"运动到拍照位置失败: {str(e)}")
            self.photo_position_btn.setEnabled(True)
            if hasattr(self, 'target_coords'):
                self.grasp_btn.setEnabled(True)

    def _on_photo_position_finished(self):
        """拍照位置运动完成后的处理"""
        if self.motors:
            self.photo_position_btn.setEnabled(True)
            # 如果已经有目标坐标，启用抓取按钮
            if hasattr(self, 'target_coords'):
                self.grasp_btn.setEnabled(True)
        print("📸 机械臂已运动到标准拍照位置 [0°, 0°, 0°, 0°, 90°, 0°]")
    
    def update_claw_controller(self, claw_controller):
        """更新夹爪控制器实例"""
        self.claw_controller = claw_controller
        self.claw_connected = claw_controller is not None and claw_controller.is_connected() if claw_controller else False
        
        # 更新夹爪按钮状态
        self.claw_open_btn.setEnabled(self.claw_connected)
        self.claw_close_btn.setEnabled(self.claw_connected)
        
        # 更新按钮提示文本
        if self.claw_connected:
            self.claw_open_btn.setToolTip("张开夹爪")
            self.claw_close_btn.setToolTip("闭合夹爪")
        else:
            self.claw_open_btn.setToolTip("张开夹爪（需要先连接夹爪）")
            self.claw_close_btn.setToolTip("闭合夹爪（需要先连接夹爪）")
        
        print(f"🤏 夹爪控制器状态更新: {'已连接' if self.claw_connected else '未连接'}")
    
    def open_claw(self):
        """张开夹爪"""
        if not self.claw_controller or not self.claw_connected:
            QMessageBox.warning(self, "警告", "请先在'夹爪连接与控制'界面连接夹爪")
            return
        
        try:
            # 使用配置的张开角度
            self.claw_controller.open(self.claw_open_angle)
            print(f"🤏 夹爪张开成功 (角度: {self.claw_open_angle}°)")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"夹爪张开失败: {str(e)}")
            print(f"❌ 夹爪张开失败: {e}")
    
    def close_claw(self):
        """闭合夹爪"""
        if not self.claw_controller or not self.claw_connected:
            QMessageBox.warning(self, "警告", "请先在'夹爪连接与控制'界面连接夹爪")
            return
        
        try:
            # 使用配置的闭合角度
            self.claw_controller.close(self.claw_close_angle)
            print(f"✋ 夹爪闭合成功 (角度: {self.claw_close_angle}°)")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"夹爪闭合失败: {str(e)}")
            print(f"❌ 夹爪闭合失败: {e}")
