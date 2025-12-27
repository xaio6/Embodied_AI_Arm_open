#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉抓取 SDK 封装
=================

本模块基于现有的视觉抓取 / 跟随控制实现，提供一个**无界面依赖**的高层视觉抓取接口，
便于在以下场景中复用现有能力（只保留传统视觉逻辑，不包含 LLM / 对话 AI）：

- Ubuntu + ROS2 节点，通过 rclpy 封装为 Service / Action；

当前主要封装能力：
- `VisualGraspSDK.grasp_at_bbox`：基础视觉抓取（框选中心点  抓取），对应原来 Qt 中点选抓取的几何逻辑，改为框选中心；
- `VisualGraspSDK.grasp_at_pixel`：基础视觉抓取（像素点  抓取），完全沿用原有标定与 TCP / 深度参数；
- （后续可选）颜色阈值法检测到目标后，把像素/框中心传给以上接口即可；
- `FollowGraspSDK`：跟随抓取（YOLOv8 + CSRT/跟踪器），对应原有跟随抓取模块的逻辑封装。

注意：
- 本 SDK 不负责建立 CAN 连接，只接收已经连接好的 `motors` 字典；
- 需要调用方在程序启动时，先通过 `Control_SDK.Control_Core.ZDTMotorController`
  建立电机连接，再将 `motors` 交给 `bind_motors`。
