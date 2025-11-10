# -*- coding: utf-8 -*-
"""
具身智能控件
通过自然语言指令与LLM交互，控制机械臂执行复杂动作
"""

import sys
import os
import time
import threading
import yaml
import cv2
import numpy as np
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QScrollArea, QSplitter, QFrame, QHeaderView,
                             QPlainTextEdit, QDialog, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot, QMutex, QWaitCondition
from PyQt5.QtGui import QFont, QPalette, QColor, QTextCursor, QPixmap, QImage
import numpy as np
import queue
import json
import re

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

try:
    from core.embodied_core.hierarchical_decision_system import HierarchicalDecisionSystem
except ImportError:
    HierarchicalDecisionSystem = None

# 添加运动学模块导入
try:
    from Main_UI.utils.kinematics_factory import create_configured_kinematics
    KINEMATICS_AVAILABLE = True
except ImportError:
    KINEMATICS_AVAILABLE = False

# 添加电机配置管理器导入
from .motor_config_manager import motor_config_manager

# 添加配置管理器导入
try:
    from core.config_manager import config_manager
    CONFIG_MANAGER_AVAILABLE = True
except ImportError:
    CONFIG_MANAGER_AVAILABLE = False

class NoWheelComboBox(QComboBox):
    """禁用滚轮事件的下拉框"""
    def wheelEvent(self, event):
        # 忽略滚轮事件，不传递给父类
        event.ignore()


class EmbodiedGraspParametersDialog(QDialog):
    """具身智能视觉抓取参数设置对话框"""
    
    def __init__(self, parent_widget):
        super().__init__(parent_widget)
        self.parent_widget = parent_widget
        
        self.setWindowTitle("🤖 视觉抓取参数设置")
        self.setFixedSize(650, 720)
        self.setModal(True)
        
        # 初始化配置管理器
        self.config_manager = config_manager if CONFIG_MANAGER_AVAILABLE else None
        
        # 初始化参数
        self.init_parameters()
        
        # 从配置文件加载参数
        self.load_parameters_from_config()
        
        # 初始化UI
        self.init_ui()
        
        # UI创建完成后，刷新夹爪状态
        self.refresh_claw_status()

    
    def init_parameters(self):
        """初始化参数默认值"""
        # 设置默认参数（将从配置文件覆盖）
        self._set_default_parameters()
        
        # 从父组件获取夹爪连接状态
        self.claw_controller = getattr(self.parent_widget, 'claw_controller', None)
        self.claw_connected = getattr(self.parent_widget, 'claw_connected', False)
    
    def _set_default_parameters(self):
        """设置默认参数值"""
        # 姿态参数
        self.euler_yaw = 0.0
        self.euler_pitch = 0.0
        self.euler_roll = 180.0
        
        # 姿态控制模式
        self.use_dynamic_pose = False  # 默认使用固定姿态
        
        # 运动参数
        self.motion_speed = 100
        self.motion_acceleration = 200
        
        # TCP修正参数（毫米）
        self.tcp_offset_x = 0.0
        self.tcp_offset_y = 0.0
        self.tcp_offset_z = 0.0
        
        # 抓取深度参数（毫米）
        self.grasp_depth = 300.0
        
        # 夹爪角度参数（连接由外部管理，角度在此设置）
        self.claw_open_angle = 0
        self.claw_close_angle = 90
        
    
    def load_parameters_from_config(self):
        """从配置文件加载抓取参数并设置到实例变量"""
        try:
            if not self.config_manager:
                print("⚠️ 配置管理器不可用，使用默认抓取参数")
                return
            
            # 加载姿态参数（欧拉角）
            euler_angles = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.euler_angles", [0.0, 0.0, 180.0]
            )
            if len(euler_angles) >= 3:
                self.euler_yaw = euler_angles[0]
                self.euler_pitch = euler_angles[1] 
                self.euler_roll = euler_angles[2]
            
            # 加载姿态模式
            self.use_dynamic_pose = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.use_dynamic_pose", False
            )
            
            # 加载运动参数
            self.motion_speed = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.motion_speed", 100
            )
            self.motion_acceleration = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.motion_acceleration", 200
            )
            
            # 加载TCP修正参数
            tcp_offset = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.tcp_offset", [0.0, 0.0, 0.0]
            )
            if len(tcp_offset) >= 3:
                self.tcp_offset_x = tcp_offset[0]
                self.tcp_offset_y = tcp_offset[1]
                self.tcp_offset_z = tcp_offset[2]
            
            # 加载抓取深度参数
            self.grasp_depth = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.grasp_depth", 300.0
            )
            
            # 加载夹爪参数
            self.claw_port = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.claw_port", "COM6"
            )
            self.claw_baudrate = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.claw_baudrate", 9600
            )
            
            # 加载夹爪角度参数
            claw_angles = self.config_manager.get_config_value(
                "embodied_intelligence", "grasp_params.claw_angles", [0, 90]
            )
            if len(claw_angles) >= 2:
                self.claw_open_angle = claw_angles[0]
                self.claw_close_angle = claw_angles[1]
            
        except Exception as e:
            print(f"❌ 加载具身智能抓取参数失败，使用默认值: {e}")
            self._set_default_parameters()
    
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
        
        # 抓取深度设置组
        self.create_depth_settings_group(scroll_layout)
        
        # 夹爪设置组
        self.create_claw_settings_group(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        # 按钮组
        self.create_button_group(layout)
    
    def create_pose_settings_group(self, parent_layout):
        """创建姿态设置组"""
        group = QGroupBox("🎭 末端抓取姿态设置 (欧拉角)")
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
        # 根据从配置文件加载的值设置当前选项
        mode_index = 1 if self.use_dynamic_pose else 0
        self.pose_mode_combo.setCurrentIndex(mode_index)
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
        
        print(f"具身智能姿态控制模式已切换为: {'动态姿态' if is_dynamic else '固定姿态'}")
    
    def create_motion_settings_group(self, parent_layout):
        """创建运动参数设置组"""
        group = QGroupBox("⚙️ 运动控制参数")
        layout = QHBoxLayout(group)
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
        group = QGroupBox("🔧 TCP修正 (工具中心点偏移)")
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
    
    def create_depth_settings_group(self, parent_layout):
        """创建抓取深度设置组"""
        group = QGroupBox("📏 抓取深度设置")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 添加说明标签
        info_label = QLabel("💡 设置视觉抓取时使用的深度值（毫米）:")
        info_label.setStyleSheet("color: #666; font-style: italic; font-size: 12px;")
        main_layout.addWidget(info_label)
        
        # 深度设置布局
        depth_layout = QHBoxLayout()
        depth_layout.setSpacing(15)
        
        # 深度设置
        depth_section = QVBoxLayout()
        depth_section.addWidget(QLabel("抓取深度:"))
        self.grasp_depth_spin = QDoubleSpinBox()
        self.grasp_depth_spin.setRange(100.0, 1000.0)  # 100mm到1000mm
        self.grasp_depth_spin.setValue(self.grasp_depth)
        self.grasp_depth_spin.setDecimals(1)
        self.grasp_depth_spin.setSuffix(" mm")
        self.grasp_depth_spin.setToolTip("视觉抓取时使用的深度值，影响像素坐标到世界坐标的转换")
        self.grasp_depth_spin.setMaximumWidth(150)
        depth_section.addWidget(self.grasp_depth_spin)
        depth_layout.addLayout(depth_section)
        
        # 重置深度按钮
        reset_layout = QVBoxLayout()
        reset_layout.addWidget(QLabel(""))  # 占位，与上面的标签对齐
        reset_depth_btn = QPushButton("🔄 重置深度")
        reset_depth_btn.clicked.connect(self.reset_grasp_depth)
        reset_depth_btn.setMaximumWidth(120)
        reset_depth_btn.setToolTip("将抓取深度重置为默认值300mm")
        reset_layout.addWidget(reset_depth_btn)
        depth_layout.addLayout(reset_layout)
        
        depth_layout.addStretch()  # 添加弹性空间
        main_layout.addLayout(depth_layout)
        
        # 应用说明
        note_label = QLabel("⚠️ 注意: 深度值影响视觉识别位置到机械臂坐标的转换精度")
        note_label.setStyleSheet("color: #f39c12; font-size: 11px;")
        main_layout.addWidget(note_label)
        
        parent_layout.addWidget(group)
    
    def reset_grasp_depth(self):
        """重置抓取深度为默认值"""
        self.grasp_depth_spin.setValue(300.0)
        print("✅ 抓取深度已重置为默认值300mm")
    
    def create_claw_settings_group(self, parent_layout):
        """创建夹爪设置组"""
        group = QGroupBox("🤏 夹爪设置")
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 连接状态显示
        status_layout = QHBoxLayout()
        self.claw_status_label = QLabel("🔴 夹爪未连接")
        self.claw_status_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
        status_layout.addWidget(self.claw_status_label)
        
        # 连接按钮
        self.claw_connect_btn = QPushButton("🔌 前往连接夹爪")
        self.claw_connect_btn.clicked.connect(self.connect_claw)
        self.claw_connect_btn.setMaximumWidth(120)
        self.claw_connect_btn.setMinimumHeight(30)
        self.claw_connect_btn.setToolTip("跳转到夹爪连接界面")
        status_layout.addWidget(self.claw_connect_btn)
        
        status_layout.addStretch()
        main_layout.addLayout(status_layout)
        
        # 连接说明
        connection_info = QLabel("🔗 夹爪连接由主界面 '夹爪连接与控制' 管理，角度参数在此设置")
        connection_info.setStyleSheet("color: #3498db; font-size: 11px; background-color: #e8f4f8; padding: 8px; border-radius: 4px;")
        connection_info.setWordWrap(True)
        main_layout.addWidget(connection_info)
        
        # 角度设置
        angle_layout = QHBoxLayout()
        angle_layout.setSpacing(15)
        
        # 张开角度
        open_section = QVBoxLayout()
        open_section.addWidget(QLabel("张开角度:"))
        self.claw_open_angle_spin = QSpinBox()
        self.claw_open_angle_spin.setRange(0, 90)
        self.claw_open_angle_spin.setValue(self.claw_open_angle)
        self.claw_open_angle_spin.setSuffix("°")
        self.claw_open_angle_spin.setMaximumWidth(120)
        self.claw_open_angle_spin.setToolTip("夹爪完全张开时的角度")
        open_section.addWidget(self.claw_open_angle_spin)
        angle_layout.addLayout(open_section)
        
        # 闭合角度
        close_section = QVBoxLayout()
        close_section.addWidget(QLabel("闭合角度:"))
        self.claw_close_angle_spin = QSpinBox()
        self.claw_close_angle_spin.setRange(0, 90)
        self.claw_close_angle_spin.setValue(self.claw_close_angle)
        self.claw_close_angle_spin.setSuffix("°")
        self.claw_close_angle_spin.setMaximumWidth(120)
        self.claw_close_angle_spin.setToolTip("夹爪完全闭合时的角度")
        close_section.addWidget(self.claw_close_angle_spin)
        angle_layout.addLayout(close_section)
        
        angle_layout.addStretch()
        main_layout.addLayout(angle_layout)
        
        parent_layout.addWidget(group)
    
    def reset_tcp_offset(self):
        """重置TCP偏移为零"""
        self.tcp_offset_x_spin.setValue(0.0)
        self.tcp_offset_y_spin.setValue(0.0)
        self.tcp_offset_z_spin.setValue(0.0)
        print("✅ TCP偏移已重置为零")
    
    def connect_claw(self):
        """前往夹爪连接界面或显示连接状态"""
        if self.claw_connected:
            # 如果已经连接，显示成功提示
            QMessageBox.information(
                self, 
                "🎉 夹爪已连接", 
                "夹爪连接成功！\n\n"
                "✅ 具身智能已获得夹爪控制能力\n"
                "✅ 所有夹爪参数由外部控件统一管理\n\n"
                "您可以在对话中使用夹爪相关指令了。"
            )
        else:
            # 如果未连接，引导用户前往连接
            QMessageBox.information(
                self, 
                "前往连接夹爪", 
                "夹爪连接和参数设置统一由主界面管理。\n\n"
                "📍 请前往: 主界面 → '夹爪连接与控制' → '连接夹爪'\n\n"
                "✨ 连接成功后，具身智能将自动获得夹爪控制能力，\n"
                "    您就可以在对话中使用夹爪相关指令了！"
            )
    
    def disconnect_claw(self):
        """断开夹爪连接 - 现在由外部夹爪连接控件统一管理"""
        QMessageBox.information(
            self, 
            "提示", 
            "夹爪断开连接现在统一由主界面的 '夹爪连接与控制' 界面管理。\n\n"
            "请前往主界面 → 夹爪连接与控制 → 断开夹爪\n"
            "断开后，具身智能功能将自动停用夹爪控制能力。"
        )
    
    
    def update_claw_status(self):
        """更新夹爪连接状态显示"""
        if self.claw_connected and self.claw_controller:
            # 连接状态
            self.claw_status_label.setText("🟢 夹爪已连接")
            self.claw_status_label.setStyleSheet("color: #27ae60; font-weight: bold; font-size: 12px;")
            self.claw_connect_btn.setText("✅ 夹爪已连接")
            self.claw_connect_btn.setEnabled(False)
        else:
            # 未连接状态
            self.claw_status_label.setText("🔴 夹爪未连接")
            self.claw_status_label.setStyleSheet("color: #e74c3c; font-weight: bold; font-size: 12px;")
            self.claw_connect_btn.setText("🔌 前往连接夹爪")
            self.claw_connect_btn.setEnabled(True)
    
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
        
        # 取消按钮
        cancel_btn = QPushButton("❌ 取消")
        cancel_btn.clicked.connect(self.reject)
        cancel_btn.setMinimumHeight(35)
        cancel_btn.setMinimumWidth(100)
        button_layout.addWidget(cancel_btn)
        
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
            # 尝试从全局抓取参数获取
            from core.embodied_core import embodied_func
            grasp_params = embodied_func._get_grasp_params()
            motion_params = embodied_func._get_motion_params()
            
            # 加载姿态参数
            self.yaw_spin.setValue(grasp_params.get("yaw", 0.0))
            self.pitch_spin.setValue(grasp_params.get("pitch", 0.0))
            self.roll_spin.setValue(grasp_params.get("roll", 180.0))
            
            # 加载运动参数
            self.motion_speed_spin.setValue(motion_params.get("max_speed", 100))
            self.motion_acc_spin.setValue(motion_params.get("acceleration", 200))
            
            # 加载TCP修正参数
            self.tcp_offset_x_spin.setValue(grasp_params.get("tcp_offset_x", 0.0))
            self.tcp_offset_y_spin.setValue(grasp_params.get("tcp_offset_y", 0.0))
            self.tcp_offset_z_spin.setValue(grasp_params.get("tcp_offset_z", 0.0))
            
            # 加载抓取深度参数
            self.grasp_depth_spin.setValue(grasp_params.get("grasp_depth", 300.0))
            
            # 加载夹爪角度参数
            claw_angles = grasp_params.get("claw_angles", [0, 90])
            if len(claw_angles) >= 2:
                self.claw_open_angle_spin.setValue(claw_angles[0])
                self.claw_close_angle_spin.setValue(claw_angles[1])
            
            # 从父组件获取夹爪连接状态（连接由外部控件处理，角度在此管理）
            self.claw_controller = getattr(self.parent_widget, 'claw_controller', None)
            self.claw_connected = getattr(self.parent_widget, 'claw_connected', False)
            self.update_claw_status()
            
        except Exception as e:
            print(f"⚠️ 加载参数时出错: {e}")
    
    def apply_settings(self):
        """应用设置"""
        try:
            # 获取设置值
            yaw = self.yaw_spin.value()
            pitch = self.pitch_spin.value()
            roll = self.roll_spin.value()
            motion_speed = self.motion_speed_spin.value()
            acceleration = self.motion_acc_spin.value()
            tcp_x = self.tcp_offset_x_spin.value()
            tcp_y = self.tcp_offset_y_spin.value()
            tcp_z = self.tcp_offset_z_spin.value()
            grasp_depth = self.grasp_depth_spin.value()
            # 夹爪角度参数（连接由外部控件管理，角度在此设置）
            claw_open_angle = self.claw_open_angle_spin.value()
            claw_close_angle = self.claw_close_angle_spin.value()
            
            # 保存参数到配置文件
            self.save_parameters_to_config()
            
            # 应用到全局参数管理器
            from core.embodied_core import embodied_func
            
            # 设置运动参数
            embodied_func._set_motion_params(
                max_speed=motion_speed,
                acceleration=acceleration,
                deceleration=acceleration
            )
            
            # 设置抓取参数（包含姿态模式）
            use_dynamic_pose = (self.pose_mode_combo.currentIndex() == 1)
            
            embodied_func._set_grasp_params(
                yaw=yaw,
                pitch=pitch,
                roll=roll,
                use_dynamic_pose=use_dynamic_pose,
                tcp_offset_x=tcp_x,
                tcp_offset_y=tcp_y,
                tcp_offset_z=tcp_z,
                grasp_depth=grasp_depth
            )
            
            # 设置夹爪角度参数到全局状态管理器（连接由外部管理）
            from core.embodied_core import embodied_func
            embodied_func._set_claw_params(
                open_angle=claw_open_angle,
                close_angle=claw_close_angle
            )
            
            
            # 如果父组件有日志方法，记录到日志
            if hasattr(self.parent_widget, 'log_message'):
                pose_mode_desc = "动态姿态 (跟随目标)" if use_dynamic_pose else "固定姿态"
                self.parent_widget.log_message(f"🤖 视觉抓取运动参数已设置: 速度={motion_speed}RPM, 加速度={acceleration}RPM/s")
                self.parent_widget.log_message(f"🎭 抓取姿态参数: Yaw={yaw:.1f}°, Pitch={pitch:.1f}°, Roll={roll:.1f}°")
                self.parent_widget.log_message(f"🎯 姿态控制模式: {pose_mode_desc}")
                self.parent_widget.log_message(f"🔧 TCP修正参数: X={tcp_x:.2f}mm, Y={tcp_y:.2f}mm, Z={tcp_z:.2f}mm")
                self.parent_widget.log_message(f"📏 抓取深度参数: {grasp_depth:.1f}mm")
                self.parent_widget.log_message(f"🤏 夹爪角度参数: 张开={claw_open_angle}°, 闭合={claw_close_angle}° (连接由外部管理)")
            
            # 获取姿态模式信息
            pose_mode_text = "动态姿态 (跟随目标)" if (self.pose_mode_combo.currentIndex() == 1) else "固定姿态"
            
            QMessageBox.information(self, "成功", 
                f"视觉抓取参数设置已应用并保存！\n\n"
                f"🎭 抓取姿态: Yaw={yaw:.1f}°, Pitch={pitch:.1f}°, Roll={roll:.1f}°\n"
                f"🎯 姿态模式: {pose_mode_text}\n"
                f"⚙️ 运动参数: 速度={motion_speed}RPM, 加速度={acceleration}RPM/s\n"
                f"🔧 TCP修正: X={tcp_x:.2f}mm, Y={tcp_y:.2f}mm, Z={tcp_z:.2f}mm\n"
                f"📏 抓取深度: {grasp_depth:.1f}mm\n"
                f"🤏 夹爪设置: 张开{claw_open_angle}°/闭合{claw_close_angle}° (连接由外部管理)\n\n"
                f"参数已保存到配置文件，重新打开时会自动加载。")
            
            self.accept()
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"应用设置时出错: {str(e)}")
    
    def save_parameters_to_config(self):
        """保存参数到配置文件"""
        try:
            if not self.config_manager:
                print("⚠️ 无法保存具身智能抓取参数：配置管理器不可用")
                return
            
            # 构建抓取参数配置
            grasp_config = {
                "euler_angles": [
                    self.yaw_spin.value(),
                    self.pitch_spin.value(),
                    self.roll_spin.value()
                ],
                "use_dynamic_pose": (self.pose_mode_combo.currentIndex() == 1),
                "motion_speed": self.motion_speed_spin.value(),
                "motion_acceleration": self.motion_acc_spin.value(),
                "tcp_offset": [
                    self.tcp_offset_x_spin.value(),
                    self.tcp_offset_y_spin.value(),
                    self.tcp_offset_z_spin.value()
                ],
                "grasp_depth": self.grasp_depth_spin.value(),
                "claw_angles": [
                    self.claw_open_angle_spin.value(),
                    self.claw_close_angle_spin.value()
                ]
            }
            # 注意：夹爪连接信息由外部控件管理，角度参数在此保存
            
            # 获取现有配置
            embodied_config = self.config_manager.get_module_config("embodied_intelligence")
            
            # 更新抓取参数
            embodied_config["grasp_params"] = grasp_config
            
            # 保存到配置文件
            success = self.config_manager.save_module_config("embodied_intelligence", embodied_config)

        except Exception as e:
            print(f"❌ 保存具身智能抓取参数失败: {e}")
    
    def reset_all_parameters(self):
        """重置所有参数"""
        # 重置姿态参数
        self.yaw_spin.setValue(0.0)
        self.pitch_spin.setValue(0.0)
        self.roll_spin.setValue(180.0)
        
        # 重置姿态模式为固定姿态
        self.pose_mode_combo.setCurrentIndex(0)
        self.on_pose_mode_changed()  # 触发UI更新
        
        # 重置运动参数
        self.motion_speed_spin.setValue(100)
        self.motion_acc_spin.setValue(200)
        
        # 重置TCP偏移
        self.reset_tcp_offset()
        
        # 重置抓取深度
        self.reset_grasp_depth()
        
        # 重置夹爪角度参数
        self.claw_open_angle_spin.setValue(0)
        self.claw_close_angle_spin.setValue(90)
        
        # 保存重置后的参数到配置文件
        self.save_parameters_to_config()
        
        print("✅ 所有具身智能抓取参数已重置为默认值并保存")
    
    def refresh_claw_status(self):
        """从父组件刷新夹爪连接状态"""
        if self.parent_widget:
            self.claw_controller = getattr(self.parent_widget, 'claw_controller', None)
            self.claw_connected = getattr(self.parent_widget, 'claw_connected', False)
            if hasattr(self, 'claw_status_label'):
                self.update_claw_status()

