# -*- coding: utf-8 -*-
"""
IO控制界面控件
实现与ESP32的IO交互、作业管理和执行状态监控
"""

import sys
import os
import json
import time
import threading
import numpy as np
from datetime import datetime
from typing import Dict, List, Any, Optional
from PyQt5.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox,
    QLabel, QPushButton, QTableWidget, QTableWidgetItem, QComboBox,
    QLineEdit, QTextEdit, QProgressBar, QCheckBox, QSpinBox,
    QMessageBox, QFileDialog, QHeaderView, QFrame, QSplitter,
    QScrollArea, QGridLayout, QButtonGroup, QRadioButton, QFormLayout,
    QDialog, QDoubleSpinBox
)
from PyQt5.QtCore import Qt, QTimer, pyqtSignal, QThread, pyqtSlot, QObject
from PyQt5.QtGui import QFont, QColor, QPalette

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

from core.esp32_io_controller import ESP32IOController

# 导入全局配置管理器和运动学模块
try:
    from .motor_config_manager import motor_config_manager
    from Main_UI.utils.kinematics_factory import create_configured_kinematics
    KINEMATICS_AVAILABLE = True
except ImportError as e:
    print(f"导入配置管理器或运动学工厂模块失败: {e}")
    motor_config_manager = None
    KINEMATICS_AVAILABLE = False


