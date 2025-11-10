# -*- coding: utf-8 -*-
"""
多电机控制组件
"""

import sys
import os
import time
import threading
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QListWidget, QListWidgetItem, QSplitter, QScrollArea,
                             QSizePolicy)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread
from PyQt5.QtGui import QFont

# 添加Control_SDK目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
control_sdk_dir = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "Control_SDK")
sys.path.insert(0, control_sdk_dir)

class MultiMotorWidget(QWidget):
    """多电机控制组件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        self.selected_motors = []  # 选中的电机ID列表
        self.motor_reducer_ratios = {}  # 每个电机的减速比字典
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.update_status_display)
        
        # 循环控制相关变量
        self.cycle_actions_dict = {}  # 电机ID -> 动作参数列表的字典
        self.cycling_motors = set()  # 正在循环运动的电机ID集合
        self.motor_current_action_index = {}  # 电机ID -> 当前动作索引的字典
        self.motor_action_start_time = {}  # 电机ID -> 动作开始时间的字典
        self.multi_cycle_timer = QTimer()
        self.multi_cycle_timer.timeout.connect(self.execute_next_multi_cycle_action)
        
        self.init_ui()
    
    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            
            # 停止所有定时器
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            
            if hasattr(self, 'multi_cycle_timer') and self.multi_cycle_timer:
                self.multi_cycle_timer.stop()
                self.cycling_motors.clear()
            
            # 停止所有电机运动
            if self.motors:
                try:
                    for motor_id, motor in self.motors.items():
                        motor.control_actions.stop()
                except Exception as e:
                    print(f"⚠️ 停止电机运动时出错: {e}")
            
            print("✅ 多电机控件资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 多电机控件清理资源时发生错误: {e}")
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
        group.setMaximumHeight(200)  # 设置高度
        main_layout = QVBoxLayout(group)
        main_layout.setSpacing(5)  # 减少间距
        
        # 第一行：电机列表
        motor_list_layout = QVBoxLayout()
        motor_list_layout.addWidget(QLabel("可用电机:"))
        
        self.motor_list = QListWidget()
        self.motor_list.setMaximumHeight(50)  # 减少高度
        self.motor_list.setSelectionMode(QListWidget.MultiSelection)
        self.motor_list.itemSelectionChanged.connect(self.on_motor_selection_changed)
        # 设置横向流式布局
        self.motor_list.setFlow(QListWidget.LeftToRight)
        self.motor_list.setWrapping(True)
        self.motor_list.setResizeMode(QListWidget.Adjust)
        motor_list_layout.addWidget(self.motor_list)
        
        main_layout.addLayout(motor_list_layout)
        
        # 第二行：控制按钮和状态
        control_layout = QHBoxLayout()
        
        # 快速选择按钮
        quick_select_layout = QHBoxLayout()
        quick_select_layout.addWidget(QLabel("快速选择:"))
        
        self.select_all_btn = QPushButton("全选")
        self.select_all_btn.setProperty("class", "success")
        self.select_all_btn.clicked.connect(self.select_all_motors)
        self.select_all_btn.setMaximumWidth(60)  # 限制按钮宽度
        quick_select_layout.addWidget(self.select_all_btn)
        
        self.select_none_btn = QPushButton("全不选")
        self.select_none_btn.setProperty("class", "warning")
        self.select_none_btn.clicked.connect(self.select_no_motors)
        self.select_none_btn.setMaximumWidth(60)  # 限制按钮宽度
        quick_select_layout.addWidget(self.select_none_btn)
        
        control_layout.addLayout(quick_select_layout)
        
        # 添加分隔符
        control_layout.addStretch()
        
        # 状态显示
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("选择状态:"))
        
        self.selection_status = QLabel("未选择电机")
        self.selection_status.setProperty("class", "status-disconnected")
        status_layout.addWidget(self.selection_status)
        
        control_layout.addLayout(status_layout)
        
        main_layout.addLayout(control_layout)
        
        parent_layout.addWidget(group)
    
    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()
        
        # 同步控制标签页
        self.sync_control_tab = self.create_sync_control_tab()
        self.tab_widget.addTab(self.sync_control_tab, "同步控制")
        
        # 批量操作标签页
        self.batch_operation_tab = self.create_batch_operation_tab()
        self.tab_widget.addTab(self.batch_operation_tab, "批量操作")
        
        # 循环控制标签页
        self.cycle_control_tab = self.create_cycle_control_tab()
        self.tab_widget.addTab(self.cycle_control_tab, "循环控制")
        
        # 回零参数设置标签页
        self.homing_params_tab = self.create_homing_params_tab()
        self.tab_widget.addTab(self.homing_params_tab, "回零参数设置")
        
        # 状态监控标签页
        self.status_monitor_tab = self.create_status_monitor_tab()
        self.tab_widget.addTab(self.status_monitor_tab, "状态监控")
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_sync_control_tab(self):
        """创建同步控制标签页"""
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
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(15)
        
        # 减速器设置组 - 移到滚动区域内
        reducer_group = QGroupBox("减速器设置")
        reducer_layout = QVBoxLayout(reducer_group)
        reducer_layout.setSpacing(5)  # 减少间距
        
        # 第一行：主要控件
        main_controls_layout = QHBoxLayout()
        
        # 减速比输入
        main_controls_layout.addWidget(QLabel("减速比:"))
        
        self.multi_reducer_ratio_edit = QLineEdit()
        self.multi_reducer_ratio_edit.setPlaceholderText("例如: 1:16,2:20 或 16")
        self.multi_reducer_ratio_edit.setText("1")  # 默认值
        self.multi_reducer_ratio_edit.setMaximumWidth(200)
        main_controls_layout.addWidget(self.multi_reducer_ratio_edit)
        
        self.apply_reducer_ratio_btn = QPushButton("应用减速比")
        self.apply_reducer_ratio_btn.clicked.connect(self.apply_reducer_ratios)
        self.apply_reducer_ratio_btn.setMaximumWidth(100)
        main_controls_layout.addWidget(self.apply_reducer_ratio_btn)
        
        # 角度显示模式
        main_controls_layout.addWidget(QLabel("角度显示模式:"))
        
        self.multi_angle_display_mode = QComboBox()
        self.multi_angle_display_mode.addItems(["输出端角度", "电机端角度"])
        self.multi_angle_display_mode.currentTextChanged.connect(self.update_multi_angle_display_mode)
        self.multi_angle_display_mode.setMaximumWidth(150)
        main_controls_layout.addWidget(self.multi_angle_display_mode)
        
        main_controls_layout.addStretch()
        reducer_layout.addLayout(main_controls_layout)
        
        # 第二行：状态显示
        status_layout = QHBoxLayout()
        
        # 当前减速比显示
        self.current_reducer_status = QLabel("当前减速比: 无")
        self.current_reducer_status.setStyleSheet("color: #666; font-size: 10px;")
        status_layout.addWidget(self.current_reducer_status)
        
        status_layout.addStretch()
        reducer_layout.addLayout(status_layout)
        
        scroll_layout.addWidget(reducer_group)
        
        # 提示信息
        reducer_hint = QLabel("提示：格式 ID1:比例1,ID2:比例2 或统一比例。如16:1减速器输入16")
        reducer_hint.setStyleSheet("color: #666; font-size: 10px;")
        scroll_layout.addWidget(reducer_hint)
        
        # 第一行：同步位置控制 + 同步速度控制
        # 创建网格布局容器
        controls_widget = QWidget()
        controls_layout = QGridLayout(controls_widget)
        controls_layout.setSpacing(15)
        controls_layout.setContentsMargins(0, 0, 0, 0)
        
        # 同步位置控制组
        sync_position_group = QGroupBox("同步位置控制")
        sync_position_layout = QFormLayout(sync_position_group)
        
        # 位置参数输入
        positions_layout = QVBoxLayout()
        positions_layout.addWidget(QLabel("各电机位置角度:"))
        positions_layout.addWidget(QLabel("格式: ID1:位置1,ID2:位置2 或 统一位置值"))
        
        self.sync_positions_edit = QLineEdit()
        self.sync_positions_edit.setPlaceholderText("例如: 1:90,2:180 或 90")
        positions_layout.addWidget(self.sync_positions_edit)
        
        positions_hint = QLabel("范围：0.0 ~ 429496729.5，单位：°")
        positions_hint.setStyleSheet("color: #666; font-size: 10px;")
        positions_layout.addWidget(positions_hint)
        
        sync_position_layout.addRow("", positions_layout)
        
        # 运动速度
        sync_position_speed_layout = QVBoxLayout()
        sync_position_speed_layout.addWidget(QLabel("运动速度:"))
        
        self.sync_position_speed = QDoubleSpinBox()
        self.sync_position_speed.setRange(0.0, 3000.0)
        self.sync_position_speed.setSuffix(" RPM")
        self.sync_position_speed.setValue(500.0)
        sync_position_speed_layout.addWidget(self.sync_position_speed)
        
        sync_position_speed_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        sync_position_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_position_speed_layout.addWidget(sync_position_speed_hint)
        
        sync_position_layout.addRow("", sync_position_speed_layout)
        
        # 转动方向
        sync_position_direction_layout = QVBoxLayout()
        sync_position_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.sync_position_direction = QComboBox()
        self.sync_position_direction.addItems(["CW", "CCW"])
        sync_position_direction_layout.addWidget(self.sync_position_direction)
        
        sync_position_direction_hint = QLabel("提示：控制电机的转动方向")
        sync_position_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_position_direction_layout.addWidget(sync_position_direction_hint)
        
        sync_position_layout.addRow("", sync_position_direction_layout)
        
        # 位置模式
        sync_position_mode_layout = QVBoxLayout()
        sync_position_mode_layout.addWidget(QLabel("位置模式:"))
        
        self.sync_position_absolute = QCheckBox("绝对位置")
        sync_position_mode_layout.addWidget(self.sync_position_absolute)
        
        sync_position_mode_hint = QLabel("提示：勾选绝对位置，不勾选相对位置")
        sync_position_mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_position_mode_layout.addWidget(sync_position_mode_hint)
        
        sync_position_layout.addRow("", sync_position_mode_layout)
        
        self.start_sync_position_btn = QPushButton("开始同步位置运动")
        self.start_sync_position_btn.clicked.connect(self.start_sync_position_motion)
        sync_position_layout.addRow("", self.start_sync_position_btn)
        
        # 同步速度控制组
        sync_speed_group = QGroupBox("同步速度控制")
        sync_speed_layout = QFormLayout(sync_speed_group)
        
        # 速度参数输入
        speeds_layout = QVBoxLayout()
        speeds_layout.addWidget(QLabel("各电机运动速度:"))
        speeds_layout.addWidget(QLabel("格式: ID1:速度1,ID2:速度2 或 统一速度值"))
        
        self.sync_speeds_edit = QLineEdit()
        self.sync_speeds_edit.setPlaceholderText("例如: 1:100,2:200 或 100")
        speeds_layout.addWidget(self.sync_speeds_edit)
        
        speeds_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        speeds_hint.setStyleSheet("color: #666; font-size: 10px;")
        speeds_layout.addWidget(speeds_hint)
        
        sync_speed_layout.addRow("", speeds_layout)
        
        # 转动方向
        sync_speed_direction_layout = QVBoxLayout()
        sync_speed_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.sync_speed_direction = QComboBox()
        self.sync_speed_direction.addItems(["CW", "CCW"])
        sync_speed_direction_layout.addWidget(self.sync_speed_direction)
        
        sync_speed_direction_hint = QLabel("提示：控制电机的转动方向")
        sync_speed_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_speed_direction_layout.addWidget(sync_speed_direction_hint)
        
        sync_speed_layout.addRow("", sync_speed_direction_layout)
        
        # 速度斜率(加速度)
        sync_speed_acceleration_layout = QVBoxLayout()
        sync_speed_acceleration_layout.addWidget(QLabel("速度斜率(加速度):"))
        
        self.sync_speed_acceleration = QSpinBox()
        self.sync_speed_acceleration.setRange(0, 65535)
        self.sync_speed_acceleration.setSuffix(" RPM/s")
        self.sync_speed_acceleration.setValue(1000)
        sync_speed_acceleration_layout.addWidget(self.sync_speed_acceleration)
        
        sync_speed_acceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        sync_speed_acceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_speed_acceleration_layout.addWidget(sync_speed_acceleration_hint)
        
        sync_speed_layout.addRow("", sync_speed_acceleration_layout)
        
        self.start_sync_speed_btn = QPushButton("开始同步速度运动")
        self.start_sync_speed_btn.clicked.connect(self.start_sync_speed_motion)
        sync_speed_layout.addRow("", self.start_sync_speed_btn)
        
        # 添加到网格布局 - 第一行
        controls_layout.addWidget(sync_position_group, 0, 0)
        controls_layout.addWidget(sync_speed_group, 0, 1)
        
        # 第二行：同步梯形曲线位置控制 + 同步回零控制
        # 同步梯形曲线位置控制组
        sync_trapezoid_group = QGroupBox("同步梯形曲线位置控制")
        sync_trapezoid_layout = QFormLayout(sync_trapezoid_group)
        
        # 位置参数输入
        trapezoid_positions_layout = QVBoxLayout()
        trapezoid_positions_layout.addWidget(QLabel("各电机位置角度:"))
        trapezoid_positions_layout.addWidget(QLabel("格式: ID1:位置1,ID2:位置2 或 统一位置值"))
        
        self.sync_trapezoid_positions_edit = QLineEdit()
        self.sync_trapezoid_positions_edit.setPlaceholderText("例如: 1:90,2:180 或 90")
        trapezoid_positions_layout.addWidget(self.sync_trapezoid_positions_edit)
        
        trapezoid_positions_hint = QLabel("范围：0.0 ~ 429496729.5，单位：°")
        trapezoid_positions_hint.setStyleSheet("color: #666; font-size: 10px;")
        trapezoid_positions_layout.addWidget(trapezoid_positions_hint)
        
        sync_trapezoid_layout.addRow("", trapezoid_positions_layout)
        
        # 最大速度
        sync_trapezoid_max_speed_layout = QVBoxLayout()
        sync_trapezoid_max_speed_layout.addWidget(QLabel("最大速度:"))
        
        self.sync_trapezoid_max_speed = QDoubleSpinBox()
        self.sync_trapezoid_max_speed.setRange(0.0, 3000.0)
        self.sync_trapezoid_max_speed.setSuffix(" RPM")
        self.sync_trapezoid_max_speed.setValue(500.0)
        sync_trapezoid_max_speed_layout.addWidget(self.sync_trapezoid_max_speed)
        
        sync_trapezoid_max_speed_hint = QLabel("范围：0.0 ~ 3000.0，单位：RPM")
        sync_trapezoid_max_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_trapezoid_max_speed_layout.addWidget(sync_trapezoid_max_speed_hint)
        
        sync_trapezoid_layout.addRow("", sync_trapezoid_max_speed_layout)
        
        # 转动方向
        sync_trapezoid_direction_layout = QVBoxLayout()
        sync_trapezoid_direction_layout.addWidget(QLabel("转动方向:"))
        
        self.sync_trapezoid_direction = QComboBox()
        self.sync_trapezoid_direction.addItems(["CW", "CCW"])
        sync_trapezoid_direction_layout.addWidget(self.sync_trapezoid_direction)
        
        sync_trapezoid_direction_hint = QLabel("提示：控制电机的转动方向")
        sync_trapezoid_direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_trapezoid_direction_layout.addWidget(sync_trapezoid_direction_hint)
        
        sync_trapezoid_layout.addRow("", sync_trapezoid_direction_layout)
        
        # 加速加速度
        sync_trapezoid_acceleration_layout = QVBoxLayout()
        sync_trapezoid_acceleration_layout.addWidget(QLabel("加速加速度:"))
        
        self.sync_trapezoid_acceleration = QSpinBox()
        self.sync_trapezoid_acceleration.setRange(0, 65535)
        self.sync_trapezoid_acceleration.setSuffix(" RPM/s")
        self.sync_trapezoid_acceleration.setValue(1000)
        sync_trapezoid_acceleration_layout.addWidget(self.sync_trapezoid_acceleration)
        
        sync_trapezoid_acceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        sync_trapezoid_acceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_trapezoid_acceleration_layout.addWidget(sync_trapezoid_acceleration_hint)
        
        sync_trapezoid_layout.addRow("", sync_trapezoid_acceleration_layout)
        
        # 减速加速度
        sync_trapezoid_deceleration_layout = QVBoxLayout()
        sync_trapezoid_deceleration_layout.addWidget(QLabel("减速加速度:"))
        
        self.sync_trapezoid_deceleration = QSpinBox()
        self.sync_trapezoid_deceleration.setRange(0, 65535)
        self.sync_trapezoid_deceleration.setSuffix(" RPM/s")
        self.sync_trapezoid_deceleration.setValue(1000)
        sync_trapezoid_deceleration_layout.addWidget(self.sync_trapezoid_deceleration)
        
        sync_trapezoid_deceleration_hint = QLabel("范围：0 ~ 65535，单位：RPM/s")
        sync_trapezoid_deceleration_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_trapezoid_deceleration_layout.addWidget(sync_trapezoid_deceleration_hint)
        
        sync_trapezoid_layout.addRow("", sync_trapezoid_deceleration_layout)
        
        # 位置模式
        sync_trapezoid_mode_layout = QVBoxLayout()
        sync_trapezoid_mode_layout.addWidget(QLabel("位置模式:"))
        
        self.sync_trapezoid_absolute = QCheckBox("绝对位置")
        sync_trapezoid_mode_layout.addWidget(self.sync_trapezoid_absolute)
        
        sync_trapezoid_mode_hint = QLabel("提示：勾选绝对位置，不勾选相对位置")
        sync_trapezoid_mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_trapezoid_mode_layout.addWidget(sync_trapezoid_mode_hint)
        
        sync_trapezoid_layout.addRow("", sync_trapezoid_mode_layout)
        
        self.start_sync_trapezoid_btn = QPushButton("开始同步梯形曲线运动")
        self.start_sync_trapezoid_btn.clicked.connect(self.start_sync_trapezoid_motion)
        sync_trapezoid_layout.addRow("", self.start_sync_trapezoid_btn)
        
        # 新增：Y42一次性下发（Y板）
        self.start_y42_trapezoid_btn = QPushButton("Y42一次性下发(梯形)")
        self.start_y42_trapezoid_btn.clicked.connect(self.start_y42_trapezoid_motion)
        sync_trapezoid_layout.addRow("", self.start_y42_trapezoid_btn)
        self.start_y42_trapezoid_btn.setVisible(False)
        
        # 同步回零控制组
        sync_homing_group = QGroupBox("同步回零控制")
        sync_homing_layout = QFormLayout(sync_homing_group)
        
        # 回零模式
        sync_homing_mode_layout = QHBoxLayout()
        sync_homing_mode_layout.addWidget(QLabel("回零模式:"))
        self.sync_homing_mode = QComboBox()
        self.sync_homing_mode.addItems([
            "就近回零",
            "方向回零",
            "无限位碰撞回零",
            "限位回零",
            "回到绝对位置坐标零点",
            "回到上次掉电位置角度",
        ])
        sync_homing_mode_layout.addWidget(self.sync_homing_mode)
        sync_homing_mode_hint = QLabel("提示：选择电机回零的方向模式  (注意：只能不带减速器使用，带减速器需要无限位)")
        sync_homing_mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        sync_homing_mode_layout.addWidget(sync_homing_mode_hint)
        
        sync_homing_layout.addRow("", sync_homing_mode_layout)
        
        self.start_sync_homing_btn = QPushButton("开始同步回零")
        self.start_sync_homing_btn.clicked.connect(self.start_sync_homing)
        sync_homing_layout.addRow("", self.start_sync_homing_btn)
        
        # 新增：Y42一次性下发（位置直通）
        self.start_y42_position_btn = QPushButton("Y42一次性下发(直通)")
        self.start_y42_position_btn.clicked.connect(self.start_y42_position_motion)
        sync_position_layout.addRow("", self.start_y42_position_btn)
        self.start_y42_position_btn.setVisible(False)
        
        # 添加到网格布局 - 第二行
        controls_layout.addWidget(sync_trapezoid_group, 1, 0)
        controls_layout.addWidget(sync_homing_group, 1, 1)
        
        # 第三行：同步控制状态显示
        status_group = QGroupBox("同步控制状态")
        status_layout = QFormLayout(status_group)
        
        self.sync_status_label = QLabel("停止")
        self.sync_status_label.setProperty("class", "status-disconnected")
        status_layout.addRow("当前状态:", self.sync_status_label)
        
        self.selected_motors_label = QLabel("未选择")
        status_layout.addRow("选中电机:", self.selected_motors_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.stop_sync_btn = QPushButton("停止同步运动")
        self.stop_sync_btn.setProperty("class", "danger")
        self.stop_sync_btn.clicked.connect(self.stop_sync_motion)
        control_layout.addWidget(self.stop_sync_btn)
        

        control_layout.addStretch()
        status_layout.addRow("控制:", control_layout)
        
        # 添加到网格布局 - 第三行，跨两列
        controls_layout.addWidget(status_group, 2, 0, 1, 2)
        
        # 设置列的拉伸比例
        controls_layout.setColumnStretch(0, 1)
        controls_layout.setColumnStretch(1, 1)
        
        # 添加垂直拉伸
        controls_layout.setRowStretch(3, 1)
        
        # 将控件容器添加到滚动布局
        scroll_layout.addWidget(controls_widget)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_batch_operation_tab(self):
        """创建批量操作标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
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
        
        # 基础批量操作组
        basic_batch_group = QGroupBox("基础批量操作")
        basic_batch_layout = QGridLayout(basic_batch_group)
        basic_batch_layout.setSpacing(10)
        
        self.batch_enable_btn = QPushButton("批量使能")
        self.batch_enable_btn.setProperty("class", "success")
        self.batch_enable_btn.clicked.connect(self.batch_enable_motors)
        basic_batch_layout.addWidget(self.batch_enable_btn, 0, 0)
        
        self.batch_disable_btn = QPushButton("批量失能")
        self.batch_disable_btn.setProperty("class", "warning")
        self.batch_disable_btn.clicked.connect(self.batch_disable_motors)
        basic_batch_layout.addWidget(self.batch_disable_btn, 0, 1)
        
        self.batch_stop_btn = QPushButton("批量停止")
        self.batch_stop_btn.setProperty("class", "danger")
        self.batch_stop_btn.clicked.connect(self.batch_stop_motors)
        basic_batch_layout.addWidget(self.batch_stop_btn, 0, 2)
        
        self.batch_clear_position_btn = QPushButton("批量清零位置")
        self.batch_clear_position_btn.clicked.connect(self.batch_clear_position)
        basic_batch_layout.addWidget(self.batch_clear_position_btn, 1, 0)
        
        self.batch_set_zero_btn = QPushButton("批量设置零点")
        self.batch_set_zero_btn.clicked.connect(self.batch_set_zero_position)
        basic_batch_layout.addWidget(self.batch_set_zero_btn, 1, 1)
        
        # 是否保存零点到芯片
        self.batch_save_zero_to_chip_checkbox = QCheckBox("保存零点到芯片")
        self.batch_save_zero_to_chip_checkbox.setChecked(True)
        basic_batch_layout.addWidget(self.batch_save_zero_to_chip_checkbox, 1, 2)
        
        self.batch_release_stall_btn = QPushButton("批量解除堵转保护")
        self.batch_release_stall_btn.clicked.connect(self.batch_release_stall_protection)
        basic_batch_layout.addWidget(self.batch_release_stall_btn, 2, 0)
        
        # 新增：批量回零（选择回零方式）——同一行紧凑布局，整体左对齐
        homing_row = QHBoxLayout()
        homing_row.setContentsMargins(0, 0, 0, 0)
        homing_row.setSpacing(6)
        homing_row.addWidget(QLabel("回零模式:"))
        self.batch_homing_mode_combo = QComboBox()
        self.batch_homing_mode_combo.addItems([
            "就近回零",
            "方向回零",
            "无限位碰撞回零",
            "限位回零",
            "回到绝对位置坐标零点",
            "回到上次掉电位置角度",
        ])
        homing_row.addWidget(self.batch_homing_mode_combo)
        self.batch_homing_btn = QPushButton("批量回零")
        self.batch_homing_btn.setProperty("class", "warning")
        self.batch_homing_btn.clicked.connect(self.batch_start_homing)
        homing_row.addWidget(self.batch_homing_btn)
        homing_row.addStretch()
        basic_batch_layout.addLayout(homing_row, 2, 1, 1, 3)
        
        scroll_layout.addWidget(basic_batch_group)
        
        # 批量运动控制组
        batch_motion_group = QGroupBox("批量运动控制")
        batch_motion_layout = QGridLayout(batch_motion_group)
        batch_motion_layout.setSpacing(10)
        
        # 第一行：批量位置运动控件
        batch_motion_layout.addWidget(QLabel("位置运动:"), 0, 0)
        
        # 位置角度
        batch_position_layout = QVBoxLayout()
        self.batch_position_spinbox = QDoubleSpinBox()
        self.batch_position_spinbox.setRange(0.0, 429496729.5)
        self.batch_position_spinbox.setSuffix(" °")
        self.batch_position_spinbox.setValue(90.0)
        batch_position_layout.addWidget(self.batch_position_spinbox)
        
        batch_position_hint = QLabel("范围：0.0 ~ 429496729.5")
        batch_position_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_position_layout.addWidget(batch_position_hint)
        
        batch_motion_layout.addLayout(batch_position_layout, 0, 1)
        
        # 运动速度
        batch_position_speed_layout = QVBoxLayout()
        self.batch_position_speed_spinbox = QDoubleSpinBox()
        self.batch_position_speed_spinbox.setRange(0.0, 3000.0)
        self.batch_position_speed_spinbox.setSuffix(" RPM")
        self.batch_position_speed_spinbox.setValue(500.0)
        batch_position_speed_layout.addWidget(self.batch_position_speed_spinbox)
        
        batch_position_speed_hint = QLabel("范围：0.0 ~ 3000.0")
        batch_position_speed_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_position_speed_layout.addWidget(batch_position_speed_hint)
        
        batch_motion_layout.addLayout(batch_position_speed_layout, 0, 2)
        
        # 转动方向
        batch_position_direction_layout = QVBoxLayout()
        self.batch_position_direction = QComboBox()
        self.batch_position_direction.addItems(["CW", "CCW"])
        batch_position_direction_layout.addWidget(self.batch_position_direction)
        
        batch_position_direction_hint = QLabel("提示：转动方向")
        batch_position_direction_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_position_direction_layout.addWidget(batch_position_direction_hint)
        
        batch_motion_layout.addLayout(batch_position_direction_layout, 0, 3)
        
        # 位置模式
        batch_position_mode_layout = QVBoxLayout()
        self.batch_position_absolute_checkbox = QCheckBox("绝对位置")
        batch_position_mode_layout.addWidget(self.batch_position_absolute_checkbox)
        
        batch_position_mode_hint = QLabel("提示：位置模式")
        batch_position_mode_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_position_mode_layout.addWidget(batch_position_mode_hint)
        
        batch_motion_layout.addLayout(batch_position_mode_layout, 0, 4)
        
        self.batch_position_btn = QPushButton("批量位置运动")
        self.batch_position_btn.clicked.connect(self.batch_position_motion)
        batch_motion_layout.addWidget(self.batch_position_btn, 0, 5)
        
        # 第二行：批量速度运动控件
        batch_motion_layout.addWidget(QLabel("速度运动:"), 1, 0)
        
        # 运动速度
        batch_speed_layout = QVBoxLayout()
        self.batch_speed_spinbox = QDoubleSpinBox()
        self.batch_speed_spinbox.setRange(0.0, 3000.0)
        self.batch_speed_spinbox.setSuffix(" RPM")
        self.batch_speed_spinbox.setValue(100.0)
        batch_speed_layout.addWidget(self.batch_speed_spinbox)
        
        batch_speed_hint = QLabel("范围：0.0 ~ 3000.0")
        batch_speed_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_speed_layout.addWidget(batch_speed_hint)
        
        batch_motion_layout.addLayout(batch_speed_layout, 1, 1)
        
        # 速度斜率(加速度)
        batch_speed_acceleration_layout = QVBoxLayout()
        self.batch_speed_acceleration_spinbox = QSpinBox()
        self.batch_speed_acceleration_spinbox.setRange(0, 65535)
        self.batch_speed_acceleration_spinbox.setSuffix(" RPM/s")
        self.batch_speed_acceleration_spinbox.setValue(1000)
        batch_speed_acceleration_layout.addWidget(self.batch_speed_acceleration_spinbox)
        
        batch_speed_acceleration_hint = QLabel("范围：0 ~ 65535")
        batch_speed_acceleration_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_speed_acceleration_layout.addWidget(batch_speed_acceleration_hint)
        
        batch_motion_layout.addLayout(batch_speed_acceleration_layout, 1, 2)
        
        # 转动方向
        batch_speed_direction_layout = QVBoxLayout()
        self.batch_speed_direction = QComboBox()
        self.batch_speed_direction.addItems(["CW", "CCW"])
        batch_speed_direction_layout.addWidget(self.batch_speed_direction)
        
        batch_speed_direction_hint = QLabel("提示：转动方向")
        batch_speed_direction_hint.setStyleSheet("color: #666; font-size: 9px;")
        batch_speed_direction_layout.addWidget(batch_speed_direction_hint)
        
        batch_motion_layout.addLayout(batch_speed_direction_layout, 1, 3)
        
        # 空白占位
        batch_motion_layout.addWidget(QLabel(""), 1, 4)
        
        self.batch_speed_btn = QPushButton("批量速度运动")
        self.batch_speed_btn.clicked.connect(self.batch_speed_motion)
        batch_motion_layout.addWidget(self.batch_speed_btn, 1, 5)
        
        scroll_layout.addWidget(batch_motion_group)
        
        # 批量操作状态显示
        status_group = QGroupBox("批量操作状态")
        status_layout = QFormLayout(status_group)
        
        self.batch_status_label = QLabel("停止")
        self.batch_status_label.setProperty("class", "status-disconnected")
        status_layout.addRow("当前状态:", self.batch_status_label)
        
        self.batch_selected_count_label = QLabel("0")
        status_layout.addRow("选中电机数:", self.batch_selected_count_label)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.stop_batch_btn = QPushButton("停止批量运动")
        self.stop_batch_btn.setProperty("class", "danger")
        self.stop_batch_btn.clicked.connect(self.stop_batch_motion)
        control_layout.addWidget(self.stop_batch_btn)
        
        
        control_layout.addStretch()
        status_layout.addRow("控制:", control_layout)
        
        scroll_layout.addWidget(status_group)
        
        # 添加拉伸
        scroll_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_homing_params_tab(self):
        """创建回零参数设置标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
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
        
        # 回零参数设置组
        homing_params_group = QGroupBox("批量回零参数设置")
        homing_params_layout = QFormLayout(homing_params_group)
        
        # 回零模式选择
        mode_layout = QVBoxLayout()
        mode_layout.addWidget(QLabel("回零模式:"))
        
        self.multi_homing_param_mode_combo = QComboBox()
        self.multi_homing_param_mode_combo.addItems([
            "就近回零",
            "方向回零",
            "无限位碰撞回零",
            "限位回零",
            "回到绝对位置坐标零点",
            "回到上次掉电位置角度",
        ])
        mode_layout.addWidget(self.multi_homing_param_mode_combo)
        
        mode_hint = QLabel("提示：选择电机回零的方向模式")
        mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        mode_layout.addWidget(mode_hint)
        
        homing_params_layout.addRow("", mode_layout)
        
        # 回零方向选择
        direction_layout = QVBoxLayout()
        direction_layout.addWidget(QLabel("回零方向:"))
        
        self.multi_homing_direction_combo = QComboBox()
        self.multi_homing_direction_combo.addItems(["顺时针", "逆时针"])
        direction_layout.addWidget(self.multi_homing_direction_combo)
        
        direction_hint = QLabel("提示：电机回零时的旋转方向  (注意：只能不带减速器使用，带减速器需要无限位)")
        direction_hint.setStyleSheet("color: #666; font-size: 10px;")
        direction_layout.addWidget(direction_hint)
        
        homing_params_layout.addRow("", direction_layout)
        
        # 回零速度
        speed_layout = QVBoxLayout()
        speed_layout.addWidget(QLabel("回零速度:"))
        
        self.multi_homing_speed_spinbox = QSpinBox()
        self.multi_homing_speed_spinbox.setRange(1, 3000)
        self.multi_homing_speed_spinbox.setSuffix(" RPM")
        self.multi_homing_speed_spinbox.setValue(30)
        speed_layout.addWidget(self.multi_homing_speed_spinbox)
        
        speed_hint = QLabel("范围：1 ~ 3000，单位：RPM")
        speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        speed_layout.addWidget(speed_hint)
        
        homing_params_layout.addRow("", speed_layout)
        
        # 回零超时时间
        timeout_layout = QVBoxLayout()
        timeout_layout.addWidget(QLabel("回零超时时间:"))
        
        self.multi_homing_timeout_spinbox = QSpinBox()
        self.multi_homing_timeout_spinbox.setRange(1000, 99999)
        self.multi_homing_timeout_spinbox.setSuffix(" ms")
        self.multi_homing_timeout_spinbox.setValue(10000)
        timeout_layout.addWidget(self.multi_homing_timeout_spinbox)
        
        timeout_hint = QLabel("范围：1000 ~ 99999，单位：ms")
        timeout_hint.setStyleSheet("color: #666; font-size: 10px;")
        timeout_layout.addWidget(timeout_hint)
        
        homing_params_layout.addRow("", timeout_layout)
        
        # 碰撞检测速度
        collision_speed_layout = QVBoxLayout()
        collision_speed_layout.addWidget(QLabel("碰撞检测速度:"))
        
        self.multi_collision_detection_speed_spinbox = QSpinBox()
        self.multi_collision_detection_speed_spinbox.setRange(1, 65535)
        self.multi_collision_detection_speed_spinbox.setSuffix(" RPM")
        self.multi_collision_detection_speed_spinbox.setValue(300)
        collision_speed_layout.addWidget(self.multi_collision_detection_speed_spinbox)
        
        collision_speed_hint = QLabel("范围：1 ~ 65535，单位：RPM")
        collision_speed_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_speed_layout.addWidget(collision_speed_hint)
        
        homing_params_layout.addRow("", collision_speed_layout)
        
        # 碰撞检测电流
        collision_current_layout = QVBoxLayout()
        collision_current_layout.addWidget(QLabel("碰撞检测电流:"))
        
        self.multi_collision_detection_current_spinbox = QSpinBox()
        self.multi_collision_detection_current_spinbox.setRange(1, 65535)
        self.multi_collision_detection_current_spinbox.setSuffix(" mA")
        self.multi_collision_detection_current_spinbox.setValue(800)
        collision_current_layout.addWidget(self.multi_collision_detection_current_spinbox)
        
        collision_current_hint = QLabel("范围：1 ~ 65535，单位：mA")
        collision_current_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_current_layout.addWidget(collision_current_hint)
        
        homing_params_layout.addRow("", collision_current_layout)
        
        # 碰撞检测时间
        collision_time_layout = QVBoxLayout()
        collision_time_layout.addWidget(QLabel("碰撞检测时间:"))
        
        self.multi_collision_detection_time_spinbox = QSpinBox()
        self.multi_collision_detection_time_spinbox.setRange(1, 65535)
        self.multi_collision_detection_time_spinbox.setSuffix(" ms")
        self.multi_collision_detection_time_spinbox.setValue(60)
        collision_time_layout.addWidget(self.multi_collision_detection_time_spinbox)
        
        collision_time_hint = QLabel("范围：1 ~ 65535，单位：ms")
        collision_time_hint.setStyleSheet("color: #666; font-size: 10px;")
        collision_time_layout.addWidget(collision_time_hint)
        
        homing_params_layout.addRow("", collision_time_layout)
        
        # 上电自动回零
        auto_homing_layout = QVBoxLayout()
        auto_homing_layout.addWidget(QLabel("上电自动回零:"))
        
        self.multi_auto_homing_checkbox = QCheckBox("Disable")
        self.multi_auto_homing_checkbox.toggled.connect(self.on_multi_auto_homing_toggled)
        auto_homing_layout.addWidget(self.multi_auto_homing_checkbox)
        
        auto_homing_hint = QLabel("提示：Enable开启，Disable关闭")
        auto_homing_hint.setStyleSheet("color: #666; font-size: 10px;")
        auto_homing_layout.addWidget(auto_homing_hint)
        
        homing_params_layout.addRow("", auto_homing_layout)
        
        # 是否存储参数
        save_layout = QVBoxLayout()
        self.multi_save_homing_params_checkbox = QCheckBox("是否存储")
        self.multi_save_homing_params_checkbox.setChecked(True)
        save_layout.addWidget(self.multi_save_homing_params_checkbox)
        
        save_hint = QLabel("提示：勾选后参数将保存到芯片")
        save_hint.setStyleSheet("color: #666; font-size: 10px;")
        save_layout.addWidget(save_hint)
        
        homing_params_layout.addRow("", save_layout)
        
        # 参数操作按钮
        homing_params_btn_layout = QHBoxLayout()
        
        self.multi_read_homing_params_btn = QPushButton("读取首个电机回零参数")
        self.multi_read_homing_params_btn.clicked.connect(self.multi_read_homing_parameters)
        homing_params_btn_layout.addWidget(self.multi_read_homing_params_btn)
        
        self.multi_modify_homing_params_btn = QPushButton("批量修改回零参数")
        self.multi_modify_homing_params_btn.clicked.connect(self.multi_modify_homing_parameters)
        homing_params_btn_layout.addWidget(self.multi_modify_homing_params_btn)
        
        homing_params_layout.addRow("", homing_params_btn_layout)
        
        scroll_layout.addWidget(homing_params_group)
        
        # 回零参数状态显示
        homing_status_group = QGroupBox("回零参数状态")
        homing_status_layout = QFormLayout(homing_status_group)
        
        self.multi_homing_params_status_label = QLabel("未读取")
        homing_status_layout.addRow("参数状态:", self.multi_homing_params_status_label)
        
        self.multi_selected_motors_count_label = QLabel("0")
        homing_status_layout.addRow("选中电机数:", self.multi_selected_motors_count_label)
        
        scroll_layout.addWidget(homing_status_group)
        
        # 添加拉伸
        scroll_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        return widget
    
    def create_status_monitor_tab(self):
        """创建状态监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
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
        self.setup_status_table()
        layout.addWidget(self.status_table)
        
        return widget
    
    def setup_status_table(self):
        """设置状态表格"""
        display_mode = "电机端角度"
        # 安全检查：确保控件存在且有效
        try:
            if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode and not self.multi_angle_display_mode.isHidden():
                display_mode = self.multi_angle_display_mode.currentText()
        except (RuntimeError, AttributeError):
            # 如果控件已被删除或不存在，使用默认值
            display_mode = "电机端角度"
        
        position_header = f"位置(°-{display_mode})"
        headers = ["电机ID", "使能", "到位", position_header, "速度(RPM)", "电压(V)", "电流(A)", "温度(°C)"]
        
        # 安全设置表格
        try:
            self.status_table.setColumnCount(len(headers))
            self.status_table.setHorizontalHeaderLabels(headers)
            self.status_table.horizontalHeader().setStretchLastSection(True)
        except Exception as e:
            print(f"设置状态表格时出错: {e}")
            # 如果出错，创建一个简单的表格
            self.status_table.setColumnCount(8)
            simple_headers = ["电机ID", "使能", "到位", "位置(°)", "速度(RPM)", "电压(V)", "电流(A)", "温度(°C)"]
            self.status_table.setHorizontalHeaderLabels(simple_headers)
            self.status_table.horizontalHeader().setStretchLastSection(True)
    
    def update_motors(self, motors):
        """更新电机列表"""
        self.motors = motors
        self.motor_list.clear()
        self.cycle_motor_combo.clear()
        self.selected_motors.clear()
        
        if motors:
            motor_ids = sorted(motors.keys())
            
            # 初始化每个电机的减速比为1.0
            for motor_id in motor_ids:
                if motor_id not in self.motor_reducer_ratios:
                    self.motor_reducer_ratios[motor_id] = 1.0
                
                # 更新电机列表
                item = QListWidgetItem(f"电机 {motor_id}")
                item.setData(Qt.UserRole, motor_id)
                self.motor_list.addItem(item)
                
                # 更新循环控制下拉框
                self.cycle_motor_combo.addItem(f"电机 {motor_id}", motor_id)
            
            # 初始化循环控制表格
            self.init_cycle_tables()
            
            # 更新减速比状态显示
            self.update_reducer_status()
            
            self.enable_controls(True)
            # 初始化状态
            self.update_sync_status("就绪", "status-connected")
            self.update_batch_status("就绪", "status-connected")
            
            # 初始化状态表格
            self.setup_status_table()
            
            # 新增：根据驱动板版本动态设置回零模式
            self._apply_drive_version_homing_modes_for_multi()
        else:
            self.clear_motors()
            
    def clear_motors(self):
        """清空电机列表"""
        self.motors = {}
        self.selected_motors.clear()
        self.motor_reducer_ratios.clear()  # 清空减速比设置
        self.motor_list.clear()
        self.cycle_motor_combo.clear()
        self.cycling_motors.clear()
        self.cycle_actions_dict.clear()
        
        self.enable_controls(False)
        self.status_timer.stop()
        self.multi_cycle_timer.stop()
        self.update_selection_status()
        # 更新减速比状态显示
        self.update_reducer_status()
        # 重置状态
        self.update_sync_status("停止", "status-disconnected")
        self.update_batch_status("停止", "status-disconnected")
        self.multi_cycle_status_label.setText("已停止")
        self.multi_cycle_status_label.setProperty("class", "status-disconnected")
        self.multi_current_action_label.setText("无")
        
    
    def init_cycle_tables(self):
        """初始化每个电机的循环动作表格"""
        # 为每个电机创建默认动作
        for motor_id in self.motors.keys():
            if motor_id not in self.cycle_actions_dict:
                default_actions = [
                    {"position": 45.0, "max_speed": 800.0, "acceleration": 400, "deceleration": 400, "direction": "CW", "is_absolute": False},
                    {"position": 45.0, "max_speed": 800.0, "acceleration": 400, "deceleration": 400, "direction": "CCW", "is_absolute": False},
                    {"position": 45.0, "max_speed": 800.0, "acceleration": 400, "deceleration": 400, "direction": "CCW", "is_absolute": False},
                    {"position": 45.0, "max_speed": 800.0, "acceleration": 400, "deceleration": 400, "direction": "CW", "is_absolute": False},
                    {"position": 0.0, "max_speed": 800.0, "acceleration": 400, "deceleration": 400, "direction": "CW", "is_absolute": True},
                ]
                self.cycle_actions_dict[motor_id] = default_actions
        
        # 如果有电机选择，更新表格
        if self.cycle_motor_combo.count() > 0:
            self.on_cycle_motor_changed(0)
    
    def on_cycle_motor_changed(self, index):
        """当循环控制中的电机选择改变时更新表格"""
        if index < 0:
            return
            
        motor_id = self.cycle_motor_combo.itemData(index)
        if motor_id not in self.cycle_actions_dict:
            return
        
        # 显示当前选择的电机ID
        current_selection_text = f"当前正在编辑电机 {motor_id} 的动作参数"
        # 查找并更新状态文本标签（如果存在）
        if hasattr(self, 'multi_current_action_label'):
            self.multi_current_action_label.setText(current_selection_text)
        
        # 显示当前电机的减速比
        reducer_ratio = self.motor_reducer_ratios.get(motor_id, 1.0)
        self.cycle_motor_reducer_ratio.setText(str(reducer_ratio))
        self.current_motor_reducer_ratio_label.setText(f"当前减速比: {reducer_ratio}")
            
        # 获取当前电机的动作列表
        actions = self.cycle_actions_dict[motor_id]
        
        # 更新表格内容
        for row in range(min(5, len(actions))):
            action = actions[row]
            
            # 更新表格中的数值
            self.cycle_actions_table.setItem(row, 0, QTableWidgetItem(str(action["position"])))
            self.cycle_actions_table.setItem(row, 1, QTableWidgetItem(str(action["max_speed"])))
            self.cycle_actions_table.setItem(row, 2, QTableWidgetItem(str(action["acceleration"])))
            self.cycle_actions_table.setItem(row, 3, QTableWidgetItem(str(action["deceleration"])))
            self.cycle_actions_table.setItem(row, 4, QTableWidgetItem(str(action["direction"])))
            
            # 创建绝对位置复选框
            checkbox = QCheckBox()
            checkbox.setChecked(action["is_absolute"])
            # 将复选框居中显示
            checkbox_widget = QWidget()
            checkbox_layout = QHBoxLayout(checkbox_widget)
            checkbox_layout.addWidget(checkbox)
            checkbox_layout.setAlignment(Qt.AlignCenter)
            checkbox_layout.setContentsMargins(0, 0, 0, 0)
            self.cycle_actions_table.setCellWidget(row, 5, checkbox_widget)
    
    def load_cycle_default_actions(self):
        """加载默认循环动作参数"""
        index = self.cycle_motor_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '警告', '请先选择电机')
            return
            
        motor_id = self.cycle_motor_combo.itemData(index)
        
        # 重置为默认动作
        default_actions = [
            {"position": 30.0, "max_speed": 100.0, "acceleration": 50, "deceleration": 50, "direction": "CW", "is_absolute": False},
            {"position": 30.0, "max_speed": 100.0, "acceleration": 50, "deceleration": 50, "direction": "CCW", "is_absolute": False},
            {"position": 30.0, "max_speed": 100.0, "acceleration": 50, "deceleration": 50, "direction": "CCW", "is_absolute": False},
            {"position": 30.0, "max_speed": 100.0, "acceleration": 50, "deceleration": 50, "direction": "CW", "is_absolute": False},
            {"position": 0.0, "max_speed": 100.0, "acceleration": 50, "deceleration": 50, "direction": "CW", "is_absolute": True}
        ]
        
        self.cycle_actions_dict[motor_id] = default_actions
        
        # 更新表格显示
        self.on_cycle_motor_changed(index)
        
        QMessageBox.information(self, '成功', f'已为电机 {motor_id} 加载默认动作参数')
    
    def save_cycle_current_actions(self):
        """保存当前循环动作参数"""
        index = self.cycle_motor_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '警告', '请先选择电机')
            return
            
        motor_id = self.cycle_motor_combo.itemData(index)
        
        try:
            actions = []
            for row in range(5):
                action = {}
                
                # 获取数值参数
                position_item = self.cycle_actions_table.item(row, 0)
                speed_item = self.cycle_actions_table.item(row, 1)
                accel_item = self.cycle_actions_table.item(row, 2)
                decel_item = self.cycle_actions_table.item(row, 3)
                direction_item = self.cycle_actions_table.item(row, 4)
                
                if not all([position_item, speed_item, accel_item, decel_item, direction_item]):
                    QMessageBox.warning(self, '错误', f'动作 {row+1} 的参数不完整')
                    return
                
                action['position'] = float(position_item.text())
                action['max_speed'] = float(speed_item.text())
                action['acceleration'] = int(accel_item.text())
                action['deceleration'] = int(decel_item.text())
                
                # 获取方向和绝对位置状态
                direction_text = direction_item.text()
                
                # 确保方向值是CW或CCW
                if direction_text.strip().upper() not in ["CW", "CCW"]:
                    direction_text = "CW"
                    direction_item.setText("CW")
                
                action['direction'] = direction_text
                
                # 获取绝对位置复选框状态
                checkbox_widget = self.cycle_actions_table.cellWidget(row, 5)
                if checkbox_widget:
                    # 获取复选框（在布局中的第一个子控件）
                    checkbox = checkbox_widget.layout().itemAt(0).widget()
                    action['is_absolute'] = checkbox.isChecked() if checkbox else True
                else:
                    action['is_absolute'] = True
                
                actions.append(action)
            
            # 保存动作参数
            self.cycle_actions_dict[motor_id] = actions
            
            QMessageBox.information(self, '成功', f'已保存电机 {motor_id} 的 {len(actions)} 个动作参数')
            
        except ValueError as e:
            QMessageBox.warning(self, '错误', f'参数格式错误: {str(e)}')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'保存失败: {str(e)}')
    
    def get_cycle_actual_angle(self, input_angle, motor_id, action):
        """根据减速比和显示模式计算实际发送给电机的角度"""
        # 获取指定电机的减速比，默认为1.0
        reducer_ratio = self.motor_reducer_ratios.get(motor_id, 1.0)
        display_mode = self.cycle_angle_display_mode.currentText()
        
        if display_mode == "输出端角度":
            # 用户输入的是减速器输出端角度，需要乘以减速比
            return input_angle * reducer_ratio
        else:
            # 用户输入的是电机端角度，直接使用
            return input_angle
    
    def start_multi_cycle_motion(self):
        """开始多电机循环运动"""
        # 获取选中的电机
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            QMessageBox.warning(self, '警告', '请先选择至少一个电机')
            return
        
        # 检查选中的电机是否都有动作参数
        missing_motors = []
        for motor_id, _ in selected_motors:
            if motor_id not in self.cycle_actions_dict or not self.cycle_actions_dict[motor_id]:
                missing_motors.append(motor_id)
        
        if missing_motors:
            QMessageBox.warning(self, '警告', f'以下电机缺少动作参数: {", ".join(map(str, missing_motors))}')
            return
        
        if self.cycling_motors:
            QMessageBox.warning(self, '警告', '循环运动已在进行中')
            return
        
        try:
            # 使能所有选中的电机
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.enable()
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 使能失败: {str(e)}')
            
            # 初始化循环运动参数
            self.cycling_motors = set(motor_id for motor_id, _ in selected_motors)
            self.motor_current_action_index = {motor_id: 0 for motor_id, _ in selected_motors}
            self.motor_action_start_time = {}
            
            # 为每个电机单独执行第一个动作
            motor_status_text = []
            for motor_id, motor in selected_motors:
                # 获取第一个动作参数
                actions = self.cycle_actions_dict.get(motor_id, [])
                if not actions:
                    continue
                    
                action = actions[0]  # 第一个动作
                
                try:
                    # 获取实际发送给电机的角度
                    actual_position = self.get_cycle_actual_angle(action['position'], motor_id, action)
                    
                    # 根据方向调整位置值（仅对相对位置有效）
                    direction = action['direction']
                    if direction == "CCW" and not action['is_absolute']:  # 逆时针且为相对位置
                        actual_position = -actual_position
                    
                    # 执行梯形曲线运动
                    motor.control_actions.move_to_position_trapezoid(
                        position=actual_position,
                        max_speed=action['max_speed'],
                        acceleration=action['acceleration'],
                        deceleration=action['deceleration'],
                        is_absolute=action['is_absolute']
                    )
                    
                    # 记录动作开始时间
                    self.motor_action_start_time[motor_id] = time.time()
                    
                    # 添加到状态文本
                    pos_type = "绝对位置" if action['is_absolute'] else "相对位置"
                    motor_status_text.append(
                        f"电机{motor_id}: 动作1/{len(actions)} "
                        f"({action['position']}°, {direction}, {pos_type}, "
                        f"{action['max_speed']}RPM)"
                    )
                    
                except Exception as e:
                    QMessageBox.warning(self, '错误', f'电机 {motor_id} 执行动作失败: {str(e)}')
                    if motor_id in self.cycling_motors:
                        self.cycling_motors.remove(motor_id)
            
            # 更新状态显示
            if motor_status_text:
                self.multi_current_action_label.setText(" | ".join(motor_status_text))
            
            # 启动定时器
            self.multi_cycle_timer.start(100)  # 每100ms检查一次
            
            # 更新UI状态
            self.start_multi_cycle_btn.setEnabled(False)
            self.stop_multi_cycle_btn.setEnabled(True)
            self.multi_cycle_status_label.setText("运行中")
            self.multi_cycle_status_label.setProperty("class", "status-connected")
            self.multi_cycle_status_label.setStyle(self.multi_cycle_status_label.style())
            
            QMessageBox.information(self, '成功', f'开始循环运动，共 {len(self.cycling_motors)} 个电机')
            
        except Exception as e:
            self.cycling_motors.clear()
            self.multi_cycle_timer.stop()
            QMessageBox.warning(self, '失败', f'启动循环运动失败: {str(e)}')
    
    def stop_multi_cycle_motion(self):
        """停止多电机循环运动"""
        if not self.cycling_motors:
            return
        
        self.cycling_motors.clear()
        self.multi_cycle_timer.stop()
        
        # 更新UI状态
        self.start_multi_cycle_btn.setEnabled(True)
        self.stop_multi_cycle_btn.setEnabled(False)
        self.multi_cycle_status_label.setText("已停止")
        self.multi_cycle_status_label.setProperty("class", "status-disconnected")
        self.multi_cycle_status_label.setStyle(self.multi_cycle_status_label.style())
        self.multi_current_action_label.setText("无")
        

    
    def emergency_stop_multi_cycle(self):
        """紧急停止多电机循环运动"""
        # 获取所有电机对象
        motors = self.get_selected_motor_objects()
        for motor_id, motor in motors:
            try:
                # 紧急停止电机
                motor.control_actions.stop()
            except:
                pass
        
        # 停止循环（无弹窗）
        self.stop_multi_cycle_motion()

    
    def execute_multi_cycle_actions(self):
        """执行所有正在循环的电机的当前动作"""
        if not self.cycling_motors or not self.motors:
            return
        
        motor_status_text = []
        
        for motor_id in list(self.cycling_motors):
            if motor_id not in self.motors:
                self.cycling_motors.remove(motor_id)
                continue
                
            motor = self.motors[motor_id]
            action_index = self.motor_current_action_index[motor_id]
            
            # 获取动作参数
            actions = self.cycle_actions_dict.get(motor_id, [])
            if not actions or action_index >= len(actions):
                continue
                
            action = actions[action_index]
            
            try:
                # 获取实际发送给电机的角度
                actual_position = self.get_cycle_actual_angle(action['position'], motor_id, action)
                
                # 根据方向调整位置值（仅对相对位置有效）
                direction = action['direction']
                if direction == "CCW" and not action['is_absolute']:  # 逆时针且为相对位置
                    actual_position = -actual_position
                
                # 执行梯形曲线运动
                motor.control_actions.move_to_position_trapezoid(
                    position=actual_position,
                    max_speed=action['max_speed'],
                    acceleration=action['acceleration'],
                    deceleration=action['deceleration'],
                    is_absolute=action['is_absolute']
                )
                
                # 记录动作开始时间
                self.motor_action_start_time[motor_id] = time.time()
                
                # 添加到状态文本
                display_mode = self.cycle_angle_display_mode.currentText()
                pos_type = "绝对位置" if action['is_absolute'] else "相对位置"
                motor_status_text.append(
                    f"电机{motor_id}: 动作{action_index+1}/{len(actions)} "
                    f"({action['position']}°, {direction}, {pos_type}, "
                    f"{action['max_speed']}RPM)"
                )
                
            except Exception as e:
                QMessageBox.warning(self, '错误', f'电机 {motor_id} 执行动作失败: {str(e)}')
                self.cycling_motors.remove(motor_id)
        
        # 更新状态显示
        if motor_status_text:
            self.multi_current_action_label.setText(" | ".join(motor_status_text))
    
    def execute_next_multi_cycle_action(self):
        """执行下一个动作（由定时器调用）"""
        if not self.cycling_motors or not self.motors:
            return
        
        motors_needing_next_action = []  # 需要执行下一个动作的电机列表
        
        # 检查每个电机的状态并决定是否进入下一个动作
        for motor_id in list(self.cycling_motors):
            if motor_id not in self.motors:
                self.cycling_motors.remove(motor_id)
                continue
                
            motor = self.motors[motor_id]
            
            try:
                # 检查电机是否到位
                motor_status = motor.read_parameters.get_motor_status()
                
                # 如果电机到位，等待间隔时间后执行下一个动作
                if motor_status.in_position and motor_id in self.motor_action_start_time:
                    elapsed_time = time.time() - self.motor_action_start_time[motor_id]
                    interval = self.action_interval_spinbox.value()
                    
                    if elapsed_time >= interval:
                        # 移动到下一个动作
                        actions = self.cycle_actions_dict.get(motor_id, [])
                        if actions:
                            current_index = self.motor_current_action_index[motor_id]
                            next_index = (current_index + 1) % len(actions)
                            self.motor_current_action_index[motor_id] = next_index
                            motors_needing_next_action.append(motor_id)
                
            except Exception as e:
                # 如果读取状态失败，继续运行（可能是通信问题）
                pass
        
        # 为需要执行下一个动作的电机单独执行动作
        if motors_needing_next_action:
            motor_status_text = []
            
            for motor_id in motors_needing_next_action:
                if motor_id not in self.motors or motor_id not in self.cycling_motors:
                    continue
                    
                motor = self.motors[motor_id]
                action_index = self.motor_current_action_index[motor_id]
                
                # 获取动作参数
                actions = self.cycle_actions_dict.get(motor_id, [])
                if not actions or action_index >= len(actions):
                    continue
                    
                action = actions[action_index]
                
                try:
                    # 获取实际发送给电机的角度
                    actual_position = self.get_cycle_actual_angle(action['position'], motor_id, action)
                    
                    # 根据方向调整位置值（仅对相对位置有效）
                    direction = action['direction']
                    if direction == "CCW" and not action['is_absolute']:  # 逆时针且为相对位置
                        actual_position = -actual_position
                    
                    # 执行梯形曲线运动
                    motor.control_actions.move_to_position_trapezoid(
                        position=actual_position,
                        max_speed=action['max_speed'],
                        acceleration=action['acceleration'],
                        deceleration=action['deceleration'],
                        is_absolute=action['is_absolute']
                    )
                    
                    # 记录动作开始时间
                    self.motor_action_start_time[motor_id] = time.time()
                    
                    # 添加到状态文本
                    pos_type = "绝对位置" if action['is_absolute'] else "相对位置"
                    motor_status_text.append(
                        f"电机{motor_id}: 动作{action_index+1}/{len(actions)} "
                        f"({action['position']}°, {direction}, {pos_type}, "
                        f"{action['max_speed']}RPM)"
                    )
                    
                except Exception as e:
                    QMessageBox.warning(self, '错误', f'电机 {motor_id} 执行动作失败: {str(e)}')
                    self.cycling_motors.remove(motor_id)
            
            # 更新状态显示
            if motor_status_text:
                # 获取当前其他电机的状态文本
                current_text = self.multi_current_action_label.text()
                current_motor_texts = {}
                
                # 解析当前显示的电机状态文本
                for part in current_text.split(" | "):
                    if part.startswith("电机"):
                        try:
                            motor_id_str = part.split(":")[0].replace("电机", "").strip()
                            motor_id = int(motor_id_str)
                            if motor_id not in motors_needing_next_action:
                                current_motor_texts[motor_id] = part
                        except:
                            pass
                
                # 合并新的状态文本和旧的状态文本
                for text in motor_status_text:
                    motor_id_str = text.split(":")[0].replace("电机", "").strip()
                    try:
                        motor_id = int(motor_id_str)
                        current_motor_texts[motor_id] = text
                    except:
                        pass
                
                # 更新UI显示
                all_texts = list(current_motor_texts.values())
                self.multi_current_action_label.setText(" | ".join(all_texts))
        
        # 如果没有电机在循环，停止循环运动
        if not self.cycling_motors:
            self.stop_multi_cycle_motion()
    
    def on_motor_selection_changed(self):
        """电机选择改变"""
        self.selected_motors.clear()
        for item in self.motor_list.selectedItems():
            motor_id = item.data(Qt.UserRole)
            self.selected_motors.append(motor_id)
        
        self.update_selection_status()
    
    def update_selection_status(self):
        """更新选择状态显示"""
        if self.selected_motors:
            self.selection_status.setText(f"已选择: {self.selected_motors}")
            self.selection_status.setProperty("class", "status-connected")
            self.selection_status.setStyle(self.selection_status.style())  # 刷新样式
            
            # 更新其他状态标签
            if hasattr(self, 'selected_motors_label'):
                self.selected_motors_label.setText(f"ID: {self.selected_motors}")
            if hasattr(self, 'batch_selected_count_label'):
                self.batch_selected_count_label.setText(str(len(self.selected_motors)))
            if hasattr(self, 'multi_selected_motors_count_label'):
                self.multi_selected_motors_count_label.setText(str(len(self.selected_motors)))
        else:
            self.selection_status.setText("未选择电机")
            self.selection_status.setProperty("class", "status-disconnected")
            self.selection_status.setStyle(self.selection_status.style())  # 刷新样式
            
            # 更新其他状态标签
            if hasattr(self, 'selected_motors_label'):
                self.selected_motors_label.setText("未选择")
            if hasattr(self, 'batch_selected_count_label'):
                self.batch_selected_count_label.setText("0")
            if hasattr(self, 'multi_selected_motors_count_label'):
                self.multi_selected_motors_count_label.setText("0")
    
    def select_all_motors(self):
        """全选电机"""
        self.motor_list.selectAll()
    
    def select_no_motors(self):
        """全不选电机"""
        self.motor_list.clearSelection()
    
    def enable_controls(self, enabled):
        """启用/禁用控件"""
        for tab_index in range(self.tab_widget.count()):
            tab = self.tab_widget.widget(tab_index)
            tab.setEnabled(enabled)
    
    def get_selected_motor_objects(self):
        """获取选中的电机对象"""
        if not self.selected_motors:
            QMessageBox.warning(self, '警告', '请先选择要操作的电机')
            return []
        
        return [(motor_id, self.motors[motor_id]) for motor_id in self.selected_motors if motor_id in self.motors]
    
    def toggle_auto_refresh(self, checked):
        """切换自动刷新"""
        if checked:
            self.status_timer.start(2000)  # 每2秒刷新
        else:
            self.status_timer.stop()
    
    def refresh_status(self):
        """刷新状态显示"""
        if not self.motors:
            return
        
        try:
            motor_ids = sorted(self.motors.keys())
            self.status_table.setRowCount(len(motor_ids))
            
            for row, motor_id in enumerate(motor_ids):
                motor = self.motors[motor_id]
                
                try:
                    # 读取状态信息
                    motor_status = motor.read_parameters.get_motor_status()
                    motor_position = motor.read_parameters.get_position()
                    display_position = self.get_display_angle(motor_position, motor_id)
                    speed = motor.read_parameters.get_speed()
                    voltage = motor.read_parameters.get_bus_voltage()
                    current = motor.read_parameters.get_current()
                    temperature = motor.read_parameters.get_temperature()
                    
                    # 更新表格
                    self.status_table.setItem(row, 0, QTableWidgetItem(str(motor_id)))
                    self.status_table.setItem(row, 1, QTableWidgetItem("是" if motor_status.enabled else "否"))
                    self.status_table.setItem(row, 2, QTableWidgetItem("是" if motor_status.in_position else "否"))
                    
                    # 位置信息已经在表头中显示模式，这里只显示数值
                    self.status_table.setItem(row, 3, QTableWidgetItem(f"{display_position:.2f}"))
                    
                    self.status_table.setItem(row, 4, QTableWidgetItem(f"{speed:.2f}"))
                    self.status_table.setItem(row, 5, QTableWidgetItem(f"{voltage:.2f}"))
                    self.status_table.setItem(row, 6, QTableWidgetItem(f"{current:.3f}"))
                    self.status_table.setItem(row, 7, QTableWidgetItem(f"{temperature:.1f}"))
                    
                except Exception as e:
                    # 如果读取失败，显示错误信息
                    for col in range(1, 8):
                        self.status_table.setItem(row, col, QTableWidgetItem("读取失败"))
            
        except Exception as e:
            QMessageBox.warning(self, '读取失败', f'刷新状态失败:\n{str(e)}')
    
    def update_status_display(self):
        """更新状态显示（定时器调用）"""
        self.refresh_status()
    
    # 同步控制方法
    def parse_motor_values(self, text, default_value):
        """解析电机值字符串"""
        text = text.strip()
        if not text:
            return {}
        
        motor_values = {}
        
        # 检查是否是统一值格式
        try:
            value = float(text)
            # 统一值，应用到所有选中的电机
            for motor_id in self.selected_motors:
                motor_values[motor_id] = value
            return motor_values
        except ValueError:
            pass
        
        # 解析ID:值格式
        try:
            pairs = text.split(',')
            for pair in pairs:
                if ':' in pair:
                    motor_id_str, value_str = pair.split(':', 1)
                    motor_id = int(motor_id_str.strip())
                    value = float(value_str.strip())
                    motor_values[motor_id] = value
        except (ValueError, IndexError):
            QMessageBox.warning(self, '格式错误', '输入格式错误，请使用 "ID1:值1,ID2:值2" 或统一值格式')
            return {}
        
        return motor_values
    
    def get_actual_angle(self, input_angle, motor_id=None):
        """根据减速比和显示模式计算实际发送给电机的角度"""
        # 获取对应电机的减速比
        reducer_ratio = self.motor_reducer_ratios.get(motor_id, 1.0) if motor_id else 1.0
        
        display_mode = "电机端角度"
        try:
            if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                display_mode = self.multi_angle_display_mode.currentText()
        except (RuntimeError, AttributeError):
            display_mode = "电机端角度"
        
        if display_mode == "输出端角度":
            # 用户输入的是减速器输出端角度，需要乘以减速比
            return input_angle * reducer_ratio
        else:
            # 用户输入的是电机端角度，直接使用
            return input_angle
    
    def get_display_angle(self, motor_angle, motor_id=None):
        """根据减速比和显示模式将电机角度转换为显示角度"""
        # 获取对应电机的减速比
        reducer_ratio = self.motor_reducer_ratios.get(motor_id, 1.0) if motor_id else 1.0
        
        display_mode = "电机端角度"
        try:
            if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                display_mode = self.multi_angle_display_mode.currentText()
        except (RuntimeError, AttributeError):
            display_mode = "电机端角度"
        
        if display_mode == "输出端角度":
            # 显示减速器输出端角度
            return motor_angle / reducer_ratio
        else:
            # 显示电机端角度
            return motor_angle
    
    def update_multi_angle_display_mode(self):
        """更新多电机角度显示模式"""
        try:
            if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                display_mode = self.multi_angle_display_mode.currentText()
            else:
                display_mode = "电机端角度"
        except (RuntimeError, AttributeError):
            display_mode = "电机端角度"
        
        # 更新状态表格头部
        self.setup_status_table()
        
        if display_mode == "输出端角度":
            # 更新位置控制的最大值，考虑减速比
            # 使用最小的减速比来确定最大输出角度
            min_reducer_ratio = 1.0
            if self.motor_reducer_ratios:
                min_reducer_ratio = min(self.motor_reducer_ratios.values())
            
            max_output_angle = 429496729.5 / min_reducer_ratio
            if hasattr(self, 'batch_position_spinbox') and self.batch_position_spinbox:
                self.batch_position_spinbox.setRange(0.0, max_output_angle)
            
            # 更新提示文本
            hint_text = f"范围：0.0 ~ {max_output_angle:.1f}，单位：°（输出端）"
            
        else:
            # 恢复电机端角度范围
            if hasattr(self, 'batch_position_spinbox') and self.batch_position_spinbox:
                self.batch_position_spinbox.setRange(0.0, 429496729.5)
            
            # 更新提示文本
            hint_text = "范围：0.0 ~ 429496729.5，单位：°（电机端）"
        
        # 更新相关的提示文本
        self.update_position_hints(hint_text)
    
    def start_sync_position_motion(self):
        """开始同步位置运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        # 解析位置值
        positions = self.parse_motor_values(
            self.sync_positions_edit.text(),
            self.sync_position_speed.value()
        )
        
        if not positions:
            return
        
        try:
            speed = self.sync_position_speed.value()
            direction = self.sync_position_direction.currentText()  # CW/CCW
            is_absolute = self.sync_position_absolute.isChecked()
            
            # 如果是Y板：走多电机命令一次性下发
            if self._is_y_board():
                commands = []
                for motor_id, motor in selected_motors:
                    if motor_id in positions:
                        input_position = positions[motor_id]
                        actual_position = self.get_actual_angle(input_position, motor_id)
                        if direction == "CCW" and not is_absolute:
                            actual_position = -actual_position
                        func = motor.command_builder.position_mode_direct(
                            actual_position, abs(speed), is_absolute, multi_sync=False
                        )
                        commands.append(self._build_single_command_for_y42(motor_id, func))
                if commands:
                    first_motor = selected_motors[0][1]
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                    self.update_sync_status("已下发(多电机命令)", "status-connected")
                    QMessageBox.information(self, '成功', '多电机命令(直通)已下发')
                    return
            
            # 否则：走原多机同步标志+广播
            # 更新状态为运行中
            self.update_sync_status("同步位置运动中", "status-warning")
            
            # 第一阶段：发送带同步标志的位置命令
            for motor_id, motor in selected_motors:
                if motor_id in positions:
                    input_position = positions[motor_id]
                    actual_position = self.get_actual_angle(input_position, motor_id)
                    
                    # 如果是逆时针且为相对位置，则位置值也变为负值
                    if direction == "CCW" and not is_absolute:
                        actual_position = -actual_position
                    
                    motor.control_actions.move_to_position(
                        position=actual_position,
                        speed=abs(speed),  # 速度传递绝对值
                        is_absolute=is_absolute,
                        multi_sync=True  # 同步标志
                    )
            
            # 第二阶段：发送同步运动命令
            # 使用第一个电机发送广播同步命令
            if selected_motors:
                first_motor = selected_motors[0][1]
                # 创建广播控制器（ID=0）
                broadcast_motor = first_motor.__class__(
                    motor_id=0,
                    interface_type=first_motor.interface_type,
                    shared_interface=True,
                    **first_motor.interface_kwargs
                )
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
            
            # 更新状态为完成
            self.update_sync_status("同步位置运动完成", "status-connected")
            
            # 安全获取显示模式
            try:
                if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                    display_mode = self.multi_angle_display_mode.currentText()
                else:
                    display_mode = "电机端角度"
            except (RuntimeError, AttributeError):
                display_mode = "电机端角度"
                
            QMessageBox.information(self, '成功', f'同步位置运动已开始 ({display_mode})')
            
        except Exception as e:
            # 更新状态为失败
            self.update_sync_status("同步位置运动失败", "status-disconnected")
            QMessageBox.warning(self, '失败', f'同步位置运动失败:\n{str(e)}')
    
    def start_sync_speed_motion(self):
        """开始同步速度运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        # 解析速度值
        speeds = self.parse_motor_values(
            self.sync_speeds_edit.text(),
            self.sync_speed_acceleration.value()
        )
        
        if not speeds:
            return
        
        try:
            acceleration = self.sync_speed_acceleration.value()
            direction = self.sync_speed_direction.currentText()  # CW/CCW
            
            # 如果是Y板：走多电机命令一次性下发
            if self._is_y_board():
                commands = []
                for motor_id, motor in selected_motors:
                    if motor_id in speeds:
                        spd = speeds[motor_id]
                        if direction == "CCW":
                            spd = -spd
                        func = motor.command_builder.speed_mode(
                            speed=spd,
                            acceleration=acceleration,
                            multi_sync=False
                        )
                        commands.append(self._build_single_command_for_y42(motor_id, func))
                if commands:
                    first_motor = selected_motors[0][1]
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                    QMessageBox.information(self, '成功', '多电机命令(速度)已下发')
                    return
            
            # 否则：原同步标志 + 广播
            # 第一阶段：发送带同步标志的速度命令
            for motor_id, motor in selected_motors:
                if motor_id in speeds:
                    speed = speeds[motor_id]
                    # 根据方向调整速度值
                    if direction == "CCW":  # 逆时针
                        speed = -speed
                    
                    motor.control_actions.set_speed(
                        speed=speed,
                        acceleration=acceleration,
                        multi_sync=True  # 同步标志
                    )
            
            # 第二阶段：发送同步运动命令
            if selected_motors:
                first_motor = selected_motors[0][1]
                broadcast_motor = first_motor.__class__(
                    motor_id=0,
                    interface_type=first_motor.interface_type,
                    shared_interface=True,
                    **first_motor.interface_kwargs
                )
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
            
            QMessageBox.information(self, '成功', '同步速度运动已开始')
            
        except Exception as e:
            QMessageBox.warning(self, '失败', f'同步速度运动失败:\n{str(e)}')
    
    def start_sync_trapezoid_motion(self):
        """开始同步梯形曲线运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        # 解析位置
        positions = self.parse_motor_values(
            self.sync_trapezoid_positions_edit.text(),
            self.sync_trapezoid_max_speed.value()
        )
        
        if not positions:
            return
        
        try:
            max_speed = self.sync_trapezoid_max_speed.value()
            direction = self.sync_trapezoid_direction.currentText()  # CW/CCW
            acceleration = self.sync_trapezoid_acceleration.value()
            deceleration = self.sync_trapezoid_deceleration.value()
            is_absolute = self.sync_trapezoid_absolute.isChecked()
            
            # 如果是Y板：走多电机命令一次性下发
            if self._is_y_board():
                commands = []
                for motor_id, motor in selected_motors:
                    if motor_id in positions:
                        input_position = positions[motor_id]
                        actual_position = self.get_actual_angle(input_position, motor_id)
                        if direction == "CCW" and not is_absolute:
                            actual_position = -actual_position
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
                    try:
                        display_mode = self.multi_angle_display_mode.currentText() if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode else "电机端角度"
                    except (RuntimeError, AttributeError):
                        display_mode = "电机端角度"
                    QMessageBox.information(self, '成功', f'多电机命令(梯形)已下发 ({display_mode})')
                    return
            
            # 否则：原同步标志 + 广播
            max_speed = self.sync_trapezoid_max_speed.value()
            direction = self.sync_trapezoid_direction.currentText()  # CW/CCW
            acceleration = self.sync_trapezoid_acceleration.value()
            deceleration = self.sync_trapezoid_deceleration.value()
            is_absolute = self.sync_trapezoid_absolute.isChecked()
            
            # 第一阶段：发送带同步标志的位置命令
            for motor_id, motor in selected_motors:
                if motor_id in positions:
                    input_position = positions[motor_id]
                    actual_position = self.get_actual_angle(input_position, motor_id)
                    
                    # 如果是逆时针且为相对位置，则位置值也变为负值
                    if direction == "CCW" and not is_absolute:
                        actual_position = -actual_position
                    
                    motor.control_actions.move_to_position_trapezoid(
                        position=actual_position,
                        max_speed=max_speed,
                        acceleration=acceleration,
                        deceleration=deceleration,
                        is_absolute=is_absolute,
                        multi_sync=True  # 同步标志
                    )
            
            # 第二阶段：发送同步运动命令
            # 使用第一个电机发送广播同步命令
            if selected_motors:
                first_motor = selected_motors[0][1]
                # 创建广播控制器（ID=0）
                broadcast_motor = first_motor.__class__(
                    motor_id=0,
                    interface_type=first_motor.interface_type,
                    shared_interface=True,
                    **first_motor.interface_kwargs
                )
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
            
            # 安全获取显示模式
            try:
                if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                    display_mode = self.multi_angle_display_mode.currentText()
                else:
                    display_mode = "电机端角度"
            except (RuntimeError, AttributeError):
                display_mode = "电机端角度"
                
            QMessageBox.information(self, '成功', f'同步梯形曲线运动已开始 ({display_mode})')
            
        except Exception as e:
            QMessageBox.warning(self, '失败', f'同步梯形曲线运动失败:\n{str(e)}')
    
    def start_sync_homing(self):
        """开始同步回零"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            homing_mode = self.sync_homing_mode.currentIndex()
            
            # 第一阶段：发送带同步标志的回零命令
            for motor_id, motor in selected_motors:
                motor.control_actions.trigger_homing(
                    homing_mode=homing_mode,
                    multi_sync=True  # 同步标志
                )
            
            # 第二阶段：发送同步运动命令
            if selected_motors:
                first_motor = selected_motors[0][1]
                broadcast_motor = first_motor.__class__(
                    motor_id=0,
                    interface_type=first_motor.interface_type,
                    shared_interface=True,
                    **first_motor.interface_kwargs
                )
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
            
            QMessageBox.information(self, '成功', '同步回零已开始')
            
        except Exception as e:
            QMessageBox.warning(self, '失败', f'同步回零失败:\n{str(e)}')
    
    # 批量操作方法
    def batch_enable_motors(self):
        """批量使能电机"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.enable()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 使能失败:\n{str(e)}')
        
        QMessageBox.information(self, '完成', f'成功使能 {success_count}/{len(selected_motors)} 个电机')
    
    def batch_disable_motors(self):
        """批量失能电机"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.disable()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 失能失败:\n{str(e)}')
        
        QMessageBox.information(self, '完成', f'成功失能 {success_count}/{len(selected_motors)} 个电机')
    
    def batch_stop_motors(self):
        """批量停止电机"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.stop()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 停止失败:\n{str(e)}')
        
        QMessageBox.information(self, '完成', f'成功停止 {success_count}/{len(selected_motors)} 个电机')
    
    def stop_sync_motion(self):
        """停止同步运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        # 更新状态为停止中
        self.update_sync_status("正在停止同步运动", "status-warning")
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.stop()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 停止失败:\n{str(e)}')
        
        # 更新状态为已停止
        self.update_sync_status("同步运动已停止", "status-disconnected")
        QMessageBox.information(self, '完成', f'成功停止 {success_count}/{len(selected_motors)} 个电机')
    
    
    def batch_clear_position(self):
        """批量清零位置"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.trigger_actions.clear_position()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 清零位置失败:\n{str(e)}')
        
        QMessageBox.information(self, '完成', f'成功清零 {success_count}/{len(selected_motors)} 个电机位置')
    
    def batch_set_zero_position(self):
        """批量设置零点位置"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        save_to_chip = self.batch_save_zero_to_chip_checkbox.isChecked()
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.set_zero_position(save_to_chip=save_to_chip)
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 设置零点失败:\n{str(e)}')
        
        save_info = "已保存到芯片" if save_to_chip else "未保存到芯片"
        QMessageBox.information(self, '完成', f'成功设置 {success_count}/{len(selected_motors)} 个电机零点 ({save_info})')
    
    def batch_release_stall_protection(self):
        """批量解除堵转保护"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.trigger_actions.release_stall_protection()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 解除堵转保护失败:\n{str(e)}')
        
        QMessageBox.information(self, '完成', f'成功解除 {success_count}/{len(selected_motors)} 个电机堵转保护')
    
    def batch_start_homing(self):
        """批量回零（按选择的回零方式）"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            # 获取选择的回零模式（索引即协议模式码）
            homing_mode = 0
            if hasattr(self, 'batch_homing_mode_combo') and self.batch_homing_mode_combo:
                homing_mode = self.batch_homing_mode_combo.currentIndex()
            
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.trigger_homing(homing_mode=homing_mode)
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 回零失败:\n{str(e)}')
            
            QMessageBox.information(self, '完成', f'已开始 {success_count}/{len(selected_motors)} 个电机的回零')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'批量回零失败:\n{str(e)}')
    
    def batch_position_motion(self):
        """批量位置运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            input_position = self.batch_position_spinbox.value()
            speed = self.batch_position_speed_spinbox.value()
            direction = self.batch_position_direction.currentText()  # CW/CCW
            is_absolute = self.batch_position_absolute_checkbox.isChecked()
            
            # 更新状态为运行中
            self.update_batch_status("位置运动中", "status-warning")
            
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    # 为每个电机单独计算角度
                    actual_position = self.get_actual_angle(input_position, motor_id)
                    
                    # 根据方向调整位置值（仅对相对位置有效）
                    if direction == "CCW" and not is_absolute:  # 逆时针且为相对位置
                        actual_position = -actual_position
                    
                    motor.control_actions.move_to_position(
                        position=actual_position,
                        speed=speed,
                        is_absolute=is_absolute
                    )
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 位置运动失败:\n{str(e)}')
            
            # 更新状态为完成
            self.update_batch_status("位置运动完成", "status-connected")
            
            # 安全获取显示模式
            try:
                if hasattr(self, 'multi_angle_display_mode') and self.multi_angle_display_mode:
                    display_mode = self.multi_angle_display_mode.currentText()
                else:
                    display_mode = "电机端角度"
            except (RuntimeError, AttributeError):
                display_mode = "电机端角度"
                
            QMessageBox.information(self, '完成', f'成功启动 {success_count}/{len(selected_motors)} 个电机的位置运动 ({display_mode})')
        except Exception as e:
            # 更新状态为失败
            self.update_batch_status("位置运动失败", "status-disconnected")
            QMessageBox.warning(self, '失败', f'批量位置运动失败:\n{str(e)}')
    
    def batch_speed_motion(self):
        """批量速度运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            speed = self.batch_speed_spinbox.value()
            direction = self.batch_speed_direction.currentText()  # CW/CCW
            acceleration = self.batch_speed_acceleration_spinbox.value()
            
            # 根据方向调整速度值
            if direction == "CCW":  # 逆时针
                speed = -speed
            
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.set_speed(
                        speed=speed,
                        acceleration=acceleration
                    )
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 速度运动失败:\n{str(e)}')
            
            QMessageBox.information(self, '完成', f'成功启动 {success_count}/{len(selected_motors)} 个电机速度运动')
            
        except Exception as e:
            QMessageBox.warning(self, '失败', f'批量速度运动失败:\n{str(e)}') 

    def stop_batch_motion(self):
        """停止批量运动"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        # 更新状态为停止中
        self.update_batch_status("正在停止批量运动", "status-warning")
        
        success_count = 0
        for motor_id, motor in selected_motors:
            try:
                motor.control_actions.stop()
                success_count += 1
            except Exception as e:
                QMessageBox.warning(self, '警告', f'电机 {motor_id} 停止失败:\n{str(e)}')
        
        # 更新状态为已停止
        self.update_batch_status("批量运动已停止", "status-disconnected")
        QMessageBox.information(self, '完成', f'成功停止 {success_count}/{len(selected_motors)} 个电机')
    

    
    def update_batch_status(self, status_text, status_class="status-disconnected"):
        """更新批量操作状态"""
        if hasattr(self, 'batch_status_label'):
            self.batch_status_label.setText(status_text)
            self.batch_status_label.setProperty("class", status_class)
            self.batch_status_label.setStyle(self.batch_status_label.style())
    
    def update_sync_status(self, status_text, status_class="status-disconnected"):
        """更新同步控制状态"""
        if hasattr(self, 'sync_status_label'):
            self.sync_status_label.setText(status_text)
            self.sync_status_label.setProperty("class", status_class)
            self.sync_status_label.setStyle(self.sync_status_label.style()) 

    def on_multi_auto_homing_toggled(self, checked):
        """多电机上电自动回零状态切换"""
        self.multi_auto_homing_checkbox.setText("Enable" if checked else "Disable")

    def multi_read_homing_parameters(self):
        """读取首个选中电机的回零参数"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            # 读取第一个选中电机的回零参数（严格15字节）
            first_motor = selected_motors[0][1]
            params = first_motor.read_parameters.get_homing_parameters()
            
            # 更新界面显示
            mode_count = self.multi_homing_param_mode_combo.count() if hasattr(self, 'multi_homing_param_mode_combo') else 0
            safe_mode_idx = min(params.mode, mode_count - 1) if mode_count > 0 else 0
            self.multi_homing_param_mode_combo.setCurrentIndex(safe_mode_idx)
            self.multi_homing_direction_combo.setCurrentIndex(params.direction)
            self.multi_homing_speed_spinbox.setValue(params.speed)
            self.multi_homing_timeout_spinbox.setValue(params.timeout)
            self.multi_collision_detection_speed_spinbox.setValue(params.collision_detection_speed)
            self.multi_collision_detection_current_spinbox.setValue(params.collision_detection_current)
            self.multi_collision_detection_time_spinbox.setValue(params.collision_detection_time)
            self.multi_auto_homing_checkbox.setChecked(params.auto_homing_enabled)
            
            # 启用所有字段
            self.multi_collision_detection_speed_spinbox.setEnabled(True)
            self.multi_collision_detection_current_spinbox.setEnabled(True)
            self.multi_collision_detection_time_spinbox.setEnabled(True)
            self.multi_auto_homing_checkbox.setEnabled(True)
            
            self.multi_homing_params_status_label.setText(f"已读取电机 {selected_motors[0][0]} 的参数")
            QMessageBox.information(self, '成功', f'成功读取电机 {selected_motors[0][0]} 的回零参数')
        except Exception as e:
            # 兼容7字节
            try:
                first_motor = selected_motors[0][1]
                raw = first_motor.read_parameters.get_homing_parameters_raw()
                if len(raw) == 7:
                    mode = raw[0]
                    direction = raw[1]
                    speed = (raw[2] << 8) | raw[3]
                    timeout_high3 = (raw[4] << 16) | (raw[5] << 8) | raw[6]
                    display_timeout = (timeout_high3 << 8)
                    
                    mode_count = self.multi_homing_param_mode_combo.count() if hasattr(self, 'multi_homing_param_mode_combo') else 0
                    safe_mode_idx = min(mode, mode_count - 1) if mode_count > 0 else 0
                    self.multi_homing_param_mode_combo.setCurrentIndex(safe_mode_idx)
                    self.multi_homing_direction_combo.setCurrentIndex(direction)
                    self.multi_homing_speed_spinbox.setValue(speed)
                    self.multi_homing_timeout_spinbox.setValue(min(display_timeout, self.multi_homing_timeout_spinbox.maximum()))
                    
                    self.multi_collision_detection_speed_spinbox.setEnabled(False)
                    self.multi_collision_detection_current_spinbox.setEnabled(False)
                    self.multi_collision_detection_time_spinbox.setEnabled(False)
                    self.multi_auto_homing_checkbox.setEnabled(True)
                    
                    self.multi_homing_params_status_label.setText("设备返回为精简格式(7字节)，仅已显示模式/方向/速度/超时(高3字节)")
                    QMessageBox.information(self, '提示', '设备返回为精简格式(7字节)。已显示：模式/方向/速度/超时(高3字节)。\n碰撞参数与自动回零未返回，已禁用。')
                else:
                    QMessageBox.warning(self, '失败', f'读取回零参数失败:\n设备返回{len(raw)}字节(期望15或7)。')
            except Exception as e2:
                QMessageBox.warning(self, '失败', f'读取回零参数失败:\n{str(e)}\n兼容读取也失败: {str(e2)}')
    
    def multi_modify_homing_parameters(self):
        """批量修改回零参数"""
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            # 若处于7字节兼容模式（碰撞参数控件被禁用），提示确认
            compat_mode = not (self.multi_collision_detection_speed_spinbox.isEnabled() and 
                               self.multi_collision_detection_current_spinbox.isEnabled() and 
                               self.multi_collision_detection_time_spinbox.isEnabled())
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
            mode = self.multi_homing_param_mode_combo.currentIndex()  # 使用选择的模式
            direction = self.multi_homing_direction_combo.currentIndex()
            speed = self.multi_homing_speed_spinbox.value()
            timeout = self.multi_homing_timeout_spinbox.value()
            collision_detection_speed = self.multi_collision_detection_speed_spinbox.value()
            collision_detection_current = self.multi_collision_detection_current_spinbox.value()
            collision_detection_time = self.multi_collision_detection_time_spinbox.value()
            auto_homing_enabled = self.multi_auto_homing_checkbox.isChecked()
            save_to_chip = self.multi_save_homing_params_checkbox.isChecked()
            
            # 批量修改参数
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.modify_homing_parameters(
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
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 回零参数修改失败:\n{str(e)}')
            
            save_info = "已保存到芯片" if save_to_chip else "未保存到芯片"
            self.multi_homing_params_status_label.setText(f"成功修改 {success_count} 个电机参数")
            QMessageBox.information(self, '完成', f'成功修改 {success_count}/{len(selected_motors)} 个电机的回零参数 ({save_info})')
            
        except Exception as e:
            self.multi_homing_params_status_label.setText("修改失败")
            QMessageBox.warning(self, '失败', f'批量修改回零参数失败:\n{str(e)}') 

    def apply_reducer_ratios(self):
        """应用减速比设置"""
        if not self.motors:
            QMessageBox.warning(self, '警告', '请先连接电机')
            return
        
        text = self.multi_reducer_ratio_edit.text().strip()
        if not text:
            QMessageBox.warning(self, '警告', '请输入减速比')
            return
        
        try:
            # 解析减速比设置
            motor_ratios = self.parse_motor_values(text, 1.0)
            
            if not motor_ratios:
                return
            
            # 更新减速比字典
            for motor_id, ratio in motor_ratios.items():
                if ratio < 1.0 or ratio > 1000.0:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 的减速比 {ratio} 超出范围 (1.0 ~ 1000.0)')
                    return
                self.motor_reducer_ratios[motor_id] = ratio
            
            # 更新状态显示
            self.update_reducer_status()
            
            # 更新状态表格头部
            self.setup_status_table()
            
            QMessageBox.information(self, '成功', '减速比设置成功')
            
        except Exception as e:
            QMessageBox.warning(self, '错误', f'减速比设置失败:\n{str(e)}')
    
    def update_reducer_status(self):
        """更新减速比状态显示"""
        if not self.motor_reducer_ratios:
            self.current_reducer_status.setText("当前减速比: 无")
            return
        
        # 显示当前设置的减速比
        status_text = "当前减速比: "
        ratios = []
        for motor_id in sorted(self.motor_reducer_ratios.keys()):
            ratio = self.motor_reducer_ratios[motor_id]
            ratios.append(f"ID{motor_id}:{ratio:.1f}")
        
        if len(ratios) <= 5:
            status_text += ", ".join(ratios)
        else:
            status_text += ", ".join(ratios[:5]) + "..."
        
        self.current_reducer_status.setText(status_text)

    def update_position_hints(self, hint_text):
        """更新位置控制的提示文本"""
        try:
            # 更新同步位置控制的提示
            if hasattr(self, 'sync_positions_edit') and self.sync_positions_edit:
                hint_widget = self.sync_positions_edit.parent().layout().itemAt(2).widget()
                if hint_widget:
                    hint_widget.setText(hint_text)
            
            # 更新同步梯形曲线控制的提示
            if hasattr(self, 'sync_trapezoid_positions_edit') and self.sync_trapezoid_positions_edit:
                hint_widget = self.sync_trapezoid_positions_edit.parent().layout().itemAt(2).widget()
                if hint_widget:
                    hint_widget.setText(hint_text)
                    
        except Exception as e:
            # 如果找不到对应的widget，忽略错误
            pass

    def create_cycle_control_tab(self):
        """创建多电机循环控制标签页"""
        widget = QWidget()
        main_layout = QVBoxLayout(widget)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
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
        
        # 角度显示模式设置
        display_mode_group = QGroupBox("角度显示模式")
        display_mode_layout = QHBoxLayout(display_mode_group)
        display_mode_layout.setContentsMargins(15, 10, 15, 10)
        
        display_mode_layout.addWidget(QLabel("角度显示模式:"))
        
        self.cycle_angle_display_mode = QComboBox()
        self.cycle_angle_display_mode.addItems(["输出端角度", "电机端角度"])
        self.cycle_angle_display_mode.setMaximumWidth(150)
        display_mode_layout.addWidget(self.cycle_angle_display_mode)
        
        # 添加拉伸，让控件左对齐
        display_mode_layout.addStretch()
        
        scroll_layout.addWidget(display_mode_group)
        
        # 创建动作参数表格组
        params_group = QGroupBox("动作参数设置")
        params_layout = QVBoxLayout(params_group)
        params_layout.setContentsMargins(15, 15, 15, 15)
        params_layout.setSpacing(10)
        
        # 电机选择下拉框
        motor_select_layout = QHBoxLayout()
        motor_select_layout.addWidget(QLabel("选择电机:"))
        
        self.cycle_motor_combo = QComboBox()
        self.cycle_motor_combo.currentIndexChanged.connect(self.on_cycle_motor_changed)
        motor_select_layout.addWidget(self.cycle_motor_combo)
        
        motor_select_layout.addStretch()
        params_layout.addLayout(motor_select_layout)
        
        # 添加电机减速比设置
        reducer_ratio_layout = QHBoxLayout()
        reducer_ratio_layout.addWidget(QLabel("电机减速比:"))
        
        self.cycle_motor_reducer_ratio = QLineEdit()
        self.cycle_motor_reducer_ratio.setPlaceholderText("例如: 16")
        self.cycle_motor_reducer_ratio.setText("1.0")  # 默认值
        self.cycle_motor_reducer_ratio.setMaximumWidth(120)
        reducer_ratio_layout.addWidget(self.cycle_motor_reducer_ratio)
        
        self.apply_motor_reducer_ratio_btn = QPushButton("应用减速比")
        self.apply_motor_reducer_ratio_btn.clicked.connect(self.apply_motor_reducer_ratio)
        self.apply_motor_reducer_ratio_btn.setMaximumWidth(100)
        reducer_ratio_layout.addWidget(self.apply_motor_reducer_ratio_btn)
        
        # 显示当前减速比
        self.current_motor_reducer_ratio_label = QLabel("当前减速比: 1.0")
        reducer_ratio_layout.addWidget(self.current_motor_reducer_ratio_label)
        
        reducer_ratio_layout.addStretch()
        params_layout.addLayout(reducer_ratio_layout)
        
        # 创建表格
        self.cycle_actions_table = QTableWidget()
        self.cycle_actions_table.setRowCount(5)
        self.cycle_actions_table.setColumnCount(6)  # 恢复到6列，移除减速比列
        self.cycle_actions_table.setHorizontalHeaderLabels(["位置角度(°)", "最大速度(RPM)", "加速度(RPM/s)", "减速度(RPM/s)", "转动方向", "绝对位置"])
        
        # 设置表格属性
        self.cycle_actions_table.horizontalHeader().setStretchLastSection(True)
        self.cycle_actions_table.setAlternatingRowColors(True)
        
        # 设置表格的最小尺寸
        self.cycle_actions_table.setMinimumHeight(200)
        
        # 调整列宽
        self.cycle_actions_table.setColumnWidth(0, 100)  # 位置角度
        self.cycle_actions_table.setColumnWidth(1, 110)  # 最大速度  
        self.cycle_actions_table.setColumnWidth(2, 110)  # 加速度
        self.cycle_actions_table.setColumnWidth(3, 110)  # 减速度
        self.cycle_actions_table.setColumnWidth(4, 80)   # 转动方向
        
        # 设置行高
        for i in range(5):
            self.cycle_actions_table.setRowHeight(i, 35)  # 增加行高以容纳控件
        
        params_layout.addWidget(self.cycle_actions_table)
        
        # 快速设置按钮
        quick_set_layout = QHBoxLayout()
        quick_set_layout.setSpacing(15)
        
        self.load_cycle_default_btn = QPushButton("加载默认动作")
        self.load_cycle_default_btn.clicked.connect(self.load_cycle_default_actions)
        self.load_cycle_default_btn.setMinimumHeight(35)
        quick_set_layout.addWidget(self.load_cycle_default_btn)
        
        self.save_cycle_actions_btn = QPushButton("保存当前动作")
        self.save_cycle_actions_btn.clicked.connect(self.save_cycle_current_actions)
        self.save_cycle_actions_btn.setMinimumHeight(35)
        quick_set_layout.addWidget(self.save_cycle_actions_btn)
        
        quick_set_layout.addStretch()
        params_layout.addLayout(quick_set_layout)
        
        scroll_layout.addWidget(params_group)
        
        # 循环控制组
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
        
        self.start_multi_cycle_btn = QPushButton("开始循环运动")
        self.start_multi_cycle_btn.setProperty("class", "success")
        self.start_multi_cycle_btn.clicked.connect(self.start_multi_cycle_motion)
        self.start_multi_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.start_multi_cycle_btn)
        
        self.stop_multi_cycle_btn = QPushButton("停止循环")
        self.stop_multi_cycle_btn.setProperty("class", "warning")
        self.stop_multi_cycle_btn.clicked.connect(self.stop_multi_cycle_motion)
        self.stop_multi_cycle_btn.setEnabled(False)
        self.stop_multi_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.stop_multi_cycle_btn)
        
        self.emergency_stop_multi_cycle_btn = QPushButton("紧急停止")
        self.emergency_stop_multi_cycle_btn.setProperty("class", "danger")
        self.emergency_stop_multi_cycle_btn.clicked.connect(self.emergency_stop_multi_cycle)
        self.emergency_stop_multi_cycle_btn.setMinimumHeight(40)
        control_buttons_layout.addWidget(self.emergency_stop_multi_cycle_btn)
        
        control_buttons_layout.addStretch()
        cycle_control_layout.addLayout(control_buttons_layout)
        
        # 状态显示
        status_layout = QHBoxLayout()
        status_layout.setSpacing(20)
        
        status_layout.addWidget(QLabel("循环状态:"))
        
        self.multi_cycle_status_label = QLabel("已停止")
        self.multi_cycle_status_label.setProperty("class", "status-disconnected")
        status_layout.addWidget(self.multi_cycle_status_label)
        
        status_layout.addWidget(QLabel("当前动作:"))
        
        self.multi_current_action_label = QLabel("无")
        status_layout.addWidget(self.multi_current_action_label)
        
        status_layout.addStretch()
        cycle_control_layout.addLayout(status_layout)
        
        scroll_layout.addWidget(cycle_control_group)
        
        # 添加底部空间，确保最后的内容不会被遮挡
        scroll_layout.addSpacing(20)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # 初始化数据结构
        self.cycle_actions_dict = {}  # 电机ID -> 动作参数列表的字典
        self.cycling_motors = set()  # 正在循环运动的电机ID集合
        self.motor_current_action_index = {}  # 电机ID -> 当前动作索引的字典
        self.motor_action_start_time = {}  # 电机ID -> 动作开始时间的字典
        self.multi_cycle_timer = QTimer()
        self.multi_cycle_timer.timeout.connect(self.execute_next_multi_cycle_action)
        
        return widget
    
    # def create_arm_validation_tab(self):
    #     """创建机械臂验证标签页"""
    #     widget = QWidget()

    def apply_motor_reducer_ratio(self):
        """应用当前选中电机的减速比"""
        index = self.cycle_motor_combo.currentIndex()
        if index < 0:
            QMessageBox.warning(self, '警告', '请先选择电机')
            return
            
        motor_id = self.cycle_motor_combo.itemData(index)
        
        try:
            # 获取输入的减速比
            ratio_text = self.cycle_motor_reducer_ratio.text().strip()
            ratio = float(ratio_text)
            
            if ratio <= 0:
                QMessageBox.warning(self, '警告', '减速比必须大于0')
                return
                
            # 更新电机的减速比
            self.motor_reducer_ratios[motor_id] = ratio
            
            # 更新显示
            self.current_motor_reducer_ratio_label.setText(f"当前减速比: {ratio}")
            
            QMessageBox.information(self, '成功', f'已为电机 {motor_id} 设置减速比 {ratio}')
            
        except ValueError:
            QMessageBox.warning(self, '错误', '请输入有效的数字')
        except Exception as e:
            QMessageBox.warning(self, '错误', f'设置减速比失败: {str(e)}')

    def _apply_drive_version_homing_modes_for_multi(self):
        """根据已连接电机的驱动板版本(X/Y)调整多电机回零模式下拉框项。
        若版本混合，则采用交集（X版四项）。"""
        try:
            if not self.motors:
                return
            versions = set()
            for m in self.motors.values():
                versions.add(str(getattr(m, 'drive_version', 'Y')).upper())
            # Y版全量，X版精简；若混合，使用X版精简集合
            y_modes = [
                "就近回零",
                "方向回零",
                "无限位碰撞回零",
                "限位回零",
                "回到绝对位置坐标零点",
                "回到上次掉电位置角度",
            ]
            x_modes = [
                "就近回零",
                "方向回零",
                "无限位碰撞回零",
                "限位回零",
            ]
            modes = y_modes if versions == {"Y"} else x_modes
            
            # 记录并重置同步回零下拉
            prev_sync_idx = self.sync_homing_mode.currentIndex() if hasattr(self, 'sync_homing_mode') else 0
            if hasattr(self, 'sync_homing_mode') and self.sync_homing_mode:
                self.sync_homing_mode.blockSignals(True)
                self.sync_homing_mode.clear()
                self.sync_homing_mode.addItems(modes)
                self.sync_homing_mode.setCurrentIndex(prev_sync_idx if 0 <= prev_sync_idx < len(modes) else 0)
                self.sync_homing_mode.blockSignals(False)
            
            # 记录并重置回零参数 Tab 的模式下拉
            prev_param_idx = self.multi_homing_param_mode_combo.currentIndex() if hasattr(self, 'multi_homing_param_mode_combo') else 0
            if hasattr(self, 'multi_homing_param_mode_combo') and self.multi_homing_param_mode_combo:
                self.multi_homing_param_mode_combo.blockSignals(True)
                self.multi_homing_param_mode_combo.clear()
                self.multi_homing_param_mode_combo.addItems(modes)
                self.multi_homing_param_mode_combo.setCurrentIndex(prev_param_idx if 0 <= prev_param_idx < len(modes) else 0)
                self.multi_homing_param_mode_combo.blockSignals(False)
            
            # 新增：记录并重置基础批量操作的回零模式下拉
            prev_batch_idx = self.batch_homing_mode_combo.currentIndex() if hasattr(self, 'batch_homing_mode_combo') else 0
            if hasattr(self, 'batch_homing_mode_combo') and self.batch_homing_mode_combo:
                self.batch_homing_mode_combo.blockSignals(True)
                self.batch_homing_mode_combo.clear()
                self.batch_homing_mode_combo.addItems(modes)
                self.batch_homing_mode_combo.setCurrentIndex(prev_batch_idx if 0 <= prev_batch_idx < len(modes) else 0)
                self.batch_homing_mode_combo.blockSignals(False)
        except Exception:
            pass
    
    def _is_y_board(self):
        # 判断是否全为Y板（或至少有Y板以启用Y42按钮）
        versions = set()
        for m in self.motors.values():
            versions.add(str(getattr(m, 'drive_version', 'Y')).upper())
        return versions == {"Y"}
    
    def _build_single_command_for_y42(self, motor_id, function_body):
        # function_body 已是 功能码+参数+6B
        try:
            # 通过SDK构建"地址+功能码+参数+6B"
            from Control_SDK.Control_Core import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, function_body)
        except Exception:
            # 兜底：直接前置地址
            return [motor_id] + function_body
    
    def start_y42_position_motion(self):
        """Y42一次性下发：直通位置模式"""
        if not self._is_y_board():
            QMessageBox.warning(self, '提示', '该功能仅支持Y版驱动板')
            return
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        # 解析位置值
        positions = self.parse_motor_values(self.sync_positions_edit.text(), self.sync_position_speed.value())
        if not positions:
            return
        try:
            speed = self.sync_position_speed.value()
            direction = self.sync_position_direction.currentText()
            is_absolute = self.sync_position_absolute.isChecked()
            commands = []
            for motor_id, motor in selected_motors:
                if motor_id not in positions:
                    continue
                input_position = positions[motor_id]
                actual_position = self.get_actual_angle(input_position, motor_id)
                if direction == "CCW" and not is_absolute:
                    actual_position = -actual_position
                # 构建单机直通位置功能体
                func = motor.command_builder.position_mode_direct(actual_position, abs(speed), is_absolute, multi_sync=False)
                commands.append(self._build_single_command_for_y42(motor_id, func))
            if not commands:
                return
            # 使用第一个电机实例发送Y42
            first_motor = selected_motors[0][1]
            resp = first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False)
            QMessageBox.information(self, '成功', 'Y42直通位置命令已下发')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'Y42直通位置下发失败:\n{str(e)}')
    
    def start_y42_trapezoid_motion(self):
        """Y42一次性下发：梯形曲线位置模式"""
        if not self._is_y_board():
            QMessageBox.warning(self, '提示', '该功能仅支持Y版驱动板')
            return
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        # 解析位置
        positions = self.parse_motor_values(self.sync_trapezoid_positions_edit.text(), self.sync_trapezoid_max_speed.value())
        if not positions:
            return
        try:
            max_speed = self.sync_trapezoid_max_speed.value()
            direction = self.sync_trapezoid_direction.currentText()
            acceleration = self.sync_trapezoid_acceleration.value()
            deceleration = self.sync_trapezoid_deceleration.value()
            is_absolute = self.sync_trapezoid_absolute.isChecked()
            commands = []
            for motor_id, motor in selected_motors:
                if motor_id not in positions:
                    continue
                input_position = positions[motor_id]
                actual_position = self.get_actual_angle(input_position, motor_id)
                if direction == "CCW" and not is_absolute:
                    actual_position = -actual_position
                func = motor.command_builder.position_mode_trapezoid(
                    position=actual_position,
                    max_speed=max_speed,
                    acceleration=acceleration,
                    deceleration=deceleration,
                    is_absolute=is_absolute,
                    multi_sync=False
                )
                commands.append(self._build_single_command_for_y42(motor_id, func))
            if not commands:
                return
            first_motor = selected_motors[0][1]
            resp = first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False)
            QMessageBox.information(self, '成功', 'Y42梯形曲线命令已下发')
        except Exception as e:
            QMessageBox.warning(self, '失败', f'Y42梯形曲线下发失败:\n{str(e)}')