class VoiceRecognitionWorker(QThread):
    """语音识别工作线程，支持手动控制录音开始和停止"""
    # 定义信号
    finished = pyqtSignal(str)  # 识别完成信号，传递识别的文字
    error = pyqtSignal(str)     # 错误信号
    log_message = pyqtSignal(str)  # 日志消息信号
    recording_started = pyqtSignal()  # 录音开始信号
    
    def __init__(self, config_path, provider="alibaba"):
        super().__init__()
        self.config_path = config_path
        self.provider = provider
        self.is_recording = False
        self.audio_frames = []
        self.audio = None
        self.stream = None
        self._is_running = False  # 线程运行状态
        
        # 音频参数
        self.CHUNK = 1024
        self.FORMAT = None  # 将在运行时设置
        self.CHANNELS = 1
        self.RATE = 16000
    
    def start_recording(self):
        """开始录音"""
        self.is_recording = True
        
    def stop_recording(self):
        """停止录音"""
        self.is_recording = False
    
    def stop(self):
        """安全停止线程"""
        self._is_running = False
        self.is_recording = False
        if self.isRunning():
            self.requestInterruption()
            # 给线程一些时间自然结束
            if not self.wait(3000):  # 等待3秒
                self.terminate()  # 强制终止
                self.wait()  # 等待终止完成
        # 确保资源清理
        self.cleanup_audio()
    
    def run(self):
        """在后台线程中进行录音和语音识别"""
        self._is_running = True
        
        try:
            # 导入必要的库
            try:
                import pyaudio
                import wave
                import tempfile
                import os
                from AI_SDK import AISDK
            except ImportError as e:
                self.error.emit(f"缺少必要的库: {e}")
                return
            
            # 初始化AI SDK
            try:
                sdk = AISDK(config_path=self.config_path)
            except Exception as e:
                self.error.emit(f"初始化AI SDK失败: {str(e)}")
                return
            
            # 检查线程状态
            if not self._is_running:
                return
            
            # 初始化PyAudio
            self.audio = pyaudio.PyAudio()
            self.FORMAT = pyaudio.paInt16
            
            # 打开音频流
            try:
                self.stream = self.audio.open(
                    format=self.FORMAT,
                    channels=self.CHANNELS,
                    rate=self.RATE,
                    input=True,
                    frames_per_buffer=self.CHUNK
                )
            except Exception as e:
                self.error.emit(f"无法打开麦克风: {e}")
                return
            
            if not self._is_running:
                return
            
            self.log_message.emit("🎤 麦克风已准备就绪")
            self.recording_started.emit()  # 发出录音准备就绪信号
            
            # 等待开始录音信号
            while not self.is_recording and self._is_running:
                self.msleep(100)  # 等待100ms
                if not self.isRunning():
                    return
            
            if not self._is_running:
                return
            
            self.log_message.emit("🔴 开始录音...")
            self.audio_frames = []
            
            # 录音循环
            while self.is_recording and self._is_running and self.isRunning():
                try:
                    data = self.stream.read(self.CHUNK, exception_on_overflow=False)
                    self.audio_frames.append(data)
                except Exception as e:
                    self.error.emit(f"录音过程出错: {e}")
                    return
                
                # 每50ms检查一次状态
                self.msleep(50)
            
            if not self._is_running:
                return
            
            if not self.audio_frames:
                self.error.emit("没有录制到音频数据")
                return
            
            self.log_message.emit("⏹️ 录音结束，开始语音识别...")
            
            # 保存录音到临时文件
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile(suffix='.wav', delete=False) as f:
                    temp_file = f.name
                
                # 写入WAV文件
                wf = wave.open(temp_file, 'wb')
                wf.setnchannels(self.CHANNELS)
                wf.setsampwidth(self.audio.get_sample_size(self.FORMAT))
                wf.setframerate(self.RATE)
                wf.writeframes(b''.join(self.audio_frames))
                wf.close()
                
                # 检查线程状态
                if not self._is_running:
                    return
                
                # 调用语音识别
                result = sdk.asr(
                    provider=self.provider,
                    mode="file",
                    audio_file=temp_file,
                    enable_punctuation_prediction=True,
                    enable_voice_detection=True
                )
                
                if not self._is_running:
                    return
                
                if result.get('success', False):
                    recognized_text = result.get('text', '').strip()
                    if recognized_text:
                        self.finished.emit(recognized_text)
                    else:
                        self.error.emit("识别结果为空，请重试")
                else:
                    error_msg = result.get('error', '未知错误')
                    self.error.emit(f"语音识别失败: {error_msg}")
                    
            except Exception as e:
                self.error.emit(f"处理录音文件失败: {e}")
            finally:
                # 清理临时文件
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.unlink(temp_file)
                    except:
                        pass
                
        except Exception as e:
            self.error.emit(f"语音识别过程出错: {str(e)}")
        finally:
            self._is_running = False
            # 清理音频资源
            self.cleanup_audio()
    
    def cleanup_audio(self):
        """清理音频资源"""
        try:
            if self.stream:
                self.stream.stop_stream()
                self.stream.close()
                self.stream = None
            if self.audio:
                self.audio.terminate()
                self.audio = None
        except:
            pass

class InstructionWorker(QThread):
    """指令执行工作线程，避免UI阻塞"""
    # 定义信号
    finished = pyqtSignal(dict)  # 执行完成信号
    error = pyqtSignal(str)      # 错误信号
    log_message = pyqtSignal(str)  # 日志消息信号
    progress_update = pyqtSignal(str)  # 进度更新信号
    
    def __init__(self, decision_system, instruction):
        super().__init__()
        self.decision_system = decision_system
        self.instruction = instruction
        self._is_running = False
    
    def run(self):
        """在后台线程中执行指令"""
        self._is_running = True
        
        try:
            # 清除紧急停止标志，开始新的指令执行
            try:
                from core.embodied_core import embodied_func
                embodied_func.set_emergency_stop_flag(False)
                self.log_message.emit("✅ 全局紧急停止标志已清除")
            except Exception as flag_error:
                self.log_message.emit(f"⚠️ 清除紧急停止标志失败: {flag_error}")
            
            self.log_message.emit(f"🤖 正在执行指令: {self.instruction}")
            self.log_message.emit("-" * 40)
            
            # 重置动作计数器
            self.action_counter = 0
            
            # 检查决策系统是否有效
            if not self.decision_system:
                raise Exception("决策系统未初始化")
            
            # 执行指令
            result = self.decision_system.execute_instruction(self.instruction)
            
            # 检查线程是否被中断
            if not self._is_running:
                self.log_message.emit("⚠️ 任务被中断")
                return
            # 发送完成信号
            self.finished.emit(result)
            
        except Exception as e:
            # 发送错误信号
            error_msg = str(e)
            
            # 根据错误类型提供更详细的信息
            if "模型" in error_msg or "model" in error_msg.lower():
                error_msg += "\n💡 模型可能不支持，请尝试切换其他模型"
            elif "网络" in error_msg or "network" in error_msg.lower():
                error_msg += "\n💡 请检查网络连接"
            elif "API" in error_msg or "密钥" in error_msg:
                error_msg += "\n💡 请检查API密钥配置"
            elif "not found" in error_msg.lower() or "404" in error_msg:
                error_msg += "\n💡 模型名称可能不正确，请检查模型是否存在"
            elif "unauthorized" in error_msg.lower() or "401" in error_msg:
                error_msg += "\n💡 API密钥无效或权限不足"
            elif "rate limit" in error_msg.lower() or "too many" in error_msg.lower():
                error_msg += "\n💡 请求频率过高，请稍后重试"
            
            self.error.emit(error_msg)
        finally:
            self._is_running = False
    
    def stop(self):
        """安全停止线程"""
        self._is_running = False
        if self.isRunning():
            self.requestInterruption()
            # 给线程一些时间自然结束
            if not self.wait(3000):  # 等待3秒
                self.terminate()  # 强制终止
                self.wait()  # 等待终止完成

