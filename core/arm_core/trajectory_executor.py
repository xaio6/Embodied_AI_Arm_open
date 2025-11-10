#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
空间轨迹执行器
负责笛卡尔轨迹和关节空间轨迹的规划、求解和速度同步计算
"""

import numpy as np
import time
from typing import List, Tuple, Optional, Dict, Any


class CartesianTrajectoryExecutor:
    """笛卡尔空间轨迹执行器"""
    
    def __init__(self, kinematics, cartesian_interpolator, motor_config_manager, ik_solver=None):
        """
        初始化轨迹执行器
        
        Args:
            kinematics: 运动学计算器
            cartesian_interpolator: 笛卡尔空间插补器
            motor_config_manager: 电机配置管理器
            ik_solver: 逆运动学解选择器（可选，用于调用外部的select_closest_solution）
        """
        self.kinematics = kinematics
        self.cartesian_interpolator = cartesian_interpolator
        self.motor_config_manager = motor_config_manager
        self.ik_solver = ik_solver
        
        # 速度平滑滤波器（减少抖动）
        self.previous_speeds = [0.0] * 6  # 上一次的速度
        self.speed_filter_alpha = 0.2  # 低通滤波系数（0-1，越小越平滑）
        
        # 角度平滑处理
        self._last_motor_angles = {}  # 每个电机的上一次角度
        
        # 轨迹执行状态
        self.trajectory_points = []
        self.current_index = 0
        self.is_executing = False
        
    def plan_cartesian_trajectory(self, start_position: np.ndarray, start_orientation: np.ndarray,
                                end_position: np.ndarray, end_orientation: np.ndarray,
                                max_linear_velocity: float = 50.0, max_angular_velocity: float = 30.0,
                                max_linear_acceleration: float = 100.0, max_angular_acceleration: float = 60.0) -> bool:
        """
        规划笛卡尔空间轨迹
        
        Args:
            start_position: 起始位置 [x, y, z] mm
            start_orientation: 起始姿态 [yaw, pitch, roll] 度
            end_position: 结束位置 [x, y, z] mm  
            end_orientation: 结束姿态 [yaw, pitch, roll] 度
            max_linear_velocity: 最大线性速度 mm/s
            max_angular_velocity: 最大角速度 deg/s
            max_linear_acceleration: 最大线性加速度 mm/s²
            max_angular_acceleration: 最大角加速度 deg/s²
            
        Returns:
            bool: 规划是否成功
        """
        try:
            # 构建路径点（保持姿态不变或线性插值）
            waypoints = [
                (start_position, start_orientation),
                (end_position, end_orientation)
            ]
            
            # 规划笛卡尔轨迹（使用用户设置的参数）
            success = self.cartesian_interpolator.plan_trajectory(
                waypoints=waypoints,
                max_linear_velocity=max_linear_velocity,
                max_angular_velocity=max_angular_velocity,
                max_linear_acceleration=max_linear_acceleration,
                max_angular_acceleration=max_angular_acceleration
            )
            
            if not success:
                print("❌ 笛卡尔轨迹规划失败")
                return False
            
            print(f"✅ 笛卡尔轨迹规划成功，总时长: {self.cartesian_interpolator.duration:.2f}秒")
            return True
            
        except Exception as e:
            print(f"❌ 笛卡尔轨迹规划异常: {e}")
            return False
    
    def generate_trajectory_points(self, current_joint_angles: List[float], 
                                 dt: float = 0.02) -> List[Dict[str, Any]]:
        """
        生成轨迹点序列
        
        Args:
            current_joint_angles: 当前关节角度
            dt: 控制周期（秒）
            
        Returns:
            List[Dict]: 轨迹点列表，每个点包含时间、关节角度和速度信息
        """
        try:
            total_time = self.cartesian_interpolator.duration
            t = 0.0
            
            # 收集所有时刻的关节角度和速度
            trajectory_points = []
            previous_joint_angles = np.array(current_joint_angles.copy())
            
            print(f"📐 开始收集笛卡尔轨迹点（带速度前馈）...")
            
            while t <= total_time:
                # 获取当前时刻的笛卡尔状态（包括速度）
                pos, orient, lin_vel, ang_vel, _, _ = self.cartesian_interpolator.get_cartesian_states(t)
                
                # 构造目标变换矩阵
                target_transform = self._pose_to_transform(pos.tolist(), orient.tolist())
                
                # 逆运动学求解
                solutions = self.kinematics.inverse_kinematics(target_transform, return_all=True)
                
                if solutions and len(solutions) > 0:
                    # 选择与上一时刻最接近的解
                    best_solution = self._select_best_ik_solution(solutions, previous_joint_angles)
                    
                    if best_solution is not None:
                        # 计算关节速度（用于速度前馈）
                        if t > 0 and len(trajectory_points) > 0:
                            # 使用数值差分计算关节速度
                            last_joints = trajectory_points[-1]['joints']
                            joint_velocities = (best_solution - last_joints) / dt
                        else:
                            joint_velocities = np.zeros(6)
                        
                        trajectory_points.append({
                            'time': t,
                            'joints': best_solution.copy(),
                            'velocities': joint_velocities  # 添加速度信息
                        })
                        previous_joint_angles = best_solution
                
                t += dt
            
            if len(trajectory_points) < 2:
                print("❌ 轨迹点不足，无法执行")
                return []
            
            print(f"✅ 收集到 {len(trajectory_points)} 个轨迹点")
            
            # 重置速度滤波器和角度历史
            self.previous_speeds = [0.0] * 6
            self._last_motor_angles.clear()
            
            self.trajectory_points = trajectory_points
            self.current_index = 0
            self.is_executing = True
            
            return trajectory_points
            
        except Exception as e:
            print(f"❌ 轨迹点生成失败: {e}")
            return []
    
    def get_next_motor_commands(self, current_output_angles: List[float], 
                              speed_setting: int) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        获取下一个控制周期的电机命令 - 纯位置跟随
        
        Args:
            current_output_angles: 当前输出端角度（用于兼容性，但不再用于计算）
            speed_setting: 速度设置（保留参数但设为最大值）
            
        Returns:
            Tuple[List[Dict], Dict]: (电机命令列表, 执行信息)
        """
        if not self.is_executing or self.current_index >= len(self.trajectory_points):
            return [], {'finished': True}
        
        try:
            # 获取当前轨迹点的目标关节角度
            point = self.trajectory_points[self.current_index]
            target_joint_angles = point['joints']
            
            # 构建电机命令数据 - 简化版本
            motor_commands = []
            
            for j in range(6):
                motor_id = j + 1
                
                # 将输出端角度转换为电机端角度（保留这个必要的转换）
                motor_angle = self._get_actual_angle(target_joint_angles[j], motor_id)
                
                # 构建最简单的"位置跟随"指令
                # 关键：速度设为很高的值，让电机驱动器全速跟随目标位置
                motor_commands.append({
                    'motor_id': motor_id,
                    'position': motor_angle,
                    'speed': 1500  # 解除驱动器的速度限制，让其全速跟随
                })
            
            # 执行信息 - 简化版本
            execution_info = {
                'finished': False,
                'progress': (self.current_index / len(self.trajectory_points)) * 100,
                'target_joint_angles': target_joint_angles.tolist(),
                'next_interval': 20  # 固定20ms控制周期，与轨迹生成时的dt一致
            }
            
            # 增加索引
            self.current_index += 1
            
            return motor_commands, execution_info
            
        except Exception as e:
            print(f"❌ 获取电机命令失败: {e}")
            self.is_executing = False
            return [], {'finished': True, 'error': str(e)}
    
    def stop_execution(self):
        """停止轨迹执行"""
        self.is_executing = False
        self.current_index = 0
        print("🛑 笛卡尔轨迹执行已停止")
    
    def reset(self):
        """重置执行器状态"""
        self.trajectory_points.clear()
        self.current_index = 0
        self.is_executing = False
        self.previous_speeds = [0.0] * 6
        self._last_motor_angles.clear()
    
    def _pose_to_transform(self, position: List[float], orientation: List[float]) -> np.ndarray:
        """将位置和欧拉角转换为4x4变换矩阵"""
        # 位置向量
        pos = np.array(position)
        
        # 欧拉角转旋转矩阵（ZYX顺序）
        yaw, pitch, roll = np.deg2rad(orientation)
        
        # 计算旋转矩阵
        cy = np.cos(yaw)
        sy = np.sin(yaw)
        cp = np.cos(pitch)
        sp = np.sin(pitch)
        cr = np.cos(roll)
        sr = np.sin(roll)
        
        R = np.array([
            [cy*cp, cy*sp*sr - sy*cr, cy*sp*cr + sy*sr],
            [sy*cp, sy*sp*sr + cy*cr, sy*sp*cr - cy*sr],
            [-sp, cp*sr, cp*cr]
        ])
        
        # 构造4x4变换矩阵
        T = np.eye(4)
        T[:3, :3] = R
        T[:3, 3] = pos
        
        return T
    
    def _select_best_ik_solution(self, solutions: List, reference_angles: np.ndarray) -> Optional[np.ndarray]:
        """选择最佳逆运动学解 - 使用select_closest_solution避免不必要的旋转"""
        if not solutions:
            return None
        
        # 如果有外部的IK解选择器，优先使用
        if self.ik_solver and hasattr(self.ik_solver, 'select_closest_solution'):
            try:
                result = self.ik_solver.select_closest_solution(solutions, reference_angles)
                if result is not None:
                    # select_closest_solution返回字典，包含'normalized'
                    if isinstance(result, dict) and 'normalized' in result:
                        return np.array(result['normalized'])
                    else:
                        return np.array(result)
            except Exception as e:
                print(f"⚠️ 外部IK解选择器失败，使用内置方法: {e}")
        
        # 内置的简化版本
        reference = np.array(reference_angles)
        best_solution = None
        min_distance = float('inf')
        
        for solution in solutions:
            solution_array = np.array(solution)
            
            # 计算关节角度差
            diff = solution_array - reference
            
            # 处理角度周期性
            for i in range(len(diff)):
                while diff[i] > 180:
                    diff[i] -= 360
                while diff[i] < -180:
                    diff[i] += 360
            
            # 计算距离
            distance = np.linalg.norm(diff)
            
            if distance < min_distance:
                min_distance = distance
                best_solution = solution_array
        
        return best_solution
    
    def _get_actual_angle(self, output_angle: float, motor_id: int) -> float:
        """根据减速比和方向设置计算实际发送给电机的角度"""
        # 获取对应电机的减速比和方向
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
        direction = self.motor_config_manager.get_motor_direction(motor_id)
        
        # 示教器中用户输入的总是输出端角度，需要乘以减速比得到电机端角度
        # 然后应用方向修正：正向=1，反向=-1
        motor_angle = output_angle * reducer_ratio * direction
        
        return motor_angle
    
    @property
    def is_finished(self) -> bool:
        """检查轨迹是否执行完成"""
        return not self.is_executing or self.current_index >= len(self.trajectory_points)
    
    @property
    def progress(self) -> float:
        """获取执行进度（0-100）"""
        if not self.trajectory_points:
            return 0.0
        return (self.current_index / len(self.trajectory_points)) * 100

