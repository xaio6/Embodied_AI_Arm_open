# -*- coding: utf-8 -*-
"""
ZDT电机SDK多机同步控制专用测试工具
严格按照ZDT协议进行多机同步控制测试

协议流程示例：
1. 发送带同步标志的命令到各个电机 (multi_sync=True)
2. 发送广播同步运动命令 (ID=0, 命令: 00 FF 66 6B)
3. 所有电机同时开始运动
"""

import time
import logging
from typing import Optional, Dict, List, Any
from Control_Core import ZDTMotorController, setup_logging

class ZDTMultiMotorSyncTester:
    """ZDT多机同步控制专用测试器"""
    
    def __init__(self):
        self.motors: Dict[int, ZDTMotorController] = {}  # 电机ID -> 控制器实例
        self.broadcast_controller: Optional[ZDTMotorController] = None  # 广播控制器
        self.connected_motor_ids: List[int] = []  # 已连接的电机ID列表
        self.interface_params = {}  # CAN接口参数
        
        # 设置日志
        setup_logging(logging.INFO)
        
        print("=" * 80)
        print("🎯 ZDT电机SDK多机同步控制专用测试工具")
        print("=" * 80)
        print("严格按照ZDT协议进行多机同步控制：")
        print("  1. 向各电机发送带同步标志的命令")
        print("  2. 发送广播同步运动命令 (00 FF 66 6B)")
        print("  3. 所有电机同时开始运动")
        print("=" * 80)
        print()
    
    def setup_environment(self) -> bool:
        """设置测试环境"""
        print("⚙️ 设置多机同步测试环境")
        print("-" * 50)
        
        # 检查是否已经设置过环境
        if self.connected_motor_ids or self.motors:
            print("⚠️ 检测到已有环境配置")
            choice = input("是否清理现有环境并重新设置? (y/N): ").strip().lower()
            if choice in ['y', 'yes']:
                self.cleanup()
            else:
                print("保持现有环境配置")
                return len(self.connected_motor_ids) > 0
        
        # 1. 设置CAN接口
        print("1. 配置CAN接口...")
        use_default = input("使用默认CAN配置 (COM18, 500000)? (Y/n): ").strip().lower()
        
        if use_default in ['', 'y', 'yes']:
            port = 'COM18'
            baudrate = 500000
        else:
            port = input("串口号: ").strip() or 'COM18'
            baudrate = int(input("波特率: ").strip() or '500000')
        
        self.interface_params = {
            'interface_type': 'slcan',
            'port': port,
            'baudrate': baudrate,
            'shared_interface': True
        }
        
        print(f"✓ CAN接口配置: {port}, {baudrate}")
        
        # 2. 添加电机
        print("\n2. 添加测试电机...")
        print("输入电机ID列表，用逗号分隔 (例如: 1,2)")
        
        motor_input = input("电机ID: ").strip()
        if not motor_input:
            print("✗ 必须至少添加一个电机")
            return False
        
        try:
            motor_ids = [int(x.strip()) for x in motor_input.split(',')]
            
            # 检查重复ID
            unique_ids = list(set(motor_ids))
            if len(unique_ids) != len(motor_ids):
                print("⚠️ 检测到重复的电机ID，已自动去重")
                motor_ids = unique_ids
            
            for motor_id in motor_ids:
                if 1 <= motor_id <= 255:  # 排除0，因为0是广播地址
                    if motor_id in self.motors:
                        print(f"⚠️ 电机ID {motor_id} 已存在，跳过")
                        continue
                    
                    motor = ZDTMotorController(motor_id=motor_id, **self.interface_params)
                    self.motors[motor_id] = motor
                    print(f"✓ 添加电机ID {motor_id}")
                else:
                    print(f"✗ 无效电机ID: {motor_id} (有效范围: 1-255)")
        except ValueError:
            print("✗ 输入格式错误")
            return False
        
        if not self.motors:
            print("✗ 没有添加任何有效电机")
            return False
        
        # 3. 创建广播控制器
        print("\n3. 创建广播控制器...")
        if self.broadcast_controller is None:
            self.broadcast_controller = ZDTMotorController(motor_id=0, **self.interface_params)
            print("✓ 广播控制器创建成功 (ID=0)")
        else:
            print("✓ 广播控制器已存在")
        
        # 4. 连接所有电机
        print("\n4. 连接所有电机...")
        success_count = 0
        
        for motor_id in self.motors.keys():
            # 检查是否已经连接
            if motor_id in self.connected_motor_ids:
                print(f"✓ 电机ID {motor_id} 已连接")
                success_count += 1
                continue
                
            try:
                self.motors[motor_id].connect()
                self.connected_motor_ids.append(motor_id)
                print(f"✓ 电机ID {motor_id} 连接成功")
                success_count += 1
            except Exception as e:
                print(f"✗ 电机ID {motor_id} 连接失败: {e}")
        
        # 连接广播控制器
        try:
            if self.broadcast_controller.can_interface is None:
                self.broadcast_controller.connect()
                print("✓ 广播控制器连接成功")
            else:
                print("✓ 广播控制器已连接")
        except Exception as e:
            print(f"✗ 广播控制器连接失败: {e}")
            return False
        
        print(f"\n✓ 环境设置完成: 成功连接 {success_count}/{len(self.motors)} 个电机")
        
        if success_count == 0:
            print("✗ 没有成功连接任何电机")
            return False
        
        return True
    
    def cleanup(self):
        """清理资源"""
        print("\n🧹 清理资源...")
        
        # 断开所有已连接的电机
        for motor_id in list(self.connected_motor_ids):
            try:
                if motor_id in self.motors:
                    self.motors[motor_id].disconnect()
                    print(f"✓ 电机ID {motor_id} 已断开")
            except Exception as e:
                print(f"⚠️ 电机ID {motor_id} 断开时警告: {e}")
        
        # 断开广播控制器
        if self.broadcast_controller:
            try:
                self.broadcast_controller.disconnect()
                print("✓ 广播控制器已断开")
            except Exception as e:
                print(f"⚠️ 广播控制器断开时警告: {e}")
            self.broadcast_controller = None
        
        # 强制清理所有共享接口
        ZDTMotorController.close_all_shared_interfaces()
        print("✓ 所有共享接口已清理")
        
        # 清理所有数据结构
        self.connected_motor_ids.clear()
        self.motors.clear()
        self.interface_params.clear()
        
        print("✓ 所有资源已清理完成")
    
    def test_sync_position_control(self):
        """测试多机同步位置控制"""
        print("\n🎯 多机同步位置控制测试")
        print("=" * 60)
        
        if len(self.connected_motor_ids) < 2:
            print("⚠️ 建议至少2个电机进行同步测试")
        
        print(f"参与同步的电机: {self.connected_motor_ids}")
        
        # 设置每个电机的目标位置
        motor_targets = {}
        print("\n设置各电机目标位置:")
        
        for motor_id in self.connected_motor_ids:
            while True:
                try:
                    target = float(input(f"电机ID {motor_id} 目标位置 (度): ").strip())
                    motor_targets[motor_id] = target
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            speed = float(input("运动速度 (RPM, 默认500): ").strip() or "500")
            is_absolute = input("绝对位置模式? (y/N): ").strip().lower() in ['y', 'yes']
        except ValueError:
            print("参数错误，使用默认值")
            speed = 500
            is_absolute = False
        
        print(f"\n同步位置控制参数:")
        for motor_id, target in motor_targets.items():
            print(f"  电机ID {motor_id}: {target}度")
        print(f"  速度: {speed}RPM")
        print(f"  模式: {'绝对位置' if is_absolute else '相对位置'}")
        
        confirm = input("\n确认执行同步位置控制? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消测试")
            return
        
        try:
            print("\n🚀 开始多机同步位置控制...")
            
            # 第一阶段：发送带同步标志的位置命令到各个电机
            print("\n第一阶段：发送同步位置命令...")
            success_count = 0
            
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    target_pos = motor_targets[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 发送同步位置命令 (目标: {target_pos}度)")
                    motor.control_actions.move_to_position(
                        position=target_pos,
                        speed=speed,
                        is_absolute=is_absolute,
                        multi_sync=True  # 关键：启用多机同步标志
                    )
                    print(f"  ✓ 电机ID {motor_id}: 同步命令发送成功，等待同步触发")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 同步命令发送失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有同步命令都发送失败")
                return
            
            print(f"✓ 第一阶段完成：{success_count}/{len(self.connected_motor_ids)} 个电机已接收同步命令")
            
            # 第二阶段：发送广播同步运动命令
            print("\n第二阶段：发送广播同步运动命令...")
            time.sleep(0.5)  # 稍微等待确保所有命令都已处理
            
            print("  → 发送广播同步运动命令 (00 FF 66 6B)")
            sync_command = self.broadcast_controller.command_builder.multi_sync_motion()
            print(f"  → 命令数据: {[hex(x) for x in sync_command]}")
            
            self.broadcast_controller.control_actions.sync_motion()
            print("  ✓ 广播同步运动命令发送成功！")
            print("🎉 所有电机现在应该同时开始运动！")
            
            # 第三阶段：监控运动过程
            print("\n第三阶段：监控运动过程...")
            self._monitor_sync_motion(motor_targets, timeout=20.0)
            
        except Exception as e:
            print(f"✗ 多机同步位置控制失败: {e}")
    
    def test_sync_speed_control(self):
        """测试多机同步速度控制"""
        print("\n🏃 多机同步速度控制测试")
        print("=" * 60)
        
        print(f"参与同步的电机: {self.connected_motor_ids}")
        
        # 设置每个电机的目标速度
        motor_speeds = {}
        print("\n设置各电机目标速度:")
        
        for motor_id in self.connected_motor_ids:
            while True:
                try:
                    speed = float(input(f"电机ID {motor_id} 目标速度 (RPM): ").strip())
                    motor_speeds[motor_id] = speed
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            acceleration = int(input("加速度 (RPM/s, 默认1000): ").strip() or "1000")
            run_time = float(input("运行时间 (秒, 默认5): ").strip() or "5")
        except ValueError:
            acceleration = 1000
            run_time = 5
        
        print(f"\n同步速度控制参数:")
        for motor_id, speed in motor_speeds.items():
            print(f"  电机ID {motor_id}: {speed}RPM")
        print(f"  加速度: {acceleration}RPM/s")
        print(f"  运行时间: {run_time}秒")
        
        confirm = input("\n确认执行同步速度控制? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机同步速度控制...")
            
            # 第一阶段：发送带同步标志的速度命令
            print("\n第一阶段：发送同步速度命令...")
            success_count = 0
            
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    target_speed = motor_speeds[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 发送同步速度命令 (速度: {target_speed}RPM)")
                    motor.control_actions.set_speed(
                        speed=target_speed,
                        acceleration=acceleration,
                        multi_sync=True
                    )
                    print(f"  ✓ 电机ID {motor_id}: 同步速度命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 同步速度命令发送失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有同步速度命令都发送失败")
                return
            
            # 第二阶段：发送广播同步运动命令
            print("\n第二阶段：发送广播同步运动命令...")
            time.sleep(0.5)
            
            self.broadcast_controller.control_actions.sync_motion()
            print("✓ 广播同步运动命令发送成功！所有电机开始同步运动")
            
            # 运行指定时间后停止
            print(f"\n运行 {run_time} 秒...")
            for i in range(int(run_time)):
                time.sleep(1)
                print(f"  运行中... {i+1}/{int(run_time)}秒")
            
            print("\n停止所有电机...")
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    motor.control_actions.stop()
                    print(f"✓ 电机ID {motor_id} 已停止")
                except Exception as e:
                    print(f"✗ 电机ID {motor_id} 停止失败: {e}")
            
        except Exception as e:
            print(f"✗ 多机同步速度控制失败: {e}")
    
    def test_sync_homing(self):
        """测试多机同步回零"""
        print("\n🏠 多机同步回零测试")
        print("=" * 60)
        
        print(f"参与同步回零的电机: {self.connected_motor_ids}")
        
        # 回零模式选择
        print("\n回零模式选择:")
        print("0. 就近回零")
        print("1. 正向回零")
        print("2. 负向回零")
        
        try:
            mode = int(input("选择回零模式 (0-2, 默认0): ").strip() or "0")
            if mode not in [0, 1, 2]:
                mode = 0
        except ValueError:
            mode = 0
        
        mode_names = {0: "就近回零", 1: "正向回零", 2: "负向回零"}
        print(f"选择的回零模式: {mode_names[mode]}")
        
        confirm = input("\n确认执行同步回零? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机同步回零...")
            
            # 确保所有电机都已使能
            print("检查并使能所有电机...")
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    status = motor.read_parameters.get_motor_status()
                    if not status.enabled:
                        print(f"  → 使能电机ID {motor_id}")
                        motor.control_actions.enable()
                        time.sleep(0.2)
                except Exception as e:
                    print(f"  ⚠️ 电机ID {motor_id} 状态检查失败: {e}")
            
            # 第一阶段：发送带同步标志的回零命令
            print("\n第一阶段：发送同步回零命令...")
            success_count = 0
            
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 发送同步回零命令")
                    motor.control_actions.trigger_homing(homing_mode=mode, multi_sync=True)
                    print(f"  ✓ 电机ID {motor_id}: 同步回零命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 同步回零命令发送失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有同步回零命令都发送失败")
                return
            
            # 第二阶段：发送广播同步运动命令
            print("\n第二阶段：发送广播同步运动命令...")
            time.sleep(0.5)
            
            self.broadcast_controller.control_actions.sync_motion()
            print("✓ 广播同步运动命令发送成功！所有电机开始同步回零")
            
            # 第三阶段：监控回零过程
            print("\n第三阶段：监控回零过程...")
            self._monitor_sync_homing(timeout=30.0)
            
        except Exception as e:
            print(f"✗ 多机同步回零失败: {e}")
    
    def _monitor_sync_motion(self, motor_targets: Dict[int, float], timeout: float = 15.0):
        """监控同步运动过程"""
        print("实时监控同步运动进度...")
        print(f"{'时间':<8} {'电机状态'}")
        print("-" * 60)
        
        start_time = time.time()
        all_reached = False
        
        while time.time() - start_time < timeout and not all_reached:
            time.sleep(1)
            
            status_info = []
            all_in_position = True
            
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    status = motor.read_parameters.get_motor_status()
                    position = motor.read_parameters.get_position()
                    target = motor_targets.get(motor_id, 0)
                    error = abs(position - target)
                    
                    status_char = "✓" if status.in_position else "○"
                    status_info.append(f"ID{motor_id}:{position:.1f}°(→{target:.1f}°,Δ{error:.1f}°){status_char}")
                    
                    if not status.in_position:
                        all_in_position = False
                        
                except Exception as e:
                    status_info.append(f"ID{motor_id}:ERR")
                    all_in_position = False
            
            elapsed = time.time() - start_time
            print(f"{elapsed:7.1f}s {' | '.join(status_info)}")
            
            if all_in_position:
                all_reached = True
        
        print("-" * 60)
        if all_reached:
            print("🎉 所有电机都已到达目标位置！同步运动成功完成")
        else:
            print("⏰ 监控超时，部分电机可能未到达目标位置")
    
    def _monitor_sync_homing(self, timeout: float = 30.0):
        """监控同步回零过程"""
        print("实时监控同步回零进度...")
        print(f"{'时间':<8} {'回零状态'}")
        print("-" * 60)
        
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            status_info = []
            all_completed = True
            any_failed = False
            
            for motor_id in self.connected_motor_ids:
                try:
                    motor = self.motors[motor_id]
                    homing_status = motor.read_parameters.get_homing_status()
                    position = motor.read_parameters.get_position()
                    
                    if homing_status.homing_in_progress:
                        status_info.append(f"ID{motor_id}:回零中({position:.1f}°)")
                        all_completed = False
                    elif homing_status.homing_failed:
                        status_info.append(f"ID{motor_id}:失败")
                        any_failed = True
                    else:
                        status_info.append(f"ID{motor_id}:完成({position:.1f}°)")
                        
                except Exception as e:
                    status_info.append(f"ID{motor_id}:ERR")
                    all_completed = False
            
            elapsed = time.time() - start_time
            print(f"{elapsed:7.1f}s {' | '.join(status_info)}")
            
            if all_completed and not any_failed:
                print("🎉 所有电机回零完成！")
                return
            elif any_failed:
                print("❌ 部分电机回零失败")
                return
            
            time.sleep(2)
        
        print("⏰ 回零监控超时")
    
    def read_version_info(self):
        """读取所有电机的版本信息"""
        print("\n📝 读取所有电机版本信息")
        print("-" * 70)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<8} {'固件版本':<12} {'硬件版本':<12} {'状态'}")
        print("-" * 70)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<8} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                version_info = motor.read_parameters.get_version()
                
                print(f"{motor_id:<8} {version_info['firmware']:<12} "
                      f"{version_info['hardware']:<12} ✓")
                
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
        
        print("-" * 70)
    
    def read_resistance_inductance(self):
        """读取所有电机的电阻电感"""
        print("\n⚡ 读取所有电机电阻电感")
        print("-" * 60)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<8} {'相电阻(Ω)':<12} {'相电感(mH)':<12} {'状态'}")
        print("-" * 60)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<8} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                ri_info = motor.read_parameters.get_resistance_inductance()
                
                print(f"{motor_id:<8} {ri_info['resistance']:<12.3f} "
                      f"{ri_info['inductance']:<12.3f} ✓")
                
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
        
        print("-" * 60)
    
    def read_voltage_current(self):
        """读取所有电机的电压电流信息"""
        print("\n🔋 读取所有电机电压电流信息")
        print("-" * 80)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<6} {'总线电压(V)':<12} {'总线电流(A)':<12} {'相电流(A)':<12} {'状态'}")
        print("-" * 80)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<6} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                bus_voltage = motor.read_parameters.get_bus_voltage()
                bus_current = motor.read_parameters.get_bus_current()
                phase_current = motor.read_parameters.get_current()
                
                print(f"{motor_id:<6} {bus_voltage:<12.2f} {bus_current:<12.3f} "
                      f"{phase_current:<12.3f} ✓")
                
            except Exception as e:
                print(f"{motor_id:<6} 读取失败: {e}")
        
        print("-" * 80)
    
    def read_encoder_values(self):
        """读取所有电机的编码器值"""
        print("\n🔄 读取所有电机编码器值")
        print("-" * 70)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<8} {'原始值(度)':<12} {'校准值(度)':<12} {'状态'}")
        print("-" * 70)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<8} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                encoder_raw = motor.read_parameters.get_encoder_raw()
                encoder_calibrated = motor.read_parameters.get_encoder_calibrated()
                
                print(f"{motor_id:<8} {encoder_raw:<12.2f} {encoder_calibrated:<12.2f} ✓")
                
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
        
        print("-" * 70)
    
    def read_pulse_counts(self):
        """读取所有电机的脉冲计数"""
        print("\n📊 读取所有电机脉冲计数")
        print("-" * 70)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<8} {'实时脉冲数':<12} {'输入脉冲数':<12} {'状态'}")
        print("-" * 70)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<8} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                pulse_count = motor.read_parameters.get_pulse_count()
                input_pulse = motor.read_parameters.get_input_pulse()
                
                print(f"{motor_id:<8} {pulse_count:<12} {input_pulse:<12} ✓")
                
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
        
        print("-" * 70)
    
    def read_position_info(self):
        """读取所有电机的位置信息"""
        print("\n🎯 读取所有电机位置信息")
        print("-" * 90)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<6} {'当前位置(度)':<12} {'目标位置(度)':<12} {'位置误差(度)':<12} {'状态'}")
        print("-" * 90)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<6} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                current_pos = motor.read_parameters.get_position()
                target_pos = motor.read_parameters.get_target_position()
                position_error = motor.read_parameters.get_position_error()
                
                print(f"{motor_id:<6} {current_pos:<12.2f} {target_pos:<12.2f} "
                      f"{position_error:<12.4f} ✓")
                
            except Exception as e:
                print(f"{motor_id:<6} 读取失败: {e}")
        
        print("-" * 90)
    
    def fix_duplicate_connections(self):
        """检查并修复重复连接问题"""
        print("\n🔧 检查并修复重复连接问题")
        print("-" * 50)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        # 检查重复
        unique_ids = list(set(self.connected_motor_ids))
        duplicate_count = len(self.connected_motor_ids) - len(unique_ids)
        
        if duplicate_count == 0:
            print("✓ 没有检测到重复连接")
            print(f"当前连接的电机: {sorted(unique_ids)}")
            return
        
        print(f"⚠️ 检测到 {duplicate_count} 个重复连接")
        print(f"连接列表: {self.connected_motor_ids}")
        print(f"唯一电机ID: {sorted(unique_ids)}")
        
        # 修复重复连接
        choice = input("是否修复重复连接问题? (y/N): ").strip().lower()
        if choice in ['y', 'yes']:
            print("正在修复重复连接...")
            
            # 保留唯一的连接
            self.connected_motor_ids = unique_ids
            
            # 检查motors字典是否与连接列表一致
            motor_ids_in_dict = set(self.motors.keys())
            connected_ids_set = set(self.connected_motor_ids)
            
            # 移除不在连接列表中的电机实例
            for motor_id in list(motor_ids_in_dict):
                if motor_id not in connected_ids_set:
                    print(f"移除未连接的电机实例: ID {motor_id}")
                    try:
                        self.motors[motor_id].disconnect()
                    except:
                        pass
                    del self.motors[motor_id]
            
            print("✓ 重复连接问题已修复")
            print(f"修复后连接的电机: {sorted(self.connected_motor_ids)}")
        else:
            print("跳过修复")
    
    def show_motor_status(self):
        """显示所有电机状态"""
        print("\n📊 电机状态总览")
        print("-" * 70)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            print("-" * 70)
            return
        
        print(f"{'ID':<4} {'使能':<6} {'到位':<6} {'位置':<12} {'速度':<12} {'温度':<8}")
        print("-" * 70)
        
        # 使用set确保每个电机ID只显示一次
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<4} 电机实例不存在")
                    continue
                    
                motor = self.motors[motor_id]
                status = motor.read_parameters.get_motor_status()
                position = motor.read_parameters.get_position()
                speed = motor.read_parameters.get_speed()
                temperature = motor.read_parameters.get_temperature()
                
                print(f"{motor_id:<4} {status.enabled:<6} {status.in_position:<6} "
                      f"{position:<12.2f} {speed:<12.2f} {temperature:<8.1f}")
                
            except Exception as e:
                print(f"{motor_id:<4} 读取失败: {e}")
        
        print("-" * 70)
        print(f"总计: {len(unique_motor_ids)} 个电机")
        
        # 显示调试信息
        if len(self.connected_motor_ids) != len(unique_motor_ids):
            print(f"⚠️ 检测到重复连接: 连接列表长度={len(self.connected_motor_ids)}, 唯一ID数量={len(unique_motor_ids)}")
            print(f"连接列表: {self.connected_motor_ids}")
            print(f"唯一ID: {unique_motor_ids}")
    
    def show_menu(self):
        """显示主菜单"""
        print("\n" + "=" * 80)
        print("🎯 ZDT多机同步控制测试菜单")
        print("=" * 80)
        
        if self.connected_motor_ids:
            unique_ids = sorted(set(self.connected_motor_ids))
            duplicate_count = len(self.connected_motor_ids) - len(unique_ids)
            
            if duplicate_count > 0:
                print(f"当前连接电机: {unique_ids} ⚠️ 检测到{duplicate_count}个重复连接")
            else:
                print(f"当前连接电机: {unique_ids}")
                
            shared_info = ZDTMotorController.get_shared_interface_info()
            if shared_info:
                print(f"共享CAN接口: {shared_info}")
        else:
            print("当前连接电机: 无")
        
        print()
        print("环境管理:")
        print("  1. 设置测试环境")
        print("  2. 显示电机状态")
        print("  3. 清理资源")
        print("  7. 🔧 修复重复连接")
        print()
        print("多机同步控制测试:")
        print("  4. 多机同步位置控制")
        print("  5. 多机同步速度控制")
        print("  6. 多机同步回零")
        print()
        print("状态读取:")
        print("  8. 📝 读取版本信息")
        print("  9. ⚡ 读取电阻电感")
        print("  10. 🔋 读取电压电流")
        print("  11. 🔄 读取编码器值")
        print("  12. 📊 读取脉冲计数")
        print("  13. 🎯 读取位置信息")
        print("  14. 🎛️ 读取PID参数")
        print()
        print("回零功能:")
        print("  15. 🏠 读取回零状态")
        print("  16. 📋 读取回零参数")
        print()
        print("运动控制测试:")
        print("  17. 🏃 多机速度模式测试")
        print("  18. 📍 多机位置模式测试")
        print("  19. 📐 多机梯形曲线位置模式测试")
        print("  20. 💪 多机力矩模式测试")
        print()
        print("工具功能:")
        print("  21. 🔋 多机使能")
        print("  22. 🔌 多机失能")
        print("  23. 🎯 多机设置零点位置")
        print("  24. 🛑 多机电机停止")
        print("  25. ⚙️ 多机修改驱动参数")
        print("  26. 🔄 多机清零位置")
        print()
        print("  0. 退出")
        print("=" * 80)
    
    def run(self):
        """运行多机同步测试"""
        print("欢迎使用ZDT多机同步控制专用测试工具！")
        print("本工具严格按照ZDT协议进行多机同步控制测试。")
        
        while True:
            try:
                self.show_menu()
                choice = input("\n请选择操作 (0-26): ").strip()
                
                if choice == "0":
                    print("👋 感谢使用ZDT多机同步控制测试工具！")
                    break
                elif choice == "1":
                    self.setup_environment()
                elif choice == "2":
                    self.show_motor_status()
                elif choice == "3":
                    self.cleanup()
                elif choice == "4":
                    if not self.connected_motor_ids:
                        print("⚠️ 请先设置测试环境")
                    else:
                        self.test_sync_position_control()
                elif choice == "5":
                    if not self.connected_motor_ids:
                        print("⚠️ 请先设置测试环境")
                    else:
                        self.test_sync_speed_control()
                elif choice == "6":
                    if not self.connected_motor_ids:
                        print("⚠️ 请先设置测试环境")
                    else:
                        self.test_sync_homing()
                elif choice == "7":
                    self.fix_duplicate_connections()
                elif choice == "8":
                    self.read_version_info()
                elif choice == "9":
                    self.read_resistance_inductance()
                elif choice == "10":
                    self.read_voltage_current()
                elif choice == "11":
                    self.read_encoder_values()
                elif choice == "12":
                    self.read_pulse_counts()
                elif choice == "13":
                    self.read_position_info()
                elif choice == "14":
                    self.read_pid_parameters()
                elif choice == "15":
                    self.read_homing_status()
                elif choice == "16":
                    self.read_homing_parameters()
                elif choice == "17":
                    self.test_multi_speed_mode()
                elif choice == "18":
                    self.test_multi_position_mode()
                elif choice == "19":
                    self.test_multi_trapezoid_position_mode()
                elif choice == "20":
                    self.test_multi_torque_mode()
                elif choice == "21":
                    self.test_multi_enable()
                elif choice == "22":
                    self.test_multi_disable()
                elif choice == "23":
                    self.test_multi_set_zero_position()
                elif choice == "24":
                    self.test_multi_motor_stop()
                elif choice == "25":
                    self.test_multi_modify_drive_parameters()
                elif choice == "26":
                    self.test_multi_clear_position()
                else:
                    print("❌ 无效选择，请重新输入")
                
                # 等待用户按键继续
                if choice != "0":
                    input("\n按回车键继续...")
                    
            except KeyboardInterrupt:
                print("\n\n👋 用户中断，正在退出...")
                break
            except Exception as e:
                print(f"\n❌ 发生错误: {e}")
                input("按回车键继续...")
        
        # 清理资源
        self.cleanup()

    def read_pid_parameters(self):
        """读取所有电机的PID参数"""
        print("\n🎛️ 读取所有电机PID参数")
        print("-" * 80)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<6} {'梯形Kp':<8} {'直通Kp':<8} {'速度Kp':<8} {'速度Ki':<8} {'状态'}")
        print("-" * 80)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<6} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                pid_params = motor.read_parameters.get_pid_parameters()
                
                print(f"{motor_id:<6} {pid_params.trapezoid_position_kp:<8} "
                      f"{pid_params.direct_position_kp:<8} "
                      f"{pid_params.speed_kp:<8} {pid_params.speed_ki:<8} ✓")
                
            except Exception as e:
                print(f"{motor_id:<6} 读取失败: {e}")
        
        print("-" * 80)
    
    def read_homing_status(self):
        """读取所有电机的回零状态"""
        print("\n🏠 读取所有电机回零状态")
        print("-" * 90)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<6} {'编码器就绪':<10} {'校准表就绪':<10} {'回零进行中':<10} {'回零失败':<8} {'精度高':<8}")
        print("-" * 90)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<6} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                homing_status = motor.read_parameters.get_homing_status()
                
                print(f"{motor_id:<6} {homing_status.encoder_ready:<10} "
                      f"{homing_status.calibration_table_ready:<10} "
                      f"{homing_status.homing_in_progress:<10} "
                      f"{homing_status.homing_failed:<8} "
                      f"{homing_status.position_precision_high:<8}")
                
            except Exception as e:
                print(f"{motor_id:<6} 读取失败: {e}")
        
        print("-" * 90)
    
    def read_homing_parameters(self):
        """读取所有电机的回零参数"""
        print("\n📋 读取所有电机回零参数")
        print("-" * 100)
        
        if not self.connected_motor_ids:
            print("当前没有连接的电机")
            return
        
        print(f"{'电机ID':<6} {'模式':<6} {'方向':<6} {'速度':<8} {'超时':<8} {'碰撞速度':<8} {'碰撞电流':<8} {'自动回零':<8}")
        print("-" * 100)
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        
        for motor_id in unique_motor_ids:
            try:
                if motor_id not in self.motors:
                    print(f"{motor_id:<6} 电机实例不存在")
                    continue
                
                motor = self.motors[motor_id]
                params = motor.read_parameters.get_homing_parameters()
                
                print(f"{motor_id:<6} {params.mode:<6} {params.direction:<6} "
                      f"{params.speed:<8} {params.timeout:<8} "
                      f"{params.collision_detection_speed:<8} "
                      f"{params.collision_detection_current:<8} "
                      f"{params.auto_homing_enabled:<8}")
                
            except Exception as e:
                print(f"{motor_id:<6} 读取失败: {e}")
        
        print("-" * 100)

    def test_multi_speed_mode(self):
        """测试多机速度模式"""
        print("\n🏃 多机速度模式测试")
        print("=" * 60)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        print(f"参与测试的电机: {sorted(set(self.connected_motor_ids))}")
        
        # 设置每个电机的速度
        motor_speeds = {}
        print("\n设置各电机速度:")
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        for motor_id in unique_motor_ids:
            while True:
                try:
                    speed = float(input(f"电机ID {motor_id} 目标速度 (RPM): ").strip())
                    motor_speeds[motor_id] = speed
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            acceleration = int(input("加速度 (RPM/s, 默认1000): ").strip() or "1000")
            run_time = float(input("运行时间 (秒, 默认5): ").strip() or "5")
        except ValueError:
            acceleration = 1000
            run_time = 5
        
        print(f"\n速度模式测试参数:")
        for motor_id, speed in motor_speeds.items():
            print(f"  电机ID {motor_id}: {speed}RPM")
        print(f"  加速度: {acceleration}RPM/s")
        print(f"  运行时间: {run_time}秒")
        
        confirm = input("\n确认执行多机速度模式测试? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机速度模式测试...")
            
            # 发送速度命令到各个电机
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    target_speed = motor_speeds[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 设置速度 {target_speed}RPM")
                    motor.control_actions.set_speed(
                        speed=target_speed,
                        acceleration=acceleration
                    )
                    print(f"  ✓ 电机ID {motor_id}: 速度设置成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 速度设置失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有电机速度设置都失败")
                return
            
            # 运行指定时间
            print(f"\n运行 {run_time} 秒，监控速度...")
            for i in range(int(run_time)):
                time.sleep(1)
                
                # 显示当前速度
                speed_info = []
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            current_speed = self.motors[motor_id].read_parameters.get_speed()
                            speed_info.append(f"ID{motor_id}:{current_speed:.1f}RPM")
                    except:
                        speed_info.append(f"ID{motor_id}:ERR")
                
                print(f"  {i+1}/{int(run_time)}s - {' | '.join(speed_info)}")
            
            # 停止所有电机
            print("\n停止所有电机...")
            for motor_id in unique_motor_ids:
                try:
                    if motor_id in self.motors:
                        self.motors[motor_id].control_actions.stop()
                        print(f"✓ 电机ID {motor_id} 已停止")
                except Exception as e:
                    print(f"✗ 电机ID {motor_id} 停止失败: {e}")
            
        except Exception as e:
            print(f"✗ 多机速度模式测试失败: {e}")
    
    def test_multi_position_mode(self):
        """测试多机位置模式"""
        print("\n📍 多机位置模式测试")
        print("=" * 60)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        print(f"参与测试的电机: {sorted(set(self.connected_motor_ids))}")
        
        # 设置每个电机的目标位置
        motor_positions = {}
        print("\n设置各电机目标位置:")
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        for motor_id in unique_motor_ids:
            while True:
                try:
                    position = float(input(f"电机ID {motor_id} 目标位置 (度): ").strip())
                    motor_positions[motor_id] = position
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            speed = float(input("运动速度 (RPM, 默认500): ").strip() or "500")
            is_absolute = input("绝对位置模式? (y/N): ").strip().lower() in ['y', 'yes']
        except ValueError:
            speed = 500
            is_absolute = False
        
        print(f"\n位置模式测试参数:")
        for motor_id, position in motor_positions.items():
            print(f"  电机ID {motor_id}: {position}度")
        print(f"  速度: {speed}RPM")
        print(f"  模式: {'绝对位置' if is_absolute else '相对位置'}")
        
        confirm = input("\n确认执行多机位置模式测试? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机位置模式测试...")
            
            # 发送位置命令到各个电机
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    target_pos = motor_positions[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 移动到位置 {target_pos}度")
                    motor.control_actions.move_to_position(
                        position=target_pos,
                        speed=speed,
                        is_absolute=is_absolute
                    )
                    print(f"  ✓ 电机ID {motor_id}: 位置命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 位置命令发送失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有电机位置命令都发送失败")
                return
            
            # 监控运动过程
            print("\n监控运动过程...")
            self._monitor_position_motion(motor_positions, timeout=20.0)
            
        except Exception as e:
            print(f"✗ 多机位置模式测试失败: {e}")

    def test_multi_trapezoid_position_mode(self):
        """测试多机梯形曲线位置模式"""
        print("\n📐 多机梯形曲线位置模式测试")
        print("=" * 70)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        print(f"参与测试的电机: {sorted(set(self.connected_motor_ids))}")
        
        # 设置每个电机的目标位置
        motor_positions = {}
        print("\n设置各电机目标位置:")
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        for motor_id in unique_motor_ids:
            while True:
                try:
                    position = float(input(f"电机ID {motor_id} 目标位置 (度): ").strip())
                    motor_positions[motor_id] = position
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            max_speed = float(input("最大速度 (RPM, 默认500): ").strip() or "500")
            acceleration = int(input("加速度 (RPM/s, 默认1000): ").strip() or "1000")
            deceleration = int(input("减速度 (RPM/s, 默认1000): ").strip() or "1000")
            is_absolute = input("绝对位置模式? (y/N): ").strip().lower() in ['y', 'yes']
        except ValueError:
            max_speed = 500
            acceleration = 1000
            deceleration = 1000
            is_absolute = False
        
        print(f"\n梯形曲线位置模式测试参数:")
        for motor_id, position in motor_positions.items():
            print(f"  电机ID {motor_id}: {position}度")
        print(f"  最大速度: {max_speed}RPM")
        print(f"  加速度: {acceleration}RPM/s")
        print(f"  减速度: {deceleration}RPM/s")
        print(f"  模式: {'绝对位置' if is_absolute else '相对位置'}")
        
        confirm = input("\n确认执行多机梯形曲线位置模式测试? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机梯形曲线位置模式测试...")
            
            # 发送梯形曲线位置命令到各个电机
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    target_pos = motor_positions[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 梯形曲线移动到位置 {target_pos}度")
                    motor.control_actions.move_to_position_trapezoid(
                        position=target_pos,
                        max_speed=max_speed,
                        acceleration=acceleration,
                        deceleration=deceleration,
                        is_absolute=is_absolute
                    )
                    print(f"  ✓ 电机ID {motor_id}: 梯形曲线位置命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 梯形曲线位置命令发送失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有电机梯形曲线位置命令都发送失败")
                return
            
            # 监控运动过程
            print("\n监控梯形曲线运动过程...")
            self._monitor_position_motion(motor_positions, timeout=30.0)
            
        except Exception as e:
            print(f"✗ 多机梯形曲线位置模式测试失败: {e}")
    
    def test_multi_torque_mode(self):
        """测试多机力矩模式"""
        print("\n💪 多机力矩模式测试")
        print("=" * 60)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        print(f"参与测试的电机: {sorted(set(self.connected_motor_ids))}")
        
        # 设置每个电机的目标电流
        motor_currents = {}
        print("\n设置各电机目标电流:")
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        for motor_id in unique_motor_ids:
            while True:
                try:
                    current = int(input(f"电机ID {motor_id} 目标电流 (mA): ").strip())
                    motor_currents[motor_id] = current
                    break
                except ValueError:
                    print("请输入有效数字")
        
        # 设置运动参数
        try:
            current_slope = int(input("电流斜率 (mA/s, 默认1000): ").strip() or "1000")
            run_time = float(input("运行时间 (秒, 默认3): ").strip() or "3")
        except ValueError:
            current_slope = 1000
            run_time = 3
        
        print(f"\n力矩模式测试参数:")
        for motor_id, current in motor_currents.items():
            print(f"  电机ID {motor_id}: {current}mA")
        print(f"  电流斜率: {current_slope}mA/s")
        print(f"  运行时间: {run_time}秒")
        
        confirm = input("\n确认执行多机力矩模式测试? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            return
        
        try:
            print("\n🚀 开始多机力矩模式测试...")
            
            # 发送力矩命令到各个电机
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    target_current = motor_currents[motor_id]
                    
                    print(f"  → 电机ID {motor_id}: 设置力矩 {target_current}mA")
                    motor.control_actions.set_torque(
                        current=target_current,
                        current_slope=current_slope
                    )
                    print(f"  ✓ 电机ID {motor_id}: 力矩设置成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 力矩设置失败 - {e}")
            
            if success_count == 0:
                print("❌ 所有电机力矩设置都失败")
                return
            
            # 运行指定时间并监控
            print(f"\n运行 {run_time} 秒，监控电流...")
            for i in range(int(run_time)):
                time.sleep(1)
                
                # 显示当前电流
                current_info = []
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            phase_current = self.motors[motor_id].read_parameters.get_current()
                            current_info.append(f"ID{motor_id}:{phase_current:.0f}mA")
                    except:
                        current_info.append(f"ID{motor_id}:ERR")
                
                print(f"  {i+1}/{int(run_time)}s - {' | '.join(current_info)}")
            
            # 停止所有电机
            print("\n停止所有电机...")
            for motor_id in unique_motor_ids:
                try:
                    if motor_id in self.motors:
                        self.motors[motor_id].control_actions.stop()
                        print(f"✓ 电机ID {motor_id} 已停止")
                except Exception as e:
                    print(f"✗ 电机ID {motor_id} 停止失败: {e}")
            
        except Exception as e:
            print(f"✗ 多机力矩模式测试失败: {e}")
    
    def _monitor_position_motion(self, motor_targets: Dict[int, float], timeout: float = 15.0):
        """监控位置运动过程"""
        print("实时监控位置运动进度...")
        print(f"{'时间':<8} {'电机状态'}")
        print("-" * 70)
        
        start_time = time.time()
        all_reached = False
        
        while time.time() - start_time < timeout and not all_reached:
            time.sleep(1)
            
            status_info = []
            all_in_position = True
            
            unique_motor_ids = sorted(set(self.connected_motor_ids))
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                        
                    motor = self.motors[motor_id]
                    status = motor.read_parameters.get_motor_status()
                    position = motor.read_parameters.get_position()
                    target = motor_targets.get(motor_id, 0)
                    error = abs(position - target)
                    
                    status_char = "✓" if status.in_position else "○"
                    status_info.append(f"ID{motor_id}:{position:.1f}°(→{target:.1f}°,Δ{error:.1f}°){status_char}")
                    
                    if not status.in_position:
                        all_in_position = False
                        
                except Exception as e:
                    status_info.append(f"ID{motor_id}:ERR")
                    all_in_position = False
            
            elapsed = time.time() - start_time
            print(f"{elapsed:7.1f}s {' | '.join(status_info)}")
            
            if all_in_position:
                all_reached = True
        
        print("-" * 70)
        if all_reached:
            print("🎉 所有电机都已到达目标位置！")
        else:
            print("⏰ 监控超时，部分电机可能未到达目标位置")

    def test_multi_set_zero_position(self):
        """测试多机设置零点位置"""
        print("\n🎯 多机设置零点位置")
        print("=" * 60)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"参与设置的电机: {unique_motor_ids}")
        
        # 显示当前位置
        print("\n当前各电机位置:")
        for motor_id in unique_motor_ids:
            try:
                if motor_id in self.motors:
                    current_pos = self.motors[motor_id].read_parameters.get_position()
                    print(f"  电机ID {motor_id}: {current_pos:.2f}度")
            except Exception as e:
                print(f"  电机ID {motor_id}: 读取失败 - {e}")
        
        print("\n⚠️ 此操作将把所有电机的当前位置设置为零点")
        save_choice = input("是否保存到芯片? (Y/n): ").strip().lower()
        save_to_chip = save_choice in ['', 'y', 'yes']
        
        confirm = input("确认设置所有电机当前位置为零点? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        try:
            print("\n🚀 开始多机设置零点...")
            
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    print(f"  → 电机ID {motor_id}: 设置零点")
                    motor.control_actions.set_zero_position(save_to_chip)
                    print(f"  ✓ 电机ID {motor_id}: 零点设置成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 零点设置失败 - {e}")
            
            if success_count > 0:
                print(f"\n✓ 成功设置 {success_count}/{len(unique_motor_ids)} 个电机的零点")
                if save_to_chip:
                    print("✓ 零点已保存到芯片")
                else:
                    print("⚠️ 零点未保存到芯片，断电后会丢失")
                
                # 检查设置后的位置
                print("\n设置后各电机位置:")
                time.sleep(0.5)
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            new_pos = self.motors[motor_id].read_parameters.get_position()
                            print(f"  电机ID {motor_id}: {new_pos:.2f}度")
                    except Exception as e:
                        print(f"  电机ID {motor_id}: 读取失败 - {e}")
            else:
                print("❌ 所有电机零点设置都失败")
                
        except Exception as e:
            print(f"✗ 多机设置零点失败: {e}")
    
    def test_multi_motor_stop(self):
        """测试多机电机停止"""
        print("\n🛑 多机电机停止")
        print("=" * 50)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"将要停止的电机: {unique_motor_ids}")
        
        # 显示当前状态
        print("\n当前各电机状态:")
        for motor_id in unique_motor_ids:
            try:
                if motor_id in self.motors:
                    status = self.motors[motor_id].read_parameters.get_motor_status()
                    speed = self.motors[motor_id].read_parameters.get_speed()
                    print(f"  电机ID {motor_id}: 使能={status.enabled}, 速度={speed:.1f}RPM")
            except Exception as e:
                print(f"  电机ID {motor_id}: 状态读取失败 - {e}")
        
        confirm = input("\n确认停止所有电机? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        try:
            print("\n🚀 开始多机停止...")
            
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    print(f"  → 电机ID {motor_id}: 发送停止命令")
                    motor.control_actions.stop()
                    print(f"  ✓ 电机ID {motor_id}: 停止命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 停止命令发送失败 - {e}")
            
            if success_count > 0:
                print(f"\n✓ 成功发送停止命令到 {success_count}/{len(unique_motor_ids)} 个电机")
                
                # 检查停止后的状态
                print("\n停止后各电机状态:")
                time.sleep(1)
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            speed = self.motors[motor_id].read_parameters.get_speed()
                            print(f"  电机ID {motor_id}: 速度={speed:.1f}RPM")
                    except Exception as e:
                        print(f"  电机ID {motor_id}: 状态读取失败 - {e}")
            else:
                print("❌ 所有电机停止命令都发送失败")
                
        except Exception as e:
            print(f"✗ 多机停止失败: {e}")

    def test_multi_modify_drive_parameters(self):
        """测试多机修改驱动参数"""
        print("\n⚙️ 多机修改驱动参数")
        print("=" * 70)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"参与修改的电机: {unique_motor_ids}")
        
        # 选择修改模式
        print("\n修改模式选择:")
        print("1. 统一参数模式 - 所有电机使用相同参数")
        print("2. 独立参数模式 - 每个电机使用不同参数")
        
        try:
            mode_choice = int(input("选择模式 (1-2, 默认1): ").strip() or "1")
        except ValueError:
            mode_choice = 1
        
        if mode_choice == 1:
            # 统一参数模式
            self._modify_unified_drive_parameters(unique_motor_ids)
        elif mode_choice == 2:
            # 独立参数模式
            self._modify_individual_drive_parameters(unique_motor_ids)
        else:
            print("❌ 无效选择")
    
    def _modify_unified_drive_parameters(self, motor_ids: List[int]):
        """统一参数模式修改驱动参数"""
        print("\n📝 统一参数模式 - 所有电机使用相同参数")
        print("-" * 60)
        
        try:
            # 读取第一个电机的当前参数作为模板
            template_motor = self.motors[motor_ids[0]]
            current_params = template_motor.read_parameters.get_drive_parameters()
            print(f"使用电机ID {motor_ids[0]} 的当前参数作为模板")
        except Exception as e:
            print(f"⚠️ 读取模板参数失败，使用默认参数: {e}")
            current_params = template_motor.modify_parameters.create_default_drive_parameters()
        
        # 显示关键参数选择菜单
        print("\n选择要修改的参数:")
        print("1. 控制模式 (开环/闭环)")
        print("2. 电流设置 (开环电流/闭环最大电流)")
        print("3. 速度限制")
        print("4. 细分设置")
        print("5. 堵转保护")
        print("6. 全部参数")
        
        try:
            param_choice = int(input("选择要修改的参数类型 (1-6): ").strip())
        except ValueError:
            print("❌ 无效输入")
            return
        
        # 根据选择修改参数
        if param_choice == 1:
            # 控制模式
            mode = int(input("控制模式 (0=开环, 1=闭环FOC, 默认1): ").strip() or "1")
            current_params.control_mode = mode
            
        elif param_choice == 2:
            # 电流设置
            if current_params.control_mode == 0:
                current = int(input("开环工作电流 (mA, 默认1500): ").strip() or "1500")
                current_params.open_loop_current = current
            else:
                current = int(input("闭环最大电流 (mA, 默认2000): ").strip() or "2000")
                current_params.closed_loop_max_current = current
                
        elif param_choice == 3:
            # 速度限制
            speed_limit = int(input("最大转速限制 (RPM, 默认3000): ").strip() or "3000")
            current_params.max_speed_limit = speed_limit
            
        elif param_choice == 4:
            # 细分设置
            subdivision = int(input("细分数 (1-256, 默认64): ").strip() or "64")
            current_params.subdivision = subdivision
            interp = input("启用细分插补? (y/N): ").strip().lower() in ['y', 'yes']
            current_params.subdivision_interpolation = interp
            
        elif param_choice == 5:
            # 堵转保护
            enabled = input("启用堵转保护? (y/N): ").strip().lower() in ['y', 'yes']
            current_params.stall_protection_enabled = enabled
            if enabled:
                speed_thresh = int(input("堵转保护转速阈值 (RPM, 默认50): ").strip() or "50")
                current_thresh = int(input("堵转保护电流阈值 (mA, 默认1500): ").strip() or "1500")
                current_params.stall_protection_speed = speed_thresh
                current_params.stall_protection_current = current_thresh
                
        elif param_choice == 6:
            # 全部参数 - 简化版本
            print("快速配置选项:")
            print("1. 高性能配置")
            print("2. 高精度配置") 
            print("3. 节能配置")
            
            config_choice = int(input("选择配置 (1-3): ").strip())
            if config_choice == 1:
                # 高性能
                current_params.control_mode = 1
                current_params.closed_loop_max_current = 2500
                current_params.max_speed_limit = 4000
                current_params.subdivision = 64
            elif config_choice == 2:
                # 高精度
                current_params.control_mode = 1
                current_params.subdivision = 256
                current_params.subdivision_interpolation = True
                current_params.position_precision = True
                current_params.max_speed_limit = 2000
            elif config_choice == 3:
                # 节能
                current_params.control_mode = 1
                current_params.closed_loop_max_current = 1200
                current_params.max_speed_limit = 1500
                current_params.auto_screen_off = True
        else:
            print("❌ 无效选择")
            return
        
        # 保存选项
        save_to_chip = input("是否保存到芯片? (Y/n): ").strip().lower() in ['', 'y', 'yes']
        
        # 确认修改
        print(f"\n将对 {len(motor_ids)} 个电机应用统一参数")
        print(f"保存到芯片: {'是' if save_to_chip else '否'}")
        
        confirm = input("确认执行参数修改? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        # 执行修改
        print("\n🚀 开始多机参数修改...")
        success_count = 0
        
        for motor_id in motor_ids:
            try:
                if motor_id not in self.motors:
                    continue
                
                motor = self.motors[motor_id]
                print(f"  → 电机ID {motor_id}: 修改驱动参数")
                
                response = motor.modify_parameters.modify_drive_parameters(current_params, save_to_chip)
                if response.success:
                    print(f"  ✓ 电机ID {motor_id}: 参数修改成功")
                    success_count += 1
                else:
                    print(f"  ✗ 电机ID {motor_id}: 参数修改失败 - {response.error_message}")
                    
            except Exception as e:
                print(f"  ✗ 电机ID {motor_id}: 参数修改异常 - {e}")
        
        if success_count > 0:
            print(f"\n✓ 成功修改 {success_count}/{len(motor_ids)} 个电机的驱动参数")
            if save_to_chip:
                print("✓ 参数已保存到芯片")
            else:
                print("⚠️ 参数未保存到芯片，断电后会丢失")
        else:
            print("❌ 所有电机参数修改都失败")
    
    def _modify_individual_drive_parameters(self, motor_ids: List[int]):
        """独立参数模式修改驱动参数"""
        print("\n📝 独立参数模式 - 每个电机使用不同参数")
        print("-" * 60)
        print("⚠️ 此模式需要为每个电机单独设置参数，建议使用单电机测试工具进行详细配置")
        print("这里仅提供快速批量配置功能")
        
        # 简化的独立配置
        motor_configs = {}
        
        for motor_id in motor_ids:
            print(f"\n配置电机ID {motor_id}:")
            print("1. 高性能配置")
            print("2. 高精度配置")
            print("3. 节能配置")
            print("4. 跳过此电机")
            
            try:
                choice = int(input(f"电机ID {motor_id} 选择配置 (1-4): ").strip())
                motor_configs[motor_id] = choice
            except ValueError:
                motor_configs[motor_id] = 4  # 跳过
        
        # 保存选项
        save_to_chip = input("\n是否保存到芯片? (Y/n): ").strip().lower() in ['', 'y', 'yes']
        
        # 确认修改
        active_motors = [mid for mid, config in motor_configs.items() if config != 4]
        print(f"\n将修改 {len(active_motors)} 个电机的参数")
        
        confirm = input("确认执行独立参数修改? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        # 执行修改
        print("\n🚀 开始独立参数修改...")
        success_count = 0
        
        for motor_id, config_type in motor_configs.items():
            if config_type == 4 or motor_id not in self.motors:
                continue
                
            try:
                motor = self.motors[motor_id]
                
                # 读取当前参数
                current_params = motor.read_parameters.get_drive_parameters()
                
                # 应用配置
                if config_type == 1:  # 高性能
                    current_params.control_mode = 1
                    current_params.closed_loop_max_current = 2500
                    current_params.max_speed_limit = 4000
                    current_params.subdivision = 64
                    config_name = "高性能"
                elif config_type == 2:  # 高精度
                    current_params.control_mode = 1
                    current_params.subdivision = 256
                    current_params.subdivision_interpolation = True
                    current_params.position_precision = True
                    current_params.max_speed_limit = 2000
                    config_name = "高精度"
                elif config_type == 3:  # 节能
                    current_params.control_mode = 1
                    current_params.closed_loop_max_current = 1200
                    current_params.max_speed_limit = 1500
                    current_params.auto_screen_off = True
                    config_name = "节能"
                
                print(f"  → 电机ID {motor_id}: 应用{config_name}配置")
                
                response = motor.modify_parameters.modify_drive_parameters(current_params, save_to_chip)
                if response.success:
                    print(f"  ✓ 电机ID {motor_id}: {config_name}配置应用成功")
                    success_count += 1
                else:
                    print(f"  ✗ 电机ID {motor_id}: {config_name}配置应用失败 - {response.error_message}")
                    
            except Exception as e:
                print(f"  ✗ 电机ID {motor_id}: 配置应用异常 - {e}")
        
        if success_count > 0:
            print(f"\n✓ 成功配置 {success_count}/{len(active_motors)} 个电机")
        else:
            print("❌ 所有电机配置都失败")

    def test_multi_clear_position(self):
        """测试多机清零位置"""
        print("\n🔄 多机清零位置")
        print("=" * 60)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"将要清零的电机: {unique_motor_ids}")
        
        # 显示清零前的位置
        print("\n清零前各电机位置:")
        print(f"{'电机ID':<8} {'当前位置(度)':<15} {'状态'}")
        print("-" * 40)
        
        positions_before = {}
        for motor_id in unique_motor_ids:
            try:
                if motor_id in self.motors:
                    current_pos = self.motors[motor_id].read_parameters.get_position()
                    positions_before[motor_id] = current_pos
                    print(f"{motor_id:<8} {current_pos:<15.2f} ✓")
                else:
                    print(f"{motor_id:<8} 电机实例不存在")
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
                positions_before[motor_id] = None
        
        print("-" * 40)
        
        # 说明清零位置的作用
        print("\n📖 清零位置功能说明:")
        print("  • 清零位置会将电机的当前位置重置为0度")
        print("  • 这是一个软件操作，不会改变电机的物理位置")
        print("  • 清零后，位置读数会重新从0开始计算")
        print("  • 与'设置零点位置'不同，清零位置不涉及编码器校准")
        
        confirm = input("\n确认清零所有电机位置? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        try:
            print("\n🚀 开始多机清零位置...")
            
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    print(f"  → 电机ID {motor_id}: 执行清零位置")
                    motor.trigger_actions.clear_position()
                    print(f"  ✓ 电机ID {motor_id}: 清零位置成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 清零位置失败 - {e}")
            
            if success_count > 0:
                print(f"\n✓ 成功清零 {success_count}/{len(unique_motor_ids)} 个电机的位置")
                
                # 等待一下让清零操作生效
                print("\n等待清零操作生效...")
                time.sleep(0.5)
                
                # 显示清零后的位置
                print("\n清零后各电机位置:")
                print(f"{'电机ID':<8} {'清零前位置(度)':<15} {'清零后位置(度)':<15} {'变化量(度)':<12} {'状态'}")
                print("-" * 75)
                
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            new_pos = self.motors[motor_id].read_parameters.get_position()
                            old_pos = positions_before.get(motor_id, 0)
                            
                            if old_pos is not None:
                                change = new_pos - old_pos
                                print(f"{motor_id:<8} {old_pos:<15.2f} {new_pos:<15.2f} {change:<12.2f} ✓")
                            else:
                                print(f"{motor_id:<8} {'N/A':<15} {new_pos:<15.2f} {'N/A':<12} ✓")
                    except Exception as e:
                        print(f"{motor_id:<8} 读取失败: {e}")
                
                print("-" * 75)
                
                # 验证清零效果
                all_near_zero = True
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            new_pos = self.motors[motor_id].read_parameters.get_position()
                            if abs(new_pos) > 0.1:  # 允许0.1度的误差
                                all_near_zero = False
                                break
                    except:
                        all_near_zero = False
                        break
                
                if all_near_zero:
                    print("🎉 所有电机位置已成功清零！")
                else:
                    print("⚠️ 部分电机清零后位置不为0，可能需要检查")
                
            else:
                print("❌ 所有电机清零位置都失败")
                
        except Exception as e:
            print(f"✗ 多机清零位置失败: {e}")

    def test_multi_enable(self):
        """测试多机使能"""
        print("\n🔋 多机使能")
        print("=" * 50)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"将要使能的电机: {unique_motor_ids}")
        
        # 显示使能前的状态
        print("\n使能前各电机状态:")
        print(f"{'电机ID':<8} {'使能状态':<10} {'状态'}")
        print("-" * 30)
        
        states_before = {}
        for motor_id in unique_motor_ids:
            try:
                if motor_id in self.motors:
                    status = self.motors[motor_id].read_parameters.get_motor_status()
                    states_before[motor_id] = status.enabled
                    print(f"{motor_id:<8} {status.enabled:<10} ✓")
                else:
                    print(f"{motor_id:<8} 电机实例不存在")
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
                states_before[motor_id] = None
        
        print("-" * 30)
        
        # 统计需要使能的电机
        need_enable = [mid for mid, enabled in states_before.items() if enabled is False]
        already_enabled = [mid for mid, enabled in states_before.items() if enabled is True]
        
        if already_enabled:
            print(f"✓ 已使能的电机: {already_enabled}")
        if need_enable:
            print(f"⚠️ 需要使能的电机: {need_enable}")
        else:
            print("✓ 所有电机都已使能")
            return
        
        confirm = input("\n确认使能所有电机? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        try:
            print("\n🚀 开始多机使能...")
            
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    print(f"  → 电机ID {motor_id}: 发送使能命令")
                    motor.control_actions.enable()
                    print(f"  ✓ 电机ID {motor_id}: 使能命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 使能命令发送失败 - {e}")
            
            if success_count > 0:
                print(f"\n✓ 成功发送使能命令到 {success_count}/{len(unique_motor_ids)} 个电机")
                
                # 等待一下让使能操作生效
                print("\n等待使能操作生效...")
                time.sleep(0.5)
                
                # 显示使能后的状态
                print("\n使能后各电机状态:")
                print(f"{'电机ID':<8} {'使能前':<8} {'使能后':<8} {'状态变化':<10} {'状态'}")
                print("-" * 50)
                
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            new_status = self.motors[motor_id].read_parameters.get_motor_status()
                            old_enabled = states_before.get(motor_id, False)
                            
                            if old_enabled is not None:
                                change = "✓启用" if not old_enabled and new_status.enabled else "无变化" if old_enabled == new_status.enabled else "异常"
                                print(f"{motor_id:<8} {old_enabled:<8} {new_status.enabled:<8} {change:<10} ✓")
                            else:
                                print(f"{motor_id:<8} {'N/A':<8} {new_status.enabled:<8} {'N/A':<10} ✓")
                    except Exception as e:
                        print(f"{motor_id:<8} 状态读取失败: {e}")
                
                print("-" * 50)
                
                # 验证使能效果
                all_enabled = True
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            status = self.motors[motor_id].read_parameters.get_motor_status()
                            if not status.enabled:
                                all_enabled = False
                                break
                    except:
                        all_enabled = False
                        break
                
                if all_enabled:
                    print("🎉 所有电机都已成功使能！")
                else:
                    print("⚠️ 部分电机可能未成功使能，请检查")
                
            else:
                print("❌ 所有电机使能命令都发送失败")
                
        except Exception as e:
            print(f"✗ 多机使能失败: {e}")

    def test_multi_disable(self):
        """测试多机失能"""
        print("\n🔌 多机失能")
        print("=" * 50)
        
        if not self.connected_motor_ids:
            print("⚠️ 请先设置测试环境")
            return
        
        unique_motor_ids = sorted(set(self.connected_motor_ids))
        print(f"将要失能的电机: {unique_motor_ids}")
        
        # 显示失能前的状态
        print("\n失能前各电机状态:")
        print(f"{'电机ID':<8} {'使能状态':<10} {'当前速度(RPM)':<15} {'状态'}")
        print("-" * 50)
        
        states_before = {}
        for motor_id in unique_motor_ids:
            try:
                if motor_id in self.motors:
                    motor = self.motors[motor_id]
                    status = motor.read_parameters.get_motor_status()
                    speed = motor.read_parameters.get_speed()
                    states_before[motor_id] = {'enabled': status.enabled, 'speed': speed}
                    print(f"{motor_id:<8} {status.enabled:<10} {speed:<15.1f} ✓")
                else:
                    print(f"{motor_id:<8} 电机实例不存在")
            except Exception as e:
                print(f"{motor_id:<8} 读取失败: {e}")
                states_before[motor_id] = None
        
        print("-" * 50)
        
        # 统计需要失能的电机
        need_disable = [mid for mid, state in states_before.items() if state and state['enabled'] is True]
        already_disabled = [mid for mid, state in states_before.items() if state and state['enabled'] is False]
        
        if already_disabled:
            print(f"✓ 已失能的电机: {already_disabled}")
        if need_disable:
            print(f"⚠️ 需要失能的电机: {need_disable}")
        else:
            print("✓ 所有电机都已失能")
            return
        
        # 检查是否有电机在运动
        moving_motors = []
        for motor_id, state in states_before.items():
            if state and abs(state['speed']) > 1.0:  # 速度大于1RPM认为在运动
                moving_motors.append(motor_id)
        
        if moving_motors:
            print(f"⚠️ 检测到运动中的电机: {moving_motors}")
            print("建议先停止电机运动再失能")
        
        print("\n📖 失能操作说明:")
        print("  • 失能会切断电机的驱动电流")
        print("  • 失能后电机将失去保持力矩")
        print("  • 如果电机正在运动，失能会立即停止运动")
        print("  • 失能是安全操作，可随时重新使能")
        
        confirm = input("\n确认失能所有电机? (y/N): ").strip().lower()
        if confirm not in ['y', 'yes']:
            print("已取消操作")
            return
        
        try:
            print("\n🚀 开始多机失能...")
            
            success_count = 0
            for motor_id in unique_motor_ids:
                try:
                    if motor_id not in self.motors:
                        continue
                    
                    motor = self.motors[motor_id]
                    print(f"  → 电机ID {motor_id}: 发送失能命令")
                    motor.control_actions.disable()
                    print(f"  ✓ 电机ID {motor_id}: 失能命令发送成功")
                    success_count += 1
                    
                except Exception as e:
                    print(f"  ✗ 电机ID {motor_id}: 失能命令发送失败 - {e}")
            
            if success_count > 0:
                print(f"\n✓ 成功发送失能命令到 {success_count}/{len(unique_motor_ids)} 个电机")
                
                # 等待一下让失能操作生效
                print("\n等待失能操作生效...")
                time.sleep(0.5)
                
                # 显示失能后的状态
                print("\n失能后各电机状态:")
                print(f"{'电机ID':<8} {'失能前':<8} {'失能后':<8} {'速度变化':<12} {'状态'}")
                print("-" * 55)
                
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            motor = self.motors[motor_id]
                            new_status = motor.read_parameters.get_motor_status()
                            new_speed = motor.read_parameters.get_speed()
                            old_state = states_before.get(motor_id)
                            
                            if old_state:
                                old_enabled = old_state['enabled']
                                old_speed = old_state['speed']
                                speed_change = f"{old_speed:.1f}→{new_speed:.1f}"
                                print(f"{motor_id:<8} {old_enabled:<8} {new_status.enabled:<8} {speed_change:<12} ✓")
                            else:
                                print(f"{motor_id:<8} {'N/A':<8} {new_status.enabled:<8} {'N/A':<12} ✓")
                    except Exception as e:
                        print(f"{motor_id:<8} 状态读取失败: {e}")
                
                print("-" * 55)
                
                # 验证失能效果
                all_disabled = True
                for motor_id in unique_motor_ids:
                    try:
                        if motor_id in self.motors:
                            status = self.motors[motor_id].read_parameters.get_motor_status()
                            if status.enabled:
                                all_disabled = False
                                break
                    except:
                        all_disabled = False
                        break
                
                if all_disabled:
                    print("🎉 所有电机都已成功失能！")
                else:
                    print("⚠️ 部分电机可能未成功失能，请检查")
                
            else:
                print("❌ 所有电机失能命令都发送失败")
                
        except Exception as e:
            print(f"✗ 多机失能失败: {e}")


if __name__ == "__main__":
    tester = ZDTMultiMotorSyncTester()
    tester.run() 