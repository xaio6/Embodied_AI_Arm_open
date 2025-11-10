#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
真实机械臂功能函数库
提供标准化的真实机械臂控制接口，供LLM任务规划使用

本文件只包含给LLM使用的核心功能函数：
- c_a_j: 控制机械臂关节角度运动
- c_a_p: 控制机械臂末端位置运动 
- e_p_a: 执行预设的动作
- v_s_a: 视觉分析与语音播报功能
- v_r_o: 对指定物体进行抓取
- c_c_g: 控制夹爪

所有内部辅助函数已移至 embodied_internal.py
"""

import sys
import os
import json
import time
import threading
# 添加项目根目录到Python路径
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

import numpy as np
from typing import List, Optional, Tuple, Dict, Any

# 导入内部辅助函数
from . import embodied_internal
from AI_SDK import AISDK
from .prompt import generate_multimodal_vision_prompt, generate_object_detection_prompt
try:
    # 引入命令构建器以便Y板多电机命令拼装
    from Control_SDK.Control_Core import ZDTCommandBuilder
except Exception:
    ZDTCommandBuilder = None

# 公开内部函数供外部调用（保持向后兼容）
_set_real_motors = embodied_internal._set_real_motors
_set_motion_params = embodied_internal._set_motion_params
_get_motion_params = embodied_internal._get_motion_params
_set_grasp_params = embodied_internal._set_grasp_params
_get_grasp_params = embodied_internal._get_grasp_params
_set_claw_params = embodied_internal._set_claw_params
_get_claw_params = embodied_internal._get_claw_params
_set_claw_controller = embodied_internal._set_claw_controller
_get_claw_controller = embodied_internal._get_claw_controller
_wait_for_motors_to_position = embodied_internal._wait_for_motors_to_position
_get_motor_position = embodied_internal._get_motor_position
_calculate_movement_timeout = embodied_internal._calculate_movement_timeout
_is_y_board = embodied_internal._is_y_board
_extract_json_from_response = embodied_internal._extract_json_from_response
is_valid_solution = embodied_internal.is_valid_solution
select_best_solution = embodied_internal.select_best_solution
set_emergency_stop_flag = embodied_internal.set_emergency_stop_flag
is_emergency_stop_active = embodied_internal.is_emergency_stop_active
check_emergency_stop = embodied_internal.check_emergency_stop
_get_current_arm_pose = embodied_internal._get_current_arm_pose
_return_to_initial_and_stop = embodied_internal._return_to_initial_and_stop

def c_a_j(j_a: List[float], du: float = None) -> bool:
    """
    控制机械臂关节角度运动 (Control Arm Joints)
    
    Args:
        j_a: 6个关节的目标角度值，单位度 [J1, J2, J3, J4, J5, J6]
        du: 运动持续时间，单位秒，None则自动计算最优时间
        
    Returns:
        bool: 运动执行是否成功
    """
    # 检查紧急停止状态
    try:
        check_emergency_stop()
    except Exception as e:
        print(f"🛑 {e}")
        return False
        
    joint_angles = j_a
    duration = du
    
    real_motors = embodied_internal._get_real_motors()
    if not real_motors:
        print("❌ 未连接真实机械臂，无法执行关节控制")
        return False

    try:
        print(f"🎯 关节控制: {joint_angles}")
        
        # 直接发送位置命令（不使用同步标志）
        success_count = 0
        active_motor_ids = []  # 记录参与运动的电机ID
        
        # 获取用户设置的运动参数
        motion_params = embodied_internal._get_motion_params()
        max_speed = motion_params["max_speed"]
        acceleration = motion_params["acceleration"]
        deceleration = motion_params["deceleration"]
        
        # 如果指定了持续时间，调整速度参数
        if duration is not None and duration > 0:
            # 根据持续时间适当调整速度参数（保持比例）
            if duration > 3.0:  # 慢速运动
                max_speed = int(max_speed * 0.6)      # 降低到60%
                acceleration = int(acceleration * 0.6)
                deceleration = int(deceleration * 0.6)
            elif duration < 1.5:  # 快速运动
                max_speed = int(max_speed * 1.5)      # 提高到150%
                acceleration = int(acceleration * 1.6)
                deceleration = int(deceleration * 1.6)
        
        if _is_y_board(real_motors) and ZDTCommandBuilder is not None:
            # Y板：一次性多电机命令下发
            commands = []
            try:
                for i, target_angle in enumerate(joint_angles):
                    motor_id = i + 1
                    if motor_id in real_motors:
                        active_motor_ids.append(motor_id)
                        actual_angle = embodied_internal._get_actual_angle(target_angle, motor_id)
                        func_body = ZDTCommandBuilder.position_mode_trapezoid(
                            position=actual_angle,
                            max_speed=max_speed,
                            acceleration=acceleration,
                            deceleration=deceleration,
                            is_absolute=True,
                            multi_sync=False
                        )
                        # 子命令：地址+功能体
                        sub_cmd = ZDTCommandBuilder.build_single_command_bytes(motor_id, func_body)
                        commands.append(sub_cmd)
                        success_count += 1
                
                if success_count == 0:
                    print("❌ 没有电机成功设置运动参数")
                    return False
                
                # 使用任一电机实例发多电机命令
                first_motor = list(real_motors.values())[0]
                # 不等待确认，避免设备Response设置导致超时
                first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                print(f"⚡ Y板多电机命令一次性下发 {success_count} 条")
            except Exception as y_err:
                print(f"⚠️ Y板多电机命令下发失败，回退单发: {y_err}")
                # 回退为逐台非同步发送
                success_count = 0
                active_motor_ids.clear()
                for i, target_angle in enumerate(joint_angles):
                    motor_id = i + 1
                    if motor_id in real_motors:
                        motor = real_motors[motor_id]
                        active_motor_ids.append(motor_id)
                        actual_angle = embodied_internal._get_actual_angle(target_angle, motor_id)
                        try:
                            motor.control_actions.move_to_position_trapezoid(
                                position=actual_angle,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=True,
                                multi_sync=False
                            )
                            success_count += 1
                        except Exception as e:
                            print(f"❌ 电机 {motor_id} 设置失败: {e}")
                            continue
        else:
            # X板或无构建器：多机同步标志 + 广播同步
            for i, target_angle in enumerate(joint_angles):
                motor_id = i + 1  # 电机ID从1开始
                if motor_id in real_motors:
                    motor = real_motors[motor_id]
                    active_motor_ids.append(motor_id)
                    actual_angle = embodied_internal._get_actual_angle(target_angle, motor_id)
                    try:
                        motor.control_actions.move_to_position_trapezoid(
                            position=actual_angle,
                            max_speed=max_speed,
                            acceleration=acceleration,
                            deceleration=deceleration,
                            is_absolute=True,
                            multi_sync=True   # 使用同步模式
                        )
                        success_count += 1
                        print(f"✅(已设置) 电机{motor_id}: {target_angle:.1f}° → {actual_angle:.1f}°")
                    except Exception as e:
                        print(f"❌ 电机 {motor_id} 设置失败: {e}")
                        continue
            # 广播同步启动
            if success_count > 0:
                try:
                    first_motor = list(real_motors.values())[0]
                    interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                    broadcast_motor = first_motor.__class__(
                        motor_id=0,
                        interface_type=first_motor.interface_type,
                        shared_interface=True,
                        **interface_kwargs
                    )
                    broadcast_motor.can_interface = first_motor.can_interface
                    broadcast_motor.control_actions.sync_motion()
                    print("⚡ X板广播同步启动")
                except Exception as sync_err:
                    print(f"⚠️ 同步运动命令发送失败: {sync_err}")
        
        if success_count == 0:
            print("❌ 没有电机成功设置运动参数")
            return False
        
        print(f"⚡ 已启动 {success_count} 个电机的运动")
        
        # 计算超时时间
        base_timeout = (duration + 3.0) if duration else 15.0  # 增加基础超时时间
        calculated_timeout = embodied_internal._calculate_movement_timeout(
            active_motor_ids, 
            joint_angles[:len(active_motor_ids)], 
            base_timeout
        )
        
        # 添加短暂延迟，确保运动命令处理完成
        time.sleep(0.1)  # 100ms延迟，让运动命令完全处理
        
        # 等待所有电机到位
        if embodied_internal._wait_for_motors_to_position(active_motor_ids, timeout=calculated_timeout, check_interval=0.1):
            print(f"✅ 动作完成")
            return True
        else:
            print(f"⚠️ 超时检查各电机状态:")
            all_close_enough = True
            tolerance = 3.0  # 3度误差容忍
            
            for motor_id in active_motor_ids:
                current_pos = embodied_internal._get_motor_position(motor_id)
                target_angle = joint_angles[motor_id - 1]
                error = abs(current_pos - target_angle)
                
                if error <= tolerance:
                    continue  # 不打印成功的电机信息，减少日志
                else:
                    print(f"❌ 电机{motor_id}: 误差{error:.1f}°")
                    all_close_enough = False
            
            if all_close_enough:
                print(f"✅ 动作完成 (容忍误差内)")
                return True
            else:
                print(f"❌ 部分电机未到位")
                return False
        
    except Exception as e:
        print(f"❌ 关节控制失败: {e}")
        return False

def c_a_p(pos: List[float], ori: Optional[List[float]] = None, 
          du: float = None) -> bool:
    """
    控制机械臂末端位置运动，自动进行逆运动学计算 (Control Arm Position)
    
    Args:
        pos: 末端执行器目标位置，单位毫米 [x, y, z]
        ori: 末端执行器目标姿态，单位度 [yaw, pitch, roll]，None则保持当前姿态
        du: 运动持续时间，单位秒，None则自动计算最优时间
        
    Returns:
        bool: 运动执行是否成功
    """
    # 检查紧急停止状态
    try:
        check_emergency_stop()
    except Exception as e:
        print(f"🛑 {e}")
        return False
        
    position = pos
    orientation = ori
    duration = du
    
    real_motors = embodied_internal._get_real_motors()
    if not real_motors:
        print("❌ 未连接真实机械臂，无法执行位置控制")
        return False
    
    try:
        print(f"🎯 真实机械臂末端位置控制: {position}, 姿态: {orientation}")
        
        # 导入运动学计算模块
        from core.arm_core.kinematics import RobotKinematics
        
        # 初始化运动学计算器
        kinematics = RobotKinematics()
        kinematics.set_angle_offset([0, 90, 0, 0, 0, 0])
        
        # 构建目标变换矩阵
        target_transform = embodied_internal._build_target_transform(position, orientation)
        
        # 进行逆运动学计算
        solutions = kinematics.inverse_kinematics(target_transform, return_all=True)
        
        if not solutions:
            print("❌ 逆运动学求解失败")
            return False
        
        # 使用新的解筛选逻辑，与v_g_o函数保持一致
        if isinstance(solutions, list) and len(solutions) > 0:
            # 多个解的情况 - 选择最优解
            target_joints = select_best_solution(solutions)
            if target_joints is None:
                print("❌ 无合适的逆运动学解（2轴不在0°-90°范围内）")
                return False
        elif isinstance(solutions, np.ndarray):
            # 单个解的情况 - 验证解的有效性
            candidate_angles = solutions.tolist()
            if is_valid_solution(candidate_angles):
                target_joints = candidate_angles
            else:
                print("❌ 逆运动学解不满足约束条件（2轴不在0°-90°范围内）")
                return False
        else:
            print("❌ 逆运动学计算返回格式异常")
            return False
        
        print(f"🎯 关节角度: {[f'{angle:.2f}°' for angle in target_joints]}")
        
        # 使用关节控制函数执行运动
        return c_a_j(target_joints, duration)
            
    except Exception as e:
        print(f"❌ 真实机械臂位置控制失败: {e}")
        return False
    
def e_p_a(a_n: str, sp: str = "normal") -> bool:
    """
    执行预设的动作 (Execute Preset Action)
    
    Args:
        a_n: 动作名称，如"点头"、"起床"、"摇头"等
        sp: 执行速度，"slow"/"normal"/"fast"
        
    Returns:
        bool: 动作执行是否成功
    """
    # 检查紧急停止状态
    try:
        check_emergency_stop()
    except Exception as e:
        print(f"🛑 {e}")
        return False
        
    action_name = a_n
    speed = sp
    
    real_motors = embodied_internal._get_real_motors()
    if not real_motors:
        print("❌ 未连接真实机械臂，无法执行预设动作")
        return False
    
    try:
        print(f"🎭 真实机械臂执行预设动作: {action_name} (速度: {speed})")
        
        # 获取JSON文件路径
        current_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))  # 项目根目录
        json_path = os.path.join(current_dir, "config", "embodied_config", "preset_actions.json")
        
        # 读取JSON文件
        if not os.path.exists(json_path):
            print(f"❌ 预设动作文件不存在: {json_path}")
            return False
            
        with open(json_path, 'r', encoding='utf-8') as f:
            preset_actions = json.load(f)
        
        # 检查动作是否存在
        if action_name not in preset_actions:
            print(f"❌ 未知的预设动作: {action_name}")
            available_actions = list(preset_actions.keys())
            print(f"可用动作: {available_actions}")
            return False
        
        # 获取动作参数
        action_params = preset_actions[action_name]
        joints = action_params["joints"]
        duration = action_params["duration"]
        
        # 根据速度调整持续时间
        if speed == "slow":
            duration *= 1.5
        elif speed == "fast":
            duration *= 0.7
        
        # 检查joints是否为多个关节角度序列（二维数组）
        if isinstance(joints[0], list):
            # 多个关节角度序列，需要逐个执行
            print(f"📋 复合动作参数: {len(joints)}个子动作, 总持续时间={duration:.1f}秒")
            
            # 计算每个子动作的持续时间
            sub_duration = duration / len(joints)
            
            success_count = 0
            for i, joint_sequence in enumerate(joints):
                # 在每个子动作执行前检查紧急停止状态
                try:
                    check_emergency_stop()
                except Exception as e:
                    print(f"🛑 {e} - 复合动作中断")
                    return False
                    
                print(f"🎯 执行子动作 {i+1}/{len(joints)}: {joint_sequence}")
                
                # 执行当前关节角度序列
                if c_a_j(joint_sequence, sub_duration):
                    success_count += 1
                    print(f"✅ 子动作 {i+1} 完成")
                else:
                    print(f"❌ 子动作 {i+1} 失败")
                    # 继续执行后续动作，不要因为一个子动作失败就停止
                
                # 如果不是最后一个动作，添加短暂间隔确保动作连贯
                # if i < len(joints) - 1:
                #     time.sleep(0.1)  # 100ms间隔
            
            # 如果至少有一半的子动作成功，认为整体动作成功
            success_rate = success_count / len(joints)
            if success_rate >= 0.5:
                print(f"✅ 复合动作完成 (成功率: {success_rate:.1%})")
                return True
            else:
                print(f"❌ 复合动作失败 (成功率: {success_rate:.1%})")
                return False
                
        else:
            # 单个关节角度序列，直接执行
            print(f"📋 动作参数: 关节角度={joints}, 持续时间={duration:.1f}秒")
            return c_a_j(joints, duration)
        
    except json.JSONDecodeError as e:
        print(f"❌ JSON文件解析错误: {e}")
        return False
    except FileNotFoundError:
        print(f"❌ 预设动作文件未找到: {json_path}")
        return False
    except Exception as e:
        print(f"❌ 真实机械臂预设动作执行失败: {e}")
        return False

def v_s_a(pr: str = "请描述你看到的画面", vo: str = "longxiaochun") -> bool:
    """
    视觉分析与语音播报功能 (Vision and Speak Action)
    获取当前摄像头画面，进行AI视觉分析，并通过语音播报结果
    
    Args:
        pr: 分析提示词，用户的问题"
        vo: 语音音色，默认"longxiaochun"
        
    Returns:
        bool: 分析和播报是否成功
    """
    prompt = pr
    voice = vo
    temp_image_path = None
    
    try:
        # 直接从embodied_internal获取当前摄像头画面
        current_frame = embodied_internal._get_current_camera_frame()
        if current_frame is None:
            print("❌ 无法获取摄像头画面，请确保摄像头已启动")
            return False
        
        # 保存当前帧为临时图片文件
        temp_image_path = embodied_internal._save_frame_to_temp_file(current_frame)
        if not temp_image_path:
            print("❌ 保存临时图片失败")
            return False
        
        # 初始化AI SDK并进行多模态分析
        try:

            
            sdk = AISDK()
            
            # 使用拟人化的视觉分析prompt，将用户问题作为参数传入
            enhanced_prompt = generate_multimodal_vision_prompt(prompt)
            
            print(f"🧠 开始AI视觉分析")
            print(f"👤 用户问题: {prompt}")
            
            # 调用智能多模态对话进行分析
            result = sdk.smart_multimodal_chat(
                prompt=enhanced_prompt,
                image_path=temp_image_path,
                multimodal_model="qwen-vl-max",
                tts_model="cosyvoice-v1",
                stream_output=True,
                realtime_tts=True,
                temperature=0.7,
                voice=voice
            )
            
            # 检查结果
            if result.get('success', True):
                answer = result.get('answer', '无法分析画面内容')
                print(f"✅ 视觉分析完成")
                print(f"🔊 AI回答: {answer[:100]}...")  # 只显示前100个字符
                
                # 检查TTS结果
                tts_result = result.get('tts_result', {})
                if tts_result.get('success', True):
                    print(f"🔊 语音播报完成")
                else:
                    print(f"⚠️ 语音播报失败: {tts_result.get('error', '未知错误')}")
                
                return True
            else:
                error_msg = result.get('error', '未知错误')
                print(f"❌ 视觉分析失败: {error_msg}")
                return False
                
        except ImportError as e:
            print(f"❌ AI SDK导入失败: {e}")
            return False
        except Exception as e:
            print(f"❌ AI分析过程异常: {type(e).__name__}: {e}")
            import traceback
            print(f"详细错误信息:\n{traceback.format_exc()}")
            return False
            
    except Exception as e:
        print(f"❌ 视觉分析主程序异常: {type(e).__name__}: {e}")
        import traceback
        print(f"详细错误信息:\n{traceback.format_exc()}")
        return False
    finally:
        # 清理临时文件
        try:
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
        except Exception as cleanup_error:
            print(f"⚠️ 清理临时文件失败: {cleanup_error}")


def v_r_o(obj: str) -> bool:
    """
    视觉识别物体 (Vision Recognition Object)
    通过视觉识别找到指定物体，使用PCA计算物体旋转角度，
    并且机械臂TCP（夹爪）以最佳姿态去到物体上方
    物体抓取/松开需要配合c_c_g进行！
    
    Args:
        obj: 要抓取的物体描述，如"红色的球"、"蓝色杯子"等
        
    Returns:
        bool: 视觉抓取是否成功
        
    Note:
        - 自动使用AI检测物体位置
        - 基于PCA计算物体最佳抓取角度（短边方向）
        - 动态调整机械臂Yaw角以适应物体朝向
    """
    # 检查紧急停止状态
    try:
        check_emergency_stop()
    except Exception as e:
        print(f"🛑 {e}")
        return False
        
    object_desc = obj
    
    # 从全局参数获取抓取设置
    grasp_params = embodied_internal._get_grasp_params()
    tcp_offset_x = grasp_params["tcp_offset_x"]
    tcp_offset_y = grasp_params["tcp_offset_y"] 
    tcp_offset_z = grasp_params["tcp_offset_z"]
    # 初始使用固定姿态参数，后续会根据检测结果更新
    orientation = [grasp_params["yaw"], grasp_params["pitch"], grasp_params["roll"]]
    
    real_motors = embodied_internal._get_real_motors()
    if not real_motors:
        print("❌ 未连接真实机械臂，无法执行视觉抓取")
        _return_to_initial_and_stop("未连接真实机械臂")
        return False
    
    temp_image_path = None
    
    try:
        print(f"🎯 视觉抓取物体: {object_desc}")
        print(f"🔧 TCP修正: ({tcp_offset_x:.1f}, {tcp_offset_y:.1f}, {tcp_offset_z:.1f}) mm")
        print(f"🎭 抓取姿态: ({orientation[0]:.1f}, {orientation[1]:.1f}, {orientation[2]:.1f})°")
        
        # 1. 获取当前摄像头画面
        print("📷 获取摄像头画面...")
        current_frame = embodied_internal._get_current_camera_frame()
        if current_frame is None:
            print("❌ 无法获取摄像头画面，请确保摄像头已启动")
            _return_to_initial_and_stop("无法获取摄像头画面")
            return False
        
        # 2. 获取拍照时的机械臂姿态（必须在观察动作之前
        current_pose = _get_current_arm_pose()

        # 3. 保存临时图片文件用于AI分析
        temp_image_path = embodied_internal._save_frame_to_temp_file(current_frame)
        if not temp_image_path:
            print("❌ 保存临时图片失败")
            _return_to_initial_and_stop("保存临时图片失败")
            return False
        
        # 4. 使用AI进行物体检测 - 同时启动观察动作
        print(f"🤖 AI检测物体: {object_desc}")
        
        # 定义观察动作序列
        observation_actions = [
            [0, -30, 30, 0, 60, 0],
            [0, -30, 30, 0, 60, 30],
            [0, -30, 30, 0, 60, -30],
            [0, -30, 30, 0, 60, 0]
        ]
        
        # 观察动作控制变量
        observation_thread = None
        observation_stop_flag = threading.Event()
        observation_completed = threading.Event()
        
        def observation_worker():
            """观察动作工作线程"""
            try:
                for i, action in enumerate(observation_actions):
                    # 检查是否需要停止
                    if observation_stop_flag.is_set():
                        return
                    
                    # 检查紧急停止状态
                    try:
                        check_emergency_stop()
                    except Exception as e:
                        return
                    
                    c_a_j(action)  
                    
                    
                    # 添加短暂间隔，避免命令冲突
                    if not observation_stop_flag.is_set():
                        import time
                        time.sleep(0.2)
                
                observation_completed.set()
                print("✅ 观察动作序列完成")
                
            except Exception as e:
                print(f"❌ 观察动作线程异常: {e}")
        
        # 启动观察动作线程
        try:
            observation_thread = threading.Thread(target=observation_worker, daemon=True)
            observation_thread.start()
        except Exception as e:
            print(f"⚠️ 启动观察动作线程失败: {e}")
        
        try:
            
            
            sdk = AISDK()
            # 生成物体检测prompt
            detection_prompt = generate_object_detection_prompt(object_desc)
            
            # 调用多模态分析进行物体检测 (参考simple_redball_test.py的调用方式)
            result = sdk.multimodal(
                provider="alibaba",
                mode="image",
                prompt=detection_prompt,
                image_path=temp_image_path
            )
            
            # AI检测完成，立即停止观察动作
            try:
                if observation_thread and observation_thread.is_alive():
                    observation_stop_flag.set()
                    observation_thread.join(timeout=1.0)
            except Exception as e:
                print(f"⚠️ 停止观察动作时出错: {e}")
            
            if not result.get('success', False):
                print(f"❌ AI物体检测失败: {result}")
                _return_to_initial_and_stop("AI物体检测失败")
                return False
            
            # 4. 解析检测结果 (参考simple_redball_test.py的解析方式)
            try:
                # 提取AI返回的内容
                ai_content = result['response']['choices'][0]['message']['content']
                
                # 尝试解析JSON格式的检测结果
                try:
                    import json
                    
                    # 使用JSON提取方法
                    json_content = _extract_json_from_response(ai_content)
                    print(f"🔧 提取的JSON内容: {json_content}")
                    
                    # 解析JSON
                    detection_data = json.loads(json_content)
                    bbox = detection_data.get('bbox', [])
                    label = detection_data.get('label', '')
                    
                    if not bbox or bbox == [None, None, None, None]:
                        print(f"❌ 未检测到目标物体: {object_desc}")
                        _return_to_initial_and_stop("未检测到目标物体")
                        return False
                    
                    # 计算物体中心像素坐标
                    x1, y1, x2, y2 = bbox
                    pixel_x = int((x1 + x2) / 2)
                    pixel_y = int((y1 + y2) / 2)
                    
                    print(f"✅ 检测到 {label}，中心位置: ({pixel_x}, {pixel_y})")
                    
                    # 使用PCA计算物体旋转角度
                    rotation_angle = embodied_internal._calculate_object_rotation_pca(
                        current_frame, bbox, object_desc
                    )
                    
                    print(f"🔄 物体旋转角度: {rotation_angle:.1f}°")
                    
                    # 根据姿态控制模式决定是否使用检测到的角度
                    grasp_params = embodied_internal._get_grasp_params()
                    use_dynamic_pose = grasp_params.get("use_dynamic_pose", False)
                    
                    if use_dynamic_pose:
                        # 动态模式：使用检测到的旋转角度作为Yaw角
                        orientation[0] = rotation_angle  # 更新Yaw角
                        print(f"🎯 动态姿态模式: 使用检测角度 Yaw={orientation[0]:.1f}°, Pitch={orientation[1]:.1f}°, Roll={orientation[2]:.1f}°")
                    else:
                        # 固定模式：保持原有的固定姿态参数
                        print(f"🔒 固定姿态模式: 使用设定角度 Yaw={orientation[0]:.1f}°, Pitch={orientation[1]:.1f}°, Roll={orientation[2]:.1f}° (忽略检测角度 {rotation_angle:.1f}°)")

                    
                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    print(f"❌ 检测结果解析失败: {e}")
                    print(f"原始结果: {ai_content}")
                    print(f"处理后内容: {json_content if 'json_content' in locals() else 'N/A'}")
                    _return_to_initial_and_stop("检测结果解析失败")
                    return False
                    
            except Exception as e:
                print(f"❌ 提取AI内容时出错: {e}")
                print(f"返回结果类型: {type(result)}")
                _return_to_initial_and_stop("提取AI内容失败")
                return False
                
        except Exception as e:
            print(f"❌ AI检测过程失败: {e}")
            _return_to_initial_and_stop("AI检测过程失败")
            return False
        
        # 5. 坐标转换：像素坐标 -> 基底坐标
        print(f"📐 坐标转换: 像素({pixel_x}, {pixel_y}) -> 世界坐标")
        
        try:
            # 获取标定参数
            calibration_params = embodied_internal._get_calibration_params()
            if not calibration_params:
                print("❌ 未找到相机标定参数")
                _return_to_initial_and_stop("未找到相机标定参数")
                return False
            
            # 转换像素坐标到基底坐标（含TCP修正）
            world_coords = embodied_internal._convert_pixel_to_world_coords(
                pixel_x, pixel_y, calibration_params, current_pose, tcp_offset_x, tcp_offset_y, tcp_offset_z
            )
            
            if world_coords is None:
                print("❌ 坐标转换失败")
                _return_to_initial_and_stop("坐标转换失败")
                return False
            
            target_x, target_y, target_z = world_coords
            print(f"🌍 世界坐标: ({target_x:.1f}, {target_y:.1f}, {target_z:.1f}) mm")
            
        except Exception as e:
            print(f"❌ 坐标转换失败: {e}")
            _return_to_initial_and_stop(f"坐标转换失败: {e}")
            return False
        
        # 6. 逆运动学计算
        print("🧮 逆运动学计算...")
        try:
            from core.arm_core.kinematics import RobotKinematics
            
            # 初始化运动学计算器
            kinematics = RobotKinematics()
            kinematics.set_angle_offset([0, 90, 0, 0, 0, 0])
            
            # 构建目标变换矩阵
            target_transform = embodied_internal._build_target_transform(
                [target_x, target_y, target_z], orientation
            )
            
            # 进行逆运动学计算
            solutions = kinematics.inverse_kinematics(target_transform, return_all=True)
            
            if not solutions:
                print("❌ 逆运动学求解失败")
                _return_to_initial_and_stop("逆运动学求解失败")
                return False
            
            # 使用新的解筛选逻辑
            if isinstance(solutions, list) and len(solutions) > 0:
                # 多个解的情况 - 选择最优解
                target_joints = select_best_solution(solutions)
                if target_joints is None:
                    print("❌ 无合适的逆运动学解（2轴不在0°-90°范围内）")
                    _return_to_initial_and_stop("无合适的逆运动学解")
                    return False
            elif isinstance(solutions, np.ndarray):
                # 单个解的情况 - 验证解的有效性
                candidate_angles = solutions.tolist()
                if is_valid_solution(candidate_angles):
                    target_joints = candidate_angles
                else:
                    print("❌ 逆运动学解不满足约束条件（2轴不在0°-90°范围内）")
                    _return_to_initial_and_stop("逆运动学解不满足约束条件")
                    return False
            else:
                print("❌ 逆运动学计算返回格式异常")
                _return_to_initial_and_stop("逆运动学计算返回格式异常")
                return False
            
            print(f"🎯 关节角度: {[f'{angle:.2f}°' for angle in target_joints]}")
            
        except Exception as e:
            print(f"❌ 逆运动学计算失败: {e}")
            _return_to_initial_and_stop(f"逆运动学计算失败: {e}")
            return False
        
        # 7. 执行机械臂运动
        print("🤖 执行抓取运动...")
        
        # 观察动作已在AI检测完成后停止，直接执行抓取
        success = c_a_j(target_joints, None)
        
        if success:
            print(f"✅ 视觉抓取成功完成")
            print(f"📊 最终位置: 世界坐标({target_x:.1f}, {target_y:.1f}, {target_z:.1f}) mm")
            print(f"📊 抓取姿态: Yaw={orientation[0]:.1f}°, Pitch={orientation[1]:.1f}°, Roll={orientation[2]:.1f}°")
            print(f"📊 关节角度: {[f'{angle:.1f}°' for angle in target_joints]}")
            return True
        else:
            print(f"❌ 机械臂运动失败")
            _return_to_initial_and_stop("机械臂运动失败")
            return False
            
    except Exception as e:
        print(f"❌ 视觉抓取失败: {e}")
        import traceback
        print(f"详细错误信息:\n{traceback.format_exc()}")
        _return_to_initial_and_stop(f"视觉抓取异常: {e}")
        return False
        
    finally:
        # 清理观察动作线程
        try:
            if 'observation_thread' in locals() and observation_thread and observation_thread.is_alive():
                if 'observation_stop_flag' in locals():
                    observation_stop_flag.set()
                observation_thread.join(timeout=2.0)
        except Exception as cleanup_error:
            print(f"⚠️ 清理观察动作线程失败: {cleanup_error}")
        
        # 清理临时文件
        try:
            if temp_image_path and os.path.exists(temp_image_path):
                os.unlink(temp_image_path)
        except Exception as cleanup_error:
            print(f"⚠️ 清理临时文件失败: {cleanup_error}")

def c_c_g(action: int) -> bool:
    """
    控制夹爪抓取动作 (Control Claw Grasp)
    
    Args:
        action: 夹爪动作，1=张开，0=闭合
        
    Returns:
        bool: 夹爪控制是否成功
    """
    # 检查紧急停止状态
    try:
        check_emergency_stop()
    except Exception as e:
        print(f"🛑 {e}")
        return False
    
    # 获取夹爪控制器
    claw_controller = _get_claw_controller()
    if not claw_controller:
        print("❌ 夹爪未连接，无法执行抓取动作")
        return False
    
    # 检查控制器连接状态
    try:
        if not claw_controller.is_connected():
            print("❌ 夹爪连接已断开")
            return False
    except Exception as e:
        print(f"❌ 检查夹爪连接状态失败: {e}")
        return False
    
    try:
        # 获取夹爪参数
        claw_params = _get_claw_params()
        open_angle = claw_params["open_angle"]
        close_angle = claw_params["close_angle"]
        
        if action == 1:
            # 张开夹爪
            print(f"🤏 夹爪张开到 {open_angle}°")
            claw_controller.open(open_angle)
            time.sleep(1)
            return True
        elif action == 0:
            # 闭合夹爪
            print(f"🤏 夹爪闭合到 {close_angle}°")
            claw_controller.close(close_angle)
            time.sleep(1)
            return True
        else:
            print(f"❌ 无效的夹爪动作参数: {action}，应为0（闭合）或1（张开）")
            return False
            
    except Exception as e:
        print(f"❌ 夹爪控制失败: {e}")
        return False