class StreamInstructionWorker(QThread):
    """流式指令执行工作线程，支持流式输出和动作队列"""
    # 定义信号
    finished = pyqtSignal(dict)  # 执行完成信号
    error = pyqtSignal(str)      # 错误信号
    log_message = pyqtSignal(str)  # 日志消息信号
    progress_update = pyqtSignal(str)  # 进度更新信号
    action_parsed = pyqtSignal(dict)  # 动作解析完成信号
    
    def __init__(self, decision_system, instruction, config_path):
        super().__init__()
        self.decision_system = decision_system
        self.instruction = instruction
        self.config_path = config_path
        self._is_running = False
        
        # 动作队列和执行状态
        self.action_queue = queue.Queue()
        self.executing_action = False
        self.queue_mutex = QMutex()
        self.queue_condition = QWaitCondition()
        
        # 动作计数器
        self.action_counter = 0
        
        # 添加完整AI回答收集
        self.full_ai_response = ""  # 收集完整的AI回答内容
        
        # 动作执行线程
        self.action_executor = None
    
    def run(self):
        """在后台线程中进行流式LLM调用和动作队列管理"""
        self._is_running = True
        
        try:
            # 清除紧急停止标志，开始新的指令执行
            try:
                from core.embodied_core import embodied_func
                embodied_func.set_emergency_stop_flag(False)
            except Exception as flag_error:
                self.log_message.emit(f"⚠️ 清除紧急停止标志失败: {flag_error}")
            
            self.log_message.emit(f"🤖 正在执行指令: {self.instruction}")
            self.log_message.emit("-" * 40)
            
            # 重置动作计数器
            self.action_counter = 0
            self.log_message.emit("🌊 开始流式LLM模型调用...")
            
            # 检查决策系统是否有效
            if not self.decision_system:
                raise Exception("决策系统未初始化")
            
            # 启动动作执行线程
            self.action_executor = ActionExecutorThread(
                self.action_queue, 
                self.decision_system,
                self.queue_mutex,
                self.queue_condition
            )
            self.action_executor.action_completed.connect(self.on_action_completed)
            self.action_executor.action_error.connect(self.on_action_error)
            self.action_executor.log_message.connect(self.log_message)
            self.action_executor.start()
            
            # 进行流式LLM调用
            self.stream_llm_call()
            
            # 等待所有动作执行完成
            self.wait_for_queue_completion()
            
            self.log_message.emit("✅ 所有动作执行完成")
            
            # 历史记录已经在 HighLevelPlanner.plan_task_stream 中自动保存
            # 不需要手动保存
            
            # 发送完成信号
            self.finished.emit({"success": True, "message": "流式执行完成", "full_ai_response": self.full_ai_response})
            
        except Exception as e:
            error_msg = str(e)
            if "模型" in error_msg or "model" in error_msg.lower():
                error_msg += "\n💡 模型可能不支持，请尝试切换其他模型"
            elif "网络" in error_msg or "network" in error_msg.lower():
                error_msg += "\n💡 请检查网络连接"
            elif "API" in error_msg or "密钥" in error_msg:
                error_msg += "\n💡 请检查API密钥配置"
            
            self.error.emit(error_msg)
        finally:
            self._is_running = False
            # 停止动作执行线程
            if self.action_executor:
                self.action_executor.stop()
                self.action_executor.wait()
    
    def stream_llm_call(self):
        """进行流式LLM调用 - 使用统一的HighLevelPlanner接口"""
        try:
            self.log_message.emit("🔄 开始接收流式响应...")
            
            # 检查决策系统是否有效
            if not self.decision_system or not hasattr(self.decision_system, 'high_level_planner'):
                raise Exception("决策系统未正确初始化")
            
            # 定义动作解析回调
            def on_action_parsed(action_data):
                """当HighLevelPlanner解析到动作时的回调"""
                # 添加到队列
                self.action_queue.put(action_data)
                
                # 增加动作计数器
                self.action_counter += 1
                
                # 在动作数据中添加序号信息
                action_data['_sequence_number'] = self.action_counter
                
                # 生成友好的动作描述
                action_desc = self._generate_action_description(action_data)
                self.log_message.emit(f"🎯 {action_desc}")
                
                # 通知动作执行线程
                self.queue_mutex.lock()
                self.queue_condition.wakeOne()
                self.queue_mutex.unlock()
                
                # 发送动作解析信号
                self.action_parsed.emit(action_data)
            
            # 定义chunk接收回调（可选）
            def on_chunk_received(chunk_text):
                """接收到流式文本chunk时的回调"""
                # 可以选择是否显示原始流式输出
                # self.log_message.emit(f"📡 {chunk_text.strip()}")
                pass
            
            # 定义完成回调
            def on_stream_complete(full_response):
                """流式完成时的回调"""
                # 保存完整响应
                self.full_ai_response = full_response
                
                # 显示完整的AI回答
                if full_response.strip():
                    self.log_message.emit("🧠 AI完整回答:")
                    # 将AI回答进行适当换行显示
                    if len(full_response) > 100:
                        # 如果回复很长，进行适当分行
                        lines = full_response.split('\n')
                        for line in lines:
                            if line.strip():
                                self.log_message.emit(f"   {line.strip()}")
                    else:
                        self.log_message.emit(f"   {full_response}")
                    self.log_message.emit("-" * 20)
            
            # 使用统一的HighLevelPlanner流式接口
            self.decision_system.high_level_planner.plan_task_stream(
                user_instruction=self.instruction,
                action_callback=on_action_parsed,
                chunk_callback=on_chunk_received,
                completion_callback=on_stream_complete
            )
            
            # 标记流式输入结束
            self.action_queue.put({"_END_": True})
            self.queue_mutex.lock()
            self.queue_condition.wakeOne()
            self.queue_mutex.unlock()
            
        except Exception as e:
            raise Exception(f"流式LLM调用失败: {str(e)}")
    
    # parse_actions_from_stream 方法已经被 HighLevelPlanner.plan_task_stream 内部处理
    # 不再需要这个方法
    
    def _generate_action_description(self, action_data, include_sequence=True):
        """生成友好的动作描述"""
        func_name = action_data.get('func', '未知函数')
        param = action_data.get('param', {})
        sequence_num = action_data.get('_sequence_number', '')
        
        # 验证函数是否存在
        if func_name != '未知函数':
            try:
                from core.embodied_core.prompt import validate_function_exists
                if not validate_function_exists(func_name):
                    print(f"⚠️ 函数 {func_name} 不存在于embodied_func模块中")
                    # 显示可用函数列表
                    from core.embodied_core.prompt import get_available_function_names
                    available_funcs = get_available_function_names()
            except Exception as e:
                print(f"⚠️ 验证函数存在性时出错: {e}")
        
        # 根据函数类型生成友好描述
        if func_name == 'c_a_j':
            joints = param.get('j_a', [])
            action_desc = f"关节控制 {joints}"
        elif func_name == 'c_a_p':
            pos = param.get('pos', [])
            ori = param.get('ori', [])
            action_desc = f"位置控制 {pos}" + (f" 姿态{ori}" if ori else "")
        elif func_name == 'e_p_a':
            action_name = param.get('a_n', '未知')
            speed = param.get('sp', 'normal')
            action_desc = f"预设动作 \"{action_name}\" (速度:{speed})"
        elif func_name == 'v_s_a':
            prompt = param.get('pr', '请描述你看到的画面')
            voice = param.get('vo', 'longxiaochun')
            action_desc = f"视觉分析与语音播报 (音色:{voice})"
        elif func_name == 'v_r_o':
            obj = param.get('obj', '未知物体')
            action_desc = f"视觉识别物体 \"{obj}\""
        elif func_name == 'c_c_g':
            action = param.get('action', -1)
            if action == 1:
                action_desc = "夹爪张开"
            elif action == 0:
                action_desc = "夹爪闭合"
            else:
                action_desc = f"夹爪控制 ({action})"
        else:
            # 其他函数的通用格式 - 提供更详细的信息
            param_str = str(param)
            if len(param_str) > 40:
                param_str = param_str[:40] + "..."
            
            # 检查是否是真的未知函数
            if func_name == '未知函数':
                action_desc = f"❌ 未知函数({param_str})"
                print(f"⚠️ 检测到未知函数: {action_data}")
            else:
                # 对于其他函数，显示函数名和参数
                action_desc = f"{func_name}({param_str})"
                # 记录新函数以便调试
                print(f"🔍 检测到新函数: {func_name}, 参数: {param}")
        
        # 是否包含序号
        if include_sequence and sequence_num:
            return f"动作{sequence_num}: {action_desc}"
        else:
            return action_desc
    
    # validate_action 和 finalize_stream_parsing 方法已经被 HighLevelPlanner 内部处理
    # 不再需要这些方法
    
    def wait_for_queue_completion(self):
        """等待队列中所有动作执行完成"""
        max_wait_time = 300  # 最大等待5分钟
        start_time = time.time()
        
        while time.time() - start_time < max_wait_time:
            if not self._is_running:
                break
            
            # 检查队列是否为空且没有正在执行的动作
            if self.action_queue.empty() and not self.executing_action:
                break
            
            time.sleep(0.1)
    
    def on_action_completed(self, action_data, result):
        """动作执行完成的回调"""
        self.executing_action = False
        
        # 生成友好的动作描述
        sequence_num = action_data.get('_sequence_number', '')
        action_desc = self._generate_action_description_for_callback(action_data, sequence_num)
        
        if result.get('success'):
            self.log_message.emit(f"✅ 完成{action_desc}")
        else:
            # 根据函数类型提供更友好的错误信息
            func_name = action_data.get('func', '')
            error_msg = self._generate_friendly_error_message(func_name, action_data, result)
            self.log_message.emit(f"❌ 失败{action_desc} - {error_msg}")
    
    def _generate_friendly_error_message(self, func_name, action_data, result):
        """生成友好的错误信息"""
        error_msg = result.get('error', '')
        message = result.get('message', '')
        param = action_data.get('param', {})
        
        # 根据函数类型提供具体的错误信息
        if func_name == 'v_r_o':
            obj = param.get('obj', '未知物体')
            if '未检测到' in message or '未找到' in message:
                return f"未找到目标物体 '{obj}'，请检查物体是否在摄像头视野内"
            elif '摄像头' in message:
                return f"摄像头未启动或无法获取图像，请检查摄像头连接"
            else:
                return f"视觉识别物体 '{obj}' 失败，可能不存在该物体清晰或者确保光线充足"
        elif func_name == 'c_a_j':
            joints = param.get('j_a', [])
            return f"关节运动失败，请检查角度范围 {joints} 是否合理或电机连接状态"
        elif func_name == 'c_a_p':
            pos = param.get('pos', [])
            return f"位置运动失败，请检查目标位置 {pos} 是否在机械臂工作范围内"
        elif func_name == 'e_p_a':
            action_name = param.get('a_n', '未知')
            return f"预设动作 '{action_name}' 执行失败，请检查动作名称是否正确"
        elif func_name == 'c_c_g':
            action = param.get('action', -1)
            action_desc = "张开" if action == 1 else "闭合" if action == 0 else f"控制({action})"
            return f"夹爪{action_desc}失败，请检查夹爪连接状态或参数设置"
        elif func_name == 'v_s_a':
            return f"视觉分析与语音播报失败，请检查AI服务配置或摄像头状态"
        else:
            # 其他函数的通用错误信息
            if error_msg:
                return error_msg
            elif message:
                return message
            else:
                return f"函数 {func_name} 执行失败，请检查参数设置和系统状态"
    
    def on_action_error(self, action_data, error):
        """动作执行错误的回调"""
        self.executing_action = False
        
        # 生成友好的动作描述
        sequence_num = action_data.get('_sequence_number', '')
        action_desc = self._generate_action_description_for_callback(action_data, sequence_num)
        
        self.log_message.emit(f"🚨 错误{action_desc} - {error}")
    
    def _generate_action_description_for_callback(self, action_data, sequence_num):
        """为回调生成友好的动作描述"""
        
        # 复用主要的动作描述生成逻辑
        return self._generate_action_description(action_data, include_sequence=bool(sequence_num))
    
    def stop(self):
        """安全停止线程"""
        self._is_running = False
        if self.action_executor:
            self.action_executor.stop()
        if self.isRunning():
            self.requestInterruption()
            if not self.wait(3000):
                self.terminate()
                self.wait()

class ActionExecutorThread(QThread):
    """动作执行线程，从队列中取出动作并执行"""
    action_completed = pyqtSignal(dict, dict)  # 动作完成信号 (action_data, result)
    action_error = pyqtSignal(dict, str)       # 动作错误信号 (action_data, error)
    log_message = pyqtSignal(str)              # 日志消息信号
    
    def __init__(self, action_queue, decision_system, mutex, condition):
        super().__init__()
        self.action_queue = action_queue
        self.decision_system = decision_system
        self.mutex = mutex
        self.condition = condition
        self._is_running = False
    
    def run(self):
        """执行队列中的动作"""
        self._is_running = True
        
        while self._is_running:
            try:
                # 等待队列中有动作
                self.mutex.lock()
                if self.action_queue.empty():
                    self.condition.wait(self.mutex, 1000)  # 等待1秒
                self.mutex.unlock()
                
                if not self._is_running:
                    break
                
                # 从队列中获取动作
                if not self.action_queue.empty():
                    action_data = self.action_queue.get()
                    
                    # 检查是否是结束标记
                    if action_data.get("_END_"):
                        self.log_message.emit("🏁 动作队列处理完成")
                        break
                    
                    # 执行动作
                    self.execute_action(action_data)
                
            except Exception as e:
                self.log_message.emit(f"❌ 动作执行线程错误: {str(e)}")
    
    def execute_action(self, action_data):
        """执行单个动作"""
        try:
            # 生成友好的动作描述
            sequence_num = action_data.get('_sequence_number', '')
            action_desc = self._generate_simple_action_description(action_data, sequence_num)
            
            self.log_message.emit(f"⚡ 执行{action_desc}")
            
            # 构造单个动作的任务计划格式
            single_action_plan = {
                'func': action_data['func'],
                'param': action_data['param']
            }
            
            # 使用决策系统的中层解析器执行单个动作
            if hasattr(self.decision_system, 'middle_level_parser'):
                result = self.decision_system.middle_level_parser._execute_single_action(
                    single_action_plan['func'], 
                    single_action_plan['param']
                )
            else:
                # 如果没有中层解析器，模拟执行结果
                result = {"success": True, "message": f"模拟执行: {action_data['func']}"}
            
            # 发送完成信号
            self.action_completed.emit(action_data, result)
            
        except Exception as e:
            # 发送错误信号
            self.action_error.emit(action_data, str(e))
    
    def _generate_simple_action_description(self, action_data, sequence_num):
        """为执行器生成简单的动作描述"""
        func_name = action_data.get('func', '未知函数')
        param = action_data.get('param', {})
        
        # 根据函数类型生成简单描述
        if func_name == 'c_a_j':
            joints = param.get('j_a', [])
            action_desc = f"关节控制 {joints}"
        elif func_name == 'c_a_p':
            pos = param.get('pos', [])
            ori = param.get('ori', [])
            action_desc = f"位置控制 {pos}" + (f" 姿态{ori}" if ori else "")
        elif func_name == 'e_p_a':
            action_name = param.get('a_n', '未知')
            speed = param.get('sp', 'normal')
            action_desc = f"预设动作 \"{action_name}\" (速度:{speed})"
        elif func_name == 'v_s_a':
            voice = param.get('vo', 'longxiaochun')
            action_desc = f"视觉分析与语音播报 (音色:{voice})"
        elif func_name == 'v_r_o':
            obj = param.get('obj', '未知物体')
            action_desc = f"视觉识别物体 \"{obj}\""
        elif func_name == 'c_c_g':
            action = param.get('action', -1)
            if action == 1:
                action_desc = "夹爪张开"
            elif action == 0:
                action_desc = "夹爪闭合"
            else:
                action_desc = f"夹爪控制 ({action})"
        else:
            # 其他函数的通用格式
            param_str = str(param)
            if len(param_str) > 40:
                param_str = param_str[:40] + "..."
            action_desc = f"{func_name}({param_str})"
        
        # 是否包含序号
        if sequence_num:
            return f"动作{sequence_num}: {action_desc}"
        else:
            return action_desc
    
    def stop(self):
        """停止执行线程"""
        self._is_running = False
        self.mutex.lock()
        self.condition.wakeOne()
        self.mutex.unlock()

