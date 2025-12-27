#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Joy-Con 机械臂控制测试程序
"""

import sys
import os
import time

# 添加项目路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.joycon_arm_controller import JoyConArmController, ControlMode

# 导入机械臂相关模块
try:
    from Control_SDK.Control_Core import ZDTMotorController
    from core.arm_core.kinematics import RobotKinematics
    from Main_UI.widgets.motor_config_manager import motor_config_manager
    from core.mujoco_arm_controller import MuJoCoArmController
    ARM_MODULES_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ 机械臂模块导入失败: {e}")
    ARM_MODULES_AVAILABLE = False


def clear_screen():
    """清空屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    """打印标题"""
    print("=" * 70)
    print(" " * 15 + "Joy-Con 机械臂控制系统")
    print("=" * 70)


def print_controls():
    """打印控制说明"""
    print("\n📋 控制说明:")
    print("─" * 70)
    print("【左 Joy-Con】(世界坐标系平移)")
    print("  摇杆      → 笛卡尔: 世界X/Y轴 | 关节: J1/J2")
    print("  L/ZL      → 笛卡尔: 世界Z轴   | 关节: J3")
    print("  方向键↑   → 控制关节5负向 (J5-) 🔧")
    print("  方向键↓   → 控制关节5正向 (J5+) 🔧")
    print("  方向键←→  → 控制关节6 (J6) 🔧")
    print("  - 按键    → 降低速度 🐌")
    print("  Capture   → 记录位置 💾")
    print("  摇杆按下  → 微调模式")
    print()
    print("【右 Joy-Con】(世界坐标系旋转)")
    print("  摇杆      → 笛卡尔: Roll/Pitch | 关节: J4/J5")
    print("  R/ZR      → 笛卡尔: Yaw        | 关节: J6")
    print("  A         → 关闭夹爪 ✊")
    print("  B         → 打开夹爪 ✋")
    print("  X         → 切换控制模式 ⭐")
    print("  Y         → 回到原点 🏠")
    print("  +         → 增加速度 ⚡")
    print("  HOME      → 紧急停止 🛑")
    print("─" * 70)


def print_status(controller: JoyConArmController):
    """打印状态信息"""
    status = controller.get_status()
    
    print("\n📊 当前状态:")
    print("─" * 70)
    
    # 控制模式
    mode_icon = "🌍" if status['control_mode'] == "笛卡尔模式" else "🔧"
    print(f"  模式: {mode_icon} {status['control_mode']}")
    
    # 运行状态
    if status['emergency_stopped']:
        state = "🛑 紧急停止"
    elif status['paused']:
        state = "⏸️  已暂停"
    elif status['running']:
        state = "▶️  运行中"
    else:
        state = "⏹️  已停止"
    print(f"  状态: {state}")
    
    # 速度
    print(f"  速度倍率: ⚡ {status['speed_multiplier']:.2f}x")
    
    # 微调模式
    fine_tune = "✅ 开启" if status['fine_tune_mode'] else "❌ 关闭"
    print(f"  微调模式: {fine_tune}")
    
    # 夹爪
    gripper = "✋ 打开" if status['gripper_open'] else "✊ 关闭"
    print(f"  夹爪状态: {gripper}")
    
    # 关节角度
    joints = status['current_joints']
    print(f"\n  关节角度 (度):")
    print(f"    J1:{joints[0]:+7.2f}  J2:{joints[1]:+7.2f}  J3:{joints[2]:+7.2f}")
    print(f"    J4:{joints[3]:+7.2f}  J5:{joints[4]:+7.2f}  J6:{joints[5]:+7.2f}")
    
    # 末端位置
    pos = status['current_position']
    ori = status['current_orientation']
    print(f"\n  末端位置 (mm):")
    print(f"    X:{pos[0]:+7.1f}  Y:{pos[1]:+7.1f}  Z:{pos[2]:+7.1f}")
    print(f"  末端姿态 (度):")
    print(f"    Roll:{ori[0]:+7.1f}  Pitch:{ori[1]:+7.1f}  Yaw:{ori[2]:+7.1f}")
    
    # 记录数
    if status['saved_count'] > 0:
        print(f"\n  💾 已记录位置: {status['saved_count']} 个")
    
    print("─" * 70)


