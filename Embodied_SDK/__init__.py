#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embodied_SDK
============

面向网页 / ROS2 / 脚本调用的高层具身智能机械臂 SDK。

设计目标：
- **统一入口**：将项目中已有的视觉抓取、具身智能决策、IO 作业等高级能力，以纯 Python 接口方式暴露出来；
- **与 GUI 解耦**：SDK 不依赖 PyQt5 界面，可在 Ubuntu + ROS2、后端 Web 服务等环境中直接调用；
- **可渐进扩展**：当前优先封装视觉抓取相关能力，后续可以逐步把示教器、数字孪生、IO 作业等模块迁移进来。

当前已提供的模块：
- `visual_grasp.VisualGraspSDK`：基于现有标定 / 像素坐标转换与 `c_a_p` 的基础视觉抓取（点/框中心）高层封装；
- `visual_grasp.FollowGraspSDK`：基于 YOLOv8 + CSRT/跟踪器的连续视觉伺服/跟随抓取高层封装；
- `motion.MotionSDK`：基于 `c_a_j` / `c_a_p` / `e_p_a` 的机械臂基础运动控制封装；
- `embodied.EmbodiedSDK`：基于 `HierarchicalDecisionSystem` 的具身智能高层封装（自然语言任务 -> 动作序列）；
- `joycon.JoyconSDK`：基于 `JoyConArmController` 的手柄控制封装；
- `io.IOSDK`：基于 `ESP32IOController` 的 IO / 外设控制封装；
- `digital_twin.DigitalTwinSDK`：基于 MuJoCo 的数字孪生运动控制封装（仿真端）；
- `horizon_sdk.HorizonArmSDK`：顶层聚合 SDK，一次性绑定电机/相机，对外统一暴露各类功能入口（vision/follow/motion/embodied/joycon/io/digital_twin/...）。

后续规划（示例）：
- `motion`：关节/末端运动基础封装
- `tasks`：具身智能任务规划封装
- `io`：IO 作业与外部设备交互封装
"""

from .visual_grasp import VisualGraspSDK, FollowGraspSDK
from .motion import MotionSDK
from .embodied import EmbodiedSDK
from .joycon import JoyconSDK
from .io import IOSDK
from .digital_twin import DigitalTwinSDK
from .horizon_sdk import HorizonArmSDK
from .ai import AISDK, DepthEstimationSDK
from .motion import MotionSDK, create_motor_controller, setup_logging, close_all_shared_interfaces, get_shared_interface_info, get_function_codes

__all__ = [
    "VisualGraspSDK",
    "FollowGraspSDK",
    "MotionSDK",
    "EmbodiedSDK",
    "JoyconSDK",
    "IOSDK",
    "DigitalTwinSDK",
    "HorizonArmSDK",
    "AISDK",
    "DepthEstimationSDK",
    "create_motor_controller",
    "setup_logging",
    "close_all_shared_interfaces",
    "get_shared_interface_info",
    "get_function_codes",
]