"""

from typing import Dict, Any, Optional, Tuple

import threading
import time

import cv2
import numpy as np

from Horizon_Core import gateway as horizon_gateway
from Horizon_Core.core.arm_core.yolo_onnx_detector import YOLOOnnxDetector
from Horizon_Core.core.arm_core.object_follower import SingleObjectFollower

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
        print(f" ⚠️ [VisualGraspSDK] 加载电机配置失败，使用默认值: {e}")
        
    return config

class VisualGraspSDK:
    """
    视觉抓取高层封装类。

    典型用法（伪代码）::

        from Control_SDK.Control_Core import ZDTMotorController
        from Embodied_SDK import VisualGraspSDK

        # 1. 建立电机连接（示意）
        motors = {
            1: ZDTMotorController(...),
            2: ZDTMotorController(...),
            ...
        }
        # motors[*].connect() 由调用方完成

        # 2. 创建 SDK 并绑定电机
        sdk = VisualGraspSDK(camera_id=0)
        sdk.bind_motors(motors)

        # 3. 可选：调整抓取姿态/深度等参数
        sdk.set_grasp_params(yaw=0.0, pitch=0.0, roll=180.0, grasp_depth=300.0)

        # 4. 在上层（ROS/Web）完成框选，取中心像素，然后调用：
        ok = sdk.grasp_at_bbox(x1, y1, x2, y2)
        print("框选抓取结果:", ok)
    """

    def __init__(self, camera_id: int = 0):
        """
        Args:
            camera_id: OpenCV 摄像头设备 ID，默认为 0
        """
        self.camera_id = camera_id

        # 初始化摄像头 ID 到内部全局状态（供像素世界坐标转换等函数使用）
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_camera_id(camera_id)

    # ------------------------------------------------------------------
    # 电机 & 参数绑定接口
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

        该方法会调用 `embodied_internal._set_real_motors`，为后续 `c_a_j` / `c_a_p`
        等底层运动函数提供真实电机上下文。

        Args:
            motors: 电机实例字典 {motor_id: ZDTMotorController 实例}
            use_motor_config: 是否自动从 `motor_config.json` 读取减速比与方向
            reducer_ratios: 可选，显式传入 {motor_id: ratio}
            directions: 可选，显式传入 {motor_id: direction}
        """
        if use_motor_config:
            config = _load_motor_config()
            all_ratios = {int(k): v for k, v in config["motor_reducer_ratios"].items()}
            all_dirs = {int(k): v for k, v in config["motor_directions"].items()}
            # 仅保留当前 motors 中存在的 ID
            rr = {mid: all_ratios.get(mid, 16.0) for mid in motors.keys()}
            dd = {mid: all_dirs.get(mid, 1) for mid in motors.keys()}
        else:
            rr = reducer_ratios or {}
            dd = directions or {}

        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_real_motors(motors, rr, dd)

    def set_motion_params(
        self,
        max_speed: int = 100,
        acceleration: int = 50,
        deceleration: int = 50,
    ) -> None:
        """
        设置真实机械臂的全局运动参数。

        对应 `embodied_internal._set_motion_params`，会影响 `c_a_j` / `c_a_p` 等函数。
        """
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_motion_params(
            max_speed=max_speed,
            acceleration=acceleration,
            deceleration=deceleration,
        )

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
        kwargs = {}
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
    # 摄像头相关
    # ------------------------------------------------------------------

    def set_camera_id(self, camera_id: int) -> None:
        """
        更新内部使用的摄像头 ID。

        在 ROS2 / Web 环境下，如果你使用的是虚拟摄像头或不同设备号，可以通过此方法修改。
        """
        self.camera_id = camera_id
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        embodied_internal._set_camera_id(camera_id)

    def _capture_single_frame(self) -> Optional["cv2.Mat"]:
        """
        使用 OpenCV 从当前 `camera_id` 采集一帧图像。

        Returns:
            OpenCV 图像（numpy.ndarray），失败时返回 None。
        """
        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print(f" 无法打开摄像头 {self.camera_id}")
            cap.release()
            return None

        ok, frame = cap.read()
        cap.release()

        if not ok or frame is None:
            print(f" 从摄像头 {self.camera_id} 读取图像失败")
            return None

        return frame

    # ------------------------------------------------------------------
    # 像素 / 框选式基础视觉抓取（适配 ROS / 网页框选）
    # ------------------------------------------------------------------

    def set_grasp_params(self, **kwargs) -> None:
        """
        覆盖/更新全局抓取参数 (yaw, pitch, roll, tcp_offset_x/y/z, grasp_depth, etc.)。
        
        Args:
            **kwargs: 例如 (yaw=0.0, grasp_depth=270.0, tcp_offset_z=50.0)
        """
        if not hasattr(self, '_custom_grasp_params'):
            self._custom_grasp_params = {}
        self._custom_grasp_params.update(kwargs)
        
    def grasp_at_pixel(self, u: float, v: float) -> bool:
        """
        在给定相机像素坐标 (u, v) 的情况下，按照原有标定与抓取参数，抓取该点。

        用途：
        - Qt 桌面版：你现在用的是点击图像某点抓取，背后也是像素世界坐标IK电机；
        - ROS / 网页：可以在前端做框选/点击，把转换后的像素坐标传给这个函数。

        要求：
        - (u, v) 必须是**原始相机坐标系**下的像素坐标（与 `calibration_parameter.json` 的内参对应）。
        """
        # 1) 获取当前末端位姿（与 GUI 内部逻辑一致）
        embodied_internal = horizon_gateway.get_embodied_internal_module()
        current_pose = embodied_internal._get_current_arm_pose()
        if current_pose is None:
            print(" [GraspPixel] 机械臂未连接或无法获取当前位姿")
            return False

        # 2) 加载相机 / 手眼标定参数
        calib = None
        if hasattr(embodied_internal, "_load_calibration_params"):
            calib = embodied_internal._load_calibration_params()
        else:
            # 手动加载逻辑 (备用方案)：优先使用统一外置配置目录，其次回退到项目内 config
            import json
            import os
            try:
                config_path = ""
                # 1) 优先外置配置目录（run_gui/启动代码会设置 HORIZONARM_CONFIG_DIR）
                cfg_dir = os.environ.get("HORIZONARM_CONFIG_DIR", "").strip()
                if cfg_dir:
                    candidate = os.path.join(cfg_dir, "calibration_parameter.json")
                    if os.path.exists(candidate):
                        config_path = candidate
                # 2) 其次资源根目录（HORIZON_DATA_DIR/config）
                if not config_path:
                    data_root = os.environ.get("HORIZON_DATA_DIR", "").strip()
                    if data_root:
                        candidate = os.path.join(data_root, "config", "calibration_parameter.json")
                        if os.path.exists(candidate):
                            config_path = candidate
                # 3) 最后回退到项目内 config（假设 SDK 在 Embodied_SDK 目录下）
                if not config_path:
                    current_dir = os.path.dirname(os.path.abspath(__file__))
                    root_dir = os.path.dirname(current_dir)
                    candidate = os.path.join(root_dir, "config", "calibration_parameter.json")
                    if os.path.exists(candidate):
                        config_path = candidate

                if config_path and os.path.exists(config_path):
                    with open(config_path, "r", encoding="utf-8") as f:
                        calib = json.load(f)
                else:
                    print(" 无法找到标定文件: calibration_parameter.json")
            except Exception as e:
                print(f" 手动加载标定参数失败: {e}")

        if not calib:
            print(" [GraspPixel] 未找到标定参数 calibration_parameter.json")
            return False

        # 3) 读取全局抓取参数（姿态、TCP 偏移、深度）
        grasp = embodied_internal._get_grasp_params()
        
        #  合并自定义参数 (修复 ROS 模式下参数不同步的问题)
        if hasattr(self, '_custom_grasp_params') and self._custom_grasp_params:
            grasp.update(self._custom_grasp_params)
            
        tcp_x = grasp.get("tcp_offset_x", 0.0)
        tcp_y = grasp.get("tcp_offset_y", 0.0)
        tcp_z = grasp.get("tcp_offset_z", 0.0)
        
        # 4) 像素  基座坐标 (mm)，复用 embodied_internal 中的通用转换逻辑
        # 注意：embodied_internal._convert_pixel_to_world_coords 通常依赖 grasp dict 中的 grasp_depth 等信息，
        # 如果它内部没用 grasp dict 而是其他方式，这里可能需要 hack。
        # 假设 convert_pixel_to_world_coords 只做投影，Z值控制可能依赖 grasp_depth
        # 通常 convert 函数只返回投影后的 (x, y, z_surface)
        
        world = embodied_internal._convert_pixel_to_world_coords(
            u,
            v,
            calib,
            current_pose,
            tcp_x=tcp_x,
            tcp_y=tcp_y,
            tcp_z=tcp_z,
        )
        if world is None:
            print(" [GraspPixel] 像素坐标转换失败")
            return False

        x_w, y_w, z_w = world

        #  安全保护：避免极端标定导致 Z 轴为负值或过大
        try:
            z_w = float(z_w)
            min_z = float(grasp.get("min_z", 30.0))
            max_z = float(grasp.get("max_z", 600.0))
            if z_w < min_z:
                z_w = min_z
            elif z_w > max_z:
                z_w = max_z
        except Exception:
            pass

        # 5) 构造抓取姿态（完全沿用抓取参数里的 yaw/pitch/roll）
        yaw = grasp.get("yaw", 0.0)
        pitch = grasp.get("pitch", 0.0)
        roll = grasp.get("roll", 180.0)

        pos = [float(x_w), float(y_w), float(z_w)]
        ori = [float(yaw), float(pitch), float(roll)]

        print(f" [GraspPixel] 执行抓取: Pos={pos}, Ori={ori}")

        # 6) 调用已有的 c_a_p（末端位姿控制）执行抓取运动
        embodied_func = horizon_gateway.get_embodied_module()
        ok = embodied_func.c_a_p(pos, ori)
        return bool(ok)

    def grasp_at_bbox(
        self,
        x1: float,
        y1: float,
        x2: float,
        y2: float,
    ) -> bool:
        """
        根据手动框选的矩形框进行抓取：抓取点 = 框中心。

        用于 ROS / ROS2 / 网页场景：
        - 前端只需要提供相机画面，让用户用鼠标框选目标；
        - 把选框 (x1, y1, x2, y2) 像素坐标发给后端；
        - 后端调用本函数完成框中心  像素点  机械臂抓取。
        """
        cx = (float(x1) + float(x2)) * 0.5
        cy = (float(y1) + float(y2)) * 0.5
        return self.grasp_at_pixel(cx, cy)


