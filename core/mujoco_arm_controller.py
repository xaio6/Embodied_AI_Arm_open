#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MuJoCo机械臂控制器
封装了机械臂的运动学计算和MuJoCo仿真控制功能，方便虚实结合操作
"""

import mujoco
import mujoco.viewer
import numpy as np
import time
import threading
from typing import List, Tuple, Optional, Union
import sys
import os

# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

from core.arm_core.kinematics import RobotKinematics


class MuJoCoArmController:
    """MuJoCo机械臂控制器类"""
    
    def __init__(self, model_path: str = 'config/urdf/mjmodel.xml', 
                 d: List[float] = None, a: List[float] = None, 
                 alpha: List[float] = None, enable_viewer: bool = True):
        """
        初始化机械臂控制器
        
        Args:
            model_path: MuJoCo模型文件路径
            d: DH参数 - 连杆偏移
            a: DH参数 - 连杆长度  
            alpha: DH参数 - 连杆扭转角
            enable_viewer: 是否启用MuJoCo查看器
        """
        
        # 初始化属性（确保析构函数不会出错）
        self.viewer = None
        self.viewer_thread = None
        self.viewer_running = False
        
        # 添加线程锁，解决多线程竞争问题
        self.data_lock = threading.Lock()
        
        # 轨迹记录相关属性
        self.trajectory_points = []  # 存储轨迹点 [(x, y, z), ...]
        self.max_trajectory_points = 1000  # 最大轨迹点数
        self.trajectory_enabled = True  # 是否启用轨迹记录
        self.trajectory_color = [1.0, 0.0, 0.0, 1.0]  # 轨迹颜色 (红色)
        
        # 初始化运动学
        self.robot = RobotKinematics()
        self.robot.set_angle_offset([0, 90, 0, 0, 0, 0])
        self.robot.set_joint_limits([(-360, 360), (-360, 360), (-360, 360), (-360, 360), (-360, 360), (-360, 360)])
        
        # 加载MuJoCo模型
        try:
            self.model = mujoco.MjModel.from_xml_path(model_path)
            self.data = mujoco.MjData(self.model)
            print(f"✓ MuJoCo模型加载成功: {model_path}")
        except Exception as e:
            raise RuntimeError(f"❌ 模型加载失败: {e}")
        
        # 当前状态
        self.current_joint_angles = [0.0] * 6  # 度数制

        
        # 启动查看器
        if enable_viewer:
            self.start_viewer()
        
    
    def add_trajectory_point(self, position: List[float]):
        """
        添加轨迹点
        
        Args:
            position: 位置 [x, y, z]
        """
        if not self.trajectory_enabled:
            return
        
        # 转换为毫米单位的位置
        trajectory_point = [position[0] / 1000.0, position[1] / 1000.0, position[2] / 1000.0]
        
        self.trajectory_points.append(trajectory_point)
        
        # 限制轨迹点数量
        if len(self.trajectory_points) > self.max_trajectory_points:
            self.trajectory_points.pop(0)
    
    def clear_trajectory(self):
        """清空轨迹"""
        self.trajectory_points = []
        print("✓ 轨迹已清空")
    
    def set_trajectory_enabled(self, enabled: bool):
        """
        设置轨迹记录是否启用
        
        Args:
            enabled: 是否启用轨迹记录
        """
        self.trajectory_enabled = enabled
        print(f"✓ 轨迹记录已{'启用' if enabled else '禁用'}")
    
    def set_trajectory_color(self, color: List[float]):
        """
        设置轨迹颜色
        
        Args:
            color: 颜色 [r, g, b, a]，取值范围 0-1
        """
        if len(color) == 4:
            self.trajectory_color = color
        else:
            raise ValueError("颜色必须包含4个值 [r, g, b, a]")
    
    def draw_trajectory(self, viewer):
        """
        在MuJoCo查看器中绘制轨迹
        
        Args:
            viewer: MuJoCo查看器实例
        """
        if len(self.trajectory_points) < 2:
            return
        
        # 绘制轨迹线段
        for i in range(len(self.trajectory_points) - 1):
            p1 = self.trajectory_points[i]
            p2 = self.trajectory_points[i + 1]
            
            # 计算线段的中点和方向
            mid_point = [(p1[j] + p2[j]) / 2 for j in range(3)]
            direction = [p2[j] - p1[j] for j in range(3)]
            length = np.linalg.norm(direction)
            
            if length > 0:
                # 归一化方向向量
                direction = np.array(direction) / length
                
                # 计算旋转矩阵，使胶囊体对齐方向
                z_axis = np.array([0, 0, 1])
                if np.abs(np.dot(direction, z_axis)) < 0.999:  # 避免gimbal lock
                    # 计算旋转轴
                    rotation_axis = np.cross(z_axis, direction)
                    rotation_axis = rotation_axis / np.linalg.norm(rotation_axis)
                    
                    # 计算旋转角度
                    cos_angle = np.dot(z_axis, direction)
                    sin_angle = np.linalg.norm(np.cross(z_axis, direction))
                    
                    # 构造旋转矩阵（Rodrigues公式）
                    K = np.array([
                        [0, -rotation_axis[2], rotation_axis[1]],
                        [rotation_axis[2], 0, -rotation_axis[0]],
                        [-rotation_axis[1], rotation_axis[0], 0]
                    ])
                    
                    rotation_matrix = np.eye(3) + sin_angle * K + (1 - cos_angle) * np.dot(K, K)
                else:
                    # 如果方向向量已经对齐z轴，使用单位矩阵
                    rotation_matrix = np.eye(3)
                
                # 准备mjv_initGeom的参数
                geom = viewer.user_scn.geoms[viewer.user_scn.ngeom]
                geom_type = mujoco.mjtGeom.mjGEOM_CAPSULE
                
                # 尺寸参数 (radius, radius, half_length)
                size = np.array([0.002, 0.002, length/2], dtype=np.float64).reshape(3, 1)
                
                # 位置参数
                pos = np.array(mid_point, dtype=np.float64).reshape(3, 1)
                
                # 旋转矩阵参数 (3x3矩阵展开成9x1向量)
                mat = rotation_matrix.flatten().astype(np.float64).reshape(9, 1)
                
                # 颜色参数
                rgba = np.array(self.trajectory_color, dtype=np.float32).reshape(4, 1)
                
                # 调用mjv_initGeom
                try:
                    mujoco.mjv_initGeom(geom, geom_type, size, pos, mat, rgba)
                    viewer.user_scn.ngeom += 1
                except Exception as e:
                    print(f"绘制轨迹时发生错误: {e}")
                    break
                
                # 防止超出几何体数量限制
                if viewer.user_scn.ngeom >= viewer.user_scn.maxgeom:
                    break
    
    def start_viewer(self):
        """启动MuJoCo查看器（在后台线程中运行）"""
        if self.viewer is not None:
            print("⚠ 查看器已经在运行")
            return
        
        def viewer_thread():
            with mujoco.viewer.launch_passive(self.model, self.data) as viewer:
                self.viewer = viewer
                self.viewer_running = True
                print("✓ MuJoCo查看器启动成功")
                
                try:
                    while self.viewer_running and viewer.is_running():
                        # 使用锁来安全地同步查看器
                        with self.data_lock:
                            # 清空用户自定义几何体
                            viewer.user_scn.ngeom = 0
                            
                            # 绘制轨迹
                            self.draw_trajectory(viewer)
                            
                            viewer.sync()
                        time.sleep(0.01)  # 100Hz刷新率
                except Exception as e:
                    print(f"查看器运行异常: {e}")
                finally:
                    self.viewer = None
                    self.viewer_running = False
                    print("MuJoCo查看器已关闭")
        
        self.viewer_thread = threading.Thread(target=viewer_thread, daemon=True)
        self.viewer_thread.start()
        
        # 等待查看器初始化完成
        retry_count = 0
        while self.viewer is None and retry_count < 50:  # 最多等待5秒
            time.sleep(0.1)
            retry_count += 1
        
        if self.viewer is None:
            raise RuntimeError("查看器启动超时")
    
    def stop_viewer(self):
        """停止MuJoCo查看器"""
        if self.viewer_running:
            self.viewer_running = False
            if self.viewer_thread:
                self.viewer_thread.join()
            print("MuJoCo查看器已停止")
    
    def set_joint_angles(self, angles: List[float], update_display: bool = True):
        """
        设置关节角度
        
        Args:
            angles: 关节角度列表（度数制，6个关节）
            update_display: 是否更新MuJoCo显示
        """
        if len(angles) != 6:
            raise ValueError("关节角度必须包含6个值")
        
        self.current_joint_angles = list(angles)
        
        # 记录末端位置轨迹
        if self.trajectory_enabled:
            position, _ = self.get_end_effector_pose()
            self.add_trajectory_point(position)
        
        if update_display:
            self._update_mujoco_display()
    
    def get_joint_angles(self) -> List[float]:
        """获取当前关节角度（度数制）"""
        return self.current_joint_angles.copy()
    
    def _update_mujoco_display(self):
        """更新MuJoCo显示（线程安全版本）"""
        # 使用锁确保线程安全
        with self.data_lock:
            # 完全重置MuJoCo状态
            mujoco.mj_resetData(self.model, self.data)
            
            # 应用角度偏转
            modified_angles = np.array(self.current_joint_angles).copy()
            modified_angles = [modified_angles[i]  for i in range(6)]
            
            # 转换为弧度制
            angles_rad = np.deg2rad(modified_angles)
            
            # 设置关节位置
            self.data.qpos[:6] = angles_rad
            self.data.ctrl[:6] = angles_rad
            
            # 确保所有速度和加速度都为零
            self.data.qvel[:] = 0
            self.data.qacc[:] = 0
            
            # 多步更新确保稳定
            for _ in range(10):
                mujoco.mj_forward(self.model, self.data)
    
    def forward_kinematics(self, angles: List[float] = None) -> np.ndarray:
        """
        计算正运动学
        
        Args:
            angles: 关节角度（度数制），如果为None则使用当前角度
            
        Returns:
            4x4变换矩阵
        """
        if angles is None:
            angles = self.current_joint_angles
        
        return self.robot.forward_kinematics(angles)
    
    def inverse_kinematics(self, target_transform: np.ndarray, 
                          return_all: bool = False) -> Union[List[float], List[List[float]]]:
        """
        计算逆运动学
        
        Args:
            target_transform: 目标4x4变换矩阵
            return_all: 是否返回所有解
            
        Returns:
            关节角度（度数制）或所有解的列表
        """
        solutions = self.robot.inverse_kinematics(target_transform, return_all=True)
        
        if not return_all and len(solutions) > 0:
            # 返回第一个有效解
            for solution in solutions:
                if self.robot.check_joint_limits(solution.tolist()):
                    return solution.tolist()
            return solutions[0].tolist()  # 如果没有有效解，返回第一个
        
        return [sol.tolist() for sol in solutions] if return_all else []
    
    def get_end_effector_pose(self, angles: List[float] = None) -> Tuple[List[float], List[float]]:
        """
        获取末端执行器位姿
        
        Args:
            angles: 关节角度（度数制），如果为None则使用当前角度
            
        Returns:
            (位置[x,y,z], 欧拉角[rx,ry,rz])，单位：mm, 度
        """
        T = self.forward_kinematics(angles)
        
        # 提取位置
        position = T[:3, 3].tolist()
        
        # 提取欧拉角（ZYX顺序）
        R = T[:3, :3]
        sy = np.sqrt(R[0,0] * R[0,0] + R[1,0] * R[1,0])
        
        if sy > 1e-6:
            x = np.arctan2(R[2,1], R[2,2])
            y = np.arctan2(-R[2,0], sy)
            z = np.arctan2(R[1,0], R[0,0])
        else:
            x = np.arctan2(-R[1,2], R[1,1])
            y = np.arctan2(-R[2,0], sy)
            z = 0
        
        euler_angles = np.rad2deg([x, y, z]).tolist()
        
        return position, euler_angles
    
    def move_to_pose(self, target_position: List[float], 
                     target_orientation: List[float] = None, 
                     update_display: bool = True) -> bool:
        """
        移动到指定位姿
        
        Args:
            target_position: 目标位置[x,y,z]，单位：mm
            target_orientation: 目标欧拉角[rx,ry,rz]，单位：度。如果为None则保持当前姿态
            update_display: 是否更新MuJoCo显示
            
        Returns:
            是否成功移动到目标位姿
        """
        if target_orientation is None:
            # 保持当前姿态，只改变位置
            _, current_orientation = self.get_end_effector_pose()
            target_orientation = current_orientation
        
        # 构造目标变换矩阵
        target_transform = self._pose_to_transform(target_position, target_orientation)
        
        # 计算逆运动学
        try:
            solutions = self.inverse_kinematics(target_transform, return_all=True)
            
            # 选择最优解（在关节限制范围内且与当前位置最接近）
            best_solution = None
            min_distance = float('inf')
            
            current_angles = np.array(self.current_joint_angles)
            
            for solution in solutions:
                if self.robot.check_joint_limits(solution):
                    distance = np.linalg.norm(np.array(solution) - current_angles)
                    if distance < min_distance:
                        min_distance = distance
                        best_solution = solution
            
            if best_solution is not None:
                self.set_joint_angles(best_solution, update_display)
                return True
            else:
                print("❌ 没有找到有效的逆运动学解")
                return False
                
        except Exception as e:
            print(f"❌ 逆运动学计算失败: {e}")
            return False
    
    def _pose_to_transform(self, position: List[float], 
                          euler_angles: List[float]) -> np.ndarray:
        """将位置和欧拉角转换为4x4变换矩阵"""
        T = np.eye(4)
        T[:3, 3] = position
        
        # 欧拉角转旋转矩阵（ZYX顺序）
        rx, ry, rz = np.deg2rad(euler_angles)
        
        # 绕X轴旋转
        Rx = np.array([[1, 0, 0],
                       [0, np.cos(rx), -np.sin(rx)],
                       [0, np.sin(rx), np.cos(rx)]])
        
        # 绕Y轴旋转
        Ry = np.array([[np.cos(ry), 0, np.sin(ry)],
                       [0, 1, 0],
                       [-np.sin(ry), 0, np.cos(ry)]])
        
        # 绕Z轴旋转
        Rz = np.array([[np.cos(rz), -np.sin(rz), 0],
                       [np.sin(rz), np.cos(rz), 0],
                       [0, 0, 1]])
        
        # 组合旋转矩阵（ZYX顺序）
        T[:3, :3] = Rz @ Ry @ Rx
        
        return T
    
    def smooth_move_to_angles(self, target_angles: List[float], 
                             duration: float = 2.0, steps: int = 50):
        """
        平滑移动到目标关节角度（线程安全版本）
        
        Args:
            target_angles: 目标关节角度（度数制）
            duration: 移动持续时间（秒）
            steps: 插值步数
        """
        if len(target_angles) != 6:
            raise ValueError("目标角度必须包含6个值")
        
        start_angles = np.array(self.current_joint_angles)
        end_angles = np.array(target_angles)
        
        # 生成插值轨迹
        for i in range(steps + 1):
            alpha = i / steps
            # 使用平滑插值函数（S曲线）
            smooth_alpha = 3 * alpha**2 - 2 * alpha**3
            current_angles = start_angles + smooth_alpha * (end_angles - start_angles)
            
            self.set_joint_angles(current_angles.tolist())
            time.sleep(duration / steps)
    
    def get_dh_parameters(self) -> dict:
        """获取DH参数"""
        return self.robot.get_dh_parameters()
    
    def check_joint_limits(self, angles: List[float]) -> bool:
        """检查关节角度是否在限制范围内"""
        return self.robot.check_joint_limits(angles)
    
    def print_status(self):
        """打印当前状态"""
        print("\n=== 机械臂当前状态 ===")
        print(f"关节角度（度）: {[f'{angle:.1f}' for angle in self.current_joint_angles]}")
        
        position, orientation = self.get_end_effector_pose()
        print(f"末端位置（mm）: [{position[0]:.1f}, {position[1]:.1f}, {position[2]:.1f}]")
        print(f"末端姿态（度）: [{orientation[0]:.1f}, {orientation[1]:.1f}, {orientation[2]:.1f}]")
        print(f"查看器状态: {'运行中' if self.viewer_running else '已停止'}")
        print(f"轨迹记录: {'启用' if self.trajectory_enabled else '禁用'}")
        print(f"轨迹点数: {len(self.trajectory_points)}")
    
    def __del__(self):
        """析构函数，确保资源清理"""
        self.stop_viewer()