class CreateJobDialog(QDialog):
    """创建作业对话框"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建新作业")
        self.setModal(True)
        self.resize(450, 300)
        
        layout = QVBoxLayout(self)
        
        # 作业名称输入
        name_group = QGroupBox("作业名称")
        name_layout = QFormLayout(name_group)
        
        self.name_edit = QLineEdit("new_job")
        name_layout.addRow("名称:", self.name_edit)
        layout.addWidget(name_group)
        
        # 作业类型选择
        type_group = QGroupBox("作业类型")
        type_group.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #ddd;
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 8px 0 8px;
                color: #2c3e50;
            }
        """)
        type_layout = QVBoxLayout(type_group)
        type_layout.setSpacing(15)
        
        from PyQt5.QtWidgets import QButtonGroup, QRadioButton
        self.type_button_group = QButtonGroup()
        
        # 普通作业选项卡
        normal_card = QWidget()
        normal_card.setStyleSheet("""
            QWidget {
                background-color: #f8f9fa;
                border: 2px solid #e9ecef;
                border-radius: 8px;
                padding: 10px;
            }
            QWidget:hover {
                border-color: #007bff;
                background-color: #e7f3ff;
            }
        """)
        normal_layout = QVBoxLayout(normal_card)
        normal_layout.setSpacing(5)
        
        self.normal_radio = QRadioButton("📝 普通作业")
        self.normal_radio.setStyleSheet("""
            QRadioButton {
                font-size: 14px;
                font-weight: bold;
                color: #2c3e50;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.normal_radio.setChecked(True)
        self.type_button_group.addButton(self.normal_radio, 0)
        normal_layout.addWidget(self.normal_radio)
        
        normal_desc = QLabel("创建空作业，可手动添加各种运动步骤、IO控制等")
        normal_desc.setStyleSheet("color: #6c757d; font-size: 12px; margin-left: 25px;")
        normal_desc.setWordWrap(True)
        normal_layout.addWidget(normal_desc)
        
        type_layout.addWidget(normal_card)
        
        # 特殊作业选项卡
        special_card = QWidget()
        special_card.setStyleSheet("""
            QWidget {
                background-color: #fff5f5;
                border: 2px solid #fecaca;
                border-radius: 8px;
                padding: 10px;
            }
            QWidget:hover {
                border-color: #ef4444;
                background-color: #fef2f2;
            }
        """)
        special_layout = QVBoxLayout(special_card)
        special_layout.setSpacing(5)
        
        self.special_radio = QRadioButton("🛑 紧急停止作业")
        self.special_radio.setStyleSheet("""
            QRadioButton {
                font-size: 14px;
                font-weight: bold;
                color: #dc2626;
            }
            QRadioButton::indicator {
                width: 18px;
                height: 18px;
            }
        """)
        self.type_button_group.addButton(self.special_radio, 1)
        special_layout.addWidget(self.special_radio)
        
        special_desc = QLabel("创建紧急停止作业，用于外部信号触发时立即停止所有电机运动")
        special_desc.setStyleSheet("color: #991b1b; font-size: 12px; margin-left: 25px;")
        special_desc.setWordWrap(True)
        special_layout.addWidget(special_desc)
        
        type_layout.addWidget(special_card)
        
        layout.addWidget(type_group)
        
        # 按钮组
        button_layout = QHBoxLayout()
        
        self.ok_btn = QPushButton("创建")
        self.ok_btn.setProperty("class", "success")
        self.ok_btn.clicked.connect(self.accept)
        button_layout.addWidget(self.ok_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def get_job_name(self) -> str:
        """获取作业名称"""
        return self.name_edit.text().strip()
        
    def get_job_type(self) -> str:
        """获取作业类型"""
        if self.special_radio.isChecked():
            return "emergency_stop"
        else:
            return "normal"


class JobExecutionWorker(QObject):
    """作业执行工作线程"""
    
    # 定义信号
    progress_updated = pyqtSignal(int, str)  # 进度更新 (百分比, 步骤描述)
    log_message = pyqtSignal(str)  # 日志消息
    job_completed = pyqtSignal(str)  # 作业完成
    job_error = pyqtSignal(str)  # 作业错误
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_job = None
        self.jobs_data = {}
        self.should_stop = False
        
        # 添加机械臂控制相关属性
        self.motors = {}
        self.claw_controller = None
        self.kinematics = None
        self.cartesian_executor = None
        self.joint_executor = None
        self.motor_config_manager = None
        self.output_joint_angles = [0.0] * 6
        
    def set_job_data(self, job_name: str, jobs_data: dict):
        """设置作业数据"""
        self.current_job = job_name
        self.jobs_data = jobs_data
        self.should_stop = False
        
    def set_control_components(self, motors, claw_controller, kinematics, motor_config_manager, esp32_controller=None):
        """设置控制组件"""
        self.motors = motors
        self.claw_controller = claw_controller
        self.kinematics = kinematics
        self.motor_config_manager = motor_config_manager
        self.esp32_controller = esp32_controller
        
        # 调试信息
        if motors:
            self.log_message.emit(f"🔧 JobExecutionWorker接收到电机: {list(motors.keys())}")
        else:
            self.log_message.emit("⚠️ JobExecutionWorker未接收到电机信息")
        
        # 初始化插补执行器
        self._initialize_interpolation_executors()
        
    def stop_job(self):
        """停止作业执行"""
        self.should_stop = True
        
    def _initialize_interpolation_executors(self):
        """初始化插补执行器"""
        if not self.kinematics or not self.motor_config_manager:
            return
            
        try:
            # 导入插补相关模块
            from core.arm_core.interpolation import CartesianSpaceInterpolator, JointSpaceInterpolator
            from core.arm_core.trajectory_executor import CartesianTrajectoryExecutor, JointSpaceTrajectoryExecutor
            
            # 初始化笛卡尔空间插补器
            cartesian_interpolator = CartesianSpaceInterpolator()
            self.cartesian_executor = CartesianTrajectoryExecutor(
                self.kinematics, 
                cartesian_interpolator, 
                self.motor_config_manager,
                ik_solver=self  # 传入self作为IK解选择器
            )
            
            # 初始化关节空间插补器
            joint_interpolator = JointSpaceInterpolator()
            self.joint_executor = JointSpaceTrajectoryExecutor(
                joint_interpolator, 
                self.motor_config_manager
            )
            
            self.log_message.emit("插补执行器初始化成功")
            
        except ImportError as e:
            self.log_message.emit(f"导入插补模块失败: {e}")
        except Exception as e:
            self.log_message.emit(f"插补执行器初始化失败: {e}")
            
        
    @pyqtSlot()
    def execute_job(self):
        """执行作业"""
        try:
            if not self.current_job or self.current_job not in self.jobs_data:
                self.job_error.emit("作业数据无效")
                return
                
            job_data = self.jobs_data[self.current_job]
            steps = job_data.get("steps", [])
            
            self.log_message.emit(f"开始执行作业: {self.current_job}")
            
            job_stopped_by_user = False
            
            for i, step in enumerate(steps):
                if self.should_stop:
                    # 检查是否是紧急停止步骤导致的停止
                    if step.get("type") == "emergency_stop":
                        # 紧急停止步骤，继续执行完成
                        pass
                    else:
                        # 用户手动停止
                        job_stopped_by_user = True
                        self.log_message.emit("作业被用户停止")
                        return
                    
                # 更新进度
                progress = int((i + 1) / len(steps) * 100)
                step_desc = step.get("description", f"步骤 {i+1}")
                self.progress_updated.emit(progress, f"执行步骤{i+1}: {step_desc}")
                
                # 执行步骤
                self.log_message.emit(f"执行步骤{i+1}: {step_desc}")
                
                # 根据步骤类型执行不同的操作
                success = self._execute_step(step)
                if not success:
                    self.job_error.emit(f"步骤{i+1}执行失败")
                    return
                
            # 作业完成（包括紧急停止作业）
            if not job_stopped_by_user:
                self.job_completed.emit(self.current_job)
                
        except Exception as e:
            self.job_error.emit(str(e))
            
    def _execute_step(self, step: dict) -> bool:
        """执行单个步骤"""
        try:
            step_type = step.get("type", "")
            parameters = step.get("parameters", {})
            
            if step_type == "move_joints":
                return self._execute_move_joints_step(parameters)
            elif step_type == "claw_control":
                return self._execute_claw_control_step(parameters)
            elif step_type == "wait":
                return self._execute_wait_step(parameters)
            elif step_type == "io_control":
                return self._execute_io_control_step(parameters)
            elif step_type == "emergency_stop":
                return self._execute_emergency_stop_step(parameters)
            else:
                self.log_message.emit(f"未知的步骤类型: {step_type}")
                return False
                
        except Exception as e:
            self.log_message.emit(f"执行步骤时出错: {e}")
            return False
            
    def _execute_move_joints_step(self, parameters: dict) -> bool:
        """执行关节运动步骤"""
        try:
            if not self.motors:
                self.log_message.emit("未连接电机，无法执行关节运动")
                return False
            
            # 同步当前关节角度
            self._sync_current_joint_angles()
                
            joint_angles = parameters.get("joint_angles", [0] * 6)
            interpolation_params_type = parameters.get("interpolation_params_type", "trapezoid")
            
            self.log_message.emit(f"当前关节角度: {[f'{a:.1f}°' for a in self.output_joint_angles]}")
            self.log_message.emit(f"目标关节角度: {[f'{a:.1f}°' for a in joint_angles]}")
            self.log_message.emit(f"插补类型: {interpolation_params_type}")
            
            if interpolation_params_type == "cartesian":
                # 笛卡尔空间插补
                return self._execute_cartesian_interpolation(joint_angles, parameters)
            elif interpolation_params_type == "joint_space":
                # 关节空间插补
                return self._execute_joint_space_interpolation(joint_angles, parameters)
            else:
                # 梯形曲线插补（默认）
                return self._execute_trapezoid_interpolation(joint_angles, parameters)
                
        except Exception as e:
            self.log_message.emit(f"关节运动执行失败: {e}")
            return False
            
    def _sync_current_joint_angles(self):
        """同步当前关节角度（参考示教器实现）"""
        try:
            if self.motors and self.motor_config_manager:
                current_angles = []
                for i in range(6):
                    motor_id = i + 1
                    if motor_id in self.motors:
                        motor = self.motors[motor_id]
                        # 获取当前位置 - 使用示教器的方法
                        try:
                            motor_pos = motor.read_parameters.get_position()
                        except AttributeError:
                            try:
                                motor_pos = motor.get_position()
                            except AttributeError:
                                motor_pos = None
                        
                        if motor_pos is not None:
                            # 获取减速比和方向设置
                            reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                            direction = self.motor_config_manager.get_motor_direction(motor_id)
                            
                            # 将电机角度转换为输出端角度：(电机角度 * 方向) / 减速比
                            output_angle = (motor_pos * direction) / reducer_ratio
                            current_angles.append(output_angle)
                        else:
                            current_angles.append(0.0)
                            self.log_message.emit(f"⚠️ 无法获取关节J{motor_id}位置，使用默认值0°")
                    else:
                        current_angles.append(0.0)
                
                self.output_joint_angles = current_angles
                self.log_message.emit(f"同步关节角度: {[f'{a:.1f}°' for a in current_angles]}")
            else:
                self.log_message.emit("无法同步关节角度：缺少电机或配置管理器")
        except Exception as e:
            self.log_message.emit(f"同步关节角度失败: {e}")
            
    def _get_actual_angle(self, input_angle: float, motor_id: int) -> float:
        """获取实际角度（参考示教器实现）"""
        try:
            if self.motor_config_manager:
                # 获取减速比和方向设置
                reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                direction = self.motor_config_manager.get_motor_direction(motor_id)
                
                # 将输出角度转换为电机角度：输出角度 * 减速比 / 方向
                motor_angle = input_angle * reducer_ratio / direction
                return motor_angle
            return input_angle
        except Exception as e:
            self.log_message.emit(f"角度转换失败: {e}")
            return input_angle
             
    def _execute_cartesian_interpolation(self, target_joint_angles: list, parameters: dict) -> bool:
        """执行笛卡尔空间插补（参考示教器实现）"""
        try:
            if not self.cartesian_executor:
                self.log_message.emit("❌ 笛卡尔插补器未初始化")
                return False
                
            if not self.kinematics:
                self.log_message.emit("❌ 运动学模块未初始化")
                return False
                
            # 获取当前位姿
            current_pose = self.kinematics.get_end_effector_pose(self.output_joint_angles)
            current_position = np.array(current_pose['position'])  # 转换为numpy数组
            current_orientation = np.array(current_pose['euler_angles'])  # 转换为numpy数组
            
            # 计算目标位姿
            target_pose = self.kinematics.get_end_effector_pose(target_joint_angles)
            target_position = np.array(target_pose['position'])  # 转换为numpy数组
            target_orientation = np.array(target_pose['euler_angles'])  # 转换为numpy数组
            
            # 获取笛卡尔插补参数
            linear_velocity = parameters.get("linear_velocity", 50.0)
            angular_velocity = parameters.get("angular_velocity", 30.0)
            linear_acceleration = parameters.get("linear_acceleration", 100.0)
            angular_acceleration = parameters.get("angular_acceleration", 60.0)
            
            self.log_message.emit(f"📐 笛卡尔插补: {[f'{p:.1f}' for p in current_position]} → {[f'{p:.1f}' for p in target_position]}")
            self.log_message.emit(f"🎯 笛卡尔插补参数: 线速度 {linear_velocity}mm/s, 角速度 {angular_velocity}°/s")
            
            # 规划笛卡尔轨迹
            success = self.cartesian_executor.plan_cartesian_trajectory(
                current_position, current_orientation,
                target_position, target_orientation,
                max_linear_velocity=linear_velocity,
                max_angular_velocity=angular_velocity,
                max_linear_acceleration=linear_acceleration,
                max_angular_acceleration=angular_acceleration
            )
            
            if not success:
                self.log_message.emit("❌ 笛卡尔轨迹规划失败")
                return False
            
            # 生成轨迹点
            trajectory_points = self.cartesian_executor.generate_trajectory_points(self.output_joint_angles)
            if not trajectory_points:
                self.log_message.emit("❌ 轨迹点生成失败")
                return False
            
            # 同步执行轨迹（参考示教器的 _execute_cartesian_trajectory_sync）
            success = self._execute_cartesian_trajectory_sync()
            
            if success:
                # 更新输出端角度状态
                self.output_joint_angles = list(target_joint_angles)
                self.log_message.emit(f"✅ 笛卡尔空间插补执行完成")
            
            return success
            
        except Exception as e:
            self.log_message.emit(f"❌ 笛卡尔插补执行失败: {e}")
            return False
            
    def _execute_joint_space_interpolation(self, target_joint_angles: list, parameters: dict) -> bool:
        """执行关节空间插补（参考示教器实现）"""
        try:
            if not self.joint_executor:
                self.log_message.emit("❌ 关节插补器未初始化")
                return False
            
            current_angles = np.array(self.output_joint_angles.copy())
            target_angles = np.array(target_joint_angles)
            
            self.log_message.emit(f"📐 关节空间插补: {[f'{a:.1f}°' for a in current_angles]} → {[f'{a:.1f}°' for a in target_angles]}")
            
            # 获取关节空间插补参数：从单一值扩展为6个关节
            single_velocity = parameters.get("joint_max_velocity", parameters.get("max_velocity", 30.0))
            single_acceleration = parameters.get("joint_max_acceleration", parameters.get("max_acceleration", 60.0))
            
            # 所有6个关节使用相同的速度和加速度值
            max_velocities = np.array([single_velocity] * 6)
            max_accelerations = np.array([single_acceleration] * 6)
            
            self.log_message.emit(f"🎯 关节插补参数: 速度 {single_velocity}°/s, 加速度 {single_acceleration}°/s² (应用于所有6个关节)")
            
            # 规划关节空间轨迹
            waypoints = [current_angles, target_angles]
            success = self.joint_executor.plan_joint_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocities,
                max_acceleration=max_accelerations
            )
            
            if not success:
                self.log_message.emit("❌ 关节空间轨迹规划失败")
                return False
            
            # 生成轨迹点
            trajectory_points = self.joint_executor.generate_trajectory_points()
            if not trajectory_points:
                self.log_message.emit("❌ 轨迹点生成失败")
                return False
            
            # 同步执行轨迹（参考示教器的 _execute_joint_trajectory_sync）
            success = self._execute_joint_trajectory_sync()
            
            if success:
                # 更新输出端角度状态
                self.output_joint_angles = list(target_angles)
                self.log_message.emit(f"✅ 关节空间插补执行完成")
            
            return success
            
        except Exception as e:
            self.log_message.emit(f"❌ 关节空间插补执行失败: {e}")
            return False
            
    def _execute_trapezoid_interpolation(self, target_joint_angles: list, parameters: dict) -> bool:
        """执行梯形曲线插补"""
        try:
            if not self.motors:
                self.log_message.emit("未连接电机")
                return False
                
            # 获取梯形曲线参数
            max_speed = parameters.get("max_speed", 50)
            acceleration = parameters.get("acceleration", 50)
            deceleration = parameters.get("deceleration", 50)
            
            self.log_message.emit(f"梯形曲线插补: 速度={max_speed}, 加速度={acceleration}")
            
            # 检测板子类型
            is_y_board = self._is_y_board()
            
            if is_y_board:
                # Y板：使用多电机命令
                return self._execute_trapezoid_y_board(target_joint_angles, max_speed, acceleration, deceleration)
            else:
                # X板：使用同步标志+广播同步
                return self._execute_trapezoid_x_board(target_joint_angles, max_speed, acceleration, deceleration)
                
        except Exception as e:
            self.log_message.emit(f"梯形曲线插补执行失败: {e}")
            return False
            
    def _execute_trapezoid_y_board(self, target_joint_angles: list, max_speed: int, acceleration: int, deceleration: int) -> bool:
        """Y板梯形曲线插补执行"""
        try:
            # 导入命令构建器
            try:
                from Control_SDK.Control_Core import ZDTCommandBuilder
            except ImportError:
                self.log_message.emit("无法导入ZDT命令构建器")
                return False
            
            # 构建多电机命令
            commands = []
            for i in range(6):
                motor_id = i + 1
                if motor_id in self.motors:
                    actual_angle = self._get_actual_angle(target_joint_angles[i], motor_id)
                    func_body = ZDTCommandBuilder.position_mode_trapezoid(
                        position=actual_angle,
                        max_speed=max_speed,
                        acceleration=acceleration,
                        deceleration=deceleration,
                        is_absolute=True,
                        multi_sync=False
                    )
                    commands.append(self._build_single_command_for_multi(motor_id, func_body))
            
            if not commands:
                self.log_message.emit("没有可用的电机命令")
                return False
            
            # 发送多电机命令
            first_motor = list(self.motors.values())[0]
            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
            
            self.log_message.emit("🔄 Y板多电机命令已发送")
            
            # 等待运动完成
            return self._wait_for_position_reached(target_joint_angles)
            
        except Exception as e:
            self.log_message.emit(f"Y板梯形曲线插补执行失败: {e}")
            return False
            
    def _execute_trapezoid_x_board(self, target_joint_angles: list, max_speed: int, acceleration: int, deceleration: int) -> bool:
        """X板梯形曲线插补执行（参考示教器实现）"""
        try:
            self.log_message.emit("🔄 使用X板同步模式执行")
            
            # 预处理：计算各关节电机端角度
            per_motor_angles = {}
            for i, output_angle in enumerate(target_joint_angles):
                motor_id = i + 1
                if motor_id in self.motors:
                    actual_angle = self._get_actual_angle(output_angle, motor_id)
                    per_motor_angles[motor_id] = actual_angle
            
            if not per_motor_angles:
                self.log_message.emit("没有可用的电机")
                return False
            
            # X板：按同步标志+广播同步
            success_count = 0
            for motor_id, motor_angle in per_motor_angles.items():
                try:
                    motor = self.motors[motor_id]
                    motor.control_actions.move_to_position_trapezoid(
                        position=motor_angle,
                        max_speed=max_speed,
                        acceleration=acceleration,
                        deceleration=deceleration,
                        is_absolute=True,
                        multi_sync=True  # X板关键：设置同步标志
                    )
                    success_count += 1
                    self.log_message.emit(f"✅ 电机 {motor_id} 同步命令设置成功")
                except Exception as motor_error:
                    self.log_message.emit(f"❌ 电机 {motor_id} 设置失败: {motor_error}")
                    continue
            
            if success_count == 0:
                self.log_message.emit("没有电机成功设置运动参数")
                return False
            
            # 发送同步运动命令
            try:
                first_motor = list(self.motors.values())[0]
                interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                broadcast_motor = first_motor.__class__(
                    motor_id=0,  # 广播ID
                    interface_type=first_motor.interface_type,
                    shared_interface=True,
                    **interface_kwargs
                )
                broadcast_motor.can_interface = first_motor.can_interface
                broadcast_motor.control_actions.sync_motion()
                self.log_message.emit("🚀 X板同步运动命令已发送")
            except Exception as e:
                self.log_message.emit(f"❌ 同步运动命令发送失败: {e}")
                return False
            
            # 更新输出端角度状态
            self.output_joint_angles = list(target_joint_angles)
            
            # 等待运动完成
            return self._wait_for_position_reached(target_joint_angles)
            
        except Exception as e:
            self.log_message.emit(f"X板梯形曲线插补执行失败: {e}")
            return False
            
    def _execute_cartesian_trajectory_sync(self) -> bool:
        """同步执行笛卡尔轨迹（完全参考示教器实现）"""
        try:
            import time
            self.log_message.emit("🎯 开始同步执行笛卡尔轨迹...")
            
            while True:
                if self.should_stop:
                    self.log_message.emit("⚠️ 笛卡尔轨迹执行被中断")
                    return False
                
                # 获取下一个电机命令
                motor_commands, execution_info = self.cartesian_executor.get_next_motor_commands(
                    self.output_joint_angles, 100  # speed_setting
                )
                
                if execution_info.get('finished', False):
                    # 轨迹执行完成
                    if 'error' in execution_info:
                        self.log_message.emit(f"❌ 笛卡尔轨迹执行出错: {execution_info['error']}")
                        return False
                    else:
                        self.log_message.emit("✅ 笛卡尔轨迹同步执行完成")
                        # 更新最终状态
                        if 'target_joint_angles' in execution_info:
                            self.output_joint_angles = list(execution_info['target_joint_angles'])
                        break
                
                # 发送电机命令
                if motor_commands:
                    commands = []
                    for cmd in motor_commands:
                        try:
                            from Control_SDK.Control_Core import ZDTCommandBuilder
                            func_body = ZDTCommandBuilder.position_mode_direct(
                                position=cmd['position'],
                                speed=cmd['speed'],
                                is_absolute=True,
                                multi_sync=False
                            )
                            commands.append(self._build_single_command_for_multi(cmd['motor_id'], func_body))
                        except Exception as cmd_error:
                            self.log_message.emit(f"❌ 构建电机命令失败: {cmd_error}")
                            continue
                    
                    # 发送多电机命令
                    if commands and self.motors:
                        try:
                            first_motor = list(self.motors.values())[0]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                        except Exception as send_error:
                            self.log_message.emit(f"❌ 发送电机命令失败: {send_error}")
                
                # 更新输出端角度状态
                if 'target_joint_angles' in execution_info:
                    self.output_joint_angles = list(execution_info['target_joint_angles'])
                
                # 等待执行间隔
                next_interval = execution_info.get('next_interval', 20)
                time.sleep(next_interval / 1000.0)
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ 同步执行笛卡尔轨迹失败: {e}")
            return False
            
    def _execute_joint_trajectory_sync(self) -> bool:
        """同步执行关节空间轨迹（完全参考示教器实现）"""
        try:
            import time
            self.log_message.emit("🎯 开始同步执行关节空间轨迹...")
            
            # 使用与示教器完全一致的索引驱动循环
            while True:
                if self.should_stop:
                    self.log_message.emit("⚠️ 关节空间轨迹执行被中断")
                    return False
                
                # 获取下一个电机命令（使用索引机制）
                motor_commands, execution_info = self.joint_executor.get_next_motor_commands(
                    current_time=0.0,  # 兼容参数，不再用于核心逻辑
                    speed_setting=100  # 速度设置
                )
                
                # 检查是否执行完成（与示教器一致的完成检测）
                if execution_info.get('finished', False):
                    # 轨迹执行完成
                    if 'error' in execution_info:
                        self.log_message.emit(f"❌ 关节轨迹执行出错: {execution_info['error']}")
                        return False
                    else:
                        self.log_message.emit("✅ 关节轨迹同步执行完成")
                        # 更新最终状态
                        if 'target_joint_angles' in execution_info:
                            self.output_joint_angles = list(execution_info['target_joint_angles'])
                        break
                
                # 发送电机命令
                if motor_commands:
                    commands = []
                    for cmd in motor_commands:
                        try:
                            from Control_SDK.Control_Core import ZDTCommandBuilder
                            func_body = ZDTCommandBuilder.position_mode_direct(
                                position=cmd['position'],
                                speed=cmd['speed'],
                                is_absolute=True,
                                multi_sync=False
                            )
                            commands.append(self._build_single_command_for_multi(cmd['motor_id'], func_body))
                        except Exception as cmd_error:
                            self.log_message.emit(f"❌ 构建电机命令失败: {cmd_error}")
                            continue
                    
                    # 发送多电机命令
                    if commands and self.motors:
                        try:
                            first_motor = list(self.motors.values())[0]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                        except Exception as send_error:
                            self.log_message.emit(f"❌ 发送电机命令失败: {send_error}")
                
                # 更新输出端角度状态
                if 'target_joint_angles' in execution_info:
                    self.output_joint_angles = list(execution_info['target_joint_angles'])
                
                # 使用与示教器完全相同的等待逻辑
                next_interval = execution_info.get('next_interval', 20)  # 默认20ms
                time.sleep(next_interval / 1000.0)  # 转换为秒
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ 同步执行关节轨迹失败: {e}")
            return False
            
    def _execute_claw_control_step(self, parameters: dict) -> bool:
        """执行夹爪控制步骤"""
        try:
            if not self.claw_controller:
                self.log_message.emit("未连接夹爪控制器")
                return False
                
            # 检查夹爪控制器是否已连接
            if not self.claw_controller.is_connected():
                self.log_message.emit("夹爪控制器未连接")
                return False
                
            action = parameters.get("action", "open")
            open_angle = parameters.get("open_angle", 0)  # 0度为张开
            close_angle = parameters.get("close_angle", 90)  # 90度为闭合
            
            angle = open_angle if action == "open" else close_angle
            self.log_message.emit(f"夹爪控制: {action} 角度={angle}°")
            
            # 执行夹爪控制
            if action == "open":
                self.claw_controller.open(angle)
                self.log_message.emit(f"✅ 夹爪张开到 {angle}°")
            else:
                self.claw_controller.close(angle)
                self.log_message.emit(f"✅ 夹爪闭合到 {angle}°")
            
            # 等待夹爪动作完成
            import time
            time.sleep(1.0)  # 给夹爪足够时间完成动作
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ 夹爪控制执行失败: {e}")
            return False
            
    def _execute_wait_step(self, parameters: dict) -> bool:
        """执行等待步骤"""
        try:
            wait_duration = parameters.get("wait_duration", 1.0)
            self.log_message.emit(f"等待 {wait_duration} 秒")
            
            import time
            time.sleep(wait_duration)
            
            return True
            
        except Exception as e:
            self.log_message.emit(f"等待步骤执行失败: {e}")
            return False
            
    def _execute_io_control_step(self, parameters: dict) -> bool:
        """执行DO控制步骤"""
        try:
            # 兼容新旧格式
            if "do_number" in parameters:
                # 新格式
                do_number = parameters.get("do_number", 0)
                do_name = parameters.get("do_name", f"DO{do_number}")
                
                # 新格式使用output_level参数
                if "output_level" in parameters:
                    output_level = parameters.get("output_level", "高电平")
                    state = True if output_level == "高电平" else False
                    state_desc = "HIGH" if state else "LOW"
                else:
                    # 兼容旧的trigger_method参数
                    trigger_method = parameters.get("trigger_method", "设置高电平")
                    state = True if trigger_method == "设置高电平" else False
                    state_desc = "HIGH" if state else "LOW"
                    output_level = "高电平" if state else "低电平"
            else:
                # 旧格式兼容
                do_number = parameters.get("pin", 0)
                do_name = f"DO{do_number}"
                # 旧格式使用state参数
                old_state = parameters.get("state", "HIGH")
                state = True if old_state == "HIGH" else False
                state_desc = old_state
                output_level = "高电平" if state else "低电平"
            
            self.log_message.emit(f"DO控制: {do_name} - 输出{output_level} ({state_desc})")
            
            # 执行实际的DO控制
            if self.esp32_controller:
                success = self.esp32_controller.set_do_state(do_number, state)
                if success:
                    self.log_message.emit(f"✅ {do_name}设置成功")
                    return True
                else:
                    self.log_message.emit(f"❌ {do_name}设置失败")
                    return False
            else:
                self.log_message.emit("⚠️ ESP32控制器未连接，跳过DO控制")
                return True
            
        except Exception as e:
            self.log_message.emit(f"DO控制执行失败: {e}")
            return False
            
    def _execute_emergency_stop_step(self, parameters: dict) -> bool:
        """执行紧急停止步骤"""
        try:
            self.log_message.emit("🛑 执行紧急停止...")
            
            # 停止所有电机（不设置should_stop标志，让作业正常完成）
            if self.motors:
                stopped_count = 0
                failed_count = 0
                
                for motor_id, motor in self.motors.items():
                    try:
                        motor.control_actions.stop()
                        stopped_count += 1
                        self.log_message.emit(f"✅ 电机 {motor_id} 已停止")
                    except Exception as e:
                        failed_count += 1
                        self.log_message.emit(f"❌ 电机 {motor_id} 停止失败: {e}")
                
                if stopped_count > 0:
                    self.log_message.emit(f"🛑 成功停止 {stopped_count} 个电机")
                    if failed_count > 0:
                        self.log_message.emit(f"⚠️ {failed_count} 个电机停止失败")
                else:
                    self.log_message.emit("⚠️ 未能停止任何电机")
            else:
                self.log_message.emit("⚠️ 未检测到已连接的电机")
            
            self.log_message.emit("🛑 紧急停止执行完成")
            return True
            
        except Exception as e:
            self.log_message.emit(f"❌ 紧急停止执行失败: {e}")
            return False
            
    def _get_actual_angle(self, output_angle: float, motor_id: int) -> float:
        """根据减速比和方向设置计算实际发送给电机的角度"""
        if not self.motor_config_manager:
            # 如果没有配置管理器，使用默认值
            self.log_message.emit(f"⚠️ 警告：电机{motor_id}使用默认减速比和方向")
            return output_angle * 50.0  # 默认减速比50:1
            
        try:
            # 获取对应电机的减速比和方向
            reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
            direction = self.motor_config_manager.get_motor_direction(motor_id)
            
            # 计算电机端角度
            motor_angle = output_angle * reducer_ratio * direction
            
            return motor_angle
        except Exception as e:
            self.log_message.emit(f"⚠️ 获取电机{motor_id}参数失败: {e}，使用默认值")
            return output_angle * 50.0
        
    def _build_single_command_for_multi(self, motor_id: int, function_body: list) -> list:
        """构造单个电机命令（用于多电机命令）"""
        try:
            from Control_SDK.Control_Core import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, function_body)
        except Exception:
            return [motor_id] + function_body
            
    def _is_y_board(self) -> bool:
        """检测是否为Y板（参考示教器实现）"""
        try:
            if not self.motors:
                return False
            
            # 检查所有电机的drive_version属性
            versions = set()
            for motor in self.motors.values():
                drive_version = str(getattr(motor, 'drive_version', 'X')).upper()
                versions.add(drive_version)
                
            # 只有当所有电机都是Y版时才返回True
            is_y = versions == {"Y"}
            
            self.log_message.emit(f"🔍 板子类型检测: 电机版本={list(versions)}, 判定={'Y板' if is_y else 'X板'}")
            return is_y
                
        except Exception as e:
            self.log_message.emit(f"⚠️ 板子类型检测失败: {e}")
            return False  # 默认为X板
            
    def _wait_for_position_reached(self, target_angles: list, timeout: float = 30.0, tolerance: float = 1.0) -> bool:
        """等待机械臂到达目标位置"""
        import time
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            if self.should_stop:
                return False
            
            try:
                # 获取当前关节角度（输出端角度）
                current_angles = self._get_current_joint_angles()
                
                # 检查是否到达目标位置
                if self._is_position_reached(current_angles, target_angles, tolerance):
                    self.output_joint_angles = target_angles.copy()
                    self.log_message.emit(f"✅ 机械臂已到达目标位置: {[f'{a:.1f}°' for a in target_angles]}")
                    return True
                    
                # 短暂等待后再次检查
                time.sleep(0.05)  # 50ms检查间隔
                
            except Exception as e:
                self.log_message.emit(f"⚠️ 获取关节角度失败: {e}")
                time.sleep(0.1)
                
        self.log_message.emit(f"⚠️ 等待超时，机械臂未能在{timeout}秒内到达目标位置")
        return False
    
    def _get_current_joint_angles(self) -> list:
        """获取当前关节角度（输出端角度）"""
        try:
            if not self.motors:
                return [0.0] * 6
                
            current_angles = []
            for motor_id in range(1, 7):
                if motor_id in self.motors:
                    motor = self.motors[motor_id]
                    # 获取电机当前位置（使用read_parameters模块）
                    motor_pos = motor.read_parameters.get_position()
                    
                    # 转换为输出端角度
                    if self.motor_config_manager:
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        output_angle = (motor_pos * direction) / reducer_ratio
                    else:
                        output_angle = motor_pos / 50.0  # 默认减速比
                    
                    current_angles.append(output_angle)
                else:
                    current_angles.append(0.0)
                    
            return current_angles
            
        except Exception as e:
            self.log_message.emit(f"获取关节角度异常: {e}")
            return self.output_joint_angles.copy()  # 返回上次记录的角度
    
    def _is_position_reached(self, current_angles: list, target_angles: list, tolerance: float) -> bool:
        """检查是否到达目标位置"""
        if len(current_angles) != len(target_angles):
            return False
            
        for i, (current, target) in enumerate(zip(current_angles, target_angles)):
            error = abs(current - target)
            if error > tolerance:
                return False
                
        return True


class IOControlWidget(QWidget):
    """IO控制主界面"""
    
    # 信号定义
    job_status_changed = pyqtSignal(str, str)  # 作业状态变化信号
    io_state_changed = pyqtSignal(dict)        # IO状态变化信号
    
    def __init__(self):
        super().__init__()
        
        # 初始化属性
        self.esp32_controller = None  # ESP32控制器
        self.motors = {}              # 电机控制器字典
        self.claw_controller = None   # 夹爪控制器
        
        # 作业管理
        self.jobs = {}                # 作业字典 {job_name: job_data}
        self.job_io_mapping = {}      # IO映射 {di_pin: job_info}
        
        # 运行状态
        self.is_external_mode = False # 是否处于外部控制模式
        self.current_job = None       # 当前执行的作业
        self.job_thread = None        # 作业执行线程
        self.job_worker = None        # 作业执行工作器
        self.io_monitor_thread = None # IO监控线程
        self.stop_monitoring = False  # 停止监控标志
        
        # IO状态
        self.di_states = [False] * 8  # 数字输入状态
        self.do_states = [False] * 8  # 数字输出状态
        self.previous_di_states = [False] * 8  # 上一次DI状态
        
        # 固定GPIO引脚映射（与ESP32固件保持一致，避开UART引脚）
        self.DI_GPIO_MAP = {
            0: 23, 1: 22, 2: 17, 3: 16, 4: 21, 5: 19, 6: 18, 7: 5
        }
        self.DO_GPIO_MAP = {
            0: 2, 1: 4, 2: 25, 3: 26, 4: 27, 5: 32, 6: 33, 7: 13
        }
        
        # GPIO状态
        self.gpio_states = {}  # {gpio_pin: state}
        self.gpio_config = {}  # 保持兼容性，但使用固定映射
        
        # 配置文件路径
        self.config_dir = os.path.join(project_root, "config", "io_control")
        os.makedirs(self.config_dir, exist_ok=True)
        self.jobs_config_file = os.path.join(self.config_dir, "jobs_config.json")
        self.io_mapping_file = os.path.join(self.config_dir, "io_mapping.json")
        
        # 初始化机械臂控制相关属性
        self.motor_config_manager = motor_config_manager  # 使用全局配置管理器
        self.kinematics = None
        
        # 初始化运动学计算器
        if KINEMATICS_AVAILABLE:
            try:
                self.kinematics = create_configured_kinematics()
            except Exception as e:
                print(f"⚠️ IO控制模块: 运动学计算器初始化失败: {e}")
                self.kinematics = None
        else:
            print("⚠️ IO控制模块: 运动学模块未导入")
        
        # 板子类型检测
        self.board_type = "Y"  # 默认Y板，支持笛卡尔插补
        
        self.init_ui()
        self.load_configuration()
        
        # 初始化IO状态显示（未连接状态）
        self.refresh_io_display()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        
        # IO控制标签页
        self.io_control_tab = self.create_io_control_tab()
        self.tab_widget.addTab(self.io_control_tab, "IO控制")
        
        # 作业管理标签页
        self.job_management_tab = self.create_job_management_tab()
        self.tab_widget.addTab(self.job_management_tab, "作业管理")
        
        # 执行状态标签页
        self.execution_status_tab = self.create_execution_status_tab()
        self.tab_widget.addTab(self.execution_status_tab, "执行状态")
        
        layout.addWidget(self.tab_widget)
        
    def create_io_control_tab(self):
        """创建IO控制标签页"""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        
        # 左侧：ESP32连接和IO状态
        left_panel = QVBoxLayout()
        
        # ESP32连接组
        esp32_group = QGroupBox("ESP32连接")
        esp32_layout = QVBoxLayout(esp32_group)
        
        # 串口选择
        port_layout = QHBoxLayout()
        port_layout.addWidget(QLabel("串口:"))
        self.port_combo = QComboBox()
        self.port_combo.setEditable(True)
        self.port_combo.addItems(["COM1", "COM2", "COM3", "COM4", "COM5", "COM6", "COM7", "COM8"])
        port_layout.addWidget(self.port_combo)
        esp32_layout.addLayout(port_layout)
        
        # 波特率选择
        baudrate_layout = QHBoxLayout()
        baudrate_layout.addWidget(QLabel("波特率:"))
        self.baudrate_combo = QComboBox()
        self.baudrate_combo.addItems(["9600", "19200", "38400", "57600", "115200"])
        self.baudrate_combo.setCurrentText("115200")
        baudrate_layout.addWidget(self.baudrate_combo)
        esp32_layout.addLayout(baudrate_layout)
        
        # 连接按钮
        connect_layout = QHBoxLayout()
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setProperty("class", "success")
        self.connect_btn.clicked.connect(self.connect_esp32)
        connect_layout.addWidget(self.connect_btn)
        
        self.disconnect_btn = QPushButton("断开")
        self.disconnect_btn.setProperty("class", "danger")
        self.disconnect_btn.clicked.connect(self.disconnect_esp32)
        self.disconnect_btn.setEnabled(False)
        connect_layout.addWidget(self.disconnect_btn)
        esp32_layout.addLayout(connect_layout)
        
        # 连接状态
        self.esp32_status_label = QLabel("未连接")
        self.esp32_status_label.setProperty("class", "status-disconnected")
        esp32_layout.addWidget(self.esp32_status_label)
        
        left_panel.addWidget(esp32_group)
        
        # IO状态显示组
        io_status_group = QGroupBox("IO状态")
        io_status_layout = QVBoxLayout(io_status_group)
        
        # 数字输入状态
        di_group = QGroupBox("数字输入 (DI)")
        di_layout = QGridLayout(di_group)
        di_layout.setSpacing(10)
        self.di_indicators = []
        for i in range(8):
            # 创建一个美观的状态卡片
            card = QWidget()
            card.setFixedSize(70, 45)
            card.setStyleSheet("""
                QWidget {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                }
                QWidget:hover {
                    background-color: #e9ecef;
                    border-color: #adb5bd;
                }
            """)
            
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 3, 5, 3)
            card_layout.setSpacing(1)
            
            # 状态指示器（LED样式）
            indicator = QLabel()
            indicator.setFixedSize(20, 20)
            indicator.setAlignment(Qt.AlignCenter)
            indicator.setStyleSheet("""
                QLabel {
                    background-color: #6c757d;
                    border: 2px solid #495057;
                    border-radius: 10px;
                    color: white;
                    font-size: 10px;
                    font-weight: bold;
                }
            """)
            indicator.setText("●")
            
            # 标签
            label = QLabel(f"DI{i}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    font-size: 10px; 
                    font-weight: bold; 
                    color: #495057;
                    background: transparent;
                    border: none;
                }
            """)
            
            card_layout.addWidget(indicator, 0, Qt.AlignCenter)
            card_layout.addWidget(label, 0, Qt.AlignCenter)
            
            di_layout.addWidget(card, i // 4, i % 4)
            self.di_indicators.append(indicator)
        io_status_layout.addWidget(di_group)
        
        # 数字输出控制
        do_group = QGroupBox("数字输出 (DO)")
        do_layout = QGridLayout(do_group)
        do_layout.setSpacing(10)
        self.do_checkboxes = []
        for i in range(8):
            # 创建美观的DO控制卡片
            card = QWidget()
            card.setFixedSize(70, 45)
            card.setStyleSheet("""
                QWidget {
                    background-color: #f8f9fa;
                    border: 1px solid #dee2e6;
                    border-radius: 8px;
                }
                QWidget:hover {
                    background-color: #e9ecef;
                    border-color: #adb5bd;
                }
            """)
            
            card_layout = QVBoxLayout(card)
            card_layout.setContentsMargins(5, 3, 5, 3)
            card_layout.setSpacing(1)
            
            # 使用开关样式的复选框
            checkbox = QCheckBox()
            checkbox.setFixedSize(30, 16)
            checkbox.setStyleSheet("""
                QCheckBox::indicator {
                    width: 30px;
                    height: 16px;
                    border-radius: 8px;
                    background-color: #6c757d;
                    border: 2px solid #495057;
                }
                QCheckBox::indicator:checked {
                    background-color: #28a745;
                    border-color: #1e7e34;
                }
                QCheckBox::indicator:disabled {
                    background-color: #e9ecef;
                    border-color: #dee2e6;
                }
            """)
            checkbox.stateChanged.connect(lambda state, pin=i: self.set_do_state(pin, state == Qt.Checked))
            
            # 标签
            label = QLabel(f"DO{i}")
            label.setAlignment(Qt.AlignCenter)
            label.setStyleSheet("""
                QLabel {
                    font-size: 10px; 
                    font-weight: bold; 
                    color: #495057;
                    background: transparent;
                    border: none;
                }
            """)
            
            card_layout.addWidget(checkbox, 0, Qt.AlignCenter)
            card_layout.addWidget(label, 0, Qt.AlignCenter)
            
            do_layout.addWidget(card, i // 4, i % 4)
            self.do_checkboxes.append(checkbox)
        io_status_layout.addWidget(do_group)
        
        left_panel.addWidget(io_status_group)
        
        # 外部控制模式组
        external_mode_group = QGroupBox("外部控制模式")
        external_mode_layout = QVBoxLayout(external_mode_group)
        
        self.external_mode_btn = QPushButton("进入外部控制模式")
        self.external_mode_btn.setProperty("class", "warning")
        self.external_mode_btn.clicked.connect(self.toggle_external_mode)
        external_mode_layout.addWidget(self.external_mode_btn)
        
        self.external_mode_status = QLabel("手动控制模式")
        self.external_mode_status.setProperty("class", "status-disconnected")
        external_mode_layout.addWidget(self.external_mode_status)
        
        left_panel.addWidget(external_mode_group)
        
        # 右侧：IO映射配置
        right_panel = QVBoxLayout()
        
        # IO映射配置组
        mapping_group = QGroupBox("IO映射配置")
        mapping_layout = QVBoxLayout(mapping_group)
        
        # 添加说明标签
        info_label = QLabel("说明：GPIO引脚为用户配置的逻辑映射，ESP32固件使用固定的DI/DO引脚，上位机进行适配")
        info_label.setStyleSheet("color: #2c3e50; font-size: 12px; padding: 5px; background-color: #ecf0f1; border-radius: 3px;")
        info_label.setWordWrap(True)
        mapping_layout.addWidget(info_label)
        
        # 映射表格
        self.mapping_table = QTableWidget()
        self.mapping_table.setColumnCount(7)
        self.mapping_table.setHorizontalHeaderLabels([
            "IO类型", "IO编号", "GPIO引脚", "触发\输出方式", "调用作业", "描述", "操作"
        ])
        self.mapping_table.horizontalHeader().setStretchLastSection(True)
        
        # 设置表格行高
        self.mapping_table.verticalHeader().setDefaultSectionSize(80)   
        self.mapping_table.setAlternatingRowColors(True)  # 启用交替行颜色
        
        mapping_layout.addWidget(self.mapping_table)
        
        # 映射操作按钮
        mapping_btn_layout = QHBoxLayout()
        
        add_mapping_btn = QPushButton("添加映射")
        add_mapping_btn.clicked.connect(self.add_io_mapping)
        mapping_btn_layout.addWidget(add_mapping_btn)
        
        load_mapping_btn = QPushButton("加载配置")
        load_mapping_btn.setProperty("class", "info")
        load_mapping_btn.clicked.connect(self.load_io_mapping_from_file)
        mapping_btn_layout.addWidget(load_mapping_btn)
        
        save_mapping_btn = QPushButton("保存配置")
        save_mapping_btn.setProperty("class", "success")
        save_mapping_btn.clicked.connect(self.save_io_mapping)
        mapping_btn_layout.addWidget(save_mapping_btn)
        
        mapping_layout.addLayout(mapping_btn_layout)
        right_panel.addWidget(mapping_group)
        
        # 添加到主布局
        layout.addLayout(left_panel, 1)
        layout.addLayout(right_panel, 2)
        
        return widget
        
    def create_job_management_tab(self):
        """创建作业管理标签页"""
        widget = QWidget()
        
        # 创建水平分割器
        splitter = QSplitter(Qt.Horizontal)
        
        # 左侧：作业列表
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(5, 5, 5, 5)
        
        # 作业列表标题和操作按钮
        list_header_layout = QHBoxLayout()
        list_title = QLabel("作业列表")
        list_title.setFont(QFont("Microsoft YaHei UI", 12, QFont.Bold))
        list_header_layout.addWidget(list_title)
        list_header_layout.addStretch()
        
        
        left_layout.addLayout(list_header_layout)
        
        # 作业列表（简化版，只显示名称）
        self.job_list_widget = QTableWidget()
        self.job_list_widget.setColumnCount(1)
        self.job_list_widget.setHorizontalHeaderLabels(["作业名称"])
        self.job_list_widget.horizontalHeader().setStretchLastSection(True)
        self.job_list_widget.setSelectionBehavior(QTableWidget.SelectRows)
        self.job_list_widget.setAlternatingRowColors(True)
        self.job_list_widget.verticalHeader().setVisible(False)
        left_layout.addWidget(self.job_list_widget)
        
        # 导入操作按钮
        import_btn_layout = QVBoxLayout()
        
        self.import_job_btn = QPushButton("导入示教程序")
        self.import_job_btn.setProperty("class", "success")
        self.import_job_btn.clicked.connect(self.import_teaching_program)
        import_btn_layout.addWidget(self.import_job_btn)
        
        self.add_job_btn = QPushButton("添加作业文件")
        self.add_job_btn.clicked.connect(self.add_job_from_file)
        import_btn_layout.addWidget(self.add_job_btn)
        
        self.create_job_btn = QPushButton("创建作业")
        self.create_job_btn.setProperty("class", "info")
        self.create_job_btn.clicked.connect(self.create_new_job)
        import_btn_layout.addWidget(self.create_job_btn)
        
        self.remove_job_btn = QPushButton("删除作业")
        self.remove_job_btn.setProperty("class", "danger")
        self.remove_job_btn.clicked.connect(self.remove_job)
        import_btn_layout.addWidget(self.remove_job_btn)
        
        left_layout.addLayout(import_btn_layout)
        
        # 右侧：作业详细信息
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 5, 5, 5)
        
        # 作业信息组
        job_info_group = QGroupBox("作业信息")
        job_info_layout = QVBoxLayout(job_info_group)
        
        # 作业基本信息
        info_form_layout = QFormLayout()
        
        self.job_name_edit = QLineEdit()
        self.job_name_edit.setPlaceholderText("输入作业名称")
        info_form_layout.addRow("作业名称:", self.job_name_edit)
        
        self.job_status_label = QLabel("就绪")
        self.job_status_label.setProperty("class", "status-warning")
        info_form_layout.addRow("状态:", self.job_status_label)
        
        self.job_desc_edit = QLineEdit()
        self.job_desc_edit.setPlaceholderText("从示教器导入的动作序列，包含3个运动步骤")
        info_form_layout.addRow("描述:", self.job_desc_edit)
        
        # 作业统计信息
        stats_layout = QHBoxLayout()
        
        self.total_steps_label = QLabel("步骤数: 0")
        stats_layout.addWidget(self.total_steps_label)
        
        stats_layout.addStretch()
        
        self.test_job_btn = QPushButton("测试作业")
        self.test_job_btn.setProperty("class", "warning")
        self.test_job_btn.clicked.connect(self.test_current_job)
        stats_layout.addWidget(self.test_job_btn)
        
        self.save_job_btn = QPushButton("保存作业")
        self.save_job_btn.setProperty("class", "success")
        self.save_job_btn.clicked.connect(self.save_current_job)
        stats_layout.addWidget(self.save_job_btn)
        
        info_form_layout.addRow(stats_layout)
        job_info_layout.addLayout(info_form_layout)
        right_layout.addWidget(job_info_group)
        
        # 作业步骤组
        steps_group = QGroupBox("作业步骤")
        steps_layout = QVBoxLayout(steps_group)
        
        # 步骤操作按钮
        steps_btn_layout = QHBoxLayout()
        
        self.add_step_btn = QPushButton("添加步骤")
        self.add_step_btn.setProperty("class", "success")
        self.add_step_btn.clicked.connect(self.add_step)
        steps_btn_layout.addWidget(self.add_step_btn)
        
        self.insert_step_btn = QPushButton("插入步骤")
        self.insert_step_btn.clicked.connect(self.insert_step)
        steps_btn_layout.addWidget(self.insert_step_btn)
        
        self.edit_step_btn = QPushButton("编辑步骤")
        self.edit_step_btn.clicked.connect(self.edit_step)
        steps_btn_layout.addWidget(self.edit_step_btn)
        
        self.delete_step_btn = QPushButton("删除步骤")
        self.delete_step_btn.setProperty("class", "danger")
        self.delete_step_btn.clicked.connect(self.delete_step)
        steps_btn_layout.addWidget(self.delete_step_btn)
        
        steps_btn_layout.addStretch()
        steps_layout.addLayout(steps_btn_layout)
        
        # 步骤列表表格
        self.steps_table = QTableWidget()
        self.steps_table.setColumnCount(3)
        self.steps_table.setHorizontalHeaderLabels(["步骤", "类型", "描述"])
        self.steps_table.horizontalHeader().setStretchLastSection(True)
        self.steps_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.steps_table.setAlternatingRowColors(True)
        # 禁用表格编辑功能
        self.steps_table.setEditTriggers(QTableWidget.NoEditTriggers)
        steps_layout.addWidget(self.steps_table)
        
        right_layout.addWidget(steps_group)
        
        # 添加到分割器
        splitter.addWidget(left_widget)
        splitter.addWidget(right_widget)
        
        # 设置分割比例 (左:右 = 1:2)
        splitter.setSizes([300, 600])
        splitter.setStretchFactor(0, 0)  # 左侧固定宽度
        splitter.setStretchFactor(1, 1)  # 右侧可伸缩
        
        # 主布局
        main_layout = QHBoxLayout(widget)
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.addWidget(splitter)
        
        return widget
        
    def create_execution_status_tab(self):
        """创建执行状态标签页"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 执行状态组
        exec_status_group = QGroupBox("执行状态")
        exec_status_layout = QVBoxLayout(exec_status_group)
        
        # 当前作业信息
        current_job_layout = QGridLayout()
        
        current_job_layout.addWidget(QLabel("当前作业:"), 0, 0)
        self.current_job_label = QLabel("-")
        self.current_job_label.setStyleSheet("font-weight: bold; color: #2c3e50;")
        current_job_layout.addWidget(self.current_job_label, 0, 1)
        
        current_job_layout.addWidget(QLabel("状态:"), 0, 2)
        self.execution_status_label = QLabel("就绪")
        self.execution_status_label.setStyleSheet("""
            QLabel {
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                background-color: #f39c12;
                color: white;
            }
        """)
        current_job_layout.addWidget(self.execution_status_label, 0, 3)
        
        current_job_layout.addWidget(QLabel("当前步骤:"), 1, 0)
        self.current_step_label = QLabel("-")
        self.current_step_label.setStyleSheet("color: #34495e;")
        current_job_layout.addWidget(self.current_step_label, 1, 1, 1, 3)
        
        exec_status_layout.addLayout(current_job_layout)
        
        # 进度条
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("进度:"))
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 8px;
                text-align: center;
                font-weight: bold;
                height: 20px;
                background-color: #ecf0f1;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 7px;
            }
        """)
        progress_layout.addWidget(self.progress_bar)
        self.progress_label = QLabel("0%")
        self.progress_label.setStyleSheet("font-weight: bold; color: #2c3e50; min-width: 40px;")
        progress_layout.addWidget(self.progress_label)
        exec_status_layout.addLayout(progress_layout)
        
        # 控制按钮
        control_layout = QHBoxLayout()
        
        self.stop_job_btn = QPushButton("停止作业")
        self.stop_job_btn.setStyleSheet("""
            QPushButton {
                background-color: #e74c3c;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                font-weight: bold;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #c0392b;
            }
            QPushButton:disabled {
                background-color: #bdc3c7;
                color: #7f8c8d;
            }
        """)
        self.stop_job_btn.clicked.connect(self.stop_current_job)
        self.stop_job_btn.setEnabled(False)
        control_layout.addWidget(self.stop_job_btn)
        
        control_layout.addStretch()
        exec_status_layout.addLayout(control_layout)
        
        layout.addWidget(exec_status_group)
        
        # 执行日志组
        log_group = QGroupBox("执行日志")
        log_layout = QVBoxLayout(log_group)
        
        self.execution_log = QTextEdit()
        self.execution_log.setReadOnly(True)
        self.execution_log.setMaximumHeight(400)
        self.execution_log.setStyleSheet("""
            QTextEdit {
                background-color: #2c3e50;
                color: #ecf0f1;
                border: 1px solid #34495e;
                border-radius: 6px;
                padding: 8px;
                font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
                font-size: 12px;
                line-height: 1.4;
            }
        """)
        log_layout.addWidget(self.execution_log)
        
        # 日志操作按钮
        log_btn_layout = QHBoxLayout()
        
        clear_log_btn = QPushButton("清空日志")
        clear_log_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                padding: 6px 12px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        clear_log_btn.clicked.connect(self.clear_execution_log)
        log_btn_layout.addWidget(clear_log_btn)
        
        log_btn_layout.addStretch()
        log_layout.addLayout(log_btn_layout)
        
        layout.addWidget(log_group)
        
        # 添加示例日志
        self.add_log_entry("准备就绪")

        
        return widget
        
    def connect_esp32(self):
        """连接ESP32"""
        try:
            port = self.port_combo.currentText()
            baudrate = int(self.baudrate_combo.currentText())
            
            # 创建ESP32控制器
            self.esp32_controller = ESP32IOController(port, baudrate)
            if not self.esp32_controller.connect():
                raise Exception("ESP32连接失败")
            
            # 更新UI状态
            self.connect_btn.setEnabled(False)
            self.disconnect_btn.setEnabled(True)
            self.esp32_status_label.setText("已连接")
            self.esp32_status_label.setProperty("class", "status-connected")
            self.esp32_status_label.style().unpolish(self.esp32_status_label)
            self.esp32_status_label.style().polish(self.esp32_status_label)
            
            # 启动IO状态监控
            self.start_io_monitoring()
            
            # 更新IO状态显示
            self.refresh_io_display()
            
            self.add_log_entry(f"ESP32连接成功: {port} @ {baudrate}")
            
        except Exception as e:
            QMessageBox.critical(self, "连接失败", f"无法连接到ESP32:\n{str(e)}")
            self.add_log_entry(f"ESP32连接失败: {str(e)}")
            
    def disconnect_esp32(self):
        """断开ESP32连接"""
        try:
            # 停止IO监控
            self.stop_io_monitoring()
            
            if self.esp32_controller:
                self.esp32_controller.disconnect()
                self.esp32_controller = None
            
            # 更新UI状态
            self.connect_btn.setEnabled(True)
            self.disconnect_btn.setEnabled(False)
            self.esp32_status_label.setText("未连接")
            self.esp32_status_label.setProperty("class", "status-disconnected")
            self.esp32_status_label.style().unpolish(self.esp32_status_label)
            self.esp32_status_label.style().polish(self.esp32_status_label)
            
            # 清除IO状态并更新显示
            self.di_states = [False] * 8
            self.do_states = [False] * 8
            self.refresh_io_display()
            
            self.add_log_entry("ESP32连接已断开")
            
        except Exception as e:
            QMessageBox.critical(self, "断开失败", f"断开ESP32连接时出错:\n{str(e)}")
            
    def start_io_monitoring(self):
        """启动IO状态监控"""
        if self.io_monitor_thread and self.io_monitor_thread.is_alive():
            return
            
        self.stop_monitoring = False
        self.io_monitor_thread = threading.Thread(target=self.io_monitor_loop, daemon=True)
        self.io_monitor_thread.start()
        
    def stop_io_monitoring(self):
        """停止IO状态监控"""
        self.stop_monitoring = True
        if self.io_monitor_thread:
            self.io_monitor_thread.join(timeout=1.0)
            
    def io_monitor_loop(self):
        """IO监控循环"""
        while not self.stop_monitoring:
            try:
                if self.esp32_controller:
                    # 查询传统DI状态（向后兼容）
                    new_di_states = self.esp32_controller.read_di_states()
                    if new_di_states is not None:
                        self.di_states = new_di_states
                    
                    # 查询IO状态
                    self.update_gpio_states()
                    
                    # 更新UI显示
                    self.update_di_display()
                    self.update_do_display()
                    
                    # 检查触发条件
                    if self.is_external_mode:
                        self.check_io_triggers()
                    else:
                        # 调试信息：提醒用户需要外部控制模式
                        pass  # 避免频繁日志
                        
                time.sleep(0.02)  # 20ms查询间隔
                
            except Exception as e:
                self.add_log_entry(f"IO监控错误: {str(e)}")
                time.sleep(0.1)
                
    def update_gpio_states(self):
        """更新IO状态（使用固定GPIO映射）"""
        try:
            if not self.esp32_controller:
                return
                
            # 读取所有DI状态（使用ESP32固件的READ_DI命令）
            di_states = self.esp32_controller.read_di_states()
            if di_states is not None:
                self.di_states = di_states
            
            # 读取所有DO状态（使用ESP32固件的READ_DO命令）
            do_states = self.esp32_controller.read_do_states()
            if do_states is not None:
                self.do_states = do_states
                            
        except Exception as e:
            # 静默处理GPIO状态读取错误，避免日志过多
            pass
                
    def update_di_display(self):
        """更新DI状态显示（智能颜色显示）"""
        for i, state in enumerate(self.di_states):
            # 检查ESP32连接状态
            if not self.esp32_controller or not self.esp32_controller.is_connected:
                # 未连接：显示断开状态
                color = "#cccccc"  # 浅灰色
                description = "ESP32未连接"
                symbol = "●"  # 实心圆点
            else:
                color, description = self._get_di_display_color(i, state)
                symbol = "●"  # 实心圆点
            
            # 更新LED样式的指示器
            self.di_indicators[i].setText("●")
            
            # 根据状态设置LED颜色和效果
            if not self.esp32_controller or not self.esp32_controller.is_connected:
                # 未连接：灰色LED
                led_style = """
                    QLabel {
                        background-color: #6c757d;
                        border: 2px solid #495057;
                        border-radius: 10px;
                        color: white;
                        font-size: 10px;
                        font-weight: bold;
                    }
                """
            else:
                # 根据状态设置不同的LED颜色
                if color == "blue":
                    # 蓝色LED（高电平）- 使用渐变模拟发光
                    led_style = """
                        QLabel {
                            background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.8,
                                stop: 0 #4dabf7, stop: 0.7 #007bff, stop: 1 #0056b3);
                            border: 2px solid #0056b3;
                            border-radius: 10px;
                            color: white;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    """
                elif color == "green":
                    # 绿色LED（低电平）- 使用渐变模拟发光
                    led_style = """
                        QLabel {
                            background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.8,
                                stop: 0 #51cf66, stop: 0.7 #28a745, stop: 1 #1e7e34);
                            border: 2px solid #1e7e34;
                            border-radius: 10px;
                            color: white;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    """
                elif color == "red":
                    # 红色LED（错误）- 使用渐变模拟发光
                    led_style = """
                        QLabel {
                            background: qradialgradient(cx: 0.5, cy: 0.5, radius: 0.8,
                                stop: 0 #ff6b6b, stop: 0.7 #dc3545, stop: 1 #bd2130);
                            border: 2px solid #bd2130;
                            border-radius: 10px;
                            color: white;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    """
                else:
                    # 灰色LED（未配置）
                    led_style = """
                        QLabel {
                            background-color: #6c757d;
                            border: 2px solid #495057;
                            border-radius: 10px;
                            color: white;
                            font-size: 10px;
                            font-weight: bold;
                        }
                    """
            
            self.di_indicators[i].setStyleSheet(led_style)
            
            # 更新工具提示
            gpio_pin = self.DI_GPIO_MAP.get(i, 0)
            self.di_indicators[i].setToolTip(f"DI{i} (GPIO{gpio_pin}): {description}")
    
    def _get_di_display_color(self, di_number: int, state: bool) -> tuple:
        """
        获取DI显示颜色和描述
        
        返回: (颜色, 描述)
        - 蓝色: 已配置且高电平
        - 绿色: 已配置且低电平  
        - 红色: 已配置但GPIO配置错误
        - 灰色: 未配置
        """
        # 检查是否在IO映射中配置了此DI
        configured_info = self._get_configured_di_info(di_number)
        
        if not configured_info:
            # 未配置：灰色
            return "gray", "未配置"
        
        # 已配置：检查GPIO是否匹配
        configured_gpio = configured_info['gpio']
        expected_gpio = self.DI_GPIO_MAP.get(di_number, 0)
        
        if configured_gpio != expected_gpio:
            # GPIO配置错误：红色
            return "red", f"GPIO配置错误 (配置:{configured_gpio}, 实际:{expected_gpio})"
        
        # GPIO配置正确：根据电平状态显示
        if state:
            return "blue", f"高电平 - {configured_info['description']}"
        else:
            return "green", f"低电平 - {configured_info['description']}"
    
    def _get_configured_di_info(self, di_number: int) -> dict:
        """获取已配置的DI信息"""
        for row in range(self.mapping_table.rowCount()):
            io_type_combo = self.mapping_table.cellWidget(row, 0)
            io_number_combo = self.mapping_table.cellWidget(row, 1)
            gpio_combo = self.mapping_table.cellWidget(row, 2)
            job_combo = self.mapping_table.cellWidget(row, 4)
            desc_item = self.mapping_table.item(row, 5)
            
            if (io_type_combo and io_type_combo.currentText() == "DI" and
                io_number_combo and int(io_number_combo.currentText()) == di_number):
                
                return {
                    'gpio': int(gpio_combo.currentText()) if gpio_combo else 0,
                    'job_name': job_combo.currentText() if job_combo else "",
                    'description': desc_item.text() if desc_item else f"DI{di_number}"
                }
        
        return None
    
    def update_do_display(self):
        """更新DO状态显示（智能颜色显示）"""
        for i, state in enumerate(self.do_states):
            # 检查ESP32连接状态
            if not self.esp32_controller or not self.esp32_controller.is_connected:
                # 未连接：显示断开状态
                color = "#cccccc"  # 浅灰色
                description = "ESP32未连接"
                # 禁用复选框
                self.do_checkboxes[i].setEnabled(False)
            else:
                color, description = self._get_do_display_color(i, state)
                # 启用复选框
                self.do_checkboxes[i].setEnabled(True)
                # 同步复选框状态（不触发信号）
                self.do_checkboxes[i].blockSignals(True)
                self.do_checkboxes[i].setChecked(state)
                self.do_checkboxes[i].blockSignals(False)
            
            # 更新开关样式的复选框
            if not self.esp32_controller or not self.esp32_controller.is_connected:
                # 未连接：禁用样式
                switch_style = """
                    QCheckBox::indicator {
                        width: 30px;
                        height: 16px;
                        border-radius: 8px;
                        background-color: #e9ecef;
                        border: 2px solid #dee2e6;
                    }
                """
            else:
                # 根据状态和配置设置不同的开关颜色
                if color == "blue":
                    # 蓝色开关（已配置，高电平）
                    switch_style = """
                        QCheckBox::indicator {
                            width: 30px;
                            height: 16px;
                            border-radius: 8px;
                            background-color: #6c757d;
                            border: 2px solid #495057;
                        }
                        QCheckBox::indicator:checked {
                            background-color: #007bff;
                            border-color: #0056b3;
                        }
                    """
                elif color == "green":
                    # 绿色开关（已配置，低电平）
                    switch_style = """
                        QCheckBox::indicator {
                            width: 30px;
                            height: 16px;
                            border-radius: 8px;
                            background-color: #28a745;
                            border: 2px solid #1e7e34;
                        }
                        QCheckBox::indicator:checked {
                            background-color: #28a745;
                            border-color: #1e7e34;
                        }
                    """
                elif color == "red":
                    # 红色开关（配置错误）
                    switch_style = """
                        QCheckBox::indicator {
                            width: 30px;
                            height: 16px;
                            border-radius: 8px;
                            background-color: #dc3545;
                            border: 2px solid #bd2130;
                        }
                        QCheckBox::indicator:checked {
                            background-color: #dc3545;
                            border-color: #bd2130;
                        }
                    """
                else:
                    # 默认开关（未配置）
                    switch_style = """
                        QCheckBox::indicator {
                            width: 30px;
                            height: 16px;
                            border-radius: 8px;
                            background-color: #6c757d;
                            border: 2px solid #495057;
                        }
                        QCheckBox::indicator:checked {
                            background-color: #28a745;
                            border-color: #1e7e34;
                        }
                    """
            
            self.do_checkboxes[i].setStyleSheet(switch_style)
            # 更新工具提示
            gpio_pin = self.DO_GPIO_MAP.get(i, 0)
            self.do_checkboxes[i].setToolTip(f"DO{i} (GPIO{gpio_pin}): {description}")
    
    def _get_do_display_color(self, do_number: int, state: bool) -> tuple:
        """
        获取DO显示颜色和描述
        
        返回: (颜色, 描述)
        - 蓝色: 已配置且高电平
        - 绿色: 已配置且低电平  
        - 红色: 已配置但GPIO配置错误
        - 灰色: 未配置
        """
        # 检查是否在IO映射中配置了此DO
        configured_info = self._get_configured_do_info(do_number)
        
        if not configured_info:
            # 未配置：灰色
            return "gray", "未配置"
        
        # 已配置：检查GPIO是否匹配
        configured_gpio = configured_info['gpio']
        expected_gpio = self.DO_GPIO_MAP.get(do_number, 0)
        
        if configured_gpio != expected_gpio:
            # GPIO配置错误：红色
            return "red", f"GPIO配置错误 (配置:{configured_gpio}, 实际:{expected_gpio})"
        
        # GPIO配置正确：根据电平状态显示
        if state:
            return "blue", f"高电平 - {configured_info['description']}"
        else:
            return "green", f"低电平 - {configured_info['description']}"
    
    def _get_configured_do_info(self, do_number: int) -> dict:
        """获取已配置的DO信息"""
        for row in range(self.mapping_table.rowCount()):
            io_type_combo = self.mapping_table.cellWidget(row, 0)
            io_number_combo = self.mapping_table.cellWidget(row, 1)
            gpio_combo = self.mapping_table.cellWidget(row, 2)
            job_combo = self.mapping_table.cellWidget(row, 4)
            desc_item = self.mapping_table.item(row, 5)
            
            if (io_type_combo and io_type_combo.currentText() == "DO" and
                io_number_combo and int(io_number_combo.currentText()) == do_number):
                
                return {
                    'gpio': int(gpio_combo.currentText()) if gpio_combo else 0,
                    'job_name': job_combo.currentText() if job_combo else "",
                    'description': desc_item.text() if desc_item else f"DO{do_number}"
                }
        
        return None
    
    def refresh_io_display(self):
        """刷新IO状态显示（在配置变化后调用）"""
        self.update_di_display()
        self.update_do_display()
                
    def set_do_state(self, pin: int, state: bool):
        """设置DO状态"""
        try:
            if self.esp32_controller:
                # 使用ESP32固件的DO控制（固件内部处理GPIO映射）
                if self.esp32_controller.set_do_state(pin, state):
                    self.do_states[pin] = state
                    # 查找用户配置的GPIO引脚用于日志显示
                    configured_gpio = self.get_configured_gpio_for_do(pin)
                    self.add_log_entry(f"设置DO{pin}(用户配置GPIO{configured_gpio}) = {'HIGH' if state else 'LOW'}")
                else:
                    raise Exception("ESP32响应失败")
        except Exception as e:
            QMessageBox.critical(self, "DO控制失败", f"设置DO{pin}状态失败:\n{str(e)}")
            
    def get_configured_gpio_for_do(self, do_number: int) -> int:
        """获取用户为指定DO配置的GPIO引脚"""
        # 遍历映射表格，查找对应DO的GPIO配置
        for row in range(self.mapping_table.rowCount()):
            io_type_combo = self.mapping_table.cellWidget(row, 0)
            io_number_combo = self.mapping_table.cellWidget(row, 1)
            gpio_combo = self.mapping_table.cellWidget(row, 2)
            
            if (io_type_combo and io_type_combo.currentText() == "DO" and
                io_number_combo and int(io_number_combo.currentText()) == do_number and
                gpio_combo):
                return int(gpio_combo.currentText())
        
        # 如果没找到配置，返回固件默认的GPIO
        return self.DO_GPIO_MAP.get(do_number, 0)
            
    def check_io_triggers(self):
        """检查IO触发条件"""
        # 调试信息：记录触发检查
        trigger_count = 0
        
        # 遍历IO映射配置，建立GPIO到状态的映射关系
        for row in range(self.mapping_table.rowCount()):
            io_type_combo = self.mapping_table.cellWidget(row, 0)
            io_number_combo = self.mapping_table.cellWidget(row, 1)
            gpio_combo = self.mapping_table.cellWidget(row, 2)
            trigger_combo = self.mapping_table.cellWidget(row, 3)
            job_combo = self.mapping_table.cellWidget(row, 4)
            
            if (io_type_combo and io_type_combo.currentText() == "DI" and 
                io_number_combo and gpio_combo and trigger_combo and job_combo):
                
                io_number = int(io_number_combo.currentText())
                gpio_pin = int(gpio_combo.currentText())
                trigger_method = trigger_combo.currentText()
                job_name = job_combo.currentText()
                
                # 如果作业名称为空或为"无"，跳过触发
                if not job_name or job_name == "无":
                    continue
                
                # 获取对应DI的状态（通过ESP32固件的DI编号）
                if 0 <= io_number < 8:
                    current_state = self.di_states[io_number]
                    previous_state = self.previous_di_states[io_number]
                    
                    # 检查触发条件
                    trigger_map = {
                        "上升沿": "rising_edge",
                        "下降沿": "falling_edge", 
                        "高电平": "high_level",
                        "低电平": "low_level"
                    }
                    trigger_type = trigger_map.get(trigger_method, "rising_edge")
                    
                    if trigger_type == "rising_edge":
                        # 上升沿触发
                        if current_state and not previous_state:
                            self.add_log_entry(f"🔥 DI{io_number}上升沿触发 -> {job_name}")
                            self.trigger_job(job_name)
                            trigger_count += 1
                    elif trigger_type == "falling_edge":
                        # 下降沿触发
                        if not current_state and previous_state:
                            self.add_log_entry(f"🔥 DI{io_number}下降沿触发 -> {job_name}")
                            self.trigger_job(job_name)
                            trigger_count += 1
                    elif trigger_type == "high_level":
                        # 高电平触发
                        if current_state:
                            self.add_log_entry(f"🔥 DI{io_number}高电平触发 -> {job_name}")
                            self.trigger_job(job_name)
                            trigger_count += 1
                    elif trigger_type == "low_level":
                        # 低电平触发
                        if not current_state:
                            self.add_log_entry(f"🔥 DI{io_number}低电平触发 -> {job_name}")
                            self.trigger_job(job_name)
                            trigger_count += 1
                    
        # 更新上一次状态
        self.previous_di_states = self.di_states.copy()
        
    def trigger_job(self, job_name: str):
        """触发作业执行"""
        if job_name not in self.jobs:
            self.add_log_entry(f"❌ 作业 {job_name} 不存在")
            return
            
        # 检查是否为紧急停止作业
        job_data = self.jobs.get(job_name, {})
        is_emergency_stop = False
        
        # 检查作业步骤中是否包含紧急停止
        steps = job_data.get("steps", [])
        for step in steps:
            if step.get("type") == "emergency_stop":
                is_emergency_stop = True
                break
        
        # 如果当前有作业在执行
        if self.current_job:
            if is_emergency_stop:
                # 紧急停止作业可以中断当前作业
                self.add_log_entry(f"🛑 紧急停止作业 {job_name} 触发，中断当前作业 {self.current_job}")
                self.stop_current_job()  # 先停止当前作业
            else:
                # 普通作业不能中断当前作业
                self.add_log_entry(f"❌ 作业 {job_name} 触发失败: 当前有作业正在执行")
                return
            
        self.add_log_entry(f"🔥 触发作业: {job_name}")
        self.execute_job(job_name)
        
    def execute_job(self, job_name: str):
        """执行作业"""
        if job_name not in self.jobs:
            QMessageBox.warning(self, "作业不存在", f"作业 '{job_name}' 不存在")
            return
        
        # 清理之前的线程
        self._cleanup_job_thread()
            
        self.current_job = job_name
        self.current_job_label.setText(job_name)
        self.execution_status_label.setText("执行中")
        self.execution_status_label.setStyleSheet("""
            QLabel {
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                background-color: #3498db;
                color: white;
            }
        """)
        self.stop_job_btn.setEnabled(True)
        
        # 在新线程中执行作业
        self.job_thread = QThread()
        self.job_worker = JobExecutionWorker()
        self.job_worker.moveToThread(self.job_thread)
        
        # 连接信号
        self.job_worker.progress_updated.connect(self.on_job_progress_updated)
        self.job_worker.log_message.connect(self.add_log_entry)
        self.job_worker.job_completed.connect(self.on_job_completed)
        self.job_worker.job_error.connect(self.on_job_error)
        
        # 连接线程信号
        self.job_thread.started.connect(self.job_worker.execute_job)
        # 让Qt自动管理对象生命周期，不手动调用deleteLater
        
        # 设置作业数据和控制组件
        self.job_worker.set_job_data(job_name, self.jobs)
        
        # 传递控制组件
        try:
            # 调试信息：显示电机连接状态
            if self.motors:
                self.add_log_entry(f"✅ 传递给作业执行器的电机: {list(self.motors.keys())}")
            else:
                self.add_log_entry("⚠️ 警告：没有电机信息传递给作业执行器")
            
            # 传递控制组件
            self.job_worker.set_control_components(
                self.motors, 
                self.claw_controller, 
                self.kinematics, 
                self.motor_config_manager,
                self.esp32_controller
            )
            self.add_log_entry("控制组件已传递给作业执行器")
        except Exception as e:
            self.add_log_entry(f"设置控制组件失败: {e}")
        
        self.job_thread.start()
        
    @pyqtSlot(int, str)
    def on_job_progress_updated(self, progress: int, step_desc: str):
        """作业进度更新处理"""
        self.progress_bar.setValue(progress)
        self.progress_label.setText(f"{progress}%")
        self.current_step_label.setText(step_desc)
        
    @pyqtSlot(str)
    def on_job_completed(self, job_name: str):
        """作业完成处理"""
        self.add_log_entry(f"作业 {job_name} 执行完成")
        
        self._reset_job_status()
        
    @pyqtSlot(str)
    def on_job_error(self, error_msg: str):
        """作业错误处理"""
        self.add_log_entry(f"作业执行错误: {error_msg}")
        
        self._reset_job_status()
        
    def _reset_job_status(self):
        """重置作业状态"""
        # 清理线程资源
        self._cleanup_job_thread()
        
        self.current_job = None
        self.current_job_label.setText("-")
        self.execution_status_label.setText("就绪")
        self.execution_status_label.setStyleSheet("""
            QLabel {
                padding: 4px 12px;
                border-radius: 12px;
                font-weight: bold;
                background-color: #f39c12;
                color: white;
            }
        """)
        self.stop_job_btn.setEnabled(False)
        self.progress_bar.setValue(0)
        self.progress_label.setText("0%")
        self.current_step_label.setText("-")
        
    def _cleanup_job_thread(self):
        """清理作业执行线程"""
        try:
            # 检查并停止工作线程
            if hasattr(self, 'job_worker') and self.job_worker is not None:
                try:
                    # 检查对象是否还有效
                    if hasattr(self.job_worker, 'stop_job'):
                        self.job_worker.stop_job()
                except RuntimeError:
                    # 对象已被删除，忽略错误
                    pass
                
            # 检查并停止线程
            if hasattr(self, 'job_thread') and self.job_thread is not None:
                try:
                    if self.job_thread.isRunning():
                        # 等待线程结束
                        self.job_thread.quit()
                        if not self.job_thread.wait(3000):  # 等待3秒
                            self.add_log_entry("⚠️ 线程未能正常结束，强制终止")
                            self.job_thread.terminate()
                            self.job_thread.wait()
                except RuntimeError:
                    # 线程对象已被删除，忽略错误
                    pass
                
            # 清理引用（不调用deleteLater，让Qt自动管理）
            self.job_worker = None
            self.job_thread = None
                
        except Exception as e:
            # 只在调试时显示错误，正常运行时忽略
            pass
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            if self.motor_config_manager:
                # 重新加载配置管理器的配置
                self.motor_config_manager.config = self.motor_config_manager.load_config()
                
                # 如果插补执行器已初始化，需要重新初始化以使用新的配置
                if hasattr(self, 'cartesian_executor') or hasattr(self, 'joint_executor'):
                    self._initialize_interpolation_executors()
            else:
                print("⚠️ IO控制控件：电机配置管理器不可用")
        except Exception as e:
            print(f"⚠ IO控制控件：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            if KINEMATICS_AVAILABLE:
                # 重新创建运动学实例，使用最新的DH参数配置
                self.kinematics = create_configured_kinematics()
                
                # 如果插补执行器已初始化，需要重新初始化以使用新的运动学配置
                if hasattr(self, 'cartesian_executor') or hasattr(self, 'joint_executor'):
                    self._initialize_interpolation_executors()
                    print("✅ IO控制控件：插补执行器已使用新的运动学配置重新初始化")
            else:
                print("⚠️ 运动学模块不可用，无法重新加载DH参数配置")
        except Exception as e:
            print(f"⚠ IO控制控件：重新加载DH参数配置失败: {e}")
            self.kinematics = None
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止IO监控
            self.stop_monitoring = True
            
            # 清理作业执行线程
            self._cleanup_job_thread()
            
            # 断开ESP32连接
            if self.esp32_controller:
                self.esp32_controller.disconnect()
                
            event.accept()
        except Exception as e:
            print(f"关闭窗口时出错: {e}")
            event.accept()
            
    def stop_current_job(self):
        """停止当前作业"""
        if self.current_job and self.job_worker:
            self.add_log_entry(f"🛑 停止当前作业: {self.current_job}")
            self.job_worker.stop_job()
            
            # 立即清理作业状态
            self._cleanup_job_thread()
            
            # 重置状态
            self.current_job = None
            self.current_job_label.setText("无")
            self.execution_status_label.setText("已停止")
            self.execution_status_label.setStyleSheet("""
                QLabel {
                    padding: 4px 12px;
                    border-radius: 12px;
                    font-weight: bold;
                    background-color: #e74c3c;
                    color: white;
                }
            """)
            self.stop_job_btn.setEnabled(False)
            self.progress_bar.setValue(0)
            self.progress_label.setText("0%")
            self.current_step_label.setText("-")
            
            self.add_log_entry("✅ 作业执行已停止")
            
    def toggle_external_mode(self):
        """切换外部控制模式"""
        if not self.esp32_controller:
            QMessageBox.warning(self, "未连接", "请先连接ESP32")
            return
            
        self.is_external_mode = not self.is_external_mode
        
        if self.is_external_mode:
            self.external_mode_btn.setText("退出外部控制模式")
            self.external_mode_btn.setProperty("class", "danger")
            self.external_mode_status.setText("外部控制模式")
            self.external_mode_status.setProperty("class", "status-connected")
            self.add_log_entry("进入外部控制模式")
        else:
            self.external_mode_btn.setText("进入外部控制模式")
            self.external_mode_btn.setProperty("class", "warning")
            self.external_mode_status.setText("手动控制模式")
            self.external_mode_status.setProperty("class", "status-disconnected")
            self.add_log_entry("退出外部控制模式")
            
        # 刷新样式
        self.external_mode_btn.style().unpolish(self.external_mode_btn)
        self.external_mode_btn.style().polish(self.external_mode_btn)
        self.external_mode_status.style().unpolish(self.external_mode_status)
        self.external_mode_status.style().polish(self.external_mode_status)
        
    def add_io_mapping(self):
        """添加IO映射"""
        row = self.mapping_table.rowCount()
        self.mapping_table.insertRow(row)
        
        # IO类型选择
        io_type_combo = QComboBox()
        io_type_combo.addItems(["DI", "DO"])
        io_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_io_type_changed(r, text))
        self.mapping_table.setCellWidget(row, 0, io_type_combo)
        
        # IO编号选择
        io_number_combo = QComboBox()
        io_number_combo.addItems([str(i) for i in range(8)])
        self.mapping_table.setCellWidget(row, 1, io_number_combo)
        
        # GPIO引脚选择（可选择ESP32可用GPIO）
        gpio_combo = QComboBox()
        # ESP32可用GPIO引脚（排除一些特殊用途的引脚）
        available_gpios = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
        gpio_combo.addItems([str(gpio) for gpio in available_gpios])
        # 默认选择DI0的GPIO
        gpio_combo.setCurrentText("1")
        self.mapping_table.setCellWidget(row, 2, gpio_combo)
        
        # 触发方式选择
        trigger_combo = QComboBox()
        trigger_combo.addItems(["上升沿", "下降沿", "高电平", "低电平"])
        self.mapping_table.setCellWidget(row, 3, trigger_combo)
        
        # 作业选择
        job_combo = QComboBox()
        job_items = ["无"] + list(self.jobs.keys())
        job_combo.addItems(job_items)
        # 默认选择"无"
        job_combo.setCurrentText("无")
        self.mapping_table.setCellWidget(row, 4, job_combo)
        
        # 描述
        self.mapping_table.setItem(row, 5, QTableWidgetItem(""))
        
        # 删除按钮
        delete_btn = QPushButton("删除")
        delete_btn.setProperty("class", "danger")
        delete_btn.clicked.connect(lambda checked, r=row: self.remove_mapping_row(r))
        self.mapping_table.setCellWidget(row, 6, delete_btn)
        
    def on_io_type_changed(self, row: int, io_type: str):
        """IO类型改变时的处理"""
        trigger_combo = self.mapping_table.cellWidget(row, 3)
        job_combo = self.mapping_table.cellWidget(row, 4)
        io_number_combo = self.mapping_table.cellWidget(row, 1)
        
        if trigger_combo:
            trigger_combo.clear()
            if io_type == "DI":
                # DI支持的触发方式
                trigger_combo.addItems(["上升沿", "下降沿", "高电平", "低电平"])
                # DI可以选择作业
                if job_combo:
                    job_combo.setEnabled(True)
            else:  # DO
                # DO不需要触发方式，显示"无"且不可选择
                trigger_combo.addItems(["无"])
                trigger_combo.setEnabled(False)
                # DO不可选择作业
                if job_combo:
                    job_combo.setCurrentText("无")
                    job_combo.setEnabled(False)
        
                    
        
    def get_configured_dos(self):
        """获取已配置的DO列表"""
        configured_dos = []
        
        # 遍历映射表格，查找DO类型的配置
        for row in range(self.mapping_table.rowCount()):
            io_type_combo = self.mapping_table.cellWidget(row, 0)
            io_number_combo = self.mapping_table.cellWidget(row, 1)
            gpio_combo = self.mapping_table.cellWidget(row, 2)
            desc_item = self.mapping_table.item(row, 5)
            
            if io_type_combo and io_type_combo.currentText() == "DO":
                io_number = int(io_number_combo.currentText()) if io_number_combo else 0
                gpio_pin = int(gpio_combo.currentText()) if gpio_combo else 0
                description = desc_item.text() if desc_item else ""
                
                do_info = {
                    'name': f"DO{io_number}",
                    'number': io_number,
                    'gpio': gpio_pin,
                    'description': description
                }
                configured_dos.append(do_info)
        
        return configured_dos
        
    def load_io_mapping_from_file(self):
        """从文件加载IO映射配置"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择IO映射配置文件", self.config_dir, "JSON文件 (*.json)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                
                # 检查文件格式
                if "io_mapping" in mapping_data:
                    # 新格式
                    self.gpio_config = mapping_data.get("gpio_config", {})
                    
                    # 更新内部映射数据结构
                    self.job_io_mapping = {}
                    for io_key, mapping_info in mapping_data["io_mapping"].items():
                        if mapping_info["type"] == "input" and io_key.startswith("DI"):
                            di_pin = int(io_key[2:])
                            self.job_io_mapping[di_pin] = {
                                "trigger_type": mapping_info["trigger_type"],
                                "job_name": mapping_info["job_name"],
                                "description": mapping_info["description"],
                                "gpio": mapping_info["gpio"]
                            }
                    
                    # 重新加载表格
                    self.load_new_format_mapping(mapping_data)
                    
                    # GPIO配置现在使用固定映射，无需发送到ESP32
                        
                else:
                    # 旧格式
                    self.job_io_mapping = {int(k): v for k, v in mapping_data.items()}
                    self.gpio_config = {}
                    self.load_old_format_mapping(mapping_data)
                
                QMessageBox.information(self, "加载成功", f"IO映射配置已从文件加载:\n{file_path}")
                self.add_log_entry(f"加载IO映射配置: {os.path.basename(file_path)}")
                
                # 刷新IO状态显示
                self.refresh_io_display()
                
        except Exception as e:
            QMessageBox.critical(self, "加载失败", f"加载IO映射配置失败:\n{str(e)}")
            self.add_log_entry(f"加载IO映射配置失败: {str(e)}")
            
    def remove_mapping_row(self, row: int):
        """删除指定行的映射"""
        try:
            # 确认删除
            reply = QMessageBox.question(
                self, "确认删除", 
                f"确定要删除第 {row + 1} 行的IO映射配置吗？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            
            if reply == QMessageBox.Yes:
                # 删除行
                self.mapping_table.removeRow(row)
                self.add_log_entry(f"已删除第 {row + 1} 行IO映射配置")
                
                # 刷新IO状态显示
                self.refresh_io_display()
                
        except Exception as e:
            QMessageBox.critical(self, "删除失败", f"删除IO映射配置失败:\n{str(e)}")
            self.add_log_entry(f"删除IO映射配置失败: {str(e)}")
        
    def save_io_mapping(self):
        """保存IO映射配置"""
        try:
            mapping_data = {
                "gpio_config": {},  # GPIO配置
                "io_mapping": {}    # IO映射
            }
            
            total_rows = self.mapping_table.rowCount()
            saved_count = 0
            
            for row in range(total_rows):
                io_type_combo = self.mapping_table.cellWidget(row, 0)
                io_number_combo = self.mapping_table.cellWidget(row, 1)
                gpio_combo = self.mapping_table.cellWidget(row, 2)
                trigger_combo = self.mapping_table.cellWidget(row, 3)
                job_combo = self.mapping_table.cellWidget(row, 4)
                desc_item = self.mapping_table.item(row, 5)
                
                # 检查必要的控件是否存在（描述可以为空）
                if all([io_type_combo, io_number_combo, gpio_combo, trigger_combo, job_combo]):
                    # 检查控件是否有有效值
                    if (io_type_combo.currentText() and 
                        io_number_combo.currentText() and 
                        gpio_combo.currentText() and 
                        trigger_combo.currentText() and 
                        job_combo.currentText()):
                        
                        io_type = io_type_combo.currentText()
                        io_number = int(io_number_combo.currentText())
                        gpio_pin = int(gpio_combo.currentText())
                        trigger_text = trigger_combo.currentText()
                        job_name = job_combo.currentText()
                        description = desc_item.text() if desc_item else ""
                        
                        # 保存用户选择的GPIO配置
                        io_key = f"{io_type}{io_number}"
                        mapping_data["gpio_config"][io_key] = gpio_pin
                        
                        # 保存IO映射（包括作业为"无"的情况）
                        if io_type == "DI":
                            trigger_map = {
                                "上升沿": "rising_edge", 
                                "下降沿": "falling_edge", 
                                "高电平": "high_level",
                                "低电平": "low_level"
                            }
                            mapping_data["io_mapping"][io_key] = {
                                "type": "input",
                                "gpio": gpio_pin,
                                "trigger_type": trigger_map.get(trigger_text, "rising_edge"),
                                "job_name": job_name if job_name != "无" else "",
                                "description": description
                            }
                        else:  # DO
                            mapping_data["io_mapping"][io_key] = {
                                "type": "output",
                                "gpio": gpio_pin,
                                "job_name": job_name if job_name != "无" else "",
                                "description": description
                            }
                        
                        saved_count += 1
            
            # 选择保存位置
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存IO映射配置", 
                os.path.join(self.config_dir, "io_mapping.json"),
                "JSON文件 (*.json)"
            )
            
            if not file_path:
                return  # 用户取消保存
                
            # 保存到选择的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(mapping_data, f, ensure_ascii=False, indent=2)
                
            # 如果保存到默认位置，更新默认配置文件
            if file_path == self.io_mapping_file:
                pass  # 已经保存到默认位置
            else:
                # 同时更新默认配置文件
                with open(self.io_mapping_file, 'w', encoding='utf-8') as f:
                    json.dump(mapping_data, f, ensure_ascii=False, indent=2)
                
            # 更新内部映射数据结构（保持向后兼容）
            self.job_io_mapping = {}
            for io_key, mapping_info in mapping_data["io_mapping"].items():
                if mapping_info["type"] == "input" and io_key.startswith("DI"):
                    di_pin = int(io_key[2:])
                    # 只有当作业名称不为空时才添加到触发映射中
                    if mapping_info["job_name"]:
                        self.job_io_mapping[di_pin] = {
                            "trigger_type": mapping_info["trigger_type"],
                            "job_name": mapping_info["job_name"],
                            "description": mapping_info["description"],
                            "gpio": mapping_info["gpio"]
                        }
            
            # 更新本地GPIO配置（保持兼容性）
            self.gpio_config = mapping_data["gpio_config"]
                
            QMessageBox.information(self, "保存成功", f"IO映射配置已保存到:\n{file_path}\n\n共保存 {saved_count}/{total_rows} 行配置")
            self.add_log_entry(f"IO映射配置已保存: {os.path.basename(file_path)}")
            
            # 刷新IO状态显示
            self.refresh_io_display()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存IO映射配置失败:\n{str(e)}")
            
        
    def import_teaching_program(self):
        """导入示教程序"""
        try:
            # 检测板子类型
            self.detect_board_type()
            
            # 打开示教程序目录
            teaching_dir = os.path.join(project_root, "config", "teaching_program")
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择示教程序文件", teaching_dir, "JSON文件 (*.json)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    program_data = json.load(f)
                
                # 验证插补类型兼容性
                if not self.validate_interpolation_compatibility(program_data):
                    return
                
                # 获取默认名字
                default_name = os.path.splitext(os.path.basename(file_path))[0]
                
                # 让用户自定义作业名字
                from PyQt5.QtWidgets import QInputDialog
                job_name, ok = QInputDialog.getText(
                    self, "自定义作业名称", 
                    "请输入作业名称:", 
                    text=default_name
                )
                
                if not ok or not job_name.strip():
                    return
                    
                job_name = job_name.strip()
                
                # 检查名称是否已存在
                if job_name in self.jobs:
                    reply = QMessageBox.question(
                        self, "名称冲突", 
                        f"作业 '{job_name}' 已存在，是否覆盖？",
                        QMessageBox.Yes | QMessageBox.No, 
                        QMessageBox.No
                    )
                    if reply != QMessageBox.Yes:
                        return
                
                # 转换为作业格式
                job_data = self.convert_teaching_program_to_job(program_data)
                job_data["name"] = job_name
                
                # 直接保存到io_control目录
                job_file = os.path.join(self.config_dir, f"{job_name}.json")
                with open(job_file, 'w', encoding='utf-8') as f:
                    json.dump(job_data, f, ensure_ascii=False, indent=2)
                
                self.jobs[job_name] = job_data
                self.update_job_table()
                self.update_job_combos_in_mapping_table()  # 更新IO映射配置中的作业下拉框
                self.save_jobs_config()
                
                QMessageBox.information(self, "导入成功", f"示教程序已导入为作业 '{job_name}'")
                self.add_log_entry(f"导入示教程序: {job_name}")
                
        except Exception as e:
            QMessageBox.critical(self, "导入失败", f"导入示教程序失败:\n{str(e)}")
            
    def validate_interpolation_compatibility(self, program_data) -> bool:
        """验证示教程序的插补类型与当前板子的兼容性"""
        if not isinstance(program_data, list):
            return True  # 旧格式，默认通过
            
        # 检查是否包含笛卡尔插补
        has_cartesian = False
        cartesian_points = []
        
        for i, point in enumerate(program_data):
            interpolation_type = point.get('interpolation_type', 'joint')
            if interpolation_type == 'cartesian':
                has_cartesian = True
                cartesian_points.append(i + 1)
        
        # 如果是X板且包含笛卡尔插补，则不允许导入
        if self.is_x_board() and has_cartesian:
            QMessageBox.critical(
                self, "插补类型不兼容", 
                f"当前连接的是X板，不支持笛卡尔插补！\n\n"
                f"示教程序中第 {', '.join(map(str, cartesian_points))} 个点使用了笛卡尔插补。\n"
                f"请使用只包含关节插补的示教程序，或连接Y板。"
            )
            return False
            
        return True
    
    def detect_main_interpolation_type(self, steps_data) -> str:
        """检测示教程序的主要插补类型"""
        if not isinstance(steps_data, list) or not steps_data:
            return "joint"  # 默认关节插补
            
        # 统计插补类型
        joint_count = 0
        cartesian_count = 0
        
        for step in steps_data:
            interpolation_type = step.get('interpolation_type', 'joint')
            if interpolation_type == 'cartesian':
                cartesian_count += 1
            else:
                joint_count += 1
        
        # 返回占多数的插补类型
        return "cartesian" if cartesian_count > joint_count else "joint"
            
    def convert_teaching_program_to_job(self, program_data) -> dict:
        """将示教程序转换为作业格式"""
        # 处理新的示教程序格式（列表格式）
        if isinstance(program_data, list):
            steps_data = program_data
            job_name = "teaching_program"
            job_description = f"从示教程序导入，包含{len(steps_data)}个运动步骤"
        else:
            # 处理旧格式（字典格式）
            steps_data = program_data.get("steps", [])
            job_name = program_data.get("name", "teaching_program")
            job_description = program_data.get("description", "从示教程序导入")
        
        # 检测主要插补类型
        main_interpolation_type = self.detect_main_interpolation_type(steps_data)
        
        job_data = {
            "name": job_name,
            "description": job_description,
            "interpolation_type": main_interpolation_type,  # 添加插补类型
            "steps": [],
            "created_time": datetime.now().isoformat(),
            "total_duration": 0.0
        }
        
        total_duration = 0.0
        
        # 转换步骤
        for i, step_data in enumerate(steps_data):
            # 计算步骤持续时间（基于速度估算）
            max_speed = step_data.get("max_speed", 50)
            duration = 60.0 / max_speed  # 简单的时间估算
            total_duration += duration
            
            # 获取插补参数
            interpolation_params = step_data.get("interpolation_params", {})
            interpolation_type = step_data.get("interpolation_type", "joint")
            
            # 构建参数字典
            parameters = {
                "joint_angles": step_data.get("joint_angles", [0] * 6),
                "interpolation_type": interpolation_type,
                "mode": step_data.get("mode", "base"),
                "end_pose": step_data.get("end_pose", {})
            }
            
            # 根据插补参数的type字段添加不同参数
            params_type = interpolation_params.get("type", "point_to_point")
            if params_type == "cartesian":
                parameters.update({
                    "interpolation_params_type": "cartesian",
                    "linear_velocity": interpolation_params.get("linear_velocity", 50.0),
                    "angular_velocity": interpolation_params.get("angular_velocity", 30.0),
                    "linear_acceleration": interpolation_params.get("linear_acceleration", 100.0),
                    "angular_acceleration": interpolation_params.get("angular_acceleration", 60.0)
                })
            elif params_type == "joint_space":
                # 关节空间插补：从数组中取第一个值作为统一值（简化）
                max_velocities = interpolation_params.get("max_velocities", [90.0] * 6)
                max_accelerations = interpolation_params.get("max_accelerations", [180.0] * 6)
                parameters.update({
                    "interpolation_params_type": "joint_space",
                    "joint_max_velocity": max_velocities[0] if max_velocities else 90.0,
                    "joint_max_acceleration": max_accelerations[0] if max_accelerations else 180.0
                })
            else:  # point_to_point 或 trapezoid（兼容旧版本）
                parameters.update({
                    "interpolation_params_type": "trapezoid",
                    "max_speed": interpolation_params.get("max_speed", 50),
                    "acceleration": interpolation_params.get("acceleration", 50),
                    "deceleration": interpolation_params.get("deceleration", 50)
                })
            
            job_step = {
                "step_id": step_data.get("index", i + 1),
                "type": "move_joints",  # 示教程序主要是关节运动
                "description": f"关节运动到点{step_data.get('index', i + 1)}",
                "parameters": parameters,
                "duration": duration,
                "timestamp": step_data.get("timestamp", time.time())
            }
            job_data["steps"].append(job_step)
            
        job_data["total_duration"] = total_duration
        return job_data
        
    def add_job_from_file(self):
        """从文件添加作业"""
        try:
            file_path, _ = QFileDialog.getOpenFileName(
                self, "选择作业文件", self.config_dir, "JSON文件 (*.json)"
            )
            
            if file_path:
                with open(file_path, 'r', encoding='utf-8') as f:
                    job_data = json.load(f)
                
                job_name = job_data.get("name", os.path.splitext(os.path.basename(file_path))[0])
                self.jobs[job_name] = job_data
                self.update_job_table()
                self.save_jobs_config()
                
                QMessageBox.information(self, "添加成功", f"作业 '{job_name}' 已添加")
                self.add_log_entry(f"添加作业: {job_name}")
                
        except Exception as e:
            QMessageBox.critical(self, "添加失败", f"添加作业失败:\n{str(e)}")
            
    def create_new_job(self):
        """创建新作业"""
        try:
            # 显示创建作业对话框
            dialog = CreateJobDialog(self)
            if dialog.exec_() != QDialog.Accepted:
                return
                
            job_name = dialog.get_job_name()
            job_type = dialog.get_job_type()
            
            if not job_name:
                QMessageBox.warning(self, "输入错误", "请输入有效的作业名称")
                return
            
            # 检查名称是否已存在
            if job_name in self.jobs:
                reply = QMessageBox.question(
                    self, "名称冲突", 
                    f"作业 '{job_name}' 已存在，是否覆盖？",
                    QMessageBox.Yes | QMessageBox.No, 
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    return
            
            # 根据作业类型创建不同的作业
            if job_type == "emergency_stop":
                job_data = self._create_emergency_stop_job(job_name)
            else:
                job_data = self._create_normal_job(job_name)
            
            # 保存到文件
            job_file = os.path.join(self.config_dir, f"{job_name}.json")
            with open(job_file, 'w', encoding='utf-8') as f:
                json.dump(job_data, f, ensure_ascii=False, indent=2)
            
            # 添加到内存
            self.jobs[job_name] = job_data
            self.update_job_table()
            self.save_jobs_config()
            
            # 更新IO映射表格中的作业下拉列表
            self.update_job_combos_in_mapping_table()
            
            # 选中新创建的作业
            for row in range(self.job_list_widget.rowCount()):
                item = self.job_list_widget.item(row, 0)
                if item and item.text() == job_name:
                    self.job_list_widget.selectRow(row)
                    break
            
            if job_type == "emergency_stop":
                QMessageBox.information(self, "创建成功", f"紧急停止作业 '{job_name}' 已创建\n该作业将停止所有运动和程序")
            else:
                QMessageBox.information(self, "创建成功", f"空作业 '{job_name}' 已创建\n您可以开始添加步骤")
            
            self.add_log_entry(f"创建新作业: {job_name} (类型: {job_type})")
            
        except Exception as e:
            QMessageBox.critical(self, "创建失败", f"创建作业失败:\n{str(e)}")
            
    def update_job_combos_in_mapping_table(self):
        """更新IO映射表格中所有作业下拉列表"""
        try:
            job_items = ["无"] + list(self.jobs.keys())
            
            for row in range(self.mapping_table.rowCount()):
                job_combo = self.mapping_table.cellWidget(row, 4)
                if job_combo and isinstance(job_combo, QComboBox):
                    # 保存当前选择
                    current_selection = job_combo.currentText()
                    
                    # 清空并重新添加项目
                    job_combo.clear()
                    job_combo.addItems(job_items)
                    
                    # 恢复选择（如果仍然存在）
                    if current_selection in job_items:
                        job_combo.setCurrentText(current_selection)
                    else:
                        job_combo.setCurrentText("无")
                        
        except Exception as e:
            self.add_log_entry(f"更新作业下拉列表失败: {e}")
            
    def _create_normal_job(self, job_name: str) -> dict:
        """创建普通作业"""
        return {
            "name": job_name,
            "description": "手动创建的作业",
            "interpolation_type": "joint",  # 默认关节插补
            "steps": [],
            "created_time": datetime.now().isoformat(),
            "total_duration": 0.0
        }
        
    def _create_emergency_stop_job(self, job_name: str) -> dict:
        """创建紧急停止作业"""
        return {
            "name": job_name,
            "description": "紧急停止作业 - 停止所有电机",
            "interpolation_type": "joint",
            "steps": [
                {
                    "step_id": 1,
                    "type": "emergency_stop",
                    "description": "紧急停止所有电机",
                    "parameters": {},
                    "duration": 1.0,
                    "timestamp": time.time()
                }
            ],
            "created_time": datetime.now().isoformat(),
            "total_duration": 1.0
        }
            
    def remove_job(self):
        """删除选中的作业"""
        current_row = self.job_list_widget.currentRow()
        if current_row >= 0:
            job_name_item = self.job_list_widget.item(current_row, 0)
            if job_name_item:
                job_name = job_name_item.text()
                
                reply = QMessageBox.question(
                    self, "确认删除", f"确定要删除作业 '{job_name}' 吗？",
                    QMessageBox.Yes | QMessageBox.No, QMessageBox.No
                )
                
                if reply == QMessageBox.Yes:
                    # 删除JSON文件
                    job_file = os.path.join(self.config_dir, f"{job_name}.json")
                    if os.path.exists(job_file):
                        os.remove(job_file)
                    
                    # 从内存中删除
                    del self.jobs[job_name]
                    self.update_job_table()
                    self.update_job_combos_in_mapping_table()  # 更新IO映射配置中的作业下拉框
                    self.save_jobs_config()
                    self.add_log_entry(f"删除作业: {job_name}")
                    
                    # 清空右侧作业信息和步骤显示
                    self.clear_job_info_display()
                    
    def update_job_table(self):
        """更新作业表格"""
        self.job_list_widget.setRowCount(len(self.jobs))
        
        for row, (job_name, job_data) in enumerate(self.jobs.items()):
            # 作业名称
            self.job_list_widget.setItem(row, 0, QTableWidgetItem(job_name))
            
        # 连接选择事件
        self.job_list_widget.itemSelectionChanged.connect(self.on_job_selected)
        
        # 选择第一行时显示作业信息
        if self.jobs:
            self.job_list_widget.selectRow(0)
        else:
            # 没有作业时清空显示
            self.clear_job_info_display()
            self.on_job_selected()
            
    def test_job(self, job_name: str):
        """测试作业"""
        if self.current_job:
            QMessageBox.warning(self, "无法测试", "当前有作业正在执行")
            return
            
        reply = QMessageBox.question(
            self, "测试作业", f"确定要测试作业 '{job_name}' 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            self.execute_job(job_name)
            
    def edit_job(self, job_name: str):
        """编辑作业"""
        QMessageBox.information(self, "编辑作业", f"作业编辑功能开发中...\n作业: {job_name}")
        
    def on_job_selected(self):
        """作业选择事件"""
        current_row = self.job_list_widget.currentRow()
        if current_row >= 0:
            job_name_item = self.job_list_widget.item(current_row, 0)
            if job_name_item:
                job_name = job_name_item.text()
                if job_name in self.jobs:
                    job_data = self.jobs[job_name]
                    
                    # 更新作业信息显示
                    self.job_name_edit.setText(job_name)
                    self.job_desc_edit.setText(job_data.get("description", ""))
                    
                    # 更新统计信息
                    steps_count = len(job_data.get("steps", []))
                    self.total_steps_label.setText(f"步骤数: {steps_count}")
                    
                    # 更新步骤表格
                    self.update_steps_table(job_data.get("steps", []))
        else:
            # 没有选中作业时清空显示
            self.clear_job_info_display()
            
    def clear_job_info_display(self):
        """清空作业信息显示"""
        self.job_name_edit.clear()
        self.job_desc_edit.clear()
        self.total_steps_label.setText("步骤数: 0")
        self.steps_table.setRowCount(0)
                    
    def add_log_entry(self, message: str):
        """添加日志条目"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # 根据消息内容设置颜色
        if "完成" in message or "成功" in message:
            color = "#2ecc71"  # 绿色
            icon = "✅"
        elif "错误" in message or "失败" in message:
            color = "#e74c3c"  # 红色
            icon = "❌"
        elif "停止" in message:
            color = "#f39c12"  # 橙色
            icon = "⏹️"
        elif "执行" in message:
            color = "#3498db"  # 蓝色
            icon = "▶️"
        else:
            color = "#ecf0f1"  # 默认白色
            icon = "ℹ️"
        
        # 创建带颜色的HTML格式日志
        log_entry = f'<span style="color: #95a5a6;">[{timestamp}]</span> <span style="color: {color};">{icon} {message}</span>'
        self.execution_log.append(log_entry)
        
        # 自动滚动到底部
        scrollbar = self.execution_log.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
    def clear_execution_log(self):
        """清空执行日志"""
        self.execution_log.clear()
        
    def load_configuration(self):
        """加载配置"""
        try:
            # 加载作业配置
            if os.path.exists(self.jobs_config_file):
                with open(self.jobs_config_file, 'r', encoding='utf-8') as f:
                    self.jobs = json.load(f)
                    
            # 加载IO映射配置
            if os.path.exists(self.io_mapping_file):
                with open(self.io_mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    
                # 检查是否为新格式
                if "io_mapping" in mapping_data:
                    # 新格式
                    self.gpio_config = mapping_data.get("gpio_config", {})
                    # 转换为旧格式兼容
                    self.job_io_mapping = {}
                    for io_key, mapping_info in mapping_data["io_mapping"].items():
                        if mapping_info["type"] == "input" and io_key.startswith("DI"):
                            di_pin = int(io_key[2:])
                            self.job_io_mapping[di_pin] = {
                                "trigger_type": mapping_info["trigger_type"],
                                "job_name": mapping_info["job_name"],
                                "description": mapping_info["description"],
                                "gpio": mapping_info["gpio"]
                            }
                else:
                    # 旧格式
                    self.job_io_mapping = {int(k): v for k, v in mapping_data.items()}
                    self.gpio_config = {}
                    
            self.update_job_table()
            self.load_io_mapping_table()
            # 延迟更新作业下拉框，确保IO映射表格已经加载完成
            QTimer.singleShot(100, self.update_job_combos_in_mapping_table)
            
        except Exception as e:
            self.add_log_entry(f"加载配置失败: {str(e)}")
            
    def load_io_mapping_table(self):
        """加载IO映射表格"""
        try:
            # 尝试加载新格式的配置文件
            if os.path.exists(self.io_mapping_file):
                with open(self.io_mapping_file, 'r', encoding='utf-8') as f:
                    mapping_data = json.load(f)
                    
                # 检查是否为新格式
                if "io_mapping" in mapping_data:
                    self.load_new_format_mapping(mapping_data)
                else:
                    # 旧格式，转换为新格式显示
                    self.load_old_format_mapping(mapping_data)
            else:
                self.mapping_table.setRowCount(0)
                
        except Exception as e:
            self.add_log_entry(f"加载IO映射表格失败: {e}")
            self.mapping_table.setRowCount(0)
            
    def load_new_format_mapping(self, mapping_data: dict):
        """加载新格式的IO映射"""
        io_mappings = mapping_data.get("io_mapping", {})
        self.mapping_table.setRowCount(len(io_mappings))
        
        available_gpios = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
        
        for row, (io_key, mapping_info) in enumerate(io_mappings.items()):
            io_type = io_key[:2]  # DI 或 DO
            io_number = io_key[2:]  # 编号
            
            # IO类型选择
            io_type_combo = QComboBox()
            io_type_combo.addItems(["DI", "DO"])
            io_type_combo.setCurrentText(io_type)
            io_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_io_type_changed(r, text))
            self.mapping_table.setCellWidget(row, 0, io_type_combo)
            
            # IO编号选择
            io_number_combo = QComboBox()
            io_number_combo.addItems([str(i) for i in range(8)])
            io_number_combo.setCurrentText(io_number)
            self.mapping_table.setCellWidget(row, 1, io_number_combo)
            
            # GPIO引脚选择（可选择ESP32可用GPIO）
            gpio_combo = QComboBox()
            available_gpios = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
            gpio_combo.addItems([str(gpio) for gpio in available_gpios])
            gpio_combo.setCurrentText(str(mapping_info.get("gpio", 23)))
            self.mapping_table.setCellWidget(row, 2, gpio_combo)
            
            # 触发方式选择
            trigger_combo = QComboBox()
            if io_type == "DI":
                trigger_combo.addItems(["上升沿", "下降沿", "高电平", "低电平"])
                trigger_map_reverse = {
                    "rising_edge": "上升沿", 
                    "falling_edge": "下降沿", 
                    "high_level": "高电平",
                    "low_level": "低电平"
                }
                trigger_combo.setCurrentText(trigger_map_reverse.get(mapping_info.get("trigger_type", "rising_edge"), "上升沿"))
            else:  # DO
                trigger_combo.addItems(["无"])
                trigger_combo.setCurrentText("无")
                trigger_combo.setEnabled(False)
            self.mapping_table.setCellWidget(row, 3, trigger_combo)
            
            # 作业选择
            job_combo = QComboBox()
            job_items = ["无"] + list(self.jobs.keys())
            job_combo.addItems(job_items)
            job_name = mapping_info.get("job_name", "")
            job_combo.setCurrentText(job_name if job_name else "无")
            # 如果是DO类型，禁用作业选择
            if io_type == "DO":
                job_combo.setCurrentText("无")
                job_combo.setEnabled(False)
            self.mapping_table.setCellWidget(row, 4, job_combo)
            
            # 描述
            self.mapping_table.setItem(row, 5, QTableWidgetItem(mapping_info.get("description", "")))
            
            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setProperty("class", "danger")
            delete_btn.clicked.connect(lambda checked, r=row: self.remove_mapping_row(r))
            self.mapping_table.setCellWidget(row, 6, delete_btn)
            
    def load_old_format_mapping(self, mapping_data: dict):
        """加载旧格式的IO映射（向后兼容）"""
        self.mapping_table.setRowCount(len(mapping_data))
        
        available_gpios = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
        default_di_gpios = [23, 22, 1, 3, 21, 19, 18, 5]  # 默认DI GPIO
        
        for row, (di_pin, mapping_info) in enumerate(mapping_data.items()):
            # IO类型选择（旧格式只有DI）
            io_type_combo = QComboBox()
            io_type_combo.addItems(["DI", "DO"])
            io_type_combo.setCurrentText("DI")
            io_type_combo.currentTextChanged.connect(lambda text, r=row: self.on_io_type_changed(r, text))
            self.mapping_table.setCellWidget(row, 0, io_type_combo)
            
            # IO编号选择
            io_number_combo = QComboBox()
            io_number_combo.addItems([str(i) for i in range(8)])
            io_number_combo.setCurrentText(str(di_pin))
            self.mapping_table.setCellWidget(row, 1, io_number_combo)
            
            # GPIO引脚选择（可选择ESP32可用GPIO）
            gpio_combo = QComboBox()
            available_gpios = [0, 1, 2, 3, 4, 5, 12, 13, 14, 15, 16, 17, 18, 19, 21, 22, 23, 25, 26, 27, 32, 33, 34, 35, 36, 39]
            gpio_combo.addItems([str(gpio) for gpio in available_gpios])
            # 使用旧配置中的GPIO或默认GPIO
            default_gpio = mapping_info.get("gpio", self.DI_GPIO_MAP.get(di_pin, 23))
            gpio_combo.setCurrentText(str(default_gpio))
            self.mapping_table.setCellWidget(row, 2, gpio_combo)
            
            # 触发方式选择
            trigger_combo = QComboBox()
            trigger_combo.addItems(["上升沿", "下降沿", "高电平", "低电平"])
            trigger_map_reverse = {
                "rising_edge": "上升沿", 
                "falling_edge": "下降沿", 
                "high_level": "高电平",
                "low_level": "低电平"
            }
            trigger_combo.setCurrentText(trigger_map_reverse.get(mapping_info.get("trigger_type", "rising_edge"), "上升沿"))
            self.mapping_table.setCellWidget(row, 3, trigger_combo)
            
            # 作业选择
            job_combo = QComboBox()
            job_items = ["无"] + list(self.jobs.keys())
            job_combo.addItems(job_items)
            job_name = mapping_info.get("job_name", "")
            job_combo.setCurrentText(job_name if job_name else "无")
            # 旧格式只有DI，所以作业选择保持启用
            self.mapping_table.setCellWidget(row, 4, job_combo)
            
            # 描述
            self.mapping_table.setItem(row, 5, QTableWidgetItem(mapping_info.get("description", "")))
            
            # 删除按钮
            delete_btn = QPushButton("删除")
            delete_btn.setProperty("class", "danger")
            delete_btn.clicked.connect(lambda checked, r=row: self.remove_mapping_row(r))
            self.mapping_table.setCellWidget(row, 6, delete_btn)
            
    def save_jobs_config(self):
        """保存作业配置"""
        try:
            with open(self.jobs_config_file, 'w', encoding='utf-8') as f:
                json.dump(self.jobs, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.add_log_entry(f"保存作业配置失败: {str(e)}")
            
    def update_motors(self, motors_info: dict):
        """更新电机连接信息"""
        self.motors = motors_info
        motor_count = len(motors_info) if motors_info else 0
        self.add_log_entry(f"电机连接状态更新: {motor_count}个电机已连接")
        if motors_info:
            motor_ids = list(motors_info.keys())
            self.add_log_entry(f"已连接电机ID: {motor_ids}")
            # 重新检测板子类型
            self.detect_board_type()
        
    def update_claw_controller(self, claw_controller):
        """更新夹爪控制器"""
        self.claw_controller = claw_controller
        if claw_controller:
            self.add_log_entry(f"✅ 夹爪控制器已连接: {claw_controller.port}")
        else:
            self.add_log_entry("⚠️ 夹爪控制器已断开")
        
    def update_kinematics_and_config(self, kinematics, motor_config_manager):
        """更新运动学和电机配置管理器"""
        self.kinematics = kinematics
        self.motor_config_manager = motor_config_manager
        self.add_log_entry("运动学和电机配置管理器已更新")
        
    def clear_motors(self):
        """清空电机连接信息"""
        self.motors = {}
        
    def detect_board_type(self):
        """检测板子类型（参考示教器实现）"""
        try:
            if not self.motors:
                self.board_type = "X"  # 默认X板
                return self.board_type
            
            # 检查所有电机的drive_version属性
            versions = set()
            for motor in self.motors.values():
                drive_version = str(getattr(motor, 'drive_version', 'X')).upper()
                versions.add(drive_version)
                
            # 只有当所有电机都是Y版时才判定为Y板
            if versions == {"Y"}:
                self.board_type = "Y"
            else:
                self.board_type = "X"
                
            self.add_log_entry(f"🔍 板子类型检测: 电机版本={list(versions)}, 判定={self.board_type}板")
            return self.board_type
            
        except Exception as e:
            self.add_log_entry(f"⚠️ 板子类型检测失败: {e}")
            self.board_type = "X"  # 默认为X板
            return self.board_type
        
    def is_x_board(self):
        """判断是否为X板"""
        return self.board_type == "X"
        
    def is_y_board(self):
        """判断是否为Y板"""
        return self.board_type == "Y"
        
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            # 停止所有线程
            self.stop_io_monitoring()
            
            # 停止作业执行线程
            if self.current_job and self.job_worker:
                self.job_worker.stop_job()
                
            if self.job_thread and self.job_thread.isRunning():
                self.job_thread.quit()
                self.job_thread.wait(3000)  # 等待最多3秒
                
            self.current_job = None
                
            # 断开ESP32连接
            if self.esp32_controller:
                self.disconnect_esp32()
                
        except Exception as e:
            print(f"关闭IO控制界面时出错: {e}")
        finally:
            event.accept()
            
    def update_steps_table(self, steps: List[Dict]):
        """更新步骤表格"""
        self.steps_table.setRowCount(len(steps))
        
        for row, step in enumerate(steps):
            # 步骤ID
            self.steps_table.setItem(row, 0, QTableWidgetItem(str(step.get("step_id", row + 1))))
            
            # 步骤类型
            step_type = step.get("type", "unknown")
            type_display = {
                "move_joints": "关节运动",
                "move_cartesian": "笛卡尔运动", 
                "claw_control": "夹爪控制",
                "wait": "等待",
                "io_control": "DO控制",
                "emergency_stop": "紧急停止"
            }.get(step_type, step_type)
            
            self.steps_table.setItem(row, 1, QTableWidgetItem(type_display))
            
            # 步骤描述
            self.steps_table.setItem(row, 2, QTableWidgetItem(step.get("description", "")))
            
    def add_step(self):
        """添加步骤到末尾"""
        current_job = self.get_current_job()
        if not current_job:
            QMessageBox.warning(self, "无作业", "请先选择一个作业")
            return
            
        # 获取下一个步骤ID（末尾添加）
        steps = current_job.get("steps", [])
        next_step_id = len(steps) + 1
            
        editor = JobStepEditor(self, step_index=next_step_id-1)
        editor.step_saved.connect(self.on_step_saved)
        editor.exec_()
        
    def insert_step(self):
        """在选中步骤前插入新步骤"""
        current_row = self.steps_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "未选择", "请先选择要插入位置的步骤")
            return
            
        current_job = self.get_current_job()
        if not current_job:
            QMessageBox.warning(self, "无作业", "请先选择一个作业")
            return
            
        # 在选中行之前插入
        editor = JobStepEditor(self, step_index=current_row)
        editor.step_saved.connect(lambda step_data: self.on_step_inserted(step_data, current_row))
        editor.exec_()
        
    def edit_step(self):
        """编辑选中的步骤"""
        current_row = self.steps_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "未选择", "请先选择要编辑的步骤")
            return
            
        self.edit_step_at_row(current_row)
        
    def edit_step_at_row(self, row: int):
        """编辑指定行的步骤"""
        current_job = self.get_current_job()
        if not current_job or row >= len(current_job.get("steps", [])):
            return
            
        step_data = current_job["steps"][row]
        editor = JobStepEditor(self, step_data=step_data, step_index=row)
        editor.step_saved.connect(lambda new_step: self.on_step_edited(new_step, row))
        editor.exec_()
        
    def delete_step(self):
        """删除选中的步骤"""
        current_row = self.steps_table.currentRow()
        if current_row < 0:
            QMessageBox.warning(self, "未选择", "请先选择要删除的步骤")
            return
            
        self.delete_step_at_row(current_row)
        
    def delete_step_at_row(self, row: int):
        """删除指定行的步骤"""
        current_job = self.get_current_job()
        if not current_job or row >= len(current_job.get("steps", [])):
            return
            
        reply = QMessageBox.question(
            self, "确认删除", f"确定要删除步骤 {row + 1} 吗？",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            # 删除步骤
            current_job["steps"].pop(row)
            
            # 重新编号步骤ID
            for i, step in enumerate(current_job["steps"]):
                step["step_id"] = i + 1
                
            # 更新表格
            self.update_steps_table(current_job["steps"])
            
            # 更新统计信息
            self.update_job_statistics(current_job)
            self.add_log_entry(f"删除步骤 {row + 1}")
            
    def on_step_saved(self, step_data: Dict):
        """步骤保存事件处理"""
        current_job = self.get_current_job()
        if not current_job:
            return
            
        # 添加步骤到作业
        current_job["steps"].append(step_data)
        
        # 重新编号步骤ID
        for i, step in enumerate(current_job["steps"]):
            step["step_id"] = i + 1
            
        # 更新表格
        self.update_steps_table(current_job["steps"])
        
        # 更新统计信息
        self.update_job_statistics(current_job)
        self.add_log_entry(f"添加步骤: {step_data.get('description', '未命名步骤')}")
        
    def on_step_inserted(self, step_data: Dict, insert_position: int):
        """步骤插入事件处理"""
        current_job = self.get_current_job()
        if not current_job:
            return
            
        # 在指定位置插入步骤
        current_job["steps"].insert(insert_position, step_data)
        
        # 重新编号步骤ID
        for i, step in enumerate(current_job["steps"]):
            step["step_id"] = i + 1
            
        # 更新表格
        self.update_steps_table(current_job["steps"])
        
        # 更新统计信息
        self.update_job_statistics(current_job)
        self.add_log_entry(f"插入步骤: {step_data.get('description', '未命名步骤')}")
        
    def on_step_edited(self, step_data: Dict, row: int):
        """步骤编辑事件处理"""
        current_job = self.get_current_job()
        if not current_job or row >= len(current_job.get("steps", [])):
            return
            
        # 更新步骤数据
        current_job["steps"][row] = step_data
        
        # 更新表格
        self.update_steps_table(current_job["steps"])
        # 更新统计信息
        self.update_job_statistics(current_job)
        self.add_log_entry(f"编辑步骤 {row + 1}: {step_data.get('description', '未命名步骤')}")
        
    def update_job_statistics(self, job_data: Dict):
        """更新作业统计信息"""
        steps_count = len(job_data.get("steps", []))
        self.total_steps_label.setText(f"步骤数: {steps_count}")
        
    def test_current_job(self):
        """测试当前选中的作业"""
        current_job = self.get_current_job()
        if not current_job:
            QMessageBox.warning(self, "无作业", "请先选择一个作业")
            return
            
        job_name = current_job.get("name", "未命名作业")
        self.test_job(job_name)
        
    def get_current_job(self) -> Optional[Dict]:
        """获取当前选中的作业"""
        current_row = self.job_list_widget.currentRow()
        if current_row < 0:
            return None
            
        job_name_item = self.job_list_widget.item(current_row, 0)
        if not job_name_item:
            return None
            
        job_name = job_name_item.text()
        return self.jobs.get(job_name)
        
    def save_current_job(self):
        """保存当前作业"""
        current_job = self.get_current_job()
        if not current_job:
            QMessageBox.warning(self, "无作业", "请先选择一个作业")
            return
            
        try:
            # 更新作业信息
            current_job["name"] = self.job_name_edit.text()
            current_job["description"] = self.job_desc_edit.text()
            current_job["modified_time"] = datetime.now().isoformat()
            
            # 插补类型不允许修改，保持原有值
            
            # 移除总时长字段（如果存在）
            if "total_duration" in current_job:
                del current_job["total_duration"]
            
            # 让用户选择保存位置
            job_name = current_job["name"]
            default_file_path = os.path.join(self.config_dir, f"{job_name}.json")
            
            file_path, _ = QFileDialog.getSaveFileName(
                self, "保存作业文件", 
                default_file_path,
                "JSON文件 (*.json);;所有文件 (*)"
            )
            
            if not file_path:
                return  # 用户取消保存
            
            # 保存到选择的文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(current_job, f, ensure_ascii=False, indent=2)
                
            # 更新内存中的作业数据
            old_name = None
            for name, job_data in self.jobs.items():
                if job_data is current_job:
                    old_name = name
                    break
                    
            if old_name and old_name != job_name:
                # 作业名称改变了，需要更新字典
                del self.jobs[old_name]
                # 删除旧文件（仅删除默认目录中的旧文件）
                old_file = os.path.join(self.config_dir, f"{old_name}.json")
                if os.path.exists(old_file):
                    os.remove(old_file)
                    
            self.jobs[job_name] = current_job
            
            # 如果保存到默认目录，同时更新默认配置文件
            if os.path.dirname(file_path) == self.config_dir:
                # 保存作业配置
                self.save_jobs_config()
            else:
                # 保存到其他位置时，也同步更新默认目录中的文件
                default_job_file = os.path.join(self.config_dir, f"{job_name}.json")
                with open(default_job_file, 'w', encoding='utf-8') as f:
                    json.dump(current_job, f, ensure_ascii=False, indent=2)
                # 保存作业配置
                self.save_jobs_config()
            
            # 更新作业表格
            self.update_job_table()
            
            # 如果作业名称改变了，需要更新IO映射表格中的作业下拉框
            if old_name and old_name != job_name:
                self.update_job_combos_in_mapping_table()
            
            # 更新统计信息显示
            steps_count = len(current_job.get("steps", []))
            self.total_steps_label.setText(f"步骤数: {steps_count}")
            
            QMessageBox.information(self, "保存成功", f"作业 '{job_name}' 已保存到:\n{file_path}")
            self.add_log_entry(f"保存作业: {job_name} -> {os.path.basename(file_path)}")
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存作业失败:\n{str(e)}")
            self.add_log_entry(f"保存作业失败: {str(e)}")


class JobStepEditor(QDialog):
    """作业步骤编辑器"""
    
    step_saved = pyqtSignal(dict)  # 步骤保存信号
    
    def __init__(self, parent=None, step_data: Optional[Dict] = None, step_index: int = -1):
        super().__init__(parent)
        self.step_data = step_data or {}
        self.step_index = step_index
        self.is_edit_mode = step_data is not None
        
        self.init_ui()
        self.load_step_data()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("编辑步骤" if self.is_edit_mode else "添加步骤")
        self.setModal(True)
        self.resize(600, 700)
        
        layout = QVBoxLayout(self)
        
        # 基本信息组
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)
        
        self.step_id_spin = QSpinBox()
        self.step_id_spin.setMinimum(1)
        self.step_id_spin.setMaximum(999)
        basic_layout.addRow("步骤ID:", self.step_id_spin)
        
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("步骤描述，如：移动到抓取位置")
        basic_layout.addRow("描述:", self.description_edit)
        
        self.type_combo = QComboBox()
        self.type_combo.addItems([
            "move_joints", "claw_control", "wait", "io_control"
        ])
        self.type_combo.currentTextChanged.connect(self.on_type_changed)
        basic_layout.addRow("动作类型:", self.type_combo)
        
        
        layout.addWidget(basic_group)
        
        # 参数配置标签页
        self.params_tab = QTabWidget()
        # 禁用标签页点击切换，只能通过动作类型选择
        self.params_tab.tabBar().setEnabled(False)
        
        # 关节运动参数
        self.joints_widget = self.create_joints_params_widget()
        self.params_tab.addTab(self.joints_widget, "关节运动")
        
        # 夹爪控制参数
        self.claw_widget = self.create_claw_params_widget()
        self.params_tab.addTab(self.claw_widget, "夹爪控制")
        
        # 等待参数
        self.wait_widget = self.create_wait_params_widget()
        self.params_tab.addTab(self.wait_widget, "等待延时")
        
        # IO控制参数
        self.io_widget = self.create_io_params_widget()
        self.params_tab.addTab(self.io_widget, "IO控制")
        
        layout.addWidget(self.params_tab)
        
        # 按钮组
        button_layout = QHBoxLayout()
        
        self.save_btn = QPushButton("保存")
        self.save_btn.setProperty("class", "success")
        self.save_btn.clicked.connect(self.save_step)
        button_layout.addWidget(self.save_btn)
        
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(self.cancel_btn)
        
        layout.addLayout(button_layout)
        
    def create_joints_params_widget(self):
        """创建关节运动参数控件"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # 关节角度
        angles_layout = QGridLayout()
        self.joint_angle_spins = []
        for i in range(6):
            spin = QDoubleSpinBox()
            spin.setMinimum(-360.0)
            spin.setMaximum(360.0)
            spin.setSingleStep(0.1)
            spin.setSuffix("°")
            angles_layout.addWidget(QLabel(f"关节{i+1}:"), i // 3, (i % 3) * 2)
            angles_layout.addWidget(spin, i // 3, (i % 3) * 2 + 1)
            self.joint_angle_spins.append(spin)
        
        angles_group = QGroupBox("关节角度")
        angles_group.setLayout(angles_layout)
        layout.addRow(angles_group)
        
        # 插补类型选择（三种插补方式）
        self.interpolation_type_combo = QComboBox()
        self.interpolation_type_combo.addItems(["点到点", "关节空间插补", "笛卡尔空间插补"])
        self.interpolation_type_combo.currentTextChanged.connect(self.on_interpolation_type_changed)
        layout.addRow("插补类型:", self.interpolation_type_combo)
        
        # 点到点插补参数组（梯形曲线）
        self.point_to_point_params_group = QGroupBox("点到点插补参数（梯形曲线）")
        point_to_point_layout = QFormLayout(self.point_to_point_params_group)
        
        self.p2p_max_speed_spin = QSpinBox()
        self.p2p_max_speed_spin.setMinimum(1)
        self.p2p_max_speed_spin.setMaximum(3000)
        self.p2p_max_speed_spin.setValue(50)
        point_to_point_layout.addRow("最大速度:", self.p2p_max_speed_spin)
        
        self.p2p_acceleration_spin = QSpinBox()
        self.p2p_acceleration_spin.setMinimum(1)
        self.p2p_acceleration_spin.setMaximum(3000)
        self.p2p_acceleration_spin.setValue(50)
        point_to_point_layout.addRow("加速度:", self.p2p_acceleration_spin)
        
        self.p2p_deceleration_spin = QSpinBox()
        self.p2p_deceleration_spin.setMinimum(1)
        self.p2p_deceleration_spin.setMaximum(3000)
        self.p2p_deceleration_spin.setValue(50)
        point_to_point_layout.addRow("减速度:", self.p2p_deceleration_spin)
        
        layout.addRow(self.point_to_point_params_group)
        
        # 关节空间插补参数组
        self.joint_space_params_group = QGroupBox("关节空间插补参数")
        joint_space_layout = QFormLayout(self.joint_space_params_group)
        
        # 使用单一值应用到所有关节（简化界面）
        self.joint_max_velocity_spin = QDoubleSpinBox()
        self.joint_max_velocity_spin.setMinimum(1.0)
        self.joint_max_velocity_spin.setMaximum(500.0)
        self.joint_max_velocity_spin.setValue(90.0)
        self.joint_max_velocity_spin.setSuffix(" deg/s")
        joint_space_layout.addRow("最大速度(所有关节):", self.joint_max_velocity_spin)
        
        self.joint_max_acceleration_spin = QDoubleSpinBox()
        self.joint_max_acceleration_spin.setMinimum(1.0)
        self.joint_max_acceleration_spin.setMaximum(500.0)
        self.joint_max_acceleration_spin.setValue(180.0)
        self.joint_max_acceleration_spin.setSuffix(" deg/s²")
        joint_space_layout.addRow("最大加速度(所有关节):", self.joint_max_acceleration_spin)
        
        # 添加说明
        info_label = QLabel("注：速度和加速度将应用于所有6个关节")
        info_label.setStyleSheet("color: gray; font-size: 11px;")
        joint_space_layout.addRow("", info_label)
        
        layout.addRow(self.joint_space_params_group)
        
        # 笛卡尔空间插补参数组
        self.cartesian_params_group = QGroupBox("笛卡尔空间插补参数")
        cartesian_params_layout = QFormLayout(self.cartesian_params_group)
        
        self.linear_velocity_spin = QDoubleSpinBox()
        self.linear_velocity_spin.setMinimum(1.0)
        self.linear_velocity_spin.setMaximum(200.0)
        self.linear_velocity_spin.setValue(50.0)
        self.linear_velocity_spin.setSuffix(" mm/s")
        cartesian_params_layout.addRow("线性速度:", self.linear_velocity_spin)
        
        self.angular_velocity_spin = QDoubleSpinBox()
        self.angular_velocity_spin.setMinimum(1.0)
        self.angular_velocity_spin.setMaximum(180.0)
        self.angular_velocity_spin.setValue(30.0)
        self.angular_velocity_spin.setSuffix(" deg/s")
        cartesian_params_layout.addRow("角速度:", self.angular_velocity_spin)
        
        self.linear_acceleration_spin = QDoubleSpinBox()
        self.linear_acceleration_spin.setMinimum(1.0)
        self.linear_acceleration_spin.setMaximum(300.0)
        self.linear_acceleration_spin.setValue(100.0)
        self.linear_acceleration_spin.setSuffix(" mm/s²")
        cartesian_params_layout.addRow("线性加速度:", self.linear_acceleration_spin)
        
        self.angular_acceleration_spin = QDoubleSpinBox()
        self.angular_acceleration_spin.setMinimum(1.0)
        self.angular_acceleration_spin.setMaximum(360.0)
        self.angular_acceleration_spin.setValue(60.0)
        self.angular_acceleration_spin.setSuffix(" deg/s²")
        cartesian_params_layout.addRow("角加速度:", self.angular_acceleration_spin)
        
        layout.addRow(self.cartesian_params_group)
        
        # 初始显示点到点插补参数
        self.point_to_point_params_group.setVisible(True)
        self.joint_space_params_group.setVisible(False)
        self.cartesian_params_group.setVisible(False)
        
        return widget
        
    def on_interpolation_type_changed(self, interpolation_type: str):
        """插补类型改变时的处理"""
        # 隐藏所有参数组
        self.point_to_point_params_group.setVisible(False)
        self.joint_space_params_group.setVisible(False)
        self.cartesian_params_group.setVisible(False)
        
        # 根据选择显示对应的参数组
        if interpolation_type == "点到点":
            self.point_to_point_params_group.setVisible(True)
        elif interpolation_type == "关节空间插补":
            self.joint_space_params_group.setVisible(True)
        elif interpolation_type == "笛卡尔空间插补":
            self.cartesian_params_group.setVisible(True)
        
        
    def create_claw_params_widget(self):
        """创建夹爪控制参数控件"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self.claw_action_combo = QComboBox()
        self.claw_action_combo.addItems(["open", "close"])
        layout.addRow("动作:", self.claw_action_combo)
        
        self.claw_open_angle_spin = QDoubleSpinBox()
        self.claw_open_angle_spin.setMinimum(0.0)
        self.claw_open_angle_spin.setMaximum(180.0)
        self.claw_open_angle_spin.setSingleStep(1.0)
        self.claw_open_angle_spin.setSuffix("°")
        layout.addRow("张开角度:", self.claw_open_angle_spin)
        
        self.claw_close_angle_spin = QDoubleSpinBox()
        self.claw_close_angle_spin.setMinimum(0.0)
        self.claw_close_angle_spin.setMaximum(180.0)
        self.claw_close_angle_spin.setSingleStep(1.0)
        self.claw_close_angle_spin.setSuffix("°")
        layout.addRow("闭合角度:", self.claw_close_angle_spin)
        
        return widget
        
    def create_wait_params_widget(self):
        """创建等待参数控件"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        self.wait_duration_spin = QDoubleSpinBox()
        self.wait_duration_spin.setMinimum(0.1)
        self.wait_duration_spin.setMaximum(60.0)
        self.wait_duration_spin.setSingleStep(0.1)
        self.wait_duration_spin.setSuffix(" 秒")
        layout.addRow("等待时间:", self.wait_duration_spin)
        
        return widget
        
    def create_io_params_widget(self):
        """创建DO控制参数控件"""
        widget = QWidget()
        layout = QFormLayout(widget)
        
        # DO选择下拉框（只显示已配置的DO）
        self.do_select_combo = QComboBox()
        self.update_do_options()  # 更新DO选项
        layout.addRow("DO选择:", self.do_select_combo)
        
        # 输出电平选择
        self.output_level_combo = QComboBox()
        self.output_level_combo.addItems(["高电平", "低电平"])
        layout.addRow("输出电平:", self.output_level_combo)
        
        # 添加说明标签
        info_label = QLabel("注：选择要控制的DO口和输出电平")
        info_label.setStyleSheet("color: gray; font-size: 12px;")
        layout.addRow("", info_label)
        
        return widget
        
    def update_do_options(self):
        """更新DO选项（只显示已配置的DO）"""
        self.do_select_combo.clear()
        
        # 获取父窗口的IO映射配置
        if hasattr(self.parent(), 'get_configured_dos'):
            configured_dos = self.parent().get_configured_dos()
            if configured_dos:
                for do_info in configured_dos:
                    do_name = do_info['name']
                    do_desc = do_info.get('description', '')
                    gpio_pin = do_info.get('gpio', 0)
                    
                    display_text = f"{do_name} (GPIO{gpio_pin})"
                    if do_desc:
                        display_text += f" - {do_desc}"
                    self.do_select_combo.addItem(display_text, do_info)
            else:
                self.do_select_combo.addItem("无可用DO（请先配置IO映射）", None)
        else:
            # 如果无法获取配置，显示默认选项
            self.do_select_combo.addItem("无可用DO（请先配置IO映射）", None)
        
    def on_type_changed(self, step_type: str):
        """步骤类型改变时的处理"""
        # 根据步骤类型切换到对应的参数标签页
        type_tab_map = {
            "move_joints": 0,
            "claw_control": 1,
            "wait": 2,
            "io_control": 3
        }
        
        if step_type in type_tab_map:
            self.params_tab.setCurrentIndex(type_tab_map[step_type])
            
    def load_step_data(self):
        """加载步骤数据"""
        if not self.step_data:
            # 设置默认值
            self.step_id_spin.setValue(self.step_index + 1 if self.step_index >= 0 else 1)
            self.interpolation_type_combo.setCurrentText("点到点")
            # 点到点参数默认值
            self.p2p_max_speed_spin.setValue(50)
            self.p2p_acceleration_spin.setValue(50)
            self.p2p_deceleration_spin.setValue(50)
            # 关节空间参数默认值
            self.joint_max_velocity_spin.setValue(90.0)
            self.joint_max_acceleration_spin.setValue(180.0)
            # 笛卡尔空间参数默认值
            self.linear_velocity_spin.setValue(50.0)
            self.angular_velocity_spin.setValue(30.0)
            self.linear_acceleration_spin.setValue(100.0)
            self.angular_acceleration_spin.setValue(60.0)
            # 夹爪参数默认值
            self.claw_open_angle_spin.setValue(0)   # 0度为张开
            self.claw_close_angle_spin.setValue(90)  # 90度为闭合
            # 等待参数默认值
            self.wait_duration_spin.setValue(1.0)
            return
            
        # 加载基本信息
        self.step_id_spin.setValue(self.step_data.get("step_id", 1))
        self.description_edit.setText(self.step_data.get("description", ""))
        self.type_combo.setCurrentText(self.step_data.get("type", "move_joints"))
        
        # 加载参数
        params = self.step_data.get("parameters", {})
        
        # 关节运动参数
        if "joint_angles" in params:
            joint_angles = params["joint_angles"]
            for i, angle in enumerate(joint_angles[:6]):
                if i < len(self.joint_angle_spins):
                    self.joint_angle_spins[i].setValue(angle)
        
        # 插补参数类型（根据interpolation_params的type字段）
        interpolation_params_type = params.get("interpolation_params_type", "trapezoid")
        if interpolation_params_type == "cartesian":
            self.interpolation_type_combo.setCurrentText("笛卡尔空间插补")
            # 笛卡尔空间插补参数
            self.linear_velocity_spin.setValue(params.get("linear_velocity", 50.0))
            self.angular_velocity_spin.setValue(params.get("angular_velocity", 30.0))
            self.linear_acceleration_spin.setValue(params.get("linear_acceleration", 100.0))
            self.angular_acceleration_spin.setValue(params.get("angular_acceleration", 60.0))
        elif interpolation_params_type == "joint_space":
            self.interpolation_type_combo.setCurrentText("关节空间插补")
            # 关节空间插补参数（使用单一值）
            self.joint_max_velocity_spin.setValue(params.get("joint_max_velocity", params.get("max_velocity", 90.0)))
            self.joint_max_acceleration_spin.setValue(params.get("joint_max_acceleration", params.get("max_acceleration", 180.0)))
        else:  # trapezoid (点到点)
            self.interpolation_type_combo.setCurrentText("点到点")
            # 点到点插补参数（梯形曲线）
            self.p2p_max_speed_spin.setValue(params.get("max_speed", 50))
            self.p2p_acceleration_spin.setValue(params.get("acceleration", 50))
            self.p2p_deceleration_spin.setValue(params.get("deceleration", 50))
        
        
        # 夹爪控制参数
        self.claw_action_combo.setCurrentText(params.get("action", "open"))
        self.claw_open_angle_spin.setValue(params.get("open_angle", 0))   # 0度为张开
        self.claw_close_angle_spin.setValue(params.get("close_angle", 90))  # 90度为闭合
        
        # 等待参数
        self.wait_duration_spin.setValue(params.get("wait_duration", 1.0))
        
        # DO控制参数
        # 更新DO选项
        self.update_do_options()
        
        # 设置DO选择（兼容旧格式）
        if "do_number" in params:
            # 新格式
            do_number = params.get("do_number", 0)
        else:
            # 旧格式兼容
            do_number = params.get("pin", 0)
            
        for i in range(self.do_select_combo.count()):
            do_info = self.do_select_combo.itemData(i)
            if do_info and do_info.get('number') == do_number:
                self.do_select_combo.setCurrentIndex(i)
                break
        
        # 设置输出电平（兼容旧格式）
        if "output_level" in params:
            # 新格式
            self.output_level_combo.setCurrentText(params.get("output_level", "高电平"))
        else:
            # 旧格式兼容：从trigger_method推断
            trigger_method = params.get("trigger_method", "设置高电平")
            if trigger_method == "设置低电平":
                self.output_level_combo.setCurrentText("低电平")
            else:
                self.output_level_combo.setCurrentText("高电平")
        
            
    def save_step(self):
        """保存步骤"""
        try:
            step_type = self.type_combo.currentText()
            
            # 构建步骤数据
            step_data = {
                "step_id": self.step_id_spin.value(),
                "type": step_type,
                "description": self.description_edit.text(),
                "parameters": {}
            }
            
            # 根据步骤类型收集参数
            if step_type == "move_joints":
                # 基本参数
                parameters = {
                    "joint_angles": [spin.value() for spin in self.joint_angle_spins]
                }
                
                # 插补参数类型和对应参数
                interpolation_type = self.interpolation_type_combo.currentText()
                if interpolation_type == "笛卡尔空间插补":
                    # 笛卡尔空间插补
                    parameters.update({
                        "interpolation_params_type": "cartesian",
                        "linear_velocity": self.linear_velocity_spin.value(),
                        "angular_velocity": self.angular_velocity_spin.value(),
                        "linear_acceleration": self.linear_acceleration_spin.value(),
                        "angular_acceleration": self.angular_acceleration_spin.value()
                    })
                elif interpolation_type == "关节空间插补":
                    # 关节空间插补（使用单一值应用到所有关节）
                    parameters.update({
                        "interpolation_params_type": "joint_space",
                        "joint_max_velocity": self.joint_max_velocity_spin.value(),
                        "joint_max_acceleration": self.joint_max_acceleration_spin.value()
                    })
                else:  # 点到点
                    # 点到点插补（梯形曲线）
                    parameters.update({
                        "interpolation_params_type": "trapezoid",
                        "max_speed": self.p2p_max_speed_spin.value(),
                        "acceleration": self.p2p_acceleration_spin.value(),
                        "deceleration": self.p2p_deceleration_spin.value()
                    })
                
                step_data["parameters"] = parameters
            elif step_type == "claw_control":
                step_data["parameters"] = {
                    "action": self.claw_action_combo.currentText(),
                    "open_angle": self.claw_open_angle_spin.value(),
                    "close_angle": self.claw_close_angle_spin.value()
                }
            elif step_type == "wait":
                step_data["parameters"] = {
                    "wait_duration": self.wait_duration_spin.value()
                }
            elif step_type == "io_control":
                # 获取选中的DO信息
                selected_do = self.do_select_combo.currentData()
                if selected_do:
                    step_data["parameters"] = {
                        "do_number": selected_do['number'],
                        "do_name": selected_do['name'],
                        "gpio": selected_do['gpio'],
                        "output_level": self.output_level_combo.currentText()
                    }
                else:
                    QMessageBox.warning(self, "参数错误", "请选择一个有效的DO")
                    return
                    
            # 发送保存信号
            self.step_saved.emit(step_data)
            self.accept()
            
        except Exception as e:
            QMessageBox.critical(self, "保存失败", f"保存步骤时出错:\n{str(e)}")
