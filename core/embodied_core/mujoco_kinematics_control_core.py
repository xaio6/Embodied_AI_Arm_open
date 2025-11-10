#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
6轴机械臂运动学控制核心类
支持关节角控制、末端位置控制和MuJoCo仿真驱动
"""

import sys
import os
# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, project_root)

import numpy as np
import time
from typing import List, Optional

# 导入已有的控制器、运动学类和插补器
from core.mujoco_arm_controller import MuJoCoArmController
from core.arm_core.kinematics import RobotKinematics
from core.arm_core.interpolation import JointSpaceInterpolator


class MujocoKinematicsControlCore:
    """
    6轴机械臂运动学控制核心类
    - 封装了关节角控制、末端位置控制、MuJoCo仿真驱动等功能
    """
    
    def __init__(self, model_path: str = "config/urdf/mjmodel.xml"):
        """
        初始化运动学控制核心
        
        Args:
            model_path: MuJoCo模型文件路径
        """
        # 目标参数（待执行的参数）
        self.target_joints = None
        self.target_gripper = 0
        
        # 运动参数
        self.max_velocity = np.array([30, 30, 30, 45, 45, 45])      # 度/秒
        self.max_acceleration = np.array([60, 60, 60, 90, 90, 90])  # 度/秒²
        self.control_period = 0.05  # 50ms控制周期
        
        # 控制模式
        self.control_mode = None  # "joints"
        
        # 初始化MuJoCo机械臂控制器
        self.controller = MuJoCoArmController(model_path=model_path, enable_viewer=True)
        
        # 初始化运动学计算器
        self.kinematics = RobotKinematics()
        self.kinematics.set_angle_offset([0, 90, 0, 0, 0, 0])
        
        # 初始化关节空间插补器
        self.joint_interpolator = JointSpaceInterpolator()
    
    def set_joint_angles(self, joints: List[float]) -> bool:
        """
        设置关节角度（仅保存参数，不立即执行）
        
        Args:
            joints: 6个关节的角度值 (度)
            
        Returns:
            bool: 参数设置是否成功
        """
        if len(joints) != 6:
            print(f"❌ 关节角度数量错误: 期望6个，得到{len(joints)}个")
            return False
        
        # 保存目标参数
        self.target_joints = joints
        self.control_mode = "joints"
        
        return True
    
    def set_end_effector_position(self, position: List[float], orientation: Optional[List[float]] = None) -> bool:
        """
        设置末端执行器位置（通过逆运动学转换为关节角度保存）
        
        Args:
            position: 目标位置 [x, y, z] (毫米)
            orientation: 目标姿态 [rx, ry, rz] (度)，None则保持当前姿态
            
        Returns:
            bool: 参数设置是否成功
        """
        if len(position) != 3:
            print(f"❌ 位置参数错误: 期望3个值，得到{len(position)}个")
            return False
        
        try:
            # 如果没有提供姿态，获取当前姿态
            if orientation is None:
                _, current_orientation = self.controller.get_end_effector_pose()
                orientation = current_orientation
            
            # 构建目标变换矩阵
            target_transform = self._build_target_transform(position, orientation)
            
            # 使用本项目的运动学类进行逆运动学求解
            solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
            
            if solutions:
                # 选择第一个有效解
                target_joints = None
                for solution in solutions:
                    solution_deg = solution.tolist()
                    if self.kinematics.check_joint_limits(solution_deg):
                        target_joints = solution_deg
                        break
                
                if target_joints is None:
                    target_joints = solutions[0].tolist()  # 如果没有有效解，使用第一个
                
                # 保存计算出的关节角度
                self.target_joints = target_joints
                self.control_mode = "joints"  # 统一使用关节角度控制
                
                return True
            else:
                print("❌ 逆运动学求解失败")
                return False
                
        except Exception as e:
            print(f"❌ 逆运动学计算失败: {e}")
            return False
    
    def set_motion_parameters(self, max_velocity: List[float] = None, max_acceleration: List[float] = None):
        """
        设置运动参数
        
        Args:
            max_velocity: 最大速度 [v1, v2, v3, v4, v5, v6] (度/秒)
            max_acceleration: 最大加速度 [a1, a2, a3, a4, a5, a6] (度/秒²)
        """
        if max_velocity is not None:
            if len(max_velocity) == 6:
                self.max_velocity = np.array(max_velocity)
            else:
                print(f"❌ 速度参数错误: 期望6个值，得到{len(max_velocity)}个")
        
        if max_acceleration is not None:
            if len(max_acceleration) == 6:
                self.max_acceleration = np.array(max_acceleration)
            else:
                print(f"❌ 加速度参数错误: 期望6个值，得到{len(max_acceleration)}个")
    
    def set_gripper_state(self, state: float) -> bool:
        """
        设置夹爪状态（仅保存参数，不立即执行）
        
        Args:
            state: 夹爪状态 (0-100, 0=完全张开, 100=完全闭合)
            
        Returns:
            bool: 参数设置是否成功
        """
        if not (0 <= state <= 100):
            print(f"❌ 夹爪状态超出范围: {state} (范围: 0-100)")
            return False
        
        self.target_gripper = state
        return True
    
    def drive_to_target(self, smooth: bool = True, duration: float = None) -> bool:
        """
        驱动机械臂运动到目标位置（执行函数）
        
        Args:
            smooth: 是否使用平滑插补运动
            duration: 运动持续时间（秒），None则自动计算
            
        Returns:
            bool: 执行是否成功
        """
        if self.control_mode != "joints" or self.target_joints is None:
            print("❌ 没有设置目标关节角度，无法执行运动")
            return False
        
        # 获取当前关节角度作为起点
        current_joints = self.controller.get_joint_angles()
        target_joints = self.target_joints
        
        if smooth:
            # 使用插补运动
            return self._execute_smooth_motion(current_joints, target_joints, duration)
        else:
            # 直接运动（原有方式）
            self.controller.set_joint_angles(target_joints, update_display=True)
            return True
    
    def _execute_smooth_motion(self, start_joints: List[float], target_joints: List[float], duration: float = None) -> bool:
        """
        执行平滑插补运动
        
        Args:
            start_joints: 起始关节角度
            target_joints: 目标关节角度
            duration: 运动持续时间，None则自动计算
            
        Returns:
            bool: 执行是否成功
        """
        try:
            # 准备路径点
            waypoints = [np.array(start_joints), np.array(target_joints)]
            
            # 规划插补轨迹
            success = self.joint_interpolator.plan_trajectory(
                waypoints=waypoints,
                max_velocity=self.max_velocity,
                max_acceleration=self.max_acceleration
            )
            
            if not success:
                # 轨迹规划失败，使用直接运动
                self.controller.set_joint_angles(target_joints, update_display=True)
                return True
            
            total_time = self.joint_interpolator.duration
            if duration is not None and duration > 0:
                # 如果指定了持续时间，重新规划
                scale_factor = duration / total_time
                scaled_max_velocity = self.max_velocity / scale_factor
                scaled_max_acceleration = self.max_acceleration / (scale_factor * scale_factor)
                
                success = self.joint_interpolator.plan_trajectory(
                    waypoints=waypoints,
                    max_velocity=scaled_max_velocity,
                    max_acceleration=scaled_max_acceleration
                )
                
                if success:
                    total_time = self.joint_interpolator.duration
            
            # 执行轨迹
            t = 0.0
            
            while t <= total_time:
                # 获取当前时刻的关节状态
                positions, velocities, accelerations = self.joint_interpolator.get_joint_states(t)
                
                # 发送关节位置到机械臂
                self.controller.set_joint_angles(positions.tolist())
                
                time.sleep(self.control_period)
                t += self.control_period
            
            return True
            
        except Exception as e:
            print(f"❌ 平滑运动执行失败: {e}")
            return False

    def _build_target_transform(self, position: List[float], orientation: List[float]) -> np.ndarray:
        """
        构建目标变换矩阵
        
        Args:
            position: 位置 [x, y, z] (毫米)
            orientation: 姿态 [roll, pitch, yaw] (度) - ZYX欧拉角顺序
            
        Returns:
            4x4变换矩阵
        """
        T = np.eye(4)
        
        # 设置位置 (毫米)
        T[:3, 3] = position
        
        # 设置姿态（从欧拉角转换为旋转矩阵）
        if orientation is not None and len(orientation) == 3:
            # 转换为弧度 (ZYX顺序: Roll, Pitch, Yaw)
            roll, pitch, yaw = np.deg2rad(orientation)
            
            # 构建旋转矩阵 (ZYX顺序)
            Rx = np.array([
                [1, 0, 0],
                [0, np.cos(roll), -np.sin(roll)],
                [0, np.sin(roll), np.cos(roll)]
            ])
            
            Ry = np.array([
                [np.cos(pitch), 0, np.sin(pitch)],
                [0, 1, 0],
                [-np.sin(pitch), 0, np.cos(pitch)]
            ])
            
            Rz = np.array([
                [np.cos(yaw), -np.sin(yaw), 0],
                [np.sin(yaw), np.cos(yaw), 0],
                [0, 0, 1]
            ])
            
            # 组合旋转矩阵 (ZYX顺序: 先Z轴，再Y轴，最后X轴)
            R = Rz @ Ry @ Rx
            T[:3, :3] = R
        
        return T


# 使用示例
if __name__ == "__main__":
    # 创建控制器实例
    controller = MujocoKinematicsControlCore()
    
    # 设置运动参数（可选）
    controller.set_motion_parameters(
        max_velocity=[20, 20, 20, 30, 30, 30],
        max_acceleration=[40, 40, 40, 60, 60, 60]
    )
    
    # 关节角度控制示例
    controller.set_joint_angles([0, 0, -45, 0, 15, 0])
    controller.drive_to_target(smooth=True)
    
    time.sleep(1)
    
    # 指定运动时间
    controller.set_joint_angles([45, -30, 60, -45, 30, -15])
    controller.drive_to_target(smooth=True, duration=3.0)
    
    time.sleep(1)
    
    # 末端位置控制示例
    controller.set_end_effector_position([200, 100, 300])
    controller.drive_to_target(smooth=True)
    
    # 明确关闭控制器，避免线程问题
    time.sleep(1)  # 等待运动完成
    if hasattr(controller, 'controller') and controller.controller:
        controller.controller.stop_viewer()
    
    print("✅ 演示完成")
