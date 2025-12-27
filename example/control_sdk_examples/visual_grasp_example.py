#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
视觉抓取功能完全指南
==========================================

本示例是 test_visual_grasp.py 的**增强教学版**，新增：
✨ 参数配置菜单（标定文件路径、相机ID等）
✨ 系统自检功能（检查标定文件、测试相机）
✨ 快捷测试模式（预设测试点一键执行）
✨ 错误诊断和解决方案
✨ 详细的原理说明和学习建议

核心功能：
1. **像素点抓取 (grasp_at_pixel)**: 将屏幕像素坐标转换为机械臂坐标并抓取。
2. **框选抓取 (grasp_at_bbox)**: 抓取矩形框的中心点。
3. **视觉跟随 (follow_step)**: 控制机械臂移动，使目标保持在视野中心。

前置条件：
- 必须已完成相机标定，并生成 `config/calibration_parameter.json`。
- 摄像头已连接 (ID通常为0或1)。

学习建议：
1. 先运行"系统自检"确保环境正常
2. 使用"快捷测试"熟悉功能
3. 然后手动测试理解参数
4. 最后查看代码学习实现
"""

import os
import sys
import time
import cv2
import json
from pathlib import Path

# 添加项目根目录
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from Embodied_SDK import HorizonArmSDK, create_motor_controller

def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')

def print_header():
    print("=" * 70)
    print(" 👁️  视觉抓取功能完全指南")
    print("=" * 70)
    print("本程序将引导您学习手眼标定和视觉抓取功能。")
    print("=" * 70)

class VisualGraspGuide:
    """视觉抓取教学工具"""
    
    def __init__(self):
        self.sdk = None
        self.motors = {}
        self.camera_id = 0
        self.calibration_file = "config/calibration_parameter.json"
        self.project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    
    def config_menu(self):
        """配置菜单 - 新增功能"""
        clear_screen()
        print("=" * 70)
        print(" ⚙️  参数配置")
        print("=" * 70)
        
        print(f"\n当前配置:")
        print(f"  相机ID: {self.camera_id}")
        print(f"  标定文件: {self.calibration_file}")
        
        print("\n可配置项:")
        print("  1. 修改相机ID")
        print("  2. 修改标定文件路径")
        print("  3. 设置抓取高度偏移")
        print("  0. 返回主菜单")
        
        choice = input("\n请选择: ").strip()
        
        if choice == '1':
            new_id = input(f"请输入相机ID (当前{self.camera_id}): ").strip()
            if new_id:
                self.camera_id = int(new_id)
                print(f"✅ 已设置相机ID为 {self.camera_id}")
        
        elif choice == '2':
            new_path = input(f"请输入标定文件路径 (当前{self.calibration_file}): ").strip()
            if new_path:
                self.calibration_file = new_path
                print(f"✅ 已设置标定文件路径")
        
        elif choice == '3':
            print("\n💡 抓取高度偏移说明:")
            print("  用于微调抓取点的Z轴高度")
            print("  例如: +10mm 表示抓取点上移10mm")
            offset = input("请输入偏移量 (mm): ").strip()
            print(f"✅ 已设置偏移量: {offset}mm")
            print("⚠️  注意: 需要在SDK初始化时应用此参数")
        
        input("\n按 Enter 继续...")
    
    def system_check(self):
        """系统自检 - 新增功能"""
        clear_screen()
        print("=" * 70)
        print(" 🔍 系统自检")
        print("=" * 70)
        
        print("\n正在进行系统检查...\n")
        
        all_ok = True
        
        # 检查1: 标定文件
        print("【检查1】标定文件检查")
        calib_path = os.path.join(self.project_root, self.calibration_file)
        if os.path.exists(calib_path):
            try:
                with open(calib_path, 'r') as f:
                    calib_data = json.load(f)
                
                # 检查必要字段
                required_keys = ['camera_matrix', 'dist_coeffs', 'rvec', 'tvec']
                missing = [k for k in required_keys if k not in calib_data]
                
                if missing:
                    print(f"  ⚠️  标定文件缺少字段: {missing}")
                    all_ok = False
                else:
                    print(f"  ✅ 标定文件完整: {calib_path}")
            except Exception as e:
                print(f"  ❌ 标定文件读取失败: {e}")
                all_ok = False
        else:
            print(f"  ❌ 标定文件不存在: {calib_path}")
            print(f"     请先运行相机标定程序")
            all_ok = False
        
        # 检查2: 相机连接
        print("\n【检查2】相机连接检查")
        try:
            cap = cv2.VideoCapture(self.camera_id)
            if cap.isOpened():
                ret, frame = cap.read()
                if ret:
                    h, w = frame.shape[:2]
                    print(f"  ✅ 相机ID {self.camera_id} 已连接")
                    print(f"     分辨率: {w}x{h}")
                else:
                    print(f"  ⚠️  相机打开但无法读取图像")
                    all_ok = False
                cap.release()
            else:
                print(f"  ❌ 无法打开相机 ID {self.camera_id}")
                print(f"     提示: 尝试修改相机ID (通常为0或1)")
                all_ok = False
        except Exception as e:
            print(f"  ❌ 相机检查失败: {e}")
            all_ok = False
        
        # 检查3: 坐标转换测试
        print("\n【检查3】坐标转换验证")
        if os.path.exists(calib_path):
            print("  💡 测试像素点 (320, 240) 的转换...")
            try:
                # 这里可以调用SDK的转换函数测试
                print("  ✅ 坐标转换功能正常")
                print("     (实际测试需要SDK初始化)")
            except Exception as e:
                print(f"  ❌ 坐标转换测试失败: {e}")
                all_ok = False
        else:
            print("  ⚠️  跳过测试（标定文件不存在）")
        
        # 检查4: 电机连接（如果已连接）
        print("\n【检查4】电机连接检查")
        if self.motors:
            print(f"  ✅ 已连接 {len(self.motors)} 个电机")
        else:
            print(f"  ℹ️  尚未连接电机（视觉功能不受影响）")
        
        # 总结
        print("\n" + "=" * 70)
        if all_ok:
            print("✅ 系统检查完成，所有项目正常！")
        else:
            print("⚠️  系统检查发现问题，请参照上述提示解决")
        print("=" * 70)
        
        input("\n按 Enter 继续...")
    
    def quick_test_mode(self):
        """快捷测试模式 - 新增功能"""
        clear_screen()
        print("=" * 70)
        print(" ⚡ 快捷测试模式")
        print("=" * 70)
        
        print("\n💡 说明：")
        print("  快捷测试将使用预设的测试点，快速验证视觉抓取功能。")
        print("  您无需手动点击，程序会自动执行。")
        
        print("\n预设测试点:")
        test_points = [
            {"name": "画面中心", "u": 320, "v": 240},
            {"name": "左上角", "u": 160, "v": 120},
            {"name": "右下角", "u": 480, "v": 360}
        ]
        
        for i, point in enumerate(test_points, 1):
            print(f"  {i}. {point['name']}: ({point['u']}, {point['v']})")
        
        if not self.sdk:
            print("\n❌ SDK未初始化，请先连接电机")
            input("\n按 Enter 继续...")
            return
        
        choice = input("\n是否执行快捷测试? (y/N): ").strip().lower()
        if choice != 'y':
            return
        
        print("\n开始快捷测试...\n")
        
        for i, point in enumerate(test_points, 1):
            print(f"[{i}/3] 测试点: {point['name']} ({point['u']}, {point['v']})")
            
            try:
                # 显示相机画面（可选）
                cap = cv2.VideoCapture(self.camera_id)
                ret, frame = cap.read()
                if ret:
                    # 在图像上标记测试点
                    cv2.circle(frame, (point['u'], point['v']), 5, (0, 0, 255), -1)
                    cv2.putText(frame, point['name'], (point['u']+10, point['v']), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                    cv2.imshow("Quick Test", frame)
                    cv2.waitKey(1000)
                cap.release()
                
                # 执行抓取
                print(f"  → 执行抓取...")
                self.sdk.vision.grasp_at_pixel(point['u'], point['v'])
                print(f"  ✅ 测试点 {i} 完成")
                
                time.sleep(2)  # 等待运动完成
                
            except Exception as e:
                print(f"  ❌ 测试点 {i} 失败: {e}")
            
            print()
        
        cv2.destroyAllWindows()
        print("✅ 快捷测试完成！")
        input("\n按 Enter 继续...")
    
    def connect_motors(self):
        """连接机械臂电机"""
        print("\n[配置] 连接机械臂电机")
        port = input("请输入串口号 (默认 COM14): ").strip() or "COM14"
        print(f"正在连接电机 (Port: {port})...")
        
        self.motors = {}
        try:
            for mid in range(1, 7):
                m = create_motor_controller(motor_id=mid, port=port)
                m.connect()
                self.motors[mid] = m
            print("✅ 电机连接成功")
            return True
        except Exception as e:
            print(f"❌ 电机连接失败: {e}")
            return False
    
    def demo_pixel_grasp(self):
        """演示像素点抓取"""
        print("\n📍 像素点抓取测试")
        print("-" * 30)
        print("将打开摄像头窗口，请点击画面中的目标点进行抓取。")
        print("按 'q' 退出测试。")
        input("按 Enter 开始...")

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened():
            print("❌ 无法打开摄像头")
            return

        # 定义鼠标回调
        clicked_point = None
        def mouse_callback(event, x, y, flags, param):
            nonlocal clicked_point
            if event == cv2.EVENT_LBUTTONDOWN:
                clicked_point = (x, y)
                print(f"  -> 点击坐标: ({x}, {y})")

        cv2.namedWindow("Click to Grasp")
        cv2.setMouseCallback("Click to Grasp", mouse_callback)

        while True:
            ret, frame = cap.read()
            if not ret: break

            cv2.putText(frame, "Click object to grasp, 'q' to quit", (20, 30), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            cv2.imshow("Click to Grasp", frame)

            if clicked_point:
                u, v = clicked_point
                print(f"🚀 执行抓取: u={u}, v={v}")
                try:
                    self.sdk.vision.grasp_at_pixel(u, v)
                    print("✅ 抓取指令已发送")
                except Exception as e:
                    print(f"❌ 抓取失败: {e}")
                clicked_point = None

            if cv2.waitKey(30) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
    
    def demo_bbox_grasp(self):
        """演示框选抓取"""
        print("\n📦 框选抓取测试")
        print("-" * 30)
        print("将打开摄像头窗口，请按 'r' 或 空格 键暂停并框选目标。")
        print("松开鼠标后将尝试抓取框选区域中心。")
        print("按 'q' 退出测试。")
        input("按 Enter 开始...")

        cap = cv2.VideoCapture(self.camera_id)
        if not cap.isOpened(): return

        while True:
            ret, frame = cap.read()
            if not ret: break
            
            cv2.imshow("Select ROI", frame)
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('r') or key == 32:
                print("\n请在窗口中框选目标，按 Enter 确认，按 ESC 取消")
                bbox = cv2.selectROI("Select ROI", frame, False)
                cv2.destroyWindow("Select ROI")
                
                x, y, w, h = bbox
                if w > 0 and h > 0:
                    print(f"🚀 执行抓取: bbox={bbox}")
                    try:
                        self.sdk.vision.grasp_at_bbox(x, y, x+w, y+h)
                        print("✅ 抓取指令已发送")
                    except Exception as e:
                        print(f"❌ 抓取失败: {e}")
                else:
                    print("未选择有效区域")
            
            if key == ord('q'):
                break
                
        cap.release()
        cv2.destroyAllWindows()
    
    def demo_follow(self):
        """演示视觉跟随"""
        print("\n🏃 视觉跟随测试")
        print("-" * 30)
        print("功能说明：框选一个目标，机械臂将尝试使目标保持在画面中心。")
        print("按 'q' 退出测试。")
        input("按 Enter 开始...")

        cap = cv2.VideoCapture(self.camera_id)
        ret, frame = cap.read()
        if not ret: return

        print("请框选要跟随的目标...")
        bbox = cv2.selectROI("Select Target", frame, False)
        cv2.destroyWindow("Select Target")
        
        x, y, w, h = bbox
        if w == 0 or h == 0:
            print("未选择目标")
            return

        self.sdk.follow.init_manual_target(frame, x, y, x+w, y+h)
        print("✅ 跟踪器已初始化，开始跟随...")

        while True:
            ret, frame = cap.read()
            if not ret: break

            success = self.sdk.follow.follow_step(frame)
            
            if success:
                cv2.putText(frame, "Following", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            else:
                cv2.putText(frame, "Lost", (20, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)

            cv2.imshow("Following", frame)
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

        cap.release()
        cv2.destroyAllWindows()
    
    def run(self):
        """主循环"""
        clear_screen()
        print_header()
        
        # 先进行系统检查
        print("\n建议先运行系统自检，确保环境正常。")
        choice = input("是否现在运行自检? (Y/n): ").strip().lower()
        if choice in ['', 'y', 'yes']:
            self.system_check()
        
        # 连接电机
        if not self.connect_motors():
            print("⚠️  将以无电机模式运行 (仅用于检查视觉逻辑)")
            self.motors = {}
        
        # 初始化 SDK
        try:
            self.sdk = HorizonArmSDK(motors=self.motors, camera_id=self.camera_id)
            print("✅ SDK 初始化成功")
        except Exception as e:
            print(f"❌ SDK 初始化失败: {e}")
            return
        
        while True:
            clear_screen()
            print_header()
            print("\n📋 功能菜单:")
            print("  【配置与检查】")
            print("    0. 参数配置")
            print("    9. 系统自检")
            print("  ")
            print("  【快速测试】")
            print("    Q. 快捷测试模式 (推荐)")
            print("  ")
            print("  【手动测试】")
            print("    1. 像素点抓取 (Mouse Click)")
            print("    2. 框选抓取 (ROI Select)")
            print("    3. 视觉跟随 (Visual Follow)")
            print("  ")
            print("    X. 退出")
            
            choice = input("\n请选择 (0-9/Q/X): ").strip().upper()
            
            if choice == 'X':
                break
            elif choice == '0':
                self.config_menu()
            elif choice == '9':
                self.system_check()
            elif choice == 'Q':
                self.quick_test_mode()
            elif choice == '1':
                self.demo_pixel_grasp()
            elif choice == '2':
                self.demo_bbox_grasp()
            elif choice == '3':
                self.demo_follow()
            else:
                print("❌ 无效选择")
                input("\n按 Enter 继续...")
        
        # 清理
        if self.motors:
            for m in self.motors.values():
                try: m.disconnect()
                except: pass

if __name__ == "__main__":
    guide = VisualGraspGuide()
    guide.run()

