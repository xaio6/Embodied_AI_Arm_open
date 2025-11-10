#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实机械臂内部辅助函数库
包含所有内部工具函数和全局状态管理，供embodied_func.py使用
"""

import sys
import os
import tempfile
import cv2
import numpy as np
import math
from typing import List, Optional, Dict, Any, Tuple

# 全局变量
_real_motors = None  # 真实机械臂电机字典
_motor_reducer_ratios = {}  # 电机减速比
_motor_directions = {}  # 电机方向

# 全局运动参数
_motion_params = {
    "max_speed": 100,      # 最大速度 (RPM)
    "acceleration": 50,    # 加速度 (RPM/s)
    "deceleration": 50     # 减速度 (RPM/s)
}

# 全局抓取参数
_grasp_params = {
    "yaw": 0.0,           # 抓取姿态Yaw角
    "pitch": 0.0,         # 抓取姿态Pitch角
    "roll": 180.0,        # 抓取姿态Roll角
    "use_dynamic_pose": False,  # 姿态控制模式：False=固定姿态，True=动态姿态
    "tcp_offset_x": 0.0,  # TCP修正X偏移量（毫米）
    "tcp_offset_y": 0.0,  # TCP修正Y偏移量（毫米）
    "tcp_offset_z": 0.0,  # TCP修正Z偏移量（毫米）
    "grasp_depth": 300.0  # 抓取深度（毫米）
}

# 全局夹爪参数
_claw_params = {
    "port": "COM6",           # 串口号
    "baudrate": 9600,         # 波特率
    "open_angle": 0,          # 张开角度（0-90度）
    "close_angle": 90,        # 闭合角度（0-90度）
}

# 全局夹爪控制器
_claw_controller = None

# 全局摄像头管理变量
_current_camera_frame = None
_camera_id = 0

# 全局紧急停止标志
_emergency_stop_flag = False

def _is_y_board(motors_dict=None) -> bool:
    """判断是否全为Y版驱动板。未标记版本时默认按X处理。"""
    try:
        motors = motors_dict if motors_dict is not None else _real_motors
        if not motors:
            return False
        versions = {str(getattr(m, 'drive_version', 'X')).upper() for m in motors.values()}
        return versions == {"Y"}
    except Exception:
        return False

def _set_real_motors(motors, reducer_ratios=None, directions=None):
    """
    设置真实机械臂电机
    
    Args:
        motors: 电机实例字典 {motor_id: motor_instance}
        reducer_ratios: 减速比字典 {motor_id: ratio}
        directions: 方向字典 {motor_id: direction} (1=正向, -1=反向)
    """
    global _real_motors, _motor_reducer_ratios, _motor_directions
    _real_motors = motors or {}
    _motor_reducer_ratios = reducer_ratios or {}
    _motor_directions = directions or {}
    
    if _real_motors:
        print(f"✅ 真实机械臂已连接 {len(_real_motors)} 个电机")
    else:
        print("⚠️ 真实机械臂未连接")

def _set_motion_params(max_speed=100, acceleration=50, deceleration=50):
    """
    设置真实机械臂运动参数
    
    Args:
        max_speed: 最大速度 (RPM)
        acceleration: 加速度 (RPM/s)
        deceleration: 减速度 (RPM/s)
    """
    global _motion_params
    _motion_params = {
        "max_speed": max_speed,
        "acceleration": acceleration,
        "deceleration": deceleration
    }
    print(f"⚙️ 运动参数已更新: 速度={max_speed}RPM, 加速度={acceleration}RPM/s, 减速度={deceleration}RPM/s")

def _get_motion_params():
    """
    获取当前运动参数
    
    Returns:
        dict: 运动参数字典
    """
    global _motion_params
    return _motion_params.copy()

def _set_grasp_params(**kwargs):
    """
    设置抓取参数
    
    Args:
        yaw: 抓取姿态Yaw角
        pitch: 抓取姿态Pitch角
        roll: 抓取姿态Roll角
        use_dynamic_pose: 姿态控制模式（False=固定姿态，True=动态姿态）
        tcp_offset_x: TCP修正X偏移量（毫米）
        tcp_offset_y: TCP修正Y偏移量（毫米）
        tcp_offset_z: TCP修正Z偏移量（毫米）
        grasp_depth: 抓取深度（毫米）
    """
    global _grasp_params
    for key, value in kwargs.items():
        if key in _grasp_params:
            _grasp_params[key] = value

def _get_grasp_params():
    """
    获取抓取参数
    
    Returns:
        dict: 抓取参数字典
    """
    global _grasp_params
    return _grasp_params.copy()

def _set_claw_params(**kwargs):
    """
    设置夹爪参数
    
    Args:
        port: 串口号
        baudrate: 波特率
        open_angle: 张开角度（0-90度）
        close_angle: 闭合角度（0-90度）
    """
    global _claw_params
    for key, value in kwargs.items():
        if key in _claw_params:
            _claw_params[key] = value

def _get_claw_params():
    """
    获取夹爪参数
    
    Returns:
        dict: 夹爪参数字典
    """
    global _claw_params
    return _claw_params.copy()

def _set_claw_controller(claw_controller):
    """
    设置夹爪控制器实例
    
    Args:
        claw_controller: 夹爪控制器实例或None
    """
    global _claw_controller
    _claw_controller = claw_controller
    if _claw_controller:
        print("✅ 夹爪控制器已连接")
    else:
        print("⚠️ 夹爪控制器已断开")

def _get_claw_controller():
    """
    获取夹爪控制器实例
    
    Returns:
        object: 夹爪控制器实例，未连接返回None
    """
    global _claw_controller
    return _claw_controller

def _get_actual_angle(input_angle, motor_id):
    """根据减速比和方向设置计算实际发送给电机的角度"""
    # 获取对应电机的减速比和方向
    reducer_ratio = _motor_reducer_ratios.get(motor_id, 16.0)  # 默认16:1减速比
    direction = _motor_directions.get(motor_id, 1)  # 默认正向
    
    # 用户输入的是输出端角度，需要乘以减速比得到电机端角度，再应用方向修正
    motor_angle = input_angle * reducer_ratio * direction
    
    return motor_angle

def _get_real_motors():
    """获取真实机械臂电机字典"""
    global _real_motors
    return _real_motors

def _safe_get_motor_status(motor_id: int, operation_type: str = "position") -> any:
    """
    安全地获取电机状态，统一处理CAN通信冲突
    
    Args:
        motor_id: 电机ID
        operation_type: 操作类型 ("position", "in_position", "status")
        
    Returns:
        any: 根据操作类型返回相应的值，失败返回None
    """
    global _real_motors
    
    if not _real_motors or motor_id not in _real_motors:
        return None
    
    motor = _real_motors[motor_id]
    max_retries = 3
    
    for retry in range(max_retries):
        try:
            if operation_type == "position":
                return motor.read_parameters.get_position()
            elif operation_type == "in_position":
                status = motor.read_parameters.get_motor_status()
                return status.in_position
            elif operation_type == "status":
                return motor.read_parameters.get_motor_status()
            else:
                return None
                
        except Exception as e:
            error_msg = str(e)
            
            # 🆕 特别处理功能码不匹配的情况
            if "功能码不匹配" in error_msg and "0xFF" in error_msg:
                # 如果收到0xFF，说明可能是同步运动命令的延迟响应
                if retry < max_retries - 1:
                    import time
                    # 对于0xFF冲突，使用更长的延迟
                    delay = 0.2 * (retry + 1)  # 200ms, 400ms, 600ms
                    time.sleep(delay)
                    continue
                else:
                    print(f"⚠️ 电机{motor_id} 多机同步命令冲突 ({operation_type}): 可能同步运动尚未完成")
                    return None
            elif "功能码不匹配" in error_msg:
                # 其他功能码冲突
                if retry < max_retries - 1:
                    import time
                    delay = 0.05 * (retry + 1)  # 50ms, 100ms, 150ms
                    time.sleep(delay)
                    continue
                else:
                    print(f"⚠️ 电机{motor_id} CAN通信冲突 ({operation_type}): {error_msg}")
                    return None
            else:
                # 其他类型错误
                if retry < max_retries - 1:
                    import time
                    delay = 0.02 * (retry + 1)  # 20ms, 40ms, 60ms
                    time.sleep(delay)
                    continue  
                else:
                    print(f"⚠️ 电机{motor_id} {operation_type}操作失败: {error_msg}")
                    return None
    
    return None

def _get_motor_reducer_ratios():
    """获取电机减速比字典"""
    global _motor_reducer_ratios
    return _motor_reducer_ratios

def _get_motor_directions():
    """获取电机方向字典"""
    global _motor_directions
    return _motor_directions

def _build_target_transform(position: List[float], orientation: List[float]) -> np.ndarray:
    """
    构建目标变换矩阵
    
    Args:
        position: 位置 [x, y, z] (毫米)
        orientation: 姿态 [yaw, pitch, roll] (度) - ZYX欧拉角顺序
        
    Returns:
        4x4变换矩阵
    """
    T = np.eye(4)
    
    # 设置位置 (毫米)
    T[:3, 3] = position
    
    # 设置姿态（从欧拉角转换为旋转矩阵）
    if orientation is not None and len(orientation) == 3:
        # 转换为弧度，注意参数顺序：[yaw, pitch, roll] -> [roll, pitch, yaw]
        yaw, pitch, roll = np.deg2rad(orientation)
        
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

def _calculate_movement_timeout(motor_ids: list, target_angles: list, base_timeout: float = 10.0) -> float:
    """
    根据角度变化量计算合理的超时时间
    
    Args:
        motor_ids: 电机ID列表
        target_angles: 目标角度列表
        base_timeout: 基础超时时间
        
    Returns:
        float: 计算出的超时时间
    """
    max_angle_change = 0.0
    
    # 🆕 逐个获取电机位置，避免并发冲突
    for i, motor_id in enumerate(motor_ids):
        if i < len(target_angles):
            try:
                current_pos = _get_motor_position(motor_id)
                target_angle = target_angles[i]
                angle_change = abs(target_angle - current_pos)
                max_angle_change = max(max_angle_change, angle_change)
                
                # 🆕 添加小延迟，避免CAN总线冲突
                import time
                time.sleep(0.01)
                
            except Exception as e:
                # 如果获取失败，使用一个保守的估计值
                max_angle_change = max(max_angle_change, 90.0)  # 假设最大90度变化
    
    # 根据最大角度变化量计算超时时间
    # 假设电机速度约为 30°/秒，为安全起见增加50%余量
    calculated_timeout = max_angle_change / 20.0 * 1.5  # 20°/秒，1.5倍安全系数
    
    # 最小10秒，最大30秒
    timeout = max(base_timeout, min(calculated_timeout, 30.0))
    
    # 只在超时时间较长时才显示分析信息
    if timeout > 15.0:
        print(f"📊 预计耗时: {timeout:.1f}秒 (角度变化{max_angle_change:.0f}°)")
    return timeout

def _wait_for_motors_to_position(motor_ids: list, timeout: float = 10.0, check_interval: float = 0.1) -> bool:
    """
    等待指定电机到位
    
    Args:
        motor_ids: 电机ID列表
        timeout: 超时时间 (秒)
        check_interval: 检查间隔 (秒)
        
    Returns:
        bool: 是否所有电机都到位
    """
    global _real_motors
    
    if not _real_motors:
        return False
    
    import time
    
    # 🆕 添加初始延迟，确保同步命令处理完毕再开始检测
    time.sleep(0.2)  # 200ms初始延迟
    
    start_time = time.time()
    check_count = 0
    last_progress_time = start_time
    
    # 只在超时时间较长时才显示等待信息
    if timeout > 15.0:
        print(f"⏳ 等待电机到位 (预计{timeout:.0f}秒)")
    
    while time.time() - start_time < timeout:
        all_in_position = True
        check_count += 1
        current_time = time.time()
        
        # 只在长时间运动时显示进度（每2秒一次）
        if timeout > 15.0 and current_time - last_progress_time >= 2.0:
            elapsed = current_time - start_time
            print(f"⏳ 等待中... {elapsed:.0f}s/{timeout:.0f}s")
            last_progress_time = current_time
        
        position_status = []
        # 🆕 逐个检查电机状态，避免并发冲突
        for motor_id in motor_ids:
            if motor_id in _real_motors:
                try:
                    # 使用安全的状态获取函数
                    is_in_pos = _safe_get_motor_status(motor_id, "in_position")
                    if is_in_pos is None:
                        is_in_pos = False
                        
                    if not is_in_pos:
                        all_in_position = False
                        
                    # 🆕 添加小延迟，避免CAN总线冲突
                    time.sleep(0.01)  
                        
                except Exception as e:
                    all_in_position = False
                    # 继续检查其他电机
        
        if all_in_position:
            elapsed = time.time() - start_time
            # 只在耗时较长时显示用时信息
            if elapsed > 3.0:
                print(f"✅ 电机已到位 (用时: {elapsed:.1f}秒)")
            return True
        
        time.sleep(check_interval)
    
    # 超时时，显示详细的位置信息
    print(f"⚠️ 等待超时 ({timeout:.1f}秒)")
    return False

def _get_motor_position(motor_id: int) -> float:
    """
    获取指定电机的当前位置
    
    Args:
        motor_id: 电机ID
        
    Returns:
        float: 电机当前位置（度），获取失败返回0.0
    """
    global _real_motors
    
    if not _real_motors or motor_id not in _real_motors:
        return 0.0
    
    try:
        # 🆕 使用安全的状态获取函数
        motor_position = _safe_get_motor_status(motor_id, "position")
        
        if motor_position is None:
            return 0.0
            
        # 转换为输出端位置
        reducer_ratio = _motor_reducer_ratios.get(motor_id, 16.0)
        direction = _motor_directions.get(motor_id, 1)
        
        # 反向计算：电机端位置 -> 输出端位置
        output_position = (motor_position / direction) / reducer_ratio
        
        return output_position
    except Exception as e:
        print(f"⚠️ 获取电机{motor_id}位置异常: {e}")
        return 

def _check_target_reached(motor_ids: list, target_angles: list, tolerance: float = 2.0) -> bool:
    """
    检查电机是否到达目标角度
    
    Args:
        motor_ids: 电机ID列表
        target_angles: 目标角度列表（输出端角度）
        tolerance: 允许误差（度）
        
    Returns:
        bool: 是否所有电机都到达目标位置
    """
    if len(motor_ids) != len(target_angles):
        return False
    
    for motor_id, target_angle in zip(motor_ids, target_angles):
        current_position = _get_motor_position(motor_id)
        error = abs(current_position - target_angle)
        
        if error > tolerance:
            print(f"⚠️ 电机{motor_id}: 当前位置{current_position:.2f}°, 目标{target_angle:.2f}°, 误差{error:.2f}°")
            return False
    
    return True 

def _set_current_camera_frame(frame):
    """
    设置当前摄像头帧（由GUI调用）
    
    Args:
        frame: OpenCV图像帧
    """
    global _current_camera_frame
    _current_camera_frame = frame

def _get_current_camera_frame():
    """
    获取当前摄像头帧
    
    Returns:
        numpy.ndarray: 当前帧图像，未设置返回None
    """
    global _current_camera_frame
    return _current_camera_frame

def _set_camera_id(camera_id):
    """
    设置摄像头ID（由GUI调用）
    
    Args:
        camera_id: 摄像头设备ID
    """
    global _camera_id
    _camera_id = camera_id

def _get_camera_id():
    """
    获取摄像头ID
    
    Returns:
        int: 摄像头设备ID
    """
    global _camera_id
    return _camera_id 

def _save_frame_to_temp_file(frame):
    """
    将帧保存为临时图片文件
    
    Args:
        frame: OpenCV图像帧
        
    Returns:
        str: 临时文件路径，失败返回None
    """
    try:
        # 创建临时文件
        temp_fd, temp_path = tempfile.mkstemp(suffix='.jpg', prefix='vision_analysis_')
        os.close(temp_fd)  # 关闭文件描述符，让OpenCV来写入
        
        # 保存图像
        success = cv2.imwrite(temp_path, frame)
        if success:
            return temp_path
        else:
            # 如果保存失败，删除临时文件
            if os.path.exists(temp_path):
                os.unlink(temp_path)
            return None
            
    except Exception as e:
        print(f"❌ 保存临时图片失败: {e}")
        return None


def _get_calibration_params():
    """
    获取相机标定参数
    
    Returns:
        dict: 标定参数字典，失败返回None
    """
    try:
        import json
        
        # 添加项目根目录到Python路径
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        config_path = os.path.join(project_root, "config", "calibration_parameter.json")
        
        with open(config_path, 'r', encoding='utf-8') as f:
            calibration_params = json.load(f)
        
        return calibration_params
        
    except Exception as e:
        print(f"❌ 加载标定参数失败: {e}")
        return None


def _convert_pixel_to_world_coords(pixel_x, pixel_y, calibration_params, current_pose, tcp_x=0.0, tcp_y=0.0, tcp_z=0.0):
    """
    将像素坐标转换为世界坐标系坐标
    参考vision_grasp_widget.py的convert_coordinates方法
    
    Args:
        pixel_x: 像素x坐标
        pixel_y: 像素y坐标  
        calibration_params: 标定参数字典
        current_pose: 当前机械臂末端位姿
        tcp_x: TCP修正X偏移量，毫米
        tcp_y: TCP修正Y偏移量，毫米
        tcp_z: TCP修正Z偏移量，毫米
        
    Returns:
        tuple: (世界x, 世界y, 世界z) 毫米坐标，失败返回None
    """
    try:
        # 获取单相机参数
        one_config = calibration_params.get("one", {})
        if not one_config:
            print("❌ 未找到单相机标定参数")
            return None
        
        # 获取相机内参
        camera_matrix_data = one_config.get("camera_matrix", [])
        if not camera_matrix_data:
            print("❌ 未找到相机矩阵参数")
            return None
        
        camera_matrix = np.array(camera_matrix_data, dtype=np.float64)
        
        # 使用全局抓取参数中的深度值进行计算
        global _grasp_params
        Z_mm = _grasp_params.get("grasp_depth", 300.0)  # 可配置深度，毫米
        
        # 计算相机坐标（毫米）
        fx = camera_matrix[0, 0]
        fy = camera_matrix[1, 1]
        cx = camera_matrix[0, 2]
        cy = camera_matrix[1, 2]
        
        X_mm = (pixel_x - cx) * Z_mm / fx
        Y_mm = (pixel_y - cy) * Z_mm / fy
        
        # 相机坐标（齐次，毫米单位）
        P_camera_homogeneous = np.array([X_mm, Y_mm, Z_mm, 1.0], dtype=np.float64).reshape(4, 1)
        
        # 获取手眼标定矩阵
        RT_camera2end = np.array(calibration_params.get("eyeinhand", {}).get("RT_camera2end", []), dtype=np.float64)
        if RT_camera2end.size == 0:
            print("❌ 未找到手眼标定参数")
            return None
            
        RT_camera2end = RT_camera2end.reshape(4, 4)
        RT_camera2end[0:3, 3] = RT_camera2end[0:3, 3] * 1000.0   # 转成毫米
        
        # 相机坐标 -> 末端坐标（毫米）
        P_end_homogeneous = RT_camera2end @ P_camera_homogeneous
        
        # 获取当前机械臂末端位姿
        # current_pose = _get_current_arm_pose()
        
        # 末端到基底
        RT_end2base = _pose_to_homogeneous_matrix(current_pose)
        
        # 末端坐标转基底坐标
        P_base_homogeneous = RT_end2base @ P_end_homogeneous
        
        # 坐标系转换调整 - 统一使用毫米作为单位
        x_base_mm = P_base_homogeneous[0, 0]  # 毫米单位
        y_base_mm = P_base_homogeneous[1, 0]  
        z_base_mm = -P_base_homogeneous[2, 0]   # Z轴取反
        
        # 应用TCP修正 - 在基底坐标系中应用偏移量
        tcp_corrected_x = x_base_mm + tcp_x  # 基底坐标系X轴偏移
        tcp_corrected_y = y_base_mm + tcp_y  # 基底坐标系Y轴偏移
        tcp_corrected_z = z_base_mm + tcp_z  # 基底坐标系Z轴偏移
        
        return (tcp_corrected_x, tcp_corrected_y, tcp_corrected_z)
        
    except Exception as e:
        print(f"❌ 像素坐标转换失败: {e}")
        return None


def _get_current_arm_pose():
    """
    获取当前机械臂末端位姿
    
    Returns:
        list: [x, y, z, yaw, pitch, roll] 位姿，失败返回None
    """
    global _real_motors
    if not _real_motors:
        print("❌ 机械臂未连接")
        return None
        
    try:
        # 获取当前所有关节角度
        current_joint_angles = []
        for i in range(6):
            motor_id = i + 1
            if motor_id in _real_motors:
                motor = _real_motors[motor_id]
                # 读取当前位置
                position = motor.read_parameters.get_position()
                # 考虑减速比和方向，转换为输出端角度
                ratio = _motor_reducer_ratios.get(motor_id, 1.0)
                direction = _motor_directions.get(motor_id, 1.0)
                output_position = (position * direction) / ratio
                current_joint_angles.append(output_position)
            else:
                current_joint_angles.append(0.0)
        
        # 使用正运动学计算当前末端位姿
        try:
            from core.arm_core.kinematics import RobotKinematics
            
            kinematics = RobotKinematics()
            kinematics.set_angle_offset([0, 90, 0, 0, 0, 0])
            
            # 计算正运动学
            transform_matrix = kinematics.forward_kinematics(current_joint_angles)
            
            # 从变换矩阵提取位置和姿态
            position = transform_matrix[:3, 3]  # 位置 (mm)
            rotation_matrix = transform_matrix[:3, :3]  # 旋转矩阵
            
            # 将旋转矩阵转换为欧拉角 (ZYX顺序)
            euler_angles = _rotation_matrix_to_euler(rotation_matrix)
            
            # 构建位姿 [x(mm), y(mm), z(mm), yaw(deg), pitch(deg), roll(deg)]
            current_pose = [
                position[0], position[1], position[2],  # 位置
                euler_angles[0], euler_angles[1], euler_angles[2]  # 姿态
            ]
            
            return current_pose
            
        except Exception as e:
            print(f"❌ 正运动学计算失败: {e}")
            return None
            
    except Exception as e:
        print(f"❌ 获取机械臂位姿失败: {e}")
        return None


def _pose_to_homogeneous_matrix(pose):
    """
    将位姿转换为齐次变换矩阵（统一使用毫米单位）
    
    Args:
        pose: [x, y, z, yaw, pitch, roll] 位姿
        
    Returns:
        numpy.ndarray: 4x4齐次变换矩阵
    """
    x, y, z, yaw, pitch, roll = pose
    
    # 位置保持毫米单位
    x_mm, y_mm, z_mm = x, y, z
    
    # 角度转换为弧度
    yaw_rad = np.deg2rad(yaw)
    pitch_rad = np.deg2rad(pitch)
    roll_rad = np.deg2rad(roll)
    
    # 构建旋转矩阵 (ZYX顺序)
    cos_yaw, sin_yaw = np.cos(yaw_rad), np.sin(yaw_rad)
    cos_pitch, sin_pitch = np.cos(pitch_rad), np.sin(pitch_rad)
    cos_roll, sin_roll = np.cos(roll_rad), np.sin(roll_rad)
    
    R_z = np.array([[cos_yaw, -sin_yaw, 0],
                    [sin_yaw, cos_yaw, 0],
                    [0, 0, 1]])
    
    R_y = np.array([[cos_pitch, 0, sin_pitch],
                    [0, 1, 0],
                    [-sin_pitch, 0, cos_pitch]])
    
    R_x = np.array([[1, 0, 0],
                    [0, cos_roll, -sin_roll],
                    [0, sin_roll, cos_roll]])
    
    R = R_z @ R_y @ R_x
    
    # 构建齐次变换矩阵（位置使用毫米）
    T = np.eye(4)
    T[0:3, 0:3] = R
    T[0:3, 3] = [x_mm, y_mm, z_mm]
    
    return T


def _rotation_matrix_to_euler(R):
    """
    将旋转矩阵转换为欧拉角 (ZYX顺序)
    
    Args:
        R: 3x3旋转矩阵
        
    Returns:
        list: [yaw, pitch, roll] 欧拉角（度）
    """
    # ZYX欧拉角提取
    sy = np.sqrt(R[0, 0] * R[0, 0] + R[1, 0] * R[1, 0])
    
    singular = sy < 1e-6
    
    if not singular:
        x = np.arctan2(R[2, 1], R[2, 2])  # Roll
        y = np.arctan2(-R[2, 0], sy)      # Pitch
        z = np.arctan2(R[1, 0], R[0, 0])  # Yaw
    else:
        x = np.arctan2(-R[1, 2], R[1, 1])  # Roll
        y = np.arctan2(-R[2, 0], sy)       # Pitch
        z = 0                              # Yaw
    
    # 转换为度
    return [np.rad2deg(z), np.rad2deg(y), np.rad2deg(x)]  # [yaw, pitch, roll]


def _extract_json_from_response(response: str) -> str:
    """
    从AI回复中提取JSON部分（与hierarchical_decision_system保持一致）
    
    Args:
        response: AI的原始回复
        
    Returns:
        str: 提取的JSON字符串
    """
    # 查找JSON开始和结束的位置
    start_idx = response.find('{')
    end_idx = response.rfind('}')
    
    if start_idx != -1 and end_idx != -1 and start_idx < end_idx:
        return response[start_idx:end_idx+1]
    else:
        # 如果没有找到完整的JSON，返回原始回复
        return response.strip()


def is_valid_solution(angles: List[float]) -> bool:
    """
    检查解是否有效：2轴在90到0之间
    
    Args:
        angles: 关节角度列表
        
    Returns:
        bool: 解是否有效
    """
    if len(angles) < 2:
        return False
    
    joint2_angle = angles[1]  # 第二个关节（索引1）
    
    # 检查2轴是否在90到0度范围内
    if 0.0 <= joint2_angle <= 90.0:
        print(f"✓ 有效解：关节2角度 = {joint2_angle:.2f}° (在0°-90°范围内)")
        return True
    else:
        print(f"✗ 无效解：关节2角度 = {joint2_angle:.2f}° (不在0°-90°范围内)")
        return False


def select_best_solution(solutions: List) -> Optional[List[float]]:
    """
    选择最优的逆运动学解：2轴在90到0之间，优选接近45度的解
    
    Args:
        solutions: 逆运动学解列表
        
    Returns:
        Optional[List[float]]: 最优解，如果无有效解则返回None
    """
    valid_solutions = []
    
    for solution in solutions:
        if isinstance(solution, np.ndarray):
            angles = solution.tolist()
        else:
            angles = solution
            
        if is_valid_solution(angles):
            valid_solutions.append(angles)
    
    if not valid_solutions:
        print("❌ 未找到有效的逆运动学解")
        return None
    
    # 如果有多个有效解，选择2轴最接近45度的解（中间值）
    best_solution = None
    best_score = float('inf')
    
    for solution in valid_solutions:
        # 计算2轴与45度的距离作为评分标准
        joint2_angle = solution[1]  # 第二个关节（索引1）
        score = abs(joint2_angle - 45.0)  # 距离45度的差值
        
        if score < best_score:
            best_score = score
            best_solution = solution
    
    print(f"🎯 选择最优解：关节2角度 = {best_solution[1]:.2f}° (评分: {best_score:.2f})")
    return best_solution


def set_emergency_stop_flag(flag: bool = True):
    """
    设置全局紧急停止标志
    
    Args:
        flag: 停止标志，True表示紧急停止，False表示恢复正常
    """
    global _emergency_stop_flag
    _emergency_stop_flag = flag
    if flag:
        print("🛑 全局紧急停止标志已设置")
    else:
        print("✅ 全局紧急停止标志已清除")


def is_emergency_stop_active() -> bool:
    """
    检查是否处于紧急停止状态
    
    Returns:
        bool: True表示紧急停止激活，False表示正常状态
    """
    global _emergency_stop_flag
    return _emergency_stop_flag


def check_emergency_stop():
    """
    检查紧急停止状态，如果激活则抛出异常
    
    Raises:
        Exception: 如果紧急停止激活
    """
    if is_emergency_stop_active():
        raise Exception("🛑 检测到紧急停止，终止当前操作")


def _return_to_initial_and_stop(reason: str = "操作失败") -> None:
    """
    机械臂回到初始位置并设置紧急停止标志，阻止后续任务执行
    
    Args:
        reason: 停止的原因描述
    """
    print(f"🏠 {reason}，机械臂将回到初始位置")
    
    # 临时清除紧急停止标志，允许机械臂回到初始位置
    try:
        set_emergency_stop_flag(False)
        print("🔄 临时清除紧急停止标志，允许机械臂回到安全位置")
    except Exception as clear_error:
        print(f"⚠️ 清除紧急停止标志失败: {clear_error}")
    
    # 让机械臂回到初始位置
    try:
        # 导入c_a_j函数
        from . import embodied_func
        initial_position = [0, 0, 0, 0, 90, 0]  # 初始位置（向下看的姿态）
        success = embodied_func.c_a_j(initial_position)  # 回到初始位置
        if success:
            print("✅ 机械臂已回到初始位置")
        else:
            print("⚠️ 机械臂回到初始位置失败")
    except Exception as return_error:
        print(f"❌ 机械臂回到初始位置异常: {return_error}")
    
    # 重新设置紧急停止标志，阻止后续动作执行
    try:
        set_emergency_stop_flag(True)
        print("🛑 已重新设置紧急停止标志，后续动作将不会执行")
    except Exception as flag_error:
        print(f"⚠️ 设置紧急停止标志失败: {flag_error}")


def _calculate_object_rotation_pca(frame: np.ndarray, bbox: List[int], object_desc: str) -> float:
    """
    使用PCA方法计算物体的旋转角度
    
    Args:
        frame: 摄像头图像帧
        bbox: 边界框坐标 [x1, y1, x2, y2]
        object_desc: 物体描述（用于调试信息）
        
    Returns:
        float: 物体的短边角度（度），已转换为顺时针为正的系统标准
    """
    try:
        
        # 提取bbox坐标
        x1, y1, x2, y2 = bbox
        
        # 确保坐标有效
        height, width = frame.shape[:2]
        x1 = max(0, min(x1, width))
        y1 = max(0, min(y1, height))
        x2 = max(0, min(x2, width))
        y2 = max(0, min(y2, height))
        
        print(f"📏 裁剪区域: ({x1}, {y1}) -> ({x2}, {y2})")
        
        # 步骤1: 裁剪图像到ROI区域
        roi = frame[y1:y2, x1:x2]
        if roi.size == 0:
            print("❌ ROI区域为空")
            return 0.0
        
        # 步骤2: 物体分割（二值化）
        # 转换为灰度图
        if len(roi.shape) == 3:
            roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        else:
            roi_gray = roi.copy()
        
        # 使用自适应阈值或Otsu阈值进行二值化
        try:
            # 尝试使用Otsu自动阈值
            _, binary_mask = cv2.threshold(roi_gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        except:
            # 备用方案：使用固定阈值
            _, binary_mask = cv2.threshold(roi_gray, 128, 255, cv2.THRESH_BINARY)
        
        # 形态学操作，去除噪声
        kernel = np.ones((3, 3), np.uint8)
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_CLOSE, kernel)
        binary_mask = cv2.morphologyEx(binary_mask, cv2.MORPH_OPEN, kernel)
        
        
        # 步骤3: 提取物体像素坐标
        # 找到所有白色像素点的坐标
        white_pixels = cv2.findNonZero(binary_mask)
        
        if white_pixels is None or len(white_pixels) < 10:
            print("❌ 物体像素点数量不足，使用默认角度 0°")
            return 0.0
        
        # 转换为适合PCA的格式: (N, 2)
        points = white_pixels.reshape(-1, 2).astype(np.float32)
        
        # 步骤4: 执行PCA
        try:
            # OpenCV的PCACompute函数只返回mean和eigenvectors两个值
            mean_out, eigenvectors = cv2.PCACompute(points, None)
            
            # 检查PCA结果的有效性
            if eigenvectors is None or len(eigenvectors) == 0:
                print("❌ PCA计算结果无效")
                return 0.0
            
        except Exception as pca_error:
            print(f"❌ PCA计算出错: {pca_error}")
            return 0.0
        
        # 步骤5: 计算主方向角度
        # 第一个特征向量指向主方向（长轴方向）
        main_direction = eigenvectors[0]  # 主方向向量
        
        # 🔧 修复方向一致性问题：
        # PCA返回的特征向量方向是任意的，我们需要统一方向约定
        # 规则：让向量总是指向右半平面（x >= 0），确保角度计算的一致性
        if main_direction[0] < 0:
            main_direction = -main_direction  # 翻转向量方向
            print(f"🔄 翻转向量方向: ({main_direction[0]:.3f}, {main_direction[1]:.3f})")
        
        # 计算该向量与水平轴的夹角（数学标准：逆时针为正）
        angle_rad = math.atan2(main_direction[1], main_direction[0])
        angle_deg = math.degrees(angle_rad)
        

        
        # 步骤6: 转换为短边角度
        # 短边与长轴垂直，所以短边角度 = 长轴角度 + 90°
        short_edge_angle = angle_deg + 90.0
        
        
        # 角度规范化到 [-90, 90] 范围
        while short_edge_angle > 90:
            short_edge_angle -= 180
            print(f"🔄 角度规范化: -{180}° → {short_edge_angle:.1f}°")
        while short_edge_angle < -90:
            short_edge_angle += 180
            print(f"🔄 角度规范化: +{180}° → {short_edge_angle:.1f}°")
        
        
        # 步骤7: 转换为系统标准（顺时针为正）
        final_angle = short_edge_angle
        
        print(f"✅ 最终角度: {final_angle:.1f}° (系统标准，顺时针为正)")
        
        return final_angle
        
    except Exception as e:
        print(f"❌ PCA角度计算失败: {e}")
        # 发生错误时返回默认角度
        return 0.0 