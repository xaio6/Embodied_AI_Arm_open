#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
HorizonArm SDK 5分钟快速入门
================================

本程序是您使用 HorizonArm SDK 的第一站！
在5分钟内，您将体验到：
✅ 连接一台电机
✅ 读取电机位置和状态
✅ 执行简单的运动控制
✅ 了解SDK的核心概念

完成后，程序会引导您到更详细的示例。

推荐学习路径：
1. quickstart_guide.py (本文件) ← 您在这里
2. control_sdk_examples/motor_usage_example.py (单电机完全指南)
3. control_sdk_examples/motion_usage_example.py (运动控制详解)
4. 其他进阶示例...
"""

import os
import sys
import time

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from Embodied_SDK import create_motor_controller

def clear_screen():
    """清屏"""
    os.system('cls' if os.name == 'nt' else 'clear')

def print_welcome():
    """打印欢迎界面"""
    clear_screen()
    print("=" * 70)
    print(" 🚀 欢迎使用 HorizonArm SDK - 5分钟快速入门")
    print("=" * 70)
    print("\n本程序将引导您完成SDK的第一次体验。")
    print("整个过程大约需要5分钟。\n")
    print("⚠️  开始前请确保：")
    print("  1. 至少有一台电机已上电")
    print("  2. 串口线 (USB-CAN) 已连接到电脑")
    print("  3. 机械臂活动空间无障碍物")
    print("=" * 70)

def step1_connect_motor():
    """步骤1: 连接电机"""
    print("\n" + "="*70)
    print(" 📡 步骤 1/4: 连接电机")
    print("="*70)
    
    print("\n💡 知识点: 电机连接")
    print("  - HorizonArm使用CAN总线通信，每个电机有唯一ID (1-255)")
    print("  - 通过串口适配器(如USB-CAN)连接到电脑")
    print("  - 默认波特率: 500000 (500k)")
    
    # 输入连接参数
    port = input("\n请输入串口号 (默认 COM14): ").strip() or "COM14"
    motor_id = input("请输入要连接的电机ID (默认 1): ").strip()
    motor_id = int(motor_id) if motor_id else 1
    
    print(f"\n正在连接电机 ID={motor_id} 在端口 {port}...")
    
    try:
        # 核心API: 创建电机控制器
        motor = create_motor_controller(
            motor_id=motor_id,
            port=port,
            baudrate=500000
        )
        
        # 核心API: 建立连接
        motor.connect()
        
        print(f"✅ 电机 {motor_id} 连接成功！")
        return motor, motor_id
        
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        print("\n📖 故障排除：")
        print("  1. 检查串口号是否正确 (设备管理器查看)")
        print("  2. 检查电机ID是否正确")
        print("  3. 确认电机已上电")
        print("  4. 确认没有其他程序占用串口")
        return None, None

def step2_read_status(motor, motor_id):
    """步骤2: 读取电机状态"""
    print("\n" + "="*70)
    print(" 📊 步骤 2/4: 读取电机状态")
    print("="*70)
    
    print("\n💡 知识点: 电机状态参数")
    print("  - 位置(Position): 电机当前角度，单位：度")
    print("  - 速度(Speed): 电机当前转速，单位：RPM")
    print("  - 温度(Temperature): 驱动器温度，单位：℃")
    print("  - 使能状态(Enabled): 电机是否激活并能接受控制")
    
    input("\n按 Enter 键读取状态...")
    
    try:
        # 核心API: 读取各种参数
        position = motor.read_parameters.get_position()
        speed = motor.read_parameters.get_speed()
        temperature = motor.read_parameters.get_temperature()
        status = motor.read_parameters.get_motor_status()
        version = motor.read_parameters.get_version()
        
        print(f"\n📈 电机 {motor_id} 当前状态:")
        print(f"  位置:   {position:.2f}°")
        print(f"  速度:   {speed:.2f} RPM")
        print(f"  温度:   {temperature:.1f}℃")
        print(f"  使能:   {'是' if status.enabled else '否'}")
        print(f"  固件:   {version['firmware']}")
        
        print("\n✅ 状态读取成功！")
        return True
        
    except Exception as e:
        print(f"❌ 读取失败: {e}")
        return False

def step3_enable_motor(motor, motor_id):
    """步骤3: 使能电机"""
    print("\n" + "="*70)
    print(" ⚡ 步骤 3/4: 使能电机")
    print("="*70)
    
    print("\n💡 知识点: 电机使能")
    print("  - 使能(Enable)后，电机才能响应运动指令")
    print("  - 使能后电机会保持当前位置(有保持力矩)")
    print("  - ⚠️  警告：如果电机没有刹车，失能后会掉落损坏！")
    print("  - 停止运动请使用 stop()，不要轻易使用 disable()")
    
    # 检查是否已使能
    try:
        status = motor.read_parameters.get_motor_status()
        if status.enabled:
            print(f"\n✅ 电机 {motor_id} 已经是使能状态")
            return True
    except:
        pass
    
    choice = input("\n是否使能电机? (Y/n): ").strip().lower()
    if choice == 'n':
        print("⚠️  跳过使能，将无法执行运动测试")
        return False
    
    try:
        # 核心API: 使能电机
        motor.control_actions.enable()
        time.sleep(0.5)
        
        # 验证使能状态
        status = motor.read_parameters.get_motor_status()
        if status.enabled:
            print(f"✅ 电机 {motor_id} 使能成功！")
            return True
        else:
            print("⚠️  使能命令已发送，但状态未确认")
            return False
            
    except Exception as e:
        print(f"❌ 使能失败: {e}")
        return False

def step4_simple_motion(motor, motor_id):
    """步骤4: 简单运动测试"""
    print("\n" + "="*70)
    print(" 🎯 步骤 4/4: 简单运动测试")
    print("="*70)
    
    print("\n💡 知识点: 位置模式运动")
    print("  - 位置模式: 电机移动到指定角度后自动停止")
    print("  - 绝对位置: 移动到角度X（如 90°）")
    print("  - 相对位置: 在当前位置基础上移动X度（如 当前+45°）")
    print("  - 运动过程采用梯形速度曲线，平滑可控")
    
    print("\n⚠️  安全提示：")
    print("  - 电机即将运动，请确保周围无障碍物")
    print("  - 运动幅度：±30度（安全范围）")
    print("  - 如需紧急停止，请准备好切断电源")
    
    choice = input("\n是否执行运动测试? (y/N): ").strip().lower()
    if choice != 'y':
        print("已跳过运动测试")
        return False
    
    try:
        # 读取当前位置
        current_pos = motor.read_parameters.get_position()
        print(f"\n当前位置: {current_pos:.2f}°")
        
        # 计算目标位置（相对运动+30度）
        target_pos = current_pos + 30.0
        print(f"目标位置: {target_pos:.2f}° (相对移动 +30°)")
        
        print("\n🚀 开始运动...")
        
        # 核心API: 位置运动控制
        motor.control_actions.move_to_position(
            position=target_pos,
            speed=300,  # 速度 300 RPM (较慢，安全)
            is_absolute=True  # 绝对位置模式
        )
        
        # 等待到位
        print("等待到位...", end='', flush=True)
        timeout = 10.0
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status = motor.read_parameters.get_motor_status()
            pos = motor.read_parameters.get_position()
            
            if status.in_position:
                print(" 完成！")
                print(f"✅ 已到位！当前位置: {pos:.2f}°")
                print(f"   运动耗时: {time.time() - start_time:.1f}秒")
                return True
            
            time.sleep(0.1)
            print(".", end='', flush=True)
        
        print("\n⚠️  超时：电机可能未到位")
        return False
        
    except Exception as e:
        print(f"❌ 运动失败: {e}")
        return False

def show_next_steps():
    """显示下一步学习建议"""
    print("\n" + "="*70)
    print(" 🎓 恭喜！您已完成快速入门")
    print("="*70)
    
    print("\n接下来您可以探索：")
    print("\n📚 详细示例（推荐学习顺序）：")
    print("  1. control_sdk_examples/motor_usage_example.py")
    print("     → 单电机完全指南（速度/力矩/回零等）")
    print("  ")
    print("  2. control_sdk_examples/motion_usage_example.py")
    print("     → 多关节运动控制（基于sdk_quickstart重构）")
    print("  ")
    print("  3. control_sdk_examples/visual_grasp_example.py")
    print("     → 视觉抓取功能")
    print("  ")
    print("  4. control_sdk_examples/joycon_control_example.py")
    print("     → 手柄遥操作")
    
    print("\n🔧 配置和工具：")
    print("  - ai_sdk_examples/config_example.py (配置管理)")
    print("  - developer_tools/ (开发者调试工具)")
    
    print("\n📖 文档：")
    print("  - docs/quickstart.md (详细入门教程)")
    print("  - docs/sdk_reference/control_sdk.md (完整API参考)")
    print("  - docs/troubleshooting.md (常见问题)")
    
    print("\n" + "="*70)

def main():
    """主流程"""
    print_welcome()
    
    input("\n准备好了吗？按 Enter 键开始...")
    
    # 步骤1: 连接电机
    motor, motor_id = step1_connect_motor()
    if not motor:
        print("\n❌ 无法继续，请检查连接后重试")
        input("\n按 Enter 键退出...")
        return
    
    input("\n✅ 第一步完成！按 Enter 继续...")
    
    # 步骤2: 读取状态
    if not step2_read_status(motor, motor_id):
        print("\n⚠️  读取失败，但可以继续")
    
    input("\n按 Enter 继续...")
    
    # 步骤3: 使能电机
    enabled = step3_enable_motor(motor, motor_id)
    
    input("\n按 Enter 继续...")
    
    # 步骤4: 运动测试
    if enabled:
        step4_simple_motion(motor, motor_id)
    else:
        print("\n⚠️  电机未使能，跳过运动测试")
    
    # 显示下一步
    show_next_steps()
    
    # 清理
    try:
        print("\n正在断开连接...")
        motor.disconnect()
        print("✅ 已断开连接")
    except:
        pass
    
    input("\n按 Enter 键退出...")

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被中断")
    except Exception as e:
        print(f"\n❌ 发生错误: {e}")
        import traceback
        traceback.print_exc()