#################################################################################################################
#################################################################################################################
#################################################################################################################


class JointSpaceTrajectoryExecutor:
    """关节空间轨迹执行器"""
    
    def __init__(self, joint_interpolator, motor_config_manager):
        """
        初始化关节空间轨迹执行器
        
        Args:
            joint_interpolator: 关节空间插补器
            motor_config_manager: 电机配置管理器
        """
        self.joint_interpolator = joint_interpolator
        self.motor_config_manager = motor_config_manager
        
        # 速度平滑滤波器（减少抖动）
        self.previous_speeds = [0.0] * 6  # 上一次的速度
        self.speed_filter_alpha = 0.2  # 低通滤波系数（0-1，越小越平滑）
        
        # 角度平滑处理
        self._last_motor_angles = {}  # 每个电机的上一次角度
        
        # 轨迹执行状态
        self.trajectory_points = []
        self.current_index = 0
        self.is_executing = False
    
    def plan_joint_trajectory(self, waypoints: List[np.ndarray], 
                            max_velocity: Optional[np.ndarray] = None,
                            max_acceleration: Optional[np.ndarray] = None) -> bool:
        """
        规划关节空间轨迹
        
        Args:
            waypoints: 关节角度路径点列表
            max_velocity: 最大速度限制 (deg/s)
            max_acceleration: 最大加速度限制 (deg/s²)
            
        Returns:
            bool: 规划是否成功
        """
        try:
            # 设置默认速度和加速度限制（如果没有提供）
            if max_velocity is None:
                max_velocity = np.array([30, 30, 30, 45, 45, 45])  # deg/s
            if max_acceleration is None:
                max_acceleration = np.array([60, 60, 60, 90, 90, 90])  # deg/s²
            
            # 规划关节空间轨迹
            success = self.joint_interpolator.plan_trajectory(
                waypoints=waypoints,
                max_velocity=max_velocity,
                max_acceleration=max_acceleration
            )
            
            if not success:
                print("❌ 关节空间轨迹规划失败")
                return False
            
            print(f"✅ 关节空间轨迹规划成功，总时长: {self.joint_interpolator.duration:.2f}秒")
            return True
            
        except Exception as e:
            print(f"❌ 关节空间轨迹规划异常: {e}")
            return False
    
    def generate_trajectory_points(self, dt: float = 0.02) -> List[Dict[str, Any]]:
        """
        生成关节空间轨迹点序列
        
        Args:
            dt: 控制周期（秒）
            
        Returns:
            List[Dict]: 轨迹点列表，每个点包含时间、关节角度和速度信息
        """
        try:
            total_time = self.joint_interpolator.duration
            t = 0.0
            
            # 收集所有时刻的关节角度和速度
            trajectory_points = []
            
            
            while t <= total_time:
                # 获取当前时刻的关节状态
                positions, velocities, accelerations = self.joint_interpolator.get_joint_states(t)
                
                trajectory_points.append({
                    'time': t,
                    'joints': positions.copy(),
                    'velocities': velocities.copy(),
                    'accelerations': accelerations.copy()
                })
                
                t += dt
            
            if len(trajectory_points) < 2:
                print("❌ 轨迹点不足，无法执行")
                return []
            
            
            # 重置速度滤波器和角度历史
            self.previous_speeds = [0.0] * 6
            self._last_motor_angles.clear()
            
            self.trajectory_points = trajectory_points
            self.current_index = 0
            self.is_executing = True
            
            return trajectory_points
            
        except Exception as e:
            print(f"❌ 关节轨迹点生成失败: {e}")
            return []
    

    def stop_execution(self):
        """停止轨迹执行"""
        self.is_executing = False
        self.current_index = 0
        print("🛑 关节空间轨迹执行已停止")
    
    def reset(self):
        """重置执行器状态"""
        self.trajectory_points.clear()
        self.current_index = 0
        self.is_executing = False
        self.previous_speeds = [0.0] * 6
        self._last_motor_angles.clear()
    
    def get_next_motor_commands(self, current_time: float, 
                                       speed_setting: int) -> Tuple[List[Dict], Dict[str, Any]]:
        """
        获取关节空间插补的电机命令
        
        Args:
            current_time: 当前时间（秒，用于兼容性但不再用于核心逻辑）
            speed_setting: 速度设置
            
        Returns:
            Tuple[List[Dict], Dict]: (电机命令列表, 执行信息)
        """
        # 使用与笛卡尔插补一致的完成检测机制
        if not self.is_executing or self.current_index >= len(self.trajectory_points):
            return [], {'finished': True}
        
        try:
            # 获取当前轨迹点的目标关节角度（与笛卡尔插补一致的方式）
            point = self.trajectory_points[self.current_index]
            target_joint_angles = point['joints']
            
            # 构建电机命令数据
            motor_commands = []
            
            for j in range(6):
                motor_id = j + 1
                
                # 获取目标关节角度
                target_angle = target_joint_angles[j]
                
                # 将输出端角度转换为电机端角度
                motor_angle = self._get_actual_angle(target_angle, motor_id)
                
                # 构建电机命令数据（与笛卡尔插补一致）
                motor_commands.append({
                    'motor_id': motor_id,
                    'position': motor_angle,
                    'speed': speed_setting
                })
            
            # 执行信息（与笛卡尔插补一致的格式）
            execution_info = {
                'finished': False,
                'progress': (self.current_index / len(self.trajectory_points)) * 100,
                'target_joint_angles': target_joint_angles.tolist(),
                'next_interval': 20  # 固定20ms控制周期
            }
            
            # 增加索引（关键：与笛卡尔插补一致的递增机制）
            self.current_index += 1
            
            return motor_commands, execution_info
            
        except Exception as e:
            print(f"❌ 获取关节电机命令失败: {e}")
            self.is_executing = False
            return [], {'finished': True, 'error': str(e)}
    
    def _get_actual_angle(self, output_angle: float, motor_id: int) -> float:
        """根据减速比和方向设置计算实际发送给电机的角度"""
        # 获取对应电机的减速比和方向
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
        direction = self.motor_config_manager.get_motor_direction(motor_id)
        
        # 示教器中用户输入的总是输出端角度，需要乘以减速比得到电机端角度
        # 然后应用方向修正：正向=1，反向=-1
        motor_angle = output_angle * reducer_ratio * direction
        
        return motor_angle
    

    @property
    def is_finished(self) -> bool:
        """检查轨迹是否执行完成"""
        return not self.is_executing or self.current_index >= len(self.trajectory_points)
    
    @property
    def progress(self) -> float:
        """获取执行进度（0-100）"""
        if not self.trajectory_points:
            return 0.0
        return (self.current_index / len(self.trajectory_points)) * 100
