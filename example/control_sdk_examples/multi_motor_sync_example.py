#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
多电机同步控制入门
==========================================

本示例是 test_multi_motor_sync.py 的**简化教学版**，专注于核心同步功能。

🎯 与完整版的区别：
  完整版 (test_multi_motor_sync.py): 40+功能，适合专业开发
  简化版 (本文件): 3核心功能，适合快速学习

核心功能：
1. **同步位置控制**: 多个电机同时移动到目标位置
2. **同步速度控制**: 多个电机同时以指定速度旋转
3. **同步回零**: 多个电机同时执行回零动作

原理说明：
ZDT协议的同步控制分为三个阶段：
  Phase 1 - Pre-load:  向各电机发送带同步标志的指令（不立即执行）
  Phase 2 - Trigger:   发送广播触发命令 (ID=0)
  Phase 3 - Execute:   所有电机同时开始执行

适合人群：
- 需要多轴同步运动的开发者
- 学习ZDT同步协议的工程师
- 双臂协作、多关节协同场景

💡 提示：
  如需完整的40+功能（参数读取、诊断工具等），请使用:
  test_multi_motor_sync.py
"""

import os
import sys
import time
from typing import Dict, List, Any

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Embodied_SDK import create_motor_controller, close_all_shared_interfaces

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 70)
    print(" 🔄 多电机同步控制入门")
    print("=" * 70)
    print("本程序演示ZDT协议的三阶段同步控制。\n")

class MultiMotorSyncGuide:
    """多电机同步控制教学工具"""
    
    def __init__(self):
        self.motors: Dict[int, Any] = {}
        self.broadcast_controller: Any = None
        self.motor_ids: List[int] = []
        self.port = "COM18"
        self.baudrate = 500000
    
    def setup(self):
        """配置和连接电机"""
        print("\n📡 配置电机")
        print("-" * 50)
        
        # 简化配置：使用默认值
        use_default = input("使用默认配置? (COM18, ID=1,2) [Y/n]: ").strip().lower()
        
        if use_default in ['', 'y', 'yes']:
            self.port = "COM18"
            self.motor_ids = [1, 2]
        else:
            self.port = input("串口号: ").strip() or "COM18"
            ids_str = input("电机ID (逗号分隔, 如: 1,2,3): ").strip()
            self.motor_ids = [int(x.strip()) for x in ids_str.split(',')]
        
        print(f"\n正在连接 {len(self.motor_ids)} 个电机...")
        
        # 连接电机
        for mid in self.motor_ids:
            try:
                motor = create_motor_controller(
                    motor_id=mid,
                    interface_type="slcan",
                    shared_interface=True,  # 多电机必须用共享接口
                    port=self.port,
                    baudrate=self.baudrate
                )
                motor.connect()
                self.motors[mid] = motor
                print(f"  ✅ 电机 {mid} 连接成功")
            except Exception as e:
                print(f"  ❌ 电机 {mid} 连接失败: {e}")
        
        if not self.motors:
            print("\n❌ 未连接任何电机")
            return False
        
        # 创建广播控制器 (ID=0)
        self.broadcast_controller = create_motor_controller(
            motor_id=0,
            interface_type="slcan",
            shared_interface=True,
            port=self.port,
            baudrate=self.baudrate
        )
        self.broadcast_controller.connect()
        print(f"  ✅ 广播控制器创建成功")
        
        return True
    
    def sync_position_control(self):
        """同步位置控制"""
        clear_screen()
        print("=" * 70)
        print(" 🎯 同步位置控制")
        print("=" * 70)
        
        print("\n📚 功能说明：")
        print("  让多个电机同时移动到各自的目标位置")
        print("  ")
        print("  三阶段流程：")
        print("  ① Pre-load:  发送带 multi_sync=True 的位置命令")
        print("  ② Trigger:   发送广播同步触发 (ID=0)")
        print("  ③ Execute:   所有电机同时开始运动")
        
        # 设置目标
        print(f"\n为 {len(self.motors)} 个电机设置目标位置:")
        targets = {}
        for mid in self.motors.keys():
            target = input(f"  电机 {mid} 目标位置 (度, 默认90): ").strip()
            targets[mid] = float(target) if target else 90.0
        
        print("\n⚠️  电机即将同步运动，请确保安全")
        if input("确认执行? (y/N): ").strip().lower() != 'y':
            return
        
        try:
            # Phase 1: Pre-load
            print("\n[Phase 1] 预加载指令...")
            for mid in self.motors.keys():
                self.motors[mid].control_actions.move_to_position(
                    position=targets[mid],
                    speed=500,
                    is_absolute=True,
                    multi_sync=True  # 关键参数
                )
                print(f"  电机 {mid}: 预加载完成，等待触发")
            
            # Phase 2: Trigger
            print("\n[Phase 2] 发送广播触发...")
            time.sleep(0.5)
            self.broadcast_controller.control_actions.sync_motion()
            print("  ✅ 触发成功！所有电机开始运动")
            
            # Phase 3: Monitor
            print("\n[Phase 3] 监控运动...")
            timeout = 15.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                status_line = []
                all_done = True
                
                for mid in self.motors.keys():
                    try:
                        status = self.motors[mid].read_parameters.get_motor_status()
                        pos = self.motors[mid].read_parameters.get_position()
                        target = targets[mid]
                        
                        status_line.append(f"M{mid}:{pos:.1f}°→{target:.1f}° {'✓' if status.in_position else '→'}")
                        
                        if not status.in_position:
                            all_done = False
                    except:
                        status_line.append(f"M{mid}:ERR")
                        all_done = False
                
                print(f"\r  {' | '.join(status_line)}", end='', flush=True)
                
                if all_done:
                    print("\n\n✅ 所有电机已到位")
                    break
                
                time.sleep(0.5)
            else:
                print("\n\n⚠️  超时")
            
        except Exception as e:
            print(f"\n❌ 执行失败: {e}")
    
    def sync_speed_control(self):
        """同步速度控制"""
        clear_screen()
        print("=" * 70)
        print(" 🏃 同步速度控制")
        print("=" * 70)
        
        print("\n📚 功能说明：")
        print("  让多个电机同时以指定速度开始旋转")
        
        # 设置速度
        print(f"\n为 {len(self.motors)} 个电机设置速度:")
        speeds = {}
        for mid in self.motors.keys():
            speed = input(f"  电机 {mid} 速度 (RPM, 默认200): ").strip()
            speeds[mid] = float(speed) if speed else 200.0
        
        run_time = float(input("\n运行时间 (秒, 默认3): ").strip() or "3")
        
        if input("确认执行? (y/N): ").strip().lower() != 'y':
            return
        
        try:
            # Phase 1: Pre-load
            print("\n[Phase 1] 预加载速度命令...")
            for mid in self.motors.keys():
                self.motors[mid].control_actions.set_speed(
                    speed=speeds[mid],
                    acceleration=1000,
                    multi_sync=True
                )
                print(f"  电机 {mid}: 预加载完成")
            
            # Phase 2: Trigger
            print("\n[Phase 2] 发送触发...")
            time.sleep(0.5)
            self.broadcast_controller.control_actions.sync_motion()
            print("  ✅ 所有电机开始运动")
            
            # Phase 3: Run
            print(f"\n[Phase 3] 运行 {run_time} 秒...")
            for i in range(int(run_time)):
                time.sleep(1)
                status = []
                for mid in self.motors.keys():
                    try:
                        speed = self.motors[mid].read_parameters.get_speed()
                        status.append(f"M{mid}:{speed:.1f}RPM")
                    except:
                        status.append(f"M{mid}:ERR")
                print(f"  {i+1}s - {' | '.join(status)}")
            
            # Stop
            print("\n停止所有电机...")
            for mid in self.motors.keys():
                self.motors[mid].control_actions.stop()
            
            print("✅ 完成")
            
        except Exception as e:
            print(f"❌ 执行失败: {e}")
    
    def sync_homing(self):
        """同步回零"""
        clear_screen()
        print("=" * 70)
        print(" 🏠 同步回零")
        print("=" * 70)
        
        print("\n📚 功能说明：")
        print("  让多个电机同时执行回零动作")
        print("  ")
        print("  回零模式：")
        print("    0 - 单圈就近回零")
        print("    1 - 单圈方向回零")
        print("    2 - 无限位碰撞回零")
        print("    4 - 回到绝对位置坐标零点 (推荐，需要先设置零点)")
        print("    5 - 回到上次掉电位置")
        
        print("\n⚠️  注意：模式4需要先通过set_zero_position设置零点！")
        mode = int(input("\n选择回零模式 (0,1,2,4,5，默认4): ").strip() or "4")
        
        if input("确认执行同步回零? (y/N): ").strip().lower() != 'y':
            return
        
        try:
            # 确保所有电机已使能
            print("\n检查并使能电机...")
            for mid in self.motors.keys():
                try:
                    status = self.motors[mid].read_parameters.get_motor_status()
                    if not status.enabled:
                        self.motors[mid].control_actions.enable()
                        print(f"  电机 {mid} 已使能")
                except:
                    pass
            
            time.sleep(0.5)
            
            # Phase 1: Pre-load
            print("\n[Phase 1] 预加载回零命令...")
            for mid in self.motors.keys():
                self.motors[mid].control_actions.trigger_homing(
                    homing_mode=mode,
                    multi_sync=True
                )
                print(f"  电机 {mid}: 预加载完成")
            
            # Phase 2: Trigger
            print("\n[Phase 2] 发送触发...")
            time.sleep(0.5)
            self.broadcast_controller.control_actions.sync_motion()
            print("  ✅ 所有电机开始回零")
            
            # Phase 3: Monitor
            print("\n[Phase 3] 监控回零...")
            timeout = 30.0
            start_time = time.time()
            
            while time.time() - start_time < timeout:
                status_line = []
                all_done = True
                any_failed = False
                
                for mid in self.motors.keys():
                    try:
                        homing_status = self.motors[mid].read_parameters.get_homing_status()
                        pos = self.motors[mid].read_parameters.get_position()
                        
                        if homing_status.homing_in_progress:
                            status_line.append(f"M{mid}:回零中")
                            all_done = False
                        elif homing_status.homing_failed:
                            status_line.append(f"M{mid}:失败")
                            any_failed = True
                        else:
                            status_line.append(f"M{mid}:完成({pos:.1f}°)")
                    except:
                        status_line.append(f"M{mid}:ERR")
                        all_done = False
                
                print(f"\r  {' | '.join(status_line)}", end='', flush=True)
                
                if all_done and not any_failed:
                    print("\n\n✅ 所有电机回零完成")
                    break
                elif any_failed:
                    print("\n\n❌ 部分电机回零失败")
                    break
                
                time.sleep(2)
            else:
                print("\n\n⚠️  回零超时")
            
        except Exception as e:
            print(f"❌ 执行失败: {e}")
    
    def cleanup(self):
        """清理资源"""
        print("\n清理资源...")
        for mid, motor in self.motors.items():
            try:
                motor.disconnect()
            except:
                pass
        if self.broadcast_controller:
            try:
                self.broadcast_controller.disconnect()
            except:
                pass
        close_all_shared_interfaces()
        print("✅ 清理完成")
    
    def run(self):
        """主循环"""
        clear_screen()
        print_header()
        
        # 连接
        if not self.setup():
            return
        
        input("\n✅ 连接完成！按 Enter 继续...")
        
        while True:
            clear_screen()
            print_header()
            print(f"已连接电机: {list(self.motors.keys())}")
            
            print("\n📋 功能菜单：")
            print("  1. 同步位置控制")
            print("  2. 同步速度控制")
            print("  3. 同步回零")
            print("  ")
            print("  💡 完整功能请使用: test_multi_motor_sync.py")
            print("  ")
            print("  0. 退出")
            
            choice = input("\n请选择 (0-3): ").strip()
            
            if choice == '0':
                break
            elif choice == '1':
                self.sync_position_control()
            elif choice == '2':
                self.sync_speed_control()
            elif choice == '3':
                self.sync_homing()
            else:
                print("❌ 无效选择")
            
            input("\n按 Enter 继续...")
        
        self.cleanup()
        print("\n👋 感谢使用！")

if __name__ == "__main__":
    try:
        guide = MultiMotorSyncGuide()
        guide.run()
    except KeyboardInterrupt:
        print("\n\n⚠️  程序被中断")

