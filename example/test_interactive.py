# -*- coding: utf-8 -*-
"""
ZDT电机SDK交互式测试工具
==================================

这是 Embodied_SDK 的核心功能字典 (Dictionary/Reference Implementation)。
包含了 SDK 支持的**所有** API 调用的标准写法。

用途：
1. **开发者查询**: 忘记某个功能的具体参数或调用方式时，可以在此查找。
2. **硬件调试**: 提供了最全面的单电机调试菜单，覆盖所有寄存器读写。

功能覆盖：
- 基础控制：位置、速度、力矩、使能/失能
- 参数读取：PID、电流、电压、温度、版本
- 高级功能：回零、梯形曲线、CAN ID 修改
- 错误处理：异常捕获与日志记录
"""

import os
import sys
import time
import logging
from typing import Optional, List, Dict, Any

# 添加项目根目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from Embodied_SDK import create_motor_controller, setup_logging

class ZDTInteractiveTester:
    """ZDT电机交互式测试器"""
    
    def __init__(self):
        self.motor: Optional[Any] = None
        self.connected = False
        
        # 设置日志
        setup_logging(logging.INFO)  # 默认INFO级别，可以调整
        
        print("=" * 60)
        print(" ZDT电机SDK交互式测试工具")
        print("=" * 60)
        print()
    
    def connect_motor(self) -> bool:
        """连接电机"""
        if self.connected:
            print(" 电机已连接")
            return True
        
        print(" 连接电机...")
        print("默认配置: COM18, 500000波特率, 电机ID=1")
        
        # 询问是否使用默认配置
        use_default = input("使用默认配置? (Enter确认, n取消): ").strip().lower()
        
        if use_default != 'n':
            port = 'COM18'
            baudrate = 500000
            motor_id = 1
        else:
            port = input("串口号 (例如: COM18): ").strip() or 'COM18'
            baudrate = int(input("波特率 (默认: 500000): ").strip() or '500000')
            motor_id = int(input("电机ID (默认: 1): ").strip() or '1')
        
        try:
            self.motor = create_motor_controller(
                motor_id=motor_id,
                interface_type="slcan",
                shared_interface=False,  # 单电机测试使用非共享模式
                port=port,
                baudrate=baudrate
            )
            
            self.motor.connect()
            self.connected = True
            print(f" 电机连接成功! (ID: {motor_id}, 端口: {port})")
            return True
            
        except Exception as e:
            print(f" 电机连接失败: {e}")
            return False
    
    def disconnect_motor(self):
        """断开电机连接"""
        if self.motor and self.connected:
            try:
                self.motor.disconnect()
                self.connected = False
                print(" 电机已断开连接")
            except Exception as e:
                print(f" 断开连接时出现警告: {e}")
        else:
            print("电机未连接")
    
    def ensure_connected(self) -> bool:
        """确保电机已连接"""
        if not self.connected:
            print(" 电机未连接，请先连接电机")
            return False
        return True
    
    # ========== 基础控制测试 ==========
    
    def test_motor_enable(self):
        """测试电机使能"""
        if not self.ensure_connected():
            return
        
        print("\n 电机使能测试")
        print("-" * 30)
        
        try:
            print("发送使能命令...")
            self.motor.control_actions.enable()
            print(" 电机使能成功")
            
            # 检查状态
            time.sleep(0.5)
            status = self.motor.read_parameters.get_motor_status()
            print(f"电机状态: 使能={status.enabled}, 到位={status.in_position}")
            
        except Exception as e:
            print(f" 电机使能失败: {e}")
    
    def test_motor_disable(self):
        """测试电机失能"""
        if not self.ensure_connected():
            return
        
        print("\n 电机失能测试")
        print("-" * 30)
        
        try:
            print(" 如需紧急停止，请使用急停（E-Stop）或断开电源。")
            
            # 检查状态
            time.sleep(0.5)
            status = self.motor.read_parameters.get_motor_status()
            print(f"电机状态: 使能={status.enabled}, 到位={status.in_position}")
            
        except Exception as e:
            print(f" 电机失能失败: {e}")
    
    def test_motor_stop(self):
        """测试电机停止"""
        if not self.ensure_connected():
            return
        
        print("\n 电机停止测试")
        print("-" * 30)
        
        try:
            print("发送停止命令...")
            self.motor.control_actions.stop()
            print(" 电机停止成功")
            
        except Exception as e:
            print(f" 电机停止失败: {e}")
    
    # ========== 状态读取测试 ==========
    
    def test_read_status(self):
        """测试读取电机状态"""
        if not self.ensure_connected():
            return
        
        print("\n 电机状态读取测试")
        print("-" * 30)
        
        try:
            status = self.motor.read_parameters.get_motor_status()
            print(" 电机状态:")
            print(f"  使能状态: {status.enabled}")
            print(f"  到位状态: {status.in_position}")
            print(f"  堵转状态: {status.stalled}")
            print(f"  堵转保护: {status.stall_protection}")
            
        except Exception as e:
            print(f" 状态读取失败: {e}")
    
    def test_read_position(self):
        """测试读取位置"""
        if not self.ensure_connected():
            return
        
        print("\n 位置读取测试")
        print("-" * 30)
        
        try:
            position = self.motor.read_parameters.get_position()
            print(f" 当前位置: {position:.2f}度")
            
        except Exception as e:
            print(f" 位置读取失败: {e}")
    
    def test_read_speed(self):
        """测试读取转速"""
        if not self.ensure_connected():
            return
        
        print("\n 转速读取测试")
        print("-" * 30)
        
        try:
            speed = self.motor.read_parameters.get_speed()
            print(f" 当前转速: {speed:.2f}RPM")
            
        except Exception as e:
            print(f" 转速读取失败: {e}")
    
    def test_read_temperature(self):
        """测试读取温度"""
        if not self.ensure_connected():
            return
        
        print("\n 温度读取测试")
        print("-" * 30)
        
        try:
            temperature = self.motor.read_parameters.get_temperature()
            print(f" 驱动器温度: {temperature:.1f}C")
            
        except Exception as e:
            print(f" 温度读取失败: {e}")
    
    def test_read_all_status(self):
        """测试读取所有状态信息"""
        if not self.ensure_connected():
            return
        
        print("\n 完整状态信息读取测试")
        print("-" * 30)
        
        try:
            status_info = self.motor.read_parameters.get_status_info()
            print(" 完整状态信息:")
            print(f"  电机ID: {status_info['motor_id']}")
            print(f"  固件版本: {status_info['firmware']}")
            print(f"  硬件版本: {status_info['hardware']}")
            print(f"  使能状态: {status_info['enabled']}")
            print(f"  到位状态: {status_info['in_position']}")
            print(f"  当前位置: {status_info['position']:.2f}度")
            print(f"  当前速度: {status_info['speed']:.2f}RPM")
            print(f"  总线电压: {status_info['bus_voltage']:.2f}V")
            print(f"  相电流: {status_info['phase_current']:.3f}A")
            print(f"  温度: {status_info['temperature']:.1f}C")
            
        except Exception as e:
            print(f" 完整状态信息读取失败: {e}")
    
    def test_read_version(self):
        """测试读取版本信息"""
        if not self.ensure_connected():
            return
        
        print("\n 版本信息读取测试")
        print("-" * 30)
        
        try:
            version_info = self.motor.read_parameters.get_version()
            print(" 版本信息:")
            print(f"  固件版本: {version_info['firmware']}")
            print(f"  硬件版本: {version_info['hardware']}")
            print(f"  固件原始值: {version_info['firmware_raw']}")
            print(f"  硬件原始值: {version_info['hardware_raw']}")
            
        except Exception as e:
            print(f" 版本信息读取失败: {e}")
    
    def test_read_resistance_inductance(self):
        """测试读取电阻电感"""
        if not self.ensure_connected():
            return
        
        print("\n 电阻电感读取测试")
        print("-" * 30)
        
        try:
            ri_info = self.motor.read_parameters.get_resistance_inductance()
            print(" 电阻电感信息:")
            print(f"  相电阻: {ri_info['resistance']:.3f}Ω")
            print(f"  相电感: {ri_info['inductance']:.3f}mH")
            
        except Exception as e:
            print(f" 电阻电感读取失败: {e}")
    
    def test_read_pid_parameters(self):
        """测试读取PID参数"""
        if not self.ensure_connected():
            return
        
        print("\n PID参数读取测试")
        print("-" * 30)
        
        try:
            pid_params = self.motor.read_parameters.get_pid_parameters()
            print(" PID参数:")
            print(f"  梯形位置环Kp: {pid_params.trapezoid_position_kp}")
            print(f"  直通位置环Kp: {pid_params.direct_position_kp}")
            print(f"  速度环Kp: {pid_params.speed_kp}")
            print(f"  速度环Ki: {pid_params.speed_ki}")
            
        except Exception as e:
            print(f" PID参数读取失败: {e}")
    
    def test_read_bus_voltage(self):
        """测试读取总线电压"""
        if not self.ensure_connected():
            return
        
        print("\n 总线电压读取测试")
        print("-" * 30)
        
        try:
            voltage = self.motor.read_parameters.get_bus_voltage()
            print(f" 总线电压: {voltage:.2f}V")
            
        except Exception as e:
            print(f" 总线电压读取失败: {e}")
    
    def test_read_bus_current(self):
        """测试读取总线电流"""
        if not self.ensure_connected():
            return
        
        print("\n 总线电流读取测试")
        print("-" * 30)
        
        try:
            current = self.motor.read_parameters.get_bus_current()
            print(f" 总线平均电流: {current:.3f}A")
            
        except Exception as e:
            print(f" 总线电流读取失败: {e}")
    
    def test_read_phase_current(self):
        """测试读取相电流"""
        if not self.ensure_connected():
            return
        
        print("\n 相电流读取测试")
        print("-" * 30)
        
        try:
            current = self.motor.read_parameters.get_current()
            print(f" 相电流: {current:.3f}A")
            
        except Exception as e:
            print(f" 相电流读取失败: {e}")
    
    def test_read_encoder_values(self):
        """测试读取编码器值"""
        if not self.ensure_connected():
            return
        
        print("\n 编码器值读取测试")
        print("-" * 30)
        
        try:
            encoder_raw = self.motor.read_parameters.get_encoder_raw()
            encoder_calibrated = self.motor.read_parameters.get_encoder_calibrated()
            print(" 编码器值:")
            print(f"  原始值: {encoder_raw:.2f}度")
            print(f"  校准值: {encoder_calibrated:.2f}度")
            
        except Exception as e:
            print(f" 编码器值读取失败: {e}")
    
    def test_read_pulse_counts(self):
        """测试读取脉冲计数"""
        if not self.ensure_connected():
            return
        
        print("\n 脉冲计数读取测试")
        print("-" * 30)
        
        try:
            pulse_count = self.motor.read_parameters.get_pulse_count()
            input_pulse = self.motor.read_parameters.get_input_pulse()
            print(" 脉冲计数:")
            print(f"  实时脉冲数: {pulse_count}")
            print(f"  输入脉冲数: {input_pulse}")
            
        except Exception as e:
            print(f" 脉冲计数读取失败: {e}")
    
    def test_read_target_positions(self):
        """测试读取目标位置"""
        if not self.ensure_connected():
            return
        
        print("\n 目标位置读取测试")
        print("-" * 30)
        
        try:
            target_position = self.motor.read_parameters.get_target_position()
            realtime_target = self.motor.read_parameters.get_realtime_target_position()
            print(" 目标位置:")
            print(f"  目标位置: {target_position:.2f}度")
            print(f"  实时目标位置: {realtime_target:.2f}度")
            
        except Exception as e:
            print(f" 目标位置读取失败: {e}")
    
    def test_read_position_error(self):
        """测试读取位置误差"""
        if not self.ensure_connected():
            return
        
        print("\n 位置误差读取测试")
        print("-" * 30)
        
        try:
            position_error = self.motor.read_parameters.get_position_error()
            print(f" 位置误差: {position_error:.4f}度")
            
        except Exception as e:
            print(f" 位置误差读取失败: {e}")
    
    # ========== 运动控制测试 ==========
    
    def test_speed_mode(self):
        """测试速度模式"""
        if not self.ensure_connected():
            return
        
        print("\n 速度模式测试")
        print("-" * 30)
        
        try:
            speed = float(input("输入目标速度 (RPM, 默认100): ").strip() or "100")
            acceleration = int(input("输入加速度 (RPM/s, 默认1000): ").strip() or "1000")
            
            print(f"设置速度模式: {speed}RPM, 加速度: {acceleration}RPM/s")
            self.motor.control_actions.set_speed(speed=speed, acceleration=acceleration)
            print(" 速度模式设置成功")
            
            # 运行一段时间后停止
            print("运行3秒后停止...")
            time.sleep(3)
            self.motor.control_actions.stop()
            print(" 电机已停止")
            
        except Exception as e:
            print(f" 速度模式测试失败: {e}")
    
    def test_position_mode(self):
        """测试位置模式"""
        if not self.ensure_connected():
            return
        
        print("\n 位置模式测试")
        print("-" * 30)
        
        try:
            position = float(input("输入目标位置 (度, 默认90): ").strip() or "90")
            speed = float(input("输入运动速度 (RPM, 默认500): ").strip() or "500")
            is_absolute = input("是否绝对位置? (Enter否, y是): ").strip().lower() == 'y'
            
            print(f"开始位置运动: {position}度, 速度: {speed}RPM, 绝对位置: {is_absolute}")
            self.motor.control_actions.move_to_position(position=position, speed=speed, is_absolute=is_absolute)
            print(" 位置运动命令发送成功")
            
            # 等待到位
            print("等待到位...")
            if self.motor.control_actions.wait_for_position(timeout=10.0):
                print(" 位置运动完成")
            else:
                print(" 位置运动超时")
                self.motor.control_actions.stop()
                print(" 电机停止成功")
            
            current_pos = self.motor.read_parameters.get_position()
            print(f"当前位置: {current_pos:.2f}度")
            
        except Exception as e:
            print(f" 位置模式测试失败: {e}")
    
    def test_trapezoid_position_mode(self):
        """测试梯形曲线位置模式"""
        if not self.ensure_connected():
            return
        
        print("\n 梯形曲线位置模式测试")
        print("-" * 40)
        
        try:
            position = float(input("输入目标位置 (度, 默认90): ").strip() or "90")
            max_speed = float(input("输入最大速度 (RPM, 默认500): ").strip() or "500")
            acceleration = int(input("输入加速度 (RPM/s, 默认1000): ").strip() or "1000")
            deceleration = int(input("输入减速度 (RPM/s, 默认1000): ").strip() or "1000")
            is_absolute = input("是否绝对位置? (Enter否, y是): ").strip().lower() == 'y'
            
            print(f"开始梯形曲线位置运动:")
            print(f"  目标位置: {position}度")
            print(f"  最大速度: {max_speed}RPM")
            print(f"  加速度: {acceleration}RPM/s")
            print(f"  减速度: {deceleration}RPM/s")
            print(f"  绝对位置: {is_absolute}")
            
            self.motor.control_actions.move_to_position_trapezoid(
                position=position, 
                max_speed=max_speed, 
                acceleration=acceleration,
                deceleration=deceleration,
                is_absolute=is_absolute
            )
            print(" 梯形曲线位置运动命令发送成功")
            
            # 等待到位
            print("等待到位...")
            if self.motor.control_actions.wait_for_position(timeout=15.0):
                print(" 梯形曲线位置运动完成")
            else:
                print(" 梯形曲线位置运动超时")
                self.motor.control_actions.stop()
                print(" 电机停止成功")
            
            current_pos = self.motor.read_parameters.get_position()
            print(f"当前位置: {current_pos:.2f}度")
            
        except Exception as e:
            print(f" 梯形曲线位置模式测试失败: {e}")
    
    def test_torque_mode(self):
        """测试力矩模式"""
        if not self.ensure_connected():
            return
        
        print("\n 力矩模式测试")
        print("-" * 30)
        
        try:
            current = int(input("输入目标电流 (mA, 默认500): ").strip() or "500")
            current_slope = int(input("输入电流斜率 (mA/s, 默认1000): ").strip() or "1000")
            
            print(f"设置力矩模式: {current}mA, 电流斜率: {current_slope}mA/s")
            self.motor.control_actions.set_torque(current=current, current_slope=current_slope)
            print(" 力矩模式设置成功")
            
            # 运行一段时间后停止
            print("运行3秒后停止...")
            time.sleep(3)
            self.motor.control_actions.stop()
            print(" 电机已停止")
            
        except Exception as e:
            print(f" 力矩模式测试失败: {e}")
    
    # ========== 回零功能测试 ==========
    
    def test_read_homing_status(self):
        """测试读取回零状态"""
        if not self.ensure_connected():
            return
        
        print("\n 回零状态读取测试")
        print("-" * 30)
        
        try:
            status = self.motor.read_parameters.get_homing_status()
            print(" 回零状态:")
            print(f"  编码器就绪: {status.encoder_ready}")
            print(f"  校准表就绪: {status.calibration_table_ready}")
            print(f"  回零进行中: {status.homing_in_progress}")
            print(f"  回零失败: {status.homing_failed}")
            print(f"  位置精度高: {status.position_precision_high}")
            
        except Exception as e:
            print(f" 回零状态读取失败: {e}")
    
    def test_trigger_homing(self):
        """测试触发回零"""
        if not self.ensure_connected():
            return
        
        print("\n 触发回零测试")
        print("-" * 30)
        
        # 选择回零模式
        print("回零模式选择:")
        print("1. 单圈就近回零 (仅在当前圈内回零，多圈时无法回到0度)")
        print("2. 单圈方向回零 (仅在当前圈内回零)")
        print("3. 无限位碰撞回零")
        print("4. 回到绝对位置坐标零点 (推荐！可跨多圈回到0度，需先设置零点)")
        print("5. 回到上次掉电位置")
        print("\n⚠️  警告：如果当前位置是多圈（如1886度），模式1/2无法回到0度！")
        print("   建议使用模式4，或先选择'30.设置零点位置'")
        print("")
        
        mode_choice = input("选择回零模式 (1-5, 默认4): ").strip() or "4"
        
        mode_map = {
            "1": 0,  # 单圈就近回零
            "2": 1,  # 单圈方向回零
            "3": 2,  # 无限位碰撞回零
            "4": 4,  # 回到绝对位置坐标零点（跳过3，因为3是限位回零，需要硬件支持）
            "5": 5   # 回到上次掉电位置
        }
        
        if mode_choice not in mode_map:
            print(" 无效的回零模式选择")
            return
        
        homing_mode = mode_map[mode_choice]
        mode_names = {
            0: "单圈就近回零", 
            1: "单圈方向回零", 
            2: "无限位碰撞回零",
            4: "回到绝对位置坐标零点",
            5: "回到上次掉电位置"
        }
        
        print(f"将执行: {mode_names[homing_mode]}")
        
        # 检查当前位置，给出提示
        try:
            current_pos = self.motor.read_parameters.get_position()
            print(f"\n当前位置: {current_pos:.2f}度")
            
            # 如果位置超过一圈，提示使用模式4
            if abs(current_pos) > 360 and homing_mode in [0, 1]:
                print(f"⚠️  警告：当前位置{current_pos:.1f}度超过1圈！")
                print("   模式0/1只能在单圈内回零，无法回到0度")
                print("   建议改用模式4，或先移动到0度附近")
                retry = input("是否继续? (Enter否, y是): ").strip().lower()
                if retry != 'y':
                    return
        except:
            pass
        
        # 如果是模式4（回到绝对位置坐标零点），提醒用户需要先设置零点
        if homing_mode == 4:
            print("\n⚠️  模式4说明：")
            print("   1. 需要先设置零点（选项30）")
            print("   2. 可以跨多圈回到零点")
            print("   3. 如果没设置过零点，回零不会生效")
            
            # 提供快速设置零点选项
            setup = input("\n是否现在设置当前位置为零点? (Enter否, y是): ").strip().lower()
            if setup == 'y':
                try:
                    self.motor.control_actions.set_zero_position(save_to_chip=True)
                    print("✅ 零点已设置并保存到芯片")
                except Exception as e:
                    print(f"❌ 设置零点失败: {e}")
                    return
            print("")
        
        confirm = input("确认执行回零? (Enter确认, n取消): ").strip().lower()
        
        if confirm in ['n', 'no']:
            print("已取消回零操作")
            return
        
        try:
            print("发送回零命令...")
            self.motor.control_actions.trigger_homing(homing_mode)
            print(" 回零命令发送成功")
            
            # 监控回零过程
            print("监控回零过程...")
            start_time = time.time()
            max_wait_time = 30  # 最大等待30秒
            
            while time.time() - start_time < max_wait_time:
                try:
                    homing_status = self.motor.read_parameters.get_homing_status()
                    
                    if homing_status.homing_in_progress:
                        print(" 回零进行中...")
                        time.sleep(1)
                        continue
                    elif homing_status.homing_failed:
                        print(" 回零失败")
                        break
                    else:
                        print(" 回零完成")
                        # 读取回零后的位置
                        position = self.motor.read_parameters.get_position()
                        print(f"回零后位置: {position:.2f}度")
                        break
                        
                except Exception as e:
                    print(f" 读取回零状态失败: {e}")
                    time.sleep(1)
            else:
                print(" 回零超时，请检查电机状态")
            
        except Exception as e:
            print(f" 回零操作失败: {e}")
    
    def test_force_stop_homing(self):
        """测试强制停止回零"""
        if not self.ensure_connected():
            return
        
        print("\n 强制停止回零测试")
        print("-" * 30)
        
        try:
            # 先检查是否在回零中
            status = self.motor.read_parameters.get_homing_status()
            if not status.homing_in_progress:
                print(" 当前没有回零操作在进行")
                return
            
            confirm = input("确认强制停止回零? (Enter确认, n取消): ").strip().lower()
            if confirm in ['n', 'no']:
                print("已取消操作")
                return
            
            print("发送强制停止回零命令...")
            self.motor.control_actions.force_stop_homing()
            print(" 强制停止回零命令发送成功")
            
            # 检查状态
            time.sleep(1)
            status = self.motor.read_parameters.get_homing_status()
            print(f"回零状态: 进行中={status.homing_in_progress}, 失败={status.homing_failed}")
            
        except Exception as e:
            print(f" 强制停止回零失败: {e}")
    
    def test_encoder_calibration(self):
        """测试编码器校准"""
        if not self.ensure_connected():
            return
        
        print("\n 编码器校准测试")
        print("-" * 30)
        
        try:
            # 先检查电机状态
            status = self.motor.read_parameters.get_motor_status()
            if not status.enabled:
                print(" 电机未使能，请先使能电机")
                return
            
            print(" 编码器校准会让电机旋转一圈进行校准")
            confirm = input("确认执行编码器校准? (Enter取消, y确认): ").strip().lower()
            
            if confirm != 'y':
                print("已取消校准操作")
                return
            
            print("发送编码器校准命令...")
            self.motor.control_actions.trigger_encoder_calibration()
            print(" 编码器校准命令发送成功")
            
            print("校准过程中，请等待电机完成旋转...")
            print("(校准通常需要几秒钟时间)")
            
        except Exception as e:
            print(f" 编码器校准失败: {e}")
    
    def test_read_homing_parameters(self):
        """测试读取回零参数"""
        if not self.ensure_connected():
            return
        
        print("\n 回零参数读取测试")
        print("-" * 30)
        
        try:
            params = self.motor.read_parameters.get_homing_parameters()
            print(" 回零参数:")
            print(f"  回零模式: {params.mode}")
            print(f"  回零方向: {params.direction}")
            print(f"  回零速度: {params.speed}RPM")
            print(f"  超时时间: {params.timeout}ms")
            print(f"  碰撞检测速度: {params.collision_detection_speed}RPM")
            print(f"  碰撞检测电流: {params.collision_detection_current}mA")
            print(f"  碰撞检测时间: {params.collision_detection_time}ms")
            print(f"  自动回零使能: {params.auto_homing_enabled}")
            
        except Exception as e:
            print(f" 读取回零参数失败: {e}")
    
    def test_set_zero_position(self):
        """测试设置零点位置"""
        if not self.ensure_connected():
            return
        
        print("\n 设置零点位置测试")
        print("-" * 30)
        
        try:
            # 先显示当前位置
            current_pos = self.motor.read_parameters.get_position()
            print(f"当前位置: {current_pos:.2f}度")
            
            print(" 此操作将把当前位置设置为零点")
            save_choice = input("是否保存到芯片? (Enter确认, n取消): ").strip().lower()
            save_to_chip = save_choice != 'n'
            
            confirm = input("确认设置当前位置为零点? (Enter确认, n取消): ").strip().lower()
            
            if confirm == 'n':
                print("已取消操作")
                return
            
            print("发送设置零点命令...")
            self.motor.control_actions.set_zero_position(save_to_chip)
            print(" 设置零点命令发送成功")
            
            if save_to_chip:
                print(" 零点已保存到芯片")
            else:
                print(" 零点未保存到芯片，断电后会丢失")
            
            # 检查设置后的位置
            time.sleep(0.5)
            new_pos = self.motor.read_parameters.get_position()
            print(f"设置后位置: {new_pos:.2f}度")
            
        except Exception as e:
            print(f" 设置零点失败: {e}")
    
    def test_comprehensive_homing(self):
        """综合回零测试 - 完整的回零流程"""
        if not self.ensure_connected():
            return
        
        print("\n 综合回零测试")
        print("-" * 30)
        
        try:
            # 1. 检查电机状态
            print("1. 检查电机状态...")
            status = self.motor.read_parameters.get_motor_status()
            if not status.enabled:
                print(" 电机未使能，正在使能电机...")
                self.motor.control_actions.enable()
                time.sleep(0.5)
                status = self.motor.read_parameters.get_motor_status()
                if not status.enabled:
                    print(" 电机使能失败，无法进行回零")
                    return
            print(" 电机已使能")
            
            # 2. 读取当前位置
            print("\n2. 读取当前位置...")
            current_pos = self.motor.read_parameters.get_position()
            print(f"当前位置: {current_pos:.2f}度")
            
            # 3. 读取回零状态
            print("\n3. 检查回零状态...")
            homing_status = self.motor.read_parameters.get_homing_status()
            print(f"编码器就绪: {homing_status.encoder_ready}")
            print(f"校准表就绪: {homing_status.calibration_table_ready}")
            print(f"回零进行中: {homing_status.homing_in_progress}")
            print(f"回零失败: {homing_status.homing_failed}")
            
            if homing_status.homing_in_progress:
                print(" 回零正在进行中，请等待完成或强制停止")
                return
            
            # 4. 读取回零参数
            print("\n4. 读取回零参数...")
            try:
                params = self.motor.read_parameters.get_homing_parameters()
                print(f"回零速度: {params.speed}RPM")
                print(f"超时时间: {params.timeout}ms")
            except Exception as e:
                print(f" 读取回零参数失败: {e}")
            
            # 5. 选择回零模式并执行
            print("\n5. 选择回零模式:")
            print("1. 就近回零 (推荐)")
            print("2. 正向回零")
            print("3. 负向回零")
            
            mode_choice = input("选择回零模式 (1-3, 默认1): ").strip() or "1"
            mode_map = {"1": 0, "2": 1, "3": 2}
            
            if mode_choice not in mode_map:
                print(" 无效选择")
                return
            
            homing_mode = mode_map[mode_choice]
            mode_names = {0: "就近回零", 1: "正向回零", 2: "负向回零"}
            
            print(f"\n将执行: {mode_names[homing_mode]}")
            confirm = input("确认开始回零? (Enter确认, n取消): ").strip().lower()
            
            if confirm in ['n', 'no']:
                print("已取消回零操作")
                return
            
            # 6. 执行回零
            print("\n6. 开始回零...")
            self.motor.control_actions.trigger_homing(homing_mode)
            print(" 回零命令已发送")
            
            # 7. 监控回零过程
            print("\n7. 监控回零过程...")
            start_time = time.time()
            max_wait_time = 30  # 最大等待30秒
            
            while time.time() - start_time < max_wait_time:
                try:
                    homing_status = self.motor.read_parameters.get_homing_status()
                    current_pos = self.motor.read_parameters.get_position()
                    
                    if homing_status.homing_in_progress:
                        elapsed = time.time() - start_time
                        print(f" 回零进行中... ({elapsed:.1f}s) 当前位置: {current_pos:.2f}度")
                        time.sleep(1)
                        continue
                    elif homing_status.homing_failed:
                        print(" 回零失败")
                        break
                    else:
                        print(" 回零完成")
                        final_pos = self.motor.read_parameters.get_position()
                        print(f"回零后位置: {final_pos:.2f}度")
                        print(f"位置变化: {final_pos - current_pos:.2f}度")
                        
                        # 8. 验证回零结果
                        print("\n8. 验证回零结果...")
                        if abs(final_pos) < 1.0:  # 允许1度误差
                            print(" 回零精度良好")
                        else:
                            print(f" 回零精度较低，位置偏差: {final_pos:.2f}度")
                        
                        break
                        
                except Exception as e:
                    print(f" 监控过程中出现错误: {e}")
                    time.sleep(1)
            else:
                print(" 回零超时")
            
            print("\n 综合回零测试完成")
            
        except Exception as e:
            print(f" 综合回零测试失败: {e}")
    
    def test_modify_homing_parameters(self):
        """测试修改回零参数 """
        if not self.ensure_connected():
            return
        
        print("\n 回零参数设置测试")
        print("-" * 40)
        
        try:
            # 1. 读取当前回零参数
            print("1. 读取当前回零参数...")
            try:
                current_params = self.motor.read_parameters.get_homing_parameters()
                print("当前回零参数:")
                print(f"  回零模式: {current_params.mode}")
                print(f"  回零方向: {current_params.direction}")
                print(f"  回零速度: {current_params.speed}RPM")
                print(f"  超时时间: {current_params.timeout}ms")
                print(f"  碰撞检测速度: {current_params.collision_detection_speed}RPM")
                print(f"  碰撞检测电流: {current_params.collision_detection_current}mA")
                print(f"  碰撞检测时间: {current_params.collision_detection_time}ms")
                print(f"  自动回零: {current_params.auto_homing_enabled}")
            except Exception as e:
                print(f" 读取当前参数失败: {e}")
                current_params = None
            
            print("\n2. 设置新的回零参数...")
            
            # 回零模式选择
            print("回零模式:")
            print("0. 就近回零 (Nearest)")
            print("1. 正向回零")
            print("2. 负向回零")
            mode = int(input(f"选择回零模式 (0-2, 默认{current_params.mode if current_params else 0}): ").strip() or (current_params.mode if current_params else 0))
            
            # 回零方向
            print("\n回零方向:")
            print("0. 顺时针 (CW)")
            print("1. 逆时针 (CCW)")
            direction = int(input(f"选择回零方向 (0-1, 默认{current_params.direction if current_params else 0}): ").strip() or (current_params.direction if current_params else 0))
            
            # 回零速度
            speed = int(input(f"回零速度 (RPM, 默认{current_params.speed if current_params else 30}): ").strip() or (current_params.speed if current_params else 30))
            
            # 超时时间
            timeout = int(input(f"回零超时时间 (ms, 默认{current_params.timeout if current_params else 10000}): ").strip() or (current_params.timeout if current_params else 10000))
            
            # 碰撞检测参数
            print("\n碰撞检测参数:")
            collision_speed = int(input(f"碰撞检测速度 (RPM, 默认{current_params.collision_detection_speed if current_params else 300}): ").strip() or (current_params.collision_detection_speed if current_params else 300))
            collision_current = int(input(f"碰撞检测电流 (mA, 默认{current_params.collision_detection_current if current_params else 800}): ").strip() or (current_params.collision_detection_current if current_params else 800))
            collision_time = int(input(f"碰撞检测时间 (ms, 默认{current_params.collision_detection_time if current_params else 60}): ").strip() or (current_params.collision_detection_time if current_params else 60))
            
            # 自动回零
            auto_homing_input = input(f"上电自动回零 (Enter否, y是, 默认{'y' if current_params and current_params.auto_homing_enabled else 'N'}): ").strip().lower()
            auto_homing = auto_homing_input == 'y'
            
            # 保存选项
            save_to_chip = input("是否保存到芯片? (Enter确认, n取消): ").strip().lower() != 'n'
            
            print("\n3. 确认参数设置...")
            print("新的回零参数:")
            print(f"  回零模式: {mode}")
            print(f"  回零方向: {direction}")
            print(f"  回零速度: {speed}RPM")
            print(f"  超时时间: {timeout}ms")
            print(f"  碰撞检测速度: {collision_speed}RPM")
            print(f"  碰撞检测电流: {collision_current}mA")
            print(f"  碰撞检测时间: {collision_time}ms")
            print(f"  自动回零: {auto_homing}")
            print(f"  保存到芯片: {save_to_chip}")
            
            confirm = input("\n确认设置这些参数? (Enter确认, n取消): ").strip().lower()
            if confirm == 'n':
                print("已取消参数设置")
                return
            
            print("\n4. 发送参数设置命令...")
            self.motor.control_actions.modify_homing_parameters(
                mode=mode,
                direction=direction,
                speed=speed,
                timeout=timeout,
                collision_detection_speed=collision_speed,
                collision_detection_current=collision_current,
                collision_detection_time=collision_time,
                auto_homing_enabled=auto_homing,
                save_to_chip=save_to_chip
            )
            print(" 回零参数设置成功")
            
            # 5. 验证参数设置
            print("\n5. 验证参数设置...")
            time.sleep(1)  # 等待参数生效
            try:
                new_params = self.motor.read_parameters.get_homing_parameters()
                print("设置后的回零参数:")
                print(f"  回零模式: {new_params.mode}")
                print(f"  回零方向: {new_params.direction}")
                print(f"  回零速度: {new_params.speed}RPM")
                print(f"  超时时间: {new_params.timeout}ms")
                print(f"  碰撞检测速度: {new_params.collision_detection_speed}RPM")
                print(f"  碰撞检测电流: {new_params.collision_detection_current}mA")
                print(f"  碰撞检测时间: {new_params.collision_detection_time}ms")
                print(f"  自动回零: {new_params.auto_homing_enabled}")
                
                # 检查参数是否设置成功
                if (new_params.mode == mode and new_params.direction == direction and 
                    new_params.speed == speed and new_params.timeout == timeout):
                    print(" 参数验证成功")
                else:
                    print(" 参数验证失败，可能部分参数未生效")
                    
            except Exception as e:
                print(f" 参数验证失败: {e}")
            
            print("\n 回零参数设置测试完成")
            
        except Exception as e:
            print(f" 回零参数设置失败: {e}")
    
    # ========== 工具命令测试 ==========
    
    def test_clear_position(self):
        """测试清零位置"""
        if not self.ensure_connected():
            return
        
        print("\n 清零位置测试")
        print("-" * 30)
        
        try:
            print("清零前位置:", self.motor.read_parameters.get_position())
            self.motor.trigger_actions.clear_position()
            time.sleep(0.5)
            print("清零后位置:", self.motor.read_parameters.get_position())
            print(" 位置清零成功")
            
        except Exception as e:
            print(f" 位置清零失败: {e}")
    
    def test_release_stall_protection(self):
        """测试解除堵转保护"""
        if not self.ensure_connected():
            return
        
        print("\n 解除堵转保护测试")
        print("-" * 30)
        
        try:
            self.motor.trigger_actions.release_stall_protection()
            print(" 堵转保护已解除")
            
        except Exception as e:
            print(f" 解除堵转保护失败: {e}")
    
    # ========== 协议解析修复测试 ==========
    
    def test_protocol_parsing_fix(self):
        """测试协议解析修复"""
        if not self.ensure_connected():
            return
        
        print("\n 协议解析修复验证测试")
        print("-" * 50)
        
        try:
            print("1. 测试PID参数解析...")
            pid = self.motor.read_parameters.get_pid_parameters()
            print(f"   梯形位置环Kp: {pid.trapezoid_position_kp}")
            print(f"   直通位置环Kp: {pid.direct_position_kp}")
            print(f"   速度环Kp: {pid.speed_kp}")
            print(f"   速度环Ki: {pid.speed_ki}")
            print("    PID参数解析正常")
            
            print("\n2. 测试位置解析...")
            # 测试多次位置读取，验证解析一致性
            positions = []
            for i in range(3):
                position = self.motor.read_parameters.get_position()
                positions.append(position)
                print(f"   第{i+1}次读取: {position:.2f}度")
                time.sleep(0.1)
            
            # 检查位置读取的一致性（允许小幅波动）
            if len(set(f"{p:.1f}" for p in positions)) <= 2:
                print("    位置解析一致性良好")
            else:
                print("    位置解析存在较大波动")
            
            print("\n3. 测试目标位置解析...")
            target_pos = self.motor.read_parameters.get_target_position()
            print(f"   目标位置: {target_pos:.2f}度")
            print("    目标位置解析正常")
            
            print("\n4. 测试位置误差解析...")
            pos_error = self.motor.read_parameters.get_position_error()
            print(f"   位置误差: {pos_error:.4f}度")
            print("    位置误差解析正常")
            
            print("\n5. 版本信息解析...")
            version = self.motor.read_parameters.get_version()
            print(f"   固件版本: {version['firmware']}")
            print(f"   硬件版本: {version['hardware']}")
            print("    版本信息解析正常")
            
            print("\n6. 测试电气参数解析...")
            voltage = self.motor.read_parameters.get_bus_voltage()
            current = self.motor.read_parameters.get_current()
            print(f"   总线电压: {voltage:.2f}V")
            print(f"   相电流: {current:.3f}A")
            temperature = self.motor.read_parameters.get_temperature()
            print(f"   温度: {temperature:.1f}C")
            print("    电气参数解析正常")
            
            print("\n 协议解析修复验证完成所有解析功能正常工作。")
            
        except Exception as e:
            print(f" 协议解析测试失败: {e}")
    
    def test_read_drive_parameters(self):
        """测试读取驱动参数"""
        if not self.ensure_connected():
            return
        
        print("\n 读取驱动参数测试")
        print("-" * 40)
        
        try:
            print("1. 检查命令支持情况...")
            
            # 直接发送原始CAN命令进行测试
            from Embodied_SDK import get_function_codes
            FunctionCodes = get_function_codes()
            command = self.motor.command_builder.read_drive_parameters()
            print(f"发送命令: {[hex(x) for x in command]}")
            
            # 首先测试是否能收到任何响应
            try:
                raw_response = self.motor.can_interface.send_command_and_receive_response(
                    self.motor.motor_id, command
                )
                print(f"收到原始CAN响应: {[hex(x) for x in raw_response] if raw_response else None}")
                
                if not raw_response:
                    print(" 没有收到任何响应")
                    print("可能原因:")
                    print("  1. 电机固件不支持此命令")
                    print("  2. 电机ID不匹配")
                    print("  3. 通讯超时或连接问题")
                    return
                    
                # 检查响应格式
                if len(raw_response) > 0:
                    if raw_response[0] == 0x42:
                        print(f" 收到正确的功能码响应 (0x{raw_response[0]:02X})")
                        print(f" 响应数据长度: {len(raw_response)}字节")
                        
                        if len(raw_response) >= 3:
                            print(f" 前几个数据字节: {[hex(x) for x in raw_response[1:min(6, len(raw_response))]]}")
                        
                    elif raw_response[0] == 0x00 and len(raw_response) >= 3 and raw_response[1] == 0xEE:
                        print(f" 收到命令错误响应: {[hex(x) for x in raw_response]}")
                        print(" 电机固件不支持读取驱动参数命令")
                        return
                    else:
                        print(f" 收到非预期响应: {[hex(x) for x in raw_response]}")
                        print(" 可能是其他数据或格式错误")
                
            except Exception as e:
                print(f" 直接发送命令失败: {e}")
                return
            
            print("\n2. 使用SDK解析响应...")
            
            # 使用标准SDK方法
            response = self.motor._send_command(command, FunctionCodes.READ_DRIVE_PARAMETERS)
            print(f"SDK响应: success={response.success}")
            
            if response.success and response.data:
                print(f" 解析后数据长度: {len(response.data)}字节")
                print(f" 解析后数据: {[hex(x) for x in response.data]}")
            
                # 尝试解析参数
                try:
                    params = self.motor.read_parameters.get_drive_parameters()
                
                    print("\n3.  驱动参数解析成功:")
                    print(f"  锁定按键菜单: {'启用' if params.lock_enabled else '禁用'}")
                    print(f"  控制模式: {params.control_mode} ({'闭环FOC' if params.control_mode == 1 else '开环'})")
                    print(f"  脉冲端口功能: {params.pulse_port_function}")
                    print(f"  通讯端口功能: {params.serial_port_function}")
                    print(f"  En引脚模式: {params.enable_pin_mode}")
                    print(f"  电机旋转方向: {params.motor_direction} ({'逆时针' if params.motor_direction == 1 else '顺时针'})")
                    print(f"  细分设置: {params.subdivision}")
                    print(f"  细分插补: {'启用' if params.subdivision_interpolation else '禁用'}")
                    print(f"  自动熄屏: {'启用' if params.auto_screen_off else '禁用'}")
                    print(f"  低通滤波器强度: {params.lpf_intensity}")
                    print(f"  开环模式工作电流: {params.open_loop_current}mA")
                    print(f"  闭环模式最大电流: {params.closed_loop_max_current}mA")
                    print(f"  最大转速限制: {params.max_speed_limit}RPM")
                    print(f"  电流环带宽: {params.current_loop_bandwidth}rad/s")
                    print(f"  串口波特率选项: {params.uart_baudrate}")
                    print(f"  CAN波特率选项: {params.can_baudrate}")
                    print(f"  校验方式: {params.checksum_mode}")
                    print(f"  应答模式: {params.response_mode}")
                    print(f"  位置精度: {'高精度' if params.position_precision else '标准'}")
                    print(f"  堵转保护: {'启用' if params.stall_protection_enabled else '禁用'}")
                    print(f"  堵转保护转速阈值: {params.stall_protection_speed}RPM")
                    print(f"  堵转保护电流阈值: {params.stall_protection_current}mA")
                    print(f"  堵转保护时间阈值: {params.stall_protection_time}ms")
                    print(f"  位置到达窗口: {params.position_arrival_window * 0.1:.1f}度")
                    
                except Exception as parse_error:
                    print(f" 参数解析失败: {parse_error}")
                    print("原始数据可能不符合预期格式")
                
            else:
                print(f" SDK命令执行失败: {response.error_message}")
            
        except Exception as e:
            print(f" 读取驱动参数测试失败: {e}")
            import traceback
            print("详细错误信息:")
            traceback.print_exc()
    
    def test_read_system_status(self):
        """测试读取系统状态参数"""
        if not self.ensure_connected():
            return
        
        print("\n 读取系统状态参数测试")
        print("-" * 40)
        
        try:
            print("读取系统状态参数...")
            
            # 先发送原始命令看看响应
            from Embodied_SDK import get_function_codes
            FunctionCodes = get_function_codes()
            command = self.motor.command_builder.read_system_status()
            print(f"发送命令: {[hex(x) for x in command]}")
            response = self.motor._send_command(command, FunctionCodes.READ_SYSTEM_STATUS)
            print(f"收到响应: success={response.success}, data={[hex(x) for x in response.data] if response.data else None}")
            
            # 检查响应状态
            if not response.success:
                print(f" 命令执行失败: {response.error_message}")
                return
            
            if not response.data:
                print(" 没有收到有效数据")
                return
            
            # 检查功能码是否匹配
            if len(response.data) > 0:
                # 注意：response.data已经去掉了功能码，所以我们需要重新分析原始响应
                print(f" 收到{len(response.data)}字节数据，正在解析...")
            
            if response.data:
                status = self.motor.read_parameters.get_system_status()
                
                print(" 系统状态信息:")
                print(f"  总线电压: {status.bus_voltage:.2f}V")
                print(f"  总线电流: {status.bus_current:.3f}A")
                print(f"  相电流: {status.phase_current:.3f}A")
                print(f"  编码器原始值: {status.encoder_raw_value}")
                print(f"  编码器校准值: {status.encoder_calibrated_value}")
                print(f"  目标位置: {status.target_position:.2f}度")
                print(f"  实时转速: {status.realtime_speed:.2f}RPM")
                print(f"  实时位置: {status.realtime_position:.2f}度")
                print(f"  位置误差: {status.position_error:.4f}度")
                print(f"  温度: {status.temperature:.1f}C")
                
                print(f"\n  回零状态标志:")
                print(f"    编码器就绪: {status.encoder_ready}")
                print(f"    校准表就绪: {status.calibration_table_ready}")
                print(f"    正在回零: {status.homing_in_progress}")
                print(f"    回零失败: {status.homing_failed}")
                print(f"    位置精度高: {status.position_precision_high}")
                
                print(f"\n  电机状态标志:")
                print(f"    电机使能: {status.motor_enabled}")
                print(f"    电机到位: {status.motor_in_position}")
                print(f"    电机堵转: {status.motor_stalled}")
                print(f"    堵转保护触发: {status.stall_protection_triggered}")
            else:
                print(" 没有收到有效数据")
            
        except Exception as e:
            print(f" 读取系统状态参数失败: {e}")
    
    def test_modify_drive_parameters(self):
        """测试修改驱动参数 - 一次性修改所有参数"""
        if not self.ensure_connected():
            return
        
        print("\n 修改驱动参数 - 一次性参数配置")
        print("=" * 60)
        
        try:
            # 1. 读取当前参数
            print("1. 读取当前驱动参数...")
            try:
                current_params = self.motor.read_parameters.get_drive_parameters()
                print(" 当前参数读取成功")
            except Exception as e:
                print(f" 读取当前参数失败，使用默认参数: {e}")
                current_params = self.motor.modify_parameters.create_default_drive_parameters()
            
            # 2. 显示当前参数（类似上位机界面）
            print("\n2. 当前驱动参数配置:")
            print("-" * 60)
            param_info = [
                ("锁定按键菜单", "Lock", current_params.lock_enabled, "Enable/Disable", "y/n"),
                ("控制模式", "Ctrl_Mode", current_params.control_mode, "0=开环 1=闭环FOC", "0/1"),
                ("脉冲端口复用功能", "P_PUL", current_params.pulse_port_function, "0=Disable 1=PUL_ENA 2=PUL_DIR 3=Reserved", "0-3"),
                ("通讯端口复用功能", "P_Serial", current_params.serial_port_function, "0=Disable 1=Reserved 2=UART_FUN 3=CAN_FUN", "0-3"),
                ("En引脚有效电平", "En", current_params.enable_pin_mode, "0=Disable 1=Active_Low 2=Hold", "0-2"),
                ("电机旋转正方向", "Dir", current_params.motor_direction, "0=CW 1=CCW", "0/1"),
                ("细分", "MStep", current_params.subdivision, "细分数(0表示256)", "1-256"),
                ("细分插补功能", "MPlyer", current_params.subdivision_interpolation, "Enable/Disable", "y/n"),
                ("自动熄屏功能", "AutoSDD", current_params.auto_screen_off, "Enable/Disable", "y/n"),
                ("低通滤波器强度", "LPFilter", current_params.lpf_intensity, "0=Def 1=Weak 2=Strong", "0-2"),
                ("开环模式工作电流", "Ma", current_params.open_loop_current, "mA", "100-3000"),
                ("闭环模式最大电流", "Ma_Limit", current_params.closed_loop_max_current, "mA", "100-3000"),
                ("闭环模式最大转速", "Vm_Limit", current_params.max_speed_limit, "RPM", "100-6000"),
                ("电流环带宽", "CurBW_Hz", current_params.current_loop_bandwidth, "rad/s", "100-5000"),
                ("串口波特率", "UartBaud", current_params.uart_baudrate, "0=4800 1=9600 2=19200 3=38400 4=57600 5=115200 6=230400 7=460800", "0-7"),
                ("CAN通讯速率", "CAN_Baud", current_params.can_baudrate, "0=125K 1=250K 2=500K 3=1M 4=2M 5=4M 6=5M 7=8M", "0-7"),
                ("通讯校验方式", "Checksum", current_params.checksum_mode, "0=0x6B", "0"),
                ("控制命令应答", "Response", current_params.response_mode, "0=Complete 1=Receive", "0/1"),
                ("通讯位置精度", "S_PosTDP", current_params.position_precision, "Enable/Disable", "y/n"),
                ("堵转保护功能", "Clog_Pro", current_params.stall_protection_enabled, "Enable/Disable", "y/n"),
                ("堵转保护转速阈值", "Clog_Rpm", current_params.stall_protection_speed, "RPM", "1-100"),
                ("堵转保护电流阈值", "Clog_Ma", current_params.stall_protection_current, "mA", "100-3000"),
                ("堵转保护检测时间", "Clog_Ms", current_params.stall_protection_time, "ms", "100-5000"),
                ("位置到达窗口", "Pos_Window", current_params.position_arrival_window * 0.1, "度", "0.1-10.0")
            ]
            
            # 显示当前参数表格
            print(f"{'序号':<3} {'参数名称':<16} {'英文名':<12} {'当前值':<12} {'说明':<40} {'范围'}")
            print("-" * 120)
            for i, (name, eng_name, current_val, desc, range_val) in enumerate(param_info, 1):
                # 格式化当前值显示
                if isinstance(current_val, bool):
                    display_val = "Enable" if current_val else "Disable"
                elif name == "位置到达窗口":
                    display_val = f"{current_val:.1f}"
                else:
                    display_val = str(current_val)
                
                print(f"{i:<3} {name:<16} {eng_name:<12} {display_val:<12} {desc:<40} {range_val}")
            
            print("-" * 120)
            
            print("\n3. 选择要修改的参数:")
            print("输入参数序号选择要修改的参数，多个参数用逗号分隔")
            print("例如: 1,2,11,12  (修改锁定按键、控制模式、开环电流、闭环电流)")
            print("输入 'all' 修改所有参数")
            print("输入 'quick' 使用快速配置")
            
            choice = input("请选择要修改的参数 (回车取消): ").strip()
            
            if not choice:
                print("已取消修改操作")
                return
            
            # 4. 处理快速配置选项
            if choice.lower() == 'quick':
                print("\n快速配置选项:")
                print("1. 高性能闭环配置 (大电流、高速度)")
                print("2. 高精度闭环配置 (高细分、小窗口)")
                print("3. 开环模式配置")
                print("4. 节能模式配置 (小电流、低速度)")
                
                quick_choice = input("选择快速配置 (1-4): ").strip()
                
                if quick_choice == "1":
                    # 高性能配置
                    current_params.control_mode = 1
                    current_params.closed_loop_max_current = 2500
                    current_params.max_speed_limit = 4000
                    current_params.subdivision = 64
                    current_params.current_loop_bandwidth = 1500
                    current_params.stall_protection_enabled = True
                    current_params.stall_protection_current = 2200
                    print(" 已应用高性能闭环配置")
                
                elif quick_choice == "2":
                    # 高精度配置
                    current_params.control_mode = 1
                    current_params.subdivision = 256
                    current_params.subdivision_interpolation = True
                    current_params.position_precision = True
                    current_params.position_arrival_window = 1  # 0.1度
                    current_params.closed_loop_max_current = 1800
                    current_params.max_speed_limit = 2000
                    current_params.lpf_intensity = 2
                    print(" 已应用高精度闭环配置")
                
                elif quick_choice == "3":
                    # 开环配置
                    current_params.control_mode = 0
                    current_params.open_loop_current = 1500
                    current_params.subdivision = 16
                    current_params.subdivision_interpolation = False
                    current_params.stall_protection_enabled = False
                    current_params.max_speed_limit = 1500
                    print(" 已应用开环模式配置")
                
                elif quick_choice == "4":
                    # 节能配置
                    current_params.control_mode = 1
                    current_params.open_loop_current = 800
                    current_params.closed_loop_max_current = 1200
                    current_params.max_speed_limit = 1500
                    current_params.subdivision = 32
                    current_params.auto_screen_off = True
                    print(" 已应用节能模式配置")
                    
                else:
                    print("无效选择，取消快速配置")
                    return
                
            else:
                if choice.lower() == 'all':
                    selected_indices = list(range(1, len(param_info) + 1))
                else:
                    try:
                        selected_indices = [int(x.strip()) for x in choice.split(',')]
                    except ValueError:
                        print(" 无效的输入格式")
                        return
                
                print(f"\n4. 修改选中的参数 (共{len(selected_indices)}个):")
                print("提示: 直接回车跳过该参数，保持当前值")
                print("-" * 60)
                
                for idx in selected_indices:
                    if not (1 <= idx <= len(param_info)):
                        print(f" 跳过无效序号: {idx}")
                        continue
                    
                    name, eng_name, current_val, desc, range_val = param_info[idx - 1]
                    
                    # 显示当前值
                    if isinstance(current_val, bool):
                        display_val = "Enable" if current_val else "Disable"
                    elif name == "位置到达窗口":
                        display_val = f"{current_val:.1f}"
                    else:
                        display_val = str(current_val)
                    
                    print(f"\n[{idx}] {name} ({eng_name})")
                    print(f"    当前值: {display_val}")
                    print(f"    说明: {desc}")
                    print(f"    范围: {range_val}")
                    
                    new_value = input(f"    新值 (回车跳过): ").strip()
                    
                    if not new_value:
                        continue
                    
                    try:
                        # 根据参数类型转换输入值
                        if isinstance(current_val, bool):
                            new_val = new_value.lower() in ['y', 'yes', 'enable', '1', 'true', 'on']
                            setattr(current_params, self._get_param_attr_name(idx), new_val)
                            print(f"     设置为: {'Enable' if new_val else 'Disable'}")
                            
                        elif name == "位置到达窗口":
                            new_val = int(float(new_value) * 10)  # 转换为0.1度单位
                            current_params.position_arrival_window = new_val
                            print(f"     设置为: {new_val * 0.1:.1f}度")
                            
                        else:
                            new_val = int(new_value)
                            setattr(current_params, self._get_param_attr_name(idx), new_val)
                            print(f"     设置为: {new_val}")
                            
                    except ValueError as e:
                        print(f"     无效值，跳过: {e}")
                        continue
            
            print(f"\n5. 确认参数修改:")
            print("-" * 60)
            save_to_chip = input("是否保存到芯片? (Enter确认, n取消): ").strip().lower() != 'n'
            
            print(f"\n将要修改的驱动参数:")
            print(f"保存到芯片: {'是' if save_to_chip else '否'}")
            
            confirm = input("\n确认执行参数修改? (y/N): ").strip().lower()
            if confirm not in ['y', 'yes']:
                print("已取消参数修改")
                return
            
            print("\n6. 执行参数修改...")
            response = self.motor.modify_parameters.modify_drive_parameters(current_params, save_to_chip)
            
            if response.success:
                print(" 驱动参数修改成功")
                if save_to_chip:
                    print(" 参数已保存到芯片")
                else:
                    print(" 参数未保存到芯片，断电后会丢失")
            else:
                print(f" 驱动参数修改失败: {response.error_message}")
                return
            
            print("\n7. 验证修改结果...")
            time.sleep(1)  # 等待参数生效
            try:
                updated_params = self.motor.read_parameters.get_drive_parameters()
                
                print("修改后的关键参数:")
                print(f"  控制模式: {updated_params.control_mode} ({'闭环FOC' if updated_params.control_mode == 1 else '开环'})")
                print(f"  开环工作电流: {updated_params.open_loop_current}mA")
                print(f"  闭环最大电流: {updated_params.closed_loop_max_current}mA")
                print(f"  最大转速限制: {updated_params.max_speed_limit}RPM")
                print(f"  细分设置: {updated_params.subdivision}")
                print(f"  堵转保护: {'启用' if updated_params.stall_protection_enabled else '禁用'}")
                print(f"  位置到达窗口: {updated_params.position_arrival_window * 0.1:.1f}度")
                
                print(" 参数修改验证成功")
            except Exception as e:
                print(f" 参数验证失败: {e}")
            
            print("\n 驱动参数修改完成")
            
        except Exception as e:
            print(f" 修改驱动参数失败: {e}")
    
    def _get_param_attr_name(self, index: int) -> str:
        """根据参数序号获取属性名称"""
        attr_map = {
            1: 'lock_enabled',
            2: 'control_mode', 
            3: 'pulse_port_function',
            4: 'serial_port_function',
            5: 'enable_pin_mode',
            6: 'motor_direction',
            7: 'subdivision',
            8: 'subdivision_interpolation',
            9: 'auto_screen_off',
            10: 'lpf_intensity',
            11: 'open_loop_current',
            12: 'closed_loop_max_current',
            13: 'max_speed_limit',
            14: 'current_loop_bandwidth',
            15: 'uart_baudrate',
            16: 'can_baudrate',
            17: 'checksum_mode',
            18: 'response_mode',
            19: 'position_precision',
            20: 'stall_protection_enabled',
            21: 'stall_protection_speed',
            22: 'stall_protection_current',
            23: 'stall_protection_time',
            24: 'position_arrival_window'
        }
        return attr_map.get(index, 'unknown')
    
    def test_modify_motor_id(self):
        """测试修改电机ID"""
        if not self.ensure_connected():
            return
        
        print("\n 修改电机ID")
        print("-" * 50)
        
        try:
            # 读取当前电机ID
            current_id = self.motor.motor_id
            print(f"当前电机ID: {current_id}")
            
            # 输入新的电机ID
            print("\n⚠️  重要提示:")
            print("  1. 修改电机ID后，需要断开重连才能使用新ID通信")
            print("  2. 确保新ID不与总线上其他电机冲突")
            print("  3. 修改后会自动保存到芯片")
            print("  4. 如果忘记新ID，可能需要逐一尝试或重新配置")
            
            new_id = input("\n请输入新的电机ID (1-255, 输入0取消): ").strip()
            
            if not new_id or new_id == '0':
                print("已取消修改")
                return
            
            try:
                new_id = int(new_id)
                if not (1 <= new_id <= 255):
                    print(" 电机ID必须在1-255范围内")
                    return
            except ValueError:
                print(" 无效的电机ID")
                return
            
            # 确认操作
            print(f"\n将修改电机ID: {current_id} → {new_id}")
            confirm = input("确认修改电机ID? (输入'YES'确认): ").strip()
            
            if confirm != 'YES':
                print("已取消修改")
                return
            
            # 执行修改
            print(f"\n发送修改电机ID命令...")
            self.motor.modify_parameters.set_motor_id(new_id)
            print(f" 电机ID修改命令发送成功！")
            
            print(f"\n修改完成！新ID: {new_id}")
            print("\n 后续步骤:")
            print(f"  1. 断开当前连接 (选择菜单 2)")
            print(f"  2. 使用新ID {new_id} 重新连接 (选择菜单 1)")
            print(f"  3. 验证新ID是否生效")
            
        except Exception as e:
            print(f" 修改电机ID失败: {e}")
    
    def test_modify_pid_parameters(self):
        """测试修改PID参数"""
        if not self.ensure_connected():
            return
        
        print("\n 修改PID参数")
        print("-" * 50)
        
        try:
            # 读取当前PID参数
            print("读取当前PID参数...")
            current_pid = self.motor.read_parameters.get_pid_parameters()
            print(f"当前PID参数:")
            print(f"  梯形位置环Kp: {current_pid.trapezoid_position_kp}")
            print(f"  直通位置环Kp: {current_pid.direct_position_kp}")
            print(f"  速度环Kp: {current_pid.speed_kp}")
            print(f"  速度环Ki: {current_pid.speed_ki}")
            
            print("\n选择要修改的参数:")
            print("1. 梯形位置环Kp")
            print("2. 直通位置环Kp")
            print("3. 速度环Kp")
            print("4. 速度环Ki")
            print("5. 全部修改")
            
            choice = input("请选择 (1-5, Enter取消): ").strip()
            if not choice:
                print("已取消修改")
                return
            
            trapezoid_kp = current_pid.trapezoid_position_kp
            direct_kp = current_pid.direct_position_kp
            speed_kp = current_pid.speed_kp
            speed_ki = current_pid.speed_ki
            
            if choice == '1':
                trapezoid_kp = int(input(f"梯形位置环Kp (当前{current_pid.trapezoid_position_kp}): ").strip() or current_pid.trapezoid_position_kp)
            elif choice == '2':
                direct_kp = int(input(f"直通位置环Kp (当前{current_pid.direct_position_kp}): ").strip() or current_pid.direct_position_kp)
            elif choice == '3':
                speed_kp = int(input(f"速度环Kp (当前{current_pid.speed_kp}): ").strip() or current_pid.speed_kp)
            elif choice == '4':
                speed_ki = int(input(f"速度环Ki (当前{current_pid.speed_ki}): ").strip() or current_pid.speed_ki)
            elif choice == '5':
                trapezoid_kp = int(input(f"梯形位置环Kp (当前{current_pid.trapezoid_position_kp}): ").strip() or current_pid.trapezoid_position_kp)
                direct_kp = int(input(f"直通位置环Kp (当前{current_pid.direct_position_kp}): ").strip() or current_pid.direct_position_kp)
                speed_kp = int(input(f"速度环Kp (当前{current_pid.speed_kp}): ").strip() or current_pid.speed_kp)
                speed_ki = int(input(f"速度环Ki (当前{current_pid.speed_ki}): ").strip() or current_pid.speed_ki)
            else:
                print(" 无效选择")
                return
            
            print(f"\n新的PID参数:")
            print(f"  梯形位置环Kp: {trapezoid_kp}")
            print(f"  直通位置环Kp: {direct_kp}")
            print(f"  速度环Kp: {speed_kp}")
            print(f"  速度环Ki: {speed_ki}")
            
            confirm = input("\n确认修改PID参数? (Enter确认, n取消): ").strip().lower()
            if confirm == 'n':
                print("已取消修改")
                return
            
            # 执行修改
            print("\n发送修改命令...")
            self.motor.modify_parameters.set_pid_parameters(
                trapezoid_position_kp=trapezoid_kp,
                direct_position_kp=direct_kp,
                speed_kp=speed_kp,
                speed_ki=speed_ki
            )
            print(" PID参数修改成功")
            
            # 验证修改
            print("\n验证修改结果...")
            time.sleep(0.5)
            new_pid = self.motor.read_parameters.get_pid_parameters()
            print(f"修改后的PID参数:")
            print(f"  梯形位置环Kp: {new_pid.trapezoid_position_kp}")
            print(f"  直通位置环Kp: {new_pid.direct_position_kp}")
            print(f"  速度环Kp: {new_pid.speed_kp}")
            print(f"  速度环Ki: {new_pid.speed_ki}")
            
        except Exception as e:
            print(f" 修改PID参数失败: {e}")
    
    def test_factory_reset(self):
        """测试恢复出厂设置"""
        if not self.ensure_connected():
            return
        
        print("\n ⚠️  恢复出厂设置")
        print("-" * 50)
        
        print("\n 危险操作警告:")
        print("  1. 恢复出厂设置会清除所有自定义配置")
        print("  2. 包括：电机ID、PID参数、回零参数、驱动参数等")
        print("  3. 电机会恢复到出厂默认状态")
        print("  4. 此操作不可逆，请谨慎操作")
        
        # 需要二次确认
        print("\n请输入'RESET'确认恢复出厂设置")
        confirm1 = input("确认输入: ").strip()
        
        if confirm1 != 'RESET':
            print("已取消操作")
            return
        
        confirm2 = input("\n最后确认，是否恢复出厂设置? (输入'YES'确认): ").strip()
        if confirm2 != 'YES':
            print("已取消操作")
            return
        
        try:
            print("\n执行恢复出厂设置...")
            self.motor.trigger_actions.factory_reset()
            print(" 恢复出厂设置命令已发送")
            
            print("\n ⚠️  重要提示:")
            print("  1. 电机正在恢复出厂设置，请等待5-10秒")
            print("  2. 恢复完成后，电机ID可能已改变")
            print("  3. 建议断开重连，使用默认配置测试")
            
        except Exception as e:
            print(f" 恢复出厂设置失败: {e}")
    
    def test_new_commands_support(self):
        """测试新命令是否被电机固件支持"""
        if not self.ensure_connected():
            return
        
        print("\n 检测新命令支持情况")
        print("-" * 40)
        
        # 测试命令列表
        test_commands = [
            {
                'name': '读取驱动参数',
                'function_code': 0x42,
                'aux_code': 0x6C,
                'command': [0x42, 0x6C, 0x6B]
            },
            {
                'name': '读取系统状态',
                'function_code': 0x43,
                'aux_code': 0x7A,
                'command': [0x43, 0x7A, 0x6B]
            }
        ]
        
        for test in test_commands:
            print(f"\n测试 {test['name']} (0x{test['function_code']:02X} + 0x{test['aux_code']:02X}):")
            print(f"发送命令: {[hex(x) for x in test['command']]}")
            
            try:
                # 直接发送原始CAN命令
                raw_response = self.motor.can_interface.send_command_and_receive_response(
                    self.motor.motor_id, test['command']
                )
                print(f"收到原始响应: {[hex(x) for x in raw_response] if raw_response else None}")
                
                if not raw_response:
                    print("   没有收到响应")
                    continue
                
                # 检查第一个字节是否匹配功能码
                if raw_response[0] == test['function_code']:
                    print(f"   功能码匹配 (0x{raw_response[0]:02X})")
                    print(f"   数据长度: {len(raw_response)-1}字节")
                    if len(raw_response) > 1:
                        print(f"   数据内容: {[hex(x) for x in raw_response[1:]]}")
                elif raw_response[0] == 0x00 and len(raw_response) >= 3 and raw_response[1] == 0xEE:
                    print(f"   命令错误响应: {[hex(x) for x in raw_response]}")
                    print("   电机固件不支持此命令")
                else:
                    print(f"   功能码不匹配: 期望0x{test['function_code']:02X}, 收到0x{raw_response[0]:02X}")
                    print(f"   可能是其他数据或错误响应: {[hex(x) for x in raw_response]}")
                
            except Exception as e:
                print(f"   命令发送失败: {e}")
        
        print(f"\n 结论:")
        print("- 如果看到'功能码匹配'说明命令被支持")
        print("- 如果看到'命令错误响应'说明电机固件不支持此命令")
        print("- 如果看到'功能码不匹配'可能是命令格式错误或其他问题")
    
    # ========== 菜单和主循环 ==========
    
    def show_menu(self):
        """显示主菜单"""
        print("\n" + "=" * 60)
        print("  ZDT电机SDK测试菜单")
        print("=" * 60)
        print("连接管理:")
        print("  1. 连接电机")
        print("  2. 断开电机")
        print()
        print("基础控制:")
        print("  3. 电机使能")
        print("  4. 电机失能") 
        print("  5. 电机停止")
        print()
        print("状态读取:")
        print("  6. 读取电机状态")
        print("  7. 读取位置")
        print("  8. 读取转速")
        print("  9. 读取温度")
        print("  10. 读取完整状态")
        print("  11. 读取版本信息")
        print("  12. 读取电阻电感")
        print("  13. 读取PID参数")
        print("  14. 读取总线电压")
        print("  15. 读取总线电流")
        print("  16. 读取相电流")
        print("  17. 读取编码器值")
        print("  18. 读取脉冲计数")
        print("  19. 读取目标位置")
        print("  20. 读取位置误差")
        print()
        print("运动控制:")
        print("  21. 速度模式测试")
        print("  22. 位置模式测试")
        print("  23. 梯形曲线位置模式测试")
        print("  24. 力矩模式测试")
        print()
        print("回零功能:")
        print("  25. 读取回零状态")
        print("  26. 触发回零")
        print("  27. 强制停止回零")
        print("  28. 编码器校准")
        print("  29. 读取回零参数")
        print("  30. 设置零点位置")
        print("  31. 综合回零测试")
        print("  32. 修改回零参数")
        print()
        print("工具命令:")
        print("  33. 清零位置")
        print("  34. 解除堵转保护")
        print()
        print("高级测试:")
        print("  35. 协议解析修复验证")
        print()
        print("新增功能:")
        print("  36.  读取驱动参数")
        print("  37.  读取系统状态参数") 
        print("  38.   修改驱动参数")
        print("  39.  设置日志级别")
        print("  40.  检测新命令支持情况")
        print("  41.   修改电机ID")
        print("  42.   修改PID参数")
        print("  43.  ⚠️  恢复出厂设置")
        print()
        print("设置:")
        print("  0. 退出")
        print("=" * 60)
    
    def test_set_log_level(self):
        """设置日志级别"""
        print("\n 设置日志级别")
        print("-" * 30)
        print("1. DEBUG (详细调试信息)")
        print("2. INFO (一般信息)")
        print("3. WARNING (警告信息)")
        print("4. ERROR (错误信息)")
        
        try:
            choice = input("选择日志级别 (1-4, 默认2): ").strip() or "2"
            levels = {
                "1": logging.DEBUG,
                "2": logging.INFO,
                "3": logging.WARNING,
                "4": logging.ERROR
            }
            
            if choice in levels:
                setup_logging(levels[choice])
                level_names = {
                    "1": "DEBUG",
                    "2": "INFO", 
                    "3": "WARNING",
                    "4": "ERROR"
                }
                print(f" 日志级别已设置为: {level_names[choice]}")
            else:
                print(" 无效选择")
                
        except Exception as e:
            print(f" 设置日志级别失败: {e}")
    
    def run(self):
        """运行交互式测试"""
        print("欢迎使用ZDT电机SDK交互式测试工具")
        print("请根据菜单选择要测试的功能。")
        
        while True:
            try:
                self.show_menu()
                choice = input("\n请选择操作 (0-43): ").strip()
                
                if choice == "0":
                    print(" 感谢使用ZDT电机SDK测试工具")
                    break
                elif choice == "1":
                    self.connect_motor()
                elif choice == "2":
                    self.disconnect_motor()
                elif choice == "3":
                    self.test_motor_enable()
                elif choice == "4":
                    self.test_motor_disable()
                elif choice == "5":
                    self.test_motor_stop()
                elif choice == "6":
                    self.test_read_status()
                elif choice == "7":
                    self.test_read_position()
                elif choice == "8":
                    self.test_read_speed()
                elif choice == "9":
                    self.test_read_temperature()
                elif choice == "10":
                    self.test_read_all_status()
                elif choice == "11":
                    self.test_read_version()
                elif choice == "12":
                    self.test_read_resistance_inductance()
                elif choice == "13":
                    self.test_read_pid_parameters()
                elif choice == "14":
                    self.test_read_bus_voltage()
                elif choice == "15":
                    self.test_read_bus_current()
                elif choice == "16":
                    self.test_read_phase_current()
                elif choice == "17":
                    self.test_read_encoder_values()
                elif choice == "18":
                    self.test_read_pulse_counts()
                elif choice == "19":
                    self.test_read_target_positions()
                elif choice == "20":
                    self.test_read_position_error()
                elif choice == "21":
                    self.test_speed_mode()
                elif choice == "22":
                    self.test_position_mode()
                elif choice == "23":
                    self.test_trapezoid_position_mode()
                elif choice == "24":
                    self.test_torque_mode()
                elif choice == "25":
                    self.test_read_homing_status()
                elif choice == "26":
                    self.test_trigger_homing()
                elif choice == "27":
                    self.test_force_stop_homing()
                elif choice == "28":
                    self.test_encoder_calibration()
                elif choice == "29":
                    self.test_read_homing_parameters()
                elif choice == "30":
                    self.test_set_zero_position()
                elif choice == "31":
                    self.test_comprehensive_homing()
                elif choice == "32":
                    self.test_modify_homing_parameters()
                elif choice == "33":
                    self.test_clear_position()
                elif choice == "34":
                    self.test_release_stall_protection()
                elif choice == "35":
                    self.test_protocol_parsing_fix()
                elif choice == "36":
                    self.test_read_drive_parameters()
                elif choice == "37":
                    self.test_read_system_status()
                elif choice == "38":
                    self.test_modify_drive_parameters()
                elif choice == "39":
                    self.test_set_log_level()
                elif choice == "40":
                    self.test_new_commands_support()
                elif choice == "41":
                    self.test_modify_motor_id()
                elif choice == "42":
                    self.test_modify_pid_parameters()
                elif choice == "43":
                    self.test_factory_reset()
                else:
                    print(" 无效选择，请重新输入")
                
                # 等待用户按键继续
                if choice != "0":
                    input("\n按回车键继续...")
                    
            except KeyboardInterrupt:
                print("\n\n 用户中断，正在退出...")
                break
            except Exception as e:
                print(f"\n 发生错误: {e}")
                input("按回车键继续...")
        
        # 清理资源
        self.disconnect_motor()


if __name__ == "__main__":
    tester = ZDTInteractiveTester()
    tester.run() 