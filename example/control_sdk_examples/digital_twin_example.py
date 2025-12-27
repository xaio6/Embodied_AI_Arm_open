#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
数字孪生 (MuJoCo仿真) 功能指南
==========================================

本示例展示了如何使用 Embodied_SDK 的 DigitalTwinSDK (数字孪生) 模块。
此模块允许在没有物理机械臂的情况下，在 MuJoCo 物理引擎中仿真机械臂的运动。

核心概念：
1. **Digital Twin (数字孪生)**: 这里的含义是将控制指令发送到虚拟模型，而非真实硬件。
2. **Kinematics (运动学)**: 仿真器主要用于验证正/逆运动学解算和轨迹规划。
3. **无需硬件**: 此脚本可在纯软件环境下运行。

应用场景：
- 算法验证：在仿真中测试运动规划算法
- 轨迹预览：可视化机械臂运动路径
- 离线开发：没有硬件时也能开发调试
- 教学演示：安全地演示机械臂功能

前置条件：
- 已安装 mujoco 库 (pip install mujoco)
- 已安装 numpy 库 (pip install numpy)

SDK API:
- `sdk.start_simulation()`: 启动 MuJoCo 查看器窗口
- `sdk.set_joint_angles(angles)`: 直接设置虚拟机械臂的关节角度
- `sdk.move_joints(target, duration)`: 生成轨迹并平滑移动到目标
- `sdk.execute_preset_action(name)`: 执行预设动作
"""

import os
import sys
import time
import numpy as np

# 添加项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embodied_SDK.digital_twin import DigitalTwinSDK

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 70)
    print(" 🦾 数字孪生 (MuJoCo仿真) 功能指南")
    print("=" * 70)
    print("本程序将启动 MuJoCo 物理仿真窗口。")
    print("您可以在不连接真实机械臂的情况下测试运动逻辑。")
    print("提示：请确保已安装 `mujoco` 和 `numpy` 库。")
    print("=" * 70)

def demo_auto_wave(sdk):
    """
    自动波形演示
    
    原理：
    - 使用正弦函数生成连续变化的关节角度。
    - 高频调用 `set_joint_angles` 更新仿真模型姿态。
    - 这展示了 SDK 的低延迟控制能力。
    """
    print("\n🌊 自动波形演示")
    print("-" * 30)
    print("机械臂 J1 和 J2 关节将进行正弦摆动。")
    print("观察仿真窗口中的运动...")
    print("按 Ctrl+C 停止演示。")
    input("按 Enter 开始...")
    
    print("🚀 正在运行波形控制...")
    try:
        start_time = time.time()
        while sdk.is_running():
            t = time.time() - start_time
            
            # 计算目标角度
            # J1: 幅度 +/- 45度, 频率 0.5Hz
            angle_j1 = 45 * np.sin(2 * np.pi * 0.5 * t)
            
            # J2: 幅度 +/- 20度, 频率 0.25Hz, 偏置 45度(避免碰撞地面)
            angle_j2 = 20 * np.sin(2 * np.pi * 0.25 * t) + 45 
            
            # 组合 6 个关节的角度 (其他保持 0)
            target = [angle_j1, angle_j2, 0, 0, 0, 0]
            
            # 核心调用：更新仿真模型
            sdk.set_joint_angles(target)
            
            # 维持约 100Hz 更新率
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        print("\n✅ 停止演示")

def demo_preset_action(sdk):
    """
    预设动作演示
    
    原理：
    - SDK 内置了一些常用的姿态 (如 Home, Wave)。
    - `execute_preset_action` 会自动规划轨迹并执行。
    """
    print("\n🎬 预设动作演示")
    print("-" * 30)

    # 动态读取配置
    actions = []
    try:
        import json
        cfg_path = os.path.join(project_root, "config", "embodied_config", "preset_actions.json")
        if os.path.exists(cfg_path):
            data = json.load(open(cfg_path, "r", encoding="utf-8"))
            if isinstance(data, dict):
                actions = list(data.keys())
    except Exception:
        pass

    # 别名映射
    alias = {}
    if "初始位置" in actions: alias["home"] = "初始位置"
    if "挥手" in actions: alias["wave"] = "挥手"

    if actions:
        print("可用动作：")
        for i, name in enumerate(actions, 1):
            print(f"  {i}. {name}")
        print("  0. 返回")
        
        choice = input("\n请选择序号或输入动作名: ").strip()
        if choice == "0" or not choice:
            return
        if choice.isdigit():
            idx = int(choice)
            if idx < 1 or idx > len(actions):
                print("❌ 无效选择")
                return
            action = actions[idx - 1]
        else:
            action = alias.get(choice.lower(), choice)
    else:
        # 兜底
        print("  1. Home (归零 - 直立状态)")
        print("  2. Wave (挥手 - 示例动作)")
        choice = input("请选择动作 (1-2): ").strip()
        action = None
        if choice == '1': action = "home"
        elif choice == '2': action = "wave"
    
    if action:
        print(f"🚀 执行动作: '{action}'...")
        # 核心调用：执行预设
        sdk.execute_preset_action(action)
        
        # 简单等待动作完成 (实际应用中可查询状态)
        time.sleep(2)
        print("✅ 动作完成")
    else:
        print("❌ 无效选择")

def demo_random_pose(sdk):
    """
    随机姿态演示
    
    原理：
    - 在安全范围内随机生成 6 个关节角度。
    - 使用 `move_joints` 进行带插值的平滑运动。
    """
    print("\n🎲 随机姿态演示")
    print("-" * 30)
    
    # 生成随机目标 (限制在 +/- 45度以保证视觉上的安全感)
    target = list(np.random.uniform(-45, 45, 6))
    # 将 J2 抬起一点，避免碰到地板
    target[1] += 30 
    
    target_str = ", ".join([f"{x:.1f}" for x in target])
    print(f"目标关节角: [{target_str}]")
    
    print("🚀 开始移动 (耗时 1.5s)...")
    # 核心调用：平滑移动
    sdk.move_joints(target, duration=1.5)
    
    time.sleep(1.5)
    print("✅ 到达目标")

def main():
    clear_screen()
    print_header()

    print("\n[1/2] 正在启动 MuJoCo 仿真器...")
    try:
        sdk = DigitalTwinSDK()
        if not sdk.start_simulation():
            print("❌ 仿真启动失败")
            print("可能原因：")
            print("1. 未安装 mujoco 库 (pip install mujoco)")
            print("2. 模型文件 (xml) 路径错误")
            input("按 Enter 退出...")
            return
        print("✅ 仿真已启动 (请查看弹出的窗口)")
    except Exception as e:
        print(f"❌ 初始化异常: {e}")
        return

    while True:
        # 检查仿真窗口是否被用户手动关闭
        if not sdk.is_running():
            print("\n⚠️  仿真窗口已关闭，程序结束。")
            break

        print("\n📋 功能菜单:")
        print("  1. 自动波形演示 (Auto Wave - 连续控制)")
        print("  2. 执行预设动作 (Preset Action - 离散动作)")
        print("  3. 移动到随机姿态 (Random Pose - 轨迹规划)")
        print("  0. 退出程序")
        
        choice = input("\n请选择 (0-3): ").strip()
        
        if choice == '0':
            print("👋 正在停止仿真...")
            break
        elif choice == '1':
            demo_auto_wave(sdk)
        elif choice == '2':
            demo_preset_action(sdk)
        elif choice == '3':
            demo_random_pose(sdk)
        else:
            print("❌ 无效选择")

    sdk.stop_simulation()
    print("程序已安全退出。")

if __name__ == "__main__":
    main()

