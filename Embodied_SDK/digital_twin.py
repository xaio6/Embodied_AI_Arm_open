#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字孪生 / MuJoCo 仿真 SDK 封装
===============================

目标：
- 提供一套**无界面依赖**、可在脚本环境直接运行的 MuJoCo 仿真控制入口；
- 与 `MotionSDK` 的接口风格尽量一致：关节运动/笛卡尔运动/预设动作；
- 额外提供"启动/停止仿真查看器、设置关节角、查询运行状态"等便捷方法，
  以便开发者在脚本环境中也能直观看到效果。

注意：
- 本 SDK 的仿真能力依赖 `mujoco` 与 OpenGL 环境；若未安装或环境不支持，将返回 False 并打印提示。
- 本 SDK **只影响仿真世界**，不会驱动真实机械臂电机。
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple


@dataclass
class SimulationStatus:
    """仿真运行状态快照（用于调试/日志）。"""
    running: bool
    viewer_running: bool
    model_path: str
    last_error: Optional[str] = None


class DigitalTwinSDK:
    """
    MuJoCo 数字孪生运动控制 SDK。

    - 接口风格与 MotionSDK 尽量保持一致；
    - 若当前环境未安装 MuJoCo / 未能初始化，将打印提示并返回 False；
    - 提供 `start_simulation/stop_simulation/is_running/set_joint_angles` 等便捷接口，
      与 `example/mujoco_control.py` 保持一致。
    """

    def __init__(self, model_path: str = "config/urdf/mjmodel.xml", *, enable_viewer: bool = True) -> None:
        self._model_path = model_path
        self._enable_viewer = bool(enable_viewer)
        self._controller = None  # 延迟创建：MuJoCoArmController
        self._last_error: Optional[str] = None

    # ------------------------------------------------------------------
    # 仿真生命周期
    # ------------------------------------------------------------------

    def start_simulation(self) -> bool:
        """
        启动 MuJoCo 仿真（打开查看器窗口）。

        Returns:
            bool: 启动成功返回 True；若环境缺少 MuJoCo / OpenGL 不可用则返回 False。
        """
        try:
            # 延迟导入，避免在未安装 mujoco 的环境下直接 ImportError
            from Horizon_Core.core.mujoco_arm_controller import MuJoCoArmController

            if self._controller is None:
                self._controller = MuJoCoArmController(
                    model_path=self._model_path,
                    enable_viewer=self._enable_viewer,
                )
            else:
                # 若之前 stop_viewer 过，可再次启动
                if getattr(self._controller, "viewer_running", False) is False and self._enable_viewer:
                    self._controller.start_viewer()

            self._last_error = None
            return True
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] 启动 MuJoCo 仿真失败：{self._last_error}")
            return False

    def stop_simulation(self) -> None:
        """停止 MuJoCo 仿真查看器并释放资源（若已启动）。"""
        try:
            if self._controller is not None and hasattr(self._controller, "stop_viewer"):
                self._controller.stop_viewer()
        except Exception as e:
            # 停止失败不抛出，避免影响上层退出流程
            self._last_error = f"{type(e).__name__}: {e}"
        finally:
            # 允许后续重新 start_simulation() 重新初始化
            self._controller = None

    def is_running(self) -> bool:
        """判断仿真查看器是否仍在运行（窗口关闭或 stop 后为 False）。"""
        if self._controller is None:
            return False
        return bool(getattr(self._controller, "viewer_running", False))

    def get_status(self) -> SimulationStatus:
        """返回当前仿真状态快照。"""
        running = self._controller is not None
        viewer_running = bool(getattr(self._controller, "viewer_running", False)) if self._controller else False
        return SimulationStatus(
            running=running,
            viewer_running=viewer_running,
            model_path=self._model_path,
            last_error=self._last_error,
        )

    # ------------------------------------------------------------------
    # 运动参数
    # ------------------------------------------------------------------

    def set_motion_params(
        self,
        max_speed: int = 100,
        acceleration: int = 50,
        deceleration: int = 50,
    ) -> None:
        """
        设置 MuJoCo 仿真运动参数（用于同步与日志）。

        说明：MuJoCo 纯显示模式下并不直接使用 RPM 参数；本方法主要用于上层统一参数体系。
        """
        # 兼容旧接口：仅记录，不强制参与控制
        self._motion_params = {
            "max_speed": int(max_speed),
            "acceleration": int(acceleration),
            "deceleration": int(deceleration),
        }

    def get_motion_params(self) -> Dict[str, Any]:
        """
        获取当前 MuJoCo 仿真运动参数（若未设置则返回默认值）。
        """
        return dict(getattr(self, "_motion_params", {"max_speed": 100, "acceleration": 50, "deceleration": 50}))

    # ------------------------------------------------------------------
    # 关节 / 笛卡尔运动
    # ------------------------------------------------------------------

    def move_joints(self, joint_angles: List[float], duration: Optional[float] = None) -> bool:
        """
        在 MuJoCo 中执行关节空间运动（不影响真实机械臂）。
        """
        if self._controller is None:
            if not self.start_simulation():
                return False

        try:
            # 使用平滑插值，避免瞬跳；duration 为空则使用控制器默认
            if duration is not None and duration > 0:
                # steps 取一个经验值：50Hz 控制周期下的插补
                steps = max(10, int(duration / 0.05))
                self._controller.smooth_move_to_angles(list(joint_angles), duration=float(duration), steps=int(steps))
            else:
                self._controller.set_joint_angles(list(joint_angles), update_display=True)
            return True
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] move_joints 失败：{self._last_error}")
            return False

    def move_cartesian(
        self,
        position: List[float],
        orientation: Optional[List[float]] = None,
        duration: Optional[float] = None,
    ) -> bool:
        """
        在 MuJoCo 中执行末端笛卡尔运动（自动 IK）。
        """
        if self._controller is None:
            if not self.start_simulation():
                return False

        try:
            ok = self._controller.move_to_pose(list(position), list(orientation) if orientation is not None else None, update_display=True)
            if not ok:
                return False
            # 若指定 duration，则用关节插补实现“更像真实机械臂”的运动时间
            if duration is not None and duration > 0:
                # move_to_pose 已经把关节设定为目标；此处不再重复插补，保持轻量
                pass
            return True
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] move_cartesian 失败：{self._last_error}")
            return False

    # ------------------------------------------------------------------
    # 便捷接口（与示例脚本保持一致）
    # ------------------------------------------------------------------

    def set_joint_angles(self, angles: List[float]) -> bool:
        """直接设置仿真关节角（不做规划，主要用于实时同步/波形演示）。"""
        if self._controller is None:
            if not self.start_simulation():
                return False
        try:
            self._controller.set_joint_angles(list(angles), update_display=True)
            return True
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] set_joint_angles 失败：{self._last_error}")
            return False

    def get_joint_angles(self) -> Optional[List[float]]:
        """获取当前仿真关节角；仿真未启动时返回 None。"""
        if self._controller is None:
            return None
        try:
            return list(self._controller.get_joint_angles())
        except Exception:
            return None

    # ------------------------------------------------------------------
    # 预设动作 / 轨迹
    # ------------------------------------------------------------------

    def execute_preset_action(self, name: str, speed: str = "normal") -> bool:
        """
        在 MuJoCo 中执行预设动作。
        """
        # 目前仿真侧不重复实现 JSON 预设解析，复用 mujoco 版函数库
        try:
            from Horizon_Core.core.embodied_core import embodied_mujoco_func as mj
            return bool(mj.e_p_a(name, speed))
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] execute_preset_action 失败：{self._last_error}")
            return False

    def clear_trajectory(self) -> bool:
        """
        清空当前仿真轨迹。
        """
        if self._controller is None:
            if not self.start_simulation():
                return False
        try:
            if hasattr(self._controller, "clear_trajectory"):
                self._controller.clear_trajectory()
                return True
            return False
        except Exception as e:
            self._last_error = f"{type(e).__name__}: {e}"
            print(f"⚠️ [DigitalTwinSDK] clear_trajectory 失败：{self._last_error}")
            return False


