#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Joy-Con 手柄控制 SDK 封装
=========================

目标：
- 复用现有 `core.joycon_arm_controller.JoyConArmController` 的所有控制逻辑；
- 提供一个**无界面依赖**的手柄控制接口，方便在桌面 / ROS / 后端服务中直接启用 Joy-Con 控制。
"""

from __future__ import annotations

from typing import Dict, Any, Tuple, Optional, List

from Horizon_Core.core.joycon_arm_controller import JoyConArmController, ControlMode
from Horizon_Core.core.arm_core.kinematics import RobotKinematics

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
        print(f" ⚠️ [JoyconSDK] 加载电机配置失败，使用默认值: {e}")
        
    return config

class JoyconSDK:
    """
    Joy-Con 手柄控制 SDK。

    - 内部封装一个 JoyConArmController；
    - 只提供绑定机械臂 + 连接手柄 + 启动/停止控制等高层接口；
    - 具体按键映射 / 运动学控制完全复用 core.joycon_arm_controller 内部实现。
    """

    def __init__(self) -> None:
        self._controller = JoyConArmController()

    # ------------------------------------------------------------------
    # 机械臂绑定
    # ------------------------------------------------------------------

    def bind_arm(
        self,
        motors: Dict[int, Any],
        *,
        use_motor_config: bool = True,
        kinematics: Optional[RobotKinematics] = None,
        mujoco_controller: Optional[Any] = None,
    ) -> None:
        """
        绑定真实机械臂对象到 Joy-Con 控制器。

        Args:
            motors: 电机实例字典 {motor_id: ZDTMotorController}
            use_motor_config: 是否使用全局 motor_config.json 里的减速比/方向
            kinematics: 可选，若不传则自动创建一个默认 RobotKinematics
            mujoco_controller: 可选，用于同时驱动 MuJoCo 数字孪生
        """
        mcm = None
        if use_motor_config:
            # 这里的 _load_motor_config 会被后续 controller 使用
            # 注意：JoyConArmController 内部原本可能期望一个有 get_all_* 方法的对象
            # 我们需要检查一下 JoyConArmController 的实现
            config = _load_motor_config()
            # 为了兼容，我们构造一个简单的类模拟 motor_config_manager
            class SimpleConfigManager:
                def __init__(self, cfg):
                    self.cfg = cfg

                def get_all_reducer_ratios(self):
                    return {int(k): v for k, v in self.cfg["motor_reducer_ratios"].items()}

                def get_all_directions(self):
                    return {int(k): v for k, v in self.cfg["motor_directions"].items()}

                # ----------------------------
                # 单电机查询接口（兼容不同版本实现）
                # ----------------------------
                def get_motor_reducer_ratio(self, motor_id: int):
                    ratios = self.get_all_reducer_ratios()
                    return float(ratios.get(int(motor_id), 1.0))

                def get_motor_direction(self, motor_id: int):
                    dirs = self.get_all_directions()
                    return int(dirs.get(int(motor_id), 1))

                # 兼容某些二进制封装里存在的历史拼写错误：
                # JoyConArmController 可能会调用 geet_motor_reducer_ratio
                def geet_motor_reducer_ratio(self, motor_id: int):
                    return self.get_motor_reducer_ratio(motor_id)
            mcm = SimpleConfigManager(config)

        if kinematics is None:
            kin = RobotKinematics()
            kin.set_angle_offset([0, 90, 0, 0, 0, 0])
        else:
            kin = kinematics

        self._controller.set_arm(
            motors=motors,
            motor_config_manager=mcm,
            kinematics=kin,
            mujoco_controller=mujoco_controller,
        )

    # 兼容旧接口：保持 set_arm 与 GUI 现有调用一致
    def set_arm(
        self,
        motors: Dict[int, Any],
        motor_config_manager=None,
        kinematics: Optional[RobotKinematics] = None,
        mujoco_controller: Optional[Any] = None,
    ) -> None:
        self.bind_arm(
            motors=motors,
            use_motor_config=(motor_config_manager is not None),
            kinematics=kinematics,
            mujoco_controller=mujoco_controller,
        )

    # ------------------------------------------------------------------
    # 手柄连接 / 控制启动
    # ------------------------------------------------------------------

    def connect_joycon(self) -> Tuple[bool, bool]:
        """
        连接 Joy-Con 手柄。

        Returns:
            (left_ok, right_ok): 左/右手柄是否连接成功。
        """
        return self._controller.connect_joycon()

    def disconnect_joycon(self) -> None:
        """断开 Joy-Con 连接。"""
        self._controller.disconnect_joycon()

    # ------------------------------------------------------------------
    # 手柄状态读取（用于无 UI 调试 / 可视化）
    # ------------------------------------------------------------------

    def get_left_joycon_status(self) -> Optional[Dict[str, Any]]:
        """
        获取左 Joy-Con 当前状态（按键、摇杆、电池、陀螺仪等）。

        Returns:
            dict 或 None：若未连接或读取失败则返回 None。
        """
        try:
            joycon = getattr(self._controller, "joycon", None)
            if joycon is None:
                return None
            return joycon.get_left_status()
        except Exception:
            return None

    def get_right_joycon_status(self) -> Optional[Dict[str, Any]]:
        """
        获取右 Joy-Con 当前状态（按键、摇杆、电池、陀螺仪等）。

        Returns:
            dict 或 None：若未连接或读取失败则返回 None。
        """
        try:
            joycon = getattr(self._controller, "joycon", None)
            if joycon is None:
                return None
            return joycon.get_right_status()
        except Exception:
            return None

    def start_control(self) -> None:
        """启动 Joy-Con 控制循环（开启独立线程）。"""
        self._controller.start()

    def stop_control(self) -> None:
        """停止 Joy-Con 控制循环。"""
        self._controller.stop()

    def pause_control(self) -> None:
        """暂停控制（不再响应手柄输入，但不断开连接）。"""
        self._controller.pause()

    def resume_control(self) -> None:
        """恢复控制。"""
        self._controller.resume()

    def emergency_stop(self) -> None:
        """紧急停止（停止所有电机，并置位急停标志）。"""
        self._controller.emergency_stop()

    # ------------------------------------------------------------------
    # 模式 / 速度 / 常用动作
    # ------------------------------------------------------------------

    def toggle_mode(self) -> None:
        """在笛卡尔模式 / 关节模式之间切换。"""
        self._controller.toggle_control_mode()

    def set_mode_cartesian(self) -> None:
        """强制切换到笛卡尔控制模式。"""
        if self._controller.control_mode != ControlMode.CARTESIAN:
            self._controller.toggle_control_mode()

    def set_mode_joint(self) -> None:
        """强制切换到关节控制模式。"""
        if self._controller.control_mode != ControlMode.JOINT:
            self._controller.toggle_control_mode()

    def increase_speed(self) -> None:
        """提高手柄控制速度等级。"""
        self._controller.increase_speed()

    def decrease_speed(self) -> None:
        """降低手柄控制速度等级。"""
        self._controller.decrease_speed()

    def move_to_home(self) -> None:
        """回到软件定义的 home 姿态（所有关节 0）。"""
        self._controller.move_to_home()

    def home_to_hardware_zero(self) -> None:
        """回到驱动器保存的硬件零位（与示教器的回零位(坐标原点)一致）。"""
        self._controller.home_to_hardware_zero()

    # ------------------------------------------------------------------
    # 参数配置（保持与 JoyConArmController.params / 限位一致）
    # ------------------------------------------------------------------

    def set_stick_deadzone(self, deadzone: int) -> None:
        """
        设置摇杆死区（对应 JoyConArmController.params['stick_deadzone']）。
        """
        self._controller.params["stick_deadzone"] = int(deadzone)

    def configure_cartesian(
        self,
        *,
        position_step: Optional[float] = None,
        rotation_step: Optional[float] = None,
        max_speed: Optional[float] = None,
        max_angular_speed: Optional[float] = None,
    ) -> None:
        """
        配置笛卡尔模式参数（对应 params 中 cartesian_* 字段）。
        """
        p = self._controller.params
        if position_step is not None:
            p["cartesian_position_step"] = float(position_step)
        if rotation_step is not None:
            p["cartesian_rotation_step"] = float(rotation_step)
        if max_speed is not None:
            p["cartesian_max_speed"] = float(max_speed)
        if max_angular_speed is not None:
            p["cartesian_max_angular_speed"] = float(max_angular_speed)

    def configure_joint(
        self,
        *,
        angle_step: Optional[float] = None,
        max_speed: Optional[int] = None,
        acceleration: Optional[int] = None,
        deceleration: Optional[int] = None,
    ) -> None:
        """
        配置关节模式参数（对应 params 中 joint_* 字段）。
        """
        p = self._controller.params
        if angle_step is not None:
            p["joint_angle_step"] = float(angle_step)
        if max_speed is not None:
            p["joint_max_speed"] = int(max_speed)
        if acceleration is not None:
            p["joint_acceleration"] = int(acceleration)
        if deceleration is not None:
            p["joint_deceleration"] = int(deceleration)

    def configure_speed_levels(
        self,
        levels: Optional[List[float]] = None,
        current_index: Optional[int] = None,
    ) -> None:
        """
        配置速度等级数组及当前等级索引（对应 params['speed_levels'] / params['current_speed_index']）。
        """
        p = self._controller.params
        if levels is not None and len(levels) > 0:
            p["speed_levels"] = [float(v) for v in levels]
        if current_index is not None:
            idx = int(current_index)
            idx = max(0, min(idx, len(p.get("speed_levels", [])) - 1))
            p["current_speed_index"] = idx

    def configure_workspace(
        self,
        *,
        min_radius: Optional[float] = None,
        max_radius: Optional[float] = None,
        min_z: Optional[float] = None,
        max_z: Optional[float] = None,
    ) -> None:
        """
        配置工作空间限制（对应 JoyConArmController.workspace_limits）。
        """
        ws = self._controller.workspace_limits
        if min_radius is not None:
            ws["min_radius"] = float(min_radius)
        if max_radius is not None:
            ws["max_radius"] = float(max_radius)
        if min_z is not None:
            ws["min_z"] = float(min_z)
        if max_z is not None:
            ws["max_z"] = float(max_z)

    def configure_gripper_angles(
        self,
        *,
        open_angle: Optional[float] = None,
        close_angle: Optional[float] = None,
    ) -> None:
        """
        配置手柄侧使用的夹爪开合角度（对应 params['gripper_open_angle'] / params['gripper_close_angle']）。
        """
        p = self._controller.params
        if open_angle is not None:
            p["gripper_open_angle"] = float(open_angle)
        if close_angle is not None:
            p["gripper_close_angle"] = float(close_angle)

    def set_joint_limits(self, limits: Optional[List[Tuple[float, float]]] = None) -> None:
        """
        设置关节角度限位（对应 JoyConArmController.joint_limits）。

        Args:
            limits: 长度为 6 的列表，每项为 (min_angle, max_angle)。
        """
        if not limits:
            return
        if len(limits) != 6:
            raise ValueError("joint_limits 长度必须为 6")
        self._controller.joint_limits = [(float(a), float(b)) for a, b in limits]

    # ------------------------------------------------------------------
    # 状态查询
    # ------------------------------------------------------------------

    def get_status(self) -> Dict[str, Any]:
        """
        查询当前 Joy-Con 控制器状态（直接转发 JoyConArmController.get_status）。
        """
        return self._controller.get_status()

    # ------------------------------------------------------------------
    # 兼容底层属性访问（供 GUI 等高层代码复用现有逻辑）
    # ------------------------------------------------------------------

    @property
    def running(self) -> bool:
        """当前控制线程是否在运行。"""
        return bool(getattr(self._controller, "running", False))

    @property
    def params(self) -> Dict[str, Any]:
        """暴露底层控制参数字典（只读引用，供配置界面使用）。"""
        return self._controller.params

    @property
    def joint_limits(self) -> List[Tuple[float, float]]:
        """暴露关节角度限位（列表长度为 6）。"""
        return self._controller.joint_limits

    @joint_limits.setter
    def joint_limits(self, limits: List[Tuple[float, float]]) -> None:
        self._controller.joint_limits = [(float(a), float(b)) for a, b in limits]

    @property
    def workspace_limits(self) -> Dict[str, float]:
        """暴露工作空间限制字典。"""
        return self._controller.workspace_limits

    @workspace_limits.setter
    def workspace_limits(self, limits: Dict[str, float]) -> None:
        self._controller.workspace_limits.update(
            {
                "min_radius": float(limits.get("min_radius", self._controller.workspace_limits.get("min_radius", 0.0))),
                "max_radius": float(limits.get("max_radius", self._controller.workspace_limits.get("max_radius", 0.0))),
                "min_z": float(limits.get("min_z", self._controller.workspace_limits.get("min_z", 0.0))),
                "max_z": float(limits.get("max_z", self._controller.workspace_limits.get("max_z", 0.0))),
            }
        )


