# -*- coding: utf-8 -*-
"""
单电机控制组件
"""

import sys
import os
import time
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QScrollArea)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont

# 添加Control_SDK目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
control_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "Control_SDK")
sys.path.insert(0, control_sdk_dir)

class SingleMotorWidget(QWidget):
    """单电机控制组件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        self.current_motor = None  # 当前选中的电机
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        
        # 循环梯形曲线运动相关变量
        self.cycle_timer = QTimer()
        self.cycle_timer.timeout.connect(self.execute_next_action)
        self.cycle_actions = []  # 存储5个动作的参数
        self.current_action_index = 0  # 当前执行的动作索引
        self.is_cycling = False  # 是否正在循环运行
        self.action_start_time = None  # 动作开始时间
        
        self.init_ui()
    
    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            
            # 停止所有定时器
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            
            if hasattr(self, 'cycle_timer') and self.cycle_timer:
                self.cycle_timer.stop()
                self.is_cycling = False
            
            # 停止所有电机运动
            if self.motors:
                try:
                    for motor_id, motor in self.motors.items():
                        motor.control_actions.stop()
                except Exception as e:
                    print(f"⚠️ 停止电机运动时出错: {e}")
            
            print("✅ 单电机控件资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 单电机控件清理资源时发生错误: {e}")
        finally:
            event.accept()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)  # 增大边距
        layout.setSpacing(10)  # 增大间距
        try:
            from PyQt5.QtGui import QIcon
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        # 创建电机选择区域
        self.create_motor_selection(layout)
        
        # 创建标签页
        self.create_tabs(layout)
        
    def create_motor_selection(self, parent_layout):
        """创建电机选择区域"""
        group = QGroupBox("电机选择")
        layout = QHBoxLayout(group)
        
        layout.addWidget(QLabel("选择电机:"))
        
        self.motor_combo = QComboBox()
        self.motor_combo.currentTextChanged.connect(self.on_motor_changed)
        layout.addWidget(self.motor_combo)
        
        # 状态指示器
        self.connection_status = QLabel("未连接")
        self.connection_status.setProperty("class", "status-disconnected")
        layout.addWidget(self.connection_status)
        
        layout.addStretch()
        parent_layout.addWidget(group)
    
    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()
        
        # 基础控制标签页
        self.basic_control_tab = self.create_basic_control_tab()
        self.tab_widget.addTab(self.basic_control_tab, "基础控制")
        
        # 运动控制标签页
        self.motion_control_tab = self.create_motion_control_tab()
        self.tab_widget.addTab(self.motion_control_tab, "运动控制")
        
        # 循环运动标签页（新增）
        self.cycle_motion_tab = self.create_cycle_motion_tab()
        self.tab_widget.addTab(self.cycle_motion_tab, "循环运动")
        
        # 状态监控标签页
        self.status_monitor_tab = self.create_status_monitor_tab()
        self.tab_widget.addTab(self.status_monitor_tab, "状态监控")
        
        # 回零功能标签页
        self.homing_tab = self.create_homing_tab()
        self.tab_widget.addTab(self.homing_tab, "回零功能")
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_basic_control_tab(self):
        """创建基础控制标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 使能控制组
        enable_group = QGroupBox("使能控制")
        enable_layout = QHBoxLayout(enable_group)
        
        self.enable_btn = QPushButton("使能电机")
        self.enable_btn.setProperty("class", "success")
        self.enable_btn.clicked.connect(self.enable_motor)
        enable_layout.addWidget(self.enable_btn)
        
        self.disable_btn = QPushButton("失能电机")
        self.disable_btn.setProperty("class", "warning")
        self.disable_btn.clicked.connect(self.disable_motor)
        enable_layout.addWidget(self.disable_btn)
        
        self.stop_btn = QPushButton("停止电机")
        self.stop_btn.setProperty("class", "danger")
        self.stop_btn.clicked.connect(self.stop_motor)
        enable_layout.addWidget(self.stop_btn)
        
        enable_layout.addStretch()
        layout.addWidget(enable_group)
        
        # 快速操作组
        quick_group = QGroupBox("快速操作")
        quick_layout = QGridLayout(quick_group)
        
        # 清零位置
        self.clear_position_btn = QPushButton("清零位置")
        self.clear_position_btn.clicked.connect(self.clear_position)
        quick_layout.addWidget(self.clear_position_btn, 0, 0)
        
        # 设置零点
        self.set_zero_btn = QPushButton("设置零点")
        self.set_zero_btn.clicked.connect(self.set_zero_position)
        quick_layout.addWidget(self.set_zero_btn, 0, 1)
        
        # 是否保存零点到芯片
        self.save_zero_to_chip_checkbox = QCheckBox("保存零点到芯片")
        self.save_zero_to_chip_checkbox.setChecked(True)
        quick_layout.addWidget(self.save_zero_to_chip_checkbox, 0, 2)
        
        # 解除堵转保护
        self.release_stall_btn = QPushButton("解除堵转保护")
        self.release_stall_btn.clicked.connect(self.release_stall_protection)
        quick_layout.addWidget(self.release_stall_btn, 1, 0)
        
        # 新增：修改电机ID
        self.new_motor_id_spin = QSpinBox()
        self.new_motor_id_spin.setRange(1, 255)
        self.new_motor_id_spin.setValue(1)
        self.new_motor_id_spin.setFixedWidth(80)
        
        self.change_id_btn = QPushButton("修改电机ID")
        self.change_id_btn.setProperty("class", "warning")
        self.change_id_btn.clicked.connect(self.on_change_motor_id)
        
        id_row = QHBoxLayout()
        id_row.setSpacing(8)
        id_row.addWidget(QLabel("新ID:"))
        id_row.addWidget(self.new_motor_id_spin)
        id_row.addWidget(self.change_id_btn)
        id_row.addStretch()
        
        quick_layout.addLayout(id_row, 1, 1, 1, 3)
        self.calibrate_encoder_btn = QPushButton("编码器校准")
        self.calibrate_encoder_btn.clicked.connect(self.calibrate_encoder)
        quick_layout.addWidget(self.calibrate_encoder_btn)
        
        layout.addWidget(quick_group)
        
        # 信息显示组
        info_group = QGroupBox("电机信息")
        info_layout = QFormLayout(info_group)
        
        self.resistance_label = QLabel("未读取")
        self.resistance_label.setStyleSheet("color: #6c757d; font-size: 10px;")
        info_layout.addRow("电阻电感:", self.resistance_label)
        
        layout.addWidget(info_group)
        
        layout.addStretch()
        return widget
    
    def create_motion_control_tab(self):
        """创建运动控制标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)  # 去掉边框
        
        # 创建滚动区域的内容widget
        scroll_widget = QWidget()
        scroll_layout = QGridLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        
        # 减速器设置组 - 移到滚动区域内
        reducer_group = QGroupBox("减速器设置")
        reducer_layout = QHBoxLayout(reducer_group)
        
        # 减速比设置
        reducer_layout.addWidget(QLabel("减速比:"))
        
        self.reducer_ratio_spinbox = QDoubleSpinBox()
        self.reducer_ratio_spinbox.setRange(1.0, 1000.0)
        self.reducer_ratio_spinbox.setValue(1.0)
        self.reducer_ratio_spinbox.setSuffix(" : 1")
        self.reducer_ratio_spinbox.setDecimals(1)
        self.reducer_ratio_spinbox.setMaximumWidth(120)
        reducer_layout.addWidget(self.reducer_ratio_spinbox)
        
        # 角度显示模式
        reducer_layout.addWidget(QLabel("角度显示模式:"))
        
        self.angle_display_mode = QComboBox()
        self.angle_display_mode.addItems(["输出端角度", "电机端角度"])
        self.angle_display_mode.currentTextChanged.connect(self.update_angle_display_mode)
        self.angle_display_mode.setMaximumWidth(150)
        reducer_layout.addWidget(self.angle_display_mode)
        
        # 添加拉伸，让控件左对齐
        reducer_layout.addStretch()
        
        # 添加到网格布局 - 第0行，跨两列
        scroll_layout.addWidget(reducer_group, 0, 0, 1, 2)
        
        # 第一行：速度控制 + 位置控制
        # 速度控制组
        speed_group = QGroupBox("速度模式")
        speed_layout = QFormLayout(speed_group)
        
        # 运动速度
        speed_value_layout = QVBoxLayout()
        speed_value_layout.addWidget(QLabel("运动速度:"))
        
        self.speed_spinbox = QDoubleSpinBox()
        self.speed_spinbox.setRange(0.0, 3000.0)
        self.speed_spinbox.setSuffix(" RPM")
        self.speed_spinbox.setValue(100.0)
        speed_value_layout.addWidget(self.speed_spinbox)
        
        speed_value_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        speed_value_hint.setStyleSheet("color: #666; font-size: 10px;")
        speed_value_layout.addWidget(speed_value_hint)
        
        speed_layout.addRow("", speed_value_layout)
        
        # 转动方向
        speed_direction_layout = QVBoxLayout()
        speed_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.speed_direction = QComboBox()
        self.speed_direction.addItems(["CW", "CCW"])
        speed_direction_layout.addWidget(self.speed_direction)
        
        speed_direction_hint = QLabel("提示：控制电机的转动方向")
        speed_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        speed_direction_layout.addWidget(speed_direction_hint)
        
        speed_layout.addRow("", speed_direction_layout)
        
        # 速度斜率(加速度)
        speed_acceleration_layout = QVBoxLayout()
        speed_acceleration_layout.addWidget(QLabel("速度斜率(加速度):"))
        
        self.acceleration_spinbox = QSpinBox()
        self.acceleration_spinbox.setRange(0, 65535)
        self.acceleration_spinbox.setSuffix(" RPM/s")
        self.acceleration_spinbox.setValue(1000)
        speed_acceleration_layout.addWidget(self.acceleration_spinbox)
        
        speed_acceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        speed_acceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        speed_acceleration_layout.addWidget(speed_acceleration_hint)
        
        speed_layout.addRow("", speed_acceleration_layout)
        
        self.start_speed_btn = QPushButton("开始速度运动")
        self.start_speed_btn.clicked.connect(self.start_speed_motion)
        speed_layout.addRow("", self.start_speed_btn)
        
        # 位置控制组
        position_group = QGroupBox("直通限速位置模式")
        position_layout = QFormLayout(position_group)
        
        # 位置角度
        position_value_layout = QVBoxLayout()
        position_value_layout.addWidget(QLabel("位置角度:"))
        
        self.position_spinbox = QDoubleSpinBox()
        self.position_spinbox.setRange(0.0, 429496729.5)
        self.position_spinbox.setSuffix(" °")
        self.position_spinbox.setValue(90.0)
        position_value_layout.addWidget(self.position_spinbox)
        
        position_value_hint = QLabel("范围：0.0 ~ 429496729.5，单位：°")
        position_value_hint.setStyleSheet("color: #666; font-size: 10px;")
        position_value_layout.addWidget(position_value_hint)
        
        position_layout.addRow("", position_value_layout)
        
        # 运动速度
        position_speed_layout = QVBoxLayout()
        position_speed_layout.addWidget(QLabel("运动速度:"))
        
        self.position_speed_spinbox = QDoubleSpinBox()
        self.position_speed_spinbox.setRange(0.0, 3000.0)
        self.position_speed_spinbox.setSuffix(" RPM")
        self.position_speed_spinbox.setValue(500.0)
        position_speed_layout.addWidget(self.position_speed_spinbox)
        
        position_speed_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        position_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        position_speed_layout.addWidget(position_speed_hint)
        
        position_layout.addRow("", position_speed_layout)
        
        # 转动方向
        position_direction_layout = QVBoxLayout()
        position_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.position_direction = QComboBox()
        self.position_direction.addItems(["CW", "CCW"])
        position_direction_layout.addWidget(self.position_direction)
        
        position_direction_hint = QLabel("提示：控制电机的转动方向")
        position_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        position_direction_layout.addWidget(position_direction_hint)
        
        position_layout.addRow("", position_direction_layout)
        
        # 位置模式
        position_mode_layout = QVBoxLayout()
        position_mode_layout.addWidget(QLabel("位置模式:"))
        
        self.absolute_checkbox = QCheckBox("绝对位置")
        position_mode_layout.addWidget(self.absolute_checkbox)
        
        position_mode_hint = QLabel("提示：勾选绝对位置，不勾选相对位置")
        position_mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        position_mode_layout.addWidget(position_mode_hint)
        
        position_layout.addRow("", position_mode_layout)
        
        self.start_position_btn = QPushButton("开始位置运动")
        self.start_position_btn.clicked.connect(self.start_position_motion)
        position_layout.addRow("", self.start_position_btn)
        
        # 添加到网格布局 - 第一行
        scroll_layout.addWidget(speed_group, 1, 0)
        scroll_layout.addWidget(position_group, 1, 1)
        
        # 第二行：梯形曲线位置控制 + 力矩控制
        # 梯形曲线位置控制组
        trapezoid_group = QGroupBox("梯形曲线加减速位置模式")
        trapezoid_layout = QFormLayout(trapezoid_group)
        
        # 位置角度
        trapezoid_position_layout = QVBoxLayout()
        trapezoid_position_layout.addWidget(QLabel("位置角度:"))
        
        self.trapezoid_position_spinbox = QDoubleSpinBox()
        self.trapezoid_position_spinbox.setRange(0.0, 429496729.5)
        self.trapezoid_position_spinbox.setSuffix(" °")
        self.trapezoid_position_spinbox.setValue(90.0)
        trapezoid_position_layout.addWidget(self.trapezoid_position_spinbox)
        
        trapezoid_position_hint = QLabel("范围：0.0 ~ 429496729.5，单位：°")
        trapezoid_position_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_position_layout.addWidget(trapezoid_position_hint)
        
        trapezoid_layout.addRow("", trapezoid_position_layout)
        
        # 最大速度
        trapezoid_max_speed_layout = QVBoxLayout()
        trapezoid_max_speed_layout.addWidget(QLabel("最大速度:"))
        
        self.trapezoid_max_speed_spinbox = QDoubleSpinBox()
        self.trapezoid_max_speed_spinbox.setRange(0.0, 3000.0)
        self.trapezoid_max_speed_spinbox.setSuffix(" RPM")
        self.trapezoid_max_speed_spinbox.setValue(500.0)
        trapezoid_max_speed_layout.addWidget(self.trapezoid_max_speed_spinbox)
        
        trapezoid_max_speed_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        trapezoid_max_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_max_speed_layout.addWidget(trapezoid_max_speed_hint)
        
        trapezoid_layout.addRow("", trapezoid_max_speed_layout)
        
        # 转动方向
        trapezoid_direction_layout = QVBoxLayout()
        trapezoid_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.trapezoid_direction = QComboBox()
        self.trapezoid_direction.addItems(["CW", "CCW"])
        trapezoid_direction_layout.addWidget(self.trapezoid_direction)
        
        trapezoid_direction_hint = QLabel("提示：控制电机的转动方向")
        trapezoid_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_direction_layout.addWidget(trapezoid_direction_hint)
        
        trapezoid_layout.addRow("", trapezoid_direction_layout)
        
        # 加速加速度
        trapezoid_acceleration_layout = QVBoxLayout()
        trapezoid_acceleration_layout.addWidget(QLabel("加速加速度:"))
        
        self.trapezoid_acceleration_spinbox = QSpinBox()
        self.trapezoid_acceleration_spinbox.setRange(0, 65535)
        self.trapezoid_acceleration_spinbox.setSuffix(" RPM/s")
        self.trapezoid_acceleration_spinbox.setValue(1000)
        trapezoid_acceleration_layout.addWidget(self.trapezoid_acceleration_spinbox)
        
        trapezoid_acceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        trapezoid_acceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_acceleration_layout.addWidget(trapezoid_acceleration_hint)
        
        trapezoid_layout.addRow("", trapezoid_acceleration_layout)
        
        # 减速加速度
        trapezoid_deceleration_layout = QVBoxLayout()
        trapezoid_deceleration_layout.addWidget(QLabel("减速加速度:"))
        
        self.trapezoid_deceleration_spinbox = QSpinBox()
        self.trapezoid_deceleration_spinbox.setRange(0, 65535)
        self.trapezoid_deceleration_spinbox.setSuffix(" RPM/s")
        self.trapezoid_deceleration_spinbox.setValue(1000)
        trapezoid_deceleration_layout.addWidget(self.trapezoid_deceleration_spinbox)
        
        trapezoid_deceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        trapezoid_deceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_deceleration_layout.addWidget(trapezoid_deceleration_hint)
        
        trapezoid_layout.addRow("", trapezoid_deceleration_layout)
        
        # 位置模式
        trapezoid_mode_layout = QVBoxLayout()
        trapezoid_mode_layout.addWidget(QLabel("位置模式:"))
        
        self.trapezoid_absolute_checkbox = QCheckBox("绝对位置")
        trapezoid_mode_layout.addWidget(self.trapezoid_absolute_checkbox)
        
        trapezoid_mode_hint = QLabel("提示：勾选绝对位置，不勾选相对位置")
        trapezoid_mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_mode_layout.addWidget(trapezoid_mode_hint)
        
        trapezoid_layout.addRow("", trapezoid_mode_layout)
        
        self.start_trapezoid_btn = QPushButton("开始梯形曲线运动")
        self.start_trapezoid_btn.clicked.connect(self.start_trapezoid_motion)
        trapezoid_layout.addRow("", self.start_trapezoid_btn)
        
        # 力矩控制组
        torque_group = QGroupBox("力矩模式")
        torque_layout = QFormLayout(torque_group)
        
        # 力矩电流
        torque_current_layout = QVBoxLayout()
        torque_current_layout.addWidget(QLabel("力矩电流:"))
        
        self.torque_spinbox = QSpinBox()
        self.torque_spinbox.setRange(0, 4000)
        self.torque_spinbox.setSuffix(" mA")
        self.torque_spinbox.setValue(500)
        torque_current_layout.addWidget(self.torque_spinbox)
        
        torque_current_hint = QLabel("范围：0 ~ 4000，单位：mA")
        torque_current_hint.setStyleSheet("color: #666; font-size: 10px;")
        torque_current_layout.addWidget(torque_current_hint)
        
        torque_layout.addRow("", torque_current_layout)
        
        # 电流符号
        torque_direction_layout = QVBoxLayout()
        torque_direction_layout.addWidget(QLabel("电流符号:"))
        
        self.torque_direction = QComboBox()
        self.torque_direction.addItems(["CW", "CCW"])
        torque_direction_layout.addWidget(self.torque_direction)
        
        torque_direction_hint = QLabel("提示：控制电机的电流方向")
        torque_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        torque_direction_layout.addWidget(torque_direction_hint)
        
        torque_layout.addRow("", torque_direction_layout)
        
        # 电流斜率(加速度)
        torque_slope_layout = QVBoxLayout()
        torque_slope_layout.addWidget(QLabel("电流斜率(加速度):"))
        
        self.current_slope_spinbox = QSpinBox()
        self.current_slope_spinbox.setRange(0, 65535)
        self.current_slope_spinbox.setSuffix(" mA/s")
        self.current_slope_spinbox.setValue(1000)
        torque_slope_layout.addWidget(self.current_slope_spinbox)
        
        torque_slope_hint = QLabel("范围：0 ~ 65535，单位：mA/s")
        torque_slope_hint.setStyleSheet("color: #666; font-size: 10px;")
        torque_slope_layout.addWidget(torque_slope_hint)
        
        torque_layout.addRow("", torque_slope_layout)
        
        self.start_torque_btn = QPushButton("开始力矩控制")
        self.start_torque_btn.clicked.connect(self.start_torque_control)
        torque_layout.addRow("", self.start_torque_btn)
        
        # 添加到网格布局 - 第二行
        scroll_layout.addWidget(trapezoid_group, 2, 0)
        scroll_layout.addWidget(torque_group, 2, 1)
        
        # 第三行：运动状态显示
        status_group = QGroupBox("运动状态")
        status_layout = QFormLayout(status_group)
        
        self.motion_status_label = QLabel("停止")
        self.motion_status_label.setProperty("class", "status-disconnected")
        status_layout.addRow("当前状态:", self.motion_status_label)
        
        self.current_position_label = QLabel("未读取")
        status_layout.addRow("当前位置:", self.current_position_label)
        
        self.current_speed_label = QLabel("未读取")
        status_layout.addRow("当前速度:", self.current_speed_label)
        
        self.current_torque_label = QLabel("未读取")
        status_layout.addRow("当前力矩:", self.current_torque_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        

        self.stop_motion_btn = QPushButton("停止运动")
        self.stop_motion_btn.setProperty("class", "danger")
        self.stop_motion_btn.clicked.connect(self.stop_motor)
        control_layout.addWidget(self.stop_motion_btn)
        control_layout.addStretch()  # 右侧拉伸
        
        status_layout.addRow("控制:", control_layout)
        
        # 添加到网格布局 - 第三行，跨两列
        scroll_layout.addWidget(status_group, 3, 0, 1, 2)
        
        # 设置列的拉伸比例
        scroll_layout.setColumnStretch(0, 1)
        scroll_layout.setColumnStretch(1, 1)
        
        # 添加垂直拉伸
        scroll_layout.setRowStretch(4, 1)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_cycle_motion_tab(self):
        """创建循环运动标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)  # 去掉边框
        
        # 创建滚动区域的内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(15)
        
        # 减速器设置组
        reducer_group = QGroupBox("减速器设置")
        reducer_layout = QHBoxLayout(reducer_group)
        reducer_layout.setContentsMargins(15, 10, 15, 10)
        
        # 减速比设置
        reducer_layout.addWidget(QLabel("减速比:"))
        
        self.cycle_reducer_ratio_spinbox = QDoubleSpinBox()
        self.cycle_reducer_ratio_spinbox.setRange(1.0, 1000.0)
        self.cycle_reducer_ratio_spinbox.setValue(1.0)
        self.cycle_reducer_ratio_spinbox.setSuffix(" : 1")
        self.cycle_reducer_ratio_spinbox.setDecimals(1)
        self.cycle_reducer_ratio_spinbox.setMaximumWidth(120)
        reducer_layout.addWidget(self.cycle_reducer_ratio_spinbox)
        
        # 角度显示模式
        reducer_layout.addWidget(QLabel("角度显示模式:"))
        
        self.cycle_angle_display_mode = QComboBox()
        self.cycle_angle_display_mode.addItems(["输出端角度", "电机端角度"])
        self.cycle_angle_display_mode.setMaximumWidth(150)
        reducer_layout.addWidget(self.cycle_angle_display_mode)
        
        # 添加拉伸，让控件左对齐
        reducer_layout.addStretch()
        
        scroll_layout.addWidget(reducer_group)
        
        # 动作参数设置表格
        actions_group = QGroupBox("动作参数设置")
        actions_layout = QVBoxLayout(actions_group)
        actions_layout.setContentsMargins(15, 15, 15, 15)
        actions_layout.setSpacing(10)
        
        # 创建表格
        self.actions_table = QTableWidget()
        self.actions_table.setRowCount(5)
        self.actions_table.setColumnCount(6)  # 增加一列
        self.actions_table.setHorizontalHeaderLabels(["位置角度(°)", "最大速度(RPM)", "加速度(RPM/s)", "减速度(RPM/s)", "转动方向", "绝对位置"])
        
        # 设置表格属性 - 让表格可以自然伸展
        self.actions_table.horizontalHeader().setStretchLastSection(True)
        self.actions_table.setAlternatingRowColors(True)
        
        # 设置表格的最小尺寸，让它能够完整显示内容
        self.actions_table.setMinimumHeight(200)
        
        # 调整列宽
        self.actions_table.setColumnWidth(0, 120)  # 位置角度
        self.actions_table.setColumnWidth(1, 120)  # 最大速度  
        self.actions_table.setColumnWidth(2, 120)  # 加速度
        self.actions_table.setColumnWidth(3, 120)  # 减速度
        self.actions_table.setColumnWidth(4, 100)  # 转动方向 - 增加宽度
        
        # 设置行高
        for i in range(5):
            self.actions_table.setRowHeight(i, 35)  # 增加行高以容纳控件
        
        # 设置默认值
        default_actions = [
            [360.0, 500.0, 1000, 1000, "CW", False],
            [360.0, 600.0, 1200, 1200, "CCW", False],
            [180.0, 700.0, 1400, 1400, "CW", False],
            [180.0, 800.0, 1600, 1600, "CCW", False],
            [90.0, 500.0, 1000, 1000, "CW", False]
        ]
        
        for row in range(5):
            for col in range(5):  # 前5列是数值（包括转动方向）
                item = QTableWidgetItem(str(default_actions[row][col]))
                self.actions_table.setItem(row, col, item)
            
            # 第6列：创建绝对位置复选框
            checkbox = QCheckBox()
            checkbox.setChecked(default_actions[row][5])
            # 将复选框居中显示
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.actions_table.setCellWidget(row, 5, checkbox_widget)
        
        actions_layout.addWidget(self.actions_table)
        
        # 快速设置按钮
        quick_set_layout = QHBoxLayout()
        quick_set_layout.setSpacing(15)
        
        self.load_default_btn = QPushButton("加载默认动作")
        self.load_default_btn.clicked.connect(self.load_default_actions)
        self.load_default_btn.setMinimumHeight(35)
        quick_set_layout.addWidget(self.load_default_btn)
        
        self.save_actions_btn = QPushButton("保存当前动作")
        self.save_actions_btn.clicked.connect(self.save_current_actions)
        self.save_actions_btn.setMinimumHeight(35)
        quick_set_layout.addWidget(self.save_actions_btn)
        
        quick_set_layout.addStretch()
        actions_layout.addLayout(quick_set_layout)
        
        scroll_layout.addWidget(actions_group)
        
        # 循环控制
        cycle_control_group = QGroupBox("循环控制")
        cycle_control_layout = QVBoxLayout(cycle_control_group)
        cycle_control_layout.setContentsMargins(15, 15, 15, 15)
        cycle_control_layout.setSpacing(15)
        
        # 动作间隔时间
        interval_layout = QHBoxLayout()
        interval_layout.addWidget(QLabel("动作间隔时间:"))
        
        self.action_interval_spinbox = QDoubleSpinBox()
        self.action_interval_spinbox.setRange(0.1, 60.0)
        self.action_interval_spinbox.setValue(2.0)
        self.action_interval_spinbox.setSuffix(" 秒")
        self.action_interval_spinbox.setDecimals(1)
        self.action_interval_spinbox.setMaximumWidth(120)
        interval_layout.addWidget(self.action_interval_spinbox)
        
        interval_hint = QLabel("提示：每个动作完成后的等待时间")
        interval_hint.setStyleSheet("color: #666; font-size: 10px;")
        interval_layout.addWidget(interval_hint)
        
        interval_layout.addStretch()
        cycle_control_layout.addLayout(interval_layout)
        
        # 控制按钮
        control_buttons_layout = QHBoxLayout()
        control_buttons_layout.setSpacing(15)
        
        self.start_cycle_btn = QPushButton("开始循环运动")
        self.start_cycle_btn.setProperty("class", "success")
        self.start_cycle_btn.clicked.connect(self.start_cycle_motion)
        self.start_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.start_cycle_btn)
        
        self.stop_cycle_btn = QPushButton("停止循环")
        self.stop_cycle_btn.setProperty("class", "warning")
        self.stop_cycle_btn.clicked.connect(self.stop_cycle_motion)
        self.stop_cycle_btn.setEnabled(False)
        self.stop_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.stop_cycle_btn)
        
        self.emergency_stop_cycle_btn = QPushButton("紧急停止")
        self.emergency_stop_cycle_btn.setProperty("class", "danger")
        self.emergency_stop_cycle_btn.clicked.connect(self.emergency_stop_cycle)
        self.emergency_stop_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.emergency_stop_cycle_btn)
        
        control_buttons_layout.addStretch()
        cycle_control_layout.addLayout(control_buttons_layout)
        
        # 状态显示
        status_layout = QHBoxLayout()
        status_layout.setSpacing(20)
        
        status_layout.addWidget(QLabel("循环状态:"))
        
        self.cycle_status_label = QLabel("已停止")
        self.cycle_status_label.setProperty("class", "status-disconnected")
        status_layout.addWidget(self.cycle_status_label)
        
        status_layout.addWidget(QLabel("当前动作:"))
        
        self.current_action_label = QLabel("无")
        status_layout.addWidget(self.current_action_label)
        
        status_layout.addStretch()
        cycle_control_layout.addLayout(status_layout)
        
        scroll_layout.addWidget(cycle_control_group)
        
        # 添加底部空间，确保最后的内容不会被遮挡
        scroll_layout.addSpacing(20)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_status_monitor_tab(self):
        """创建状态监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.auto_refresh_checkbox = QCheckBox("自动刷新")
        self.auto_refresh_checkbox.toggled.connect(self.toggle_auto_refresh)
        control_layout.addWidget(self.auto_refresh_checkbox)
        
        self.refresh_btn = QPushButton("手动刷新")
        self.refresh_btn.clicked.connect(self.refresh_status)
        control_layout.addWidget(self.refresh_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.status_table.setColumnCount(2)
        self.status_table.setHorizontalHeaderLabels(["参数", "值"])
        self.status_table.horizontalHeader().setStretchLastSection(True)
        layout.addWidget(self.status_table)
        
        return widget
    
    def create_homing_tab(self):
        """创建回零功能标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建滚动区域的内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(15)
        scroll_layout.setContentsMargins(5, 5, 5, 5)
        
        # 回零控制组
        homing_control_group = QGroupBox("回零控制")
        homing_control_layout = QFormLayout(homing_control_group)
        
        self.homing_mode_combo = QComboBox()
        self.homing_mode_combo.addItems([
            "就近回零",
            "方向回零",
            "无限位碰撞回零",
            "限位回零",
            "回到绝对位置坐标零点",
            "回到上次掉电位置角度",
        ])
        homing_control_layout.addRow("回零模式:", self.homing_mode_combo)
        
        homing_btn_layout = QHBoxLayout()
        
        self.start_homing_btn = QPushButton("开始回零")
        self.start_homing_btn.clicked.connect(self.start_homing)
        homing_btn_layout.addWidget(self.start_homing_btn)
        
        self.stop_homing_btn = QPushButton("停止回零")
        self.stop_homing_btn.clicked.connect(self.stop_homing)
        homing_btn_layout.addWidget(self.stop_homing_btn)
        

        
        homing_control_layout.addRow("", homing_btn_layout)
        scroll_layout.addWidget(homing_control_group)
        
        # 回零参数设置组
        homing_params_group = QGroupBox("原点回零参数")
        homing_params_layout = QFormLayout(homing_params_group)
        
        # 回零模式选择
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("回零模式:"))
        
        self.homing_param_mode_combo = QComboBox()
        self.homing_param_mode_combo.addItems([
            "就近回零",
            "方向回零",
            "无限位碰撞回零",
            "限位回零",
            "回到绝对位置坐标零点",
            "回到上次掉电位置角度",
        ])
        mode_layout.addWidget(self.homing_param_mode_combo)
        
        mode_hint = QLabel("提示：选择电机回零的方向模式 (注意：只能不带减速器使用，带减速器需要无限位)")
        mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        mode_layout.addWidget(mode_hint)
        
        homing_params_layout.addRow("", mode_layout)
        
        # 回零方向选择
        direction_layout = QVBoxLayout()
        direction_layout.addWidget(QLabel("回零方向:"))
        
        self.homing_direction_combo = QComboBox()
        self.homing_direction_combo.addItems(["顺时针", "逆时针"])
        direction_layout.addWidget(self.homing_direction_combo)
        
        direction_hint = QLabel("提示：电机回零时的旋转方向 (注意：只能不带减速器使用，带减速器需要无限位)")
        direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        direction_layout.addWidget(direction_hint)
        
        homing_params_layout.addRow("", direction_layout)
        
        # 回零速度
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("回零速度:"))
        
        self.homing_speed_spinbox = QSpinBox()
        self.homing_speed_spinbox.setRange(1, 3000)
        self.homing_speed_spinbox.setSuffix(" RPM")
        self.homing_speed_spinbox.setValue(30)
        speed_layout.addWidget(self.homing_speed_spinbox)
        
        speed_hint = QLabel("范围：1 ~ 3000，单位：RPM")
        speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        speed_layout.addWidget(speed_hint)
        
        homing_params_layout.addRow("", speed_layout)
        
        # 回零超时时间
        timeout_layout = QVBoxLayout()
        timeout_layout.addWidget(QLabel("回零超时时间:"))
        
        self.homing_timeout_spinbox = QSpinBox()
        self.homing_timeout_spinbox.setRange(1000, 99999)
        self.homing_timeout_spinbox.setSuffix(" ms")
        self.homing_timeout_spinbox.setValue(10000)
        timeout_layout.addWidget(self.homing_timeout_spinbox)
        
        timeout_hint = QLabel("范围：1000 ~ 99999，单位：ms")
        timeout_hint.setStyleSheet("color: #666; font-size: 10px;")
        timeout_layout.addWidget(timeout_hint)
        
        homing_params_layout.addRow("", timeout_layout)
        
        # 碰撞检测速度
        collision_speed_layout = QVBoxLayout()
        collision_speed_layout.addWidget(QLabel("碰撞检测速度:"))
        
        self.collision_detection_speed_spinbox = QSpinBox()
        self.collision_detection_speed_spinbox.setRange(1, 65535)
        self.collision_detection_speed_spinbox.setSuffix(" RPM")
        self.collision_detection_speed_spinbox.setValue(300)
        collision_speed_layout.addWidget(self.collision_detection_speed_spinbox)
        
        collision_speed_hint = QLabel("范围：1 ~ 65535，单位：RPM")
        collision_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_speed_layout.addWidget(collision_speed_hint)
        
        homing_params_layout.addRow("", collision_speed_layout)
        
        # 碰撞检测电流
        collision_current_layout = QVBoxLayout()
        collision_current_layout.addWidget(QLabel("碰撞检测电流:"))
        
        self.collision_detection_current_spinbox = QSpinBox()
        self.collision_detection_current_spinbox.setRange(1, 65535)
        self.collision_detection_current_spinbox.setSuffix(" mA")
        self.collision_detection_current_spinbox.setValue(800)
        collision_current_layout.addWidget(self.collision_detection_current_spinbox)
        
        collision_current_hint = QLabel("范围：1 ~ 65535，单位：mA")
        collision_current_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_current_layout.addWidget(collision_current_hint)
        
        homing_params_layout.addRow("", collision_current_layout)
        
        # 碰撞检测时间
        collision_time_layout = QVBoxLayout()
        collision_time_layout.addWidget(QLabel("碰撞检测时间:"))
        
        self.collision_detection_time_spinbox = QSpinBox()
        self.collision_detection_time_spinbox.setRange(1, 65535)
        self.collision_detection_time_spinbox.setSuffix(" ms")
        self.collision_detection_time_spinbox.setValue(60)
        collision_time_layout.addWidget(self.collision_detection_time_spinbox)
        
        collision_time_hint = QLabel("范围：1 ~ 65535，单位：ms")
        collision_time_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_time_layout.addWidget(collision_time_hint)
        
        homing_params_layout.addRow("", collision_time_layout)
        
        # 上电自动回零
        auto_homing_layout = QVBoxLayout()
        auto_homing_layout.addWidget(QLabel("上电自动回零:"))
        
        self.auto_homing_checkbox = QCheckBox("Disable")
        self.auto_homing_checkbox.toggled.connect(self.on_auto_homing_toggled)
        auto_homing_layout.addWidget(self.auto_homing_checkbox)
        
        auto_homing_hint = QLabel("提示：Enable开启，Disable关闭")
        auto_homing_hint.setStyleSheet("color: #666; font-size: 10px;")
        auto_homing_layout.addWidget(auto_homing_hint)
        
        homing_params_layout.addRow("", auto_homing_layout)
        
        # 是否存储参数
        save_layout = QVBoxLayout()
        self.save_homing_params_checkbox = QCheckBox("是否存储")
        self.save_homing_params_checkbox.setChecked(True)
        save_layout.addWidget(self.save_homing_params_checkbox)
        
        save_hint = QLabel("提示：勾选后参数将保存到芯片")
        save_hint.setStyleSheet("color: #666; font-size: 10px;")
        save_layout.addWidget(save_hint)
        
        homing_params_layout.addRow("", save_layout)
        
        # 参数操作按钮
        homing_params_btn_layout = QHBoxLayout()
        
        self.read_homing_params_btn = QPushButton("读取回零参数")
        self.read_homing_params_btn.clicked.connect(self.read_homing_parameters)
        homing_params_btn_layout.addWidget(self.read_homing_params_btn)
        
        self.modify_homing_params_btn = QPushButton("修改回零参数")
        self.modify_homing_params_btn.clicked.connect(self.modify_homing_parameters)
        homing_params_btn_layout.addWidget(self.modify_homing_params_btn)
        
        homing_params_layout.addRow("", homing_params_btn_layout)
        
        scroll_layout.addWidget(homing_params_group)
        
        # 回零状态显示
        status_group = QGroupBox("回零状态")
        status_layout = QFormLayout(status_group)
        
        self.homing_status_label = QLabel("未读取")
        status_layout.addRow("回零状态:", self.homing_status_label)
        
        scroll_layout.addWidget(status_group)
        
        # 添加拉伸
        scroll_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def on_auto_homing_toggled(self, checked):
        """上电自动回零状态切换"""
        self.auto_homing_checkbox.setText("Enable" if checked else "Disable")
    
    def update_motors(self, motors):
        """更新电机列表"""
        self.motors = motors
        self.motor_combo.clear()
        
        if motors:
            motor_ids = sorted(motors.keys())
            for motor_id in motor_ids:
                self.motor_combo.addItem(f"电机 {motor_id}")
            
            # 选择第一个电机
            if motor_ids:
                self.current_motor = motors[motor_ids[0]]
                self.connection_status.setText("已连接")
                self.connection_status.setProperty("class", "status-connected")
                self.connection_status.setStyle(self.connection_status.style())  # 刷新样式
                self.enable_controls(True)
                # 按驱动板版本调整回零模式
                self._apply_drive_version_homing_modes()
                self.load_motor_info()
        else:
            self.clear_motors()
    
    def clear_motors(self):
        """清空电机列表"""
        self.motors = {}
        self.current_motor = None
        self.motor_combo.clear()
        self.connection_status.setText("未连接")
        self.connection_status.setProperty("class", "status-disconnected")
        self.connection_status.setStyle(self.connection_status.style())  # 刷新样式
        self.enable_controls(False)
        self.status_timer.stop()
    
    def on_motor_changed(self, text):
        """电机选择改变"""
        if not text or not self.motors:
            return
        
        try:
            motor_id = int(text.split()[-1])
            self.current_motor = self.motors.get(motor_id)
            if self.current_motor:
                # 按驱动板版本调整回零模式
                self._apply_drive_version_homing_modes()
                self.load_motor_info()
        except:
            pass
    
    def enable_controls(self, enabled):
        """启用/禁用控件"""
        # 设置所有控件的启用状态
        for tab_index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(tab_index)
            tab.setEnabled(enabled)
    
    def load_motor_info(self):
        """加载电机信息"""
        if not self.current_motor:
            return
        
        try:
            
            # 读取电阻电感
            ri_info = self.current_motor.read_parameters.get_resistance_inductance()
            self.resistance_label.setText(f"电阻: {ri_info['resistance']:.3f}Ω, 电感: {ri_info['inductance']:.3f}mH")
            
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'读取电机信息失败:\n{str(e)}')
    
    def toggle_auto_refresh(self, checked):
        """切换自动刷新"""
        if checked:
            self.status_timer.start(1000)  # 每秒刷新
        else:
            self.status_timer.stop()
    
    def get_actual_angle(self, input_angle):
        """根据减速比和显示模式计算实际发送给电机的角度"""
        reducer_ratio = self.reducer_ratio_spinbox.value()
        display_mode = self.angle_display_mode.currentText()
        
        if display_mode == "输出端角度":
            # 用户输入的是减速器输出端角度，需要乘以减速比
            return input_angle * reducer_ratio
        else:
            # 用户输入的是电机端角度，直接使用
            return input_angle
    
    def get_display_angle(self, motor_angle):
        """根据减速比和显示模式将电机角度转换为显示角度"""
        reducer_ratio = self.reducer_ratio_spinbox.value()
        display_mode = self.angle_display_mode.currentText()
        
        if display_mode == "输出端角度":
            # 显示减速器输出端角度
            return motor_angle / reducer_ratio
        else:
            # 显示电机端角度
            return motor_angle
    
    def get_cycle_actual_angle(self, input_angle):
        """循环运动：根据减速比和显示模式计算实际发送给电机的角度"""
        reducer_ratio = self.cycle_reducer_ratio_spinbox.value()
        display_mode = self.cycle_angle_display_mode.currentText()
        
        if display_mode == "输出端角度":
            # 用户输入的是减速器输出端角度，需要乘以减速比
            return input_angle * reducer_ratio
        else:
            # 用户输入的是电机端角度，直接使用
            return input_angle
    
    def get_cycle_display_angle(self, motor_angle):
        """循环运动：根据减速比和显示模式将电机角度转换为显示角度"""
        reducer_ratio = self.cycle_reducer_ratio_spinbox.value()
        display_mode = self.cycle_angle_display_mode.currentText()
        
        if display_mode == "输出端角度":
            # 显示减速器输出端角度
            return motor_angle / reducer_ratio
        else:
            # 显示电机端角度
            return motor_angle
    
    def update_angle_display_mode(self):
        """更新角度显示模式"""
        display_mode = self.angle_display_mode.currentText()
        reducer_ratio = self.reducer_ratio_spinbox.value()
        
        if display_mode == "输出端角度":
            # 更新位置控制的最大值，考虑减速比
            max_output_angle = 429496729.5 / reducer_ratio
            self.position_spinbox.setRange(0.0, max_output_angle)
            self.trapezoid_position_spinbox.setRange(0.0, max_output_angle)
            
            # 更新提示文本 - 需要找到对应的hint标签
            # 在运动控制tab中找到对应的hint标签并更新
            try:
                # 更新位置控制的hint
                position_hint_text = f"范围：0.0 ~ {max_output_angle:.1f}，单位：°（输出端）"
                # 更新梯形控制的hint
                trapezoid_hint_text = f"范围：0.0 ~ {max_output_angle:.1f}，单位：°（输出端）"
                
                # 这里我们需要在界面刷新时更新，而不是直接查找widget
                # 因为布局结构比较复杂，我们在motion control tab的创建时会设置这些hint
                
            except Exception as e:
                pass  # 如果找不到对应的widget，忽略错误
        else:
            # 恢复电机端角度范围
            self.position_spinbox.setRange(0.0, 429496729.5)
            self.trapezoid_position_spinbox.setRange(0.0, 429496729.5)
            
            # 更新提示文本
            try:
                position_hint_text = "范围：0.0 ~ 429496729.5，单位：°（电机端）"
                trapezoid_hint_text = "范围：0.0 ~ 429496729.5，单位：°（电机端）"
                
            except Exception as e:
                pass  # 如果找不到对应的widget，忽略错误

    def refresh_status(self):
        """刷新状态显示"""
        if not self.current_motor:
            return
        
        try:
            # 读取各种状态参数
            status_data = []
            
            # 基本状态
            motor_status = self.current_motor.read_parameters.get_motor_status()
            status_data.append(["使能状态", "是" if motor_status.enabled else "否"])
            status_data.append(["到位状态", "是" if motor_status.in_position else "否"])
            status_data.append(["堵转状态", "是" if motor_status.stalled else "否"])
            
            # 位置和速度
            motor_position = self.current_motor.read_parameters.get_position()
            display_position = self.get_display_angle(motor_position)
            speed = self.current_motor.read_parameters.get_speed()
            
            display_mode = self.angle_display_mode.currentText()
            status_data.append(["当前位置", f"{display_position:.2f} 度 ({display_mode})"])
            status_data.append(["当前速度", f"{speed:.2f} RPM"])
            
            # 电压电流
            voltage = self.current_motor.read_parameters.get_bus_voltage()
            current = self.current_motor.read_parameters.get_current()
            status_data.append(["总线电压", f"{voltage:.2f} V"])
            status_data.append(["相电流", f"{current:.3f} A"])
            
            # 温度
            temperature = self.current_motor.read_parameters.get_temperature()
            status_data.append(["温度", f"{temperature:.1f} °C"])
            
            # 减速比信息
            reducer_ratio = self.reducer_ratio_spinbox.value()
            status_data.append(["减速比", f"{reducer_ratio:.1f} : 1"])
            
            # 更新表格
            self.status_table.setRowCount(len(status_data))
            for row, (param, value) in enumerate(status_data):
                self.status_table.setItem(row, 0, QTableWidgetItem(param))
                self.status_table.setItem(row, 1, QTableWidgetItem(str(value)))
            
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'读取状态失败:\n{str(e)}')
    
    def update_status_display(self):
        """更新状态显示（定时器调用）"""
        self.refresh_status()
    
    # 基础控制方法
    def enable_motor(self):
        """使能电机"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.enable()
            QMessageBox.information(self, '成功', '电机使能成功')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'电机使能失败:\n{str(e)}')
    
    def disable_motor(self):
        """失能电机"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.disable()
            QMessageBox.information(self, '成功', '电机失能成功')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'电机失能失败:\n{str(e)}')
    
    def stop_motor(self):
        """停止电机"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.stop()
            QMessageBox.information(self, '成功', '电机停止成功')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'电机停止失败:\n{str(e)}')
    
    def clear_position(self):
        """清零位置"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.trigger_actions.clear_position()
            QMessageBox.information(self, '成功', '位置清零成功')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'位置清零失败:\n{str(e)}')
    
    def set_zero_position(self):
        """设置零点位置"""
        if not self.current_motor:
            return
        
        try:
            save_to_chip = self.save_zero_to_chip_checkbox.isChecked()
            self.current_motor.control_actions.set_zero_position(save_to_chip=save_to_chip)
            save_info = "已保存到芯片" if save_to_chip else "未保存到芯片"
            QMessageBox.information(self, '成功', f'零点设置成功 ({save_info})')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'零点设置失败:\n{str(e)}')
    
    def release_stall_protection(self):
        """解除堵转保护"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.trigger_actions.release_stall_protection()
            QMessageBox.information(self, '成功', '堵转保护已解除')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'解除堵转保护失败:\n{str(e)}')
    
    def on_change_motor_id(self):
        """修改电机ID（基础控制-快速操作）"""
        if not self.current_motor:
            return
        try:
            new_id = int(self.new_motor_id_spin.value())
            # 二次确认
            ret = QMessageBox.question(self, '确认修改', f'将把当前电机ID修改为 {new_id}，确定继续？', QMessageBox.Yes | QMessageBox.No)
            if ret != QMessageBox.Yes:
                return
            # 调用SDK的修改参数接口
            self.current_motor.modify_parameters.set_motor_id(new_id)
            QMessageBox.information(self, '成功', f'已发送修改ID命令，新ID: {new_id}\n提示：部分驱动需断电重启后生效')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'修改电机ID失败:\n{str(e)}')
    
    # 运动控制方法
    def start_speed_motion(self):
        """开始速度运动"""
        if not self.current_motor:
            return
        
        try:
            speed = self.speed_spinbox.value()
            direction = self.speed_direction.currentText()  # CW/CCW
            acceleration = self.acceleration_spinbox.value()
            
            # 根据方向调整速度值
            if direction == "CCW":  # 逆时针
                speed = -speed
            
            self.current_motor.control_actions.set_speed(
                speed=speed,
                acceleration=acceleration
            )
            QMessageBox.information(self, '成功', f'速度运动开始: {speed} RPM')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'速度运动失败:\n{str(e)}')
    
    def start_position_motion(self):
        """开始位置运动"""
        if not self.current_motor:
            return
        
        try:
            input_position = self.position_spinbox.value()
            actual_position = self.get_actual_angle(input_position)
            speed = self.position_speed_spinbox.value()
            direction = self.position_direction.currentText()  # CW/CCW
            is_absolute = self.absolute_checkbox.isChecked()
            
            # 根据方向调整位置值（仅对相对位置有效）
            if direction == "CCW" and not is_absolute:  # 逆时针且为相对位置
                actual_position = -actual_position
            
            self.current_motor.control_actions.move_to_position(
                position=actual_position,
                speed=speed,
                is_absolute=is_absolute
            )
            
            display_mode = self.angle_display_mode.currentText()
            QMessageBox.information(self, '成功', f'位置运动开始: {input_position} 度 ({display_mode})')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'位置运动失败:\n{str(e)}')
    
    def start_torque_control(self):
        """开始力矩控制"""
        if not self.current_motor:
            return
        
        try:
            current = self.torque_spinbox.value()
            direction = self.torque_direction.currentText()  # CW/CCW
            current_slope = self.current_slope_spinbox.value()
            
            # 根据方向调整电流值
            if direction == "CCW":  # 逆时针
                current = -current
            
            self.current_motor.control_actions.set_torque(
                current=current,
                current_slope=current_slope
            )
            QMessageBox.information(self, '成功', f'力矩控制开始: {current} mA')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'力矩控制失败:\n{str(e)}')
    
    def start_trapezoid_motion(self):
        """开始梯形曲线位置运动"""
        if not self.current_motor:
            return
        
        try:
            input_position = self.trapezoid_position_spinbox.value()
            actual_position = self.get_actual_angle(input_position)
            max_speed = self.trapezoid_max_speed_spinbox.value()
            direction = self.trapezoid_direction.currentText()  # CW/CCW
            acceleration = self.trapezoid_acceleration_spinbox.value()
            deceleration = self.trapezoid_deceleration_spinbox.value()
            is_absolute = self.trapezoid_absolute_checkbox.isChecked()
            
            # 根据方向调整位置值（仅对相对位置有效）
            if direction == "CCW" and not is_absolute:  # 逆时针且为相对位置
                actual_position = -actual_position
            
            self.current_motor.control_actions.move_to_position_trapezoid(
                position=actual_position,
                max_speed=max_speed,
                acceleration=acceleration,
                deceleration=deceleration,
                is_absolute=is_absolute
            )
            
            display_mode = self.angle_display_mode.currentText()
            QMessageBox.information(self, '成功', f'梯形曲线位置运动开始: {input_position} 度 ({display_mode})')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'梯形曲线位置运动失败:\n{str(e)}')
    
    def emergency_stop(self):
        """紧急停止"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.stop()
            QMessageBox.information(self, '成功', '停止成功')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'紧急停止失败:\n{str(e)}')
    
    # 回零功能方法
    def start_homing(self):
        """开始回零"""
        if not self.current_motor:
            return
        
        try:
            mode = self.homing_mode_combo.currentIndex()
            self.current_motor.control_actions.trigger_homing(homing_mode=mode)
            QMessageBox.information(self, '成功', '回零开始')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'回零失败:\n{str(e)}')
    
    def stop_homing(self):
        """停止回零"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.force_stop_homing()
            QMessageBox.information(self, '成功', '回零已停止')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'停止回零失败:\n{str(e)}')
    
    def calibrate_encoder(self):
        """编码器校准"""
        if not self.current_motor:
            return
        
        try:
            self.current_motor.control_actions.trigger_encoder_calibration()
            QMessageBox.information(self, '成功', '编码器校准开始')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'编码器校准失败:\n{str(e)}') 

    def read_homing_parameters(self):
        """读取回零参数"""
        if not self.current_motor:
            return
        
        try:
            params = self.current_motor.read_parameters.get_homing_parameters()
            
            # 更新界面显示（完整15字节）
            # 边界保护：根据可用项数量裁剪模式索引
            mode_count = self.homing_param_mode_combo.count() if hasattr(self, 'homing_param_mode_combo') else 0
            safe_mode_idx = min(params.mode, mode_count - 1) if mode_count > 0 else 0
            self.homing_param_mode_combo.setCurrentIndex(safe_mode_idx)
            self.homing_direction_combo.setCurrentIndex(params.direction)
            self.homing_speed_spinbox.setValue(params.speed)
            self.homing_timeout_spinbox.setValue(params.timeout)
            self.collision_detection_speed_spinbox.setValue(params.collision_detection_speed)
            self.collision_detection_current_spinbox.setValue(params.collision_detection_current)
            self.collision_detection_time_spinbox.setValue(params.collision_detection_time)
            self.auto_homing_checkbox.setChecked(params.auto_homing_enabled)
            
            # 启用所有字段
            self.collision_detection_speed_spinbox.setEnabled(True)
            self.collision_detection_current_spinbox.setEnabled(True)
            self.collision_detection_time_spinbox.setEnabled(True)
            self.auto_homing_checkbox.setEnabled(True)
            
            QMessageBox.information(self, '成功', '回零参数读取成功')
        except Exception as e:
            # 严格解析失败，尝试原始7字节兼容展示
            try:
                raw = self.current_motor.read_parameters.get_homing_parameters_raw()
                if len(raw) == 7:
                    mode = raw[0]
                    direction = raw[1]
                    speed = (raw[2] << 8) | raw[3]
                    # 回零超时在精简格式中仅返回高3字节
                    timeout_high3 = (raw[4] << 16) | (raw[5] << 8) | raw[6]
                    # 为避免显示为极小值(被控件下限夹到1000ms)，按协议位宽将高3字节左移8位展示（低1字节未知）
                    display_timeout = (timeout_high3 << 8)
                    # 无法获取的项禁用并清空
                    mode_count = self.homing_param_mode_combo.count() if hasattr(self, 'homing_param_mode_combo') else 0
                    safe_mode_idx = min(mode, mode_count - 1) if mode_count > 0 else 0
                    self.homing_param_mode_combo.setCurrentIndex(safe_mode_idx)
                    self.homing_direction_combo.setCurrentIndex(direction)
                    self.homing_speed_spinbox.setValue(speed)
                    # 仅为展示，保留高3字节左移8位；不推断低字节
                    self.homing_timeout_spinbox.setValue(min(display_timeout, self.homing_timeout_spinbox.maximum()))
                    
                    # 置灰不可编辑
                    self.collision_detection_speed_spinbox.setEnabled(False)
                    self.collision_detection_current_spinbox.setEnabled(False)
                    self.collision_detection_time_spinbox.setEnabled(False)
                    
                    # 给予提示，不用默认值
                    QMessageBox.information(self, '提示', '设备返回为精简格式(7字节)。已显示：模式/方向/速度/超时(高3字节)。\n碰撞参数与自动回零未返回，已禁用。')
                    return
                else:
                    QMessageBox.warning(self, '失败', f'读取回零参数失败:\n设备返回{len(raw)}字节(期望15或7)。')
            except Exception as e2:
                QMessageBox.warning(self, '失败', f'读取回零参数失败:\n{str(e)}\n兼容读取也失败: {str(e2)}')
    
    def modify_homing_parameters(self):
        """修改回零参数"""
        if not self.current_motor:
            return
        
        try:
            # 若当前处于7字节兼容模式（碰撞参数被禁用），给出确认提示
            compat_mode = not (self.collision_detection_speed_spinbox.isEnabled() and 
                               self.collision_detection_current_spinbox.isEnabled() and 
                               self.collision_detection_time_spinbox.isEnabled())
            if compat_mode:
                reply = QMessageBox.question(
                    self,
                    '确认下发',
                    '若继续，将以界面当前显示值下发以下参数，并可能覆盖电机原有值：\n'
                    '• 碰撞检测转速\n• 碰撞检测电流\n• 碰撞检测时间\n\n是否继续？',
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # 从界面获取参数
            mode = self.homing_param_mode_combo.currentIndex()  # 使用选择的模式
            direction = self.homing_direction_combo.currentIndex()
            speed = self.homing_speed_spinbox.value()
            timeout = self.homing_timeout_spinbox.value()
            collision_detection_speed = self.collision_detection_speed_spinbox.value()
            collision_detection_current = self.collision_detection_current_spinbox.value()
            collision_detection_time = self.collision_detection_time_spinbox.value()
            auto_homing_enabled = self.auto_homing_checkbox.isChecked()
            save_to_chip = self.save_homing_params_checkbox.isChecked()
            
            # 调用SDK方法修改参数
            self.current_motor.control_actions.modify_homing_parameters(
                mode=mode,
                direction=direction,
                speed=speed,
                timeout=timeout,
                collision_detection_speed=collision_detection_speed,
                collision_detection_current=collision_detection_current,
                collision_detection_time=collision_detection_time,
                auto_homing_enabled=auto_homing_enabled,
                save_to_chip=save_to_chip
            )
            
            save_info = "已保存到芯片" if save_to_chip else "未保存到芯片"
            QMessageBox.information(self, '成功', f'回零参数修改成功 ({save_info})')
            
        except Exception as e:
            QMessageBox.warning(self, '失败', f'修改回零参数失败:\n{str(e)}') 

    # 循环梯形曲线运动相关方法
    def load_default_actions(self):
        """加载默认动作参数"""
        default_actions = [
            [360.0, 500.0, 1000, 1000, "CW", False],
            [360.0, 600.0, 1200, 1200, "CCW", False],
            [180.0, 700.0, 1400, 1400, "CW", False],
            [180.0, 800.0, 1600, 1600, "CCW", False],
            [90.0, 500.0, 1000, 1000, "CW", False]
        ]
        
        for row in range(5):
            for col in range(5):  # 前5列是数值（包括转动方向）
                item = QTableWidgetItem(str(default_actions[row][col]))
                self.actions_table.setItem(row, col, item)
            
            # 第6列：创建绝对位置复选框
            checkbox = QCheckBox()
            checkbox.setChecked(default_actions[row][5])
            # 将复选框居中显示
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.actions_table.setCellWidget(row, 5, checkbox_widget)
        
        QMessageBox.information(self, '成功', '已加载默认动作参数')
    
    def save_current_actions(self):
        """保存当前动作参数"""
        try:
            self.cycle_actions = []
            for row in range(5):
                action = {}
                
                # 获取数值参数
                position_item = self.actions_table.item(row, 0)
                speed_item = self.actions_table.item(row, 1)
                accel_item = self.actions_table.item(row, 2)
                decel_item = self.actions_table.item(row, 3)
                
                if not all([position_item, speed_item, accel_item, decel_item]):
                    QMessageBox.warning(self, '错误', f'动作 {row+1} 的参数不完整')
                    return
                
                action['position'] = float(position_item.text())
                action['max_speed'] = float(speed_item.text())
                action['acceleration'] = int(accel_item.text())
                action['deceleration'] = int(decel_item.text())
                
                # 获取方向和绝对位置状态
                direction_item = self.actions_table.item(row, 4)
                direction_text = direction_item.text() if direction_item else "CW"
                
                # 确保方向值是CW或CCW
                if direction_text.strip().upper() not in ["CW", "CCW"]:
                    direction_text = "CW"
                    if direction_item:
                        direction_item.setText("CW")
                
                action['direction'] = direction_text
                
                checkbox_widget = self.actions_table.cellWidget(row, 5)
                if checkbox_widget:
                    # 获取复选框（在布局中的第一个子控件）
                    checkbox = checkbox_widget.layout().itemAt(0).widget()
                    action['is_absolute'] = checkbox.isChecked() if checkbox else True
                else:
                    action['is_absolute'] = True
                
                self.cycle_actions.append(action)
            
            QMessageBox.information(self, '成功', f'已保存 {len(self.cycle_actions)} 个动作参数')
            
        except ValueError as e:
            QMessageBox.warning(self, '错误', f'参数格式错误: {str(e)}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'保存失败: {str(e)}')
    
    def start_cycle_motion(self):
        """开始循环运动"""
        if not self.current_motor:
            QMessageBox.warning(self, '错误', '请先连接电机')
            return
        
        if self.is_cycling:
            QMessageBox.warning(self, '警告', '循环运动已在进行中')
            return
        
        # 先保存当前动作参数
        self.save_current_actions()
        
        if not self.cycle_actions:
            QMessageBox.warning(self, '错误', '没有有效的动作参数')
            return
        
        try:
            # 确保电机是使能状态
            self.current_motor.control_actions.enable()
            
            # 开始循环
            self.is_cycling = True
            self.current_action_index = 0
            self.cycle_timer.start(100)  # 每100ms检查一次
            
            # 更新UI状态
            self.start_cycle_btn.setEnabled(False)
            self.stop_cycle_btn.setEnabled(True)
            self.cycle_status_label.setText("运行中")
            self.cycle_status_label.setProperty("class", "status-connected")
            self.cycle_status_label.setStyle(self.cycle_status_label.style())
            
            # 执行第一个动作
            self.execute_current_action()
            
            QMessageBox.information(self, '成功', f'开始循环运动，共 {len(self.cycle_actions)} 个动作')
            
        except Exception as e:
            self.is_cycling = False
            self.cycle_timer.stop()
            QMessageBox.warning(self, '失败', f'启动循环运动失败: {str(e)}')
    
    def stop_cycle_motion(self):
        """停止循环运动"""
        if not self.is_cycling:
            return
        
        self.is_cycling = False
        self.cycle_timer.stop()
        
        # 更新UI状态
        self.start_cycle_btn.setEnabled(True)
        self.stop_cycle_btn.setEnabled(False)
        self.cycle_status_label.setText("已停止")
        self.cycle_status_label.setProperty("class", "status-disconnected")
        self.cycle_status_label.setStyle(self.cycle_status_label.style())
        self.current_action_label.setText("无")
        
        QMessageBox.information(self, '成功', '循环运动已停止')
    
    def emergency_stop_cycle(self):
        """紧急停止循环运动"""
        if self.current_motor:
            try:
                # 紧急停止电机
                self.current_motor.control_actions.stop()
            except:
                pass
        
        # 停止循环
        self.stop_cycle_motion()
        QMessageBox.warning(self, '紧急停止', '已紧急停止所有运动！')
    
    def execute_current_action(self):
        """执行当前动作"""
        if not self.is_cycling or not self.cycle_actions:
            return
        
        try:
            action = self.cycle_actions[self.current_action_index]
            
            # 获取实际发送给电机的角度（使用循环运动标签页的设置）
            actual_position = self.get_cycle_actual_angle(action['position'])
            
            # 根据方向调整位置值（仅对相对位置有效）
            direction = action['direction']
            if direction == "CCW" and not action['is_absolute']:  # 逆时针且为相对位置
                actual_position = -actual_position
            
            # 执行梯形曲线运动
            self.current_motor.control_actions.move_to_position_trapezoid(
                position=actual_position,
                max_speed=action['max_speed'],
                acceleration=action['acceleration'],
                deceleration=action['deceleration'],
                is_absolute=action['is_absolute']
            )
            
            # 更新状态显示
            display_mode = self.cycle_angle_display_mode.currentText()
            self.current_action_label.setText(f"动作 {self.current_action_index + 1}: {action['position']:.1f}° ({display_mode}, {direction})")
            
            # 记录动作开始时间
            self.action_start_time = time.time()
            
        except Exception as e:
            QMessageBox.warning(self, '错误', f'执行动作失败: {str(e)}')
            self.stop_cycle_motion()
    
    def execute_next_action(self):
        """执行下一个动作（由定时器调用）"""
        if not self.is_cycling or not self.current_motor:
            return
        
        try:
            # 检查电机是否到位
            motor_status = self.current_motor.read_parameters.get_motor_status()
            
            # 如果电机到位，等待间隔时间后执行下一个动作
            if motor_status.in_position and self.action_start_time:
                elapsed_time = time.time() - self.action_start_time
                interval = self.action_interval_spinbox.value()
                
                if elapsed_time >= interval:
                    # 移动到下一个动作
                    self.current_action_index = (self.current_action_index + 1) % len(self.cycle_actions)
                    self.execute_current_action()
                    
        except Exception as e:
            # 如果读取状态失败，继续运行（可能是通信问题）
            pass 

    def _apply_drive_version_homing_modes(self):
        """根据驱动板版本(X/Y)调整回零模式下拉框项"""
        try:
            # 若未连接电机，跳过
            if not self.current_motor:
                return
            version = getattr(self.current_motor, 'drive_version', 'Y')
            # 记录当前选择，尽量保持不变
            current_idx1 = self.homing_mode_combo.currentIndex() if hasattr(self, 'homing_mode_combo') else 0
            current_idx2 = self.homing_param_mode_combo.currentIndex() if hasattr(self, 'homing_param_mode_combo') else 0
            
            # 全量模式列表（Y版）
            y_modes = [
                "就近回零",
                "方向回零",
                "无限位碰撞回零",
                "限位回零",
                "回到绝对位置坐标零点",
                "回到上次掉电位置角度",
            ]
            # X版不包含绝对零点/掉电位置
            x_modes = [
                "就近回零",
                "方向回零",
                "无限位碰撞回零",
                "限位回零",
            ]
            modes = y_modes if str(version).upper() == 'Y' else x_modes
            
            # 更新两个下拉框的条目
            def reset_combo(combo, modes, prev_idx):
                if not combo:
                    return
                combo.blockSignals(True)
                combo.clear()
                combo.addItems(modes)
                # 恢复索引（若越界则置为0）
                if 0 <= prev_idx < len(modes):
                    combo.setCurrentIndex(prev_idx)
                else:
                    combo.setCurrentIndex(0)
                combo.blockSignals(False)
            
            reset_combo(getattr(self, 'homing_mode_combo', None), modes, current_idx1)
            reset_combo(getattr(self, 'homing_param_mode_combo', None), modes, current_idx2)
        except Exception:
            pass