#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Joy-Con 按键和摇杆显示"""

import os
import sys
import time

# 添加项目根目录到路径
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

from core.joycon_map import JoyConMap


def clear_screen():
    """清空终端屏幕"""
    os.system('cls' if os.name == 'nt' else 'clear')


def main():
    controller = JoyConMap()
    
    print("正在连接Joy-Con...")
    left_ok, right_ok = controller.connect_both()
    
    if not left_ok and not right_ok:
        print("❌ 未找到Joy-Con，请确保已通过蓝牙配对")
        print("\n提示：")
        print("1. 打开电脑蓝牙设置")
        print("2. 同时按住Joy-Con的同步按钮（侧面小圆按钮）")
        print("3. 等待配对完成后重新运行程序")
        return
    
    if not left_ok:
        print("⚠️ 未找到左Joy-Con")
    if not right_ok:
        print("⚠️ 未找到右Joy-Con")
    
    print(f"\n连接成功！")
    print(f"左手柄: {'✅ 已连接' if left_ok else '❌ 未连接'}")
    print(f"右手柄: {'✅ 已连接' if right_ok else '❌ 未连接'}")
    
    # 设置指示灯
    if left_ok:
        controller.set_player_light('left', 0b0001)
    if right_ok:
        controller.set_player_light('right', 0b1000)
    
    time.sleep(1)
    
    try:
        frame_count = 0
        while True:
            clear_screen()
            print("=" * 60)
            print("Joy-Con 状态监控 (按 Ctrl+C 退出)")
            print("=" * 60)
            print(f"刷新次数: {frame_count}")
            print()
            
            # 左Joy-Con状态
            if left_ok:
                left_status = controller.get_left_status()
                if left_status:
                    print("【左 Joy-Con】")
                    print(f"  电池: {left_status['battery']}")
                    print()
                    
                    print("  按键状态:")
                    buttons = left_status['buttons']
                    for btn, pressed in buttons.items():
                        status = "■ 按下" if pressed else "□ 松开"
                        print(f"    {btn:12s}: {status}")
                    
                    print()
                    print("  摇杆:")
                    stick = left_status['analog_stick']
                    h, v = stick['horizontal'], stick['vertical']
                    print(f"    横向: {h:6d}")
                    print(f"    纵向: {v:6d}")
                    
                    # 陀螺仪
                    gyro = left_status.get('gyro', {})
                    if gyro:
                        print()
                        print("  陀螺仪:")
                        print(f"    x: {gyro.get('x', 0):6d}")
                        print(f"    y: {gyro.get('y', 0):6d}")
                        print(f"    z: {gyro.get('z', 0):6d}")
            
            print()
            print("-" * 60)
            print()
            
            # 右Joy-Con状态
            if right_ok:
                right_status = controller.get_right_status()
                if right_status:
                    print("【右 Joy-Con】")
                    print(f"  电池: {right_status['battery']}")
                    print()
                    
                    print("  按键状态:")
                    buttons = right_status['buttons']
                    for btn, pressed in buttons.items():
                        status = "■ 按下" if pressed else "□ 松开"
                        print(f"    {btn:12s}: {status}")
                    
                    print()
                    print("  摇杆:")
                    stick = right_status['analog_stick']
                    h, v = stick['horizontal'], stick['vertical']
                    print(f"    横向: {h:6d}")
                    print(f"    纵向: {v:6d}")
                    
                    # 陀螺仪
                    gyro = right_status.get('gyro', {})
                    if gyro:
                        print()
                        print("  陀螺仪:")
                        print(f"    x: {gyro.get('x', 0):6d}")
                        print(f"    y: {gyro.get('y', 0):6d}")
                        print(f"    z: {gyro.get('z', 0):6d}")
            
            print()
            print("=" * 60)
            
            frame_count += 1
            time.sleep(0.05)
            
    except KeyboardInterrupt:
        print("\n\n退出程序")
    finally:
        controller.disconnect()


if __name__ == "__main__":
    main()

