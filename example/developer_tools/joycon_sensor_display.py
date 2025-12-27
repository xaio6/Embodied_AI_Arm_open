#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Joy-Con 传感器深度监控工具
==================================

这是一个专业调试工具，用于查看Joy-Con的底层传感器数据。
适合需要校准摇杆死区或调试IMU的高级用户。

原文件: test_joycon_display.py (已移至开发者工具)

功能：
1. 显示摇杆原始模拟值
2. 显示IMU (陀螺仪/加速度计) 数据
3. 显示详细的按键状态
4. 显示电池电量

用途：
- 摇杆死区 (Deadzone) 校准
- IMU 漂移检测
- 开发者理解 Joy-Con HID 报告格式
"""

import os
import sys
import time

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Embodied_SDK.joycon import JoyconSDK

def clear_screen():
    """清空终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    sdk = JoyconSDK()
    
    print("正在连接Joy-Con...")
    left_ok, right_ok = sdk.connect_joycon()
    
    if not left_ok and not right_ok:
        print("❌ 未找到Joy-Con，请确保已通过蓝牙配对")
        print("\n提示：")
        print("1. 打开电脑蓝牙设置")
        print("2. 同时按住Joy-Con的同步按钮（侧面小圆按钮）")
        print("3. 等待配对完成后重新运行程序")
        return
    
    if not left_ok:
        print("⚠️  未找到左Joy-Con")
    if not right_ok:
        print("⚠️  未找到右Joy-Con")
    
    print(f"\n✅ 连接成功")
    print(f"左手柄: {'已连接' if left_ok else '未连接'}")
    print(f"右手柄: {'已连接' if right_ok else '未连接'}")
    
    input("\n按 Enter 开始监控数据...")
    
    try:
        frame_count = 0
        while True:
            clear_screen()
            print("=" * 70)
            print(" 🎮 Joy-Con 传感器深度监控 (开发者工具)")
            print("=" * 70)
            print(f"Frame: {frame_count}  |  Ctrl+C 退出")
            print()
            
            # 左Joy-Con状态
            if left_ok:
                left_status = sdk.get_left_joycon_status()
                if left_status:
                    print("【左 Joy-Con (L)】")
                    print(f"  🔋 电池: {left_status.get('battery', 'Unknown')}")
                    
                    print("  🎮 摇杆 (Analog):")
                    stick = left_status.get('analog_stick', {})
                    h, v = stick.get('horizontal', 0), stick.get('vertical', 0)
                    print(f"    H: {h:6d} | V: {v:6d}")
                    print(f"    死区建议: H±2000, V±2000")
                    
                    print("  🧭 陀螺仪 (IMU):")
                    gyro = left_status.get('gyro', {})
                    if gyro:
                        print(f"    X: {gyro.get('x', 0):6d}  Y: {gyro.get('y', 0):6d}  Z: {gyro.get('z', 0):6d}")
                    else:
                        print("    无数据")

                    print("  🔘 按键:")
                    buttons = left_status.get('buttons', {})
                    active_btns = [k for k, v in buttons.items() if v]
                    if active_btns:
                        print(f"    {' '.join(active_btns)}")
                    else:
                        print("    (无)")
            
            print("-" * 70)
            
            # 右Joy-Con状态
            if right_ok:
                right_status = sdk.get_right_joycon_status()
                if right_status:
                    print("【右 Joy-Con (R)】")
                    print(f"  🔋 电池: {right_status.get('battery', 'Unknown')}")
                    
                    print("  🎮 摇杆 (Analog):")
                    stick = right_status.get('analog_stick', {})
                    h, v = stick.get('horizontal', 0), stick.get('vertical', 0)
                    print(f"    H: {h:6d} | V: {v:6d}")
                    print(f"    死区建议: H±2000, V±2000")
                    
                    print("  🧭 陀螺仪 (IMU):")
                    gyro = right_status.get('gyro', {})
                    if gyro:
                        print(f"    X: {gyro.get('x', 0):6d}  Y: {gyro.get('y', 0):6d}  Z: {gyro.get('z', 0):6d}")
                    else:
                        print("    无数据")

                    print("  🔘 按键:")
                    buttons = right_status.get('buttons', {})
                    active_btns = [k for k, v in buttons.items() if v]
                    if active_btns:
                        print(f"    {' '.join(active_btns)}")
                    else:
                        print("    (无)")
            
            print("=" * 70)
            
            frame_count += 1
            time.sleep(0.1)  # 10Hz 刷新
            
    except KeyboardInterrupt:
        print("\n\n退出程序")
    finally:
        sdk.disconnect_joycon()


if __name__ == "__main__":
    main()

