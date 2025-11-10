# -*- coding: utf-8 -*-
"""
示教器控件
支持关节模式、基座模式和工具模式的机械臂控制
"""

import sys
import os
import yaml
import time
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QScrollArea, QSplitter, QFrame, QHeaderView,
                             QButtonGroup, QRadioButton, QFileDialog, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor
import numpy as np
import threading

from Control_SDK.Control_Core import ZDTCommandBuilder

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

try:
    from Main_UI.utils.kinematics_factory import create_configured_kinematics
    KINEMATICS_AVAILABLE = True
except ImportError:
    KINEMATICS_AVAILABLE = False

# 添加电机配置管理器导入
from .motor_config_manager import motor_config_manager


class MotionController:
    """运动控制管理器 - 统一管理所有运动相关功能"""
    
    def __init__(self, parent_widget):
        """
        初始化运动控制器
        
        Args:
            parent_widget: 父控件（示教器）
        """
        import numpy as np  # 确保numpy可用
        self.parent = parent_widget
        
        # 基础属性引用
        self.motors = None
        self.motor_config_manager = None
        self.kinematics = None
        self.output_joint_angles = None
        
        # 运动参数
        self.speed = 100
        self.acceleration = 200
        self.deceleration = 200
        
        # 笛卡尔运动参数
        self.cartesian_linear_velocity = 150.0
        self.cartesian_angular_velocity = 90.0
        self.cartesian_linear_acceleration = 300.0
        self.cartesian_angular_acceleration = 180.0
        
        # 关节运动参数
        self.joint_max_velocities = [90.0] * 6
        self.joint_max_accelerations = [180.0] * 6
        
        # 插补类型
        self.interpolation_type = "direct"  # "direct", "cartesian", "joint"
        
        # 轨迹执行器
        self.cartesian_interpolator = None
        self.cartesian_executor = None
        self.joint_interpolator = None
        self.joint_executor = None
    
    def initialize(self, motors, motor_config_manager, kinematics, output_joint_angles):
        """初始化运动控制器的基础组件"""
        self.motors = motors
        self.motor_config_manager = motor_config_manager
        self.kinematics = kinematics
        self.output_joint_angles = output_joint_angles
    
    def update_motion_parameters(self, speed=None, acceleration=None, deceleration=None):
        """更新运动参数"""
        if speed is not None:
            self.speed = speed
        if acceleration is not None:
            self.acceleration = acceleration
        if deceleration is not None:
            self.deceleration = deceleration
    
    def update_cartesian_parameters(self, linear_velocity=None, angular_velocity=None, 
                                  linear_acceleration=None, angular_acceleration=None):
        """更新笛卡尔运动参数"""
        if linear_velocity is not None:
            self.cartesian_linear_velocity = linear_velocity
        if angular_velocity is not None:
            self.cartesian_angular_velocity = angular_velocity
        if linear_acceleration is not None:
            self.cartesian_linear_acceleration = linear_acceleration
        if angular_acceleration is not None:
            self.cartesian_angular_acceleration = angular_acceleration
    
    def update_joint_parameters(self, max_velocities=None, max_accelerations=None):
        """更新关节运动参数"""
        if max_velocities is not None:
            self.joint_max_velocities = max_velocities
        if max_accelerations is not None:
            self.joint_max_accelerations = max_accelerations
    
    def set_interpolation_type(self, interpolation_type):
        """设置插补类型"""
        self.interpolation_type = interpolation_type
    
    def _is_y_board(self):
        """判断是否为Y板"""
        return self.parent._is_y_board()
    
    def _initialize_cartesian_executor(self):
        """初始化笛卡尔执行器"""
        if self.cartesian_executor is None:
            try:
                from core.arm_core.interpolation import CartesianSpaceInterpolator
                from core.arm_core.trajectory_executor import CartesianTrajectoryExecutor
                
                self.cartesian_interpolator = CartesianSpaceInterpolator()
                self.cartesian_executor = CartesianTrajectoryExecutor(
                    self.kinematics, 
                    self.cartesian_interpolator, 
                    self.motor_config_manager,
                    ik_solver=self.parent  # 传入父控件作为IK解选择器
                )
                print("✅ 笛卡尔空间插补器初始化成功")
                return True
            except ImportError as e:
                print(f"❌ 无法导入笛卡尔空间插补器: {e}")
                return False
            except Exception as e:
                print(f"❌ 笛卡尔空间插补器初始化失败: {e}")
                return False
        return True
    
    def _initialize_joint_executor(self):
        """初始化关节执行器"""
        if self.joint_executor is None:
            try:
                from core.arm_core.interpolation import JointSpaceInterpolator
                from core.arm_core.trajectory_executor import JointSpaceTrajectoryExecutor
                
                joint_interpolator = JointSpaceInterpolator()
                self.joint_executor = JointSpaceTrajectoryExecutor(
                    joint_interpolator, 
                    self.motor_config_manager
                )
                print("✅ 关节空间插补器初始化成功")
                return True
            except ImportError as e:
                print(f"❌ 无法导入关节空间插补器: {e}")
                return False
            except Exception as e:
                print(f"❌ 关节空间插补器初始化失败: {e}")
                return False
        return True
    
    def move_joint(self, joint_index, angle_delta):
        """移动指定关节"""
        if not self.motors:
            QMessageBox.warning(self.parent, "警告", "未连接电机，无法执行运动！\n\n请确保电机连接正常。")
            return
        
        if len(self.motors) < 6:
            QMessageBox.warning(self.parent, "警告", f"当前只连接了{len(self.motors)}个电机，建议连接完整的6轴机械臂！")
        
        if joint_index < 0 or joint_index >= 6:
            return
            
        try:
            motor_id = joint_index + 1  # 电机ID从1开始
            
            if motor_id not in self.motors:
                QMessageBox.warning(self.parent, "警告", f"关节J{motor_id}未连接，无法执行运动！\n\n可用电机ID: {list(self.motors.keys())}")
                return
            
            # 1. 获取当前输出端角度值
            current_output_angle = self.parent.output_joint_angles[joint_index]
            
            # 2. 计算新的输出端角度（加上或减去步进大小）
            new_output_angle = current_output_angle + angle_delta
            
            # 规范化角度到 [-180°, +180°] 范围
            new_output_angle = self.parent.kinematics.normalize_angle(new_output_angle)
            
            # 3. 检查角度范围限制（规范化后应该在合理范围内）
            if abs(new_output_angle) > 180:
                QMessageBox.warning(self.parent, "警告", f"关节J{motor_id}角度超出范围")
                return
            
            # 4. 更新输出端角度状态
            self.parent.output_joint_angles[joint_index] = new_output_angle
            
            # 5. 如果有连接的电机，立即执行运动
            motor = self.motors[motor_id]
            try:
                # 计算实际电机角度（考虑减速比和方向）
                actual_angle = self.parent.get_actual_angle(new_output_angle, motor_id)
                
                # 发送位置命令到电机
                motor.control_actions.move_to_position_trapezoid(
                    position=actual_angle,
                    max_speed=self.speed,
                    acceleration=self.acceleration,
                    deceleration=self.deceleration,
                    is_absolute=True,
                    multi_sync=False  # 单关节运动不使用同步模式
                )
                
            except Exception as motor_error:
                QMessageBox.warning(self.parent, "警告", f"关节J{motor_id}运动失败:\n{str(motor_error)}")
                # 回退角度设置
                self.parent.output_joint_angles[joint_index] = current_output_angle
                return
            
            # 6. 更新界面显示
            self.parent.update_joint_angle_labels()
            self.parent.update_end_effector_pose()
                
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"关节运动出错: {str(e)}\n\n请检查电机连接和通信状态。")
    
    def move_base_translation(self, axis, distance):
        """基座坐标系平移"""
        if not self.kinematics:
            QMessageBox.warning(self.parent, "警告", "运动学计算器未初始化")
            return
        
        # Y板根据插补类型选择执行方式
        if self._is_y_board():
            if self.interpolation_type == "cartesian":
                # 笛卡尔空间插补
                print(f"🎯 使用笛卡尔空间插补执行基座{axis.upper()}轴平移")
                self._move_base_translation_cartesian(axis, distance)
                return
            elif self.interpolation_type == "joint" and self.joint_executor is not None:
                # 关节空间插补
                print(f"🎯 使用关节空间插补执行基座{axis.upper()}轴平移")
                self._move_base_translation_joint(axis, distance)
                return
            elif self.interpolation_type == "point_to_point":
                # 点到点运动
                print(f"🎯 使用点到点运动执行基座{axis.upper()}轴平移")
                self._move_base_translation_direct(axis, distance)
                return
            else:
                print(f"⚠️ 插补类型未识别或未初始化，回退到直接运动学方式")
        
        # X板使用点到点运动
        print(f"🎯 X板使用点到点运动执行基座{axis.upper()}轴平移")
        self._move_base_translation_direct(axis, distance)
    
    def move_tool_translation(self, axis, distance):
        """工具坐标系平移"""
        if not self.kinematics:
            QMessageBox.warning(self.parent, "警告", "运动学计算器未初始化")
            return
        
        # Y板根据插补类型选择执行方式
        if self._is_y_board():
            if self.interpolation_type == "cartesian":
                # 笛卡尔空间插补
                print(f"🎯 使用笛卡尔空间插补执行工具{axis.upper()}轴平移")
                self._move_tool_translation_cartesian(axis, distance)
                return
            elif self.interpolation_type == "joint" and self.joint_executor is not None:
                # 关节空间插补
                print(f"🎯 使用关节空间插补执行工具{axis.upper()}轴平移")
                self._move_tool_translation_joint(axis, distance)
                return
            elif self.interpolation_type == "point_to_point":
                # 点到点运动
                print(f"🎯 使用点到点运动执行工具{axis.upper()}轴平移")
                self._move_tool_translation_direct(axis, distance)
                return
            else:
                print(f"⚠️ 插补类型未识别或未初始化，回退到直接运动学方式")
        
        # X板使用点到点运动
        print(f"🎯 X板使用点到点运动执行工具{axis.upper()}轴平移")
        self._move_tool_translation_direct(axis, distance)
    
    def move_base_rotation(self, axis, angle_delta):
        """基座坐标系旋转"""
        if not self.kinematics:
            QMessageBox.warning(self.parent, "警告", "运动学计算器未初始化")
            return
        
        try:
            # 映射旋转轴名称：支持 'roll'/'pitch'/'yaw' 和 'x'/'y'/'z'
            axis_mapping = {
                'roll': 'x',
                'pitch': 'y', 
                'yaw': 'z',
                'x': 'x',
                'y': 'y',
                'z': 'z'
            }
            
            # 转换轴名称
            axis = axis_mapping.get(axis.lower(), axis.lower())
            
            # 直接使用输出端角度状态，不从电机读取
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿（返回4x4矩阵）
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 计算目标变换矩阵
            import numpy as np
            target_transform = current_transform.copy()
            
            # 创建旋转矩阵
            angle_rad = np.deg2rad(angle_delta)
            if axis == 'x':
                rotation_matrix = np.array([
                    [1, 0, 0],
                    [0, np.cos(angle_rad), -np.sin(angle_rad)],
                    [0, np.sin(angle_rad), np.cos(angle_rad)]
                ])
            elif axis == 'y':
                rotation_matrix = np.array([
                    [np.cos(angle_rad), 0, np.sin(angle_rad)],
                    [0, 1, 0],
                    [-np.sin(angle_rad), 0, np.cos(angle_rad)]
                ])
            elif axis == 'z':
                rotation_matrix = np.array([
                    [np.cos(angle_rad), -np.sin(angle_rad), 0],
                    [np.sin(angle_rad), np.cos(angle_rad), 0],
                    [0, 0, 1]
                ])
            else:
                QMessageBox.warning(self.parent, "警告", f"无效的旋转轴: {axis}，必须是 'x', 'y' 或 'z'")
                return
            
            # 应用旋转
            target_transform[:3, :3] = rotation_matrix @ current_transform[:3, :3]
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取原始解和规范化解
            target_joints_display = solution_result['original']    # 用于界面显示
            target_joints_control = solution_result['normalized']  # 用于电机控制
            
            # 更新输出端角度状态（使用原始解进行显示）
            self.parent.output_joint_angles = list(target_joints_display)
            
            # 执行运动到目标关节角度（使用规范化解控制电机）
            self.parent.move_to_joint_angles(target_joints_control)
            
            # 更新界面显示
            self.parent.update_joint_angle_labels()
            self.parent.update_end_effector_pose()
            
            print(f"✅ 基座{axis.upper()}轴旋转 {angle_delta:+.1f}° 执行成功")
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"基座旋转出错: {str(e)}")
    
    def move_tool_rotation(self, axis, angle_delta):
        """工具坐标系旋转"""
        if not self.kinematics:
            QMessageBox.warning(self.parent, "警告", "运动学计算器未初始化")
            return
        
        try:
            # 映射旋转轴名称：支持 'roll'/'pitch'/'yaw' 和 'x'/'y'/'z'
            axis_mapping = {
                'roll': 'x',
                'pitch': 'y',
                'yaw': 'z',
                'x': 'x',
                'y': 'y',
                'z': 'z'
            }
            
            # 转换轴名称
            axis = axis_mapping.get(axis.lower(), axis.lower())
            
            # 直接使用输出端角度状态，不从电机读取
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿（返回4x4矩阵）
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 计算目标变换矩阵
            import numpy as np
            target_transform = current_transform.copy()
            
            # 在工具坐标系中创建旋转矩阵
            angle_rad = np.deg2rad(angle_delta)
            if axis == 'x':
                tool_rotation = np.array([
                    [1, 0, 0],
                    [0, np.cos(angle_rad), -np.sin(angle_rad)],
                    [0, np.sin(angle_rad), np.cos(angle_rad)]
                ])
            elif axis == 'y':
                tool_rotation = np.array([
                    [np.cos(angle_rad), 0, np.sin(angle_rad)],
                    [0, 1, 0],
                    [-np.sin(angle_rad), 0, np.cos(angle_rad)]
                ])
            elif axis == 'z':
                tool_rotation = np.array([
                    [np.cos(angle_rad), -np.sin(angle_rad), 0],
                    [np.sin(angle_rad), np.cos(angle_rad), 0],
                    [0, 0, 1]
                ])
            else:
                QMessageBox.warning(self.parent, "警告", f"无效的旋转轴: {axis}，必须是 'x', 'y' 或 'z'")
                return
            
            # 应用工具坐标系旋转
            target_transform[:3, :3] = current_transform[:3, :3] @ tool_rotation
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取原始解和规范化解
            target_joints_display = solution_result['original']    # 用于界面显示
            target_joints_control = solution_result['normalized']  # 用于电机控制
            
            # 更新输出端角度状态（使用原始解进行显示）
            self.parent.output_joint_angles = list(target_joints_display)
            
            # 执行运动到目标关节角度（使用规范化解控制电机）
            self.parent.move_to_joint_angles(target_joints_control)
            
            # 更新界面显示
            self.parent.update_joint_angle_labels()
            self.parent.update_end_effector_pose()
            
            print(f"✅ 工具{axis.upper()}轴旋转 {angle_delta:+.1f}° 执行成功")
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"工具旋转出错: {str(e)}")
    
    def move_to_teaching_point(self, teaching_point, use_saved_params=False):
        """移动到示教点
        
        Args:
            teaching_point: 示教点数据
            use_saved_params: 是否使用示教点保存的参数（True）还是使用当前界面参数（False）
        """
        if not self.motors:
            QMessageBox.warning(self.parent, "警告", "未连接电机，无法执行运动！")
            return False
        
        try:
            if use_saved_params:
                # 使用示教点保存的插补方式和参数
                saved_interpolation_type = teaching_point.get('interpolation_type', 'point_to_point')
                saved_interpolation_params = teaching_point.get('interpolation_params', {})
                saved_mode = teaching_point.get('mode', 'joint')
                
                print(f"🎯 使用保存参数移动到示教点 {teaching_point['index']}")
                print(f"   保存的插补类型: {saved_interpolation_type}")
                print(f"   保存的模式: {saved_mode}")
                
                # 根据保存的模式和插补类型执行运动
                if saved_mode == "joint":
                    print("🔄 关节模式：直接控制关节角度")
                    self._move_to_teaching_point_direct(teaching_point)
                elif saved_interpolation_type == "cartesian":
                    print("🔄 使用笛卡尔空间插补执行")
                    if not self._initialize_cartesian_executor():
                        QMessageBox.warning(self.parent, "警告", "笛卡尔插补器初始化失败")
                        return False
                    self._move_to_teaching_point_cartesian_interpolation(teaching_point, saved_interpolation_params)
                elif saved_interpolation_type == "joint":
                    print("🔄 使用关节空间插补执行")
                    if not self._initialize_joint_executor():
                        QMessageBox.warning(self.parent, "警告", "关节插补器初始化失败")
                        return False
                    self._move_to_teaching_point_joint_space_interpolation(teaching_point, saved_interpolation_params)
                else:
                    print("🔄 使用点到点运动执行")
                    self._move_to_teaching_point_direct(teaching_point)
            else:
                # 使用当前界面参数
                interpolation_params = self.parent._get_current_interpolation_params()
                current_mode = self.parent.get_current_mode()
                
                print(f"🎯 使用当前界面参数移动到示教点")
                print(f"   当前插补类型: {self.interpolation_type}")
                print(f"   当前模式: {current_mode}")
                
                if current_mode == "joint":
                    # 关节模式：直接控制关节角度，不使用插补
                    print("🎯 关节模式：直接控制关节角度")
                    self._move_to_teaching_point_direct(teaching_point)
                elif self.interpolation_type == "cartesian":
                    # 笛卡尔空间插补
                    if not self._initialize_cartesian_executor():
                        QMessageBox.warning(self.parent, "警告", "笛卡尔插补器初始化失败")
                        return False
                    self._move_to_teaching_point_cartesian_interpolation(teaching_point, interpolation_params)
                elif self.interpolation_type == "joint":
                    # 关节空间插补
                    if not self._initialize_joint_executor():
                        QMessageBox.warning(self.parent, "警告", "关节插补器初始化失败")
                        return False
                    self._move_to_teaching_point_joint_space_interpolation(teaching_point, interpolation_params)
                elif self.interpolation_type == "point_to_point":
                    # 点到点运动
                    print("🎯 使用点到点运动到示教点")
                    self._move_to_teaching_point_direct(teaching_point)
                else:
                    # 默认直接运动
                    print("⚠️ 插补类型未识别，使用直接运动")
                    self._move_to_teaching_point_direct(teaching_point)
            
            return True
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"移动到示教点失败: {str(e)}")
            return False
    
    # 以下是具体的运动实现方法，将原有的方法移动到这里
    def _move_base_translation_direct(self, axis, distance):
        """直接基座平移（原有逻辑）"""
        try:
            # 直接使用输出端角度状态，不从电机读取
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿（返回4x4矩阵）
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 计算目标变换矩阵
            target_transform = current_transform.copy()
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            target_transform[axis_index, 3] += distance  # 修改位置部分
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败，可能超出工作空间")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取原始解和规范化解
            target_joints_display = solution_result['original']    # 用于界面显示
            target_joints_control = solution_result['normalized']  # 用于电机控制
            
            # 更新输出端角度状态（使用原始解进行显示）
            self.parent.output_joint_angles = list(target_joints_display)
            
            # 执行运动到目标关节角度（使用规范化解控制电机）
            self.parent.move_to_joint_angles(target_joints_control)
            
            # 更新界面显示
            self.parent.update_joint_angle_labels()
            self.parent.update_end_effector_pose()
            
            print(f"✅ 基座{axis.upper()}轴平移 {distance:+.1f}mm 执行成功")
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"基座平移出错: {str(e)}")
    
    def _move_tool_translation_direct(self, axis, distance):
        """直接工具平移（原有逻辑）"""
        try:
            # 直接使用输出端角度状态，不从电机读取
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿（返回4x4矩阵）
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 在工具坐标系中计算位移
            import numpy as np
            target_transform = current_transform.copy()
            
            # 创建工具坐标系中的位移向量
            tool_displacement = np.array([0.0, 0.0, 0.0])
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            tool_displacement[axis_index] = distance
            
            # 将工具坐标系位移转换到基座坐标系
            R_current = current_transform[:3, :3]  # 当前姿态矩阵
            base_displacement = R_current @ tool_displacement
            
            # 应用位移
            target_transform[:3, 3] += base_displacement
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取原始解和规范化解
            target_joints_display = solution_result['original']    # 用于界面显示
            target_joints_control = solution_result['normalized']  # 用于电机控制
            
            # 更新输出端角度状态（使用原始解进行显示）
            self.parent.output_joint_angles = list(target_joints_display)
            
            # 执行运动到目标关节角度（使用规范化解控制电机）
            self.parent.move_to_joint_angles(target_joints_control)
            
            # 更新界面显示
            self.parent.update_joint_angle_labels()
            self.parent.update_end_effector_pose()
            
            print(f"✅ 工具{axis.upper()}轴平移 {distance:+.1f}mm 执行成功")
            
        except Exception as e:
            QMessageBox.critical(self.parent, "错误", f"工具平移出错: {str(e)}")
    
    def _move_to_teaching_point_direct(self, teaching_point):
        """直接移动到示教点（原有逻辑）"""
        try:
            target_joints = teaching_point['joint_angles']
            
            # 更新输出端角度状态
            self.parent.output_joint_angles = list(target_joints)
            
            # 执行运动到目标关节角度
            self.parent.move_to_joint_angles(target_joints)
            
            print(f"✅ 直接运动到示教点执行完成")
            
        except Exception as e:
            print(f"❌ 直接运动到示教点失败: {e}")
            raise
    
    # ========== 插补相关的具体实现方法 ==========
    
    def _move_base_translation_cartesian(self, axis, distance):
        """使用笛卡尔空间插补的基座坐标系平移（Y板专用）"""
        try:
            # 获取当前末端位姿
            current_joints = self.parent.output_joint_angles.copy()
            pose_info = self.kinematics.get_end_effector_pose(current_joints)
            current_position = np.array(pose_info['position'])  # [x, y, z] mm
            current_orientation = np.array(pose_info['euler_angles'])  # [yaw, pitch, roll] 度
            
            # 计算目标位置
            target_position = current_position.copy()
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            target_position[axis_index] += distance
            
            # 初始化笛卡尔执行器
            if not self._initialize_cartesian_executor():
                QMessageBox.warning(self.parent, "警告", "笛卡尔插补器初始化失败")
                return
            
            # 使用轨迹执行器规划轨迹（使用用户设置的参数）
            success = self.cartesian_executor.plan_cartesian_trajectory(
                current_position, current_orientation,
                target_position, current_orientation,
                max_linear_velocity=self.cartesian_linear_velocity,
                max_angular_velocity=self.cartesian_angular_velocity,
                max_linear_acceleration=self.cartesian_linear_acceleration,
                max_angular_acceleration=self.cartesian_angular_acceleration
            )
            
            if not success:
                QMessageBox.warning(self.parent, "警告", "笛卡尔轨迹规划失败")
                return
            
            # 生成轨迹点
            current_joints = self.parent.output_joint_angles.copy()
            trajectory_points = self.cartesian_executor.generate_trajectory_points(current_joints)
            
            
            if not trajectory_points:
                QMessageBox.warning(self.parent, "警告", "轨迹点生成失败")
                return
            
            # 同步执行轨迹（避免线程安全问题）
            self._execute_cartesian_trajectory_sync()
            
            print(f"✅ 笛卡尔空间插补基座{axis.upper()}轴平移 {distance:+.1f}mm 执行完成")
            
        except Exception as e:
            print(f"❌ 笛卡尔空间插补平移失败: {e}")
            QMessageBox.critical(self.parent, "错误", f"笛卡尔空间插补平移失败: {str(e)}")
    
    def _move_base_translation_joint(self, axis, distance):
        """使用关节空间插补的基座坐标系平移（Y板专用）
        
        真正的关节空间插补：
        1. 计算目标位置对应的关节角度
        2. 在关节空间进行插补（各关节独立运动）
        3. 末端轨迹自然形成曲线
        """
        try:
            import time
            # 获取当前关节角度
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 计算目标变换矩阵
            target_transform = current_transform.copy()
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            target_transform[axis_index, 3] += distance  # 修改位置部分
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败，可能超出工作空间")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取目标关节角度
            target_joints = solution_result['normalized']  # 用于电机控制
            
            print(f"📐 基座{axis.upper()}轴关节空间插补:")
            print(f"  起始: {[f'{j:.1f}°' for j in current_joints]}")
            print(f"  目标: {[f'{j:.1f}°' for j in target_joints]}")
            
            # 确保关节执行器已初始化
            if not self._initialize_joint_executor():
                QMessageBox.warning(self.parent, "警告", "关节空间插补器初始化失败")
                return
            
            # 规划关节空间轨迹（使用统一的执行器）
            waypoints = [np.array(current_joints), np.array(target_joints)]
            
            # 使用保存的插补参数
            max_velocities = np.array(self.joint_max_velocities)
            max_accelerations = np.array(self.joint_max_accelerations)
            
            success = self.joint_executor.plan_joint_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocities,
                max_acceleration=max_accelerations
            )
            
            if not success:
                QMessageBox.warning(self.parent, "警告", "关节空间轨迹规划失败")
                return

            # 生成轨迹点
            trajectory_points = self.joint_executor.generate_trajectory_points()
            if not trajectory_points:
                QMessageBox.warning(self.parent, "警告", "轨迹点生成失败")
                return
            
            # 使用现有的同步执行方法
            self._execute_joint_trajectory_sync()
            
            # 更新输出端角度状态
            self.parent.output_joint_angles = list(target_joints)
            
            
        except Exception as e:
            print(f"❌ 关节空间插补平移失败: {e}")
            QMessageBox.critical(self.parent, "错误", f"关节空间插补平移失败: {str(e)}")
    
    def _move_tool_translation_cartesian(self, axis, distance):
        """使用笛卡尔空间插补的工具坐标系平移（Y板专用）"""
        try:
            import numpy as np
            
            # 获取当前末端位姿
            current_joints = self.parent.output_joint_angles.copy()
            pose_info = self.kinematics.get_end_effector_pose(current_joints)
            current_position = np.array(pose_info['position'])  # [x, y, z] mm
            current_orientation = np.array(pose_info['euler_angles'])  # [yaw, pitch, roll] 度
            
            # 获取当前变换矩阵
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 在工具坐标系中计算位移
            tool_displacement = np.array([0.0, 0.0, 0.0])
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            tool_displacement[axis_index] = distance
            
            # 将工具坐标系位移转换到基座坐标系
            R_current = current_transform[:3, :3]  # 当前姿态矩阵
            base_displacement = R_current @ tool_displacement
            
            # 计算目标位置
            target_position = current_position + base_displacement
            
            # 初始化笛卡尔执行器
            if not self._initialize_cartesian_executor():
                QMessageBox.warning(self.parent, "警告", "笛卡尔插补器初始化失败")
                return
            
            # 使用轨迹执行器规划轨迹（使用用户设置的参数）
            success = self.cartesian_executor.plan_cartesian_trajectory(
                current_position, current_orientation,
                target_position, current_orientation,
                max_linear_velocity=self.cartesian_linear_velocity,
                max_angular_velocity=self.cartesian_angular_velocity,
                max_linear_acceleration=self.cartesian_linear_acceleration,
                max_angular_acceleration=self.cartesian_angular_acceleration
            )
            
            if not success:
                QMessageBox.warning(self.parent, "警告", "笛卡尔轨迹规划失败")
                return
            
            # 生成轨迹点
            current_joints = self.parent.output_joint_angles.copy()
            trajectory_points = self.cartesian_executor.generate_trajectory_points(current_joints)
            
            
            if not trajectory_points:
                QMessageBox.warning(self.parent, "警告", "轨迹点生成失败")
                return
            
            # 同步执行轨迹（避免线程安全问题）
            self._execute_cartesian_trajectory_sync()
            
            print(f"✅ 笛卡尔空间插补工具{axis.upper()}轴平移 {distance:+.1f}mm 执行完成")
            
        except Exception as e:
            print(f"❌ 笛卡尔空间插补工具平移失败: {e}")
            QMessageBox.critical(self.parent, "错误", f"笛卡尔空间插补工具平移失败: {str(e)}")
    
    def _move_tool_translation_joint(self, axis, distance):
        """使用关节空间插补的工具坐标系平移（Y板专用）
        
        真正的关节空间插补：
        1. 计算目标位置对应的关节角度
        2. 在关节空间进行插补（各关节独立运动）
        3. 末端轨迹自然形成曲线
        """
        try:
            import time
            # 获取当前关节角度
            current_joints = self.parent.output_joint_angles.copy()
            
            # 正运动学计算当前末端位姿
            current_transform = self.kinematics.forward_kinematics(current_joints)
            if current_transform is None:
                QMessageBox.warning(self.parent, "警告", "正运动学计算失败")
                return
            
            # 在工具坐标系中计算位移
            import numpy as np
            target_transform = current_transform.copy()
            
            # 创建工具坐标系中的位移向量
            tool_displacement = np.array([0.0, 0.0, 0.0])
            axis_index = {'x': 0, 'y': 1, 'z': 2}[axis]
            tool_displacement[axis_index] = distance
            
            # 将工具坐标系位移转换到基座坐标系
            R_current = current_transform[:3, :3]  # 当前姿态矩阵
            base_displacement = R_current @ tool_displacement
            
            # 应用位移
            target_transform[:3, 3] += base_displacement
            
            # 逆运动学计算目标关节角度
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            if solutions is None or len(solutions) == 0:
                QMessageBox.warning(self.parent, "警告", "逆运动学求解失败")
                return
            
            # 选择与当前角度最接近的解
            solution_result = self.parent.kinematics.select_closest_solution(solutions, current_joints)
            if solution_result is None:
                QMessageBox.warning(self.parent, "警告", "未找到有效的逆运动学解")
                return
            
            # 获取目标关节角度
            target_joints = solution_result['normalized']  # 用于电机控制
            
            print(f"📐 工具{axis.upper()}轴关节空间插补:")
            print(f"  起始: {[f'{j:.1f}°' for j in current_joints]}")
            print(f"  目标: {[f'{j:.1f}°' for j in target_joints]}")
            
            # 确保关节执行器已初始化
            if not self._initialize_joint_executor():
                QMessageBox.warning(self.parent, "警告", "关节空间插补器初始化失败")
                return
            
            # 规划关节空间轨迹（使用统一的执行器）
            waypoints = [np.array(current_joints), np.array(target_joints)]
            
            # 使用保存的插补参数
            max_velocities = np.array(self.joint_max_velocities)
            max_accelerations = np.array(self.joint_max_accelerations)
            
            success = self.joint_executor.plan_joint_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocities,
                max_acceleration=max_accelerations
            )
            
            if not success:
                QMessageBox.warning(self.parent, "警告", "关节空间轨迹规划失败")
                return
            
            
            # 生成轨迹点
            trajectory_points = self.joint_executor.generate_trajectory_points()
            if not trajectory_points:
                QMessageBox.warning(self.parent, "警告", "轨迹点生成失败")
                return
            
            # 使用现有的同步执行方法
            self._execute_joint_trajectory_sync()
            
            # 更新输出端角度状态
            self.parent.output_joint_angles = list(target_joints)

            
        except Exception as e:
            print(f"❌ 关节空间插补工具平移失败: {e}")
            QMessageBox.critical(self.parent, "错误", f"关节空间插补工具平移失败: {str(e)}")
    
    def _move_to_teaching_point_cartesian_interpolation(self, teaching_point, interpolation_params):
        """使用笛卡尔空间插补移动到示教点"""
        try:
            # 获取当前位姿
            if not self.kinematics:
                raise Exception("运动学模块未初始化")
                
            current_pose = self.kinematics.get_end_effector_pose(self.parent.output_joint_angles)
            current_position = np.array(current_pose['position'])
            current_orientation = np.array(current_pose['euler_angles'])
            
            # 计算目标位姿（从目标关节角度）
            target_pose = self.kinematics.get_end_effector_pose(teaching_point['joint_angles'])
            target_position = np.array(target_pose['position'])
            target_orientation = np.array(target_pose['euler_angles'])
            
            # 确保笛卡尔执行器已初始化
            if not self._initialize_cartesian_executor():
                raise Exception("笛卡尔空间插补器初始化失败")
            
            # 获取插补参数
            max_linear_velocity = interpolation_params.get('linear_velocity', 50.0)
            max_angular_velocity = interpolation_params.get('angular_velocity', 30.0)
            max_linear_acceleration = interpolation_params.get('linear_acceleration', 100.0)
            max_angular_acceleration = interpolation_params.get('angular_acceleration', 60.0)
            
            # 规划笛卡尔轨迹
            success = self.cartesian_executor.plan_cartesian_trajectory(
                current_position, current_orientation,
                target_position, target_orientation,
                max_linear_velocity=max_linear_velocity,
                max_angular_velocity=max_angular_velocity,
                max_linear_acceleration=max_linear_acceleration,
                max_angular_acceleration=max_angular_acceleration
            )
            
            if not success:
                raise Exception("笛卡尔轨迹规划失败")
            
            # 生成轨迹点
            current_joints = self.parent.output_joint_angles.copy()
            trajectory_points = self.cartesian_executor.generate_trajectory_points(current_joints)
            
            if not trajectory_points:
                raise Exception("轨迹点生成失败")
            
            # 同步执行轨迹（避免线程安全问题）
            self._execute_cartesian_trajectory_sync()
            
            # 更新输出端角度状态
            self.parent.output_joint_angles = list(teaching_point['joint_angles'])
            print(f"✅ 笛卡尔空间插补执行完成")
        
        except Exception as e:
            print(f"❌ 笛卡尔空间插补执行失败: {e}")
            raise
    
    def _move_to_teaching_point_joint_space_interpolation(self, teaching_point, interpolation_params):
        """使用关节空间插补移动到示教点"""
        try:
            current_angles = np.array(self.parent.output_joint_angles.copy())
            target_angles = np.array(teaching_point['joint_angles'])
            
            print(f"📐 关节空间插补: {current_angles} -> {target_angles}")
            
            # 确保关节执行器已初始化
            if not self._initialize_joint_executor():
                raise Exception("关节空间插补器初始化失败")
            
            # 规划关节空间轨迹
            waypoints = [current_angles, target_angles]
            
            # 使用保存的插补参数：从上位机的单一值扩展为6个关节
            single_velocity = interpolation_params.get('joint_max_velocity', 30.0)
            single_acceleration = interpolation_params.get('joint_max_acceleration', 60.0)
            
            # 所有6个关节使用相同的速度和加速度值
            max_velocities = np.array([single_velocity] * 6)
            max_accelerations = np.array([single_acceleration] * 6)
            
            success = self.joint_executor.plan_joint_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocities,
                max_acceleration=max_accelerations
            )
            
            if not success:
                raise Exception("关节空间轨迹规划失败")
            
            # 生成轨迹点
            trajectory_points = self.joint_executor.generate_trajectory_points()
            
            if not trajectory_points:
                raise Exception("轨迹点生成失败")
            
            # 同步执行轨迹（避免线程安全问题）
            self._execute_joint_trajectory_sync()
            
            # 更新输出端角度状态
            self.output_joint_angles = list(target_angles)
            print(f"✅ 关节空间插补执行完成")
        
        except Exception as e:
            print(f"❌ 关节空间插补执行失败: {e}")
            raise
    
    def _execute_cartesian_trajectory_sync(self):
        """同步执行笛卡尔轨迹（避免线程安全问题）"""
        try:
            import time
            print("🎯 开始同步执行笛卡尔轨迹...")
            
            while True:
                # 获取下一个电机命令
                motor_commands, execution_info = self.cartesian_executor.get_next_motor_commands(
                    self.parent.output_joint_angles, self.parent.speed
                )
                
                if execution_info.get('finished', False):
                    # 轨迹执行完成
                    if 'error' in execution_info:
                        raise Exception(f"笛卡尔轨迹执行出错: {execution_info['error']}")
                    else:
                        print("✅ 笛卡尔轨迹同步执行完成")
                        # 更新最终状态
                        if 'target_joint_angles' in execution_info:
                            self.parent.output_joint_angles = list(execution_info['target_joint_angles'])
                        # 更新界面显示
                        self.parent.update_joint_angle_labels()
                        self.parent.update_end_effector_pose()
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
                            commands.append(self.parent._build_single_command_for_multi(cmd['motor_id'], func_body))
                        except Exception as cmd_error:
                            print(f"❌ 构建电机命令失败: {cmd_error}")
                            continue
                    
                    # 发送多电机命令
                    if commands and self.motors:
                        try:
                            first_motor = list(self.motors.values())[0]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                        except Exception as send_error:
                            print(f"❌ 发送电机命令失败: {send_error}")
                
                # 更新输出端角度状态
                if 'target_joint_angles' in execution_info:
                    self.parent.output_joint_angles = list(execution_info['target_joint_angles'])
                    # 实时更新界面显示
                    self.parent.update_joint_angle_labels()
                    self.parent.update_end_effector_pose()
                
                # 等待执行间隔
                next_interval = execution_info.get('next_interval', 20)  # 默认20ms
                time.sleep(next_interval / 1000.0)  # 转换为秒
                
        except Exception as e:
            print(f"❌ 同步执行笛卡尔轨迹失败: {e}")
            raise
    
    def _execute_joint_trajectory_sync(self):
        """同步执行关节轨迹（避免线程安全问题）
        
        真正的关节空间插补：实时计算每个时刻的关节角度并发送
        """
        try:
            import time
            print("🎯 开始同步执行关节轨迹...")
            
            # 使用与笛卡尔插补完全一致的索引驱动循环
            while True:
                # 获取下一个电机命令（现在使用索引机制，时间参数保持兼容性）
                motor_commands, execution_info = self.joint_executor.get_next_motor_commands(
                    current_time=0.0,  # 兼容参数，不再用于核心逻辑
                    speed_setting=self.parent.speed
                )
                
                # 检查是否执行完成（与笛卡尔插补一致的完成检测）
                if execution_info.get('finished', False):
                    # 轨迹执行完成
                    if 'error' in execution_info:
                        raise Exception(f"关节轨迹执行出错: {execution_info['error']}")
                    else:
                        print("✅ 关节轨迹同步执行完成")
                        # 更新最终状态
                        if 'target_joint_angles' in execution_info:
                            self.parent.output_joint_angles = list(execution_info['target_joint_angles'])
                        # 更新界面显示
                        self.parent.update_joint_angle_labels()
                        self.parent.update_end_effector_pose()
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
                            commands.append(self.parent._build_single_command_for_multi(cmd['motor_id'], func_body))
                        except Exception as cmd_error:
                            print(f"❌ 构建电机命令失败: {cmd_error}")
                            continue
                    
                    # 发送多电机命令
                    if commands and self.motors:
                        try:
                            first_motor = list(self.motors.values())[0]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                        except Exception as send_error:
                            print(f"❌ 发送电机命令失败: {send_error}")
                
                # 更新输出端角度状态
                if 'target_joint_angles' in execution_info:
                    self.parent.output_joint_angles = list(execution_info['target_joint_angles'])
                    # 实时更新界面显示
                    self.parent.update_joint_angle_labels()
                    self.parent.update_end_effector_pose()           
                
                # 使用与笛卡尔插补完全相同的等待逻辑
                next_interval = execution_info.get('next_interval', 20)  # 默认20ms
                time.sleep(next_interval / 1000.0)  # 转换为秒
            
        except Exception as e:
            print(f"❌ 同步执行关节轨迹失败: {e}")
            raise



