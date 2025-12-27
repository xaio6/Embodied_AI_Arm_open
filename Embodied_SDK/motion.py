#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
运动控制 SDK 封装
================

目标：
- 在不改动现有底层实现的前提下，给关节运动 / 末端运动 / 预设动作提供一个
  无界面依赖、接口统一的高层封装，方便在 Web / ROS2 / 脚本中直接调用。

本模块只是对 `core.embodied_core.embodied_func` 中已有函数的**薄封装**：
- `c_a_j`  关节角度运动
- `c_a_p`  末端位置/姿态运动（自动 IK）
- `e_p_a`  预设动作（从 preset_actions.json 读取）
"""

from __future__ import annotations

from typing import Dict, Any, List, Optional
import logging

from Horizon_Core import gateway as horizon_gateway

def _load_motor_config():
    """从 config/motor_config.json 加载电机配置"""
    import os
    import json
    
    # 默认配置
    config = {
        "motor_reducer_ratios": {
            "1": 62.0, "2": 51.0, "3": 51.0, "4": 62.0, "5": 12.0, "6": 8.0
        },
        "motor_directions": {
            "1": 1, "2": 1, "3": 1, "4": 1, "5": 1, "6": 1
        }
    }
    
    try:
        # 优先使用环境变量
        config_dir = os.environ.get("HORIZONARM_CONFIG_DIR", "").strip()
        if not config_dir:
            # 尝试定位项目根目录
            current_dir = os.path.dirname(os.path.abspath(__file__))
            config_dir = os.path.join(os.path.dirname(current_dir), "config")
            
        config_path = os.path.join(config_dir, "motor_config.json")
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                if "motor_reducer_ratios" in loaded:
                    config["motor_reducer_ratios"].update(loaded["motor_reducer_ratios"])
                if "motor_directions" in loaded:
                    config["motor_directions"].update(loaded["motor_directions"])
    except Exception as e:
        print(f" ⚠️ [MotionSDK] 加载电机配置失败，使用默认值: {e}")
        
    return config

def create_motor_controller(*args, **kwargs) -> Any:
    """
    创建电机控制器实例（ZDTMotorController）。
    
    这是获取底层电机控制对象的推荐方式，它会自动处理授权验证。
    """
    return horizon_gateway.create_motor_controller(*args, **kwargs)

def get_function_codes() -> Any:
    """
    获取底层功能码常量类 (FunctionCodes)。
    
    Returns:
        FunctionCodes 类，包含各类控制指令的功能码常量
    """
    Control_Core = horizon_gateway.get_control_core()
    return Control_Core.constants.FunctionCodes

def setup_logging(level=logging.INFO):
    """
    设置日志配置
    
    Args:
        level: 日志级别
    """
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )

def close_all_shared_interfaces():
    """关闭所有共享的 CAN 接口连接"""
    Control_Core = horizon_gateway.get_control_core()
    Control_Core.ZDTMotorController.close_all_shared_interfaces()

def get_shared_interface_info():
    """获取共享接口信息"""
    Control_Core = horizon_gateway.get_control_core()
    return Control_Core.ZDTMotorController.get_shared_interface_info()

class MotionSDK:
    """
    机械臂基础运动控制 SDK：
    - 与 GUI 解耦，仅依赖已有的 embodied_func / embodied_internal；
    - 主要面向：Web 后端、ROS2 节点、独立 Python 脚本等。
    """

    def __init__(self) -> None:
        # 缓存底层命令构建器类
        self._command_builder_cls = None

    # ------------------------------------------------------------------
    # 电机 & 运动参数绑定
    # ------------------------------------------------------------------

    def bind_motors(
        self,
        motors: Dict[int, Any],
        *,
        use_motor_config: bool = True,
        reducer_ratios: Optional[Dict[int, float]] = None,
        directions: Optional[Dict[int, int]] = None,
    ) -> None:
        """
        绑定真实机械臂电机实例。
        
        与 VisualGraspSDK 的 bind_motors 行为一致，最终都调用
        `embodied_internal._set_real_motors`。
        """
        if use_motor_config:
            config = _load_motor_config()
            all_ratios = {int(k): v for k, v in config["motor_reducer_ratios"].items()}
            all_dirs = {int(k): v for k, v in config["motor_directions"].items()}
            rr = {mid: all_ratios.get(mid, 16.0) for mid in motors.keys()}
            dd = {mid: all_dirs.get(mid, 1) for mid in motors.keys()}
        else:
            rr = reducer_ratios or {}
            dd = directions or {}

        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_real_motors(motors, rr, dd)

    def unbind_motors(self) -> None:
        """
        解绑 / 清空真实机械臂电机绑定。

        本质上是调用 `embodied_internal._set_real_motors(None, None, None)`，
        用于在停止系统或断开机械臂时清理全局状态。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_real_motors(None, None, None)

    def set_motion_params(
        self,
        max_speed: int = 100,
        acceleration: int = 50,
        deceleration: int = 50,
    ) -> None:
        """
        设置真实机械臂的全局运动参数。
        
        对应 `embodied_internal._set_motion_params`，会影响 `c_a_j` / `c_a_p`。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_motion_params(
            max_speed=max_speed,
            acceleration=acceleration,
            deceleration=deceleration,
        )

    def get_motion_params(self) -> Dict[str, Any]:
        """
        获取当前全局运动参数（直接转发 embodied_internal._get_motion_params）。
        
        Returns:
            dict: {"max_speed": int, "acceleration": int, "deceleration": int}
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        return embodied_internal._get_motion_params()

    # ------------------------------------------------------------------
    # 摄像头 / 视觉相关辅助接口
    # ------------------------------------------------------------------

    def set_camera_id(self, camera_id: int) -> None:
        """
        设置用于具身智能 / 视觉抓取的摄像头 ID。

        对应 `embodied_internal._set_camera_id`。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_camera_id(camera_id)

    def set_current_camera_frame(self, frame: Any) -> None:
        """
        将当前摄像头画面传递给底层具身智能模块使用。

        Args:
            frame: OpenCV 读取的图像帧（numpy.ndarray），此处按 Any 透传。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_current_camera_frame(frame)

    # ------------------------------------------------------------------
    # 抓取参数（姿态 / TCP / 深度）封装
    # ------------------------------------------------------------------

    def get_grasp_params(self) -> Dict[str, Any]:
        """
        获取当前全局抓取参数（直接转发 embodied_internal._get_grasp_params）。

        Returns:
            dict: 包含 yaw/pitch/roll、tcp_offset_x/y/z、grasp_depth 等字段。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        return embodied_internal._get_grasp_params()

    def set_grasp_params(
        self,
        *,
        yaw: Optional[float] = None,
        pitch: Optional[float] = None,
        roll: Optional[float] = None,
        use_dynamic_pose: Optional[bool] = None,
        tcp_offset_x: Optional[float] = None,
        tcp_offset_y: Optional[float] = None,
        tcp_offset_z: Optional[float] = None,
        grasp_depth: Optional[float] = None,
    ) -> None:
        """
        设置视觉抓取相关的全局参数（姿态、TCP 偏移、抓取深度等）。

        所有参数都是可选的，未传入的字段保持原值。
        """
        kwargs: Dict[str, Any] = {}
        if yaw is not None:
            kwargs["yaw"] = yaw
        if pitch is not None:
            kwargs["pitch"] = pitch
        if roll is not None:
            kwargs["roll"] = roll
        if use_dynamic_pose is not None:
            kwargs["use_dynamic_pose"] = use_dynamic_pose
        if tcp_offset_x is not None:
            kwargs["tcp_offset_x"] = tcp_offset_x
        if tcp_offset_y is not None:
            kwargs["tcp_offset_y"] = tcp_offset_y
        if tcp_offset_z is not None:
            kwargs["tcp_offset_z"] = tcp_offset_z
        if grasp_depth is not None:
            kwargs["grasp_depth"] = grasp_depth

        if kwargs:
            embodied_internal = horizon_gateway.get_embodied_internal_module()
            embodied_internal._set_grasp_params(**kwargs)

    # ------------------------------------------------------------------
    # 关节空间运动
    # ------------------------------------------------------------------

    def move_joints(self, joint_angles: List[float], duration: Optional[float] = None) -> bool:
        """
        关节空间绝对运动（通过授权网关调用 embodied_func.c_a_j）。
        
        Args:
            joint_angles: 6 轴目标角度，单位度 [J1..J6]
            duration: 期望运动时间（秒），None 则由底层自动计算
        """
        embodied_func = horizon_gateway.get_embodied_module()
        return bool(embodied_func.c_a_j(joint_angles, duration))

    # ------------------------------------------------------------------
    # 笛卡尔空间运动
    # ------------------------------------------------------------------

    def move_cartesian(
        self,
        position: List[float],
        orientation: Optional[List[float]] = None,
        duration: Optional[float] = None,
    ) -> bool:
        """
        末端笛卡尔空间运动（通过授权网关调用 embodied_func.c_a_p，内部自动 IK）。
        
        Args:
            position: [x, y, z] 末端目标位置（mm）
            orientation: [yaw, pitch, roll] 末端目标姿态（deg），None 则保持当前姿态
            duration: 期望运动时间（秒），None 则由底层自动计算
        """
        embodied_func = horizon_gateway.get_embodied_module()
        return bool(embodied_func.c_a_p(position, orientation, duration))

    # ------------------------------------------------------------------
    # 预设动作
    # ------------------------------------------------------------------

    def execute_preset_action(self, name: str, speed: str = "normal") -> bool:
        """
        执行预设动作（基于 config/embodied_config/preset_actions.json，通过授权网关调用）。
        
        Args:
            name: 动作名称（JSON 中的 key）
            speed: "slow" / "normal" / "fast"
        """
        embodied_func = horizon_gateway.get_embodied_module()
        return bool(embodied_func.e_p_a(name, speed))

    # ------------------------------------------------------------------
    # 夹爪控制（直接转发 c_c_g）
    # ------------------------------------------------------------------

    def control_claw(self, action: int) -> bool:
        """
        控制夹爪抓取动作（完全复用 embodied_func.c_c_g，经授权网关调用）:
        - action=1: 张开
        - action=0: 闭合
        """
        embodied_func = horizon_gateway.get_embodied_module()
        return bool(embodied_func.c_c_g(action))

    # ------------------------------------------------------------------
    # 夹爪参数 / 控制器绑定（保持与 GUI 相同能力）
    # ------------------------------------------------------------------

    def bind_claw_controller(self, controller: Any) -> None:
        """
        绑定夹爪控制器实例（通过授权网关转发 embodied_func._set_claw_controller）。
        
        一般在完成串口连接后调用，例如::
        
            motion.bind_claw_controller(claw_controller)
        """
        embodied_func = horizon_gateway.get_embodied_module()
        embodied_func._set_claw_controller(controller)

    def set_claw_params(
        self,
        *,
        open_angle: Optional[float] = None,
        close_angle: Optional[float] = None,
    ) -> None:
        """
        设置夹爪开合角度参数（通过授权网关转发 embodied_func._set_claw_params）。
        
        所有参数可选，未传入的字段保持原值。
        """
        kwargs: Dict[str, Any] = {}
        if open_angle is not None:
            kwargs["open_angle"] = open_angle
        if close_angle is not None:
            kwargs["close_angle"] = close_angle

        if kwargs:
            embodied_func = horizon_gateway.get_embodied_module()
            embodied_func._set_claw_params(**kwargs)

    def get_claw_params(self) -> Dict[str, Any]:
        """
        获取当前夹爪参数（通过授权网关转发 embodied_func._get_claw_params）。
        """
        embodied_func = horizon_gateway.get_embodied_module()
        return embodied_func._get_claw_params()

    # ------------------------------------------------------------------
    # 低层命令构建器（供示教器 / 轨迹 / 多电机 Y42 命令复用）
    # ------------------------------------------------------------------

    def get_command_builder(self):
        """
        获取底层 `ZDTCommandBuilder` 类，用于构建 Y42 多电机命令等低层功能体。

        说明：
        - 仅作为 GUI / 高级工具模块的兼容接口；
        - 外部脚本 / ROS 等推荐优先使用 move_joints / move_cartesian 等高层 API；
        - 具体实现细节仍通过 `Horizon_Core.gateway.get_control_core()` 间接访问。
        """
        if getattr(self, "_command_builder_cls", None) is None:
            Control_Core = horizon_gateway.get_control_core()
            # ZDTCommandBuilder 为底层提供的命令构建工具类（含 position_mode_* / build_single_command_bytes 等）
            self._command_builder_cls = Control_Core.ZDTCommandBuilder  # type: ignore[attr-defined]
        return self._command_builder_cls
