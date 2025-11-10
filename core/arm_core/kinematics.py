#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
6自由度机械臂运动学算法
提供正运动学和逆运动学求解
"""

import numpy as np
from typing import List, Tuple, Optional, Union

class RobotKinematics:
    """
    6自由度机械臂运动学类
    支持正运动学和逆运动学计算
    """
    
    def __init__(self, 
                 d: Optional[List[float]] = None,
                 a: Optional[List[float]] = None, 
                 alpha: Optional[List[float]] = None,
                 joint_limits: Optional[List[Tuple[float, float]]] = None,
                 angle_unit: str = 'deg',
                 joint_offsets: Optional[List[float]] = None):
        """
        初始化机械臂运动学参数
        
        Args:
            d: 连杆偏移参数 [d1, d2, d3, d4, d5, d6] (mm)
            a: 连杆长度参数 [a1, a2, a3, a4, a5, a6] (mm)
            alpha: 连杆扭角参数 [α1, α2, α3, α4, α5, α6] (弧度)
            joint_limits: 关节限制 [(min1,max1), (min2,max2), ...] (度)
            angle_unit: 角度单位 'deg' 或 'rad'
            joint_offsets: 关节角度偏转 [offset1, offset2, ...] (与angle_unit单位一致)
            enable_forward_offset: 是否启用正运动学输入偏转
            enable_inverse_offset: 是否启用逆运动学输出偏转
        """
        # 默认DH参数 (基于原MATLAB代码)
        self.d = d if d is not None else [160.4, 0.0, 0.0, 220, 0.0, 62.4]
        self.a = a if a is not None else [0.0, 0.0, 200.6, 23.5, 0.0, 0.0]
        self.alpha = alpha if alpha is not None else [0, -np.pi/2, 0, -np.pi/2, np.pi/2, -np.pi/2]
        
        # 验证参数长度
        if len(self.d) != 6 or len(self.a) != 6 or len(self.alpha) != 6:
            raise ValueError("DH参数长度必须为6")
        
        # 关节限制 (度)
        self.joint_limits = joint_limits if joint_limits is not None else [
            (-180, 180), (-180, 180), (-180, 180), 
            (-180, 180), (-180, 180), (-180, 180)
        ]
        
        # 角度单位
        self.angle_unit = angle_unit.lower()
        if self.angle_unit not in ['deg', 'rad']:
            raise ValueError("角度单位必须为 'deg' 或 'rad'")
            
        # 关节偏转参数
        self.joint_offsets = joint_offsets if joint_offsets is not None else [0.0] * 6
        if len(self.joint_offsets) != 6:
            raise ValueError("关节偏转参数长度必须为6")
            
        # 偏转控制开关
        self.enable_offset = False
        self.angle_offset = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        
        # 精度设置
        self.tolerance = 1e-6
        
        
    def set_angle_offset(self, offset: List[float]):
        """
        设置关节角度偏转
        
        Args:
            offset: 6个关节的角度偏转值，单位与初始化时的angle_unit一致
        """
        if len(offset) != 6:
            raise ValueError("角度偏转数量必须为6")
        self.angle_offset = offset
        self.enable_offset = True
        
        
        
    def set_dh_parameters(self, d: List[float], a: List[float], alpha: List[float]):
        """
        设置DH参数
        
        Args:
            d: 连杆偏移参数 (mm)
            a: 连杆长度参数 (mm) 
            alpha: 连杆扭角参数 (弧度)
        """
        if len(d) != 6 or len(a) != 6 or len(alpha) != 6:
            raise ValueError("DH参数长度必须为6")
            
        self.d = d
        self.a = a
        self.alpha = alpha
        
    def get_dh_parameters(self) -> dict:
        """
        获取当前DH参数
        
        Returns:
            包含DH参数的字典
        """
        return {
            'd': self.d.copy(),
            'a': self.a.copy(), 
            'alpha': self.alpha.copy(),
        }
        
    def set_joint_limits(self, limits: List[Tuple[float, float]]):
        """
        设置关节限制
        
        Args:
            limits: 关节限制列表 [(min1,max1), (min2,max2), ...]
        """
        if len(limits) != 6:
            raise ValueError("关节限制数量必须为6")
        self.joint_limits = limits
        
    def check_joint_limits(self, angles: List[float]) -> bool:
        """
        检查关节角度是否在限制范围内
        
        Args:
            angles: 关节角度 (度)
            
        Returns:
            是否在限制范围内
        """
        for i, angle in enumerate(angles):
            min_limit, max_limit = self.joint_limits[i]
            if angle < min_limit or angle > max_limit:
                return False
        return True
        
    def _convert_angles(self, angles: List[float], to_unit: str) -> List[float]:
        """
        角度单位转换
        
        Args:
            angles: 角度列表
            to_unit: 目标单位 'deg' 或 'rad'
            
        Returns:
            转换后的角度列表
        """
        if self.angle_unit == to_unit:
            return angles
        elif self.angle_unit == 'deg' and to_unit == 'rad':
            return [np.deg2rad(ang) for ang in angles]
        elif self.angle_unit == 'rad' and to_unit == 'deg':
            return [np.rad2deg(ang) for ang in angles]
        else:
            raise ValueError("无效的角度单位")
    
    def trans_cal(self, alpha_ii: float, a_ii: float, d_i: float, theta_i: float) -> np.ndarray:
        """
        计算变换矩阵T_{i-1,i}
        
        Args:
            alpha_ii: 连杆扭角 α_{i-1} (度)
            a_ii: 连杆长度 a_{i-1} (mm)
            d_i: 连杆偏移 d_i (mm)
            theta_i: 关节角度 θ_i (度)
            
        Returns:
            4x4变换矩阵
        """
        theta_rad = np.deg2rad(theta_i)
        alpha_rad = np.deg2rad(alpha_ii)
        
        cos_theta = np.cos(theta_rad)
        sin_theta = np.sin(theta_rad)
        cos_alpha = np.cos(alpha_rad)
        sin_alpha = np.sin(alpha_rad)
        
        T = np.array([
            [cos_theta, -sin_theta, 0, a_ii],
            [sin_theta * cos_alpha, cos_theta * cos_alpha, -sin_alpha, -sin_alpha * d_i],
            [sin_theta * sin_alpha, cos_theta * sin_alpha, cos_alpha, cos_alpha * d_i],
            [0, 0, 0, 1]
        ])
        
        return T
    
    def forward_kinematics(self, theta: Union[List[float], np.ndarray]) -> np.ndarray:
        """
        正运动学求解
        
        Args:
            theta: 关节角度数组 (根据初始化时的angle_unit确定单位)
            
        Returns:
            4x4末端执行器位姿矩阵
        """
        # 转换为列表
        if isinstance(theta, np.ndarray):
            theta = theta.tolist()
            
        if len(theta) != 6:
            raise ValueError("关节角度数量必须为6")

        if self.enable_offset:
            theta = [theta[i] - self.angle_offset[i] for i in range(6)]
            
        # 转换为度制进行计算
        theta_deg = self._convert_angles(theta, 'deg')
        
        # 检查关节限制
        if not self.check_joint_limits(theta_deg):
            print("警告: 关节角度超出限制范围")
        
        # 计算正运动学
        trans_matrix = np.eye(4)
        alpha_deg = [np.rad2deg(ang) for ang in self.alpha]
        
        for i in range(6):
            T = self.trans_cal(alpha_deg[i], self.a[i], self.d[i], theta_deg[i])
            trans_matrix = trans_matrix @ T
            
        return trans_matrix
    
    def get_end_effector_pose(self, theta: Union[List[float], np.ndarray]) -> dict:
        """
        获取末端执行器位姿信息
        
        Args:
            theta: 关节角度数组
            
        Returns:
            包含位置、姿态矩阵等信息的字典
        """
        T = self.forward_kinematics(theta)

        
        position = T[:3, 3]
        rotation_matrix = T[:3, :3]
        
        # 计算欧拉角
        sy = np.sqrt(rotation_matrix[0, 0] ** 2 + rotation_matrix[1, 0] ** 2)
        singular = sy < 1e-6
        
        if not singular:
            rx = np.arctan2(rotation_matrix[2, 1], rotation_matrix[2, 2])
            ry = np.arctan2(-rotation_matrix[2, 0], sy)
            rz = np.arctan2(rotation_matrix[1, 0], rotation_matrix[0, 0])
        else:
            rx = np.arctan2(-rotation_matrix[1, 2], rotation_matrix[1, 1])
            ry = np.arctan2(-rotation_matrix[2, 0], sy)
            rz = 0  
            
        euler_angles = [rz, ry, rx] # 对应 [Yaw, Pitch, Roll] ZYX 欧拉角顺序
        if self.angle_unit == 'deg':
            euler_angles = [np.rad2deg(ang) for ang in euler_angles]
        
        return {
            'transformation_matrix': T,
            'position': position,
            'rotation_matrix': rotation_matrix,
            'euler_angles': euler_angles,
            'angle_unit': self.angle_unit
        }
    
    def _theta2_calculate(self, theta1: float, T_ni: np.ndarray) -> Tuple[float, float]:
        """计算theta2的两个解"""
        theta1_rad = np.deg2rad(theta1)
        
        r1_3 = T_ni[0, 2]; PX_X = T_ni[0, 3]
        r2_3 = T_ni[1, 2]; PY_Y = T_ni[1, 3]
        r3_3 = T_ni[2, 2]; PZ_Z = T_ni[2, 3]
        
        d1, d4, d6 = self.d[0], self.d[3], self.d[5]
        a2, a3, a4 = self.a[1], self.a[2], self.a[3]
        
        A2 = (PX_X - d6*r1_3)*np.cos(theta1_rad) + (PY_Y - d6*r2_3)*np.sin(theta1_rad) - a2
        B2 = d1 + d6*r3_3 - PZ_Z
        C2 = 2*A2*a3
        D2 = 2*B2*a3
        E2 = A2**2 + B2**2 + a3**2 - a4**2 - d4**2
        F2 = np.sqrt(C2**2 + D2**2)
        
        theta2_1 = (-np.arctan2(C2, D2) + np.arctan2(E2/F2, np.sqrt(1 - (E2/F2)**2))) * 180/np.pi
        theta2_2 = (-np.arctan2(C2, D2) + np.arctan2(E2/F2, -np.sqrt(1 - (E2/F2)**2))) * 180/np.pi
        
        return theta2_1, theta2_2
    
    def _theta3_calculate(self, theta1: float, theta2: float, T_ni: np.ndarray) -> float:
        """计算theta3"""
        theta1_rad = np.deg2rad(theta1)
        theta2_rad = np.deg2rad(theta2)
        
        r1_3 = T_ni[0, 2]; PX_X = T_ni[0, 3]
        r2_3 = T_ni[1, 2]; PY_Y = T_ni[1, 3]  
        r3_3 = T_ni[2, 2]; PZ_Z = T_ni[2, 3]
        
        d1, d4, d6 = self.d[0], self.d[3], self.d[5]
        a2, a3, a4 = self.a[1], self.a[2], self.a[3]
        
        A3 = (d1*np.sin(theta2_rad) - a2*np.cos(theta2_rad) - PZ_Z*np.sin(theta2_rad) + 
              d6*r3_3*np.sin(theta2_rad) + PX_X*np.cos(theta1_rad)*np.cos(theta2_rad) +
              PY_Y*np.cos(theta2_rad)*np.sin(theta1_rad) - d6*r1_3*np.cos(theta1_rad)*np.cos(theta2_rad) -
              d6*r2_3*np.cos(theta2_rad)*np.sin(theta1_rad) - a3)
        
        B3 = (d1*np.cos(theta2_rad) - PZ_Z*np.cos(theta2_rad) + a2*np.sin(theta2_rad) + 
              d6*r3_3*np.cos(theta2_rad) - PX_X*np.cos(theta1_rad)*np.sin(theta2_rad) -
              PY_Y*np.sin(theta1_rad)*np.sin(theta2_rad) + d6*r2_3*np.sin(theta1_rad)*np.sin(theta2_rad) +
              d6*r1_3*np.cos(theta1_rad)*np.sin(theta2_rad))
        
        C3 = (a4*B3 - d4*A3) / (a4**2 + d4**2)
        D3 = (a4*A3 + d4*B3) / (a4**2 + d4**2)
        
        theta3 = np.arctan2(C3, D3) * 180/np.pi
        
        return theta3
    
    def _theta4_calculate(self, theta1: float, theta2: float, theta3: float, T_ni: np.ndarray) -> Tuple[float, float]:
        """计算theta4的两个解"""
        theta1_rad = np.deg2rad(theta1)
        theta2_rad = np.deg2rad(theta2)
        theta3_rad = np.deg2rad(theta3)
        
        r1_3 = T_ni[0, 2]
        r2_3 = T_ni[1, 2]
        r3_3 = T_ni[2, 2]
        
        A4 = (r3_3*np.cos(theta2_rad)*np.sin(theta3_rad) + r3_3*np.cos(theta3_rad)*np.sin(theta2_rad) -
              r1_3*np.cos(theta1_rad)*np.cos(theta2_rad)*np.cos(theta3_rad) -
              r2_3*np.cos(theta2_rad)*np.cos(theta3_rad)*np.sin(theta1_rad) +
              r1_3*np.cos(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad) +
              r2_3*np.sin(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad))
        
        B4 = r2_3*np.cos(theta1_rad) - r1_3*np.sin(theta1_rad)
        
        theta4_1 = (np.arctan2(0, 1) + np.arctan2(B4, A4)) * 180/np.pi
        theta4_2 = (np.arctan2(0, -1) + np.arctan2(B4, A4)) * 180/np.pi
        
        return theta4_1, theta4_2
    
    def _theta5_calculate(self, theta1: float, theta2: float, theta3: float, theta4: float, T_ni: np.ndarray) -> float:
        """计算theta5"""
        theta1_rad = np.deg2rad(theta1)
        theta2_rad = np.deg2rad(theta2)
        theta3_rad = np.deg2rad(theta3)
        theta4_rad = np.deg2rad(theta4)
        
        r1_3 = T_ni[0, 2]
        r2_3 = T_ni[1, 2]
        r3_3 = T_ni[2, 2]
        
        A5 = (r1_3*np.sin(theta1_rad)*np.sin(theta4_rad) - r2_3*np.cos(theta1_rad)*np.sin(theta4_rad) -
              r3_3*np.cos(theta2_rad)*np.cos(theta4_rad)*np.sin(theta3_rad) -
              r3_3*np.cos(theta3_rad)*np.cos(theta4_rad)*np.sin(theta2_rad) +
              r1_3*np.cos(theta1_rad)*np.cos(theta2_rad)*np.cos(theta3_rad)*np.cos(theta4_rad) +
              r2_3*np.cos(theta2_rad)*np.cos(theta3_rad)*np.cos(theta4_rad)*np.sin(theta1_rad) -
              r1_3*np.cos(theta1_rad)*np.cos(theta4_rad)*np.sin(theta2_rad)*np.sin(theta3_rad) -
              r2_3*np.cos(theta4_rad)*np.sin(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad))
        
        B5 = (r3_3*np.sin(theta2_rad)*np.sin(theta3_rad) - r3_3*np.cos(theta2_rad)*np.cos(theta3_rad) -
              r1_3*np.cos(theta1_rad)*np.cos(theta2_rad)*np.sin(theta3_rad) -
              r1_3*np.cos(theta1_rad)*np.cos(theta3_rad)*np.sin(theta2_rad) -
              r2_3*np.cos(theta2_rad)*np.sin(theta1_rad)*np.sin(theta3_rad) -
              r2_3*np.cos(theta3_rad)*np.sin(theta1_rad)*np.sin(theta2_rad))
        
        theta5 = np.arctan2(-A5, B5) * 180/np.pi
        
        return theta5
    
    def _theta6_calculate(self, theta1: float, theta2: float, theta3: float, theta4: float, T_ni: np.ndarray) -> float:
        """计算theta6"""
        theta1_rad = np.deg2rad(theta1)
        theta2_rad = np.deg2rad(theta2)
        theta3_rad = np.deg2rad(theta3)
        theta4_rad = np.deg2rad(theta4)
        
        r1_1 = T_ni[0, 0]; r1_2 = T_ni[0, 1]
        r2_1 = T_ni[1, 0]; r2_2 = T_ni[1, 1]
        r3_1 = T_ni[2, 0]; r3_2 = T_ni[2, 1]
        
        A6 = (r2_1*np.cos(theta1_rad)*np.cos(theta4_rad) - r1_1*np.cos(theta4_rad)*np.sin(theta1_rad) -
              r3_1*np.cos(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad) -
              r3_1*np.cos(theta3_rad)*np.sin(theta2_rad)*np.sin(theta4_rad) +
              r1_1*np.cos(theta1_rad)*np.cos(theta2_rad)*np.cos(theta3_rad)*np.sin(theta4_rad) +
              r2_1*np.cos(theta2_rad)*np.cos(theta3_rad)*np.sin(theta1_rad)*np.sin(theta4_rad) -
              r1_1*np.cos(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad) -
              r2_1*np.sin(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad))
        
        B6 = (r2_2*np.cos(theta1_rad)*np.cos(theta4_rad) - r1_2*np.cos(theta4_rad)*np.sin(theta1_rad) -
              r3_2*np.cos(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad) -
              r3_2*np.cos(theta3_rad)*np.sin(theta2_rad)*np.sin(theta4_rad) +
              r1_2*np.cos(theta1_rad)*np.cos(theta2_rad)*np.cos(theta3_rad)*np.sin(theta4_rad) +
              r2_2*np.cos(theta2_rad)*np.cos(theta3_rad)*np.sin(theta1_rad)*np.sin(theta4_rad) -
              r1_2*np.cos(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad) -
              r2_2*np.sin(theta1_rad)*np.sin(theta2_rad)*np.sin(theta3_rad)*np.sin(theta4_rad))
        
        theta6 = np.arctan2(-A6, -B6) * 180/np.pi
        
        return theta6
    
    def inverse_kinematics(self, T_target: np.ndarray, return_all: bool = True) -> Union[np.ndarray, List[np.ndarray]]:
        """
        逆运动学求解
        
        Args:
            T_target: 目标位姿矩阵 (4x4)
            return_all: 是否返回所有解，否则返回第一个有效解
            
        Returns:
            关节角度解 (度制，除非初始化时指定为弧度)
        """
        if T_target.shape != (4, 4):
            raise ValueError("目标位姿矩阵必须为4x4")
        
        T_ni = T_target
        d6 = self.d[5]
        
        # 提取位姿矩阵元素
        r1_1 = T_ni[0, 0]; r1_2 = T_ni[0, 1]; r1_3 = T_ni[0, 2]; PX_X = T_ni[0, 3]
        r2_1 = T_ni[1, 0]; r2_2 = T_ni[1, 1]; r2_3 = T_ni[1, 2]; PY_Y = T_ni[1, 3]
        r3_1 = T_ni[2, 0]; r3_2 = T_ni[2, 1]; r3_3 = T_ni[2, 2]; PZ_Z = T_ni[2, 3]
        
        # theta1的解
        theta1_1 = (np.arctan2(0, 1) - np.arctan2(d6*r2_3 - PY_Y, PX_X - d6*r1_3)) * 180/np.pi
        theta1_2 = (-np.arctan2(0, -1) - np.arctan2(d6*r2_3 - PY_Y, PX_X - d6*r1_3)) * 180/np.pi
        
        solutions = []
        
        try:
            # 对于每个theta1解，计算其他关节角度
            for theta1 in [theta1_1, theta1_2]:
                # theta2的解
                theta2_1, theta2_2 = self._theta2_calculate(theta1, T_ni)
                
                for theta2 in [theta2_1, theta2_2]:
                    # theta3的解
                    theta3 = self._theta3_calculate(theta1, theta2, T_ni)
                    
                    # theta4的解
                    theta4_1, theta4_2 = self._theta4_calculate(theta1, theta2, theta3, T_ni)
                    
                    for theta4 in [theta4_1, theta4_2]:
                        # theta5的解
                        theta5 = self._theta5_calculate(theta1, theta2, theta3, theta4, T_ni)
                        
                        # theta6的解
                        theta6 = self._theta6_calculate(theta1, theta2, theta3, theta4, T_ni)
                        
                        solution = [theta1, theta2, theta3, theta4, theta5, theta6]
                        
                        # 处理角度偏移 - 逆运动学需要减去偏移
                        if self.enable_offset:
                            solution = [solution[i] + self.angle_offset[i] for i in range(6)]
                        
                        # 转换角度单位
                        if self.angle_unit == 'rad':
                            solution = [np.deg2rad(ang) for ang in solution]
                        
                        solutions.append(np.array(solution))
                        
        except Exception as e:
            print(f"逆运动学求解出错: {e}")
            
        if not solutions:
            raise ValueError("无法找到逆运动学解")
            
        if return_all:
            return solutions
        else:
            return solutions[0]
    
##################################################################################################################################### 
#####################################################################################################################################        
#####################################################################################################################################

    def normalize_angle(self, angle: float) -> float:
        """
        将角度规范化到 [-180°, +180°] 范围内
        
        Args:
            angle: 输入角度（度）
            
        Returns:
            规范化后的角度
        """
        # 将角度限制在 [-180, +180] 范围内
        while angle > 180:
            angle -= 360
        while angle <= -180:
            angle += 360
        return angle
    
    def normalize_joint_angles(self, joint_angles: List[float]) -> List[float]:
        """
        规范化所有关节角度
        
        Args:
            joint_angles: 关节角度列表
            
        Returns:
            规范化后的关节角度列表
        """
        if joint_angles is None:
            return None
            
        normalized = []
        for angle in joint_angles:
            normalized_angle = self.normalize_angle(angle)
            normalized.append(normalized_angle)
        
        return normalized
    
    def select_closest_solution(self, solutions: Union[np.ndarray, List[np.ndarray]], 
                              current_angles: List[float]) -> dict:
        """
        从多个逆运动学解中选择与当前关节角度最接近的解
        
        Args:
            solutions: 逆运动学解列表或单个解
            current_angles: 当前关节角度列表
            
        Returns:
            包含'original'和'normalized'解的字典
        """
        if solutions is None:
            return None
            
        # 如果只有一个解，直接返回
        if not isinstance(solutions, list):
            normalized_solution = self.normalize_joint_angles(solutions)
            return {
                'original': solutions,           # 原始解用于显示
                'normalized': normalized_solution # 规范化解用于控制
            }
            
        if len(solutions) == 0:
            return None
            
        if len(solutions) == 1:
            normalized_solution = self.normalize_joint_angles(solutions[0])
            return {
                'original': solutions[0],        # 原始解用于显示
                'normalized': normalized_solution # 规范化解用于控制
            }
        
        # 计算每个解与当前角度的距离
        min_distance = float('inf')
        best_solution = solutions[0]
        best_original_solution = solutions[0]  # 保存原始解用于显示
        
        for i, solution in enumerate(solutions):
            if solution is None:
                continue
            
            # 规范化解的角度用于距离计算
            normalized_solution = self.normalize_joint_angles(solution)
            
            # 计算所有关节角度差的平方和
            distance = 0
            for j in range(min(len(normalized_solution), len(current_angles))):
                # 考虑角度的周期性（-180°和+180°是相邻的）
                angle_diff = abs(normalized_solution[j] - current_angles[j])
                # 处理跨越±180°边界的情况
                if angle_diff > 180:
                    angle_diff = 360 - angle_diff
                distance += angle_diff ** 2
            
            if distance < min_distance:
                min_distance = distance
                best_solution = normalized_solution  # 规范化解用于电机控制
                best_original_solution = solution    # 原始解用于界面显示
        
        print(f"🎯 逆运动学解选择: 从{len(solutions)}个解中选择最接近解，距离={min_distance:.2f}")
        print(f"   原始解（显示用）: {[f'{a:.1f}°' for a in best_original_solution]}")
        print(f"   规范化解（控制用）: {[f'{a:.1f}°' for a in best_solution]}")
        
        # 返回包含两个解的字典
        return {
            'original': best_original_solution,  # 用于界面显示
            'normalized': best_solution          # 用于电机控制
        }
    