class FollowGraspSDK(VisualGraspSDK):
    """
    跟随抓取 SDK 封装
    ==================

    将原先集成在界面里的检测+跟随+伺服逻辑抽离出来，
    作为独立的可调用模块，便于 ROS2 / Web 后端按需使用。

    - `configure_follow(...)`         配置跟随参数
    - `follow_step(frame, ...)`       在给定帧上执行一次检测+伺服
    - `start_follow_grasp(...)`       内部起线程，自动采图并连续跟随
    - `stop_follow_grasp()` / `is_following()`  控制/查询线程模式状态
    """

    def __init__(self, camera_id: int = 0):
        super().__init__(camera_id=camera_id)

        # 跟随相关内部状态（用于线程/单步两种模式）
        self._detector: Optional[YOLOOnnxDetector] = None
        self._follower: Optional[SingleObjectFollower] = None
        self._follow_target_class: str = "person(人)"
        self._follow_conf: float = 0.35
        self._follow_running: bool = False
        self._follow_thread: Optional[threading.Thread] = None
        # 手动框选跟踪器（CSRT/模板匹配，与 GUI 中 _create_manual_tracker 行为一致）
        self._manual_tracker = None
        self._manual_min_bbox: int = 24
        # 坐标补偿参数（与 GUI 中 follow_scale_x/y、follow_offset_x/y 含义一致）
        self._scale_x: float = 1.0
        self._scale_y: float = 1.0
        self._offset_x: float = 0.0
        self._offset_y: float = 0.0
        # 默认使用平面跟随——只改 XY，不改 Z，更安全
        self._follow_plane_mode: bool = True
        # 跟随循环的最大频率（单线程模式下）
        self._follow_interval: float = 0.1  # 10Hz

    # === 公共配置接口 ===

    def configure_follow(
        self,
        *,
        target_class: str = "person(人)",
        conf_thres: float = 0.35,
        plane_mode: bool = True,
        interval: float = 0.1,
        min_bbox: int = 24,
        scale_x: Optional[float] = None,
        scale_y: Optional[float] = None,
        offset_x: Optional[float] = None,
        offset_y: Optional[float] = None,
    ) -> None:
        """配置跟随抓取的基础参数。"""
        self._follow_target_class = target_class
        self._follow_conf = conf_thres
        self._follow_plane_mode = plane_mode
        self._follow_interval = max(0.02, float(interval))
        self._manual_min_bbox = int(max(8, min_bbox))
        if scale_x is not None:
            self._scale_x = float(scale_x)
        if scale_y is not None:
            self._scale_y = float(scale_y)
        if offset_x is not None:
            self._offset_x = float(offset_x)
        if offset_y is not None:
            self._offset_y = float(offset_y)

    def set_follow_compensation(
        self,
        *,
        scale_x: float = 1.0,
        scale_y: float = 1.0,
        offset_x: float = 0.0,
        offset_y: float = 0.0,
    ) -> None:
        """
        设置跟随坐标补偿参数：
        - scale_x/scale_y: XY 缩放系数（对应 GUI 中 follow_scale_x / follow_scale_y）
        - offset_x/offset_y: XY 平移偏移量（mm，对应 GUI 中 follow_offset_x / follow_offset_y）
        """
        self._scale_x = float(scale_x)
        self._scale_y = float(scale_y)
        self._offset_x = float(offset_x)
        self._offset_y = float(offset_y)

    # === 手动框选初始化（CSRT 跟随） ===

    def init_manual_target(self, frame: "cv2.Mat", x1: float, y1: float, x2: float, y2: float) -> bool:
        """
        使用手动框选区域初始化跟踪器（与 GUI 中手动CSRT逻辑一致）:
        - (x1,y1,x2,y2) 为图像坐标系下的框选区域；
        - 内部自动规范化为 (x,y,w,h) 并做最小尺寸保护；
        - 之后在 `follow_step(frame)` 中会使用该手动跟踪器进行更新。
        """
        try:
            if frame is None:
                return False

            h, w = frame.shape[:2]
            # 规范化坐标
            x1, x2 = float(min(x1, x2)), float(max(x1, x2))
            y1, y2 = float(min(y1, y2)), float(max(y1, y2))
            x1 = max(0.0, min(w - 1.0, x1))
            x2 = max(0.0, min(w - 1.0, x2))
            y1 = max(0.0, min(h - 1.0, y1))
            y2 = max(0.0, min(h - 1.0, y2))

            bw = max(x2 - x1, 1.0)
            bh = max(y2 - y1, 1.0)

            # 最小尺寸保护：与 GUI 中 follow_min_bbox_* 一致的思路
            min_size = float(self._manual_min_bbox)
            if bw < min_size or bh < min_size:
                cx = x1 + bw / 2.0
                cy = y1 + bh / 2.0
                bw = max(bw, min_size)
                bh = max(bh, min_size)
                x1 = max(0.0, min(w - bw, cx - bw / 2.0))
                y1 = max(0.0, min(h - bh, cy - bh / 2.0))

            bbox = (x1, y1, bw, bh)

            # 创建 CSRT / 模板匹配混合跟踪器（精简版 ManualTracker）
            self._manual_tracker = self._create_manual_tracker_like_gui()
            ok = self._manual_tracker.init(frame, bbox)
            return bool(ok)
        except Exception as e:
            print(f" [Follow] 手动框选初始化失败: {e}")
            return False

    # === ROS / Web 推荐：单步跟随接口 ===

    def follow_step(
        self,
        frame: "cv2.Mat",
        *,
        target_class: Optional[str] = None,
        conf_thres: Optional[float] = None,
    ) -> bool:
        """
        单步跟随：在给定一帧图像的情况下，完成一次检测/跟踪  伺服移动。
        """
        if target_class is not None:
            self._follow_target_class = target_class
        if conf_thres is not None:
            self._follow_conf = conf_thres

        # 1) 若存在手动跟踪器，则优先使用（对应 GUI 中手动框选模式）
        if self._manual_tracker is not None:
            ok, center = self._manual_tracker.update(frame)
        else:
            # 2) 否则使用 YOLO + 跟随器（对应 GUI 中YOLO检测模式）
            if not self._ensure_detector_and_follower():
                return False
            ok, center = self._follower.update(frame)  # type: ignore[arg-type]
        if not ok or center is None:
            return False

        cx, cy = center
        return self._apply_follow_servo(cx, cy)

    # === 内置线程模式：自己采图 + 跟随（可选用，不强制） ===

    def start_follow_grasp(
        self,
        *,
        target_class: Optional[str] = None,
        conf_thres: Optional[float] = None,
        interval: Optional[float] = None,
    ) -> None:
        """
        启动内部线程，持续从摄像头采集画面并执行跟随伺服。
        """
        if target_class is not None:
            self._follow_target_class = target_class
        if conf_thres is not None:
            self._follow_conf = conf_thres
        if interval is not None:
            self._follow_interval = max(0.02, float(interval))

        if self._follow_running:
            # 已在运行，直接返回
            return

        if not self._ensure_detector_and_follower():
            return

        self._follow_running = True

        def _loop():
            cap = cv2.VideoCapture(self.camera_id)
            if not cap.isOpened():
                print(f" [Follow] 无法打开摄像头 {self.camera_id}")
                self._follow_running = False
                cap.release()
                return

            print(f" [Follow] 启动跟随线程，target_class={self._follow_target_class}, conf={self._follow_conf}")
            try:
                while self._follow_running:
                    ok, frame = cap.read()
                    if not ok or frame is None:
                        print(" [Follow] 读取摄像头帧失败")
                        time.sleep(self._follow_interval)
                        continue

                    # 一步跟随
                    try:
                        self.follow_step(frame)
                    except Exception as e:
                        print(f" [Follow] 单步跟随异常: {e}")

                    time.sleep(self._follow_interval)
            finally:
                cap.release()
                self._follow_running = False
                print(" [Follow] 跟随线程已退出")

        self._follow_thread = threading.Thread(target=_loop, daemon=True)
        self._follow_thread.start()

    def stop_follow_grasp(self) -> None:
        """停止内部跟随线程。"""
        self._follow_running = False
        if self._follow_thread and self._follow_thread.is_alive():
            self._follow_thread.join(timeout=2.0)
        self._follow_thread = None

    def is_following(self) -> bool:
        """返回内部线程模式下是否正在跟随。"""
        return self._follow_running

    # ------------------------------------------------------------------
    # 内部辅助函数
    # ------------------------------------------------------------------

    def _ensure_detector_and_follower(self) -> bool:
        """懒加载 YOLO 检测器与单目标跟随器。"""
        # 如果当前在手动模式下（有 _manual_tracker），则不需要 YOLO
        if self._manual_tracker is not None:
            return True
        if self._detector is None:
            try:
                import os
                model_path = ""
                # 1) 优先统一外置配置目录（与 GUI 一致）
                cfg_dir = os.environ.get("HORIZONARM_CONFIG_DIR", "").strip()
                if cfg_dir:
                    candidate = os.path.join(cfg_dir, "yolov8n.onnx")
                    if os.path.exists(candidate):
                        model_path = candidate
                # 2) 其次资源根目录（HORIZON_DATA_DIR/config）
                if not model_path:
                    data_root = os.environ.get("HORIZON_DATA_DIR", "").strip()
                    if data_root:
                        candidate = os.path.join(data_root, "config", "yolov8n.onnx")
                        if os.path.exists(candidate):
                            model_path = candidate
                # 3) 最后回退相对路径（适配源码/自定义运行目录）
                if not model_path:
                    model_path = os.path.join("config", "yolov8n.onnx")

                self._detector = YOLOOnnxDetector(model_path)
            except Exception as e:
                print(f" [Follow] 加载 YOLO-ONNX 模型失败: {e}")
                self._detector = None
                return False

        # 若还没有跟随器，或类别/阈值发生变化，则重建跟随器
        if (
            self._follower is None
            or self._follower.target_class != self._follow_target_class
            or abs(self._follower.conf_thres - self._follow_conf) > 1e-6
        ):
            self._follower = SingleObjectFollower(
                self._detector,
                conf_thres=self._follow_conf,
                iou_thres=0.45,
                target_class=self._follow_target_class,
            )

        return True

    def _apply_follow_servo(self, pixel_x: float, pixel_y: float) -> bool:
        """
        将像素坐标作为跟随目标，执行一次简单的平面伺服：
        - 像素 (u,v)  基座坐标 (x,y,z)（使用全局抓取深度与手眼标定参数）；
        - 采用抓取参数中的 yaw/pitch/roll 作为姿态；
        - 通过 `c_a_p` 发送一次绝对位姿命令。
        """
        try:
            # 1) 获取当前机械臂末端位姿
            embodied_internal = horizon_gateway.get_embodied_internal_module()
            current_pose = embodied_internal._get_current_arm_pose()
            if current_pose is None:
                return False

            # 2) 加载相机标定参数
            calib = embodied_internal._load_calibration_params()
            if not calib:
                print(" [Follow] 未找到标定参数 calibration_parameter.json")
                return False

            # 3) 获取抓取参数（含 tcp_offset / 深度等）
            grasp = embodied_internal._get_grasp_params()
            tcp_x = grasp.get("tcp_offset_x", 0.0)
            tcp_y = grasp.get("tcp_offset_y", 0.0)
            tcp_z = grasp.get("tcp_offset_z", 0.0)

            # 4) 像素  世界坐标（单位：毫米）
            world = embodied_internal._convert_pixel_to_world_coords(
                pixel_x,
                pixel_y,
                calib,
                current_pose,
                tcp_x=tcp_x,
                tcp_y=tcp_y,
                tcp_z=tcp_z,
            )
            if world is None:
                return False

            x_w, y_w, z_w = world

            # 5) 应用与 GUI 一致的坐标补偿：先缩放，再偏移
            try:
                sx = float(self._scale_x)
                sy = float(self._scale_y)
                ox = float(self._offset_x)
                oy = float(self._offset_y)
            except Exception:
                sx, sy, ox, oy = 1.0, 1.0, 0.0, 0.0

            x_w = x_w * sx + ox
            y_w = y_w * sy + oy

            # 6) 简单平面模式：只改 XY，不改 Z（高度用当前的）
            if self._follow_plane_mode:
                target_pos = [float(x_w), float(y_w), float(current_pose[2])]
            else:
                target_pos = [float(x_w), float(y_w), float(z_w)]

            # 7) 姿态来自抓取参数（与视觉抓取保持一致）
            yaw = grasp.get("yaw", 0.0)
            pitch = grasp.get("pitch", 0.0)
            roll = grasp.get("roll", 180.0)
            target_ori = [float(yaw), float(pitch), float(roll)]

            # 8) 简单死区控制：如果位移很小就不动，避免抖动
            delta = np.linalg.norm(np.array(target_pos) - np.array(current_pose[:3], dtype=float))
            if delta < 2.0:  # 2mm 死区
                return False

            # 9) 直接调用 c_a_p 执行一次绝对运动
            embodied_func = horizon_gateway.get_embodied_module()
            ok = embodied_func.c_a_p(target_pos, target_ori)
            return bool(ok)

        except Exception as e:
            print(f" [Follow] 伺服控制失败: {e}")
            return False

    # ------------------------------------------------------------------
    # 手动跟踪器实现（参考 GUI 中 _create_manual_tracker / CSRT+模板匹配）
    # ------------------------------------------------------------------

    def _create_manual_tracker_like_gui(self):
        """
        精简版 ManualTracker：
        - 优先使用 OpenCV CSRT 跟踪器；
        - CSRT 初始化或更新失败时，退化为模板匹配；
        - 对外暴露 init(frame, bbox) / update(frame) 两个方法。
        """

        class _ManualTracker:
            def __init__(self, min_bbox: int = 24):
                self.tracker = None
                self.template = None
                self.last_center = None
                self.current_bbox = None  # x, y, w, h
                self._min_bbox = max(8, int(min_bbox))

            def _normalize_bbox(self, x, y, w, h, fw, fh):
                # 与 GUI 中 _normalize_bbox 类似：既不越界，又保证最小尺寸
                w = max(w, self._min_bbox)
                h = max(h, self._min_bbox)
                x = max(0, min(fw - w, x))
                y = max(0, min(fh - h, y))
                return x, y, w, h

            def init(self, frame, bbox):
                try:
                    fh, fw = frame.shape[:2]
                    x, y, w, h = bbox
                    x, y, w, h = self._normalize_bbox(int(x), int(y), int(w), int(h), fw, fh)

                    # 尝试创建 CSRT
                    if hasattr(cv2, "legacy") and hasattr(cv2.legacy, "TrackerCSRT_create"):
                        self.tracker = cv2.legacy.TrackerCSRT_create()
                    elif hasattr(cv2, "TrackerCSRT_create"):
                        self.tracker = cv2.TrackerCSRT_create()
                    else:
                        raise Exception("CSRT 跟踪器不可用")

                    ok = self.tracker.init(frame, (x, y, w, h))
                    if ok:
                        self.current_bbox = (x, y, w, h)
                        self.last_center = (x + w / 2.0, y + h / 2.0)
                        return True
                except Exception:
                    # 忽略 CSRT 初始化异常，后面用模板匹配兜底
                    pass

                # CSRT 不可用或初始化失败：退化为模板匹配
                try:
                    fh, fw = frame.shape[:2]
                    x, y, w, h = bbox
                    x, y, w, h = self._normalize_bbox(int(x), int(y), int(w), int(h), fw, fh)
                    tmpl = frame[y : y + h, x : x + w].copy()
                    if tmpl.size == 0:
                        return False
                    self.template = tmpl
                    self.current_bbox = (x, y, w, h)
                    self.last_center = (x + w / 2.0, y + h / 2.0)
                    return True
                except Exception:
                    return False

            def update(self, frame):
                # 优先使用 CSRT
                if self.tracker is not None:
                    try:
                        ok, bbox = self.tracker.update(frame)
                        if ok:
                            x, y, w, h = bbox
                            self.current_bbox = (x, y, w, h)
                            self.last_center = (x + w / 2.0, y + h / 2.0)
                            return True, self.last_center
                    except Exception:
                        pass

                # CSRT 失败时，使用模板匹配（若可用）
                if self.template is not None:
                    try:
                        fh, fw = frame.shape[:2]
                        th, tw = self.template.shape[:2]
                        if fh < th or fw < tw:
                            return False, None
                        res = cv2.matchTemplate(frame, self.template, cv2.TM_CCOEFF_NORMED)
                        _, max_val, _, max_loc = cv2.minMaxLoc(res)
                        if max_val < 0.4:  # 置信度阈值
                            return False, None
                        x, y = max_loc
                        x, y, w, h = self._normalize_bbox(x, y, tw, th, fw, fh)
                        self.current_bbox = (x, y, w, h)
                        self.last_center = (x + w / 2.0, y + h / 2.0)
                        return True, self.last_center
                    except Exception:
                        return False, None

                return False, None

        return _ManualTracker(self._manual_min_bbox)