def connect_arm():
    """连接机械臂"""
    print("\n🔌 连接机械臂...")
    
    if not ARM_MODULES_AVAILABLE:
        print("❌ 机械臂模块不可用")
        return None, None, None, None
    
    # 获取连接配置
    port = input("  串口号 (默认 COM18): ").strip() or "COM14"
    motor_ids_str = input("  电机ID (默认 1,2,3,4,5,6): ").strip() or "1,2,3,4,5,6"
    motor_ids = [int(x.strip()) for x in motor_ids_str.split(',')]
    
    print(f"\n  连接配置:")
    print(f"    串口: {port}")
    print(f"    电机ID: {motor_ids}")
    
    # 创建电机控制器
    motors = {}
    print("\n  正在连接电机...")
    
    for motor_id in motor_ids:
        try:
            print(f"    电机 {motor_id}...", end='', flush=True)
            motor = ZDTMotorController(
                motor_id=motor_id,
                interface_type="slcan",
                shared_interface=True,
                port=port,
                baudrate=500000
            )
            motor.connect()
            motors[motor_id] = motor
            print(" ✅")
        except Exception as e:
            print(f" ❌ {e}")
    
    if not motors:
        print("❌ 未连接任何电机")
        return None, None, None, None
    
    print(f"\n✅ 成功连接 {len(motors)} 个电机")
    
    # 创建运动学计算器
    print("\n  初始化运动学计算器...")
    try:
        kinematics = RobotKinematics()
        kinematics.set_angle_offset([0, 90, 0, 0, 0, 0])
        print("  ✅ 运动学计算器就绪")
    except Exception as e:
        print(f"  ⚠️ 运动学计算器初始化失败: {e}")
        kinematics = None
    
    # 创建MuJoCo控制器（可选）
    mujoco_controller = None
    try:
        use_mujoco = input("\n  是否启用MuJoCo仿真? (y/n, 默认n): ").strip().lower()
        if use_mujoco == 'y':
            mujoco_controller = MuJoCoArmController()
            print("  ✅ MuJoCo仿真已启用")
    except Exception as e:
        print(f"  ⚠️ MuJoCo初始化失败: {e}")
    
    return motors, motor_config_manager, kinematics, mujoco_controller


def main():
    """主函数"""
    clear_screen()
    print_header()
    print_controls()
    
    # 创建控制器
    controller = JoyConArmController()
    
    # 设置回调
    def on_status_message(msg):
        print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    
    controller.on_status_message = on_status_message
    
    # 连接Joy-Con
    print("\n🎮 连接Joy-Con手柄...")
    left_ok, right_ok = controller.connect_joycon()
    
    if not left_ok and not right_ok:
        print("❌ 未找到Joy-Con，请确保已通过蓝牙配对")
        print("\n提示:")
        print("  1. 打开Windows蓝牙设置")
        print("  2. 按住Joy-Con的同步按钮（侧面小圆按钮）")
        print("  3. 等待配对完成后重新运行程序")
        return
    
    print(f"✅ Joy-Con连接成功")
    print(f"   左手柄: {'✅' if left_ok else '❌'}")
    print(f"   右手柄: {'✅' if right_ok else '❌'}")
    
    # 询问是否连接机械臂
    print("\n" + "=" * 70)
    connect = input("是否连接机械臂? (y/n, 默认n): ").strip().lower()
    
    if connect == 'y':
        motors, config_mgr, kinematics, mujoco = connect_arm()
        
        if motors and config_mgr and kinematics:
            controller.set_arm(motors, config_mgr, kinematics, mujoco)
            print("\n✅ 机械臂设置完成")
            
            # 同步当前位置
            print("\n📍 同步当前位置...")
            controller.sync_current_joint_angles()
            
            # 启动控制
            print("\n" + "=" * 70)
            input("按 Enter 键启动Joy-Con控制...")
            controller.start()
        else:
            print("\n❌ 机械臂连接失败，仅演示Joy-Con输入")
    else:
        print("\n⚠️ 未连接机械臂，仅演示Joy-Con输入")
    
    # 主循环
    print("\n" + "=" * 70)
    print("Joy-Con控制已启动！")
    print("按 Ctrl+C 退出")
    print("=" * 70)
    
    try:
        last_update = time.time()
        update_interval = 1.0  # 每秒更新一次显示
        
        while True:
            current_time = time.time()
            
            # 定期更新显示
            if current_time - last_update >= update_interval:
                clear_screen()
                print_header()
                print_status(controller)
                print("\n💡 提示: 按 Ctrl+C 退出")
                last_update = current_time
            
            time.sleep(0.1)
            
    except KeyboardInterrupt:
        print("\n\n⏹️ 正在停止...")
        controller.stop()
        controller.disconnect_joycon()
        
        # 显示记录的位置
        saved_positions = controller.get_saved_positions()
        if saved_positions:
            print(f"\n💾 本次记录了 {len(saved_positions)} 个位置:")
            for i, pos_info in enumerate(saved_positions, 1):
                joints = pos_info['joints']
                print(f"  {i}. J=[{', '.join([f'{j:.1f}' for j in joints])}]")
        
        print("\n👋 程序已退出")


if __name__ == "__main__":
    main()