#########################################################################################################################################
#########################################################################################################################################
#########################################################################################################################################



class TeachPendantWidget(QWidget):
    """示教器控件"""
    
    def __init__(self):
        super().__init__()
        self.motors = {}  # 电机实例字典
        self.motor_config_manager = motor_config_manager
        self.current_mode = "joint"  # 当前模式：joint, base, tool
        self.step_size = 1.0  # 步进大小
        self.speed = 100  # 运动速度
        self.acceleration = 50  # 加速度
        self.deceleration = 50  # 减速度
        
        # 初始化运动学计算器
        self.kinematics = None
        if KINEMATICS_AVAILABLE:
            try:
                self.kinematics = create_configured_kinematics()
            except Exception as e:
                print(f"运动学计算器初始化失败: {e}")
                self.kinematics = None
        
        # 当前关节角度缓存
        self.current_joint_angles = [0.0] * 6
        
        # 输出端角度状态管理（类似digital_twin_widget的joint_spins）
        self.output_joint_angles = [0.0] * 6  # 维护输出端角度状态
        
        # 创建运动控制器
        self.motion_controller = MotionController(self)
        
        # 示教编程数据管理
        self.teaching_program = []  # 存储示教点列表
        self.current_teaching_index = -1  # 当前选中的示教点索引
        self.execution_count = 0  # 程序执行次数计数器
        
        # 插补类型设置
        self.interpolation_type = "joint"  # "joint" 或 "cartesian"
        
        # 动态参数管理
        self.current_board_type = "X"  # X板或Y板
        self.parameter_widgets = {}  # 存储参数控件的引用
        
        # 参数缓存机制 - 为不同模式和插补类型组合保存参数值
        self.parameter_cache = {
            # 格式: f"{board_type}_{interpolation_type}_{mode}": {param_name: value}
        }
        
        # 笛卡尔空间参数
        self.cartesian_linear_velocity = 150.0    # mm/s
        self.cartesian_angular_velocity = 90.0   # deg/s
        self.cartesian_linear_acceleration = 300.0  # mm/s²
        self.cartesian_angular_acceleration = 180.0  # deg/s²
        
        # 关节空间参数
        self.joint_max_velocities = [90.0, 90.0, 90.0, 90.0, 90.0, 90.0]  # deg/s for each joint
        self.joint_max_accelerations = [180.0, 180.0, 180.0, 180.0, 180.0, 180.0]  # deg/s² for each joint
        
        # 保持向后兼容的属性（用于现有代码）
        self.cartesian_interpolator = None
        self.cartesian_executor = None
        self.joint_executor = None
        
        self.init_ui()
        
    
    def init_ui(self):
        """初始化用户界面"""
        # 设置窗口属性
        self.setWindowTitle("机械臂示教器 - Horizon 具身智能系统")
        self.setGeometry(10, 50, 1200, 1000)  # 保持原有尺寸
        self.setMinimumSize(1000, 800)  # 稍微增加最小高度，确保内容能完整显示
        
        # 设置窗口图标
        current_dir = os.path.dirname(os.path.abspath(__file__))
        icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
        if os.path.exists(icon_path):
            from PyQt5.QtGui import QIcon
            self.setWindowIcon(QIcon(icon_path))
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)
        
        # 创建运动参数设置区域（固定）
        self.create_parameter_settings(layout)
        
        # 创建模式选择区域 - 使用标签页风格（固定）
        self.create_mode_selection(layout)
    
    def create_mode_selection(self, parent_layout):
        """创建模式选择区域 - 使用标签页风格"""
        # 直接创建标签页控件，不需要额外的GroupBox
        self.mode_tab_widget = QTabWidget()
        # 移除高度限制，让内容自然展开
        
        # 创建三个标签页对应三种模式
        # 关节模式标签页
        self.joint_mode_tab = QWidget()
        self.mode_tab_widget.addTab(self.joint_mode_tab, "🔧 关节模式")
        
        # 基座模式标签页  
        self.base_mode_tab = QWidget()
        self.mode_tab_widget.addTab(self.base_mode_tab, "🌐 基座模式")
        
        # 工具模式标签页
        self.tool_mode_tab = QWidget()
        self.mode_tab_widget.addTab(self.tool_mode_tab, "🔨 工具模式")
        
        # 示教编程标签页
        self.teaching_program_tab = QWidget()
        self.mode_tab_widget.addTab(self.teaching_program_tab, "📝 示教编程")
        
        # 连接标签页切换事件
        self.mode_tab_widget.currentChanged.connect(self.on_mode_tab_changed)
        
        # 创建各个模式的内容
        self.create_joint_mode_content()
        self.create_base_mode_content()
        self.create_tool_mode_content()
        self.create_teaching_program_content()
        
        parent_layout.addWidget(self.mode_tab_widget)
        
        # 初始化时手动触发一次模式切换，确保步进大小单位正确显示
        self.on_mode_tab_changed(0)  # 默认选择第一个标签页（关节模式）
    
    def on_mode_tab_changed(self, index):
        """标签页切换事件"""
        current_tab = self.mode_tab_widget.currentWidget()
        
        # 处理前三个标签页的模式切换逻辑
        mode_map = {0: "joint", 1: "base", 2: "tool"}
        mode_names = {0: "关节模式", 1: "基座模式", 2: "工具模式"}
        
        if index in mode_map:
            self.current_mode = mode_map[index]
            
            # 根据模式设置步进大小的范围和单位
            if self.current_mode == "joint":
                # 关节模式：范围1-360，单位为度
                self.step_size_spinbox.setRange(1.0, 360.0)
                self.step_size_spinbox.setSuffix("°")
                # 更新范围显示标签
                if hasattr(self, 'step_range_label') and self.step_range_label is not None:
                    self.step_range_label.setText("(1.0-360.0)")
                # 如果当前值小于1，重置为1
                if self.step_size_spinbox.value() < 1.0:
                    self.step_size_spinbox.setValue(1.0)
                
                # 关节模式下，强制设置插补类型为点到点，并禁用其他选项
                if hasattr(self, 'interpolation_type_combo'):
                    # 临时断开信号连接，避免触发处理函数
                    self.interpolation_type_combo.currentTextChanged.disconnect()
                    
                    # 设置为点到点模式
                    self.interpolation_type_combo.setCurrentText("点到点")
                    self.interpolation_type = "point_to_point"
                    self.interpolation_info_label.setText("📌 点到点：直接运动到目标位置")
                    
                    # 禁用插补类型选择框
                    self.interpolation_type_combo.setEnabled(False)
                    self.interpolation_type_combo.setToolTip("关节模式下只能使用点到点运动")
                    
                    # 重新连接信号
                    self.interpolation_type_combo.currentTextChanged.connect(self.on_interpolation_type_changed)

            else:
                # 基座模式和工具模式：范围0.1-360，单位为mm
                self.step_size_spinbox.setRange(0.1, 360.0)
                self.step_size_spinbox.setSuffix(" mm")
                # 更新范围显示标签
                if hasattr(self, 'step_range_label') and self.step_range_label is not None:
                    self.step_range_label.setText("(0.1-360.0)")
                # 如果当前值为整数且大于等于1，可以保持；如果需要更精确，可以设为0.1
                if self.step_size_spinbox.value() == 1.0:
                    self.step_size_spinbox.setValue(1.0)  # 保持1.0作为合理默认值
                
                # 基座模式和工具模式下，恢复插补类型选择
                if hasattr(self, 'interpolation_type_combo'):
                    # 确保有所有插补选项
                    if self.interpolation_type_combo.count() != 3:
                        # 临时断开信号
                        try:
                            self.interpolation_type_combo.currentTextChanged.disconnect()
                        except:
                            pass
                        
                        # 清空并重新添加所有选项
                        self.interpolation_type_combo.clear()
                        self.interpolation_type_combo.addItems(["关节空间插补", "笛卡尔空间插补", "点到点"])
                        
                        # 重新连接信号
                        self.interpolation_type_combo.currentTextChanged.connect(self.on_interpolation_type_changed)
                    
                    # 启用插补类型选择框
                    self.interpolation_type_combo.setEnabled(True)
                    self.interpolation_type_combo.setToolTip("选择运动插补类型\n关节空间：各关节独立运动\n笛卡尔空间：末端直线运动\n点到点：直接运动到目标位置")
                    
                    # 如果之前是点到点（从关节模式切换过来），默认切换到笛卡尔
                    if self.interpolation_type == "point_to_point":
                        self.interpolation_type_combo.setCurrentText("笛卡尔空间插补")
                        self.interpolation_type = "cartesian"
                        self.interpolation_info_label.setText("📌 笛卡尔空间：末端沿直线运动到目标")
            
            # 更新按钮文字
            self.update_button_texts()
            
            # 更新参数显示（根据当前模式显示相应的参数）
            if hasattr(self, 'interpolation_type'):
                # 检测当前板卡类型
                current_board_type = "Y" if self._is_y_board() else "X"
                self.switch_parameter_display(current_board_type, self.interpolation_type, self.current_mode)
            
        elif current_tab == self.teaching_program_tab:
            print("切换到示教编程模式")
            # 示教编程模式：范围0.1-360，单位为mm
            if hasattr(self, 'step_size_spinbox'):
                self.step_size_spinbox.setRange(0.1, 360.0)
                self.step_size_spinbox.setSuffix(" mm")
                # 更新范围显示标签
                if hasattr(self, 'step_range_label') and self.step_range_label is not None:
                    self.step_range_label.setText("(0.1-360.0)")
                # 如果当前值为1.0，保持不变作为合理默认值
                if self.step_size_spinbox.value() == 1.0:
                    self.step_size_spinbox.setValue(1.0)
        
        # 根据当前模式控制保存示教点按钮的可用状态
        if hasattr(self, 'save_teaching_point_btn'):
            # 只有在关节、基座、工具模式下才能保存示教点
            if current_tab in [self.joint_mode_tab, self.base_mode_tab, self.tool_mode_tab]:
                # 进一步检查插补类型：只有笛卡尔插补才能保存
                self.update_save_button_state()
            else:
                # 在示教编程模式下禁用
                self.save_teaching_point_btn.setEnabled(False)
                self.save_teaching_point_btn.setToolTip("请切换到关节模式、基座模式或工具模式后再保存示教点")
        
        # 同步输出端角度状态
        self.sync_output_angles_from_motors()
    
    def create_joint_mode_content(self):
        """创建关节模式标签页内容"""
        layout = QVBoxLayout(self.joint_mode_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
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
        scroll_layout.setSpacing(10)
        
        # 模式说明
        info_label = QLabel("💡 关节模式: 直接控制各个关节的转动，每个关节独立运动")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-radius: 4px;")
        info_label.setWordWrap(True)
        scroll_layout.addWidget(info_label)
        
        # 创建关节控制按钮
        self.create_joint_mode_buttons(scroll_layout)
        
        # 创建状态显示区域
        self.create_independent_status_display(scroll_layout)
        
        scroll_layout.addStretch()  # 添加弹性空间
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def create_base_mode_content(self):
        """创建基座模式标签页内容"""
        layout = QVBoxLayout(self.base_mode_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
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
        scroll_layout.setSpacing(10)
        
        # 模式说明
        info_label = QLabel("🌐 基座模式(世界模式): 相对于基座坐标系移动机械臂末端，支持XYZ平移和Roll/Pitch/Yaw旋转")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-radius: 4px;")
        info_label.setWordWrap(True)
        scroll_layout.addWidget(info_label)
        
        # 创建基座控制按钮
        self.create_base_mode_buttons(scroll_layout)
        
        # 创建状态显示区域
        self.create_independent_status_display(scroll_layout)
        
        scroll_layout.addStretch()  # 添加弹性空间
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def create_tool_mode_content(self):
        """创建工具模式标签页内容"""
        layout = QVBoxLayout(self.tool_mode_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
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
        scroll_layout.setSpacing(10)
        
        # 模式说明
        info_label = QLabel("🔨 工具模式: 相对于机械臂坐标系移动机械臂，运动方向跟随末端执行器姿态")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-radius: 4px;")
        info_label.setWordWrap(True)
        scroll_layout.addWidget(info_label)
        
        # 创建工具控制按钮
        self.create_tool_mode_buttons(scroll_layout)
        
        # 添加手眼标定位置保存功能
        self.create_hand_eye_save_section(scroll_layout)
        
        # 创建状态显示区域
        self.create_independent_status_display(scroll_layout)
        
        scroll_layout.addStretch()  # 添加弹性空间
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def create_parameter_settings(self, parent_layout):
        """创建运动参数设置区域"""
        group = QGroupBox("运动参数设置")
        group.setMinimumHeight(180)  # 增加高度以容纳更多控件
        group.setMaximumHeight(220)  # 设置最大高度
        main_layout = QVBoxLayout(group)  # 改为垂直布局
        main_layout.setContentsMargins(15, 10, 15, 10)  # 设置边距
        main_layout.setSpacing(8)  # 设置间距
        
        # 第一行：插补类型选择
        interpolation_layout = QHBoxLayout()
        interpolation_layout.setSpacing(15)
        
        interpolation_label = QLabel("插补类型:")
        interpolation_label.setStyleSheet("font-size: 11px; color: #666;")
        interpolation_layout.addWidget(interpolation_label)
        
        self.interpolation_type_combo = QComboBox()
        self.interpolation_type_combo.addItems(["关节空间插补", "笛卡尔空间插补", "点到点"])
        self.interpolation_type_combo.setFixedWidth(150)
        self.interpolation_type_combo.setToolTip("选择运动插补类型\n关节空间：各关节独立运动\n笛卡尔空间：末端直线运动\n点到点：直接运动到目标位置")
        self.interpolation_type_combo.currentTextChanged.connect(self.on_interpolation_type_changed)
        interpolation_layout.addWidget(self.interpolation_type_combo)
        
        # 插补类型说明标签
        self.interpolation_info_label = QLabel("📌 关节空间：各关节独立运动到目标")
        self.interpolation_info_label.setStyleSheet("font-size: 10px; color: #888;")
        interpolation_layout.addWidget(self.interpolation_info_label)
        
        interpolation_layout.addStretch()
        main_layout.addLayout(interpolation_layout)
        
        # 第二行：动态运动参数区域
        self.params_container = QHBoxLayout()
        self.params_container.setSpacing(20)
        
        # 创建参数区域容器（用于动态切换）
        self.dynamic_params_widget = QWidget()
        self.dynamic_params_layout = QHBoxLayout(self.dynamic_params_widget)
        self.dynamic_params_layout.setContentsMargins(0, 0, 0, 0)
        self.dynamic_params_layout.setSpacing(20)
        
        # 初始创建通用参数（步进大小）
        self.create_step_size_param()
        
        # 初始创建X板参数（默认）
        self.create_x_board_params()
        
        self.params_container.addWidget(self.dynamic_params_widget)
        
        # 添加弹性空间
        self.params_container.addStretch()
        
        # 右侧：功能按钮区域
        # 刷新按钮
        self.refresh_position_btn = QPushButton("🔄 刷新状态")
        self.refresh_position_btn.setFixedSize(85, 35)
        self.refresh_position_btn.setStyleSheet("""
            QPushButton {
                background-color: #607D8B;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
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
        self.refresh_position_btn.setToolTip("刷新关节角度和末端位姿显示")
        self.params_container.addWidget(self.refresh_position_btn)
        
        # 回零按钮
        self.home_position_btn = QPushButton("🏠 回零位")
        self.home_position_btn.setFixedSize(85, 35)
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
        self.home_position_btn.clicked.connect(self.go_home_position)
        self.home_position_btn.setToolTip("将所有关节回到零位")
        self.params_container.addWidget(self.home_position_btn)
        
        # 保存示教位置按钮
        self.save_teaching_point_btn = QPushButton("📍 保存示教点")
        self.save_teaching_point_btn.setFixedSize(95, 35)
        self.save_teaching_point_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 5px 10px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.save_teaching_point_btn.clicked.connect(self.save_teaching_point)
        self.save_teaching_point_btn.setToolTip("保存当前位置和运动参数为示教点")
        self.params_container.addWidget(self.save_teaching_point_btn)
        
        # 将参数容器添加到主布局
        main_layout.addLayout(self.params_container)
        
        parent_layout.addWidget(group)
    
    def create_step_size_param(self):
        """创建步进大小参数（通用）"""
        step_container = QVBoxLayout()
        step_container.setAlignment(Qt.AlignCenter)
        step_container.setSpacing(3)
        
        step_label = QLabel("步进大小")
        step_label.setAlignment(Qt.AlignCenter)
        step_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        self.step_range_label = QLabel("(1.0-360.0)")
        self.step_range_label.setAlignment(Qt.AlignCenter)
        self.step_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.step_size_spinbox = QDoubleSpinBox()
        self.step_size_spinbox.setRange(1.0, 360.0)  # 默认以关节模式的范围初始化
        self.step_size_spinbox.setValue(1.0)
        self.step_size_spinbox.setSuffix("°")  # 默认以度数初始化
        self.step_size_spinbox.setFixedWidth(130)
        self.step_size_spinbox.setAlignment(Qt.AlignCenter)
        self.step_size_spinbox.valueChanged.connect(self.update_step_size)
        
        step_container.addWidget(step_label)
        step_container.addWidget(self.step_size_spinbox)
        step_container.addWidget(self.step_range_label)
        
        self.dynamic_params_layout.addLayout(step_container)
        self.parameter_widgets['step_size'] = [step_label, self.step_size_spinbox, self.step_range_label]
    
    def create_x_board_params(self):
        """创建梯形曲线参数（X板专用，Y板关节模式下用于单关节运动）"""
        # 最大速度
        speed_container = QVBoxLayout()
        speed_container.setAlignment(Qt.AlignCenter)
        speed_container.setSpacing(3)
        
        speed_label = QLabel("最大速度")
        speed_label.setAlignment(Qt.AlignCenter)
        speed_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        speed_range_label = QLabel("(1-3000)")
        speed_range_label.setAlignment(Qt.AlignCenter)
        speed_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.max_speed_spinbox = QSpinBox()
        self.max_speed_spinbox.setRange(1, 3000)
        self.max_speed_spinbox.setValue(200)
        self.max_speed_spinbox.setSuffix(" RPM")
        self.max_speed_spinbox.setFixedWidth(130)
        self.max_speed_spinbox.setAlignment(Qt.AlignCenter)
        self.max_speed_spinbox.valueChanged.connect(self.update_max_speed)
        
        speed_container.addWidget(speed_label)
        speed_container.addWidget(self.max_speed_spinbox)
        speed_container.addWidget(speed_range_label)
        self.dynamic_params_layout.addLayout(speed_container)
         
        # 加速度
        acc_container = QVBoxLayout()
        acc_container.setAlignment(Qt.AlignCenter)
        acc_container.setSpacing(3)
        
        acc_label = QLabel("加速度")
        acc_label.setAlignment(Qt.AlignCenter)
        acc_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        acc_range_label = QLabel("(1-3000)")
        acc_range_label.setAlignment(Qt.AlignCenter)
        acc_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.acceleration_spinbox = QSpinBox()
        self.acceleration_spinbox.setRange(1, 3000)
        self.acceleration_spinbox.setValue(500)
        self.acceleration_spinbox.setSuffix(" RPM/s")
        self.acceleration_spinbox.setFixedWidth(130)
        self.acceleration_spinbox.setAlignment(Qt.AlignCenter)
        self.acceleration_spinbox.valueChanged.connect(self.update_acceleration)
        
        acc_container.addWidget(acc_label)
        acc_container.addWidget(self.acceleration_spinbox)
        acc_container.addWidget(acc_range_label)
        self.dynamic_params_layout.addLayout(acc_container)
        
        # 减速度
        dec_container = QVBoxLayout()
        dec_container.setAlignment(Qt.AlignCenter)
        dec_container.setSpacing(3)
        
        dec_label = QLabel("减速度")
        dec_label.setAlignment(Qt.AlignCenter)
        dec_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        dec_range_label = QLabel("(1-3000)")
        dec_range_label.setAlignment(Qt.AlignCenter)
        dec_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.deceleration_spinbox = QSpinBox()
        self.deceleration_spinbox.setRange(1, 3000)
        self.deceleration_spinbox.setValue(500)
        self.deceleration_spinbox.setSuffix(" RPM/s")
        self.deceleration_spinbox.setFixedWidth(130)
        self.deceleration_spinbox.setAlignment(Qt.AlignCenter)
        self.deceleration_spinbox.valueChanged.connect(self.update_deceleration)
        
        dec_container.addWidget(dec_label)
        dec_container.addWidget(self.deceleration_spinbox)
        dec_container.addWidget(dec_range_label)
        self.dynamic_params_layout.addLayout(dec_container)
        
        # 存储X板参数控件引用
        self.parameter_widgets['x_board'] = [
            speed_label, self.max_speed_spinbox, speed_range_label,
            acc_label, self.acceleration_spinbox, acc_range_label,
            dec_label, self.deceleration_spinbox, dec_range_label
        ]
    
    def create_cartesian_params(self):
        """创建Y板笛卡尔空间参数"""
        # 线性速度
        linear_vel_container = QVBoxLayout()
        linear_vel_container.setAlignment(Qt.AlignCenter)
        linear_vel_container.setSpacing(3)
        
        linear_vel_label = QLabel("线性速度")
        linear_vel_label.setAlignment(Qt.AlignCenter)
        linear_vel_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        linear_vel_range_label = QLabel("(1.0-1000.0)")
        linear_vel_range_label.setAlignment(Qt.AlignCenter)
        linear_vel_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.cartesian_linear_vel_spinbox = QDoubleSpinBox()
        self.cartesian_linear_vel_spinbox.setRange(1.0, 1000.0)
        self.cartesian_linear_vel_spinbox.setValue(150.0)
        self.cartesian_linear_vel_spinbox.setSuffix(" mm/s")
        self.cartesian_linear_vel_spinbox.setFixedWidth(130)
        self.cartesian_linear_vel_spinbox.setAlignment(Qt.AlignCenter)
        self.cartesian_linear_vel_spinbox.valueChanged.connect(self.update_cartesian_linear_velocity)
        
        linear_vel_container.addWidget(linear_vel_label)
        linear_vel_container.addWidget(self.cartesian_linear_vel_spinbox)
        linear_vel_container.addWidget(linear_vel_range_label)
        self.dynamic_params_layout.addLayout(linear_vel_container)
        
        # 角速度
        angular_vel_container = QVBoxLayout()
        angular_vel_container.setAlignment(Qt.AlignCenter)
        angular_vel_container.setSpacing(3)
        
        angular_vel_label = QLabel("角速度")
        angular_vel_label.setAlignment(Qt.AlignCenter)
        angular_vel_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        angular_vel_range_label = QLabel("(1.0-360.0)")
        angular_vel_range_label.setAlignment(Qt.AlignCenter)
        angular_vel_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.cartesian_angular_vel_spinbox = QDoubleSpinBox()
        self.cartesian_angular_vel_spinbox.setRange(1.0, 360.0)
        self.cartesian_angular_vel_spinbox.setValue(90.0)
        self.cartesian_angular_vel_spinbox.setSuffix(" °/s")
        self.cartesian_angular_vel_spinbox.setFixedWidth(130)
        self.cartesian_angular_vel_spinbox.setAlignment(Qt.AlignCenter)
        self.cartesian_angular_vel_spinbox.valueChanged.connect(self.update_cartesian_angular_velocity)
        
        angular_vel_container.addWidget(angular_vel_label)
        angular_vel_container.addWidget(self.cartesian_angular_vel_spinbox)
        angular_vel_container.addWidget(angular_vel_range_label)
        self.dynamic_params_layout.addLayout(angular_vel_container)
        
        # 线性加速度
        linear_acc_container = QVBoxLayout()
        linear_acc_container.setAlignment(Qt.AlignCenter)
        linear_acc_container.setSpacing(3)
        
        linear_acc_label = QLabel("线性加速度")
        linear_acc_label.setAlignment(Qt.AlignCenter)
        linear_acc_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        linear_acc_range_label = QLabel("(10.0-1000.0)")
        linear_acc_range_label.setAlignment(Qt.AlignCenter)
        linear_acc_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.cartesian_linear_acc_spinbox = QDoubleSpinBox()
        self.cartesian_linear_acc_spinbox.setRange(10.0, 1000.0)
        self.cartesian_linear_acc_spinbox.setValue(300.0)
        self.cartesian_linear_acc_spinbox.setSuffix(" mm/s²")
        self.cartesian_linear_acc_spinbox.setFixedWidth(130)
        self.cartesian_linear_acc_spinbox.setAlignment(Qt.AlignCenter)
        self.cartesian_linear_acc_spinbox.valueChanged.connect(self.update_cartesian_linear_acceleration)
        
        linear_acc_container.addWidget(linear_acc_label)
        linear_acc_container.addWidget(self.cartesian_linear_acc_spinbox)
        linear_acc_container.addWidget(linear_acc_range_label)
        self.dynamic_params_layout.addLayout(linear_acc_container)
        
        # 角加速度
        angular_acc_container = QVBoxLayout()
        angular_acc_container.setAlignment(Qt.AlignCenter)
        angular_acc_container.setSpacing(3)
        
        angular_acc_label = QLabel("角加速度")
        angular_acc_label.setAlignment(Qt.AlignCenter)
        angular_acc_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        angular_acc_range_label = QLabel("(10.0-720.0)")
        angular_acc_range_label.setAlignment(Qt.AlignCenter)
        angular_acc_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.cartesian_angular_acc_spinbox = QDoubleSpinBox()
        self.cartesian_angular_acc_spinbox.setRange(10.0, 720.0)
        self.cartesian_angular_acc_spinbox.setValue(180.0)
        self.cartesian_angular_acc_spinbox.setSuffix(" °/s²")
        self.cartesian_angular_acc_spinbox.setFixedWidth(130)
        self.cartesian_angular_acc_spinbox.setAlignment(Qt.AlignCenter)
        self.cartesian_angular_acc_spinbox.valueChanged.connect(self.update_cartesian_angular_acceleration)
        
        angular_acc_container.addWidget(angular_acc_label)
        angular_acc_container.addWidget(self.cartesian_angular_acc_spinbox)
        angular_acc_container.addWidget(angular_acc_range_label)
        self.dynamic_params_layout.addLayout(angular_acc_container)
        
        # 存储笛卡尔参数控件引用
        self.parameter_widgets['cartesian'] = [
            linear_vel_label, self.cartesian_linear_vel_spinbox, linear_vel_range_label,
            angular_vel_label, self.cartesian_angular_vel_spinbox, angular_vel_range_label,
            linear_acc_label, self.cartesian_linear_acc_spinbox, linear_acc_range_label,
            angular_acc_label, self.cartesian_angular_acc_spinbox, angular_acc_range_label
        ]
    
    def create_joint_space_params(self):
        """创建Y板关节空间参数"""
        # 关节速度
        joint_vel_container = QVBoxLayout()
        joint_vel_container.setAlignment(Qt.AlignCenter)
        joint_vel_container.setSpacing(3)
        
        joint_vel_label = QLabel("关节速度")
        joint_vel_label.setAlignment(Qt.AlignCenter)
        joint_vel_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        joint_vel_range_label = QLabel("(5.0-360.0)")
        joint_vel_range_label.setAlignment(Qt.AlignCenter)
        joint_vel_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.joint_max_vel_spinbox = QDoubleSpinBox()
        self.joint_max_vel_spinbox.setRange(5.0, 360.0)
        self.joint_max_vel_spinbox.setValue(90.0)
        self.joint_max_vel_spinbox.setSuffix(" °/s")
        self.joint_max_vel_spinbox.setFixedWidth(130)
        self.joint_max_vel_spinbox.setAlignment(Qt.AlignCenter)
        self.joint_max_vel_spinbox.valueChanged.connect(self.update_joint_max_velocity)
        
        joint_vel_container.addWidget(joint_vel_label)
        joint_vel_container.addWidget(self.joint_max_vel_spinbox)
        joint_vel_container.addWidget(joint_vel_range_label)
        self.dynamic_params_layout.addLayout(joint_vel_container)
        
        # 关节加速度
        joint_acc_container = QVBoxLayout()
        joint_acc_container.setAlignment(Qt.AlignCenter)
        joint_acc_container.setSpacing(3)
        
        joint_acc_label = QLabel("关节加速度")
        joint_acc_label.setAlignment(Qt.AlignCenter)
        joint_acc_label.setStyleSheet("font-size: 11px; color: #666; margin-bottom: 0px;")
        
        joint_acc_range_label = QLabel("(10.0-720.0)")
        joint_acc_range_label.setAlignment(Qt.AlignCenter)
        joint_acc_range_label.setStyleSheet("font-size: 10px; color: #888; margin-top: 0px;")
        
        self.joint_max_acc_spinbox = QDoubleSpinBox()
        self.joint_max_acc_spinbox.setRange(10.0, 720.0)
        self.joint_max_acc_spinbox.setValue(180.0)
        self.joint_max_acc_spinbox.setSuffix(" °/s²")
        self.joint_max_acc_spinbox.setFixedWidth(130)
        self.joint_max_acc_spinbox.setAlignment(Qt.AlignCenter)
        self.joint_max_acc_spinbox.valueChanged.connect(self.update_joint_max_acceleration)
        
        joint_acc_container.addWidget(joint_acc_label)
        joint_acc_container.addWidget(self.joint_max_acc_spinbox)
        joint_acc_container.addWidget(joint_acc_range_label)
        self.dynamic_params_layout.addLayout(joint_acc_container)
        
        # 存储关节空间参数控件引用
        self.parameter_widgets['joint_space'] = [
            joint_vel_label, self.joint_max_vel_spinbox, joint_vel_range_label,
            joint_acc_label, self.joint_max_acc_spinbox, joint_acc_range_label
        ]
    
    def create_y_board_joint_separator(self):
        """创建Y板关节模式下的分隔符和说明"""
        # 创建分隔线
        separator_layout = QVBoxLayout()
        separator_layout.setAlignment(Qt.AlignCenter)
        separator_layout.setSpacing(5)
        
        # 分隔线
        separator_line = QFrame()
        separator_line.setFrameShape(QFrame.VLine)
        separator_line.setFrameShadow(QFrame.Sunken)
        separator_line.setMaximumWidth(2)
        separator_line.setMinimumHeight(40)
        separator_line.setStyleSheet("color: #ccc;")
        
        # 说明标签
        separator_label = QLabel("单关节运动")
        separator_label.setAlignment(Qt.AlignCenter)
        separator_label.setStyleSheet("font-size: 10px; color: #888; font-style: italic;")
        
        separator_layout.addWidget(separator_line)
        separator_layout.addWidget(separator_label)
        
        self.dynamic_params_layout.addLayout(separator_layout)
        
        # 存储分隔符控件引用
        self.parameter_widgets['y_joint_separator'] = [separator_line, separator_label]
    
    def clear_parameter_widgets(self, param_type):
        """清除指定类型的参数控件"""
        if param_type in self.parameter_widgets:
            widgets = self.parameter_widgets[param_type]
            for widget in widgets:
                if widget.parent():
                    widget.setParent(None)
                widget.deleteLater()
            
            # 清除引用
            del self.parameter_widgets[param_type]
            print(f"🗑️ 已清除 {param_type} 参数控件")
            
            # 清除对应的控件引用，避免访问已删除的控件
            if param_type == 'x_board':
                self.max_speed_spinbox = None
                self.acceleration_spinbox = None
                self.deceleration_spinbox = None
            elif param_type == 'cartesian':
                self.cartesian_linear_vel_spinbox = None
                self.cartesian_angular_vel_spinbox = None
                self.cartesian_linear_acc_spinbox = None
            elif param_type == 'joint_space':
                self.joint_max_vel_spinbox = None
                self.joint_max_acc_spinbox = None
    
    def clear_all_parameter_layouts(self):
        """清除所有参数布局（重建参数界面时使用）"""
        # 清除动态参数布局中的所有子项
        while self.dynamic_params_layout.count():
            child = self.dynamic_params_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())
        
        # 清除所有控件引用，避免访问已删除的控件
        self.max_speed_spinbox = None
        self.acceleration_spinbox = None
        self.deceleration_spinbox = None
        self.cartesian_linear_vel_spinbox = None
        self.cartesian_angular_vel_spinbox = None
        self.cartesian_linear_acc_spinbox = None
        self.joint_max_vel_spinbox = None
        self.joint_max_acc_spinbox = None
    
    def _clear_layout(self, layout):
        """递归清除布局中的所有控件"""
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self._clear_layout(child.layout())
    
    def switch_parameter_display(self, board_type, interpolation_type=None, current_mode=None):
        """根据驱动板类型、插补模式和当前模式切换参数显示"""
        
        # 保存当前参数值到缓存
        self._save_current_parameters_to_cache()
        
        # 完全清除现有参数界面并重建
        self.clear_all_parameter_layouts()
        self.parameter_widgets.clear()
        
        # 重新创建步进大小参数（始终需要）
        self.create_step_size_param()
        
        # 根据当前模式设置步进大小的单位
        current_tab = self.mode_tab_widget.currentWidget()
        if current_tab == self.joint_mode_tab or (hasattr(self, 'current_mode') and self.current_mode == "joint"):
            # 关节模式：单位为度
            self.step_size_spinbox.setRange(1.0, 360.0)
            self.step_size_spinbox.setSuffix("°")
            if hasattr(self, 'step_range_label') and self.step_range_label is not None:
                self.step_range_label.setText("(1.0-360.0)")
        else:
            # 基座模式、工具模式和示教编程模式：单位为mm
            self.step_size_spinbox.setRange(0.1, 360.0)
            self.step_size_spinbox.setSuffix(" mm")
            if hasattr(self, 'step_range_label') and self.step_range_label is not None:
                self.step_range_label.setText("(0.1-360.0)")
        
        # 根据板卡类型和插补模式创建相应参数
        if board_type.upper() == 'X':
            # X板：显示梯形曲线参数
            self.create_x_board_params()
        elif board_type.upper() == 'Y':
            # Y板：根据当前模式和插补类型显示参数
            if current_mode == "joint":
                # 关节模式：无论什么插补类型都统一使用梯形曲线参数
                self.create_x_board_params()
            elif interpolation_type == "cartesian":
                # 非关节模式的笛卡尔插补：显示笛卡尔参数
                self.create_cartesian_params()
            elif interpolation_type == "joint":
                # 非关节模式的关节插补：显示关节空间参数
                self.create_joint_space_params()
            elif interpolation_type == "point_to_point":
                # 非关节模式的点到点运动：显示梯形曲线参数
                self.create_x_board_params()
            else:
                # 默认显示笛卡尔参数
                self.create_cartesian_params()
        
        # 更新当前板卡类型
        self.current_board_type = board_type.upper()
        
        # 从缓存恢复参数值
        self._restore_parameters_from_cache(board_type, interpolation_type, current_mode)
        
        # 更新示教点表格表头
        self.update_table_headers()
        
        # 强制刷新界面
        self.dynamic_params_widget.update()
        self.dynamic_params_widget.repaint()
        QApplication.processEvents()
    
    def _save_current_parameters_to_cache(self):
        """保存当前参数值到缓存"""
        try:
            # 构建缓存键
            cache_key = f"{self.current_board_type}_{self.interpolation_type}_{self.current_mode}"
            
            # 收集当前参数值
            params = {}
            
            # 步进大小参数（所有模式都有）
            if hasattr(self, 'step_size_spinbox') and self.step_size_spinbox is not None:
                try:
                    params['step_size'] = self.step_size_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            
            # X板参数（梯形曲线）
            if hasattr(self, 'max_speed_spinbox') and self.max_speed_spinbox is not None:
                try:
                    params['max_speed'] = self.max_speed_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'acceleration_spinbox') and self.acceleration_spinbox is not None:
                try:
                    params['acceleration'] = self.acceleration_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'deceleration_spinbox') and self.deceleration_spinbox is not None:
                try:
                    params['deceleration'] = self.deceleration_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 笛卡尔空间参数
            if hasattr(self, 'cartesian_linear_vel_spinbox') and self.cartesian_linear_vel_spinbox is not None:
                try:
                    params['cartesian_linear_velocity'] = self.cartesian_linear_vel_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'cartesian_angular_vel_spinbox') and self.cartesian_angular_vel_spinbox is not None:
                try:
                    params['cartesian_angular_velocity'] = self.cartesian_angular_vel_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'cartesian_linear_acc_spinbox') and self.cartesian_linear_acc_spinbox is not None:
                try:
                    params['cartesian_linear_acceleration'] = self.cartesian_linear_acc_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'cartesian_angular_acc_spinbox') and self.cartesian_angular_acc_spinbox is not None:
                try:
                    params['cartesian_angular_acceleration'] = self.cartesian_angular_acc_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            
            # Y板关节空间参数
            if hasattr(self, 'joint_max_vel_spinbox') and self.joint_max_vel_spinbox is not None:
                try:
                    params['joint_max_velocity'] = self.joint_max_vel_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            if hasattr(self, 'joint_max_acc_spinbox') and self.joint_max_acc_spinbox is not None:
                try:
                    params['joint_max_acceleration'] = self.joint_max_acc_spinbox.value()
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 保存到缓存
            if params:
                self.parameter_cache[cache_key] = params
                
        except Exception as e:
            print(f"⚠️ 保存参数到缓存失败: {e}")
    
    def _restore_parameters_from_cache(self, board_type, interpolation_type, current_mode):
        """从缓存恢复参数值"""
        try:
            # 构建当前缓存键
            current_cache_key = f"{board_type.upper()}_{interpolation_type}_{current_mode}"
            
            # 尝试多个缓存键来查找参数值（优先级递减）
            possible_keys = [
                current_cache_key,  # 完全匹配
                f"{board_type.upper()}_{interpolation_type}_joint",  # 同板同插补的关节模式
                f"{board_type.upper()}_{interpolation_type}_base",   # 同板同插补的基座模式
                f"{board_type.upper()}_{interpolation_type}_tool",   # 同板同插补的工具模式
                f"{board_type.upper()}_joint_{current_mode}",        # 同板关节插补
                f"{board_type.upper()}_cartesian_{current_mode}",    # 同板笛卡尔插补
            ]
            
            # 收集所有相关缓存中的参数值
            all_cached_params = {}
            for key in possible_keys:
                if key in self.parameter_cache:
                    cached_params = self.parameter_cache[key]
                    for param_name, param_value in cached_params.items():
                        if param_name not in all_cached_params and param_value > 0:
                            all_cached_params[param_name] = param_value
            
            if not all_cached_params:
                return
            
            
            # 恢复步进大小参数
            if 'step_size' in all_cached_params and hasattr(self, 'step_size_spinbox') and self.step_size_spinbox is not None:
                try:
                    self.step_size_spinbox.setValue(all_cached_params['step_size'])
                    self.step_size = all_cached_params['step_size']
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 恢复梯形曲线参数（X板参数）
            if 'max_speed' in all_cached_params and hasattr(self, 'max_speed_spinbox') and self.max_speed_spinbox is not None:
                try:
                    self.max_speed_spinbox.setValue(all_cached_params['max_speed'])
                    self.speed = all_cached_params['max_speed']
                except RuntimeError:
                    pass  # 控件已被删除
            if 'acceleration' in all_cached_params and hasattr(self, 'acceleration_spinbox') and self.acceleration_spinbox is not None:
                try:
                    self.acceleration_spinbox.setValue(all_cached_params['acceleration'])
                    self.acceleration = all_cached_params['acceleration']
                except RuntimeError:
                    pass  # 控件已被删除
            if 'deceleration' in all_cached_params and hasattr(self, 'deceleration_spinbox') and self.deceleration_spinbox is not None:
                try:
                    self.deceleration_spinbox.setValue(all_cached_params['deceleration'])
                    self.deceleration = all_cached_params['deceleration']
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 恢复笛卡尔空间参数
            if 'cartesian_linear_velocity' in all_cached_params and hasattr(self, 'cartesian_linear_vel_spinbox') and self.cartesian_linear_vel_spinbox is not None:
                try:
                    self.cartesian_linear_vel_spinbox.setValue(all_cached_params['cartesian_linear_velocity'])
                    self.cartesian_linear_velocity = all_cached_params['cartesian_linear_velocity']
                except RuntimeError:
                    pass  # 控件已被删除
            if 'cartesian_angular_velocity' in all_cached_params and hasattr(self, 'cartesian_angular_vel_spinbox') and self.cartesian_angular_vel_spinbox is not None:
                try:
                    self.cartesian_angular_vel_spinbox.setValue(all_cached_params['cartesian_angular_velocity'])
                    self.cartesian_angular_velocity = all_cached_params['cartesian_angular_velocity']
                except RuntimeError:
                    pass  # 控件已被删除
            if 'cartesian_linear_acceleration' in all_cached_params and hasattr(self, 'cartesian_linear_acc_spinbox') and self.cartesian_linear_acc_spinbox is not None:
                try:
                    self.cartesian_linear_acc_spinbox.setValue(all_cached_params['cartesian_linear_acceleration'])
                    self.cartesian_linear_acceleration = all_cached_params['cartesian_linear_acceleration']
                except RuntimeError:
                    pass  # 控件已被删除
            if 'cartesian_angular_acceleration' in all_cached_params and hasattr(self, 'cartesian_angular_acc_spinbox') and self.cartesian_angular_acc_spinbox is not None:
                try:
                    self.cartesian_angular_acc_spinbox.setValue(all_cached_params['cartesian_angular_acceleration'])
                    self.cartesian_angular_acceleration = all_cached_params['cartesian_angular_acceleration']
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 恢复关节空间参数
            if 'joint_max_velocity' in all_cached_params and hasattr(self, 'joint_max_vel_spinbox') and self.joint_max_vel_spinbox is not None:
                try:
                    self.joint_max_vel_spinbox.setValue(all_cached_params['joint_max_velocity'])
                    # 更新所有关节速度（简化版）
                    self.joint_max_velocities = [all_cached_params['joint_max_velocity']] * 6
                except RuntimeError:
                    pass  # 控件已被删除
            if 'joint_max_acceleration' in all_cached_params and hasattr(self, 'joint_max_acc_spinbox') and self.joint_max_acc_spinbox is not None:
                try:
                    self.joint_max_acc_spinbox.setValue(all_cached_params['joint_max_acceleration'])
                    # 更新所有关节加速度（简化版）
                    self.joint_max_accelerations = [all_cached_params['joint_max_acceleration']] * 6
                except RuntimeError:
                    pass  # 控件已被删除
            
            # 更新按钮文字
            self.update_button_texts()
                
        except Exception as e:
            print(f"⚠️ 从缓存恢复参数失败: {e}")
    
    def _get_current_interpolation_params(self):
        """获取当前插补方式的参数"""
        # 关节模式下：无论什么插补类型都使用点到点（梯形曲线）参数
        if self.current_mode == "joint":
            return {
                'type': 'point_to_point',
                'max_speed': self.speed,
                'acceleration': self.acceleration,
                'deceleration': self.deceleration
            }
        elif self.interpolation_type == "cartesian":
            # 笛卡尔空间插补参数
            return {
                'type': 'cartesian',
                'linear_velocity': self.cartesian_linear_velocity,
                'angular_velocity': self.cartesian_angular_velocity, 
                'linear_acceleration': self.cartesian_linear_acceleration,
                'angular_acceleration': 60.0  # 固定的角加速度，可以后续添加界面控制
            }
        elif self.interpolation_type == "joint":
            if self.current_board_type == "Y":
                # Y板关节空间插补参数
                return {
                    'type': 'joint_space',
                    'max_velocities': self.joint_max_velocities.copy(),
                    'max_accelerations': self.joint_max_accelerations.copy()
                }
            else:
                # X板点到点（梯形曲线）参数
                return {
                    'type': 'point_to_point',
                    'max_speed': self.speed,
                    'acceleration': self.acceleration,
                    'deceleration': self.deceleration
                }
        elif self.interpolation_type == "point_to_point":
            # 点到点运动：使用梯形曲线参数
            return {
                'type': 'point_to_point',
                'max_speed': self.speed,
                'acceleration': self.acceleration,
                'deceleration': self.deceleration
            }
        else:
            # 默认点到点（梯形曲线）参数
            return {
                'type': 'point_to_point',
                'max_speed': self.speed,
                'acceleration': self.acceleration,
                'deceleration': self.deceleration
            }
    
    def _get_current_mode_parameters(self):
        """只获取当前模式和插补类型相关的参数"""
        params = {}
        
        # 关节模式：统一使用梯形曲线参数
        if self.current_mode == "joint":
            max_speed_widget = getattr(self, 'max_speed_spinbox', None)
            acceleration_widget = getattr(self, 'acceleration_spinbox', None)
            deceleration_widget = getattr(self, 'deceleration_spinbox', None)
            
            params['max_speed'] = (
                max_speed_widget.value() if max_speed_widget else self.speed
            )
            params['acceleration'] = (
                acceleration_widget.value() if acceleration_widget else self.acceleration
            )
            params['deceleration'] = (
                deceleration_widget.value() if deceleration_widget else self.deceleration
            )
        
        # 基座模式和工具模式：根据插补类型决定参数
        elif self.current_mode in ["base", "tool"]:
            if self.interpolation_type == "cartesian":
                # 笛卡尔空间参数
                linear_vel_widget = getattr(self, 'cartesian_linear_vel_spinbox', None)
                angular_vel_widget = getattr(self, 'cartesian_angular_vel_spinbox', None)
                linear_acc_widget = getattr(self, 'cartesian_linear_acc_spinbox', None)
                angular_acc_widget = getattr(self, 'cartesian_angular_acc_spinbox', None)
                
                params['cartesian_linear_velocity'] = (
                    linear_vel_widget.value() if linear_vel_widget else 
                    getattr(self, 'cartesian_linear_velocity', 50.0)
                )
                params['cartesian_angular_velocity'] = (
                    angular_vel_widget.value() if angular_vel_widget else 
                    getattr(self, 'cartesian_angular_velocity', 30.0)
                )
                params['cartesian_linear_acceleration'] = (
                    linear_acc_widget.value() if linear_acc_widget else 
                    getattr(self, 'cartesian_linear_acceleration', 100.0)
                )
                params['cartesian_angular_acceleration'] = (
                    angular_acc_widget.value() if angular_acc_widget else 
                    getattr(self, 'cartesian_angular_acceleration', 60.0)
                )
            
            elif self.interpolation_type == "joint":
                # 关节空间参数
                joint_vel_widget = getattr(self, 'joint_max_vel_spinbox', None)
                joint_acc_widget = getattr(self, 'joint_max_acc_spinbox', None)
                
                joint_vel_value = joint_vel_widget.value() if joint_vel_widget else 30.0
                joint_acc_value = joint_acc_widget.value() if joint_acc_widget else 60.0
                
                params['joint_max_velocity'] = joint_vel_value
                params['joint_max_acceleration'] = joint_acc_value
                
                print(f"💾 保存关节插补参数: 速度 {joint_vel_value}°/s, 加速度 {joint_acc_value}°/s²")
                params['joint_max_velocities'] = getattr(self, 'joint_max_velocities', [30.0] * 6)
                params['joint_max_accelerations'] = getattr(self, 'joint_max_accelerations', [60.0] * 6)
        
        return params
    
    def _get_interpolation_param_display(self, interpolation_params):
        """获取插补参数的显示字符串"""
        param_type = interpolation_params.get('type', 'point_to_point')
        
        if param_type == 'cartesian':
            return (f"线速={interpolation_params['linear_velocity']:.1f}mm/s, "
                   f"角速={interpolation_params['angular_velocity']:.1f}°/s, "
                   f"线加速={interpolation_params['linear_acceleration']:.1f}mm/s²")
        elif param_type == 'joint_space':
            max_vel = max(interpolation_params['max_velocities'])
            max_acc = max(interpolation_params['max_accelerations'])
            return f"关节速度={max_vel:.1f}°/s, 关节加速度={max_acc:.1f}°/s²"
        elif param_type == 'point_to_point':
            return (f"速度={interpolation_params['max_speed']}RPM, "
                   f"加速度={interpolation_params['acceleration']}RPM/s, "
                   f"减速度={interpolation_params['deceleration']}RPM/s")
        else:  # trapezoid (兼容旧版本)
            return (f"速度={interpolation_params['max_speed']}RPM, "
                   f"加速度={interpolation_params['acceleration']}RPM/s, "
                   f"减速度={interpolation_params['deceleration']}RPM/s")
    
    def update_table_headers(self):
        """根据当前插补方式更新示教点表格表头"""
        base_headers = ["序号", "X(mm)", "Y(mm)", "Z(mm)", "Roll(°)", "Pitch(°)", "Yaw(°)"]
        
        if self.interpolation_type == "cartesian":
            # 笛卡尔空间插补表头
            param_headers = ["线速/最大速度(mm)", "角速/加速度(°)", "线加速/减速度(mm)", "角加速(°)"]
        elif self.interpolation_type == "joint" and self.current_board_type == "Y":
            # Y板关节空间插补表头
            param_headers = ["关节速度(°/s)", "关节加速(°/s²)", "--", "--"]
        elif self.interpolation_type == "point_to_point":
            # 点到点运动表头
            param_headers = ["速度(RPM)", "加速度", "减速度", "--"]
        else:
            # 默认梯形曲线表头
            param_headers = ["速度(RPM)", "加速度", "减速度", "--"]
        
        headers = base_headers + param_headers + ["模式"]
        
        if hasattr(self, 'teaching_points_table'):
            self.teaching_points_table.setHorizontalHeaderLabels(headers)
    
    def update_save_button_state(self):
        """根据驱动板类型和插补类型更新保存示教点按钮状态"""
        if hasattr(self, 'save_teaching_point_btn'):
            # 判断当前配置是否可以保存示教点
            can_save = False
            tooltip = ""
            
            if self.current_board_type == "X":
                # X板：关节插补使用梯形曲线参数，可以保存
                if self.interpolation_type == "joint":
                    can_save = True
                    tooltip = "保存当前位置和梯形曲线参数为示教点"
                else:
                    can_save = False
                    tooltip = "X板只支持关节空间插补模式"
            elif self.current_board_type == "Y":
                # Y板：笛卡尔插补、关节插补、点到点都可以保存
                if self.interpolation_type == "cartesian":
                    can_save = True
                    tooltip = "保存当前位置和笛卡尔插补参数为示教点"
                elif self.interpolation_type == "joint":
                    can_save = True
                    tooltip = "保存当前位置和关节空间插补参数为示教点"
                elif self.interpolation_type == "point_to_point":
                    can_save = True
                    tooltip = "保存当前位置和点到点参数为示教点"
                else:
                    can_save = False
                    tooltip = "未知插补类型"
            else:
                can_save = False
                tooltip = "未检测到驱动板类型"
            
            self.save_teaching_point_btn.setEnabled(can_save)
            self.save_teaching_point_btn.setToolTip(tooltip)
    
    def create_joint_mode_buttons(self, parent_layout):
        """创建关节模式控制按钮"""
        # 创建关节控制组
        joint_control_group = QGroupBox("关节控制")
        layout = QGridLayout(joint_control_group)
        
        # 创建6个关节的控制按钮
        joint_names = ["J1 (基座)", "J2 (肩部)", "J3 (肘部)", "J4 (腕部1)", "J5 (腕部2)", "J6 (腕部3)"]
        
        for i, joint_name in enumerate(joint_names):
            # 关节标签
            label = QLabel(joint_name)
            label.setAlignment(Qt.AlignCenter)
            layout.addWidget(label, i, 0)
            
            # 负方向按钮
            neg_btn = QPushButton(f"← -{self.step_size}°")
            neg_btn.setProperty("class", "warning")
            neg_btn.clicked.connect(lambda checked, joint=i: self.move_joint(joint, -self.step_size))
            layout.addWidget(neg_btn, i, 1)
            
            # 当前角度显示
            angle_label = QLabel("0.0°")
            angle_label.setAlignment(Qt.AlignCenter)
            angle_label.setMinimumWidth(80)
            angle_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
            layout.addWidget(angle_label, i, 2)
            setattr(self, f'joint_{i+1}_angle_label', angle_label)
            
            # 正方向按钮
            pos_btn = QPushButton(f"→ +{self.step_size}°")
            pos_btn.setProperty("class", "success")
            pos_btn.clicked.connect(lambda checked, joint=i: self.move_joint(joint, self.step_size))
            layout.addWidget(pos_btn, i, 3)
        
        # 保存引用以便后续访问
        self.joint_control_group = joint_control_group
        parent_layout.addWidget(joint_control_group)
    
    def create_base_mode_buttons(self, parent_layout):
        """创建基座模式控制按钮"""
        base_control_group = QGroupBox("基座坐标系控制")
        layout = QGridLayout(base_control_group)
        
        # 平移控制
        translation_group = QGroupBox("平移控制")
        trans_layout = QGridLayout(translation_group)
        
        # X轴控制
        trans_layout.addWidget(QLabel("X轴:"), 0, 0)
        x_neg_btn = QPushButton(f"← -{self.step_size}mm")
        x_neg_btn.setProperty("class", "warning")
        x_neg_btn.clicked.connect(lambda: self.move_base_translation('x', -self.step_size))
        trans_layout.addWidget(x_neg_btn, 0, 1)
        
        self.base_x_label = QLabel("0.0mm")
        self.base_x_label.setAlignment(Qt.AlignCenter)
        self.base_x_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        trans_layout.addWidget(self.base_x_label, 0, 2)
        
        x_pos_btn = QPushButton(f"→ +{self.step_size}mm")
        x_pos_btn.setProperty("class", "success")
        x_pos_btn.clicked.connect(lambda: self.move_base_translation('x', self.step_size))
        trans_layout.addWidget(x_pos_btn, 0, 3)
        
        # Y轴控制
        trans_layout.addWidget(QLabel("Y轴:"), 1, 0)
        y_neg_btn = QPushButton(f"← -{self.step_size}mm")
        y_neg_btn.setProperty("class", "warning")
        y_neg_btn.clicked.connect(lambda: self.move_base_translation('y', -self.step_size))
        trans_layout.addWidget(y_neg_btn, 1, 1)
        
        self.base_y_label = QLabel("0.0mm")
        self.base_y_label.setAlignment(Qt.AlignCenter)
        self.base_y_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        trans_layout.addWidget(self.base_y_label, 1, 2)
        
        y_pos_btn = QPushButton(f"→ +{self.step_size}mm")
        y_pos_btn.setProperty("class", "success")
        y_pos_btn.clicked.connect(lambda: self.move_base_translation('y', self.step_size))
        trans_layout.addWidget(y_pos_btn, 1, 3)
        
        # Z轴控制
        trans_layout.addWidget(QLabel("Z轴:"), 2, 0)
        z_neg_btn = QPushButton(f"↓ -{self.step_size}mm")
        z_neg_btn.setProperty("class", "warning")
        z_neg_btn.clicked.connect(lambda: self.move_base_translation('z', -self.step_size))
        trans_layout.addWidget(z_neg_btn, 2, 1)
        
        self.base_z_label = QLabel("0.0mm")
        self.base_z_label.setAlignment(Qt.AlignCenter)
        self.base_z_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        trans_layout.addWidget(self.base_z_label, 2, 2)
        
        z_pos_btn = QPushButton(f"↑ +{self.step_size}mm")
        z_pos_btn.setProperty("class", "success")
        z_pos_btn.clicked.connect(lambda: self.move_base_translation('z', self.step_size))
        trans_layout.addWidget(z_pos_btn, 2, 3)
        
        layout.addWidget(translation_group, 0, 0)
        
        # 旋转控制
        rotation_group = QGroupBox("旋转控制")
        rot_layout = QGridLayout(rotation_group)
        
        # Roll控制
        rot_layout.addWidget(QLabel("Roll(X):"), 0, 0)
        roll_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        roll_neg_btn.setProperty("class", "warning")
        roll_neg_btn.clicked.connect(lambda: self.move_base_rotation('roll', -self.step_size))
        rot_layout.addWidget(roll_neg_btn, 0, 1)
        
        self.base_roll_label = QLabel("0.0°")
        self.base_roll_label.setAlignment(Qt.AlignCenter)
        self.base_roll_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        rot_layout.addWidget(self.base_roll_label, 0, 2)
        
        roll_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        roll_pos_btn.setProperty("class", "success")
        roll_pos_btn.clicked.connect(lambda: self.move_base_rotation('roll', self.step_size))
        rot_layout.addWidget(roll_pos_btn, 0, 3)
        
        # Pitch控制
        rot_layout.addWidget(QLabel("Pitch(Y):"), 1, 0)
        pitch_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        pitch_neg_btn.setProperty("class", "warning")
        pitch_neg_btn.clicked.connect(lambda: self.move_base_rotation('pitch', -self.step_size))
        rot_layout.addWidget(pitch_neg_btn, 1, 1)
        
        self.base_pitch_label = QLabel("0.0°")
        self.base_pitch_label.setAlignment(Qt.AlignCenter)
        self.base_pitch_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        rot_layout.addWidget(self.base_pitch_label, 1, 2)
        
        pitch_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        pitch_pos_btn.setProperty("class", "success")
        pitch_pos_btn.clicked.connect(lambda: self.move_base_rotation('pitch', self.step_size))
        rot_layout.addWidget(pitch_pos_btn, 1, 3)
        
        # Yaw控制
        rot_layout.addWidget(QLabel("Yaw(Z):"), 2, 0)
        yaw_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        yaw_neg_btn.setProperty("class", "warning")
        yaw_neg_btn.clicked.connect(lambda: self.move_base_rotation('yaw', -self.step_size))
        rot_layout.addWidget(yaw_neg_btn, 2, 1)
        
        self.base_yaw_label = QLabel("0.0°")
        self.base_yaw_label.setAlignment(Qt.AlignCenter)
        self.base_yaw_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        rot_layout.addWidget(self.base_yaw_label, 2, 2)
        
        yaw_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        yaw_pos_btn.setProperty("class", "success")
        yaw_pos_btn.clicked.connect(lambda: self.move_base_rotation('yaw', self.step_size))
        rot_layout.addWidget(yaw_pos_btn, 2, 3)
        
        layout.addWidget(rotation_group, 0, 1)
        
        # 保存引用以便后续访问
        self.base_control_group = base_control_group
        parent_layout.addWidget(base_control_group)
    
    def create_tool_mode_buttons(self, parent_layout):
        """创建工具模式控制按钮"""
        tool_control_group = QGroupBox("工具坐标系控制 (相对于TCP)")
        layout = QGridLayout(tool_control_group)
        
        # TCP平移控制
        tcp_trans_group = QGroupBox("TCP平移控制")
        tcp_trans_layout = QGridLayout(tcp_trans_group)
        
        # TCP X轴控制
        tcp_trans_layout.addWidget(QLabel("TCP X:"), 0, 0)
        tcp_x_neg_btn = QPushButton(f"← -{self.step_size}mm")
        tcp_x_neg_btn.setProperty("class", "warning")
        tcp_x_neg_btn.clicked.connect(lambda: self.move_tool_translation('x', -self.step_size))
        tcp_trans_layout.addWidget(tcp_x_neg_btn, 0, 1)
        
        self.tcp_x_label = QLabel("0.0mm")
        self.tcp_x_label.setAlignment(Qt.AlignCenter)
        self.tcp_x_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_trans_layout.addWidget(self.tcp_x_label, 0, 2)
        
        tcp_x_pos_btn = QPushButton(f"→ +{self.step_size}mm")
        tcp_x_pos_btn.setProperty("class", "success")
        tcp_x_pos_btn.clicked.connect(lambda: self.move_tool_translation('x', self.step_size))
        tcp_trans_layout.addWidget(tcp_x_pos_btn, 0, 3)
        
        # TCP Y轴控制
        tcp_trans_layout.addWidget(QLabel("TCP Y:"), 1, 0)
        tcp_y_neg_btn = QPushButton(f"← -{self.step_size}mm")
        tcp_y_neg_btn.setProperty("class", "warning")
        tcp_y_neg_btn.clicked.connect(lambda: self.move_tool_translation('y', -self.step_size))
        tcp_trans_layout.addWidget(tcp_y_neg_btn, 1, 1)
        
        self.tcp_y_label = QLabel("0.0mm")
        self.tcp_y_label.setAlignment(Qt.AlignCenter)
        self.tcp_y_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_trans_layout.addWidget(self.tcp_y_label, 1, 2)
        
        tcp_y_pos_btn = QPushButton(f"→ +{self.step_size}mm")
        tcp_y_pos_btn.setProperty("class", "success")
        tcp_y_pos_btn.clicked.connect(lambda: self.move_tool_translation('y', self.step_size))
        tcp_trans_layout.addWidget(tcp_y_pos_btn, 1, 3)
        
        # TCP Z轴控制
        tcp_trans_layout.addWidget(QLabel("TCP Z:"), 2, 0)
        tcp_z_neg_btn = QPushButton(f"↓ -{self.step_size}mm")
        tcp_z_neg_btn.setProperty("class", "warning")
        tcp_z_neg_btn.clicked.connect(lambda: self.move_tool_translation('z', -self.step_size))
        tcp_trans_layout.addWidget(tcp_z_neg_btn, 2, 1)
        
        self.tcp_z_label = QLabel("0.0mm")
        self.tcp_z_label.setAlignment(Qt.AlignCenter)
        self.tcp_z_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_trans_layout.addWidget(self.tcp_z_label, 2, 2)
        
        tcp_z_pos_btn = QPushButton(f"↑ +{self.step_size}mm")
        tcp_z_pos_btn.setProperty("class", "success")
        tcp_z_pos_btn.clicked.connect(lambda: self.move_tool_translation('z', self.step_size))
        tcp_trans_layout.addWidget(tcp_z_pos_btn, 2, 3)
        
        layout.addWidget(tcp_trans_group, 0, 0)
        
        # TCP旋转控制
        tcp_rot_group = QGroupBox("TCP旋转控制")
        tcp_rot_layout = QGridLayout(tcp_rot_group)
        
        # TCP Roll控制
        tcp_rot_layout.addWidget(QLabel("TCP Roll(X):"), 0, 0)
        tcp_roll_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        tcp_roll_neg_btn.setProperty("class", "warning")
        tcp_roll_neg_btn.clicked.connect(lambda: self.move_tool_rotation('roll', -self.step_size))
        tcp_rot_layout.addWidget(tcp_roll_neg_btn, 0, 1)
        
        self.tcp_roll_label = QLabel("0.0°")
        self.tcp_roll_label.setAlignment(Qt.AlignCenter)
        self.tcp_roll_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_rot_layout.addWidget(self.tcp_roll_label, 0, 2)
        
        tcp_roll_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        tcp_roll_pos_btn.setProperty("class", "success")
        tcp_roll_pos_btn.clicked.connect(lambda: self.move_tool_rotation('roll', self.step_size))
        tcp_rot_layout.addWidget(tcp_roll_pos_btn, 0, 3)
        
        # TCP Pitch控制
        tcp_rot_layout.addWidget(QLabel("TCP Pitch(Y):"), 1, 0)
        tcp_pitch_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        tcp_pitch_neg_btn.setProperty("class", "warning")
        tcp_pitch_neg_btn.clicked.connect(lambda: self.move_tool_rotation('pitch', -self.step_size))
        tcp_rot_layout.addWidget(tcp_pitch_neg_btn, 1, 1)
        
        self.tcp_pitch_label = QLabel("0.0°")
        self.tcp_pitch_label.setAlignment(Qt.AlignCenter)
        self.tcp_pitch_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_rot_layout.addWidget(self.tcp_pitch_label, 1, 2)
        
        tcp_pitch_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        tcp_pitch_pos_btn.setProperty("class", "success")
        tcp_pitch_pos_btn.clicked.connect(lambda: self.move_tool_rotation('pitch', self.step_size))
        tcp_rot_layout.addWidget(tcp_pitch_pos_btn, 1, 3)
        
        # TCP Yaw控制
        tcp_rot_layout.addWidget(QLabel("TCP Yaw(Z):"), 2, 0)
        tcp_yaw_neg_btn = QPushButton(f"↺ -{self.step_size}°")
        tcp_yaw_neg_btn.setProperty("class", "warning")
        tcp_yaw_neg_btn.clicked.connect(lambda: self.move_tool_rotation('yaw', -self.step_size))
        tcp_rot_layout.addWidget(tcp_yaw_neg_btn, 2, 1)
        
        self.tcp_yaw_label = QLabel("0.0°")
        self.tcp_yaw_label.setAlignment(Qt.AlignCenter)
        self.tcp_yaw_label.setStyleSheet("background-color: #f8f9fa; border: 1px solid #dee2e6; border-radius: 4px; padding: 5px;")
        tcp_rot_layout.addWidget(self.tcp_yaw_label, 2, 2)
        
        tcp_yaw_pos_btn = QPushButton(f"↻ +{self.step_size}°")
        tcp_yaw_pos_btn.setProperty("class", "success")
        tcp_yaw_pos_btn.clicked.connect(lambda: self.move_tool_rotation('yaw', self.step_size))
        tcp_rot_layout.addWidget(tcp_yaw_pos_btn, 2, 3)
        
        layout.addWidget(tcp_rot_group, 0, 1)
        
        # 保存引用以便后续访问
        self.tool_control_group = tool_control_group
        parent_layout.addWidget(tool_control_group)
    
    def create_hand_eye_save_section(self, parent_layout):
        """创建手眼标定位置保存区域"""
        save_group = QGroupBox("📋 手眼标定位置保存")
        save_layout = QVBoxLayout(save_group)
        save_layout.setSpacing(8)
        
        # 说明文字
        info_label = QLabel("💡 将当前机械臂关节角度保存到手眼标定预设位置配置中")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f0f8ff; border-radius: 4px;")
        info_label.setWordWrap(True)
        save_layout.addWidget(info_label)
        
        # 位置名称输入和保存按钮
        input_layout = QHBoxLayout()
        
        input_layout.addWidget(QLabel("位置名称:"))
        self.pose_name_input = QLineEdit()
        self.pose_name_input.setPlaceholderText("输入位置名称，如: pose_new_1")
        self.pose_name_input.setMaximumWidth(200)
        input_layout.addWidget(self.pose_name_input)
        
        self.save_pose_btn = QPushButton("💾 保存当前位置")
        self.save_pose_btn.setStyleSheet("""
            QPushButton {
                background-color: #2196F3;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                min-height: 20px;
            }
            QPushButton:hover {
                background-color: #1976D2;
            }
            QPushButton:pressed {
                background-color: #0D47A1;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.save_pose_btn.setToolTip("将当前关节角度保存到手眼标定配置文件")
        self.save_pose_btn.clicked.connect(self.save_current_pose_to_hand_eye_config)
        input_layout.addWidget(self.save_pose_btn)
        
        # 新增：清空已保存的位置
        self.clear_poses_btn = QPushButton("🧹 清空已保存的位置")
        self.clear_poses_btn.setStyleSheet("QPushButton { background-color: #ff5722; color: white; border: none; border-radius: 6px; font-weight: bold; padding: 8px 12px; } QPushButton:hover { background-color: #e64a19; } QPushButton:pressed { background-color: #d84315; }")
        self.clear_poses_btn.setToolTip("清空手眼标定配置文件中的全部预设位置")
        self.clear_poses_btn.clicked.connect(self.clear_hand_eye_saved_positions)
        input_layout.addWidget(self.clear_poses_btn)
        
        input_layout.addStretch()
        save_layout.addLayout(input_layout)
        
        # 状态显示
        self.save_status_label = QLabel("准备保存位置...")
        self.save_status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
        save_layout.addWidget(self.save_status_label)
        
        parent_layout.addWidget(save_group)
    
    def clear_hand_eye_saved_positions(self):
        """清空手眼标定配置中的已保存位置"""
        try:
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(current_dir)),
                "config", "hand_eye_calibration_poses.yaml")
            
            # 先检查是否存在已保存的位置
            pose_count = 0
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        import yaml
                        data = yaml.safe_load(f) or {}
                        pose_count = data.get('pose_count', 0)
                except Exception:
                    pose_count = 0
            
            # 如果没有已保存的位置，直接提示
            if pose_count == 0:
                QMessageBox.information(self, "提示", "手眼标定配置中没有已保存的位置！")
                self.save_status_label.setText("💡 没有需要清空的位置")
                self.save_status_label.setStyleSheet("color: #666; font-size: 10px; padding: 2px;")
                return
            
            # 弹出确认对话框
            reply = QMessageBox.question(
                self, 
                "确认清空", 
                f"确定要清空手眼标定配置中的所有已保存位置吗？\n\n"
                f"当前共有 {pose_count} 个位置，此操作不可撤销！",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No  # 默认选择"否"，更安全
            )
            
            # 如果用户选择"否"，则取消操作
            if reply != QMessageBox.Yes:
                self.save_status_label.setText("❌ 清空操作已取消")
                self.save_status_label.setStyleSheet("color: orange; font-size: 10px; padding: 2px;")
                print("🚫 用户取消了清空手眼标定预设位置操作")
                return
            
            # 执行清空操作
            data = {}
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        import yaml
                        data = yaml.safe_load(f) or {}
                except Exception:
                    data = {}
            
            # 重置内容
            data.setdefault('description', '手眼标定预设位置配置')
            data.setdefault('notes', '关节角度单位为度制，范围建议在±120度内')
            data['poses'] = []
            data['pose_count'] = 0
            
            # 写回文件
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                import yaml
                yaml.dump(data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            # 更新状态显示
            self.save_status_label.setText(f"✅ 已清空 {pose_count} 个预设位置")
            self.save_status_label.setStyleSheet("color: green; font-size: 10px; padding: 2px;")
            
            # 控制台输出
            print(f"🧹 已清空手眼标定预设位置: {config_path}")
            print(f"   清空了 {pose_count} 个位置")
            
            # 成功提示
            QMessageBox.information(
                self, 
                "清空成功", 
                f"已成功清空手眼标定配置中的所有位置！\n\n"
                f"清空位置数: {pose_count}\n"
                f"配置文件: {os.path.basename(config_path)}"
            )
            
        except Exception as e:
            error_msg = f"清空已保存位置失败: {str(e)}"
            print(f"❌ {error_msg}")
            self.save_status_label.setText(f"❌ 清空失败: {str(e)[:50]}...")
            self.save_status_label.setStyleSheet("color: red; font-size: 10px; padding: 2px;")
            QMessageBox.critical(self, "错误", f"{error_msg}\n\n请检查文件权限和路径。")
    
    def create_independent_status_display(self, parent_layout):
        """创建独立的状态显示区域（用于标签页内）"""
        group = QGroupBox("当前状态")
        group.setMinimumHeight(350)
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # 创建关节角度状态表格
        joint_label = QLabel("关节角度状态")
        joint_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        layout.addWidget(joint_label)
        
        status_table = QTableWidget()
        status_table.setRowCount(1)
        status_table.setColumnCount(6)
        status_table.setHorizontalHeaderLabels(["J1", "J2", "J3", "J4", "J5", "J6"])
        status_table.setVerticalHeaderLabels(["角度(°)"])
        
        # 设置表格属性
        status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        status_table.setSelectionMode(QTableWidget.NoSelection)
        status_table.setMaximumHeight(90)
        status_table.setMinimumHeight(90)
        
        # 初始化关节角度表格内容
        for col in range(6):
            status_table.setItem(0, col, QTableWidgetItem("0.0"))
            item = status_table.item(0, col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)
        
        # 调整行高和禁用滚动条
        status_table.resizeRowsToContents()
        status_table.setRowHeight(0, 35)
        status_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        status_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(status_table)
        
        # 创建末端位姿表格
        pose_label = QLabel("末端位姿状态")
        pose_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        layout.addWidget(pose_label)
        
        pose_table = QTableWidget()
        pose_table.setRowCount(2)
        pose_table.setColumnCount(4)
        pose_table.setHorizontalHeaderLabels(["X/Roll", "Y/Pitch", "Z/Yaw", "单位"])
        pose_table.setVerticalHeaderLabels(["位置", "姿态"])
        
        # 设置末端位姿表格属性
        pose_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        pose_table.setEditTriggers(QTableWidget.NoEditTriggers)
        pose_table.setSelectionMode(QTableWidget.NoSelection)
        pose_table.setMaximumHeight(120)
        pose_table.setMinimumHeight(120)
        
        # 初始化末端位姿表格内容
        # 第一行：位置
        pose_table.setItem(0, 0, QTableWidgetItem("--"))
        pose_table.setItem(0, 1, QTableWidgetItem("--"))
        pose_table.setItem(0, 2, QTableWidgetItem("--"))
        pose_table.setItem(0, 3, QTableWidgetItem("mm"))
        
        # 第二行：姿态
        pose_table.setItem(1, 0, QTableWidgetItem("--"))
        pose_table.setItem(1, 1, QTableWidgetItem("--"))
        pose_table.setItem(1, 2, QTableWidgetItem("--"))
        pose_table.setItem(1, 3, QTableWidgetItem("°"))
        
        # 设置文本居中对齐
        for row in range(2):
            for col in range(4):
                item = pose_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
        
        # 调整行高
        pose_table.resizeRowsToContents()
        for row in range(2):
            pose_table.setRowHeight(row, 35)
        
        # 禁用滚动条
        pose_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        pose_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(pose_table)
        
        # 添加说明文字
        info_label = QLabel("💡 提示: 关节角度为输出端角度，末端位姿通过正运动学实时计算")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        parent_layout.addWidget(group)
        
        # 保存所有状态表格的引用
        if not hasattr(self, 'all_status_tables'):
            self.all_status_tables = []
            self.all_pose_tables = []
        
        self.all_status_tables.append(status_table)
        self.all_pose_tables.append(pose_table)
    
    def create_status_display(self, parent_layout):
        """创建状态显示区域"""
        group = QGroupBox("当前状态")
        group.setMinimumHeight(350)  # 设置最小高度而不是最大高度，让内容充分显示
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # 创建关节角度状态表格
        joint_label = QLabel("关节角度状态")
        joint_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        layout.addWidget(joint_label)
        
        self.status_table = QTableWidget()
        self.status_table.setRowCount(1)
        self.status_table.setColumnCount(6)  # 减少到6列，去掉"类型"列
        self.status_table.setHorizontalHeaderLabels(["J1", "J2", "J3", "J4", "J5", "J6"])
        self.status_table.setVerticalHeaderLabels(["角度(°)"])
        
        # 设置表格属性
        self.status_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.status_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.status_table.setSelectionMode(QTableWidget.NoSelection)
        self.status_table.setMaximumHeight(90)  # 设置合适的高度
        self.status_table.setMinimumHeight(90)
        
        # 初始化关节角度表格内容（去掉类型列）
        for col in range(6):
            self.status_table.setItem(0, col, QTableWidgetItem("0.0"))
        
        # 设置文本居中对齐
        for col in range(6):  # 改为6列
            item = self.status_table.item(0, col)
            if item:
                item.setTextAlignment(Qt.AlignCenter)
        
        # 调整行高和禁用滚动条
        self.status_table.resizeRowsToContents()
        self.status_table.setRowHeight(0, 35)
        self.status_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.status_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        layout.addWidget(self.status_table)
        
        # 创建末端位姿表格
        pose_label = QLabel("末端位姿状态")
        pose_label.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        layout.addWidget(pose_label)
        
        self.pose_table = QTableWidget()
        self.pose_table.setRowCount(2)
        self.pose_table.setColumnCount(4)
        self.pose_table.setHorizontalHeaderLabels(["X/Roll", "Y/Pitch", "Z/Yaw", "单位"])
        self.pose_table.setVerticalHeaderLabels(["位置", "姿态"])
        
        # 设置末端位姿表格属性
        self.pose_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.pose_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.pose_table.setSelectionMode(QTableWidget.NoSelection)
        self.pose_table.setMaximumHeight(120)  # 设置合适的高度
        self.pose_table.setMinimumHeight(120)
        
        # 初始化末端位姿表格
        self.init_pose_table()
        layout.addWidget(self.pose_table)
        
        # 添加说明文字
        info_label = QLabel("💡 提示: 关节角度为输出端角度，末端位姿通过正运动学实时计算")
        info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px;")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        parent_layout.addWidget(group)
    
    def init_pose_table(self):
        """初始化末端位姿表格"""
        # 第一行：位置
        self.pose_table.setItem(0, 0, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 1, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 2, QTableWidgetItem("--"))
        self.pose_table.setItem(0, 3, QTableWidgetItem("mm"))
        
        # 第二行：姿态
        self.pose_table.setItem(1, 0, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 1, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 2, QTableWidgetItem("--"))
        self.pose_table.setItem(1, 3, QTableWidgetItem("°"))
        
        # 设置文本居中对齐
        for row in range(2):
            for col in range(4):
                item = self.pose_table.item(row, col)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
        
        # 调整行高以确保内容完全显示
        self.pose_table.resizeRowsToContents()
        # 设置固定行高，避免内容被截断
        for row in range(2):
            self.pose_table.setRowHeight(row, 35)
        
        # 禁用滚动条
        self.pose_table.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.pose_table.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    
    def update_end_effector_pose(self):
        """更新末端执行器位姿显示 - 基于输出端角度状态"""
        if not self.kinematics:
            # 显示未初始化状态
            if hasattr(self, 'all_pose_tables'):
                for pose_table in self.all_pose_tables:
                    try:
                        pose_table.setItem(0, 0, QTableWidgetItem("--"))
                        pose_table.setItem(0, 1, QTableWidgetItem("--"))
                        pose_table.setItem(0, 2, QTableWidgetItem("--"))
                        pose_table.setItem(1, 0, QTableWidgetItem("--"))
                        pose_table.setItem(1, 1, QTableWidgetItem("--"))
                        pose_table.setItem(1, 2, QTableWidgetItem("--"))
                    except Exception:
                        continue
            return
            
        try:
            # 直接使用输出端角度状态进行计算
            joint_angles = self.output_joint_angles.copy()
            
            # 使用运动学计算器计算末端位姿
            pose_info = self.kinematics.get_end_effector_pose(joint_angles)
            
            # 提取位置和姿态信息
            position = pose_info['position']  # [x, y, z] 单位：mm
            euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 单位：度（ZYX顺序）
            
            # 更新所有位姿表格内容 - XYZ顺序显示
            if hasattr(self, 'all_pose_tables'):
                for pose_table in self.all_pose_tables:
                    try:
                        # 位置行：X, Y, Z顺序
                        pose_table.setItem(0, 0, QTableWidgetItem(f"{position[0]:.2f}"))  # X位置
                        pose_table.setItem(0, 1, QTableWidgetItem(f"{position[1]:.2f}"))  # Y位置
                        pose_table.setItem(0, 2, QTableWidgetItem(f"{position[2]:.2f}"))  # Z位置
                        
                        # 姿态行：Roll, Pitch, Yaw顺序
                        pose_table.setItem(1, 0, QTableWidgetItem(f"{euler_angles[2]:.2f}"))  # Roll (绕X轴)
                        pose_table.setItem(1, 1, QTableWidgetItem(f"{euler_angles[1]:.2f}"))  # Pitch (绕Y轴)
                        pose_table.setItem(1, 2, QTableWidgetItem(f"{euler_angles[0]:.2f}"))  # Yaw (绕Z轴)
                        
                        # 设置文本居中对齐
                        for row in range(2):
                            for col in range(3):
                                item = pose_table.item(row, col)
                                if item:
                                    item.setTextAlignment(Qt.AlignCenter)
                    except Exception:
                        continue
            
            # 更新基座模式的位置显示标签
            if hasattr(self, 'base_x_label'):
                self.base_x_label.setText(f"{position[0]:.1f}mm")
            if hasattr(self, 'base_y_label'):
                self.base_y_label.setText(f"{position[1]:.1f}mm")
            if hasattr(self, 'base_z_label'):
                self.base_z_label.setText(f"{position[2]:.1f}mm")
            
            # 更新基座模式的姿态显示标签
            if hasattr(self, 'base_roll_label'):
                self.base_roll_label.setText(f"{euler_angles[2]:.1f}°")  # Roll
            if hasattr(self, 'base_pitch_label'):
                self.base_pitch_label.setText(f"{euler_angles[1]:.1f}°")  # Pitch
            if hasattr(self, 'base_yaw_label'):
                self.base_yaw_label.setText(f"{euler_angles[0]:.1f}°")  # Yaw
            
            # 更新工具模式的位置显示标签（如果存在）
            if hasattr(self, 'tcp_x_label'):
                self.tcp_x_label.setText(f"{position[0]:.1f}mm")
            if hasattr(self, 'tcp_y_label'):
                self.tcp_y_label.setText(f"{position[1]:.1f}mm")
            if hasattr(self, 'tcp_z_label'):
                self.tcp_z_label.setText(f"{position[2]:.1f}mm")
            
            # 更新工具模式的姿态显示标签（如果存在）
            if hasattr(self, 'tcp_roll_label'):
                self.tcp_roll_label.setText(f"{euler_angles[2]:.1f}°")  # Roll
            if hasattr(self, 'tcp_pitch_label'):
                self.tcp_pitch_label.setText(f"{euler_angles[1]:.1f}°")  # Pitch
            if hasattr(self, 'tcp_yaw_label'):
                self.tcp_yaw_label.setText(f"{euler_angles[0]:.1f}°")  # Yaw
            
        except Exception as e:
            # 显示错误状态
            if hasattr(self, 'all_pose_tables'):
                for pose_table in self.all_pose_tables:
                    try:
                        for row in range(2):
                            for col in range(3):
                                pose_table.setItem(row, col, QTableWidgetItem("错误"))
                    except Exception:
                        continue
            print(f"末端位姿计算失败: {e}")
    
    def update_joint_angle_display(self):
        """手动更新关节角度显示 - 只在运动后调用"""
        try:
            # 更新关节角度显示
            for i in range(6):
                motor_id_int = i + 1  # 电机ID从1开始，使用整数
                
                if motor_id_int in self.motors:
                    # 获取电机位置 - 使用正确的方法名
                    try:
                        motor_pos = self.motors[motor_id_int].read_parameters.get_position()
                    except AttributeError:
                        try:
                            motor_pos = self.motors[motor_id_int].get_position()
                        except AttributeError:
                            motor_pos = None
                    
                    if motor_pos is not None:
                        # 获取减速比和方向设置
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id_int)
                        direction = self.motor_config_manager.get_motor_direction(motor_id_int)
                        
                        # 将电机角度转换为输出端角度
                        output_angle = (motor_pos * direction) / reducer_ratio
                        self.current_joint_angles[i] = output_angle
                        
                        # 更新关节角度标签
                        if hasattr(self, f'joint_{i+1}_angle_label'):
                            getattr(self, f'joint_{i+1}_angle_label').setText(f"{output_angle:.1f}°")
                        
                        # 更新状态表格（显示输出端角度）
                        self.status_table.setItem(0, i, QTableWidgetItem(f"{output_angle:.1f}"))
                        
        except Exception as e:
            print(f"更新关节角度显示失败: {e}")
    
    def get_actual_angle(self, input_angle, motor_id=None):
        """根据减速比和方向设置计算实际发送给电机的角度"""
        # 获取对应电机的减速比和方向
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
        direction = self.motor_config_manager.get_motor_direction(motor_id)
        
        # 示教器中用户输入的总是输出端角度，需要乘以减速比得到电机端角度
        # 然后应用方向修正：正向=1，反向=-1
        motor_angle = input_angle * reducer_ratio * direction
        
        return motor_angle
    
    def update_joint_angle_labels(self):
        """更新关节角度标签显示 - 基于输出端角度状态"""
        try:
            for i in range(6):
                output_angle = self.output_joint_angles[i]
                
                # 更新关节角度标签
                if hasattr(self, f'joint_{i+1}_angle_label'):
                    getattr(self, f'joint_{i+1}_angle_label').setText(f"{output_angle:.1f}°")
                
                # 更新所有状态表格（显示输出端角度）
                if hasattr(self, 'all_status_tables'):
                    for status_table in self.all_status_tables:
                        try:
                            status_table.setItem(0, i, QTableWidgetItem(f"{output_angle:.1f}"))
                            item = status_table.item(0, i)
                            if item:
                                item.setTextAlignment(Qt.AlignCenter)
                        except Exception:
                            continue
                
                # 更新缓存
                self.current_joint_angles[i] = output_angle
                
        except Exception as e:
            print(f"更新关节角度标签失败: {e}")
    
    def sync_output_angles_from_motors(self):
        """从电机同步输出端角度状态 - 在电机连接时调用"""
        try:
            for i in range(6):
                motor_id = i + 1
                
                if motor_id in self.motors:
                    # 获取电机位置
                    try:
                        motor_pos = self.motors[motor_id].read_parameters.get_position()
                    except AttributeError:
                        try:
                            motor_pos = self.motors[motor_id].get_position()
                        except AttributeError:
                            motor_pos = None
                    
                    if motor_pos is not None:
                        # 获取减速比和方向设置
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        
                        # 将电机角度转换为输出端角度
                        output_angle = motor_pos / (reducer_ratio * direction)
                        
                        # 规范化输出端角度
                        output_angle = self.kinematics.normalize_angle(output_angle)
                        
                        self.output_joint_angles[i] = output_angle
                    else:
                        self.output_joint_angles[i] = 0.0
                else:
                    self.output_joint_angles[i] = 0.0
            
            # 同步后更新显示
            self.update_joint_angle_labels()
            self.update_end_effector_pose()
            
            
        except Exception as e:
            print(f"同步输出端角度状态失败: {e}")
    
    def go_home_position(self):
        """回零位功能 - 将所有关节回到零位"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "未连接电机，无法执行回零！\n\n请确保电机连接正常。")
            return
        
        # 确认对话框
        reply = QMessageBox.question(self, "确认回零", 
                                   "确定要将所有关节回到零位吗？\n\n这将使机械臂移动到初始姿态。",
                                   QMessageBox.Yes | QMessageBox.No,
                                   QMessageBox.No)
        
        if reply != QMessageBox.Yes:
            return
        
        # Y板：使用回到坐标原点（homing_mode=4），逐台触发回零
        if self._is_y_board():
            try:
                success_count = 0
                total_motors = len(self.motors)
                for motor_id, motor in self.motors.items():
                    try:
                        motor.control_actions.trigger_homing(homing_mode=4, multi_sync=False)
                        success_count += 1
                    except Exception as motor_error:
                        print(f"电机 {motor_id} 回零触发失败: {motor_error}")
                        continue
                if success_count > 0:
                    QMessageBox.information(self, "回零", f"已触发回零：成功 {success_count}/{total_motors} 台")
                else:
                    QMessageBox.warning(self, "失败", "未能成功触发任何电机回零")
                
                # UI: 先将角度显示置为零并在短延时后同步真实位置
                self.output_joint_angles = [0.0] * 6
                self.update_joint_angle_labels()
                self.update_end_effector_pose()
                QTimer.singleShot(1500, self.sync_output_angles_from_motors)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"回零操作失败: {str(e)}\n\n请检查电机连接和通信状态。")
            return
        
        # X板：原逻辑——设置各关节0°并使用同步标志 + 广播同步
        try:
            success_count = 0
            total_motors = len(self.motors)
            
            # 设置所有关节的目标角度为0
            target_angles = [0.0] * 6
            
            # 使用同步运动模式
            for i in range(6):
                motor_id = i + 1
                
                if motor_id in self.motors:
                    try:
                        motor = self.motors[motor_id]
                        
                        # 计算实际电机角度（考虑减速比和方向）
                        actual_angle = self.get_actual_angle(0.0, motor_id)
                        
                        # 发送同步位置命令
                        motor.control_actions.move_to_position_trapezoid(
                            position=actual_angle,
                            max_speed=self.speed,
                            acceleration=self.acceleration,
                            deceleration=self.deceleration,
                            is_absolute=True,
                            multi_sync=True  # 使用同步模式
                        )
                        success_count += 1
                        
                    except Exception as motor_error:
                        print(f"电机 {motor_id} 回零设置失败: {motor_error}")
                        continue
            
            if success_count == 0:
                QMessageBox.warning(self, "失败", "没有电机成功设置回零参数")
                return
            
            # 发送同步运动命令
            if self.motors:
                first_motor = list(self.motors.values())[0]
                try:
                    # 创建广播控制器（ID=0）
                    interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                    broadcast_motor = first_motor.__class__(
                        motor_id=0,
                        interface_type=first_motor.interface_type,
                        shared_interface=True,
                        **interface_kwargs
                    )
                    broadcast_motor.can_interface = first_motor.can_interface
                    broadcast_motor.control_actions.sync_motion()
                    
                except Exception:
                    print("同步运动命令发送失败，但单个电机命令已发送")
            
            # 更新输出端角度状态
            self.output_joint_angles = [0.0] * 6
            
            # 更新界面显示
            self.update_joint_angle_labels()
            self.update_end_effector_pose()
            
            # 延时同步一次真实角度，确保完成后状态一致
            QTimer.singleShot(1500, self.sync_output_angles_from_motors)
            
            print(f"✅ 回零命令已发送给 {success_count}/{total_motors} 个电机")
            print(f"🎯 目标位置: 所有关节 0.0°（规范化角度）")
            print(f"⚙️ 运动参数: 速度={self.speed}RPM, 加速度={self.acceleration}RPM/s, 减速度={self.deceleration}RPM/s")
            
            QMessageBox.information(self, "成功", f"回零命令已发送！\n\n成功设置 {success_count}/{total_motors} 个电机回零")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"回零操作失败: {str(e)}\n\n请检查电机连接和通信状态。")
    
    def refresh_position_and_pose(self):
        """刷新关节角度和末端位姿显示"""
        try:
            if not self.motors:
                QMessageBox.warning(self, "警告", "未连接电机，无法刷新状态！\n\n请确保电机连接正常。")
                return
            
            print("🔄 开始刷新关节角度和末端位姿...")
            
            # 1. 从电机同步输出端角度状态
            self.sync_output_angles_from_motors()
            
            # 2. 更新关节角度标签显示
            self.update_joint_angle_labels()
            
            # 3. 更新末端位姿显示
            self.update_end_effector_pose()
            
            # 4. 输出当前状态信息到控制台
            print("✅ 状态刷新完成！当前信息：")
            print(f"   关节角度: {[f'J{i+1}={a:.1f}°' for i, a in enumerate(self.output_joint_angles)]}")
            
            # 如果运动学模块可用，输出末端位姿信息
            if self.kinematics:
                try:
                    pose_info = self.kinematics.get_end_effector_pose(self.output_joint_angles)
                    position = pose_info['position']  # [x, y, z] mm
                    euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 度
                    
                    print(f"   末端位置: X={position[0]:.1f}mm, Y={position[1]:.1f}mm, Z={position[2]:.1f}mm")
                    print(f"   末端姿态: Roll={euler_angles[2]:.1f}°, Pitch={euler_angles[1]:.1f}°, Yaw={euler_angles[0]:.1f}°")
                    
                except Exception as pose_error:
                    print(f"⚠ 计算末端位姿失败: {pose_error}")
            else:
                print("   注：运动学模块未初始化，无法计算末端位姿")
            
            # 5. 简单的成功提示（不阻塞用户操作）
            print("🎉 关节角度和末端位姿刷新成功")
            
        except Exception as e:
            error_msg = f"刷新状态失败: {str(e)}"
            print(f"❌ {error_msg}")
            QMessageBox.critical(self, "错误", f"{error_msg}\n\n请检查电机连接和通信状态。")
    
    def update_step_size(self, value):
        """更新步进大小"""
        self.step_size = value
        self.update_button_texts()
    
    def update_speed(self, value):
        """更新运动速度"""
        self.speed = value
    
    def update_max_speed(self, value):
        """更新最大速度"""
        self.speed = value  # 最大速度作为运动速度
    
    def update_acceleration(self, value):
        """更新加速度"""
        self.acceleration = value
    
    def update_deceleration(self, value):
        """更新减速度"""
        self.deceleration = value
    
    def update_cartesian_linear_velocity(self, value):
        """更新笛卡尔线性速度"""
        self.cartesian_linear_velocity = value
        # 更新插补器参数
  
    
    def update_cartesian_angular_velocity(self, value):
        """更新笛卡尔角速度"""
        self.cartesian_angular_velocity = value
        # 更新插补器参数
  
    
    def update_cartesian_linear_acceleration(self, value):
        """更新笛卡尔线性加速度"""
        self.cartesian_linear_acceleration = value
        # 更新插补器参数
  
    
    def update_cartesian_angular_acceleration(self, value):
        """更新笛卡尔角加速度"""
        self.cartesian_angular_acceleration = value
        # 更新插补器参数
  
    
    def update_joint_max_velocity(self, value):
        """更新关节最大速度"""
        # 更新所有关节速度（简化版，实际可以分别设置）
        self.joint_max_velocities = [value] * 6
        # 更新插补器参数
 
    
    def update_joint_max_acceleration(self, value):
        """更新关节最大加速度"""
        # 更新所有关节加速度（简化版，实际可以分别设置）
        self.joint_max_accelerations = [value] * 6
        # 更新插补器参数
 
    
    
    def on_interpolation_type_changed(self, text):
        """插补类型改变时的处理"""
        # 保存当前参数值到缓存
        self._save_current_parameters_to_cache()
        
        if text == "关节空间插补":
            self.interpolation_type = "joint"
            self.interpolation_info_label.setText("📌 关节空间：各关节独立运动到目标")
            
            # 初始化关节空间执行器（如果还没有初始化）
            if self.joint_executor is None:
                try:
                    from core.arm_core.interpolation import JointSpaceInterpolator
                    from core.arm_core.trajectory_executor import JointSpaceTrajectoryExecutor
                    
                    joint_interpolator = JointSpaceInterpolator()
                    self.joint_executor = JointSpaceTrajectoryExecutor(
                        joint_interpolator, 
                        self.motor_config_manager
                    )
                    
                    # 同步到运动控制器
                    self.motion_controller.joint_executor = self.joint_executor
                    print("✅ 关节空间插补器和执行器初始化成功")
                except ImportError as e:
                    print(f"❌ 无法导入关节空间插补器: {e}")
                    QMessageBox.warning(self, "警告", "关节空间插补器不可用，请检查插补模块")
        elif text == "笛卡尔空间插补":
            self.interpolation_type = "cartesian"
            self.interpolation_info_label.setText("📌 笛卡尔空间：末端沿直线运动到目标")
            
            # 初始化笛卡尔插补器和执行器（如果还没有初始化）
            if self.cartesian_interpolator is None:
                try:
                    from core.arm_core.interpolation import CartesianSpaceInterpolator
                    from core.arm_core.trajectory_executor import CartesianTrajectoryExecutor
                    
                    self.cartesian_interpolator = CartesianSpaceInterpolator()
                    self.cartesian_executor = CartesianTrajectoryExecutor(
                        self.kinematics, 
                        self.cartesian_interpolator, 
                        self.motor_config_manager,
                        ik_solver=self.kinematics  # 传入运动学实例作为IK解选择器
                    )
                    
                    # 同步到运动控制器
                    self.motion_controller.cartesian_interpolator = self.cartesian_interpolator
                    self.motion_controller.cartesian_executor = self.cartesian_executor
                    print("✅ 笛卡尔空间插补器和执行器初始化成功")
                except ImportError as e:
                    print(f"❌ 无法导入笛卡尔空间插补器: {e}")
                    QMessageBox.warning(self, "警告", "笛卡尔空间插补器不可用，请检查插补模块")
                    # 回退到关节空间插补
                    self.interpolation_type_combo.setCurrentText("关节空间插补")
                    self.interpolation_type = "joint"
                    # 更新按钮状态（回退到关节插补，按钮应该被禁用）
                    self.update_save_button_state()
                    return
        elif text == "点到点":
            self.interpolation_type = "point_to_point"
            self.interpolation_info_label.setText("📌 点到点：直接运动到目标位置")
        
        # 根据板卡类型和插补类型切换参数界面
        # 首先检测当前板卡类型
        current_board_type = "Y" if self._is_y_board() else "X"
        self.switch_parameter_display(current_board_type, self.interpolation_type, self.current_mode)
        
        # 更新保存示教点按钮状态
        self.update_save_button_state()
        
    
    def update_button_texts(self):
        """更新按钮文字显示"""
        try:
            # 更新关节模式按钮
            if hasattr(self, 'joint_control_group'):
                for child in self.joint_control_group.findChildren(QPushButton):
                    text = child.text()
                    if "← -" in text and "°" in text:
                        child.setText(f"← -{self.step_size}°")
                    elif "→ +" in text and "°" in text:
                        child.setText(f"→ +{self.step_size}°")
            
            # 更新基座模式按钮文字
            if hasattr(self, 'base_control_group'):
                for child in self.base_control_group.findChildren(QPushButton):
                    text = child.text()
                    if "mm" in text:
                        if "← -" in text:
                            child.setText(f"← -{self.step_size}mm")
                        elif "→ +" in text:
                            child.setText(f"→ +{self.step_size}mm")
                        elif "↓ -" in text:
                            child.setText(f"↓ -{self.step_size}mm")
                        elif "↑ +" in text:
                            child.setText(f"↑ +{self.step_size}mm")
                    elif "°" in text:
                        if "↺ -" in text:
                            child.setText(f"↺ -{self.step_size}°")
                        elif "↻ +" in text:
                            child.setText(f"↻ +{self.step_size}°")
            
            # 更新工具模式按钮文字
            if hasattr(self, 'tool_control_group'):
                for child in self.tool_control_group.findChildren(QPushButton):
                    text = child.text()
                    if "mm" in text:
                        if "← -" in text:
                            child.setText(f"← -{self.step_size}mm")
                        elif "→ +" in text:
                            child.setText(f"→ +{self.step_size}mm")
                        elif "↓ -" in text:
                            child.setText(f"↓ -{self.step_size}mm")
                        elif "↑ +" in text:
                            child.setText(f"↑ +{self.step_size}mm")
                    elif "°" in text:
                        if "↺ -" in text:
                            child.setText(f"↺ -{self.step_size}°")
                        elif "↻ +" in text:
                            child.setText(f"↻ +{self.step_size}°")
                            
        except Exception as e:
            print(f"更新按钮文字失败: {e}")
    
    def move_joint(self, joint_index, angle_delta):
        """移动指定关节 - 使用运动控制器"""
        # 更新运动控制器的参数
        self.motion_controller.update_motion_parameters(
            speed=self.speed,
                    acceleration=self.acceleration,
            deceleration=self.deceleration
        )
        
        # 委托给运动控制器执行
        self.motion_controller.move_joint(joint_index, angle_delta)
    
    def move_base_translation(self, axis, distance):
        """基座坐标系平移 - 使用运动控制器"""
        # 更新运动控制器的参数
        self.motion_controller.update_cartesian_parameters(
            linear_velocity=self.cartesian_linear_velocity,
            angular_velocity=self.cartesian_angular_velocity,
            linear_acceleration=self.cartesian_linear_acceleration,
            angular_acceleration=self.cartesian_angular_acceleration
        )
        self.motion_controller.update_joint_parameters(
            max_velocities=self.joint_max_velocities,
            max_accelerations=self.joint_max_accelerations
        )
        self.motion_controller.set_interpolation_type(self.interpolation_type)
        
        # 委托给运动控制器执行
        self.motion_controller.move_base_translation(axis, distance)
    
    def move_base_rotation(self, axis, angle_delta):
        """基座坐标系旋转 - 使用运动控制器"""
        # 委托给运动控制器执行
        self.motion_controller.move_base_rotation(axis, angle_delta)
    
    def move_tool_translation(self, axis, distance):
        """工具坐标系平移 - 使用运动控制器"""
        # 更新运动控制器的参数
        self.motion_controller.update_cartesian_parameters(
            linear_velocity=self.cartesian_linear_velocity,
            angular_velocity=self.cartesian_angular_velocity,
            linear_acceleration=self.cartesian_linear_acceleration,
            angular_acceleration=self.cartesian_angular_acceleration
        )
        self.motion_controller.update_joint_parameters(
            max_velocities=self.joint_max_velocities,
            max_accelerations=self.joint_max_accelerations
        )
        self.motion_controller.set_interpolation_type(self.interpolation_type)
        
        # 委托给运动控制器执行
        self.motion_controller.move_tool_translation(axis, distance)
    
    
    def move_tool_rotation(self, axis, angle_delta):
        """工具坐标系旋转 - 使用运动控制器"""
        # 委托给运动控制器执行
        self.motion_controller.move_tool_rotation(axis, angle_delta)
    
    
    def get_current_joint_angles(self):
        """获取当前所有关节角度（输出端角度）"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "未连接电机，无法获取关节角度！")
            return None
        
        if len(self.motors) < 6:
            QMessageBox.warning(self, "提示", f"当前只连接了{len(self.motors)}个电机，部分关节角度将使用默认值0°")
        
        try:
            angles = []
            for i in range(6):
                motor_id_int = i + 1  # 电机ID从1开始，使用整数
                
                if motor_id_int in self.motors:
                    # 获取电机位置 - 使用正确的方法名
                    try:
                        motor_pos = self.motors[motor_id_int].read_parameters.get_position()
                    except AttributeError:
                        try:
                            motor_pos = self.motors[motor_id_int].get_position()
                        except AttributeError:
                            motor_pos = None
                    
                    if motor_pos is not None:
                        # 获取减速比和方向设置
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id_int)
                        direction = self.motor_config_manager.get_motor_direction(motor_id_int)
                        
                        # 将电机角度转换为输出端角度：(电机角度 * 方向) / 减速比
                        output_angle = (motor_pos * direction) / reducer_ratio
                        angles.append(output_angle)
                    else:
                        angles.append(0.0)
                        print(f"⚠ 警告: 无法获取关节J{motor_id_int}位置，使用默认值0°")
                else:
                    angles.append(0.0)
            return angles
        except Exception as e:
            print(f"获取关节角度失败: {e}")
            # QMessageBox.critical(self, "错误", f"获取关节角度失败: {str(e)}\n\n请检查电机连接状态。")
            return None
    
    def move_to_joint_angles(self, target_joints):
        """移动到指定关节角度"""
        try:
            if not self.motors:
                QMessageBox.warning(self, "警告", "未连接电机，无法执行运动！")
                return
            
            # 预处理：计算各关节电机端角度
            per_motor_angles = {}
            for i, output_angle in enumerate(target_joints):
                motor_id_int = i + 1
                if motor_id_int in self.motors:
                    normalized_output_angle = self.kinematics.normalize_angle(output_angle)
                    reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id_int)
                    direction = self.motor_config_manager.get_motor_direction(motor_id_int)
                    motor_angle = normalized_output_angle * reducer_ratio * direction
                    per_motor_angles[motor_id_int] = (normalized_output_angle, motor_angle)
            
            if self._is_y_board():
                # Y板：一次性多电机命令下发（FD梯形）
                try:
                    from Control_SDK.Control_Core import ZDTCommandBuilder
                except Exception as e:
                    QMessageBox.critical(self, "错误", f"导入命令构建器失败: {e}")
                    return
                
                commands = []
                for motor_id_int, (normalized_output_angle, motor_angle) in per_motor_angles.items():
                    func_body = ZDTCommandBuilder.position_mode_trapezoid(
                        position=motor_angle,
                        max_speed=self.speed,
                        acceleration=self.acceleration,
                        deceleration=self.deceleration,
                        is_absolute=True,
                        multi_sync=False
                    )
                    commands.append(self._build_single_command_for_multi(motor_id_int, func_body))
                
                # 选择任一已连接电机实例发送多电机命令
                first_motor = list(self.motors.values())[0]
                try:
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                except Exception as e:
                    QMessageBox.warning(self, "警告", f"多电机命令下发失败，尝试逐台控制: {e}")
                    # 兜底：逐电机发送（非同步）
                    for motor_id_int, (_, motor_angle) in per_motor_angles.items():
                        self.motors[motor_id_int].control_actions.move_to_position_trapezoid(
                            position=motor_angle,
                            max_speed=self.speed,
                            acceleration=self.acceleration,
                            deceleration=self.deceleration,
                            is_absolute=True,
                            multi_sync=False
                        )
            else:
                # X板：按同步标志+广播同步
                success_count = 0
                for motor_id_int, (_, motor_angle) in per_motor_angles.items():
                    self.motors[motor_id_int].control_actions.move_to_position_trapezoid(
                        position=motor_angle,
                        max_speed=self.speed,
                        acceleration=self.acceleration,
                        deceleration=self.deceleration,
                        is_absolute=True,
                        multi_sync=True
                    )
                    success_count += 1
                if success_count > 0:
                    try:
                        first_motor = list(self.motors.values())[0]
                        interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                        broadcast_motor = first_motor.__class__(
                            motor_id=0,
                            interface_type=first_motor.interface_type,
                            shared_interface=True,
                            **interface_kwargs
                        )
                        broadcast_motor.can_interface = first_motor.can_interface
                        broadcast_motor.control_actions.sync_motion()
                    except Exception as e:
                        print(f"同步运动命令发送失败: {e}")
            
            # 调试信息
            for motor_id_int, (normalized_output_angle, _) in per_motor_angles.items():
                original_angle = target_joints[motor_id_int - 1]
                if abs(original_angle - normalized_output_angle) > 0.1:
                    print(f"  J{motor_id_int}: 显示角度={original_angle:.1f}°, 控制角度={normalized_output_angle:.1f}°")
        except Exception as e:
            QMessageBox.critical(self, "错误", f"多关节运动失败: {str(e)}")
    
    def update_current_pose(self):
        """更新当前位姿显示 - 只更新关节角度，不计算末端位姿"""
        try:
            # 更新关节角度显示
            for i in range(6):
                motor_id_int = i + 1  # 电机ID从1开始，使用整数
                
                if motor_id_int in self.motors:
                    # 获取电机位置 - 使用正确的方法名
                    try:
                        motor_pos = self.motors[motor_id_int].read_parameters.get_position()
                    except AttributeError:
                        try:
                            motor_pos = self.motors[motor_id_int].get_position()
                        except AttributeError:
                            motor_pos = None
                    
                    if motor_pos is not None:
                        # 获取减速比和方向设置
                        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id_int)
                        direction = self.motor_config_manager.get_motor_direction(motor_id_int)
                        
                        # 将电机角度转换为输出端角度
                        output_angle = (motor_pos * direction) / reducer_ratio
                        self.current_joint_angles[i] = output_angle
                        
                        # 更新关节角度标签
                        if hasattr(self, f'joint_{i+1}_angle_label'):
                            getattr(self, f'joint_{i+1}_angle_label').setText(f"{output_angle:.1f}°")
                        
                        # 更新状态表格（显示输出端角度）
                        self.status_table.setItem(0, i, QTableWidgetItem(f"{output_angle:.1f}"))
            
            # 不再自动更新末端位姿 - 只在角度改变时手动调用update_end_effector_pose()
            # self.update_end_effector_pose()  # 移除这行
            
            # 更新基座模式和工具模式的位姿显示标签（基于当前缓存的角度）
            if self.kinematics and any(angle != 0 for angle in self.current_joint_angles):
                try:
                    pose_info = self.kinematics.get_end_effector_pose(self.current_joint_angles)
                    position = pose_info['position']  # [x, y, z] mm
                    euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 度
                    
                    # 更新基座模式显示标签
                    if hasattr(self, 'base_x_label'):
                        self.base_x_label.setText(f"{position[0]:.1f}mm")
                        self.base_y_label.setText(f"{position[1]:.1f}mm")
                        self.base_z_label.setText(f"{position[2]:.1f}mm")
                        self.base_roll_label.setText(f"{euler_angles[2]:.1f}°")  # Roll
                        self.base_pitch_label.setText(f"{euler_angles[1]:.1f}°")  # Pitch
                        self.base_yaw_label.setText(f"{euler_angles[0]:.1f}°")  # Yaw
                    
                    # 更新工具模式显示标签（与基座模式相同）
                    if hasattr(self, 'tcp_x_label'):
                        self.tcp_x_label.setText(f"{position[0]:.1f}mm")
                        self.tcp_y_label.setText(f"{position[1]:.1f}mm")
                        self.tcp_z_label.setText(f"{position[2]:.1f}mm")
                        self.tcp_roll_label.setText(f"{euler_angles[2]:.1f}°")  # Roll
                        self.tcp_pitch_label.setText(f"{euler_angles[1]:.1f}°")  # Pitch
                        self.tcp_yaw_label.setText(f"{euler_angles[0]:.1f}°")  # Yaw
                        
                except Exception as pose_error:
                    print(f"更新位姿标签失败: {pose_error}")
                        
        except Exception as e:
            pass  # 静默处理错误，避免频繁弹窗
    
    def update_motors(self, motors_info):
        """更新电机连接信息"""
        self.motors = motors_info
        motor_count = len(motors_info) if motors_info else 0
        
        # 初始化运动控制器
        if motors_info:
            self.motion_controller.initialize(
                motors=motors_info,
                motor_config_manager=self.motor_config_manager,
                kinematics=self.kinematics,
                output_joint_angles=self.output_joint_angles
            )
            
            # 同步已初始化的插补器到运动控制器
            if self.joint_executor is not None:
                self.motion_controller.joint_executor = self.joint_executor
            if self.cartesian_interpolator is not None:
                self.motion_controller.cartesian_interpolator = self.cartesian_interpolator
            if self.cartesian_executor is not None:
                self.motion_controller.cartesian_executor = self.cartesian_executor
        
        # 如果有电机连接，同步输出端角度状态
        if motors_info:
            self.sync_output_angles_from_motors()
            
            # 根据驱动板类型设置插补类型可用性和参数界面
            if self._is_y_board():
                # Y板：根据当前模式设置插补类型
                # 首先确保有所有插补选项
                if self.interpolation_type_combo.count() != 3:
                    # 临时断开信号
                    try:
                        self.interpolation_type_combo.currentTextChanged.disconnect()
                    except:
                        pass
                    
                    # 清空并重新添加所有选项
                    self.interpolation_type_combo.clear()
                    self.interpolation_type_combo.addItems(["关节空间插补", "笛卡尔空间插补", "点到点"])
                    
                    # 重新连接信号
                    self.interpolation_type_combo.currentTextChanged.connect(self.on_interpolation_type_changed)
                
                # 根据当前模式设置插补类型和可用性
                if self.current_mode == "joint":
                    # 关节模式：强制使用点到点，禁用选择
                    self.interpolation_type_combo.setCurrentText("点到点")
                    self.interpolation_type = "point_to_point"
                    self.interpolation_type_combo.setEnabled(False)
                    self.interpolation_type_combo.setToolTip("关节模式下只能使用点到点运动")
                    self.interpolation_info_label.setText("📌 点到点：直接运动到目标位置")
                    
                    # 切换到梯形曲线参数界面
                    self.switch_parameter_display("Y", "point_to_point", self.current_mode)
                else:
                    # 基座或工具模式：启用所有插补类型，默认选择笛卡尔
                    self.interpolation_type_combo.setEnabled(True)
                    self.interpolation_type_combo.setToolTip("选择运动插补类型\n关节空间：各关节独立运动\n笛卡尔空间：末端直线运动\n点到点：直接运动到目标位置")
                    self.interpolation_type_combo.setCurrentText("笛卡尔空间插补")
                    self.interpolation_type = "cartesian"
                    self.interpolation_info_label.setText("📌 笛卡尔空间：末端沿直线运动到目标")
                    
                    # 切换到Y板笛卡尔参数界面
                    self.switch_parameter_display("Y", "cartesian", self.current_mode)
                
                # 自动初始化笛卡尔插补器
                if self.cartesian_interpolator is None:
                    try:
                        from core.arm_core.interpolation import CartesianSpaceInterpolator
                        from core.arm_core.trajectory_executor import CartesianTrajectoryExecutor
                        
                        self.cartesian_interpolator = CartesianSpaceInterpolator()
                        self.cartesian_executor = CartesianTrajectoryExecutor(
                            self.kinematics, 
                            self.cartesian_interpolator, 
                            self.motor_config_manager,
                            ik_solver=self  # 传入self作为IK解选择器
                        )
                        print("✅ 检测到Y板，默认使用笛卡尔空间插补，插补器已自动初始化")
                    except ImportError as e:
                        print(f"❌ 无法导入笛卡尔空间插补器: {e}")
                        # 回退到关节空间插补
                        self.interpolation_type_combo.setCurrentText("关节空间插补")
                        self.interpolation_type = "joint"
                        self.switch_parameter_display("Y", "joint", self.current_mode)
                        self.interpolation_info_label.setText("📌 关节空间：各关节独立运动到目标")
                        # 更新按钮状态（回退到关节插补，按钮应该被禁用）
                        self.update_save_button_state()
                        return
                else:
                    print("✅ 检测到Y板，默认使用笛卡尔空间插补")
                
                # 更新插补信息标签
                self.interpolation_info_label.setText("📌 笛卡尔空间：末端沿直线运动到目标")
            else:
                # X板：只允许点到点运动，使用梯形曲线参数
                # 清空现有选项，只保留点到点
                self.interpolation_type_combo.clear()
                self.interpolation_type_combo.addItem("点到点")
                self.interpolation_type_combo.setCurrentText("点到点")
                self.interpolation_type = "point_to_point"
                self.interpolation_type_combo.setEnabled(False)
                self.interpolation_info_label.setText("📌 点到点：直接运动到目标位置")
                
                # 切换到X板梯形曲线参数界面
                self.switch_parameter_display("X", None, self.current_mode)
                print("✅ 检测到X板，仅支持点到点运动，使用梯形曲线参数")
            
            # 根据最终的插补类型更新保存示教点按钮状态
            self.update_save_button_state()
        else:
            # 没有电机时重置输出端角度状态
            self.output_joint_angles = [0.0] * 6
            self.update_joint_angle_labels()
            self.update_end_effector_pose()
            # 恢复插补类型选择，显示所有选项
            self.interpolation_type_combo.setEnabled(True)
            self.interpolation_type_combo.clear()
            self.interpolation_type_combo.addItems(["关节空间插补", "笛卡尔空间插补", "点到点"])
            self.interpolation_type_combo.setCurrentText("关节空间插补")
            self.interpolation_type = "joint"
            self.interpolation_info_label.setText("📌 关节空间：各关节独立运动到目标")
            
            # 没有电机连接时禁用保存示教点按钮
            if hasattr(self, 'save_teaching_point_btn'):
                self.save_teaching_point_btn.setEnabled(False)
                self.save_teaching_point_btn.setToolTip("请先连接电机")
        
        print(f"✅ 示教器：已更新电机连接信息，共{motor_count}个电机")
    
    def clear_motors(self):
        """清空电机连接"""
        self.motors = {}
        print("✅ 示教器：已清空电机连接")
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            self.motor_config_manager.config = self.motor_config_manager.load_config()
            print("✅ 示教器：电机配置已重新加载")
        except Exception as e:
            print(f"⚠ 示教器：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            if KINEMATICS_AVAILABLE:
                # 重新创建运动学实例，使用最新的DH参数配置
                self.kinematics = create_configured_kinematics()
                
                # 立即更新界面显示
                self.update_joint_angle_labels()
                self.update_end_effector_pose()
            else:
                print("⚠️ 运动学模块不可用，无法重新加载DH参数配置")
        except Exception as e:
            print(f"⚠ 示教器：重新加载DH参数配置失败: {e}")
            self.kinematics = None
    
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            
            # 停止笛卡尔运动定时器
            if hasattr(self, 'cartesian_timer') and self.cartesian_timer:
                self.cartesian_timer.stop()
            
            # 停止所有正在执行的程序
            if hasattr(self, 'program_running') and self.program_running:
                self.stop_teaching_program()
            
            # 停止所有电机运动
            if hasattr(self, 'motors') and self.motors:
                try:
                    for motor_id, motor in self.motors.items():
                        motor.control_actions.stop()
                except Exception as e:
                    print(f"⚠️ 停止电机运动时出错: {e}")
            
            print("✅ 示教器控件资源清理完成")
            
        except Exception as e:
            print(f"⚠️ 示教器控件清理资源时发生错误: {e}")
        finally:
            event.accept() 
    
    
    def save_current_pose_to_hand_eye_config(self):
        """保存当前关节角度到手眼标定配置文件"""
        try:
            # 检查是否有电机连接
            if not self.motors:
                QMessageBox.warning(self, "警告", "未连接电机，无法保存当前位置！\n\n请确保电机连接正常。")
                self.save_status_label.setText("❌ 保存失败：未连接电机")
                self.save_status_label.setStyleSheet("color: red; font-size: 10px; padding: 2px;")
                return
            
            # 检查位置名称
            pose_name = self.pose_name_input.text().strip()
            if not pose_name:
                QMessageBox.warning(self, "警告", "请输入位置名称！")
                self.save_status_label.setText("❌ 保存失败：请输入位置名称")
                self.save_status_label.setStyleSheet("color: red; font-size: 10px; padding: 2px;")
                return
            
            # 确保位置名称符合规范
            if not pose_name.startswith('pose_'):
                pose_name = f"pose_{pose_name}"
            
            # 获取当前规范化后的关节角度（用于保存）
            current_normalized_angles = []
            for i in range(6):
                # 使用规范化后的输出端角度
                normalized_angle = self.kinematics.normalize_angle(self.output_joint_angles[i])
                # 确保是纯Python float类型，避免numpy对象序列化问题
                current_normalized_angles.append(float(round(normalized_angle, 1)))  # 保留1位小数
            
            # 构建手眼标定配置文件路径
            config_path = os.path.join(
                os.path.dirname(os.path.dirname(current_dir)),
                "config", "hand_eye_calibration_poses.yaml")
            
            # 读取现有配置
            poses_data = {
                'description': '手眼标定预设位置配置',
                'notes': '关节角度单位为度制，范围建议在±120度内',
                'pose_count': 0,
                'poses': []
            }
            
            if os.path.exists(config_path):
                try:
                    with open(config_path, 'r', encoding='utf-8') as f:
                        poses_data = yaml.safe_load(f) or poses_data
                except Exception as e:
                    print(f"读取现有配置失败，将创建新配置: {e}")
            
            # 检查是否已存在同名位置
            existing_names = [pose.get('name', '') for pose in poses_data.get('poses', [])]
            if pose_name in existing_names:
                reply = QMessageBox.question(
                    self, 
                    "位置已存在", 
                    f"位置 '{pose_name}' 已存在，是否覆盖？\n\n"
                    f"当前角度: {[f'{a:.1f}°' for a in current_normalized_angles]}",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply != QMessageBox.Yes:
                    self.save_status_label.setText("❌ 保存取消：位置已存在")
                    self.save_status_label.setStyleSheet("color: orange; font-size: 10px; padding: 2px;")
                    return
                
                # 找到并更新现有位置
                for pose in poses_data['poses']:
                    if pose.get('name') == pose_name:
                        pose['joint_angles'] = current_normalized_angles
                        break
            else:
                # 添加新位置
                new_pose = {
                    'name': pose_name,
                    'joint_angles': current_normalized_angles
                }
                poses_data['poses'].append(new_pose)
            
            # 更新位置计数
            poses_data['pose_count'] = len(poses_data['poses'])
            
            # 保存到文件
            os.makedirs(os.path.dirname(config_path), exist_ok=True)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(poses_data, f, default_flow_style=False, allow_unicode=True, indent=2)
            
            # 更新状态显示
            self.save_status_label.setText(f"✅ 已保存位置 '{pose_name}': {[f'{a:.1f}°' for a in current_normalized_angles]}")
            self.save_status_label.setStyleSheet("color: green; font-size: 10px; padding: 2px;")
            
            # 清空输入框
            self.pose_name_input.clear()
            
            # 控制台输出
            print(f"手眼标定位置已保存: {pose_name}")
            print(f"关节角度: {[f'J{i+1}={a:.1f}°' for i, a in enumerate(current_normalized_angles)]}")
            print(f"配置文件: {config_path}")
            print(f"总位置数: {poses_data['pose_count']}")
            
            # 成功提示
            QMessageBox.information(
                self, 
                "保存成功", 
                f"位置 '{pose_name}' 已成功保存到手眼标定配置！\n\n"
                f"关节角度: {[f'J{i+1}={a:.1f}°' for i, a in enumerate(current_normalized_angles)]}\n"
                f"配置文件: {os.path.basename(config_path)}\n"
                f"总位置数: {poses_data['pose_count']}"
            )
            
        except Exception as e:
            error_msg = f"保存位置失败: {str(e)}"
            print(f"❌ {error_msg}")
            self.save_status_label.setText(f"❌ 保存失败: {str(e)[:50]}...")
            self.save_status_label.setStyleSheet("color: red; font-size: 10px; padding: 2px;")
            QMessageBox.critical(self, "错误", f"{error_msg}\n\n请检查文件权限和路径。")
    
    def create_teaching_program_content(self):
        """创建示教编程标签页内容"""
        layout = QVBoxLayout(self.teaching_program_tab)
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        
        # 添加滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setFrameShape(QScrollArea.NoFrame)
        
        # 创建滚动区域的内容widget
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setContentsMargins(10, 10, 10, 10)
        scroll_layout.setSpacing(10)
        
        # 模式说明
        info_label = QLabel("📝 示教编程: 保存和回放机械臂运动轨迹，支持多点连续运动")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 5px; background-color: #f8f9fa; border-radius: 4px;")
        info_label.setWordWrap(True)
        scroll_layout.addWidget(info_label)
        
        # 创建示教点列表区域
        self.create_teaching_points_list(scroll_layout)
        
        # 创建示教编程控制按钮
        self.create_teaching_program_controls(scroll_layout)
        
        # 创建状态显示区域
        self.create_independent_status_display(scroll_layout)
        
        scroll_layout.addStretch()
        
        # 设置滚动区域
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def create_teaching_points_list(self, parent_layout):
        """创建示教点列表区域"""
        group = QGroupBox("📋 示教点列表")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # 示教点表格
        self.teaching_points_table = QTableWidget()
        self.teaching_points_table.setColumnCount(12)  # 增加一列用于角加速度
        # 初始设置表头（将在update_table_headers中根据插补方式更新）
        self.update_table_headers()
        
        # 设置表格属性
        self.teaching_points_table.setAlternatingRowColors(True)
        self.teaching_points_table.setSelectionBehavior(QTableWidget.SelectRows)
        self.teaching_points_table.setSelectionMode(QTableWidget.SingleSelection)
        self.teaching_points_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.teaching_points_table.setMinimumHeight(200)
        
        # 设置列宽
        header = self.teaching_points_table.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.Fixed)  # 序号列固定宽度
        self.teaching_points_table.setColumnWidth(0, 50)
        header.setSectionResizeMode(11, QHeaderView.Fixed)  # 模式列固定宽度
        self.teaching_points_table.setColumnWidth(11, 80)
        for i in range(1, 11):
            header.setSectionResizeMode(i, QHeaderView.Stretch)
        
        layout.addWidget(self.teaching_points_table)
        
        # 表格操作按钮
        table_controls_layout = QHBoxLayout()
        
        self.delete_point_btn = QPushButton("🗑️ 删除选中")
        self.delete_point_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.delete_point_btn.clicked.connect(self.delete_selected_teaching_point)
        table_controls_layout.addWidget(self.delete_point_btn)
        
        self.clear_all_points_btn = QPushButton("🧹 清空所有")
        self.clear_all_points_btn.setStyleSheet("QPushButton { background-color: #ff5722; color: white; }")
        self.clear_all_points_btn.clicked.connect(self.clear_all_teaching_points)
        table_controls_layout.addWidget(self.clear_all_points_btn)
        
        self.move_to_point_btn = QPushButton("➡️ 移动到选中点")
        self.move_to_point_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.move_to_point_btn.clicked.connect(self.move_to_selected_point)
        table_controls_layout.addWidget(self.move_to_point_btn)
        
        table_controls_layout.addStretch()
        layout.addLayout(table_controls_layout)
        
        parent_layout.addWidget(group)
    
    def create_teaching_program_controls(self, parent_layout):
        """创建示教编程控制区域"""
        group = QGroupBox("🎮 程序控制")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)
        
        # 第一行：程序执行控制
        control_layout = QHBoxLayout()
        
        self.run_program_btn = QPushButton("▶️ 运行程序")
        self.run_program_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                font-size: 14px;
                padding: 10px 20px;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        self.run_program_btn.clicked.connect(self.run_teaching_program)
        control_layout.addWidget(self.run_program_btn)
        
        self.emergency_stop_btn = QPushButton("🛑 紧急停止")
        self.emergency_stop_btn.setStyleSheet("""
            QPushButton {
                background-color: #f44336;
                color: white;
                border: none;
                border-radius: 6px;
                font-weight: bold;
                font-size: 12px;
                padding: 8px 16px;
                min-width: 100px;
            }
            QPushButton:hover {
                background-color: #da190b;
            }
            QPushButton:pressed {
                background-color: #c62828;
            }
            QPushButton:disabled {
                background-color: #ffcdd2;
                color: #666666;
            }
        """)
        self.emergency_stop_btn.clicked.connect(self.emergency_stop_teaching_program)
        self.emergency_stop_btn.setEnabled(False)  # 初始状态禁用
        control_layout.addWidget(self.emergency_stop_btn)
        
        control_layout.addStretch()
        layout.addLayout(control_layout)
        
        # 第二行：程序状态显示
        status_layout = QHBoxLayout()
        status_layout.addWidget(QLabel("程序状态:"))
        self.program_status_label = QLabel("就绪")
        self.program_status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        status_layout.addWidget(self.program_status_label)
        
        status_layout.addWidget(QLabel("  |  当前点:"))
        self.current_point_label = QLabel("--/--")
        self.current_point_label.setStyleSheet("font-weight: bold; color: #2196F3;")
        status_layout.addWidget(self.current_point_label)
        
        status_layout.addStretch()
        layout.addLayout(status_layout)
        
        # 第二点五行：重复执行选项
        repeat_layout = QHBoxLayout()
        self.repeat_execution_checkbox = QCheckBox("🔄 重复执行")
        self.repeat_execution_checkbox.setToolTip("勾选后程序将循环执行，直到手动停止")
        repeat_layout.addWidget(self.repeat_execution_checkbox)
        
        repeat_layout.addWidget(QLabel("  |  执行次数:"))
        self.execution_count_label = QLabel("0")
        self.execution_count_label.setStyleSheet("font-weight: bold; color: #9C27B0;")
        repeat_layout.addWidget(self.execution_count_label)
        
        repeat_layout.addStretch()
        layout.addLayout(repeat_layout)
        
        # 第三行：保存/加载程序
        file_layout = QHBoxLayout()
        
        self.save_program_btn = QPushButton("💾 保存程序")
        self.save_program_btn.clicked.connect(self.save_teaching_program_to_file)
        file_layout.addWidget(self.save_program_btn)
        
        self.load_program_btn = QPushButton("📁 加载程序")
        self.load_program_btn.clicked.connect(self.load_teaching_program_from_file)
        file_layout.addWidget(self.load_program_btn)
        
        file_layout.addStretch()
        layout.addLayout(file_layout)
        
        parent_layout.addWidget(group)
    
    def save_teaching_point(self):
        """保存当前位置为示教点"""
        try:
            if not self.motors:
                QMessageBox.warning(self, "警告", "未连接电机，无法保存示教点！\n\n请确保电机连接正常。")
                return
            
            # 获取当前规范化的关节角度（用于驱动）
            normalized_joint_angles = []
            for i in range(6):
                normalized_angle = self.kinematics.normalize_angle(self.output_joint_angles[i])
                normalized_joint_angles.append(float(normalized_angle))
            
            # 计算当前末端位姿（用于显示）
            end_pose = None
            if self.kinematics:
                try:
                    pose_info = self.kinematics.get_end_effector_pose(self.output_joint_angles)
                    position = pose_info['position']  # [x, y, z] mm
                    euler_angles = pose_info['euler_angles']  # [yaw, pitch, roll] 度
                    end_pose = {
                        'position': position,
                        'euler_angles': euler_angles
                    }
                except Exception as e:
                    print(f"计算末端位姿失败: {e}")
            
            # 获取当前插补方式和参数
            interpolation_params = self._get_current_interpolation_params()
            
            # 创建示教点数据
            teaching_point = {
                'index': len(self.teaching_program) + 1,
                'joint_angles': normalized_joint_angles,  # 用于驱动的规范化角度
                'end_pose': end_pose,  # 用于显示的末端位姿
                'interpolation_type': self.interpolation_type,  # 插补方式
                'interpolation_params': interpolation_params,  # 当前使用的插补参数（包含所有运动参数）
                'mode': self.current_mode,  # 当前模式
                'timestamp': time.time(),  # 时间戳
            }
            
            # 添加到示教程序列表
            self.teaching_program.append(teaching_point)
            
            # 更新表格显示
            self.update_teaching_points_table()
            
            # 显示成功消息
            mode_names = {"joint": "关节", "base": "基座", "tool": "工具"}
            mode_name = mode_names.get(self.current_mode, "未知")
            
            if end_pose:
                pos = end_pose['position']
                euler = end_pose['euler_angles']
                # 根据插补方式生成参数显示信息
                param_info = self._get_interpolation_param_display(interpolation_params)
                
            else:
                param_info = self._get_interpolation_param_display(interpolation_params)
                print(f"✅ 已保存示教点 {teaching_point['index']} ({mode_name}模式, {self.interpolation_type}插补)")
            
            # 根据插补类型显示名称
            interpolation_names = {
                "cartesian": "笛卡尔空间插补",
                "joint": "关节空间插补", 
                "point_to_point": "点到点运动"
            }
            interpolation_name = interpolation_names.get(self.interpolation_type, "未知插补类型")
            param_info = self._get_interpolation_param_display(interpolation_params)
            QMessageBox.information(self, "成功", 
                f"示教点 {teaching_point['index']} 已保存！\n\n"
                f"模式: {mode_name}模式\n"
                f"插补: {interpolation_name}\n"
                f"运动参数: {param_info}")
        
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存示教点失败: {str(e)}")
    
    def update_teaching_points_table(self):
        """更新示教点表格显示"""
        self.teaching_points_table.setRowCount(len(self.teaching_program))
        
        for i, point in enumerate(self.teaching_program):
            # 序号
            self.teaching_points_table.setItem(i, 0, QTableWidgetItem(str(point['index'])))
            
            # 末端位姿
            if point['end_pose']:
                pos = point['end_pose']['position']
                euler = point['end_pose']['euler_angles']
                
                self.teaching_points_table.setItem(i, 1, QTableWidgetItem(f"{pos[0]:.1f}"))  # X
                self.teaching_points_table.setItem(i, 2, QTableWidgetItem(f"{pos[1]:.1f}"))  # Y
                self.teaching_points_table.setItem(i, 3, QTableWidgetItem(f"{pos[2]:.1f}"))  # Z
                self.teaching_points_table.setItem(i, 4, QTableWidgetItem(f"{euler[2]:.1f}"))  # Roll
                self.teaching_points_table.setItem(i, 5, QTableWidgetItem(f"{euler[1]:.1f}"))  # Pitch
                self.teaching_points_table.setItem(i, 6, QTableWidgetItem(f"{euler[0]:.1f}"))  # Yaw
            else:
                for j in range(1, 7):
                    self.teaching_points_table.setItem(i, j, QTableWidgetItem("--"))
            
            # 运动参数 - 根据插补类型显示
            interpolation_type = point.get('interpolation_type', 'joint')
            interpolation_params = point.get('interpolation_params', {})
            
            if interpolation_type == "cartesian" and interpolation_params.get('type') == 'cartesian':
                # 笛卡尔参数显示（4个参数）
                self.teaching_points_table.setItem(i, 7, QTableWidgetItem(f"{interpolation_params.get('linear_velocity', 50.0):.1f}"))
                self.teaching_points_table.setItem(i, 8, QTableWidgetItem(f"{interpolation_params.get('angular_velocity', 30.0):.1f}"))
                self.teaching_points_table.setItem(i, 9, QTableWidgetItem(f"{interpolation_params.get('linear_acceleration', 100.0):.1f}"))
                self.teaching_points_table.setItem(i, 10, QTableWidgetItem(f"{interpolation_params.get('angular_acceleration', 60.0):.1f}"))
            elif interpolation_type == "joint" and interpolation_params.get('type') == 'joint_space':
                # Y板关节空间参数显示（3个参数）
                max_vel = max(interpolation_params.get('max_velocities', [30.0] * 6))
                max_acc = max(interpolation_params.get('max_accelerations', [60.0] * 6))
                self.teaching_points_table.setItem(i, 7, QTableWidgetItem(f"{max_vel:.1f}"))
                self.teaching_points_table.setItem(i, 8, QTableWidgetItem(f"{max_acc:.1f}"))
                self.teaching_points_table.setItem(i, 9, QTableWidgetItem("--"))
                self.teaching_points_table.setItem(i, 10, QTableWidgetItem("--"))
            else:
                # 默认显示梯形曲线参数（3个参数）
                self.teaching_points_table.setItem(i, 7, QTableWidgetItem(str(interpolation_params.get('max_speed', 100))))
                self.teaching_points_table.setItem(i, 8, QTableWidgetItem(str(interpolation_params.get('acceleration', 500))))
                self.teaching_points_table.setItem(i, 9, QTableWidgetItem(str(interpolation_params.get('deceleration', 500))))
                self.teaching_points_table.setItem(i, 10, QTableWidgetItem("--"))
            
            # 模式（移到第11列）
            mode_names = {"joint": "关节", "base": "基座", "tool": "工具"}
            mode_name = mode_names.get(point['mode'], point['mode'])
            self.teaching_points_table.setItem(i, 11, QTableWidgetItem(mode_name))
            
            # 设置文本居中对齐
            for j in range(12):
                item = self.teaching_points_table.item(i, j)
                if item:
                    item.setTextAlignment(Qt.AlignCenter)
    
    def delete_selected_teaching_point(self):
        """删除选中的示教点"""
        current_row = self.teaching_points_table.currentRow()
        if current_row >= 0 and current_row < len(self.teaching_program):
            reply = QMessageBox.question(self, "确认删除", 
                f"确定要删除示教点 {current_row + 1} 吗？",
                QMessageBox.Yes | QMessageBox.No)
            
            if reply == QMessageBox.Yes:
                del self.teaching_program[current_row]
                # 重新编号
                for i, point in enumerate(self.teaching_program):
                    point['index'] = i + 1
                self.update_teaching_points_table()
                print(f"✅ 已删除示教点，当前共有 {len(self.teaching_program)} 个示教点")
    
    def clear_all_teaching_points(self):
        """清空所有示教点"""
        if len(self.teaching_program) == 0:
            QMessageBox.information(self, "提示", "示教点列表已经为空！")
            return
        
        reply = QMessageBox.question(self, "确认清空", 
            f"确定要清空所有 {len(self.teaching_program)} 个示教点吗？\n\n此操作不可撤销！",
            QMessageBox.Yes | QMessageBox.No)
        
        if reply == QMessageBox.Yes:
            self.teaching_program.clear()
            self.update_teaching_points_table()
            print("✅ 已清空所有示教点")
    
    def move_to_selected_point(self):
        """移动到选中的示教点"""
        current_row = self.teaching_points_table.currentRow()
        if current_row < 0 or current_row >= len(self.teaching_program):
            QMessageBox.warning(self, "警告", "请先选择一个示教点！")
            return
        
        if not self.motors:
            QMessageBox.warning(self, "警告", "未连接电机，无法执行运动！")
            return
        
        try:
            point = self.teaching_program[current_row]
            self.move_to_teaching_point(point)
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"移动到示教点失败: {str(e)}")
    
    def move_to_teaching_point(self, teaching_point):
        """移动到指定示教点（使用保存的参数）"""
        try:
            joint_angles = teaching_point['joint_angles']
            
            print(f"🎯 开始移动到示教点 {teaching_point['index']}")
            print(f"   目标角度: {[f'{a:.1f}°' for a in joint_angles]}")
            
            # 调用MotionController的统一方法，使用保存的参数
            success = self.motion_controller.move_to_teaching_point(teaching_point, use_saved_params=True)
            
            if success:
                # 更新输出端角度状态
                self.output_joint_angles = list(joint_angles)
                self.update_joint_angle_labels()
                self.update_end_effector_pose()
                
                print(f"✅ 示教点 {teaching_point['index']} 运动命令已发送")
            else:
                raise Exception("MotionController执行失败")
                
        except Exception as e:
            raise Exception(f"移动到示教点失败: {str(e)}")
    
    def run_teaching_program(self):
        """运行示教程序"""
        if len(self.teaching_program) == 0:
            QMessageBox.warning(self, "警告", "示教程序为空，请先添加示教点！")
            return
        
        if not self.motors:
            QMessageBox.warning(self, "警告", "未连接电机，无法运行程序！")
            return
        
        # 重置执行次数计数器
        self.execution_count = 0
        self.execution_count_label.setText("0")
        
        # 获取重复执行选项
        repeat_execution = self.repeat_execution_checkbox.isChecked()
        
        # 启动程序执行线程
        self.program_thread = TeachingProgramThread(
            self.teaching_program, self.motors, self, repeat_execution
        )
        self.program_thread.point_started.connect(self.on_program_point_started)
        self.program_thread.point_reached.connect(self.on_program_point_reached)
        self.program_thread.program_finished.connect(self.on_program_finished)
        self.program_thread.program_error.connect(self.on_program_error)
        self.program_thread.cycle_completed.connect(self.on_program_cycle_completed)
        self.program_thread.waiting_for_position.connect(self.on_waiting_for_position)
        
        self.program_thread.start()
        
        # 更新按钮状态
        self.run_program_btn.setEnabled(False)
        self.emergency_stop_btn.setEnabled(True)
        
        # 更新状态显示
        if repeat_execution:
            self.program_status_label.setText("循环运行中")
            print(f"开始循环运行示教程序，共 {len(self.teaching_program)} 个点")
        else:
            self.program_status_label.setText("运行中")
            print(f"开始运行示教程序，共 {len(self.teaching_program)} 个点")
        
        self.program_status_label.setStyleSheet("font-weight: bold; color: #ff9800;")
        self.current_point_label.setText(f"1/{len(self.teaching_program)}")
        
        # 禁用重复执行选项，防止运行中修改
        self.repeat_execution_checkbox.setEnabled(False)
    
    def emergency_stop_teaching_program(self):
        """紧急停止示教程序"""
        # 首先停止程序线程
        if hasattr(self, 'program_thread') and self.program_thread.isRunning():
            self.program_thread.stop()
        
        # 紧急停止所有电机
        if self.motors:
            try:
                for motor_id, motor in self.motors.items():
                    try:
                        motor.control_actions.stop()
                        print(f"✅ 电机 {motor_id} 停止成功")
                    except Exception as e:
                        print(f"❌ 电机 {motor_id} 停止失败: {e}")
            except Exception as e:
                print(f"❌ 紧急停止过程中发生错误: {e}")
        
        # 更新按钮状态
        self.run_program_btn.setEnabled(True)
        self.emergency_stop_btn.setEnabled(False)
        
        # 恢复重复执行选项
        self.repeat_execution_checkbox.setEnabled(True)
        
        # 更新状态显示
        self.program_status_label.setText("紧急停止")
        self.program_status_label.setStyleSheet("font-weight: bold; color: #f44336;")
        self.current_point_label.setText("--/--")
        
        
        print("🛑 示教程序紧急停止完成")
    
    def on_program_point_reached(self, point_index):
        """程序执行到某个点时的回调"""
        self.current_point_label.setText(f"{point_index + 1}/{len(self.teaching_program)}")
        print(f"📍 已到达示教点 {point_index + 1}")
    
    def on_program_finished(self):
        """程序执行完成时的回调"""
        # 更新按钮状态
        self.run_program_btn.setEnabled(True)
        self.emergency_stop_btn.setEnabled(False)
        
        # 恢复重复执行选项
        self.repeat_execution_checkbox.setEnabled(True)
        
        # 更新状态显示
        self.program_status_label.setText("就绪")
        self.program_status_label.setStyleSheet("font-weight: bold; color: #4CAF50;")
        self.current_point_label.setText("--/--")
        
        print("✅ 示教程序执行完成")
    
    def on_program_error(self, error_message):
        """程序执行错误时的回调"""
        self.on_program_finished()
        QMessageBox.critical(self, "程序执行错误", f"示教程序执行失败:\n{error_message}")
    
    def save_teaching_program_to_file(self):
        """保存示教程序到文件"""
        if len(self.teaching_program) == 0:
            QMessageBox.warning(self, "警告", "示教程序为空，无法保存！")
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "保存示教程序", "config/teaching_program/teaching_program.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                import json
                # 创建可序列化的数据副本
                serializable_program = []
                
                for point in self.teaching_program:
                    serializable_point = {
                        'index': int(point['index']),
                        'joint_angles': [float(angle) for angle in point['joint_angles']],
                        'mode': str(point['mode']),
                        'timestamp': float(point['timestamp'])
                    }
                    
                    # 添加插补类型和参数
                    if 'interpolation_type' in point:
                        serializable_point['interpolation_type'] = str(point['interpolation_type'])
                    if 'interpolation_params' in point:
                        serializable_point['interpolation_params'] = point['interpolation_params']
                    
                    # 处理末端位姿数据
                    if point['end_pose'] and point['end_pose'] is not None:
                        serializable_point['end_pose'] = {
                            'position': [float(pos) for pos in point['end_pose']['position']],
                            'euler_angles': [float(angle) for angle in point['end_pose']['euler_angles']]
                        }
                    else:
                        serializable_point['end_pose'] = None
                    
                    # 运动参数已经包含在interpolation_params中，不需要重复保存
                    
                    serializable_program.append(serializable_point)
                
                # 保存到文件
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(serializable_program, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(self, "成功", f"示教程序已保存到:\n{file_path}")
                print(f"💾 示教程序已保存: {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"保存示教程序失败:\n{str(e)}")
                print(f"保存失败详细错误: {e}")  # 调试信息
    
    def load_teaching_program_from_file(self):
        """从文件加载示教程序"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "加载示教程序", "config/teaching_program/teaching_program.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                import json
                with open(file_path, 'r', encoding='utf-8') as f:
                    loaded_program = json.load(f)
                
                # 验证数据格式
                if not isinstance(loaded_program, list):
                    raise ValueError("无效的示教程序格式")
                
                # 清空当前程序并加载新程序
                self.teaching_program = loaded_program
                self.update_teaching_points_table()
                
                QMessageBox.information(self, "成功", 
                    f"示教程序已加载！\n\n共加载 {len(self.teaching_program)} 个示教点")
                print(f"📁 示教程序已加载: {file_path}, 共 {len(self.teaching_program)} 个点")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"加载示教程序失败:\n{str(e)}")
    
    def on_program_cycle_completed(self):
        """程序循环完成时的回调"""
        self.execution_count += 1
        self.execution_count_label.setText(str(self.execution_count))
        
        # 更新状态显示
        self.program_status_label.setText(f"循环运行中 (第{self.execution_count}轮)")
        self.program_status_label.setStyleSheet("font-weight: bold; color: #ff9800;")
        self.current_point_label.setText(f"1/{len(self.teaching_program)}")
        
        print(f"完成第 {self.execution_count} 轮执行")
    
    def on_waiting_for_position(self, point_index, status_msg):
        """等待到位状态更新"""
        # 更新状态显示
        self.program_status_label.setText(f"运行中 - {status_msg}")
        self.program_status_label.setStyleSheet("font-weight: bold; color: #2196f3;")
    
    def _is_y_board(self):
        """判断是否全为Y版驱动板"""
        if not self.motors:
            return False
        versions = set()
        for m in self.motors.values():
            versions.add(str(getattr(m, 'drive_version', 'Y')).upper())
        return versions == {"Y"}
    
    def _build_single_command_for_multi(self, motor_id, function_body):
        """构造"地址+功能码+参数+6B"的子命令（用于多电机命令）"""
        try:
            from Control_SDK.Control_Core import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, function_body)
        except Exception:
            return [motor_id] + function_body
    
    def on_program_point_started(self, point_index):
        """程序开始执行某个点时：高亮该行并滚动可见"""
        try:
            if hasattr(self, 'teaching_points_table') and self.teaching_points_table.rowCount() > point_index >= 0:
                self.teaching_points_table.selectRow(point_index)
                item = self.teaching_points_table.item(point_index, 0)
                if item:
                    self.teaching_points_table.scrollToItem(item)
                # 同步当前点标签
                self.current_point_label.setText(f"{point_index + 1}/{len(self.teaching_program)}")
        except Exception as e:
            print(f"高亮示教点行失败: {e}")


class TeachingProgramThread(QThread):
    """示教程序执行线程"""
    
    point_reached = pyqtSignal(int)  # 到达某个点
    point_started = pyqtSignal(int)  # 开始执行某个点
    program_finished = pyqtSignal()  # 程序完成
    program_error = pyqtSignal(str)  # 程序错误
    cycle_completed = pyqtSignal()  # 程序循环完成
    waiting_for_position = pyqtSignal(int, str)  # 等待到位状态 (点序号, 状态信息)
    
    def __init__(self, teaching_program, motors, parent_widget, repeat_execution):
        super().__init__()
        self.teaching_program = teaching_program
        self.motors = motors
        self.parent_widget = parent_widget
        self.is_running = True
        self.repeat_execution = repeat_execution
    
    def run(self):
        """执行示教程序"""
        try:
            while self.is_running:
                # 执行一轮示教程序
                for i, point in enumerate(self.teaching_program):
                    if not self.is_running:
                        break
                    
                    # 通知开始执行该点：用于UI高亮
                    self.point_started.emit(i)
                    
                    # 移动到示教点（根据保存的插补类型执行）
                    try:
                        saved_interpolation_type = point.get('interpolation_type', 'point_to_point')
                        print(f"🎯 示教点 {i+1}: 使用 {saved_interpolation_type} 插补类型")
                        self.parent_widget.move_to_teaching_point(point)
                    except Exception as point_error:
                        self.program_error.emit(f"示教点 {i+1} 执行失败: {str(point_error)}")
                        break
                    
                    # 根据插补类型和模式精确判断是否需要等待实际位置到达
                    saved_interpolation_type = point.get('interpolation_type', 'point_to_point')
                    saved_mode = point.get('mode', 'joint')
                    
                    need_wait_for_position = True  # 默认需要等待
                    
                    # 根据MotionController的执行逻辑判断是否使用了插补器
                    if saved_mode == "joint":
                        # 关节模式：直接控制关节角度，需要位置检测
                        need_wait_for_position = True
                        print(f"  关节模式直接运动，需要等待实际位置到达")
                    elif saved_interpolation_type == "cartesian":
                        # 笛卡尔空间插补，不需要位置检测
                        need_wait_for_position = False
                        print(f"  笛卡尔插补运动已完成，跳过位置等待")
                    elif saved_interpolation_type == "joint":
                        # 关节空间插补，不需要位置检测
                        need_wait_for_position = False
                        print(f"  关节空间插补运动已完成，跳过位置等待")
                    else:
                        # 点到点运动，需要位置检测
                        need_wait_for_position = True
                        print(f"  点到点运动，需要等待实际位置到达")
                    
                    if need_wait_for_position:
                        # 等待机械臂到达目标位置
                        if not self._wait_for_position_reached(point['joint_angles'], timeout=30.0):
                            if self.is_running:  # 只有在非停止状态下才报错
                                self.program_error.emit(f"示教点 {i+1} 运动超时，未能在30秒内到达目标位置")
                            break
                    else:
                        # 插补运动：只做简单的延时等待，不做严格的位置检测
                        print(f"  插补运动，延时等待200ms以确保运动稳定...")
                        remaining_ms = 200  # 200ms缓冲时间
                        step_ms = 50
                        while self.is_running and remaining_ms > 0:
                            self.msleep(step_ms)
                            remaining_ms -= step_ms
                    
                    if not self.is_running:
                        break
                    
                    # 发送点到达信号
                    self.point_reached.emit(i)
                    
                    # 示教点间短暂稳定等待
                    remaining_ms = 200  # 减少到200ms，因为已经等待到位了
                    step_ms = 50
                    while self.is_running and remaining_ms > 0:
                        self.msleep(step_ms)
                        remaining_ms -= step_ms
                    if not self.is_running:
                        break
                
                # 如果程序还在运行，发送循环完成信号
                if self.is_running:
                    self.cycle_completed.emit()
                    
                    # 如果不是重复执行模式，退出循环
                    if not self.repeat_execution:
                        break
                    
                    # 在循环间添加短暂延时（可中断）
                    remaining_ms = 500  # 减少到500ms，给用户观察时间但不过长
                    step_ms = 50
                    while self.is_running and remaining_ms > 0:
                        self.msleep(step_ms)
                        remaining_ms -= step_ms
            
            # 程序正常结束
            if self.is_running:
                self.program_finished.emit()
                
        except Exception as e:
            self.program_error.emit(str(e))
    
    def _wait_for_position_reached(self, target_angles, timeout=30.0, tolerance=1.0):
        """等待机械臂到达目标位置
        
        Args:
            target_angles: 目标关节角度列表
            timeout: 超时时间（秒）
            tolerance: 角度容差（度）
        
        Returns:
            bool: 是否成功到达目标位置
        """
        start_time = time.time()
        check_interval = 0.1  # 100ms检查一次
        last_status_time = 0
        status_interval = 1.0  # 每秒更新一次状态
        
        while self.is_running and (time.time() - start_time) < timeout:
            try:
                current_time = time.time()
                elapsed_time = current_time - start_time
                
                # 获取当前关节角度
                current_angles = self.parent_widget.get_current_joint_angles()
                if current_angles is None:
                    self.msleep(int(check_interval * 1000))
                    continue
                
                # 检查是否所有关节都到达目标位置
                all_reached = True
                max_diff = 0.0
                for i, (current, target) in enumerate(zip(current_angles, target_angles)):
                    angle_diff = abs(current - target)
                    max_diff = max(max_diff, angle_diff)
                    if angle_diff > tolerance:
                        all_reached = False
                
                if all_reached:
                    return True
                
                # 定期发送等待状态信息
                if current_time - last_status_time >= status_interval:
                    status_msg = f"等待到位中... 最大偏差: {max_diff:.1f}° (已用时: {elapsed_time:.1f}s)"
                    self.waiting_for_position.emit(0, status_msg)  # 点序号在外层设置
                    last_status_time = current_time
                
                # 等待一段时间再检查
                self.msleep(int(check_interval * 1000))
                
            except Exception as e:
                print(f"⚠️ 检查位置时出错: {e}")
                self.msleep(int(check_interval * 1000))
                continue
        
        # 超时或被停止
        if self.is_running:
            print(f"⚠️ 等待到位超时，用时 {time.time() - start_time:.2f} 秒")
            # 输出当前位置和目标位置的差异
            try:
                current_angles = self.parent_widget.get_current_joint_angles()
                if current_angles:
                    print("当前位置与目标位置差异:")
                    for i, (current, target) in enumerate(zip(current_angles, target_angles)):
                        diff = abs(current - target)
                        print(f"  J{i+1}: 当前 {current:.1f}°, 目标 {target:.1f}°, 差异 {diff:.1f}°")
            except:
                pass
        
        return False
    
    def stop(self):
        """停止程序执行"""
        self.is_running = False