class EmbodiedIntelligenceWidget(QWidget):
    """具身智能控件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        self.decision_system = None  # 决策系统实例
        self.system_initialized = False  # 系统初始化状态
        self.settings_applied = False  # 具身智能参数是否已应用
        
        # 使用统一的电机配置管理器
        self.motor_config_manager = motor_config_manager
        
        # 工作线程管理
        self.instruction_worker = None  # 指令执行工作线程
        self.is_executing = False  # 是否正在执行指令
        
        # 语音录音状态管理
        self.is_recording = False  # 是否正在录音
        self.voice_worker = None  # 语音识别工作线程
        
        # 摄像头管理
        self.camera_worker = None  # 摄像头工作线程
        self.camera_enabled = False  # 摄像头是否启用
        self.camera_label = None  # 摄像头显示标签
        
        # 夹爪控制器相关
        self.claw_controller = None  # 夹爪控制器实例
        self.claw_connected = False  # 夹爪连接状态
        
        # 配置文件路径：优先 ProgramData 外置目录，其次项目内 config
        ext_dir = os.environ.get('HORIZONARM_CONFIG_DIR')
        if ext_dir:
            ext_candidate = os.path.join(ext_dir, 'aisdk_config.yaml')
            self.config_path = ext_candidate if os.path.exists(ext_candidate) else "config/aisdk_config.yaml"
        else:
            self.config_path = "config/aisdk_config.yaml"
        
        # 初始化运动学计算器
        self.kinematics = None
        if KINEMATICS_AVAILABLE:
            try:
                self.kinematics = create_configured_kinematics()
            except Exception as e:
                print(f"运动学计算器初始化失败: {e}")
                self.kinematics = None
        
        self.init_ui()
        
        # 初始化参数状态显示
        try:
            self.update_params_status()
        except Exception as e:
            print(f"⚠️ 初始化参数状态显示失败: {e}")
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            # 重新加载配置管理器的配置
            self.motor_config_manager.config = self.motor_config_manager.load_config()
            print("✅ 具身智能控件：电机配置已重新加载")
        except Exception as e:
            print(f"⚠ 具身智能控件：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            if KINEMATICS_AVAILABLE:
                # 重新创建运动学实例，使用最新的DH参数配置
                self.kinematics = create_configured_kinematics()
                
                # 立即更新界面显示
                self.update_end_effector_pose_display()
            else:
                print("⚠️ 运动学模块不可用，无法重新加载DH参数配置")
        except Exception as e:
            print(f"⚠ 具身智能控件：重新加载DH参数配置失败: {e}")
            self.kinematics = None
    
    def load_config(self):
        """从配置文件加载设置"""
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
        except Exception as e:
            print(f"加载配置文件失败: {e}")
        return {}
    
    def save_config(self, config):
        """保存设置到配置文件"""
        try:
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, default_flow_style=False, allow_unicode=True)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        
        # 创建具身智能系统控制区域（固定在顶部，不滚动）
        self.create_system_control_group(layout)
        
        # 创建标签页切换栏（固定显示，不滚动）
        self.create_tabs(layout)
        
        # 初始化时加载配置文件中的API密钥
        QTimer.singleShot(100, self.load_api_keys)  # 延迟一点确保UI完全创建
    
    def create_system_control_group(self, parent_layout):
        """创建具身智能系统控制组"""
        group = QGroupBox("具身智能系统控制")
        group.setMaximumHeight(140)  # 减少高度，因为减少了一行
        layout = QVBoxLayout(group)
        layout.setSpacing(4)
        layout.setContentsMargins(8, 8, 8, 8)
        
        # 系统状态显示
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("系统状态:"))
        self.system_status_label = QLabel("等待初始化条件")
        self.system_status_label.setProperty("class", "status-disconnected")
        status_layout.addWidget(self.system_status_label)
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 前置条件状态显示和控制按钮在同一行
        condition_layout = QHBoxLayout()
        condition_layout.addWidget(QLabel("前置条件:"))
        
        self.motor_status_label = QLabel("❌ 机械臂未连接")
        self.motor_status_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        condition_layout.addWidget(self.motor_status_label)
        
        condition_layout.addWidget(QLabel(" | "))
        
        self.ai_config_label = QLabel("❌ 具身智能参数未配置")
        self.ai_config_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        condition_layout.addWidget(self.ai_config_label)
        
        # 在前置条件右边添加控制按钮
        condition_layout.addSpacing(20)  # 添加一些间距
        
        self.init_system_btn = QPushButton("🧠 初始化AI系统")
        self.init_system_btn.setProperty("class", "success")
        self.init_system_btn.clicked.connect(self.init_ai_system)
        self.init_system_btn.setMinimumHeight(30)
        self.init_system_btn.setMaximumWidth(150)
        self.init_system_btn.setEnabled(False)  # 默认禁用
        self.init_system_btn.setToolTip("请先连接机械臂并配置具身智能参数")
        condition_layout.addWidget(self.init_system_btn)
        
        self.stop_system_btn = QPushButton("⏹️ 停止系统")
        self.stop_system_btn.setProperty("class", "danger")
        self.stop_system_btn.clicked.connect(self.stop_ai_system)
        self.stop_system_btn.setEnabled(False)
        self.stop_system_btn.setMinimumHeight(30)
        self.stop_system_btn.setMaximumWidth(120)
        condition_layout.addWidget(self.stop_system_btn)
        
        condition_layout.addStretch()
        layout.addLayout(condition_layout)
        
        parent_layout.addWidget(group)
    
    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()
        
        # 机械臂设置标签页
        self.settings_tab = self.create_settings_tab()
        self.tab_widget.addTab(self.settings_tab, "机械臂设置")
        
        # 具身智能控制标签页
        self.intelligence_tab = self.create_intelligence_tab()
        self.tab_widget.addTab(self.intelligence_tab, "具身驱动")
        
        # 状态监控标签页
        self.status_monitor_tab = self.create_status_monitor_tab()
        self.tab_widget.addTab(self.status_monitor_tab, "状态监控")
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_settings_tab(self):
        """创建机械臂设置标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 创建滚动内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # 机械臂设置内容
        self.create_arm_settings_content(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_intelligence_tab(self):
        """创建具身智能标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 创建滚动内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # 具身智能内容
        self.create_intelligence_content(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_status_monitor_tab(self):
        """创建状态监控标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动内容容器
        scroll_content = QWidget()
        content_layout = QVBoxLayout(scroll_content)
        content_layout.setContentsMargins(10, 10, 10, 10)
        content_layout.setSpacing(10)
        
        # 状态监控内容
        self.create_status_monitor_content(content_layout)
        
        # 设置滚动区域的内容
        scroll_area.setWidget(scroll_content)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_arm_settings_content(self, layout):
        """创建机械臂设置内容"""
        # 添加说明信息
        info_label = QLabel("使用说明：选择具身智能服务商并输入API密钥，选择模型，然后点击'应用具身智能设置'。\n• 控制模式：控制真实机械臂，需要连接电机\n• 流式执行：AI输出动作立即执行，适合复杂多步骤指令，大幅提升响应速度\n• 模型选择：如果选择的模型不支持，调用时会返回错误提示\n配置会自动保存到config.yaml文件中，下次启动时自动加载。")
        info_label.setMaximumHeight(120)
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f5f5f5; border-radius: 3px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)

        # 具身智能模型设置
        ai_group = QGroupBox("具身智能模型设置")
        ai_group.setMaximumHeight(380)  # 增加高度以容纳摄像头ID设置
        ai_layout = QFormLayout(ai_group)
        
        # 服务提供商选择
        self.provider_combo = NoWheelComboBox()  # 使用自定义下拉框
        self.provider_combo.addItems(["alibaba","deepseek"])
        self.provider_combo.setCurrentText("alibaba")
        self.provider_combo.currentTextChanged.connect(self.on_provider_changed)  # 添加切换事件
        ai_layout.addRow("服务提供商:", self.provider_combo)
        
        # API Key输入
        self.api_key_input = QLineEdit()
        self.api_key_input.setPlaceholderText("请输入API密钥")
        self.api_key_input.setEchoMode(QLineEdit.Password)  # 隐藏显示
        ai_layout.addRow("API密钥:", self.api_key_input)
        
        # 模型选择
        self.model_combo = NoWheelComboBox()  # 使用自定义下拉框
        # 初始模型列表，会根据服务商动态更新
        self.update_model_list("alibaba")
        ai_layout.addRow("LLM模型:", self.model_combo)
        
        # 添加模型说明
        model_info = QLabel("💡 提示：模型将在调用时自动验证，如果不支持会返回错误信息")
        model_info.setStyleSheet("color: #666; font-size: 10px; margin-left: 5px;")
        model_info.setWordWrap(True)
        ai_layout.addRow("", model_info)
        
        # 控制模式选择（简化为仅真实机械臂）
        self.control_mode_combo = NoWheelComboBox() # 使用自定义下拉框
        self.control_mode_combo.addItem("真实机械臂", "real_only")
        self.control_mode_combo.setCurrentIndex(0)  # 默认真实机械臂
        self.control_mode_combo.setToolTip("控制真实机械臂")
        self.control_mode_combo.setEnabled(False)  # 禁用选择，因为只有一个选项
        ai_layout.addRow("控制模式:", self.control_mode_combo)
        
        # 摄像头ID选择
        self.camera_id_spin = QSpinBox()
        self.camera_id_spin.setRange(0, 10)  # 支持0-10个摄像头设备
        self.camera_id_spin.setValue(0)  # 默认摄像头0
        self.camera_id_spin.setToolTip("选择摄像头设备ID，通常0是默认摄像头，系统初始化时自动启动")
        ai_layout.addRow("摄像头ID:", self.camera_id_spin)
        
        # 应用具身智能设置按钮
        apply_ai_btn = QPushButton("应用具身智能设置")
        apply_ai_btn.clicked.connect(self.apply_settings)
        apply_ai_btn.setMaximumWidth(150)
        apply_ai_btn.setProperty("class", "success")
        apply_ai_btn.setToolTip("保存LLM模型配置，配置后可初始化具身智能系统")
        ai_layout.addRow("", apply_ai_btn)
        
        # 加载配置文件中的API密钥
        self.load_api_keys()
        
        layout.addWidget(ai_group)

        # 视觉抓取参数设置 - 简化为按钮
        params_group = QGroupBox("🤖 视觉抓取参数设置")
        params_layout = QHBoxLayout(params_group)
        params_layout.setSpacing(10)
        

        
        # 抓取参数设置按钮
        self.grasp_params_btn = QPushButton("抓取参数设置")
        self.grasp_params_btn.setProperty("class", "primary")
        self.grasp_params_btn.clicked.connect(self.open_grasp_params_dialog)
        self.grasp_params_btn.setMinimumHeight(35)
        self.grasp_params_btn.setMinimumWidth(150)
        self.grasp_params_btn.setToolTip("设置抓取姿态、运动参数和TCP修正")
        params_layout.addWidget(self.grasp_params_btn)
        
        # 显示当前参数状态
        self.params_status_label = QLabel("参数未设置")
        self.params_status_label.setStyleSheet("color: #f39c12; font-size: 11px; font-weight: bold;")
        params_layout.addWidget(self.params_status_label)
        
        params_layout.addStretch()
        layout.addWidget(params_group)
        
        # 移除原有的减速比设置界面，现在使用统一配置管理器
        # 减速比和方向设置已移至菜单栏"工具"->"电机参数设置"
        
        # 移除安全设置区域，不再显示安全相关选项
    
    def create_intelligence_content(self, layout):
        """创建具身智能内容"""
        # 指令输入区域
        input_group = QGroupBox("自然语言指令输入")
        input_layout = QVBoxLayout(input_group)
        
        # 添加语音对话说明
        voice_info = QLabel("🎤 语音对话: 点击'语音对话'开始录音，再次点击停止录音并自动识别执行。🌊 流式执行：AI输出动作立即执行，提升响应速度。")
        voice_info.setStyleSheet("color: #5bc0de; font-size: 11px; padding: 3px; background-color: #f0f8ff; border-radius: 3px;")
        voice_info.setWordWrap(True)
        input_layout.addWidget(voice_info)
        
        # 指令输入框
        self.instruction_input = QLineEdit()
        self.instruction_input.setPlaceholderText("请输入自然语言指令，例如：机械臂向前伸展、第一个关节转动30度、回到初始位置。")
        self.instruction_input.returnPressed.connect(self.execute_instruction)
        input_layout.addWidget(self.instruction_input)
        
        # 流式执行选项
        stream_layout = QHBoxLayout()
        self.stream_execution_checkbox = QCheckBox("🌊 流式执行")
        self.stream_execution_checkbox.setChecked(True)  # 默认启用流式执行
        self.stream_execution_checkbox.setToolTip("启用后AI输出一个动作就立即执行，提升响应速度")
        stream_layout.addWidget(self.stream_execution_checkbox)
        
        stream_info = QLabel("💡 流式执行：AI输出动作立即执行，无需等待完整回复")
        stream_info.setStyleSheet("color: #5bc0de; font-size: 10px;")
        stream_layout.addWidget(stream_info)
        
        stream_layout.addStretch()
        input_layout.addLayout(stream_layout)
        
        # 执行按钮和示例按钮
        button_layout = QHBoxLayout()
        
        self.execute_btn = QPushButton("🚀 执行指令")
        self.execute_btn.setProperty("class", "success")
        self.execute_btn.clicked.connect(self.execute_instruction)
        self.execute_btn.setEnabled(False)  # 初始禁用，系统初始化后启用
        self.execute_btn.setMaximumWidth(120)
        self.execute_btn.setToolTip("请先初始化AI系统")
        button_layout.addWidget(self.execute_btn)
        
        self.voice_btn = QPushButton("🎤 语音对话")
        self.voice_btn.clicked.connect(self.toggle_voice_recording)
        self.voice_btn.setEnabled(False)  # 初始禁用，系统初始化后启用
        self.voice_btn.setMaximumWidth(120)
        self.voice_btn.setToolTip("点击开始录音，再次点击处理语音")
        button_layout.addWidget(self.voice_btn)
        
        self.clear_btn = QPushButton("🗑️ 清空日志")
        self.clear_btn.clicked.connect(self.clear_log)
        self.clear_btn.setMaximumWidth(100)
        self.clear_btn.setToolTip("清空执行日志和AI对话历史记录")
        button_layout.addWidget(self.clear_btn)
        
        button_layout.addStretch()
        input_layout.addLayout(button_layout)
        
        layout.addWidget(input_group)
        
        # 执行日志和摄像头显示区域（使用水平分割器）
        log_camera_group = QGroupBox("执行日志与摄像头监控")
        log_camera_layout = QVBoxLayout(log_camera_group)
        
        # 创建水平分割器
        self.log_camera_splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：执行日志区域
        log_widget = QWidget()
        log_widget_layout = QVBoxLayout(log_widget)
        log_widget_layout.setContentsMargins(5, 5, 5, 5)
        
        log_title = QLabel("📝 执行日志")
        log_title.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        log_widget_layout.addWidget(log_title)
        
        self.log_display = QPlainTextEdit()
        self.log_display.setReadOnly(True)
        self.log_display.setMaximumHeight(450)
        self.log_display.setMinimumWidth(400)
        self.log_display.setPlainText("🤖 具身智能系统日志\n" + "="*50 + "\n")
        log_widget_layout.addWidget(self.log_display)
        
        self.log_camera_splitter.addWidget(log_widget)
        
        # 右侧：摄像头显示区域
        camera_widget = QWidget()
        camera_widget_layout = QVBoxLayout(camera_widget)
        camera_widget_layout.setContentsMargins(5, 5, 5, 5)
        
        camera_title = QLabel("📷 双目摄像头 (右侧)")
        camera_title.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        camera_widget_layout.addWidget(camera_title)
        
        # 摄像头显示标签
        self.camera_label = QLabel()
        self.camera_label.setMinimumSize(480, 360)
        self.camera_label.setMaximumHeight(450)
        self.camera_label.setMinimumWidth(480)
        self.camera_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                background-color: #f8f9fa;
                color: #666;
                font-size: 14px;
                text-align: center;
            }
        """)
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setText("📷\n摄像头未启动\n系统初始化时将自动尝试启动")
        self.camera_label.setScaledContents(True)  # 自动缩放图像内容
        camera_widget_layout.addWidget(self.camera_label)
        
        self.log_camera_splitter.addWidget(camera_widget)
        
        # 设置分割器的初始比例（左侧占50%，右侧占50%）
        self.log_camera_splitter.setSizes([500, 500])
        
        log_camera_layout.addWidget(self.log_camera_splitter)
        layout.addWidget(log_camera_group)
    
    def create_status_monitor_content(self, layout):
        """创建状态监控内容"""
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.auto_refresh_checkbox = QCheckBox("自动刷新")
        self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        control_layout.addWidget(self.auto_refresh_checkbox)
        
        self.refresh_btn = QPushButton("手动刷新")
        self.refresh_btn.clicked.connect(self.refresh_status)
        control_layout.addWidget(self.refresh_btn)
        
        # 刷新频率设置
        control_layout.addWidget(QLabel("频率:"))
        self.refresh_rate_spin = QSpinBox()
        self.refresh_rate_spin.setRange(1, 10)
        self.refresh_rate_spin.setValue(2)  # 默认2Hz
        self.refresh_rate_spin.setSuffix(" Hz")
        self.refresh_rate_spin.setMaximumWidth(80)
        control_layout.addWidget(self.refresh_rate_spin)
        
        # 连接状态显示
        control_layout.addWidget(QLabel("🔗 连接状态:"))
        
        self.connection_status_label = QLabel("未连接电机")
        self.connection_status_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        control_layout.addWidget(self.connection_status_label)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.setup_status_table()
        layout.addWidget(self.status_table)
        
        # 添加末端位姿显示区域
        self.create_end_effector_pose_display(layout)
        
        # 初始化状态刷新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_status)
    
    def setup_status_table(self):
        """设置状态表格"""
        headers = ["电机ID", "使能", "到位", "位置(°)", "速度(RPM)", "电压(V)", "电流(A)", "温度(°C)"]
        
        self.status_table.setColumnCount(len(headers))
        self.status_table.setHorizontalHeaderLabels(headers)
        self.status_table.horizontalHeader().setStretchLastSection(True)
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.setAlternatingRowColors(True)
        
        
        # 初始化6行数据
        self.status_table.setRowCount(6)
        for i in range(6):
            motor_id = i + 1
            self.status_table.setItem(i, 0, QTableWidgetItem(str(motor_id)))
            for col in range(1, 8):
                self.status_table.setItem(i, col, QTableWidgetItem("未连接"))
        
        # 自动调整行高
        self.status_table.resizeRowsToContents()
    
    def toggle_auto_refresh(self, checked):
        """切换自动刷新"""
        if checked:
            if self.motors:
                interval = int(1000 / self.refresh_rate_spin.value())  # 转换为毫秒
                self.status_timer.start(interval)
            else:
                QMessageBox.warning(self, "警告", "请先连接电机")
                self.auto_refresh_checkbox.setChecked(False)
        else:
            self.status_timer.stop()
    
    def refresh_status(self):
        """刷新状态显示"""
        if not hasattr(self, 'status_table') or not self.motors:
            return
        
        try:
            # 固定显示6行（对应6个关节）
            self.status_table.setRowCount(6)
         
            for i in range(6):
                motor_id = i + 1
                
                # 设置电机ID列
                self.status_table.setItem(i, 0, QTableWidgetItem(str(motor_id)))
                
                if motor_id in self.motors:
                    motor = self.motors[motor_id]
                    
                    try:
                        # 读取状态信息
                        motor_status = motor.read_parameters.get_motor_status()
                        position = motor.read_parameters.get_position()
                        speed = motor.read_parameters.get_speed()
                        voltage = motor.read_parameters.get_bus_voltage()
                        current = motor.read_parameters.get_current()
                        temperature = motor.read_parameters.get_temperature()
                        
                        # 考虑减速比和方向显示正确的输出端角度
                        ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        # 电机读取的角度需要先应用方向修正，再除以减速比得到输出端角度
                        output_position = (position * direction) / ratio

                        # 更新表格
                        self.status_table.setItem(i, 1, QTableWidgetItem("是" if motor_status.enabled else "否"))
                        self.status_table.setItem(i, 2, QTableWidgetItem("是" if motor_status.in_position else "否"))
                        self.status_table.setItem(i, 3, QTableWidgetItem(f"{output_position:.2f}"))
                        self.status_table.setItem(i, 4, QTableWidgetItem(f"{speed:.2f}"))
                        self.status_table.setItem(i, 5, QTableWidgetItem(f"{voltage:.2f}"))
                        self.status_table.setItem(i, 6, QTableWidgetItem(f"{current:.3f}"))
                        self.status_table.setItem(i, 7, QTableWidgetItem(f"{temperature:.1f}"))
                        
                    except Exception as e:
                        # 如果读取失败，显示读取失败
                        for col in range(1, 8):
                            self.status_table.setItem(i, col, QTableWidgetItem("读取失败"))
                else:
                    # 电机未连接
                    for col in range(1, 8):
                        self.status_table.setItem(i, col, QTableWidgetItem("未连接"))
            
            # 更新末端位姿显示
            self.update_end_effector_pose_display()
            
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'刷新状态失败:\n{str(e)}')
    
    def update_status_display(self):
        """更新状态显示（定时器调用）"""
        self.refresh_status()
    
    def check_initialization_conditions(self):
        """检查初始化条件并更新按钮状态"""
        # 简化：只需要真实机械臂模式
        has_motors = len(self.motors) > 0
        has_ai_config = self.settings_applied
        
        # 更新状态显示
        if has_motors:
            motor_count = len(self.motors)
            self.motor_status_label.setText(f"✅ 已连接 {motor_count} 个电机")
            self.motor_status_label.setStyleSheet("color: #5cb85c; font-size: 11px;")
        else:
            self.motor_status_label.setText("❌ 机械臂未连接")
            self.motor_status_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        
        if has_ai_config:
            self.ai_config_label.setText("✅ 具身智能参数已配置")
            self.ai_config_label.setStyleSheet("color: #5cb85c; font-size: 11px;")
        else:
            self.ai_config_label.setText("❌ 具身智能参数未配置")
            self.ai_config_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        
        # 更新按钮状态
        can_initialize = has_motors and has_ai_config and not self.system_initialized
        self.init_system_btn.setEnabled(can_initialize)
        
        # 执行按钮只有在系统已初始化且没有正在执行指令时才启用
        if hasattr(self, 'execute_btn'):
            self.execute_btn.setEnabled(self.system_initialized and not self.is_executing)
        
        # 语音按钮只有在系统已初始化且没有正在执行指令或录音时才启用
        if hasattr(self, 'voice_btn'):
            self.voice_btn.setEnabled(self.system_initialized and not self.is_executing and not self.is_recording)
        
        if can_initialize:
            self.init_system_btn.setToolTip("条件满足，可以初始化AI系统")
            self.system_status_label.setText("准备就绪")
        else:
            missing_conditions = []
            if not has_motors:
                missing_conditions.append("连接机械臂")
            if not has_ai_config:
                missing_conditions.append("配置具身智能参数")
            if self.system_initialized:
                self.init_system_btn.setToolTip("AI系统已初始化")
            else:
                if missing_conditions:
                    self.init_system_btn.setToolTip(f"请先: {', '.join(missing_conditions)}")
                else:
                    self.init_system_btn.setToolTip("可以初始化AI系统")
                self.system_status_label.setText("等待初始化条件")
    
    def init_ai_system(self):
        """初始化AI系统"""
        # 简化：只支持真实机械臂模式
        if not self.motors:
            QMessageBox.warning(self, "错误", "请先连接机械臂！")
            return
        
        if not self.settings_applied:
            QMessageBox.warning(self, "错误", "请先配置LLM参数！\n\n请在'机械臂设置'标签页中配置LLM模型参数并点击'应用设置'。")
            return
        
        try:
            if HierarchicalDecisionSystem is None:
                QMessageBox.warning(self, "错误", "具身智能模块未找到，请检查core目录")
                return
            
            self.log_message("🔧 正在初始化具身智能系统...")
            
            # 获取设置参数
            provider = self.provider_combo.currentText()
            model = self.model_combo.currentText()
            control_mode = "real_only"  # 简化为仅真实机械臂模式
            
            # 从配置文件获取API密钥验证
            config = self.load_config()
            providers = config.get('providers', {})
            if provider not in providers or not providers[provider].get('api_key'):
                QMessageBox.warning(self, "错误", f"配置文件中未找到 {provider} 的API密钥！\n请先在机械臂设置中配置并应用设置。")
                return
            
            # 简化配置检查，只验证供应商和API密钥
            provider_config = providers[provider]
            if not provider_config.get('enabled', False):
                QMessageBox.warning(self, "错误", f"提供商 {provider} 未启用！\n请检查配置文件。")
                return
            
            self.log_message(f"🔍 配置检查通过: {provider}/{model}")
            self.log_message(f"🔑 API密钥: {'已配置' if provider_config.get('api_key') else '未配置'}")
            self.log_message(f"💡 模型将由供应商验证，如果不支持会返回错误")
            
            # 初始化决策系统（HierarchicalDecisionSystem会自动从配置文件读取API密钥）
            self.decision_system = HierarchicalDecisionSystem(
                provider=provider, 
                model=model,
                control_mode=control_mode,
                config_path=self.config_path
            )
            
            self.system_initialized = True
            
            # 设置真实机械臂连接
            try:
                from core.embodied_core import embodied_func
                embodied_func._set_real_motors(
                    motors=self.motors,
                    reducer_ratios=self.motor_config_manager.get_all_reducer_ratios(),
                    directions=self.motor_config_manager.get_all_directions()
                )
                self.log_message("🔗 真实机械臂已连接到具身智能系统")
            except Exception as e:
                self.log_message(f"⚠️ 连接真实机械臂失败: {str(e)}")
            
            # 应用抓取参数设置
            try:
                # 从全局参数管理器获取当前设置
                from core.embodied_core import embodied_func
                grasp_params = embodied_func._get_grasp_params()
                motion_params = embodied_func._get_motion_params()
                
                # 记录当前抓取参数到日志
                self.log_message(f"🤖 当前抓取参数: 速度={motion_params['max_speed']}RPM, 加速度={motion_params['acceleration']}RPM/s")
                self.log_message(f"🎭 抓取姿态: Yaw={grasp_params['yaw']:.1f}°, Pitch={grasp_params['pitch']:.1f}°, Roll={grasp_params['roll']:.1f}°")
                self.log_message(f"🔧 TCP修正: X={grasp_params['tcp_offset_x']:.2f}mm, Y={grasp_params['tcp_offset_y']:.2f}mm, Z={grasp_params['tcp_offset_z']:.2f}mm")
                
                # 更新参数状态显示
                self.update_params_status()
                    
            except Exception as e:
                self.log_message(f"⚠️ 应用抓取参数失败: {str(e)}")
            
            # 自动尝试启动摄像头
            self.log_message("📷 尝试自动启动摄像头...")
            if self.auto_start_camera():
                self.log_message("✅ 摄像头自动启动成功")
            else:
                self.log_message("⚠️ 摄像头自动启动失败，可在具身智能模型设置中调整摄像头ID")
            
            # 更新UI状态
            self.system_status_label.setText("已初始化")
            self.system_status_label.setProperty("class", "status-connected")
            self.init_system_btn.setEnabled(False)
            self.stop_system_btn.setEnabled(True)
            # 只有在没有执行中的指令时才启用执行按钮
            if not self.is_executing:
                self.execute_btn.setEnabled(True)
            
            # 启用语音按钮
            if not self.is_executing and not self.is_recording:
                self.voice_btn.setEnabled(True)
            
            # 启用清空历史记录按钮
            if hasattr(self, 'clear_history_btn'):
                self.clear_history_btn.setEnabled(True)
            
            motor_count = len(self.motors)
            self.log_message(f"✅ 具身智能系统初始化成功！")
            self.log_message(f"📋 使用模型: {provider}/{model}")
            self.log_message(f"🎯 控制模式: 真实机械臂")
            self.log_message(f"🔗 已连接 {motor_count} 个电机，准备接收指令")
            
            # 构建成功消息
            success_message = (f"具身智能系统初始化成功！\n\n"
                f"• LLM模型: {provider}/{model}\n"
                f"• 控制模式: 真实机械臂\n"
                f"• 连接电机: {motor_count} 个\n"
                f"• 现在可以输入自然语言指令控制机械臂")
                
            QMessageBox.information(self, "成功", success_message)
            
        except Exception as e:
            self.log_message(f"❌ 系统初始化失败: {str(e)}")
            QMessageBox.critical(self, "错误", f"具身智能系统初始化失败: {str(e)}")
    
    def emergency_stop(self):
        """紧急停止具身智能系统 - 专用于全局紧急停止"""
        try:
            self.log_message("🛑 具身智能紧急停止触发！")
            
            # 设置全局紧急停止标志，阻止后续动作执行
            try:
                from core.embodied_core import embodied_func
                embodied_func.set_emergency_stop_flag(True)
            except Exception as flag_error:
                self.log_message(f"⚠️ 设置紧急停止标志失败: {flag_error}")
            
            # 立即停止所有执行线程
            if self.instruction_worker and self.instruction_worker.isRunning():
                self.log_message("🛑 紧急停止指令执行线程...")
                self.instruction_worker.stop()
                self._reset_execution_state()
            
            # 停止语音录音线程
            if self.voice_worker and self.voice_worker.isRunning():
                self.log_message("🛑 紧急停止语音录音线程...")
                self.voice_worker.stop()
                self.reset_voice_state()
            
            # 清空任务队列（如果使用的是流式执行线程）
            if (self.instruction_worker and 
                isinstance(self.instruction_worker, StreamInstructionWorker) and 
                self.instruction_worker.isRunning()):
                
                self.log_message("🛑 紧急停止流式执行线程和任务队列...")
                
                # 清空动作队列
                if hasattr(self.instruction_worker, 'action_queue'):
                    try:
                        while not self.instruction_worker.action_queue.empty():
                            self.instruction_worker.action_queue.get_nowait()
                        self.log_message("🛑 任务队列已清空")
                    except Exception as queue_error:
                        self.log_message(f"⚠️ 清空任务队列时出错: {queue_error}")
                
                # 停止动作执行线程
                if hasattr(self.instruction_worker, 'action_executor') and self.instruction_worker.action_executor:
                    self.instruction_worker.action_executor._is_running = False
                    self.log_message("🛑 动作执行线程已停止")
            
            self.log_message("✅ 具身智能紧急停止完成")
            
        except Exception as e:
            self.log_message(f"❌ 具身智能紧急停止失败: {str(e)}")
    
    def stop_ai_system(self):
        """停止AI系统"""
        try:
            # 如果有正在执行的工作线程，先安全停止它
            if self.instruction_worker and self.instruction_worker.isRunning():
                self.log_message("⏹️ 正在停止指令执行线程...")
                self.instruction_worker.stop()  # 使用安全停止方法
                self._reset_execution_state()
            
            # 如果有正在执行的语音工作线程，先安全停止它
            if self.voice_worker and self.voice_worker.isRunning():
                self.log_message("⏹️ 正在停止语音录音线程...")
                self.voice_worker.stop()  # 使用安全停止方法
                self.reset_voice_state()
            
            # 停止摄像头
            if self.camera_enabled:
                self.log_message("⏹️ 正在停止摄像头...")
                self.stop_camera()
            
            self.decision_system = None
            self.system_initialized = False
            
            # 🔗 断开真实机械臂连接
            try:
                from core.embodied_core import embodied_func
                embodied_func._set_real_motors(None, None, None)
                self.log_message("🔌 真实机械臂已从具身智能系统断开")
            except Exception as e:
                self.log_message(f"⚠️ 断开真实机械臂失败: {str(e)}")
            
            # 更新UI状态
            self.system_status_label.setText("已停止")
            self.system_status_label.setProperty("class", "status-disconnected")
            self.stop_system_btn.setEnabled(False)
            # 系统停止后禁用执行按钮
            self.execute_btn.setEnabled(False)
            self.execute_btn.setText("🚀 执行指令")  # 重置按钮文本
            
            # 禁用语音按钮
            self.voice_btn.setEnabled(False)
            self.reset_voice_state()  # 重置语音状态
            
            # 禁用清空历史记录按钮
            if hasattr(self, 'clear_history_btn'):
                self.clear_history_btn.setEnabled(False)
            
            # 重新检查初始化条件
            self.check_initialization_conditions()
            
            self.log_message("⏹️ 具身智能系统已停止")
            QMessageBox.information(self, "成功", "具身智能系统已停止")
            
        except Exception as e:
            self.log_message(f"❌ 停止系统失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"停止系统失败: {str(e)}")
    
    def execute_instruction(self):
        """执行用户指令（使用后台线程避免UI阻塞）"""
        if not self.system_initialized or not self.decision_system:
            QMessageBox.warning(self, "警告", "请先初始化AI系统")
            return
        
        if self.is_executing:
            QMessageBox.warning(self, "提示", "正在执行指令，请稍候...")
            return
        
        instruction = self.instruction_input.text().strip()
        if not instruction:
            QMessageBox.warning(self, "警告", "请输入指令")
            return
        
        # 清除紧急停止标志，开始新的指令执行
        try:
            from core.embodied_core import embodied_func
            embodied_func.set_emergency_stop_flag(False)
        except Exception as flag_error:
            self.log_message(f"⚠️ 清除紧急停止标志失败: {flag_error}")
        
        # 设置执行状态
        self.is_executing = True
        self.execute_btn.setEnabled(False)
        
        # 清空输入框
        self.instruction_input.clear()
        
        # 根据流式执行选项选择不同的工作线程
        if self.stream_execution_checkbox.isChecked():
            # 使用流式执行
            self.execute_btn.setText("🌊 流式执行中...")
            self.log_message("🌊 使用流式执行模式，AI输出动作立即执行")
            
            self.instruction_worker = StreamInstructionWorker(
                self.decision_system, 
                instruction,
                self.config_path
            )
            # 连接流式特有的信号
            self.instruction_worker.action_parsed.connect(self.on_action_parsed)
        else:
            # 使用传统执行
            self.execute_btn.setText("🔄 执行中...")
            self.log_message("⏳ 使用传统执行模式，等待AI完整回复后执行")
            
            self.instruction_worker = InstructionWorker(self.decision_system, instruction)
        
        # 连接通用信号
        self.instruction_worker.finished.connect(self.on_instruction_finished)
        self.instruction_worker.error.connect(self.on_instruction_error)
        self.instruction_worker.log_message.connect(self.log_message)
        self.instruction_worker.start()
    
    @pyqtSlot(dict)
    def on_action_parsed(self, action_data):
        """流式执行中动作解析完成的槽函数"""
        pass
    
    @pyqtSlot(dict)
    def on_instruction_finished(self, result):
        """指令执行完成的槽函数"""
        try:
            # 检查是流式执行还是传统执行的结果格式
            if 'execution_result' in result:
                # 传统执行格式: {task_plan: {...}, execution_result: {...}, llm_response: "..."}
                self._handle_traditional_result(result)
            else:
                # 流式执行格式: {success: True, message: "..."}
                self._handle_stream_result(result)
            
            self.log_message("-" * 40)
            
        except Exception as e:
            self.log_message(f"❌ 处理执行结果时发生错误: {str(e)}")
        finally:
            # 恢复UI状态
            self._reset_execution_state()
    
    def _handle_stream_result(self, result):
        """处理流式执行的结果"""
        success = result.get('success', False)
        message = result.get('message', '')
        full_ai_response = result.get('full_ai_response', '')
        
        # 如果AI回答在流式过程中没有显示，这里显示一次
        # 由于流式执行过程中已经显示了完整回答，这里只显示结果摘要
        if success:
            self.log_message("✅ 流式指令执行成功")
            if message:
                self.log_message(f"📝 执行信息: {message}")
            
            # 显示AI回答摘要（如果有的话）
            if full_ai_response and full_ai_response.strip():
                response_length = len(full_ai_response.strip())
                self.log_message(f"📊 AI回答统计: 共 {response_length} 个字符")
        else:
            self.log_message("❌ 流式指令执行失败") 
            if message:
                self.log_message(f"�� 错误信息: {message}")
    
    def _handle_traditional_result(self, result):
        """处理传统执行的结果"""
        # 显示LLM原始回复
        if result.get('llm_response'):
            self.log_message(f"🧠 LLM原始回复:")
            # 将LLM回复进行适当换行显示
            llm_response = result['llm_response'].strip()
            if len(llm_response) > 100:
                # 如果回复很长，进行适当分行
                lines = llm_response.split('\n')
                for line in lines:
                    if line.strip():
                        self.log_message(f"   {line.strip()}")
            else:
                self.log_message(f"   {llm_response}")
            self.log_message("-" * 20)
        
        # 显示执行结果
        task_plan = result.get('task_plan', {})
        execution_result = result.get('execution_result', {})
        
        # 检查是否为动作序列
        if execution_result.get('sequence_type') == 'action_sequence':
            # 动作序列结果显示
            self._display_sequence_result(task_plan, execution_result)
        else:
            # 单个动作结果显示（原有逻辑）
            self._display_single_action_result(task_plan, execution_result)
    
    def _display_sequence_result(self, task_plan, execution_result):
        """显示动作序列执行结果"""
        total_actions = execution_result.get('total_actions', 0)
        executed_actions = execution_result.get('executed_actions', 0)
        sequence_success = execution_result.get('success', False)
        
        # 显示序列总体信息
        self.log_message(f"🎬 动作序列执行结果:")
        self.log_message(f"   总动作数: {total_actions}")
        self.log_message(f"   已完成: {executed_actions}")
        self.log_message(f"   序列状态: {'✅ 全部完成' if sequence_success else '❌ 部分失败'}")
        
        if execution_result.get('message'):
            self.log_message(f"   序列信息: {execution_result['message']}")
        
        # 添加执行模式说明
        if sequence_success:
            self.log_message(f"   🎯 基于实际到位检测，每个动作完成后立即执行下一个")
        
        self.log_message("-" * 20)
        
        # 显示每个动作的执行结果
        sequence_results = execution_result.get('sequence_results', [])
        for action_result in sequence_results:
            action_index = action_result.get('action_index', '?')
            total_count = action_result.get('total_actions', total_actions)
            func_name = action_result.get('func', '未知')
            action_success = action_result.get('success', False)
            
            status_icon = "✅" if action_success else "❌"
            self.log_message(f"{status_icon} [{action_index}/{total_count}] {func_name}")
            
            # 显示动作参数
            if action_result.get('param'):
                param_str = str(action_result['param'])
                if len(param_str) > 50:
                    param_str = param_str[:50] + "..."
                self.log_message(f"   参数: {param_str}")
            
            # 显示动作结果信息
                # 显示动作结果信息
                if action_result.get('message'):
                    self.log_message(f"   结果: {action_result['message']}")
                elif action_result.get('error'):
                    self.log_message(f"   错误: {action_result['error']}")
                elif not action_success:
                    # 如果没有具体错误信息，生成友好的错误描述
                    func_name = action_result.get('func', '')
                    if func_name:
                        friendly_error = self._generate_friendly_error_message(func_name, action_result, action_result)
                        self.log_message(f"   错误: {friendly_error}")
            
            # 显示到位检测信息
            if action_success and action_index < total_actions:
                self.log_message(f"   🎯 电机已到位，立即开始下一动作")
            
            # 如果动作失败且不是最后一个，说明序列被中断
            if not action_success and action_index < total_actions:
                remaining = total_actions - action_index
                self.log_message(f"   ⚠️ 动作失败，跳过剩余 {remaining} 个动作")
                break
    
    def _display_single_action_result(self, task_plan, execution_result):
        """显示单个动作执行结果（原有逻辑）"""
        if 'func' in task_plan:
            self.log_message(f"🎯 LLM选择的函数: {task_plan['func']}")
            self.log_message(f"📋 函数参数: {task_plan['param']}")
        
        if execution_result.get('success'):
            self.log_message("✅ 指令执行成功")
            if execution_result.get('message'):
                self.log_message(f"📝 执行信息: {execution_result['message']}")
        else:
            self.log_message("❌ 指令执行失败")
            
            # 生成友好的错误信息
            func_name = task_plan.get('func', '')
            if func_name and execution_result:
                friendly_error = self._generate_friendly_error_message(func_name, task_plan, execution_result)
                self.log_message(f"🚨 错误信息: {friendly_error}")
            elif execution_result.get('error'):
                self.log_message(f"🚨 错误信息: {execution_result['error']}")
            
            # 如果是任务规划阶段的错误，也要显示
            if 'error' in task_plan:
                self.log_message(f"🚨 任务规划错误: {task_plan['error']}")
    
    @pyqtSlot(str)
    def on_instruction_error(self, error_message):
        """指令执行错误的槽函数"""
        self.log_message(f"❌ 执行指令时发生错误: {error_message}")
        
        # 提供更详细的错误分析
        if "未知函数" in error_message or "unknown function" in error_message.lower():
            self.log_message("🔍 错误分析: 检测到未知函数错误")
            self.log_message("📝 建议解决方案:")
            self.log_message("  1. 检查 embodied_func.py 中是否存在该函数")
            self.log_message("  2. 确认函数名称拼写正确")
            self.log_message("  3. 检查函数是否正确导出（不以_开头）")
        elif "未找到" in error_message or "未检测到" in error_message or "v_r_o" in error_message:
            self.log_message("🔍 错误分析: 检测到视觉识别错误")
            self.log_message("💡 视觉识别建议:")
            self.log_message("  1. 确保目标物体在摄像头视野内")
            self.log_message("  2. 检查光线是否充足")
            self.log_message("  3. 确保物体与背景有明显对比")
            self.log_message("  4. 尝试调整物体位置或角度")
            self.log_message("  5. 检查摄像头是否正常工作")
        elif "参数" in error_message or "parameter" in error_message.lower():
            self.log_message("🔍 错误分析: 检测到参数错误")
            self.log_message("📝 建议解决方案:")
            self.log_message("  1. 检查函数参数类型和格式")
            self.log_message("  2. 确认参数名称和值的正确性")
        elif "AI" in error_message or "LLM" in error_message or "模型" in error_message:
            self.log_message("🔍 错误分析: 检测到LLM模型错误")
            self.log_message("📝 建议解决方案:")
            self.log_message("  1. 检查网络连接是否正常")
            self.log_message("  2. 验证API密钥是否正确")
            self.log_message("  3. 尝试切换其他模型")
        
        self.log_message("-" * 40)
        # 恢复UI状态
        self._reset_execution_state()
    
    def _reset_execution_state(self):
        """重置执行状态"""
        self.is_executing = False
        self.execute_btn.setEnabled(True)
        self.execute_btn.setText("🚀 执行指令")
        
        # 重新启用语音按钮（如果系统已初始化且未在录音）
        if self.system_initialized and not self.is_recording:
            self.voice_btn.setEnabled(True)
        
        # 安全清理工作线程
        if self.instruction_worker:
            if self.instruction_worker.isRunning():
                self.instruction_worker.stop()
            self.instruction_worker.deleteLater()
            self.instruction_worker = None
    
    def toggle_voice_recording(self):
        """切换语音录音状态"""
        if not self.system_initialized or not self.decision_system:
            QMessageBox.warning(self, "警告", "请先初始化AI系统")
            return
        
        if self.is_executing:
            QMessageBox.warning(self, "提示", "正在执行指令，请稍候...")
            return
        
        if not self.is_recording:
            # 第一次点击：开始录音
            self.start_voice_recording()
        else:
            # 第二次点击：停止录音并处理
            self.stop_voice_recording()
    
    def start_voice_recording(self):
        """开始语音录音"""
        try:
            # 立即设置录音状态和按钮
            self.is_recording = True
            self.voice_btn.setText("🔄 准备中...")
            self.voice_btn.setEnabled(False)
            
            # 获取当前配置的服务提供商
            provider = self.provider_combo.currentText() if hasattr(self, 'provider_combo') else "alibaba"
            
            self.log_message("🎤 准备开始语音录音...")
            self.log_message("💡 说话提示: 请清晰说出机械臂控制指令")
            self.log_message("   例如: '机械臂点头'、'移动到位置200 100 300'、'先点头然后挥手'")
            
            # 创建并启动语音识别工作线程
            self.voice_worker = VoiceRecognitionWorker(self.config_path, provider)
            self.voice_worker.recording_started.connect(self.on_voice_recording_started)
            self.voice_worker.finished.connect(self.on_voice_recognition_finished)
            self.voice_worker.error.connect(self.on_voice_recognition_error)
            self.voice_worker.log_message.connect(self.log_message)
            self.voice_worker.start()
            
        except Exception as e:
            self.log_message(f"❌ 启动录音失败: {str(e)}")
            self.reset_voice_state()
    
    def stop_voice_recording(self):
        """停止语音录音（用户点击停止按钮）"""
        self.voice_btn.setEnabled(False)
        self.voice_btn.setText("🔄 处理中...")
        self.voice_btn.setStyleSheet("")  # 清除红色样式
        
        if self.voice_worker:
            self.voice_worker.stop_recording()  # 通知工作线程停止录音
    
    @pyqtSlot()
    def on_voice_recording_started(self):
        """语音录音准备就绪的槽函数"""
        self.log_message("🔴 正在录音，再次点击按钮停止录音")
        
        # 更新按钮状态为正在录音
        self.voice_btn.setEnabled(True)
        self.voice_btn.setText("⏹️ 停止录音")
        self.voice_btn.setProperty("class", "danger")
        self.voice_btn.setStyleSheet("background-color: #d9534f; color: white;")
        self.voice_btn.setToolTip("点击停止录音并开始识别")
        
        # 自动开始录音
        if self.voice_worker:
            self.voice_worker.start_recording()
    
    @pyqtSlot(str)
    def on_voice_recognition_finished(self, recognized_text):
        """语音识别完成的槽函数"""
        try:
            self.log_message(f"🎯 识别到语音指令: {recognized_text}")
            self.log_message("-" * 30)
            
            # 将识别的文字填入指令输入框
            if hasattr(self, 'instruction_input'):
                self.instruction_input.setText(recognized_text)
            
            # 自动执行识别到的指令
            self.log_message("🚀 自动执行语音指令...")
            
            # 重置语音状态
            self.reset_voice_state()
            
            # 执行指令（复用现有的execute_instruction逻辑）
            self.execute_voice_instruction(recognized_text)
            
        except Exception as e:
            self.log_message(f"❌ 处理语音识别结果时发生错误: {str(e)}")
            self.reset_voice_state()
    
    @pyqtSlot(str)
    def on_voice_recognition_error(self, error_message):
        """语音识别错误的槽函数"""
        self.log_message(f"❌ 语音识别失败: {error_message}")
        
        # 根据错误类型提供具体的解决方案
        if "缺少必要的库" in error_message or "pyaudio" in error_message.lower():
            self.log_message("💡 解决方案: 请安装pyaudio库")
            self.log_message("   Windows: pip install pyaudio")
            self.log_message("   Linux: sudo apt-get install portaudio19-dev python3-pyaudio")
            self.log_message("   macOS: brew install portaudio && pip install pyaudio")
        elif "无法打开麦克风" in error_message:
            self.log_message("💡 解决方案:")
            self.log_message("   1. 检查麦克风是否正常连接")
            self.log_message("   2. 确认已授予应用麦克风权限")
            self.log_message("   3. 关闭其他正在使用麦克风的应用")
        elif "网络" in error_message or "连接" in error_message:
            self.log_message("💡 解决方案: 请检查网络连接是否正常")
        elif "API" in error_message or "密钥" in error_message:
            self.log_message("💡 解决方案: 请检查AI服务配置和API密钥")
        else:
            self.log_message("💡 建议: 请检查麦克风、网络连接和AI服务配置")
        
        self.log_message("-" * 30)
        self.reset_voice_state()
    
    def execute_voice_instruction(self, instruction):
        """执行语音指令（复用现有逻辑）"""
        if not instruction.strip():
            self.log_message("⚠️ 语音指令为空")
            return
        
        # 清除紧急停止标志，开始新的指令执行
        try:
            from core.embodied_core import embodied_func
            embodied_func.set_emergency_stop_flag(False)
            self.log_message("✅ 全局紧急停止标志已清除")
        except Exception as flag_error:
            self.log_message(f"⚠️ 清除紧急停止标志失败: {flag_error}")
        
        
        # 设置执行状态
        self.is_executing = True
        self.execute_btn.setEnabled(False)
        self.voice_btn.setEnabled(False)  # 执行期间禁用语音按钮
        
        # 根据流式执行选项选择不同的工作线程
        if self.stream_execution_checkbox.isChecked():
            # 使用流式执行
            self.execute_btn.setText("🌊 语音流式执行中...")
            
            self.instruction_worker = StreamInstructionWorker(
                self.decision_system, 
                instruction,
                self.config_path
            )
            # 连接流式特有的信号
            self.instruction_worker.action_parsed.connect(self.on_action_parsed)
        else:
            # 使用传统执行
            self.execute_btn.setText("🔄 语音执行中...")
            self.log_message("⏳ 语音指令使用传统执行模式")
            
            self.instruction_worker = InstructionWorker(self.decision_system, instruction)
        
        # 连接通用信号
        self.instruction_worker.finished.connect(self.on_instruction_finished)
        self.instruction_worker.error.connect(self.on_instruction_error)
        self.instruction_worker.log_message.connect(self.log_message)
        self.instruction_worker.start()
    
    def reset_voice_state(self):
        """重置语音状态"""
        self.is_recording = False
        self.voice_btn.setText("🎤 语音对话")
        self.voice_btn.setProperty("class", "")
        self.voice_btn.setStyleSheet("")  # 清除自定义样式
        self.voice_btn.setEnabled(True)
        self.voice_btn.setToolTip("点击开始录音，再次点击处理语音")
        
        # 安全清理语音工作线程
        if self.voice_worker:
            if self.voice_worker.isRunning():
                self.voice_worker.stop()
            self.voice_worker.deleteLater()
            self.voice_worker = None

    def apply_settings(self):
        """应用设置"""
        # 检查API密钥是否已填写
        api_key = self.api_key_input.text().strip()
        if not api_key:
            QMessageBox.warning(self, "错误", "请先输入API密钥！")
            return
        
        # 保存API密钥到配置文件
        try:
            config = self.load_config()
            provider = self.provider_combo.currentText()
            
            # 确保providers节点存在
            if 'providers' not in config:
                config['providers'] = {}
            if provider not in config['providers']:
                config['providers'][provider] = {}
            
            # 更新API密钥
            config['providers'][provider]['api_key'] = api_key
            config['providers'][provider]['enabled'] = True
            
            # 保存配置文件
            if self.save_config(config):
                self.log_message(f"✅ 已保存 {provider} 的API密钥到配置文件")
            else:
                QMessageBox.warning(self, "错误", "保存配置文件失败！")
                return
                
        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存配置时发生错误: {str(e)}")
            return
        
        # 标记具身智能参数已配置
        self.settings_applied = True
        
        # 检查初始化条件
        self.check_initialization_conditions()
        
        # 如果系统已初始化，提示需要重新初始化
        if self.system_initialized:
            reply = QMessageBox.question(self, "重新初始化", 
                                       "设置已更改，需要重新初始化AI系统才能生效。\n是否现在重新初始化？",
                                       QMessageBox.Yes | QMessageBox.No)
            if reply == QMessageBox.Yes:
                self.stop_ai_system()
                self.init_ai_system()
        else:
            QMessageBox.information(self, "成功", f"具身智能参数设置已保存到配置文件！\n\n• 服务商: {provider}\n• 模型: {self.model_combo.currentText()}\n• API密钥: 已加密保存\n• 模型验证: 调用时自动验证\n• 如果机械臂已连接，现在可以初始化AI系统。")

    def clear_log(self):
        """清空日志和历史记录"""
        # 清空日志显示
        self.log_display.setPlainText("🤖 具身智能系统日志\n" + "="*50 + "\n")
        
        # 如果AI系统已初始化，也清空历史记录
        if self.system_initialized and self.decision_system:
            try:
                # 获取清空前的历史数量
                history_count = self.decision_system.get_history_count()
                
                # 清空历史记录
                self.decision_system.clear_history()
                
                # 记录到日志
                if history_count > 0:
                    self.log_message(f"📝 已清空 {history_count} 条历史记录")
                    self.log_message("🔄 日志和历史记录已清空，可以重新开始对话")
                else:
                    self.log_message("🔄 日志已清空")
                    
            except Exception as e:
                self.log_message(f"⚠️ 清空历史记录失败: {str(e)}")
        else:
            self.log_message("🔄 日志已清空")
    
    def clear_history(self):
        """清空AI对话历史记录"""
        if not self.system_initialized or not self.decision_system:
            QMessageBox.warning(self, "提示", "请先初始化AI系统")
            return
        
        try:
            # 获取清空前的历史数量
            history_count = self.decision_system.get_history_count()
            
            # 清空历史记录
            self.decision_system.clear_history()
            
            # 记录到日志
            self.log_message(f"📝 已清空 {history_count} 条历史记录")
            
            # 显示成功消息
            QMessageBox.information(self, "成功", f"已清空 {history_count} 条AI对话历史记录\n现在可以重新开始对话了")
            
        except Exception as e:
            self.log_message(f"❌ 清空历史记录失败: {str(e)}")
            QMessageBox.warning(self, "错误", f"清空历史记录失败: {str(e)}")
    
    def log_message(self, message):
        """添加日志消息"""
        current_time = time.strftime("%H:%M:%S")
        log_entry = f"[{current_time}] {message}"
        
        # 检查log_display是否已创建
        if hasattr(self, 'log_display') and self.log_display is not None:
            # 添加到日志显示
            self.log_display.appendPlainText(log_entry)
            
            # 自动滚动到底部
            cursor = self.log_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            self.log_display.setTextCursor(cursor)
        else:
            # 如果日志控件还未创建，暂时打印到控制台
            print(log_entry)
    
    def update_motors(self, motors):
        """更新电机列表"""
        self.motors = motors
        
        # 使用统一配置管理器，不需要清空和重新初始化减速比设置
        # 配置管理器会自动处理默认值
        
        if motors:
            # 🔗 如果AI系统已初始化，更新真实机械臂连接
            if self.system_initialized:
                try:
                    from core.embodied_core import embodied_func
                    embodied_func._set_real_motors(
                        motors=self.motors,
                        reducer_ratios=self.motor_config_manager.get_all_reducer_ratios(),
                        directions=self.motor_config_manager.get_all_directions()
                    )
                    self.log_message("🔄 真实机械臂连接已更新")
                except Exception as e:
                    self.log_message(f"⚠️ 更新真实机械臂连接失败: {str(e)}")
        
        # 检查初始化条件并更新UI状态
        self.check_initialization_conditions()
        
        # 更新状态显示
        if motors:
            motor_count = len(motors)
            self.log_message(f"🔗 已连接 {motor_count} 个电机: {list(motors.keys())}")
            
            # 更新状态监控表格
            if hasattr(self, 'status_table'):
                self.setup_status_table()
            
            # 更新连接状态显示
            if hasattr(self, 'connection_status_label'):
                self.connection_status_label.setText(f"已连接 {motor_count} 个电机")
                self.connection_status_label.setStyleSheet("color: #5cb85c; font-size: 11px;")
                
        else:
            self.log_message("🔌 电机已断开连接")
            
            # 更新连接状态显示
            if hasattr(self, 'connection_status_label'):
                self.connection_status_label.setText("未连接电机")
                self.connection_status_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        
            self.log_message("🔌 电机连接已清空")
    
    def clear_motors(self):
        """清空电机列表"""
        # 停止状态刷新定时器
        if hasattr(self, 'status_timer') and self.status_timer:
            self.status_timer.stop()
        if hasattr(self, 'auto_refresh_checkbox'):
            self.auto_refresh_checkbox.setChecked(False)
            
        self.motors = {}
        
        # 检查初始化条件并更新UI状态
        self.check_initialization_conditions()
        
        # 清空状态监控表格
        if hasattr(self, 'status_table'):
            self.setup_status_table()
        
        # 更新连接状态显示
        if hasattr(self, 'connection_status_label'):
            self.connection_status_label.setText("未连接电机")
            self.connection_status_label.setStyleSheet("color: #d9534f; font-size: 11px;")
        
        self.log_message("🔌 电机连接已清空")
    
    def update_claw_controller(self, claw_controller):
        """更新夹爪控制器实例（从外部夹爪连接控件接收）"""
        self.claw_controller = claw_controller
        self.claw_connected = claw_controller is not None and claw_controller.is_connected() if claw_controller else False
        
        # 记录连接状态
        if self.claw_connected:
            self.log_message("🤏 夹爪已连接，具身智能可使用夹爪功能")
        else:
            self.log_message("🔌 夹爪已断开，具身智能暂停夹爪功能")
        
        # 更新参数对话框中的夹爪状态（如果对话框已打开）
        # 注意：由于参数对话框是临时创建的，这里主要用于日志记录
        print(f"🤏 具身智能夹爪控制器状态更新: {'已连接' if self.claw_connected else '未连接'}")

    def on_provider_changed(self):
        """当服务提供商切换时更新模型列表"""
        current_provider = self.provider_combo.currentText()
        self.update_model_list(current_provider)
        self.load_api_keys() # 加载对应服务商的API密钥

    def update_model_list(self, provider):
        """根据服务商更新模型列表"""
        self.model_combo.clear()
        if provider == "alibaba":
            self.model_combo.addItems(["qwen-plus", "qwen-turbo", "qwen-max", "qwen-long"])
            self.model_combo.setCurrentText("qwen-plus")
        elif provider == "deepseek":
            self.model_combo.addItems(["deepseek-chat", "deepseek-coder", "deepseek-reasoner"])
            self.model_combo.setCurrentText("deepseek-chat")
        else:
            self.model_combo.addItems(["请选择服务提供商"])
        
        # 添加提示文字
        self.model_combo.setToolTip("选择LLM模型，如果模型不支持，调用时会返回错误")
    
    def load_api_keys(self):
        """从配置文件加载API密钥"""
        config = self.load_config()
        provider = self.provider_combo.currentText()
        
        # 检查providers配置节点
        providers = config.get('providers', {})
        if provider in providers:
            api_key = providers[provider].get('api_key', '')
            self.api_key_input.setText(api_key)
            if api_key and hasattr(self, 'log_display'):
                self.log_message(f"📋 已加载 {provider} 的API密钥")
            elif not api_key and hasattr(self, 'log_display'):
                self.log_message(f"⚠️  {provider} 的API密钥为空，请输入")
        else:
            self.api_key_input.clear()
            if hasattr(self, 'log_display'):
                self.log_message(f"❌ 配置文件中未找到 {provider} 的配置") 

    def open_grasp_params_dialog(self):
        """打开抓取参数设置对话框"""
        try:
            dialog = EmbodiedGraspParametersDialog(self)
            if dialog.exec_() == QDialog.Accepted:
                self.update_params_status()
                print("✅ 抓取参数设置已更新")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"打开参数设置对话框失败: {str(e)}")
    
    def update_params_status(self):
        """更新参数状态显示"""
        try:
            from core.embodied_core import embodied_func
            grasp_params = embodied_func._get_grasp_params()
            motion_params = embodied_func._get_motion_params()
            
            # 简化显示关键参数
            yaw = grasp_params.get("yaw", 0.0)
            pitch = grasp_params.get("pitch", 0.0)  
            roll = grasp_params.get("roll", 180.0)
            speed = motion_params.get("max_speed", 100)
            tcp_x = grasp_params.get("tcp_offset_x", 0.0)
            tcp_y = grasp_params.get("tcp_offset_y", 0.0)
            tcp_z = grasp_params.get("tcp_offset_z", 0.0)
            
            # 检查是否使用默认参数
            is_default = (yaw == 0.0 and pitch == 0.0 and roll == 180.0 and 
                         tcp_x == 0.0 and tcp_y == 0.0 and tcp_z == 0.0 and speed == 100)
            
            if is_default:
                self.params_status_label.setText("默认参数")
                self.params_status_label.setStyleSheet("color: #f39c12; font-size: 11px; font-weight: bold;")
            else:
                self.params_status_label.setText(f"已设置 | {speed}RPM | ({yaw:.0f}°,{pitch:.0f}°,{roll:.0f}°) | TCP({tcp_x:.0f},{tcp_y:.0f},{tcp_z:.0f})")
                self.params_status_label.setStyleSheet("color: #27ae60; font-size: 11px; font-weight: bold;")
                
        except Exception as e:
            self.params_status_label.setText("获取参数失败")
            self.params_status_label.setStyleSheet("color: #e74c3c; font-size: 11px; font-weight: bold;")
            print(f"⚠️ 更新参数状态失败: {e}")

    def apply_reducer_ratios(self):
        """兼容性方法 - 现在抓取参数通过对话框设置"""
        QMessageBox.information(self, "提示", 
            "抓取参数设置已改为对话框方式！\n\n"
            "请点击上方的 '⚙️ 抓取参数设置' 按钮\n"
            "进行详细的视觉抓取参数配置。")


    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            # 如果有正在执行的指令工作线程，先安全停止它
            if self.instruction_worker and self.instruction_worker.isRunning():
                self.instruction_worker.stop()
            
            # 如果有正在执行的语音工作线程，先安全停止它
            if self.voice_worker and self.voice_worker.isRunning():
                self.voice_worker.stop()
            
            # 停止摄像头
            if self.camera_enabled:
                self.stop_camera()
            
            # 停止状态刷新定时器
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            
            # 清理决策系统
            if self.decision_system:
                self.decision_system = None
                
        except Exception as e:
            print(f"⚠️ 清理资源时发生错误: {e}")
        finally:
            event.accept()

    def get_main_window(self):
        """获取主窗口实例"""
        try:
            # 向上遍历父级组件，找到MainWindow
            widget = self
            while widget:
                if hasattr(widget, 'digital_twin_widget'):
                    return widget
                widget = widget.parent()
            return None
        except Exception as e:
            print(f"获取主窗口失败: {e}")
            return None

    def start_camera(self):
        """启动摄像头"""
        try:
            if self.camera_worker is not None:
                self.stop_camera()
            
            # 获取用户选择的摄像头ID
            camera_id = self.camera_id_spin.value() if hasattr(self, 'camera_id_spin') else 0
            
            # 将摄像头ID传递给embodied_internal供具身智能使用
            try:
                from core.embodied_core import embodied_internal
                embodied_internal._set_camera_id(camera_id)
            except ImportError:
                pass  # 如果没有embodied_internal模块就跳过
            except Exception:
                pass  # 静默处理错误，不影响摄像头启动
            
            # 创建摄像头工作线程
            self.camera_worker = CameraWorker(camera_index=camera_id)
            
            # 连接信号
            self.camera_worker.frame_ready.connect(self.update_camera_display)
            self.camera_worker.error.connect(self.on_camera_error)
            
            # 启动摄像头
            self.camera_worker.start_camera()
            
            # 更新状态和UI
            self.camera_enabled = True
            if hasattr(self, 'camera_btn'):
                self.camera_btn.setText("📷 停止摄像头")
                self.camera_btn.setToolTip("停止双目摄像头显示")
            
            self.log_message(f"📷 双目摄像头已启动 (设备ID: {camera_id})")
            
        except Exception as e:
            self.log_message(f"❌ 启动摄像头失败: {str(e)}")
            if hasattr(self, 'camera_btn'):
                QMessageBox.warning(self, "摄像头错误", f"启动摄像头失败：{str(e)}")
            return False
        
        return True
    
    def stop_camera(self):
        """停止摄像头"""
        try:
            if self.camera_worker is not None:
                self.camera_worker.stop_camera()
                self.camera_worker = None
            
            # 更新状态和UI
            self.camera_enabled = False
            
            # 重置摄像头显示 - 清除图像和设置文本
            if self.camera_label:
                self.camera_label.clear()  # 清除之前的图像
                self.camera_label.setText("📷\n摄像头已停止\n系统将在下次初始化时自动尝试启动")
            
            self.log_message("📷 双目摄像头已停止")
            
        except Exception as e:
            self.log_message(f"❌ 停止摄像头失败: {str(e)}")
    
    @pyqtSlot(np.ndarray)
    def update_camera_display(self, frame):
        """更新摄像头显示"""
        try:
            # 将当前帧保存到embodied_internal供具身智能使用
            try:
                from core.embodied_core import embodied_internal
                embodied_internal._set_current_camera_frame(frame.copy())
            except ImportError:
                pass  # 如果没有embodied_internal模块就跳过
            except Exception:
                pass  # 静默处理错误，不影响摄像头显示
            
            # 将OpenCV的BGR格式转换为RGB格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 获取图像尺寸
            height, width, channel = rgb_frame.shape
            bytes_per_line = 3 * width
            
            # 创建QImage
            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap并设置到标签
            pixmap = QPixmap.fromImage(q_image)
            
            # 根据标签大小缩放图像，保持宽高比
            if self.camera_label:
                scaled_pixmap = pixmap.scaled(
                    self.camera_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.camera_label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            self.log_message(f"❌ 更新摄像头显示失败: {str(e)}")
    
    @pyqtSlot(str)
    def on_camera_error(self, error_message):
        """处理摄像头错误"""
        self.log_message(f"❌ 摄像头错误: {error_message}")
        
        # 自动停止摄像头
        if self.camera_enabled:
            self.stop_camera()
    
    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            # 如果有正在执行的指令工作线程，先安全停止它
            if self.instruction_worker and self.instruction_worker.isRunning():
                self.instruction_worker.stop()
            
            # 如果有正在执行的语音工作线程，先安全停止它
            if self.voice_worker and self.voice_worker.isRunning():
                self.voice_worker.stop()
            
            # 停止摄像头
            if self.camera_enabled:
                self.stop_camera()
            
            # 停止状态刷新定时器
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            
            # 清理决策系统
            if self.decision_system:
                self.decision_system = None
                
        except Exception as e:
            print(f"⚠️ 清理资源时发生错误: {e}")
        finally:
            event.accept()

    def auto_start_camera(self):
        """自动检测并启动摄像头"""
        try:
            # 获取用户选择的摄像头ID
            camera_id = self.camera_id_spin.value() if hasattr(self, 'camera_id_spin') else 0
            
            # 先检测摄像头是否可用
            cap = cv2.VideoCapture(camera_id)
            
            if cap.isOpened():
                # 测试读取一帧
                ret, frame = cap.read()
                cap.release()
                
                if ret and frame is not None:
                    # 摄像头可用，启动摄像头显示
                    return self.start_camera()
                else:
                    self.log_message(f"⚠️ 摄像头 {camera_id} 无法读取画面")
                    return False
            else:
                self.log_message(f"⚠️ 摄像头 {camera_id} 不存在或被占用")
                return False
                
        except Exception as e:
            self.log_message(f"⚠️ 检测摄像头时出错: {str(e)}")
            return False

    def create_end_effector_pose_display(self, layout):
        """创建末端执行器位姿显示区域"""
        # 创建末端位姿显示组
        pose_group = QGroupBox("🎯 机械臂末端位姿")
        pose_group.setMaximumHeight(200)
        # 移除高度限制，让内容自然显示
        pose_layout = QVBoxLayout(pose_group)
        
        # 创建位姿信息表格
        self.pose_table = QTableWidget()
        self.setup_pose_table()
        pose_layout.addWidget(self.pose_table)
        
        layout.addWidget(pose_group)
    
    def setup_pose_table(self):
        """设置末端位姿表格"""
        # 设置表格结构：位置(Z,Y,X) 和 姿态(Yaw,Pitch,Roll) - ZYX顺序
        headers = ["项目", "Z/Yaw", "Y/Pitch", "X/Roll", "单位"]
        
        self.pose_table.setColumnCount(len(headers))
        self.pose_table.setHorizontalHeaderLabels(headers)
        self.pose_table.horizontalHeader().setStretchLastSection(True)
        self.pose_table.verticalHeader().setVisible(False)
        self.pose_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pose_table.setAlternatingRowColors(True)
        
        # 设置2行数据：位置和姿态
        self.pose_table.setRowCount(2)
        
        # 位置行
        self.pose_table.setItem(0, 0, QTableWidgetItem("位置"))
        self.pose_table.setItem(0, 1, QTableWidgetItem("--"))  # Z
        self.pose_table.setItem(0, 2, QTableWidgetItem("--"))  # Y  
        self.pose_table.setItem(0, 3, QTableWidgetItem("--"))  # X
        self.pose_table.setItem(0, 4, QTableWidgetItem("mm"))
        
        # 姿态行
        self.pose_table.setItem(1, 0, QTableWidgetItem("姿态"))
        self.pose_table.setItem(1, 1, QTableWidgetItem("--"))  # Yaw
        self.pose_table.setItem(1, 2, QTableWidgetItem("--"))  # Pitch
        self.pose_table.setItem(1, 3, QTableWidgetItem("--"))  # Roll
        self.pose_table.setItem(1, 4, QTableWidgetItem("°"))
        
        # 调整表格高度和列宽
        # 移除高度限制，让表格内容完全显示
        self.pose_table.resizeRowsToContents()
        
        # 设置列宽
        self.pose_table.setColumnWidth(0, 60)  # 项目列
        for i in range(1, 4):  # X/Y/Z 列
            self.pose_table.setColumnWidth(i, 80)
        self.pose_table.setColumnWidth(4, 40)  # 单位列
    
    def update_end_effector_pose_display(self):
        """更新末端执行器位姿显示"""
        if not hasattr(self, 'pose_table') or not self.kinematics:
            return
            
        try:
            # 收集当前所有关节的角度
            joint_angles = []
            all_motors_available = True
            
            for i in range(6):
                motor_id = i + 1
                if motor_id in self.motors:
                    try:
                        motor = self.motors[motor_id]
                        position = motor.read_parameters.get_position()
                        
                        # 考虑减速比和方向计算正确的输出端角度
                        ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        # 电机读取的角度需要先应用方向修正，再除以减速比得到输出端角度
                        output_position = (position * direction) / ratio
                        
                        joint_angles.append(output_position)
                    except Exception:
                        all_motors_available = False
                        break
                else:
                    all_motors_available = False
                    break
            
            if all_motors_available and len(joint_angles) == 6:
                # 使用运动学计算器计算末端位姿
                pose_info = self.kinematics.get_end_effector_pose(joint_angles)
                
                # 提取位置和姿态信息
                position = pose_info['position']  # [x, y, z] 单位：mm
                euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 单位：度（ZYX顺序）
                
                # 更新位置显示 (转换为mm) - ZYX顺序显示
                self.pose_table.setItem(0, 1, QTableWidgetItem(f"{position[2]:.2f}"))  # Z
                self.pose_table.setItem(0, 2, QTableWidgetItem(f"{position[1]:.2f}"))  # Y
                self.pose_table.setItem(0, 3, QTableWidgetItem(f"{position[0]:.2f}"))  # X
                
                # 更新姿态显示 (欧拉角：Yaw, Pitch, Roll) - ZYX顺序显示
                self.pose_table.setItem(1, 1, QTableWidgetItem(f"{euler_angles[0]:.2f}"))  # Yaw (绕Z轴)
                self.pose_table.setItem(1, 2, QTableWidgetItem(f"{euler_angles[1]:.2f}"))  # Pitch (绕Y轴)
                self.pose_table.setItem(1, 3, QTableWidgetItem(f"{euler_angles[2]:.2f}"))  # Roll (绕X轴)
                
            else:
                # 如果电机未全部连接，显示未连接状态
                for row in range(2):
                    for col in range(1, 4):
                        self.pose_table.setItem(row, col, QTableWidgetItem("--"))
                        
        except Exception as e:
            # 如果计算失败，显示错误状态
            for row in range(2):
                for col in range(1, 4):
                    self.pose_table.setItem(row, col, QTableWidgetItem("错误"))
            print(f"末端位姿计算失败: {e}")

class CameraWorker(QThread):
    """摄像头工作线程，用于捕获和处理双目摄像头画面"""
    # 定义信号
    frame_ready = pyqtSignal(np.ndarray)  # 帧准备就绪信号，传递处理后的右侧摄像头画面
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self.cap = None
        self._is_running = False
        self.frame_width = 1280
        self.frame_height = 480  # 根据实际摄像头调整
        
    def start_camera(self):
        """启动摄像头"""
        self._is_running = True
        if not self.isRunning():
            self.start()
    
    def stop_camera(self):
        """停止摄像头"""
        self._is_running = False
        if self.isRunning():
            self.requestInterruption()
            if not self.wait(3000):  # 等待3秒
                self.terminate()
                self.wait()
        # 清理资源
        if self.cap is not None:
            self.cap.release()
            self.cap = None
    
    def run(self):
        """在后台线程中捕获摄像头画面"""
        try:
            # 初始化摄像头
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.error.emit(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            while self._is_running:
                ret, frame = self.cap.read()
                if not ret:
                    self.error.emit("无法读取摄像头画面")
                    break
                
                try:
                    # 分离左右摄像头画面（假设左右并排排列）
                    frame_L = frame[:, 0:640]  # 左侧画面
                    frame_R = frame[:, 640:1280]  # 右侧画面
                    
                    # 只发送右侧摄像头画面
                    self.frame_ready.emit(frame_R)
                    
                except Exception as e:
                    self.error.emit(f"处理摄像头画面时出错: {str(e)}")
                    break
                
                # 控制帧率（约30fps）
                self.msleep(33)
        
        except Exception as e:
            self.error.emit(f"摄像头线程错误: {str(e)}")
        finally:
            if self.cap is not None:
                self.cap.release()
                self.cap = None