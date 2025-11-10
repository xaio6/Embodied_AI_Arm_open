# -*- coding: utf-8 -*-
"""
机械臂控制控件
实现6自由度机械臂控制，支持MuJoCo仿真联动
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
                             QScrollArea, QSplitter, QFrame, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor
import numpy as np

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

try:
    from core.mujoco_arm_controller import MuJoCoArmController
    from core.arm_core.interpolation import JointSpaceInterpolator
    from Main_UI.utils.kinematics_factory import create_configured_kinematics
    KINEMATICS_AVAILABLE = True
except ImportError:
    MuJoCoArmController = None
    JointSpaceInterpolator = None
    KINEMATICS_AVAILABLE = False

# 添加电机配置管理器导入
from .motor_config_manager import motor_config_manager

class DigitalTwinWidget(QWidget):
    """机械臂控制控件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        # 使用统一的电机配置管理器
        self.motor_config_manager = motor_config_manager
        self.mujoco_controller = None
        self.status_timer = None  # 状态刷新定时器
        self.mujoco_interpolating = False  # MuJoCo插补状态标志
        self.current_interpolation_thread = None  # 当前插补线程
        self.speed_ratio = 1
        
        # 初始化运动学计算器
        self.kinematics = None
        if KINEMATICS_AVAILABLE:
            try:
                # 使用配置的DH参数初始化运动学计算器
                self.kinematics = create_configured_kinematics()
            except Exception as e:
                print(f"运动学计算器初始化失败: {e}")
                self.kinematics = None
        
        self.init_ui()
        
        # 初始化微调显示（移动到init_ui方法中）
        # 初始化末端位姿显示（移动到init_ui方法中）
    
    def closeEvent(self, event):
        """组件关闭时的清理工作"""
        try:
            
            # 停止状态刷新定时器
            if hasattr(self, 'status_timer') and self.status_timer:
                self.status_timer.stop()
            
            # 停止插补线程
            if hasattr(self, 'current_interpolation_thread') and self.current_interpolation_thread:
                if self.current_interpolation_thread.is_alive():
                    # 设置停止标志
                    self.mujoco_interpolating = False
                    # 给线程一些时间自然结束
                    self.current_interpolation_thread.join(timeout=2.0)
            
            # 停止所有电机运动
            if self.motors:
                try:
                    for motor_id, motor in self.motors.items():
                        motor.control_actions.stop()
                    print("🛑 所有电机运动已停止")
                except Exception as e:
                    print(f"⚠️ 停止电机运动时出错: {e}")
            
            # 清理MuJoCo控制器
            if hasattr(self, 'mujoco_controller') and self.mujoco_controller:
                try:
                    # MuJoCo控制器通常不需要特殊清理，但可以重置状态
                    self.mujoco_controller = None
                except Exception as e:
                    print(f"⚠️ 清理MuJoCo控制器时出错: {e}")
            
            print("✅ 机械臂控件资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 机械臂控件清理资源时发生错误: {e}")
        finally:
            event.accept()
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            # 重新加载配置管理器的配置
            self.motor_config_manager.config = self.motor_config_manager.load_config()
            print("✅ 机械臂控制控件：电机配置已重新加载")
        except Exception as e:
            print(f"⚠ 机械臂控制控件：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            if KINEMATICS_AVAILABLE:
                # 重新创建运动学实例，使用最新的DH参数配置
                self.kinematics = create_configured_kinematics()
                
                # 立即更新界面显示
                self.update_end_effector_pose()
            else:
                print("⚠️ 运动学模块不可用，无法重新加载DH参数配置")
        except Exception as e:
            print(f"⚠ 机械臂控制控件：重新加载DH参数配置失败: {e}")
            self.kinematics = None
    
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(6)
        
        # 创建MuJoCo控制区域（固定在顶部，不滚动）
        self.create_mujoco_control_group(layout)
        
        # 创建标签页切换栏（固定显示，不滚动）
        self.create_tabs(layout)
        
        # 不需要额外的滚动区域，标签页内部自己管理滚动
        
        # 初始化微调显示
        QTimer.singleShot(100, self.update_fine_tune_display)  # 延迟100ms执行，确保界面已创建完成
        
        # 初始化末端位姿显示
        QTimer.singleShot(200, self.update_end_effector_pose)  # 延迟200ms执行，确保界面已创建完成
    
    def create_mujoco_control_group(self, parent_layout):
        """创建MuJoCo控制组"""
        group = QGroupBox("MuJoCo仿真联动控制")
        group.setMaximumHeight(350)  # 设置最大宽度，和减速比设置组件保持一致
        layout = QVBoxLayout(group)
        layout.setSpacing(4)  # 减少间距从6到4
        layout.setContentsMargins(8, 8, 8, 8)  # 设置更小的内边距
        
        # MuJoCo状态显示 - 更紧凑的布局
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("仿真状态:"))
        self.mujoco_status_label = QLabel("未启动")
        self.mujoco_status_label.setProperty("class", "status-disconnected")
        status_layout.addWidget(self.mujoco_status_label)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 隐藏模型文件路径设置，直接在代码中使用默认路径
        # 默认模型文件路径
        self.default_model_path = "config/urdf/mjmodel.xml"
        
        # 控制按钮 - 缩小按钮
        button_layout = QHBoxLayout()
        
        self.start_mujoco_btn = QPushButton("🚀 启动仿真联动")
        self.start_mujoco_btn.setProperty("class", "success")
        self.start_mujoco_btn.clicked.connect(self.start_mujoco)
        self.start_mujoco_btn.setMinimumHeight(30)
        self.start_mujoco_btn.setMaximumWidth(150)
        button_layout.addWidget(self.start_mujoco_btn)
        
        self.stop_mujoco_btn = QPushButton("⏹️ 停止联动")
        self.stop_mujoco_btn.setProperty("class", "danger")
        self.stop_mujoco_btn.clicked.connect(self.stop_mujoco)
        self.stop_mujoco_btn.setEnabled(False)
        self.stop_mujoco_btn.setMinimumHeight(30)
        self.stop_mujoco_btn.setMaximumWidth(120)
        button_layout.addWidget(self.stop_mujoco_btn)
        
        button_layout.addStretch()
        layout.addLayout(button_layout)
        
        parent_layout.addWidget(group)
    
    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()
        
        # 机械臂控制标签页（整合了设置和控制功能）
        self.control_tab = self.create_unified_control_tab()
        self.tab_widget.addTab(self.control_tab, "机械臂控制")
        
        # 状态监控标签页
        self.status_monitor_tab = self.create_status_monitor_tab()
        self.tab_widget.addTab(self.status_monitor_tab, "状态监控")
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_unified_control_tab(self):
        """创建统一的机械臂控制标签页（整合设置和控制功能）"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加滚动区域
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
        
        # 统一的机械臂控制内容
        self.create_unified_control_content(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_unified_control_content(self, layout):
        """创建统一的机械臂控制内容（整合设置和控制功能）"""
        
        # 1. 运动参数设置区域（顶部）
        params_group = QGroupBox("运动参数设置")
        params_layout = QHBoxLayout(params_group)
        params_layout.setSpacing(15)
        
        # 速度设置
        params_layout.addWidget(QLabel("最大速度:"))
        self.max_speed_spin = QSpinBox()
        self.max_speed_spin.setRange(1, 3000)
        self.max_speed_spin.setValue(100)
        self.max_speed_spin.setSuffix(" RPM")
        self.max_speed_spin.setMaximumWidth(110)
        params_layout.addWidget(self.max_speed_spin)
        
        # 加速度设置
        params_layout.addWidget(QLabel("加速度:"))
        self.acceleration_spin = QSpinBox()
        self.acceleration_spin.setRange(1, 10000)
        self.acceleration_spin.setValue(50)
        self.acceleration_spin.setSuffix(" RPM/s")
        self.acceleration_spin.setMaximumWidth(110)
        params_layout.addWidget(self.acceleration_spin)
        
        # 减速度设置
        params_layout.addWidget(QLabel("减速度:"))
        self.deceleration_spin = QSpinBox()
        self.deceleration_spin.setRange(1, 10000)
        self.deceleration_spin.setValue(50)
        self.deceleration_spin.setSuffix(" RPM/s")
        self.deceleration_spin.setMaximumWidth(110)
        params_layout.addWidget(self.deceleration_spin)

        params_layout.addStretch()
        layout.addWidget(params_group)
        
        # 2. 关节角度控制区域（中上部）
        joint_group = QGroupBox("关节角度控制")
        joint_group.setMaximumHeight(200)
        joint_group_layout = QVBoxLayout(joint_group)
        joint_group_layout.setSpacing(6)
        
        # 关节角度输入框 - 水平布局
        joint_layout = QHBoxLayout()
        joint_layout.setSpacing(8)
        
        self.joint_spins = []
        for i in range(6):
            # 垂直布局：标签上方，输入框下方
            joint_container = QVBoxLayout()
            joint_container.setSpacing(2)
            joint_container.setAlignment(Qt.AlignCenter)
            
            label = QLabel(f"关节{i+1}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("font-size: 11px; color: #666;")
            joint_container.addWidget(label)
            
            joint_spin = QDoubleSpinBox()
            joint_spin.setRange(-360, 360)
            joint_spin.setValue(0)
            joint_spin.setSuffix("°")
            joint_spin.setDecimals(1)
            joint_spin.setMaximumWidth(80)
            joint_spin.setAlignment(Qt.AlignCenter)
            # 连接值变化信号，自动更新微调显示和末端位姿显示
            joint_spin.valueChanged.connect(self.update_fine_tune_display)
            joint_spin.valueChanged.connect(self.update_end_effector_pose)
            self.joint_spins.append(joint_spin)
            joint_container.addWidget(joint_spin)
            
            joint_layout.addLayout(joint_container)
        
        joint_layout.addStretch()
        joint_group_layout.addLayout(joint_layout)
        
        # 位置模式选择和运动控制按钮 - 水平布局
        bottom_layout = QHBoxLayout()
        bottom_layout.setSpacing(15)
        
        # 左侧：位置模式选择
        mode_layout = QHBoxLayout()
        mode_layout.setSpacing(8)
        
        self.position_absolute_checkbox = QCheckBox("绝对位置")
        self.position_absolute_checkbox.setChecked(True) 
        self.position_absolute_checkbox.setToolTip("勾选：绝对位置模式，不勾选：相对位置模式")
        mode_layout.addWidget(self.position_absolute_checkbox)
        
        mode_hint = QLabel("提示：如果电机未设置零点，建议使用相对位置模式")
        mode_hint.setStyleSheet("color: #666; font-size: 10px;")
        mode_layout.addWidget(mode_hint)
        
        bottom_layout.addLayout(mode_layout)
        bottom_layout.addStretch()
        
        # 右侧：运动控制按钮
        control_buttons_layout = QHBoxLayout()
        control_buttons_layout.setSpacing(8)
        
        self.move_to_position_btn = QPushButton("📍 移动到位置")
        self.move_to_position_btn.setFixedSize(120, 35)
        self.move_to_position_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.move_to_position_btn.clicked.connect(self.move_to_position)
        self.move_to_position_btn.setEnabled(False)
        control_buttons_layout.addWidget(self.move_to_position_btn)
        
        self.home_position_btn = QPushButton("🏠 回零位")
        self.home_position_btn.setFixedSize(100, 35)
        self.home_position_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #ef6c00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.home_position_btn.clicked.connect(self.go_home)
        self.home_position_btn.setEnabled(False)
        control_buttons_layout.addWidget(self.home_position_btn)
        
        self.stop_motion_btn = QPushButton("⏹️ 停止")
        self.stop_motion_btn.setFixedSize(80, 35)
        self.stop_motion_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.stop_motion_btn.clicked.connect(self.stop_motion)
        self.stop_motion_btn.setEnabled(False)
        control_buttons_layout.addWidget(self.stop_motion_btn)
        
        bottom_layout.addLayout(control_buttons_layout)
        joint_group_layout.addLayout(bottom_layout)
        
        layout.addWidget(joint_group)
        
        # 3. 创建水平布局容器，左边是关节微调控制，右边是末端位姿显示
        control_pose_layout = QHBoxLayout()
        control_pose_layout.setSpacing(15)
        
        # 关节微调控制（左侧）
        fine_tune_group = QGroupBox("关节微调控制")
        fine_tune_group.setMaximumHeight(400)
        fine_tune_group.setMinimumWidth(480)
        fine_tune_group_layout = QVBoxLayout(fine_tune_group)
        fine_tune_group_layout.setSpacing(10)
        
        # 添加说明文字
        info_label2 = QLabel("🎯  点击绿色+ 或 红色- 按钮对单个关节进行 ±1° 微调，立即执行")
        info_label2.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label2.setWordWrap(True)
        fine_tune_group_layout.addWidget(info_label2)
        
        # 使用简单的垂直布局：第一行3个关节，第二行3个关节
        # 第一行（关节1-3）
        first_row = QHBoxLayout()
        first_row.setSpacing(15)
        
        # 第二行（关节4-6）
        second_row = QHBoxLayout()
        second_row.setSpacing(15)
        
        # 初始化微调控件
        self.fine_tune_labels = []  # 当前角度显示标签
        self.fine_tune_minus_btns = []  # 减号按钮
        self.fine_tune_plus_btns = []   # 加号按钮
        
        for i in range(6):
            # 创建每个关节的控制组
            joint_widget = QWidget()
            joint_widget.setFixedSize(140, 80)
            joint_layout = QVBoxLayout(joint_widget)
            joint_layout.setSpacing(5)
            joint_layout.setContentsMargins(5, 5, 5, 5)
            
            # 关节标题
            title_label = QLabel(f"关节{i+1}")
            title_label.setAlignment(Qt.AlignCenter)
            title_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
            joint_layout.addWidget(title_label)
            
            # 当前角度显示
            angle_label = QLabel("0.0°")
            angle_label.setAlignment(Qt.AlignCenter)
            angle_label.setFixedHeight(22)
            angle_label.setStyleSheet("""
                background-color: #e3f2fd; 
                color: #1976d2; 
                font-weight: bold; 
                font-size: 12px;
                border: 1px solid #bbdefb;
                border-radius: 3px;
                padding: 2px;
            """)
            self.fine_tune_labels.append(angle_label)
            joint_layout.addWidget(angle_label)
            
            # 按钮区域
            button_layout = QHBoxLayout()
            button_layout.setSpacing(5)
            
            # 减号按钮
            minus_btn = QPushButton("−")
            minus_btn.setFixedSize(35, 25)
            minus_btn.setStyleSheet("""
                QPushButton {
                    background-color: #f44336;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #d32f2f;
                }
                QPushButton:pressed {
                    background-color: #b71c1c;
                }
            """)
            minus_btn.clicked.connect(lambda checked, joint_id=i: self.fine_tune_joint(joint_id, -1))
            self.fine_tune_minus_btns.append(minus_btn)
            button_layout.addWidget(minus_btn)
            
            # 加号按钮
            plus_btn = QPushButton("+")
            plus_btn.setFixedSize(35, 25)
            plus_btn.setStyleSheet("""
                QPushButton {
                    background-color: #4caf50;
                    color: white;
                    border: none;
                    border-radius: 4px;
                    font-weight: bold;
                    font-size: 14px;
                }
                QPushButton:hover {
                    background-color: #388e3c;
                }
                QPushButton:pressed {
                    background-color: #2e7d32;
                }
            """)
            plus_btn.clicked.connect(lambda checked, joint_id=i: self.fine_tune_joint(joint_id, 1))
            self.fine_tune_plus_btns.append(plus_btn)
            button_layout.addWidget(plus_btn)
            
            joint_layout.addLayout(button_layout)
            
            # 添加到对应的行
            if i < 3:
                first_row.addWidget(joint_widget)
            else:
                second_row.addWidget(joint_widget)
        
        # 添加弹性空间
        first_row.addStretch()
        second_row.addStretch()
        
        # 将两行添加到主布局
        fine_tune_group_layout.addLayout(first_row)
        fine_tune_group_layout.addLayout(second_row)
        
        # 微调选项
        options_layout = QHBoxLayout()
        options_layout.setContentsMargins(10, 5, 10, 5)
        
        # 自动同步MuJoCo选项
        self.auto_sync_mujoco_checkbox = QCheckBox("同步更新MuJoCo仿真")
        self.auto_sync_mujoco_checkbox.setChecked(True)
        self.auto_sync_mujoco_checkbox.setToolTip("微调时自动更新MuJoCo仿真显示")
        options_layout.addWidget(self.auto_sync_mujoco_checkbox)
        
        # 添加间距
        options_layout.addSpacing(20)
        
        # 刷新状态按钮
        self.refresh_position_btn = QPushButton("🔄 刷新状态")
        self.refresh_position_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #546E7A;
            }
            QPushButton:pressed {
                background-color: #455A64;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.refresh_position_btn.clicked.connect(self.refresh_position_and_pose)
        self.refresh_position_btn.setEnabled(False)
        self.refresh_position_btn.setMaximumWidth(100)
        self.refresh_position_btn.setToolTip("刷新关节角度和末端位姿显示")
        options_layout.addWidget(self.refresh_position_btn)
        
        # 添加间距
        options_layout.addSpacing(15)
        
        # 设置当前为零位按钮
        self.clear_position_btn = QPushButton("🔄 设置当前为零位")
        self.clear_position_btn.setStyleSheet("""
            QPushButton {
                background-color: #ff9800;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 11px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #f57c00;
            }
            QPushButton:pressed {
                background-color: #ef6c00;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.clear_position_btn.clicked.connect(self.clear_all_positions)
        self.clear_position_btn.setEnabled(False)
        self.clear_position_btn.setMaximumWidth(130)
        self.clear_position_btn.setToolTip("微调完成后，将当前位置设为电机零位参考点")
        options_layout.addWidget(self.clear_position_btn)
        
        options_layout.addStretch()
        fine_tune_group_layout.addLayout(options_layout)
        
        # 末端位姿显示（右侧）
        end_effector_group = QGroupBox("机械臂末端位姿")
        end_effector_group.setMaximumHeight(400)
        end_effector_group.setMinimumWidth(480)
        end_effector_group_layout = QVBoxLayout(end_effector_group)
        end_effector_group_layout.setSpacing(10)
        
        # 添加说明文字
        info_label = QLabel("🎯  实时显示机械臂末端执行器位姿")
        info_label.setMaximumHeight(20)
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        end_effector_group_layout.addWidget(info_label)
        
        # 创建末端位姿表格
        self.pose_table = QTableWidget()
        self.pose_table.setRowCount(2)  # 2行：位置和姿态
        self.pose_table.setColumnCount(4)  # 4列：Z/Yaw、Y/Pitch、X/Roll、单位
        self.pose_table.setHorizontalHeaderLabels(["Z/Yaw", "Y/Pitch", "X/Roll", "单位"])
        self.pose_table.setVerticalHeaderLabels(["位置", "姿态"])
        self.pose_table.verticalHeader().setVisible(True)
        self.pose_table.setMaximumHeight(140)  # 设置表格高度
        self.pose_table.setMinimumHeight(100)
        
        # 设置表格属性
        self.pose_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)  # 均匀拉伸所有列
        self.pose_table.setEditTriggers(QTableWidget.NoEditTriggers)  # 禁止编辑
        self.pose_table.setSelectionMode(QTableWidget.NoSelection)  # 禁用选择
        
        # 初始化表格内容
        self.init_pose_table()
        
        end_effector_group_layout.addWidget(self.pose_table)
        
        # 将微调控制和位姿显示添加到水平布局
        control_pose_layout.addWidget(fine_tune_group)
        control_pose_layout.addWidget(end_effector_group)
        
        layout.addLayout(control_pose_layout)
        

        
        # 关节角度控件创建完成后，触发初始的末端位姿计算
        QTimer.singleShot(50, self.update_end_effector_pose)
    

    
    def init_pose_table(self):
        """初始化末端位姿表格"""
        # 第一行：位置
        self.pose_table.setItem(0, 0, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 1, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 2, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 3, QTableWidgetItem("mm")) # 单位列
        
        # 第二行：姿态
        self.pose_table.setItem(1, 0, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 1, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 2, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 3, QTableWidgetItem("°")) # 单位列
        
        # 设置表格样式
        self.pose_table.setAlternatingRowColors(True)
        self.pose_table.resizeRowsToContents()
        
        # 设置文本居中对齐
        for row in range(2):
            for col in range(4):
                item = self.pose_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
    
    def create_status_monitor_tab(self):
        """创建状态监控标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        
        # 添加滚动区域
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
        
        # 状态监控内容
        self.create_status_monitor_content(scroll_layout)
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
        
        return widget
    
    def create_status_monitor_content(self, layout):
        """创建状态监控内容"""
        # 状态监控标题
        status_title = QLabel("📊 实时状态监控")
        status_title.setStyleSheet("font-weight: bold; font-size: 14px; color: #2c3e50; margin-bottom: 5px;")
        layout.addWidget(status_title)
        
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
        self.refresh_rate_spin.setRange(1, 50)
        self.refresh_rate_spin.setValue(5)  # 默认5Hz
        self.refresh_rate_spin.setSuffix(" Hz")
        self.refresh_rate_spin.setMaximumWidth(80)
        control_layout.addWidget(self.refresh_rate_spin)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 状态表格
        self.status_table = QTableWidget()
        self.setup_status_table()
        layout.addWidget(self.status_table)
        
        # 初始化自动刷新定时器
        self.status_timer = QTimer()
        self.status_timer.timeout.connect(self.refresh_status)
    
    def setup_status_table(self):
        """设置状态表格"""
        headers = ["电机ID", "使能", "到位", "位置(°-输出端)", "速度(RPM)", "电压(V)", "电流(A)", "温度(°C)"]
        
        self.status_table.setColumnCount(len(headers))
        self.status_table.setHorizontalHeaderLabels(headers)
        self.status_table.horizontalHeader().setStretchLastSection(True)
        self.status_table.verticalHeader().setVisible(False)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.setAlternatingRowColors(True)
        
        # 去掉表格高度限制，让它自由调整
        # self.status_table.setMaximumHeight(200)
        # self.status_table.setMinimumHeight(150)
        
        # 初始化6行数据
        self.status_table.setRowCount(6)
        for i in range(6):
            motor_id = i + 1
            self.status_table.setItem(i, 0, QTableWidgetItem(str(motor_id)))
            self.status_table.setItem(i, 1, QTableWidgetItem("未知"))
            self.status_table.setItem(i, 2, QTableWidgetItem("未知"))
            self.status_table.setItem(i, 3, QTableWidgetItem("--"))
            self.status_table.setItem(i, 4, QTableWidgetItem("--"))
            self.status_table.setItem(i, 5, QTableWidgetItem("--"))
            self.status_table.setItem(i, 6, QTableWidgetItem("--"))
            self.status_table.setItem(i, 7, QTableWidgetItem("--"))
        
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
        
        if not self.motors:
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
                        # 读取状态信息 - 参考多电机的方法
                        motor_status = motor.read_parameters.get_motor_status()
                      
                        position = motor.read_parameters.get_position()
                        speed = motor.read_parameters.get_speed()  # 使用get_speed而不是get_velocity
                        voltage = motor.read_parameters.get_bus_voltage()
                        current = motor.read_parameters.get_current()  # 使用get_current而不是get_bus_current
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
            
        except Exception as e:
            from PyQt5.QtWidgets import QMessageBox
            QMessageBox.warning(self, '读取失败', f'刷新状态失败:\n{str(e)}')
    
    def start_mujoco(self):
        """启动MuJoCo仿真"""
        try:
            if MuJoCoArmController is None:
                # QMessageBox.warning(self, "错误", "MuJoCo控制器模块未找到，请检查core目录")
                QMessageBox.information(self, "提示", "该版本暂不支持此功能")
                return
            
            # 使用默认模型文件路径
            full_path = self.default_model_path
            
            # 检查模型文件是否存在
            if not os.path.exists(full_path):
                QMessageBox.warning(self, "错误", f"模型文件不存在: {full_path}")
                return
            
            # 启动MuJoCo仿真
            self.mujoco_controller = MuJoCoArmController(model_path=full_path, enable_viewer=True)
            self.mujoco_controller.start_viewer()
            
            # 更新仿真状态
            self.mujoco_status_label.setText("运行中")
            self.mujoco_status_label.setProperty("class", "status-connected")
            self.start_mujoco_btn.setEnabled(False)
            self.stop_mujoco_btn.setEnabled(True)
            # 运动控制按钮的启用状态由电机连接状态决定，不在这里设置
            
            QMessageBox.information(self, "成功", "MuJoCo仿真联动已启动！\n可以通过机械臂控制功能控制仿真。")
            
        except Exception as e:
            # QMessageBox.critical(self, "错误", f"启动MuJoCo仿真联动失败: {str(e)}")
            QMessageBox.information(self, "提示", "该版本暂不支持此功能")
    
    def stop_mujoco(self):
        """停止MuJoCo仿真"""
        try:
            # 停止MuJoCo仿真
            if self.mujoco_controller:
                self.mujoco_controller.stop_viewer()
                self.mujoco_controller = None
            
            # 更新状态
            self.mujoco_status_label.setText("已停止")
            self.mujoco_status_label.setProperty("class", "status-disconnected")
            
            self.start_mujoco_btn.setEnabled(True)
            self.stop_mujoco_btn.setEnabled(False)
            # 运动控制按钮的启用状态由电机连接状态决定，不在这里设置
            
            QMessageBox.information(self, "成功", "MuJoCo仿真联动已停止")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止MuJoCo仿真联动失败: {str(e)}")
    
    def get_selected_motor_objects(self):
        """获取所有连接的电机对象（机械臂控制默认使用所有电机）"""
        if not self.motors:
            QMessageBox.warning(self, '警告', '请先连接电机')
            return []
        
        return [(motor_id, self.motors[motor_id]) for motor_id in sorted(self.motors.keys())[:6]]
    
    def parse_motor_values(self, values_list, default_value):
        """解析电机值列表"""
        motor_values = {}
        # 关键修正：按照电机ID→对应关节索引(motor_id-1)取值
        for motor_id in sorted(self.motors.keys())[:6]:
            idx = motor_id - 1
            if 0 <= idx < len(values_list):
                motor_values[motor_id] = values_list[idx]
            else:
                motor_values[motor_id] = default_value
        return motor_values
    
    def get_actual_angle(self, input_angle, motor_id=None):
        """根据减速比和方向设置计算实际发送给电机的角度"""
        # 获取对应电机的减速比和方向
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
        direction = self.motor_config_manager.get_motor_direction(motor_id)
        
        # 机械臂控制中用户输入的总是输出端角度，需要乘以减速比得到电机端角度
        # 然后应用方向修正：正向=1，反向=-1
        motor_angle = input_angle * reducer_ratio * direction
        
        return motor_angle

    def _is_y_board(self):
        """判断是否全为Y版驱动板"""
        if not self.motors:
            return False
        versions = set()
        for m in self.motors.values():
            # 默认按X处理，只有显式标记为Y才计入Y
            versions.add(str(getattr(m, 'drive_version', 'X')).upper())
        return versions == {"Y"}

    def _build_single_command_for_y42(self, motor_id, function_body):
        """将 功能体(功能码+参数+6B) 前置地址，构造单条Y42子命令"""
        try:
            from Control_SDK.Control_Core import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, function_body)
        except Exception:
            return [motor_id] + function_body

    def move_to_position(self):
        """移动到指定位置"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接电机")
            return
        
        # 获取选中的电机（机械臂控制使用所有连接的电机）
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            # 获取目标关节角度
            target_angles = [spin.value() for spin in self.joint_spins]
            
            # 解析位置值
            positions = self.parse_motor_values(target_angles, 0.0)
            
            if not positions:
                return
            
            # 获取运动参数
            max_speed = self.max_speed_spin.value()
            acceleration = self.acceleration_spin.value()
            deceleration = self.deceleration_spin.value()
            is_absolute = self.position_absolute_checkbox.isChecked()

            # Y板：使用多电机命令一次性下发（梯形位置FD）
            if self._is_y_board():
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
                if not commands:
                    QMessageBox.warning(self, "失败", "没有有效的关节目标角度")
                    return
                first_motor = selected_motors[0][1]
                first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                # MuJoCo插补
                if self.mujoco_controller:
                    try:
                        self._execute_mujoco_interpolation(target_angles, max_speed, acceleration)
                        mode_text = "绝对位置" if is_absolute else "相对位置"
                        QMessageBox.information(self, "成功", f"多电机命令已下发（{mode_text}），并同步更新仿真")
                    except Exception as sim_error:
                        mode_text = "绝对位置" if is_absolute else "相对位置"
                        QMessageBox.information(self, "部分成功", f"多电机命令已下发（{mode_text}），但仿真更新失败:\n{str(sim_error)}")
                else:
                    mode_text = "绝对位置" if is_absolute else "相对位置"
                    QMessageBox.information(self, "成功", f"多电机命令已下发（{mode_text}）")
                return
             
            # X板：多机同步标志 + 广播同步
            # 第一阶段：发送带同步标志的位置命令
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
                            multi_sync=True  # 同步标志
                        )
                        success_count += 1
                        
                    except Exception as motor_error:
                        QMessageBox.warning(self, "警告", f"电机 {motor_id} 设置失败:\n{str(motor_error)}")
                        continue
             
            if success_count == 0:
                QMessageBox.warning(self, "失败", "没有电机成功设置运动参数")
                return
             
            # 第二阶段：发送同步运动命令
            # 使用第一个电机发送广播同步命令
            if selected_motors:
                first_motor = selected_motors[0][1]
                # 创建广播控制器（ID=0）
                try:
                    # 尝试使用interface_kwargs属性
                    interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                    broadcast_motor = first_motor.__class__(
                        motor_id=0,
                        interface_type=first_motor.interface_type,
                        shared_interface=True,
                        **interface_kwargs
                    )
                except Exception:
                    # 如果失败，使用基本参数
                    broadcast_motor = first_motor.__class__(
                        motor_id=0,
                        interface_type=first_motor.interface_type,
                        shared_interface=True
                    )
                 
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
             
            # 如果MuJoCo仿真已启动，同时更新仿真
            if self.mujoco_controller:
                try:
                    # 使用关节空间插补算法进行平滑运动
                    self._execute_mujoco_interpolation(target_angles, max_speed, acceleration)
                    mode_text = "绝对位置" if is_absolute else "相对位置"
                    QMessageBox.information(self, "成功", f"成功启动 {success_count}/{len(selected_motors)} 个电机的同步梯形曲线运动（{mode_text}），并同步更新仿真")
                except Exception as sim_error:
                    mode_text = "绝对位置" if is_absolute else "相对位置"
                    QMessageBox.information(self, "部分成功", f"成功启动 {success_count}/{len(selected_motors)} 个电机的同步梯形曲线运动（{mode_text}），但仿真更新失败:\n{str(sim_error)}")
            else:
                mode_text = "绝对位置" if is_absolute else "相对位置"
                QMessageBox.information(self, "成功", f"成功启动 {success_count}/{len(selected_motors)} 个电机的同步梯形曲线运动（{mode_text}）")
                 
        except Exception as e:
            QMessageBox.warning(self, "失败", f"同步梯形曲线运动失败:\n{str(e)}")
    
    def _execute_mujoco_interpolation(self, target_angles, max_speed, acceleration):
        """
        使用关节空间插补算法让MuJoCo平滑运动到目标角度
        
        Args:
            target_angles: 目标关节角度列表（度）
            max_speed: 最大速度 (RPM)
            acceleration: 加速度 (RPM/s)
        """
        if not self.mujoco_controller or not JointSpaceInterpolator:
            # 如果没有MuJoCo控制器或插补算法，直接设置角度
            if self.mujoco_controller:
                self.mujoco_controller.set_joint_angles(target_angles)
            return
        
        # 如果当前正在插补，先停止
        if self.mujoco_interpolating:
            print("⚠ 停止当前MuJoCo插补，开始新的插补")
            self.mujoco_interpolating = False
            if self.current_interpolation_thread and self.current_interpolation_thread.is_alive():
                # 等待当前线程结束（最多等待0.5秒）
                self.current_interpolation_thread.join(timeout=0.5)
            
        try:
            # 获取当前MuJoCo的关节角度作为起点
            current_angles = self.mujoco_controller.get_joint_angles()
            
            # 检查是否已经在目标位置（避免不必要的插补）
            angle_diff = np.array(target_angles) - np.array(current_angles)
            if np.max(np.abs(angle_diff)) < 0.1:  # 如果差异小于0.1度
                print("✅ MuJoCo已在目标位置附近，无需插补")
                return
            
            speed_ratio = self.speed_ratio
            
            # 考虑减速比的实际输出端速度计算
            # 真实机械臂的电机RPM需要除以减速比得到输出端角速度
            effective_speeds = []
            effective_accelerations = []
            
            for i in range(6):
                motor_id = i + 1
                reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)  # 默认16:1减速比
                
                # 输出端角速度 = 电机RPM / 减速比 * 360度/60秒 
                output_speed_deg_per_sec = (max_speed / reducer_ratio * 360) / 60
                output_acc_deg_per_sec2 = (acceleration / reducer_ratio * 360) / 60
                
                
                mujoco_speed = output_speed_deg_per_sec / speed_ratio
                mujoco_acc = output_acc_deg_per_sec2 / speed_ratio
                
                effective_speeds.append(mujoco_speed)
                effective_accelerations.append(mujoco_acc)
            
            # 创建路径点：起点 -> 终点
            waypoints = [
                np.array(current_angles),
                np.array(target_angles)
            ]
            
            # 设置每个关节的速度和加速度限制
            max_velocity = np.array(effective_speeds)
            max_acceleration = np.array(effective_accelerations)
            
            # 为了更真实的运动，我们手动计算更合理的时间
            # 基于最大角度变化和平均速度估算时间
            max_angle_change = np.max(np.abs(angle_diff))
            avg_speed = np.mean(effective_speeds)
            
            # 估算基础运动时间 (考虑加速和减速阶段)
            if avg_speed > 0:
                # 简化的梯形速度计算：假设1/3时间加速，1/3匀速，1/3减速
                estimated_time = max_angle_change / (avg_speed * 0.7)  # 0.7是考虑加减速的效率系数
                # 确保最小时间，避免过快运动
                estimated_time = max(estimated_time, 1.0)  # 最少1秒
            else:
                estimated_time = 2.0
            
            # 创建关节空间插补器
            interpolator = JointSpaceInterpolator()
            
            # 规划轨迹
            success = interpolator.plan_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocity,
                max_acceleration=max_acceleration
            )
            
            if not success:
                print("⚠ 关节空间轨迹规划失败，使用直接设置角度")
                self.mujoco_controller.set_joint_angles(target_angles)
                return
            
            print(f"✅ MuJoCo关节空间插补轨迹规划成功")
            print(f"📊 角度变化: {[f'{diff:.1f}°' for diff in angle_diff]}")
            print(f"⏱️ 运动时长: {interpolator.duration:.2f}秒")
            print(f"🔧 输出端速度: {np.mean([s*speed_ratio for s in effective_speeds]):.1f}°/s (80%调速)")
            print(f"⚙️ 减速比配置: {[self.motor_config_manager.get_motor_reducer_ratio(i+1) for i in range(6)]}")
            print(f"🔄 方向配置: {[('正向' if self.motor_config_manager.get_motor_direction(i+1) == 1 else '反向') for i in range(6)]}")
            
            # 在后台线程中执行插补轨迹
            self._start_interpolation_thread(interpolator)
            
        except Exception as e:
            print(f"❌ MuJoCo插补执行失败: {e}")
            # 失败时回退到直接设置角度
            self.mujoco_controller.set_joint_angles(target_angles)
    
    def _start_interpolation_thread(self, interpolator):
        """
        在后台线程中执行插补轨迹
        
        Args:
            interpolator: 关节空间插补器
        """
        def interpolation_worker():
            try:
                self.mujoco_interpolating = True
                # 降低控制频率，让运动看起来更自然 (25Hz)
                dt = 0.04  # 25Hz控制频率，比50Hz更接近真实机械臂的控制频率
                total_time = interpolator.duration
                t = 0.0
                
                print("🎬 开始执行MuJoCo关节空间插补...")
                print("💡 可以在MuJoCo查看器中观察平滑的轨迹运动")
                print(f"🕐 预计运行时间: {total_time:.2f}秒")
                
                last_progress_print = 0
                
                while t <= total_time and self.mujoco_interpolating:
                    # 获取当前时刻的关节状态
                    positions, velocities, accelerations = interpolator.get_joint_states(t)
                    
                    # 更新MuJoCo显示
                    if self.mujoco_controller:
                        self.mujoco_controller.set_joint_angles(positions.tolist())
                    
                    # 显示进度 (每25%显示一次)
                    progress = (t / total_time) * 100
                    if progress - last_progress_print >= 25:
                        print(f"📈 插补进度: {progress:.0f}%")
                        last_progress_print = progress
                    
                    # 控制时间间隔
                    time.sleep(dt)
                    t += dt
                
                if self.mujoco_interpolating:
                    print("✅ MuJoCo关节空间插补执行完成")
                    print("🎯 已到达目标位置")
                else:
                    print("⚠ MuJoCo插补被中断")
                
                self.mujoco_interpolating = False
                
            except Exception as e:
                print(f"❌ MuJoCo插补线程执行失败: {e}")
                self.mujoco_interpolating = False
        
        # 创建并启动后台线程
        self.current_interpolation_thread = threading.Thread(target=interpolation_worker, daemon=True)
        self.current_interpolation_thread.start()
    
    def go_home(self):
        """回零位"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接电机")
            return
        
        # Y板：使用“回到坐标原点”回零（homing_mode=4），一次性多机下发
        if self._is_y_board():
            try:
                # 优先使用用户选中的电机；若未选中则使用全部已连接电机
                selected_motors = self.get_selected_motor_objects() if hasattr(self, 'get_selected_motor_objects') else []
                if not selected_motors:
                    selected_motors = sorted(self.motors.items(), key=lambda kv: kv[0])
                
                if not selected_motors:
                    QMessageBox.warning(self, "警告", "未发现可用电机")
                    return
                
                success_count = 0
                for motor_id, motor in selected_motors:
                    try:
                        # 逐台触发回零：回到坐标原点（homing_mode=4）
                        motor.control_actions.trigger_homing(homing_mode=4, multi_sync=False)
                        success_count += 1
                    except Exception as e:
                        QMessageBox.warning(self, "警告", f"电机 {motor_id} 回零触发失败:\n{str(e)}")
                        continue
                
                if success_count > 0:
                    QMessageBox.information(self, "回零", f"已触发 Y 板回零（坐标原点，mode=4）：成功 {success_count}/{len(selected_motors)} 台")
                    
                    # Y板回零后，延时更新界面显示（因为回零是异步的）
                    QTimer.singleShot(1000, self.update_display_after_homing)  # 3秒后更新显示
                else:
                    QMessageBox.warning(self, "失败", "未能成功触发任何电机回零")
            except Exception as e:
                QMessageBox.warning(self, "失败", f"触发Y板回零失败:\n{str(e)}")
            return
        
        # X板：设置所有关节角度为0并执行移动
        for spin in self.joint_spins:
            spin.setValue(0.0)
        
        # 执行移动
        self.move_to_position()
        
        # X板移动后立即更新显示（因为X板是同步的）
        QTimer.singleShot(1000, self.update_display_after_homing)  # 1秒后更新显示
    
    def update_display_after_homing(self):
        """回零后更新界面显示"""
        try:
            print("🔄 回零完成，更新界面显示...")
            
            # 1. 将所有关节角度输入框设置为0
            for spin in self.joint_spins:
                spin.setValue(0.0)
            
            # 2. 更新微调显示
            self.update_fine_tune_display()
            
            # 3. 更新末端位姿显示
            self.update_end_effector_pose()
            
            # 4. 如果可能，从电机同步实际状态
            if hasattr(self, 'refresh_position_and_pose'):
                self.refresh_position_and_pose()
            
            print("✅ 回零后界面显示更新完成")
            
        except Exception as e:
            print(f"❌ 回零后更新显示失败: {e}")
            QMessageBox.warning(self, "警告", f"回零后更新显示失败: {str(e)}")
    
    def fine_tune_joint(self, joint_id, direction):
        """
        对指定关节进行微调
        
        Args:
            joint_id: 关节ID（0-5）
            direction: 调整方向（1为+1度，-1为-1度）
        """
        if joint_id < 0 or joint_id >= 6:
            return
            
        try:
            # 1. 获取当前角度值
            current_angle = self.joint_spins[joint_id].value()
            
            # 2. 计算新角度（加上或减去1度）
            new_angle = current_angle + direction
            
            # 3. 检查角度范围限制
            if new_angle < -360 or new_angle > 360:
                QMessageBox.warning(self, "警告", f"关节{joint_id+1}角度超出范围（-360°到360°）")
                return
            
            # 4. 更新界面上的角度输入框
            self.joint_spins[joint_id].setValue(new_angle)
            
            # 5. 更新微调显示
            self.update_fine_tune_display()
            
            # 6. 如果有连接的电机，立即执行微调运动
            if self.motors:
                # 获取运动参数（使用较小的速度进行微调）
                max_speed = min(self.max_speed_spin.value(), 50)  # 限制最大速度为50RPM
                acceleration = self.acceleration_spin.value()
                deceleration = self.deceleration_spin.value()
                
                # Y板：一次性发送所有6个关节的角度
                if self._is_y_board():
                    try:
                        # 获取所有6个关节的当前角度
                        all_angles = [spin.value() for spin in self.joint_spins]
                        
                        # 构建多电机命令
                        commands = []
                        for i in range(6):
                            motor_id = i + 1
                            if motor_id in self.motors:
                                motor = self.motors[motor_id]
                                input_position = all_angles[i]
                                actual_position = self.get_actual_angle(input_position, motor_id)
                                
                                func = motor.command_builder.position_mode_trapezoid(
                                    position=actual_position,
                                    max_speed=max_speed,
                                    acceleration=acceleration,
                                    deceleration=deceleration,
                                    is_absolute=True,
                                    multi_sync=False
                                )
                                commands.append(self._build_single_command_for_y42(motor_id, func))
                        
                        if commands:
                            # 使用第一个电机发送多电机命令
                            first_motor = self.motors[list(self.motors.keys())[0]]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                            
                            direction_text = "正转" if direction > 0 else "反转"
                            print(f"✅ Y板微调：关节{joint_id+1} {direction_text}1° (同时发送所有6个关节角度)")
                            print(f"   📊 关节{joint_id+1}角度: {current_angle:.1f}° → {new_angle:.1f}°")
                            print(f"   🎯 所有关节角度: {[f'{a:.1f}°' for a in all_angles]}")
                        else:
                            QMessageBox.warning(self, "警告", "Y板微调失败：没有有效的电机连接")
                            # 回退角度设置
                            self.joint_spins[joint_id].setValue(current_angle)
                            self.update_fine_tune_display()
                            return
                            
                    except Exception as motor_error:
                        QMessageBox.warning(self, "警告", f"Y板微调失败:\n{str(motor_error)}")
                        # 回退角度设置
                        self.joint_spins[joint_id].setValue(current_angle)
                        self.update_fine_tune_display()
                        return
                
                # X板：保持原有的单关节控制逻辑
                else:
                    motor_id = joint_id + 1  # 电机ID从1开始
                    if motor_id in self.motors:
                        try:
                            # 计算实际电机角度（考虑减速比和方向）
                            actual_angle = self.get_actual_angle(new_angle, motor_id)
                            
                            # 获取减速比和方向信息用于显示
                            reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                            direction_flag = self.motor_config_manager.get_motor_direction(motor_id)
                            direction_name = "正向" if direction_flag == 1 else "反向"
                            
                            # 发送位置命令到电机
                            motor = self.motors[motor_id]
                            motor.control_actions.move_to_position_trapezoid(
                                position=actual_angle,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=True,
                                multi_sync=False  # 单关节微调不使用同步模式
                            )
                            
                            direction_text = "正转" if direction > 0 else "反转"
                            print(f"✅ X板微调：关节{joint_id+1} {direction_text}1° 微调执行成功")
                            print(f"   📊 输出端角度: {current_angle:.1f}° → {new_angle:.1f}°")
                            print(f"   ⚙️ 减速比: {reducer_ratio}:1, 方向: {direction_name}")
                            print(f"   🔧 实际电机角度: {actual_angle:.1f}° (已应用减速比和方向修正)")
                            
                        except Exception as motor_error:
                            QMessageBox.warning(self, "警告", f"关节{joint_id+1}微调失败:\n{str(motor_error)}")
                            # 回退角度设置
                            self.joint_spins[joint_id].setValue(current_angle)
                            self.update_fine_tune_display()
                            return
            
            # 7. 如果启用了MuJoCo同步且仿真已启动，同步更新仿真
            if (self.auto_sync_mujoco_checkbox.isChecked() and 
                hasattr(self, 'mujoco_controller') and 
                self.mujoco_controller):
                try:
                    # 获取所有关节的当前角度
                    all_angles = [spin.value() for spin in self.joint_spins]
                    
                    # 直接设置MuJoCo角度（微调不需要插值）
                    self.mujoco_controller.set_joint_angles(all_angles)
                    
                except Exception as sim_error:
                    print(f"⚠ MuJoCo仿真同步失败: {sim_error}")
            
            direction_text = "+" if direction > 0 else ""
            # 使用print输出状态信息，因为组件没有状态栏
            print(f"关节{joint_id+1} 微调 {direction_text}{direction}° ({current_angle:.1f}° → {new_angle:.1f}°)")
            
            # 8. 更新末端位姿显示
            self.update_end_effector_pose()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"关节微调失败:\n{str(e)}")
    
    def update_fine_tune_display(self):
        """更新微调控制界面的角度显示"""
        try:
            if hasattr(self, 'fine_tune_labels') and self.fine_tune_labels:
                for i, label in enumerate(self.fine_tune_labels):
                    if i < len(self.joint_spins):
                        current_angle = self.joint_spins[i].value()
                        label.setText(f"{current_angle:.1f}°")
        except Exception as e:
            print(f"更新微调显示失败: {e}")

    def update_end_effector_pose(self):
        """更新末端执行器位姿显示"""
        if not self.kinematics:
            # 显示未初始化状态
            self.pose_table.setItem(0, 0, QTableWidgetItem("--"))
            self.pose_table.setItem(0, 1, QTableWidgetItem("--"))
            self.pose_table.setItem(0, 2, QTableWidgetItem("--"))
            self.pose_table.setItem(0, 3, QTableWidgetItem("mm"))
            
            self.pose_table.setItem(1, 0, QTableWidgetItem("--"))
            self.pose_table.setItem(1, 1, QTableWidgetItem("--"))
            self.pose_table.setItem(1, 2, QTableWidgetItem("--"))
            self.pose_table.setItem(1, 3, QTableWidgetItem("°"))
            return
            
        # 检查joint_spins是否已经初始化
        if not hasattr(self, 'joint_spins') or not self.joint_spins:
            # joint_spins还未初始化，显示等待状态
            self.pose_table.setItem(0, 0, QTableWidgetItem("等待"))
            self.pose_table.setItem(0, 1, QTableWidgetItem("关节"))
            self.pose_table.setItem(0, 2, QTableWidgetItem("初始化"))
            self.pose_table.setItem(0, 3, QTableWidgetItem("mm"))
            
            self.pose_table.setItem(1, 0, QTableWidgetItem("等待"))
            self.pose_table.setItem(1, 1, QTableWidgetItem("关节"))
            self.pose_table.setItem(1, 2, QTableWidgetItem("初始化"))
            self.pose_table.setItem(1, 3, QTableWidgetItem("°"))
            return
            
        try:
            # 获取当前所有关节角度（从joint_spins获取实际值）
            joint_angles = [spin.value() for spin in self.joint_spins]
            
            # 使用运动学计算器计算末端位姿
            pose_info = self.kinematics.get_end_effector_pose(joint_angles)
            
            # 提取位置和姿态信息
            position = pose_info['position']  # [x, y, z] 单位：mm
            euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 单位：度（ZYX顺序）
            
            # 更新表格内容 - ZYX顺序显示
            # 位置行：Z, Y, X顺序
            self.pose_table.setItem(0, 0, QTableWidgetItem(f"{position[2]:.2f}"))  # Z位置
            self.pose_table.setItem(0, 1, QTableWidgetItem(f"{position[1]:.2f}"))  # Y位置
            self.pose_table.setItem(0, 2, QTableWidgetItem(f"{position[0]:.2f}"))  # X位置
            self.pose_table.setItem(0, 3, QTableWidgetItem("mm"))

            # 姿态行：Yaw, Pitch, Roll顺序
            self.pose_table.setItem(1, 0, QTableWidgetItem(f"{euler_angles[0]:.2f}"))  # Yaw (绕Z轴)
            self.pose_table.setItem(1, 1, QTableWidgetItem(f"{euler_angles[1]:.2f}"))  # Pitch (绕Y轴)
            self.pose_table.setItem(1, 2, QTableWidgetItem(f"{euler_angles[2]:.2f}"))  # Roll (绕X轴)
            self.pose_table.setItem(1, 3, QTableWidgetItem("°"))
            
            # 设置文本居中对齐
            for row in range(2):
                for col in range(4):
                    item = self.pose_table.item(row, col)
                    if item:
                        item.setTextAlignment(Qt.AlignCenter)
            
        except Exception as e:
            # 显示错误状态
            self.pose_table.setItem(0, 0, QTableWidgetItem("错误"))
            self.pose_table.setItem(0, 1, QTableWidgetItem("错误"))
            self.pose_table.setItem(0, 2, QTableWidgetItem("错误"))
            self.pose_table.setItem(0, 3, QTableWidgetItem("mm"))
            
            self.pose_table.setItem(1, 0, QTableWidgetItem("错误"))
            self.pose_table.setItem(1, 1, QTableWidgetItem("错误"))
            self.pose_table.setItem(1, 2, QTableWidgetItem("错误"))
            self.pose_table.setItem(1, 3, QTableWidgetItem("°"))
            
            print(f"末端位姿计算失败: {e}")
    
    def refresh_position_and_pose(self):
        """刷新关节角度和末端位姿显示"""
        try:
            if not self.motors:
                QMessageBox.warning(self, "警告", "未连接电机，无法刷新状态！\n\n请确保电机连接正常。")
                return
            
            print("🔄 开始刷新关节角度和末端位姿...")
            
            # 1. 从电机读取实际关节角度并更新界面输入框
            for i in range(6):
                motor_id = i + 1
                if motor_id in self.motors:
                    try:
                        # 获取电机位置
                        motor_pos = self.motors[motor_id].read_parameters.get_position()
                        
                        # 获取减速比和方向设置
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        
                        # 将电机角度转换为输出端角度
                        output_angle = (motor_pos * direction) / reducer_ratio
                        
                        # 更新关节角度输入框
                        self.joint_spins[i].setValue(output_angle)
                        
                    except Exception as motor_error:
                        print(f"⚠ 关节{i+1}角度读取失败: {motor_error}")
                        continue
            
            # 2. 更新微调显示
            self.update_fine_tune_display()
            
            # 3. 更新末端位姿显示
            self.update_end_effector_pose()
            
            # 4. 输出当前状态信息到控制台
            current_angles = [spin.value() for spin in self.joint_spins]
            print("✅ 状态刷新完成！当前信息：")
            print(f"   关节角度: {[f'J{i+1}={a:.1f}°' for i, a in enumerate(current_angles)]}")
            
            # 如果运动学模块可用，输出末端位姿信息
            if self.kinematics:
                try:
                    pose_info = self.kinematics.get_end_effector_pose(current_angles)
                    position = pose_info['position']  # [x, y, z] mm
                    euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 度
                    
                    print(f"   末端位置: X={position[0]:.1f}mm, Y={position[1]:.1f}mm, Z={position[2]:.1f}mm")
                    print(f"   末端姿态: Roll={euler_angles[2]:.1f}°, Pitch={euler_angles[1]:.1f}°, Yaw={euler_angles[0]:.1f}°")
                    
                except Exception as pose_error:
                    print(f"⚠ 计算末端位姿失败: {pose_error}")
            else:
                print("   注：运动学模块未初始化，无法计算末端位姿")
            
            # 5. 简单的成功提示
            print("🎉 关节角度和末端位姿刷新成功")
            
        except Exception as e:
            error_msg = f"刷新状态失败: {str(e)}"
            print(f"❌ {error_msg}")
            QMessageBox.critical(self, "错误", f"{error_msg}\n\n请检查电机连接和通信状态。")

    def clear_all_positions(self):
        """清零所有位置"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接电机")
            return
        
        # 获取所有连接的电机
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            # 1. 将界面上的所有关节角度设置为0
            for spin in self.joint_spins:
                spin.setValue(0.0)
            
            # 2. 发送清零位置命令给所有电机
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    motor.trigger_actions.clear_position()
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 清零位置失败:\n{str(e)}')
                    continue
            
            # 3. 如果有MuJoCo仿真运行，也更新仿真位置
            if self.mujoco_controller:
                try:
                    zero_angles = [0.0] * 6
                    # 使用关节空间插补让MuJoCo平滑回零
                    self._execute_mujoco_interpolation(zero_angles, 
                                                     self.max_speed_spin.value(),
                                                     self.acceleration_spin.value())
                except Exception as e:
                    print(f"更新仿真位置失败: {str(e)}")
            
            if success_count > 0:
                QMessageBox.information(self, '成功', 
                    f'已将关节角度设为0°，并成功清零 {success_count}/{len(selected_motors)} 个电机位置\n'
                    f'此位置现在为新的零位参考点')
            else:
                QMessageBox.warning(self, '部分失败', 
                    '已将关节角度设为0°，但电机清零位置失败\n'
                    '请检查电机连接状态')
                
        except Exception as e:
            QMessageBox.critical(self, '错误', f'清零位置操作失败:\n{str(e)}')
    
    def stop_motion(self):
        """停止运动"""
        # 停止MuJoCo插补（如果正在进行）
        if self.mujoco_interpolating:
            print("⏹️ 停止MuJoCo插补运动")
            self.mujoco_interpolating = False
        
        # 获取选中的电机
        selected_motors = self.get_selected_motor_objects()
        if not selected_motors:
            return
        
        try:
            success_count = 0
            for motor_id, motor in selected_motors:
                try:
                    motor.control_actions.stop()
                    success_count += 1
                except Exception as e:
                    QMessageBox.warning(self, '警告', f'电机 {motor_id} 停止失败:\n{str(e)}')
            
            if self.mujoco_interpolating:
                QMessageBox.information(self, '完成', f'成功停止 {success_count}/{len(selected_motors)} 个电机，并停止MuJoCo插补')
            else:
                QMessageBox.information(self, '完成', f'成功停止 {success_count}/{len(selected_motors)} 个电机')
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止运动失败: {str(e)}")
    
    # 移除apply_reducer_ratios方法，因为减速比设置现在由统一配置管理器处理
    
    def update_motors(self, motors):
        """更新电机列表"""
        self.motors = motors
        # 使用统一配置管理器，不需要清空和重新初始化减速比设置
        # 配置管理器会自动处理默认值
        
        # 有电机连接时启用运动控制按钮
        if motors:
            self.move_to_position_btn.setEnabled(True)
            self.home_position_btn.setEnabled(True)
            self.stop_motion_btn.setEnabled(True)
            self.clear_position_btn.setEnabled(True) # 启用清零按钮
            if hasattr(self, 'refresh_position_btn'):
                self.refresh_position_btn.setEnabled(True) # 启用刷新按钮
        else:
            self.move_to_position_btn.setEnabled(False)
            self.home_position_btn.setEnabled(False)
            self.stop_motion_btn.setEnabled(False)
            self.clear_position_btn.setEnabled(False) # 禁用清零按钮
            if hasattr(self, 'refresh_position_btn'):
                self.refresh_position_btn.setEnabled(False) # 禁用刷新按钮
        
        # 如果MuJoCo已经启动且有电机连接，应用减速比
        if motors and self.mujoco_controller:
            # self.apply_reducer_ratios() # 移除此行，减速比设置已移至配置管理器
            pass # 减速比设置已移至配置管理器，这里不再需要手动应用
        elif not motors:
            # 没有电机时更新状态
            if self.mujoco_controller:
                self.mujoco_status_label.setText("等待连接电机")
            else:
                self.mujoco_status_label.setText("未启动")
            self.mujoco_status_label.setProperty("class", "status-disconnected")
    
    def clear_motors(self):
        """清空电机列表"""
        # 停止状态刷新定时器
        if hasattr(self, 'status_timer') and self.status_timer:
            self.status_timer.stop()
        if hasattr(self, 'auto_refresh_checkbox'):
            self.auto_refresh_checkbox.setChecked(False)
        
        self.motors = {}
        # 使用统一配置管理器，清空电机时不需要清空配置
        # 减速比和方向配置保持不变
        
        # 禁用运动控制按钮
        self.move_to_position_btn.setEnabled(False)
        self.home_position_btn.setEnabled(False)
        self.stop_motion_btn.setEnabled(False)
        self.clear_position_btn.setEnabled(False) # 禁用清零按钮
        if hasattr(self, 'refresh_position_btn'):
            self.refresh_position_btn.setEnabled(False) # 禁用刷新按钮
        
        # 更新状态
        if self.mujoco_controller:
            self.mujoco_status_label.setText("等待连接电机")
        else:
            self.mujoco_status_label.setText("未启动")
        self.mujoco_status_label.setProperty("class", "status-disconnected") 