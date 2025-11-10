# -*- coding: utf-8 -*-
"""
手眼标定界面组件
"""

import sys
import os
import json
import yaml
import numpy as np
import cv2
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, 
                             QLabel, QPushButton, QTableWidget, QTableWidgetItem,
                             QProgressBar, QTextEdit, QGroupBox, QSpinBox, 
                             QDoubleSpinBox, QComboBox, QCheckBox, QMessageBox,
                             QFileDialog, QTabWidget, QScrollArea, QFrame,
                             QSplitter, QLineEdit, QHeaderView, QDialog)
from PyQt5.QtCore import Qt, QThread, pyqtSignal, QTimer, pyqtSlot
from PyQt5.QtGui import QFont, QPixmap, QImage, QPainter, QPen, QBrush

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

from core.arm_core.Hand_Eye_Calibration import EyeInHand
from Main_UI.utils.kinematics_factory import create_configured_kinematics

# 添加电机配置管理器导入
from .motor_config_manager import motor_config_manager


class CameraWorker(QThread):
    """摄像头工作线程，用于捕获和处理摄像头画面"""
    
    frame_ready = pyqtSignal(np.ndarray)  # 摄像头画面信号
    error = pyqtSignal(str)  # 错误信号
    
    def __init__(self, camera_index=0, frame_width=1280, frame_height=480):
        super().__init__()
        self.camera_index = camera_index
        self.frame_width = frame_width
        self.frame_height = frame_height
        self._is_running = False
        self.cap = None
        self.current_frame = None  # 存储当前帧
    
    def start_camera(self):
        """启动摄像头"""
        self._is_running = True
        self.start()
    
    def stop_camera(self):
        """停止摄像头"""
        self._is_running = False
        if self.isRunning():
            self.quit()
            self.wait(3000)  # 等待最多3秒
    
    def get_current_frame(self):
        """获取当前帧"""
        return self.current_frame
    
    def run(self):
        """在后台线程中捕获摄像头画面"""
        try:
            # 初始化摄像头
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.error.emit(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置摄像头参数
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.frame_width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.frame_height)
            
            while self._is_running:
                ret, frame = self.cap.read()
                if not ret:
                    self.error.emit("无法读取摄像头画面")
                    break
                
                try:
                    # 分离左右摄像头画面（假设左右并排排列）
                    if frame.shape[1] >= 1280:  # 双目摄像头
                        frame_L = frame[:, 0:640]  # 左侧画面
                        frame_R = frame[:, 640:1280]  # 右侧画面
                        self.current_frame = frame_R.copy()  # 存储右侧画面
                        self.frame_ready.emit(frame_R)
                    else:  # 单目摄像头
                        self.current_frame = frame.copy()
                        self.frame_ready.emit(frame)
                    
                except Exception as e:
                    self.error.emit(f"处理摄像头画面时出错: {str(e)}")
                    break
                
                # 控制帧率（约30fps）
                self.msleep(33)
        
        except Exception as e:
            self.error.emit(f"摄像头线程错误: {str(e)}")
        finally:
            if self.cap is not None:
                self.cap.release()
                self.cap = None


class HandEyeCalibrationThread(QThread):
    """手眼标定数据采集线程"""
    
    progress_updated = pyqtSignal(int, int)  # 当前位置, 总数
    message_updated = pyqtSignal(str)
    image_captured = pyqtSignal(str, np.ndarray)  # 图片路径和机械臂位姿
    calibration_finished = pyqtSignal(dict)  # 标定结果
    
    def __init__(self, preset_poses, output_dir, corner_width, corner_height, square_size, motor_config_manager, parent_widget, motors):
        super().__init__()
        self.preset_poses = preset_poses
        self.output_dir = output_dir
        self.corner_width = corner_width
        self.corner_height = corner_height
        self.square_size = square_size
        self.motor_config_manager = motor_config_manager
        self.is_running = False
        # 初始化运动学计算器 - 使用配置的参数
        self.kinematics = create_configured_kinematics()
        self.parent_widget = parent_widget # 添加父窗口引用
        self.motors = motors  # 添加实际motor对象
    
    def run(self):
        """执行数据采集"""
        self.is_running = True
        self.message_updated.emit("开始手眼标定数据采集...")
        
        # 检测驱动板版本（Y板支持Y42多电机命令）
        try:
            versions = set()
            for m in (self.motors or {}).values():
                versions.add(str(getattr(m, 'drive_version', 'Y')).upper())
            is_y_board = (versions == {"Y"})
        except Exception:
            is_y_board = False
        
        # 发送初始进度
        self.progress_updated.emit(0, len(self.preset_poses))
        
        # 创建输出目录
        image_dir = os.path.join(self.output_dir, "eye_hand_calibration_image")
        os.makedirs(image_dir, exist_ok=True)
        
        poses_data = []
        
        for i, pose in enumerate(self.preset_poses):
            if not self.is_running:
                break
                
            self.message_updated.emit(f"移动到第 {i+1}/{len(self.preset_poses)} 个位置...")
            
            # 真实控制机械臂移动到目标位置
            joint_angles = pose['joint_angles']
            
            # 控制机械臂移动
            try:
                if not self.motors:
                    self.message_updated.emit(f"❌ 未连接机械臂，无法移动到位置 {i+1}")
                    continue
                
                self.message_updated.emit(f"正在移动机械臂到位置 {i+1}...")
                
                # 运动参数
                max_speed = 500      # 最大速度500 RPM
                acceleration = 200    # 开始加速度200
                deceleration = 200    # 最后加速度200
                
                success_count = 0
                if is_y_board:
                    # Y板：使用Y42多电机命令一次性下发
                    commands = []
                    for j, angle in enumerate(joint_angles):
                        motor_id = j + 1
                        if motor_id in self.motors:
                            try:
                                actual_angle = self.parent_widget.get_actual_angle(angle, motor_id)
                                motor = self.motors[motor_id]
                                func = motor.command_builder.position_mode_trapezoid(
                                    position=actual_angle,
                                    max_speed=max_speed,
                                    acceleration=acceleration,
                                    deceleration=deceleration,
                                    is_absolute=True,
                                    multi_sync=False
                                )
                                try:
                                    from Control_SDK.Control_Core import ZDTCommandBuilder
                                    single = ZDTCommandBuilder.build_single_command_bytes(motor_id, func)
                                except Exception:
                                    single = [motor_id] + func
                                commands.append(single)
                            except Exception as motor_error:
                                self.message_updated.emit(f"❌ 电机 {motor_id} 参数构建失败: {str(motor_error)}")
                                continue
                    if commands:
                        try:
                            first_motor_id = list(self.motors.keys())[0]
                            first_motor = self.motors[first_motor_id]
                            first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                            success_count = len(commands)
                            self.message_updated.emit(f"✅ 已下发Y42多电机命令至位置 {i+1}")
                        except Exception as e_y42:
                            self.message_updated.emit(f"❌ Y42多电机下发失败: {str(e_y42)}")
                            success_count = 0
                    else:
                        self.message_updated.emit(f"❌ 机械臂移动到位置 {i+1} 失败 - 无有效电机命令")
                        success_count = 0
                else:
                    # X板：逐电机multi_sync + 广播同步
                    for j, angle in enumerate(joint_angles):
                        motor_id = j + 1
                        if motor_id in self.motors:
                            try:
                                actual_angle = self.parent_widget.get_actual_angle(angle, motor_id)
                                motor = self.motors[motor_id]
                                motor.control_actions.move_to_position_trapezoid(
                                    position=actual_angle,
                                    max_speed=max_speed,
                                    acceleration=acceleration,
                                    deceleration=deceleration,
                                    is_absolute=True,
                                    multi_sync=True
                                )
                                success_count += 1
                            except Exception as motor_error:
                                self.message_updated.emit(f"❌ 电机 {motor_id} 设置失败: {str(motor_error)}")
                                continue
                 
                if success_count == 0:
                    self.message_updated.emit(f"❌ 机械臂移动到位置 {i+1} 失败 - 没有电机成功设置")
                    continue
                
                # 第二阶段（仅X板需要广播同步；Y板已一次性下发）
                if not is_y_board:
                    if self.motors:
                        try:
                            first_motor_id = list(self.motors.keys())[0]
                            first_motor = self.motors[first_motor_id]
                            broadcast_motor = first_motor.__class__(
                                motor_id=0,
                                interface_type=first_motor.interface_type,
                                shared_interface=True,
                                **first_motor.interface_kwargs
                            )
                            broadcast_motor.can_interface = first_motor.can_interface
                            broadcast_motor.control_actions.sync_motion()
                            self.message_updated.emit(f"✅ 机械臂同步移动到位置 {i+1} 成功")
                        except Exception as sync_error:
                            self.message_updated.emit(f"❌ 同步执行失败: {str(sync_error)}")
                            continue
                    else:
                        self.message_updated.emit(f"❌ 机械臂同步移动到位置 {i+1} 失败 - 无可用电机")
                        continue
                
                # 等待运动完成
                self.message_updated.emit(f"等待机械臂到达位置 {i+1}...")
                self.msleep(5000)  # 等待5秒确保运动完成
                
            except Exception as e:
                self.message_updated.emit(f"❌ 控制机械臂失败: {str(e)}")
                continue
            
            # 获取真实的末端位姿 (读取电机实际角度并考虑减速比和方向)
            try:
                # 收集当前所有关节的真实角度（从电机读取）
                actual_joint_angles = []
                all_motors_available = True
                
                for j in range(6):
                    motor_id = j + 1
                    if motor_id in self.motors:
                        try:
                            motor = self.motors[motor_id]
                            # 读取电机当前位置
                            motor_position = motor.read_parameters.get_position()
                            
                            # 考虑减速比和方向计算正确的输出端角度
                            ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                            direction = self.motor_config_manager.get_motor_direction(motor_id)
                            # 电机读取的角度需要先应用方向修正，再除以减速比得到输出端角度
                            output_position = (motor_position * direction) / ratio
                            
                            actual_joint_angles.append(output_position)
                        except Exception as motor_error:
                            self.message_updated.emit(f"⚠️ 读取电机{motor_id}角度失败: {str(motor_error)}")
                            # 如果读取失败，使用预设角度作为备选
                            actual_joint_angles.append(joint_angles[j])
                    else:
                        self.message_updated.emit(f"⚠️ 电机{motor_id}未连接，使用预设角度")
                        actual_joint_angles.append(joint_angles[j])
                
                # 使用实际读取的关节角度计算末端位姿
                end_pose = self.kinematics.get_end_effector_pose(actual_joint_angles)
                position = end_pose['position']
                euler_angles = end_pose['euler_angles']
                
                # 显示实际使用的关节角度（用于调试）
                angles_str = [f"{angle:.2f}°" for angle in actual_joint_angles]
                
                # 构造位姿数据 [x(mm), y(mm), z(mm), yaw(deg), pitch(deg), roll(deg)] - ZYX顺序
                pose_data = [
                    position[0],    # X位置单位：毫米
                    position[1],    # Y位置单位：毫米
                    position[2],    # Z位置单位：毫米
                    euler_angles[0],     # Yaw角（绕Z轴旋转，度）
                    euler_angles[1],     # Pitch角（绕Y轴旋转，度）
                    euler_angles[2]      # Roll角（绕X轴旋转，度）
                ]
                poses_data.append(pose_data)
                
                
            except Exception as e:
                self.message_updated.emit(f"❌ 计算末端位姿失败: {str(e)}")
                continue
            
            # 拍摄照片
            try:
                self.message_updated.emit(f"正在拍摄第 {i+1} 张照片...")
                
                # 获取当前相机帧
                current_frame = self.parent_widget.get_current_camera_frame()
                if current_frame is None:
                    self.message_updated.emit(f"⚠️ 无法获取相机图像，请确保相机已启动")
                    # 创建一个占位符图像
                    current_frame = np.zeros((480, 640, 3), dtype=np.uint8)
                    cv2.putText(current_frame, f"No Camera Frame {i+1}", (50, 240), 
                              cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 255), 2)
                
                # 保存图像
                image_path = os.path.join(image_dir, f"{i+1}.jpg")
                cv2.imwrite(image_path, current_frame)
                
                self.message_updated.emit(f"✅ 已保存图像: {i+1}.jpg")
                self.image_captured.emit(image_path, np.array(pose_data))
                
            except Exception as e:
                self.message_updated.emit(f"❌ 拍照失败: {str(e)}")
                continue
            
            # 更新进度
            self.progress_updated.emit(i + 1, len(self.preset_poses))
            
            # 短暂延时，确保操作稳定
            self.msleep(500)
        
        if self.is_running:
            # 保存位姿数据
            targets_file = os.path.join(self.output_dir, "targets.txt")
            csv_file = os.path.join(self.output_dir, "robotToolPose.csv")
            with open(targets_file, 'w') as f:
                for pose_data in poses_data:
                    f.write(','.join(map(str, pose_data)) + '\n')
            
            self.message_updated.emit("数据采集完成，开始手眼标定计算...")
            self.message_updated.emit(f"使用标定板参数: {self.corner_width}×{self.corner_height} 角点, 方格尺寸={self.square_size}m")
            
            # 执行手眼标定 - 使用界面设置的参数
            try:
                eih = EyeInHand()
                eih.poses_to_matrix_save_csv(targets_file, csv_file)
                rotation_matrix, translation_vector = eih.compute_T(
                    image_dir, 
                    self.corner_width,   # 使用界面设置的宽度内角点数
                    self.corner_height,  # 使用界面设置的高度内角点数
                    self.square_size    # 使用界面设置的方格尺寸
                )
                
                # 构造变换矩阵 - 统一使用米作为单位
                RT_camera2end = np.eye(4)
                RT_camera2end[0:3, 0:3] = rotation_matrix
                # 保持米单位：标定结果直接使用米
                RT_camera2end[0:3, 3] = translation_vector.reshape(3)
                
                result = {
                    'rotation_matrix': rotation_matrix.tolist(),
                    'translation_vector': translation_vector.tolist(),
                    'RT_camera2end': RT_camera2end.tolist(),
                    'poses_count': len(poses_data),
                    'image_dir': image_dir,
                    'targets_file': targets_file,
                    'calibration_params': {
                        'corner_width': self.corner_width,
                        'corner_height': self.corner_height,
                        'square_size': self.square_size
                    }
                }
                
                self.calibration_finished.emit(result)
                self.message_updated.emit("手眼标定完成！")
                
            except Exception as e:
                self.message_updated.emit(f"标定计算失败: {str(e)}")
        
    def stop(self):
        """停止采集"""
        self.is_running = False


class ExistingDataCalibrationThread(QThread):
    """使用已有数据进行手眼标定计算的线程"""
    
    progress_updated = pyqtSignal(int, int)  # 当前进度, 总数
    message_updated = pyqtSignal(str)
    calibration_finished = pyqtSignal(dict)  # 标定结果
    
    def __init__(self, image_dir, targets_file, data_count, corner_width, corner_height, square_size, output_dir):
        super().__init__()
        self.image_dir = image_dir
        self.targets_file = targets_file
        self.data_count = data_count
        self.corner_width = corner_width
        self.corner_height = corner_height
        self.square_size = square_size
        self.output_dir = output_dir
        self.is_running = False
    
    def run(self):
        """执行标定计算"""
        self.is_running = True
        self.message_updated.emit("开始使用已有数据进行手眼标定计算...")
        
        try:
            # 读取位姿数据
            poses_data = []
            with open(self.targets_file, 'r') as f:
                for i, line in enumerate(f):
                    if i >= self.data_count:  # 只读取指定数量的数据
                        break
                    line = line.strip()
                    if line and not line.startswith('#'):
                        try:
                            pose_values = [float(x) for x in line.split(',')]
                            if len(pose_values) >= 6:
                                poses_data.append(pose_values)
                        except ValueError:
                            continue
            
            if len(poses_data) < self.data_count:
                self.message_updated.emit(f"⚠️ 实际可用位姿数据: {len(poses_data)} 组")
                self.data_count = len(poses_data)
            
            # 更新进度
            self.progress_updated.emit(0, self.data_count)
            
            # 验证图片文件存在性
            missing_images = []
            for i in range(1, self.data_count + 1):
                image_path = os.path.join(self.image_dir, f"{i}.jpg")
                if not os.path.exists(image_path):
                    missing_images.append(f"{i}.jpg")
            
            if missing_images:
                self.message_updated.emit(f"⚠️ 缺少图片文件: {', '.join(missing_images[:5])}{'...' if len(missing_images) > 5 else ''}")
                if len(missing_images) > self.data_count // 2:  # 如果缺少超过一半的图片
                    self.message_updated.emit("❌ 缺少的图片文件过多，无法进行标定")
                    return
            
            self.message_updated.emit(f"数据验证完成，开始手眼标定计算...")
            self.message_updated.emit(f"使用标定板参数: {self.corner_width}×{self.corner_height} 角点, 方格尺寸={self.square_size}m")
            
            # 生成CSV文件并设置csv_path
            csv_file = os.path.join(self.output_dir, "robotToolPose.csv")
            self.message_updated.emit("生成CSV格式的位姿文件...")
            
            eih = EyeInHand()
            # 调用 poses_to_matrix_save_csv 来生成CSV文件并设置 csv_path
            eih.poses_to_matrix_save_csv(self.targets_file, csv_file)
            
            # 执行手眼标定计算
            self.message_updated.emit("正在进行手眼标定计算，请稍候...")
            
            rotation_matrix, translation_vector = eih.compute_T(
                self.image_dir, 
                self.corner_width,   # 使用界面设置的宽度内角点数
                self.corner_height,  # 使用界面设置的高度内角点数
                self.square_size    # 使用界面设置的方格尺寸
            )
            
            # 构造变换矩阵 - 统一使用米作为单位
            RT_camera2end = np.eye(4)
            RT_camera2end[0:3, 0:3] = rotation_matrix
            # 保持米单位：标定结果直接使用米
            RT_camera2end[0:3, 3] = translation_vector.reshape(3)
            
            result = {
                'rotation_matrix': rotation_matrix.tolist(),
                'translation_vector': translation_vector.tolist(),
                'RT_camera2end': RT_camera2end.tolist(),
                'poses_count': len(poses_data),
                'image_dir': self.image_dir,
                'targets_file': self.targets_file,
                'calibration_params': {
                    'corner_width': self.corner_width,
                    'corner_height': self.corner_height,
                    'square_size': self.square_size
                }
            }
            
            # 更新最终进度
            self.progress_updated.emit(self.data_count, self.data_count)
            
            self.calibration_finished.emit(result)
            self.message_updated.emit("✅ 手眼标定计算完成！")
            
        except Exception as e:
            self.message_updated.emit(f"❌ 标定计算失败: {str(e)}")
            import traceback
            traceback.print_exc()
    
    def stop(self):
        """停止计算"""
        self.is_running = False


class HandEyeCalibrationWidget(QWidget):
    """手眼标定组件"""
    
    def __init__(self):
        super().__init__()
        self.motors_info = None
        self.motors = {}  # 添加实际motor对象存储
        self.calibration_thread = None
        self.preset_poses = []
        self.camera_params = self.load_camera_params()
        
        # 使用统一的电机配置管理器
        self.motor_config_manager = motor_config_manager
        
        # 摄像头控制
        self.camera_worker = None
        self.camera_enabled = False
        self.camera_index = 0  # 默认摄像头ID
        
        self.load_preset_poses()  # 启动时加载预设位置
        self.init_ui()
        
        # 初始化进度显示
        self.update_progress_display(0, len(self.preset_poses))
        
        # 初始化按钮状态 - 无电机连接时禁用回到初始位置按钮
        self.home_btn.setEnabled(False)
        
    
    def reload_motor_config(self):
        """重新加载电机配置"""
        try:
            # 重新加载配置管理器的配置
            self.motor_config_manager.config = self.motor_config_manager.load_config()
            print("✅ 手眼标定控件：电机配置已重新加载")
        except Exception as e:
            print(f"⚠ 手眼标定控件：重新加载电机配置失败: {e}")
    
    def reload_dh_config(self):
        """重新加载DH参数配置"""
        try:
            # 重新创建运动学实例，使用最新的DH参数配置
            self.kinematics = create_configured_kinematics()
        except Exception as e:
            print(f"⚠ 手眼标定控件：重新加载DH参数配置失败: {e}")
            self.kinematics = None
        
    def load_camera_params(self):
        """加载相机参数"""
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)),
            "config", "calibration_parameter.json"
        )
        
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = json.load(f)
                return config.get('one', {})
        except Exception as e:
            print(f"加载相机参数失败: {e}")
            return {}
    
    def load_preset_poses(self):
        """从YAML文件加载预设位置"""
        preset_path = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)),
            "config", "hand_eye_calibration_poses.yaml"
        )
        
        try:
            with open(preset_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                self.preset_poses = config.get('poses', [])
        except Exception as e:
            print(f"加载预设位置失败: {e}")
    
    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle("手眼标定工具")
        self.resize(1300, 1000)  
        
        # 设置窗口图标
        try:
            from PyQt5.QtGui import QIcon
            import os
            current_dir = os.path.dirname(os.path.abspath(__file__))
            icon_path = os.path.join(os.path.dirname(os.path.dirname(current_dir)), "logo.png")
            if os.path.exists(icon_path):
                self.setWindowIcon(QIcon(icon_path))
        except Exception:
            pass
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # 创建分割器
        splitter = QSplitter(Qt.Horizontal)
        main_layout.addWidget(splitter)
        
        # 左侧控制面板
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        
        # 相机参数组
        self.create_camera_group(left_layout)
        
        # 减速比设置组
        self.create_reducer_ratio_group(left_layout)
        
        # 预设位置组
        self.create_preset_group(left_layout)
        
        # 采集控制组
        self.create_control_group(left_layout)
        
        splitter.addWidget(left_widget)
        
        # 右侧结果显示
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        
        # 进度显示组
        self.create_progress_group(right_layout)
        
        # 结果显示组
        self.create_result_group(right_layout)
        
        splitter.addWidget(right_widget)
        
        # 设置分割器比例 - 调整比例适应更宽的界面
        splitter.setSizes([700, 600]) 
        
    def create_camera_group(self, parent_layout):
        """创建相机参数组"""
        group = QGroupBox("📷 相机参数(右相机)")
        main_layout = QHBoxLayout(group)  # 改为水平布局
        
        # 相机内参显示
        if self.camera_params:
            camera_matrix = self.camera_params.get('camera_matrix', [[0, 0, 0], [0, 0, 0], [0, 0, 1]])
            camera_model = self.camera_params.get('model', 'pinhole')
            
            # 模型类型显示
            model_group = QGroupBox("模型类型")
            model_layout = QVBoxLayout(model_group)
            model_name = "鱼眼模型" if camera_model == 'fisheye' else "标准针孔模型"
            model_label = QLabel(model_name)
            model_label.setStyleSheet("font-weight: bold; color: #007ACC;")
            model_layout.addWidget(model_label)
            main_layout.addWidget(model_group)
            
            # 内参矩阵分组
            intrinsic_group = QGroupBox("内参")
            intrinsic_layout = QGridLayout(intrinsic_group)
            intrinsic_layout.setContentsMargins(5, 5, 5, 5)
            intrinsic_layout.setSpacing(3)
            
            # 紧凑的2x2布局显示内参
            intrinsic_layout.addWidget(QLabel("fx:"), 0, 0)
            self.fx_label = QLabel(f"{camera_matrix[0][0]:.1f}")
            self.fx_label.setMinimumWidth(60)
            intrinsic_layout.addWidget(self.fx_label, 0, 1)
            
            intrinsic_layout.addWidget(QLabel("fy:"), 0, 2)
            self.fy_label = QLabel(f"{camera_matrix[1][1]:.1f}")
            self.fy_label.setMinimumWidth(60)
            intrinsic_layout.addWidget(self.fy_label, 0, 3)
            
            intrinsic_layout.addWidget(QLabel("cx:"), 1, 0)
            self.cx_label = QLabel(f"{camera_matrix[0][2]:.1f}")
            intrinsic_layout.addWidget(self.cx_label, 1, 1)
            
            intrinsic_layout.addWidget(QLabel("cy:"), 1, 2)
            self.cy_label = QLabel(f"{camera_matrix[1][2]:.1f}")
            intrinsic_layout.addWidget(self.cy_label, 1, 3)
            
            main_layout.addWidget(intrinsic_group)
            
            # 畸变系数分组 - 修复解析逻辑
            camera_distortion = self.camera_params.get('camera_distortion', [])
            if camera_distortion:
                # 处理多种格式的畸变系数：
                # 1. 旧格式：[[-0.04169075, -0.10853007, ...]]  (嵌套列表，一行多列)
                # 2. 新格式：[[0.281...], [0.074...], ...]      (嵌套列表，多行一列) 
                # 3. 直接格式：[-0.04169075, -0.10853007, ...]   (直接数值列表)
                distortion_coeffs = []
                
                try:
                    if len(camera_distortion) > 0:
                        if isinstance(camera_distortion[0], list):
                            if len(camera_distortion[0]) > 1:
                                # 旧格式：第一行包含多个系数
                                distortion_coeffs = camera_distortion[0]
                            else:
                                # 新格式：每行包含一个系数
                                distortion_coeffs = [row[0] for row in camera_distortion if len(row) > 0]
                        else:
                            # 直接是数值列表
                            distortion_coeffs = camera_distortion
                except (IndexError, TypeError) as e:
                    print(f"⚠️ 畸变系数解析失败: {e}，使用默认值")
                    distortion_coeffs = []
                
                # 根据相机模型和畸变系数数量进行显示
                expected_coeffs = 4 if camera_model == 'fisheye' else 5
                if len(distortion_coeffs) >= (4 if camera_model == 'fisheye' else 2):
                    distortion_group = QGroupBox(f"畸变系数 ({camera_model.upper()})")
                    distortion_layout = QGridLayout(distortion_group)
                    distortion_layout.setContentsMargins(5, 5, 5, 5)
                    distortion_layout.setSpacing(3)
                    
                    if camera_model == 'fisheye':
                        # 鱼眼模型：4个参数 k1, k2, k3, k4
                        distortion_layout.addWidget(QLabel("k1:"), 0, 0)
                        self.k1_label = QLabel(f"{float(distortion_coeffs[0]):.4f}")
                        self.k1_label.setMinimumWidth(80)
                        distortion_layout.addWidget(self.k1_label, 0, 1)
                        
                        distortion_layout.addWidget(QLabel("k2:"), 0, 2)
                        self.k2_label = QLabel(f"{float(distortion_coeffs[1]):.4f}")
                        self.k2_label.setMinimumWidth(80)
                        distortion_layout.addWidget(self.k2_label, 0, 3)
                        
                        distortion_layout.addWidget(QLabel("k3:"), 1, 0)
                        self.k3_label = QLabel(f"{float(distortion_coeffs[2]):.4f}" if len(distortion_coeffs) > 2 else "0.0000")
                        distortion_layout.addWidget(self.k3_label, 1, 1)
                        
                        distortion_layout.addWidget(QLabel("k4:"), 1, 2)
                        self.k4_label = QLabel(f"{float(distortion_coeffs[3]):.4f}" if len(distortion_coeffs) > 3 else "0.0000")
                        distortion_layout.addWidget(self.k4_label, 1, 3)
                    else:
                        # 针孔模型：通常5个参数 k1, k2, p1, p2, k3
                        distortion_layout.addWidget(QLabel("k1:"), 0, 0)
                        self.k1_label = QLabel(f"{float(distortion_coeffs[0]):.4f}")
                        self.k1_label.setMinimumWidth(80)
                        distortion_layout.addWidget(self.k1_label, 0, 1)
                        
                        distortion_layout.addWidget(QLabel("k2:"), 0, 2)
                        self.k2_label = QLabel(f"{float(distortion_coeffs[1]):.4f}" if len(distortion_coeffs) > 1 else "0.0000")
                        self.k2_label.setMinimumWidth(80)
                        distortion_layout.addWidget(self.k2_label, 0, 3)
                        
                        if len(distortion_coeffs) > 2:
                            distortion_layout.addWidget(QLabel("p1:"), 1, 0)
                            self.p1_label = QLabel(f"{float(distortion_coeffs[2]):.4f}")
                            distortion_layout.addWidget(self.p1_label, 1, 1)
                        
                        if len(distortion_coeffs) > 3:
                            distortion_layout.addWidget(QLabel("p2:"), 1, 2)
                            self.p2_label = QLabel(f"{float(distortion_coeffs[3]):.4f}")
                            distortion_layout.addWidget(self.p2_label, 1, 3)
                        
                        if len(distortion_coeffs) > 4:
                            distortion_layout.addWidget(QLabel("k3:"), 2, 0)
                            self.k3_label = QLabel(f"{float(distortion_coeffs[4]):.4f}")
                            distortion_layout.addWidget(self.k3_label, 2, 1)
                    
                    main_layout.addWidget(distortion_group)
                else:
                    # 畸变系数数量不足
                    no_distortion_group = QGroupBox("畸变系数")
                    no_distortion_layout = QVBoxLayout(no_distortion_group)
                    no_distortion_layout.addWidget(QLabel(f"⚠️ 畸变系数不足 ({len(distortion_coeffs)})"))
                    main_layout.addWidget(no_distortion_group)
            else:
                # 如果没有畸变系数，显示提示
                no_distortion_group = QGroupBox("畸变系数")
                no_distortion_layout = QVBoxLayout(no_distortion_group)
                no_distortion_layout.addWidget(QLabel("⚠️ 未找到"))
                main_layout.addWidget(no_distortion_group)
                
        else:
            # 如果没有相机参数，显示提示
            no_params_layout = QVBoxLayout()
            no_params_layout.addWidget(QLabel("⚠️ 未找到相机参数配置文件"))
            main_layout.addLayout(no_params_layout)
        
        parent_layout.addWidget(group)
    
    def create_reducer_ratio_group(self, parent_layout):
        """创建减速比设置组"""
        ratio_group = QGroupBox("⚙️ 电机参数配置")
        ratio_group.setMaximumHeight(120)
        ratio_group_layout = QVBoxLayout(ratio_group)
        
        # 说明文字
        info_label = QLabel("💡 电机减速比和方向设置已移至菜单栏\"工具\"->\"电机参数设置\"\n"
                           "📝 机械臂控制方式：采用梯形曲线位置模式，最大速度500RPM，加减速200RPM/s\n"
                           "🏠 初始位置：点击'回到初始位置'可将所有关节移动到0度位置")
        info_label.setStyleSheet("color: #666; font-size: 11px; padding: 8px; background-color: #f0f8ff; border: 1px solid #ddd; border-radius: 3px;")
        info_label.setWordWrap(True)
        ratio_group_layout.addWidget(info_label)
        
        parent_layout.addWidget(ratio_group)
    
    def create_preset_group(self, parent_layout):
        """创建预设位置组"""
        group = QGroupBox(f"🎯 预设采集位置 (共 {len(self.preset_poses)} 个)")
        self.preset_group = group
        group.setMinimumHeight(200)  # 从120增加到200，给表格更多空间
        layout = QVBoxLayout(group)
        
        # 预设位置表格
        self.preset_table = QTableWidget(0, 7)
        self.preset_table.setHorizontalHeaderLabels([
            "序号", "关节1(°)", "关节2(°)", "关节3(°)", "关节4(°)", "关节5(°)", "关节6(°)"
        ])
        self.preset_table.setAlternatingRowColors(True)
        # 设置表格的最小高度，确保能显示更多行
        self.preset_table.setMinimumHeight(150)
        layout.addWidget(self.preset_table)
        
        # 刷新预设位置显示
        self.refresh_preset_table()
        
        parent_layout.addWidget(group)
    
    def reload_preset_poses(self):
        """重新加载手眼标定预设位置并刷新界面"""
        try:
            self.load_preset_poses()
            if hasattr(self, 'preset_group') and self.preset_group:
                self.preset_group.setTitle(f"🎯 预设采集位置 (共 {len(self.preset_poses)} 个)")
            self.refresh_preset_table()
            # 重置进度显示为 0/总数
            self.update_progress_display(0, len(self.preset_poses))
        except Exception as e:
            self.update_status(f"⚠️ 重新加载预设位置失败: {e}")
    
    def refresh_preset_table(self):
        """刷新预设位置表格显示"""
        self.preset_table.setRowCount(0)
        
        for i, pose in enumerate(self.preset_poses):
            row = self.preset_table.rowCount()
            self.preset_table.insertRow(row)
            
            self.preset_table.setItem(row, 0, QTableWidgetItem(str(i + 1)))
            joint_angles = pose.get('joint_angles', [0] * 6)
            for j, angle in enumerate(joint_angles):
                self.preset_table.setItem(row, j + 1, QTableWidgetItem(f"{angle:.1f}"))
    
    def create_control_group(self, parent_layout):
        """创建采集控制组"""
        group = QGroupBox("⚙️ 采集控制")
        layout = QVBoxLayout(group)
        layout.setSpacing(8)  # 减少间距
        
        # 第一行：输出目录和摄像头ID
        top_layout = QHBoxLayout()
        
        # 输出目录选择（左侧）
        top_layout.addWidget(QLabel("输出目录:"))
        self.output_dir_label = QLabel("./data")
        self.output_dir_label.setStyleSheet("border: 1px solid gray; padding: 3px;")
        self.output_dir_label.setMaximumWidth(150)
        top_layout.addWidget(self.output_dir_label)
        
        self.select_dir_btn = QPushButton("📁")
        self.select_dir_btn.setMaximumWidth(30)
        self.select_dir_btn.setToolTip("选择输出目录")
        self.select_dir_btn.clicked.connect(self.select_output_dir)
        top_layout.addWidget(self.select_dir_btn)
        
        top_layout.addWidget(QLabel("  |  摄像头ID:"))
        self.camera_id_spin = QSpinBox()
        self.camera_id_spin.setRange(0, 10)
        self.camera_id_spin.setValue(0)
        self.camera_id_spin.setMaximumWidth(70)
        self.camera_id_spin.setToolTip("设置摄像头设备ID，通常为0")
        self.camera_id_spin.valueChanged.connect(self.on_camera_id_changed)
        top_layout.addWidget(self.camera_id_spin)
        
        self.camera_status_label = QLabel("📷 摄像头未启动")
        self.camera_status_label.setStyleSheet("color: gray; font-weight: bold; font-size: 10px;")
        top_layout.addWidget(self.camera_status_label)
        
        top_layout.addStretch()
        layout.addLayout(top_layout)
        
        # 第二行：标定板参数（紧凑的水平布局）
        board_layout = QHBoxLayout()
        board_layout.addWidget(QLabel("标定板:"))
        
        board_layout.addWidget(QLabel("宽度"))
        self.corner_width_spin = QSpinBox()
        self.corner_width_spin.setRange(5, 15)
        self.corner_width_spin.setValue(5)
        self.corner_width_spin.setMaximumWidth(70)
        self.corner_width_spin.setToolTip("棋盘格宽度方向的内角点数量")
        board_layout.addWidget(self.corner_width_spin)
        
        board_layout.addWidget(QLabel("×"))
        
        board_layout.addWidget(QLabel("高度"))
        self.corner_height_spin = QSpinBox()
        self.corner_height_spin.setRange(5, 15)
        self.corner_height_spin.setValue(8)
        self.corner_height_spin.setMaximumWidth(70)
        self.corner_height_spin.setToolTip("棋盘格高度方向的内角点数量")
        board_layout.addWidget(self.corner_height_spin)
        
        board_layout.addWidget(QLabel("内角点, 方格"))
        self.square_size_spin = QDoubleSpinBox()
        self.square_size_spin.setRange(0.001, 0.1)
        self.square_size_spin.setValue(0.03)
        self.square_size_spin.setSuffix("m")
        self.square_size_spin.setDecimals(3)
        self.square_size_spin.setMaximumWidth(110)
        board_layout.addWidget(self.square_size_spin)
        
        board_layout.addStretch()
        layout.addLayout(board_layout)
        
        # 第三行：控制按钮
        control_layout = QHBoxLayout()
        
        self.start_btn = QPushButton("🚀 开始采集")
        self.start_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; }")
        self.start_btn.setMinimumHeight(32)  # 略微减小高度
        self.start_btn.clicked.connect(self.start_calibration)
        control_layout.addWidget(self.start_btn)
        
        self.calculate_btn = QPushButton("🧮 直接计算")
        self.calculate_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; }")
        self.calculate_btn.setMinimumHeight(32)
        self.calculate_btn.setToolTip("使用已有的图片和位姿数据直接进行手眼标定计算")
        self.calculate_btn.clicked.connect(self.calculate_existing_data)
        control_layout.addWidget(self.calculate_btn)
        
        self.stop_btn = QPushButton("⏹️ 停止采集")
        self.stop_btn.setEnabled(False)
        self.stop_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.stop_btn.setMinimumHeight(32)
        self.stop_btn.clicked.connect(self.stop_calibration)
        control_layout.addWidget(self.stop_btn)
        
        self.home_btn = QPushButton("🏠 回到初始位置")
        self.home_btn.setStyleSheet("QPushButton { background-color: #FF9800; color: white; font-weight: bold; }")
        self.home_btn.setMinimumHeight(32)
        self.home_btn.setToolTip("将所有关节移动到0度位置")
        self.home_btn.clicked.connect(self.move_to_home_position)
        control_layout.addWidget(self.home_btn)
        
        layout.addLayout(control_layout)
        
        parent_layout.addWidget(group)
    
    def on_camera_id_changed(self, value):
        """摄像头ID改变事件"""
        self.camera_index = value
        if self.camera_enabled:
            # 如果摄像头正在运行，重启摄像头
            self.stop_camera()
            self.start_camera()
    
    def create_progress_group(self, parent_layout):
        """创建摄像头显示和状态组"""
        group = QGroupBox("📷 摄像头显示与采集状态")
        layout = QVBoxLayout(group)
        
        # 摄像头显示区域
        camera_title = QLabel("📷 双目摄像头 (右侧)")
        camera_title.setStyleSheet("font-weight: bold; color: #333; font-size: 12px;")
        layout.addWidget(camera_title)
        
        # 摄像头显示标签
        self.camera_display_label = QLabel()
        self.camera_display_label.setMinimumSize(320, 240)
        self.camera_display_label.setMaximumHeight(280)
        self.camera_display_label.setMinimumWidth(320)
        self.camera_display_label.setStyleSheet("""
            QLabel {
                border: 2px solid #ddd;
                background-color: #f8f9fa;
                color: #666;
                font-size: 14px;
                text-align: center;
            }
        """)
        self.camera_display_label.setAlignment(Qt.AlignCenter)
        self.camera_display_label.setText("📷\n摄像头未启动\n点击'开始采集'自动启动摄像头")
        self.camera_display_label.setScaledContents(True)  # 自动缩放图像内容
        layout.addWidget(self.camera_display_label)
        
        # 采集进度显示
        progress_layout = QHBoxLayout()
        progress_layout.addWidget(QLabel("采集进度:"))
        self.progress_label = QLabel("0 / 0")
        self.progress_label.setStyleSheet("font-weight: bold; color: #007ACC;")
        progress_layout.addWidget(self.progress_label)
        progress_layout.addStretch()
        layout.addLayout(progress_layout)
        
        # 状态信息
        self.status_text = QTextEdit()
        self.status_text.setMaximumHeight(120)
        self.status_text.setReadOnly(True)
        layout.addWidget(self.status_text)
        
        parent_layout.addWidget(group)
    
    def create_result_group(self, parent_layout):
        """创建结果显示组"""
        group = QGroupBox("📋 标定结果")
        layout = QVBoxLayout(group)
        
        # 标定结果显示
        self.result_text = QTextEdit()
        self.result_text.setReadOnly(True)
        self.result_text.setFont(QFont("Consolas", 9))
        layout.addWidget(self.result_text)
        
        # 保存和验证按钮
        save_layout = QHBoxLayout()
        self.save_result_btn = QPushButton("💾 保存标定结果")
        self.save_result_btn.setEnabled(False)
        self.save_result_btn.clicked.connect(self.save_calibration_result)
        save_layout.addWidget(self.save_result_btn)
        
        self.export_config_btn = QPushButton("📤 导出配置文件")
        self.export_config_btn.setEnabled(False)
        self.export_config_btn.clicked.connect(self.export_config)
        save_layout.addWidget(self.export_config_btn)
        
        self.verify_btn = QPushButton("🔍 验证标定精度")
        self.verify_btn.setEnabled(False)
        self.verify_btn.setStyleSheet("QPushButton { background-color: #9C27B0; color: white; font-weight: bold; }")
        self.verify_btn.setToolTip("验证手眼标定的精度，通过对比同一物体在不同视角下的世界坐标")
        self.verify_btn.clicked.connect(self.start_verification)
        save_layout.addWidget(self.verify_btn)
        
        layout.addLayout(save_layout)
        
        parent_layout.addWidget(group)
    
    def select_output_dir(self):
        """选择输出目录"""
        dir_path = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if dir_path:
            self.output_dir_label.setText(dir_path)
    
    def update_camera_display(self, frame):
        """更新摄像头显示"""
        try:
            # 将OpenCV的BGR格式转换为RGB格式
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            
            # 获取图像尺寸
            height, width, channel = rgb_frame.shape
            bytes_per_line = 3 * width
            
            # 创建QImage
            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            
            # 转换为QPixmap并设置到标签
            pixmap = QPixmap.fromImage(q_image)
            
            # 根据标签大小缩放图像，保持宽高比
            if hasattr(self, 'camera_display_label') and self.camera_display_label:
                scaled_pixmap = pixmap.scaled(
                    self.camera_display_label.size(), 
                    Qt.KeepAspectRatio, 
                    Qt.SmoothTransformation
                )
                self.camera_display_label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            # 如果显示失败，显示错误信息
            if hasattr(self, 'camera_display_label'):
                self.camera_display_label.clear()
                self.camera_display_label.setText(f"❌\n摄像头显示失败\n{str(e)}")
    
    def update_progress_display(self, current, total):
        """更新进度显示"""
        if hasattr(self, 'progress_label'):
            self.progress_label.setText(f"{current} / {total}")
            if current > 0:
                percentage = int((current / total) * 100)
                self.progress_label.setToolTip(f"进度: {percentage}%")
    
    def start_calibration(self):
        """开始手眼标定"""
        if not self.preset_poses:
            QMessageBox.warning(self, "警告", "没有找到预设位置！请检查配置文件。")
            return
        
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接机械臂！")
            return
        
        # 启动摄像头
        if not self.camera_enabled:
            self.start_camera()
            # 等待摄像头启动
            QTimer.singleShot(1000, self._start_calibration_delayed)
        else:
            self._start_calibration_delayed()
    
    def _start_calibration_delayed(self):
        """延迟启动标定（等待摄像头启动完成）"""
        # 检查摄像头状态
        if not self.camera_enabled or self.camera_worker is None:
            reply = QMessageBox.question(
                self, 
                "摄像头未启动", 
                "摄像头启动失败，这将影响图像采集质量。\n\n"
                "是否继续标定？",
                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            if reply == QMessageBox.No:
                return
        
        # 获取输出目录
        output_dir = self.output_dir_label.text()
        if not os.path.exists(output_dir):
            try:
                os.makedirs(output_dir)
            except Exception as e:
                QMessageBox.critical(self, "错误", f"创建输出目录失败:\n{str(e)}")
                return
        # 重置采集图片目录
        try:
            image_dir = os.path.join(output_dir, "eye_hand_calibration_image")
            if os.path.exists(image_dir):
                import shutil
                shutil.rmtree(image_dir, ignore_errors=True)
            os.makedirs(image_dir, exist_ok=True)
        except Exception as e:
            self.update_status(f"⚠️ 清空采集目录失败: {e}")
        
        # 获取标定板参数
        corner_width = self.corner_width_spin.value()
        corner_height = self.corner_height_spin.value()
        square_size = self.square_size_spin.value()
        
        # 清空结果显示
        self.result_text.clear()
        self.update_progress_display(0, len(self.preset_poses))  # 重置进度显示
        
        # 显示使用的参数
        self.update_status(f"标定板参数: {corner_width}×{corner_height} 内角点, 方格尺寸={square_size}m")
        self.update_status("⚠️ 手眼标定开始，机械臂将自动移动，请确保安全！")
        
        # 启动采集线程
        self.calibration_thread = HandEyeCalibrationThread(
            self.preset_poses, output_dir, corner_width, corner_height, square_size, 
            self.motor_config_manager, self, self.motors
        )
        self.calibration_thread.progress_updated.connect(self.update_progress_display) # 连接新的信号
        self.calibration_thread.message_updated.connect(self.update_status)
        self.calibration_thread.calibration_finished.connect(self.on_calibration_finished)
        
        self.calibration_thread.start()
        
        # 更新按钮状态
        self.start_btn.setEnabled(False)
        self.stop_btn.setEnabled(True)
        self.home_btn.setEnabled(False)  # 标定期间禁用回到初始位置按钮
        
        self.update_status("开始手眼标定数据采集...")
    
    def stop_calibration(self):
        """停止手眼标定"""
        if self.calibration_thread and self.calibration_thread.isRunning():
            self.calibration_thread.stop()
            self.calibration_thread.wait()
        
        # 更新按钮状态
        self.start_btn.setEnabled(True)
        self.calculate_btn.setEnabled(True)  # 恢复直接计算按钮
        self.stop_btn.setEnabled(False)
        # 根据电机连接状态设置home按钮
        self.home_btn.setEnabled(bool(self.motors))
        
        # 重置进度显示
        self.update_progress_display(0, len(self.preset_poses))
        
        # 停止摄像头
        self.stop_camera()
        
        self.update_status("手眼标定已停止，摄像头已关闭")
    
    def on_calibration_finished(self, result):
        """标定完成处理"""
        # 显示结果
        result_text = f"""
手眼标定完成！

旋转矩阵 (Rotation Matrix):
{np.array(result['rotation_matrix'])}

平移向量 (Translation Vector):
{np.array(result['translation_vector'])}

相机到末端变换矩阵 (RT_camera2end):
{np.array(result['RT_camera2end'])}

采集位置数量: {result['poses_count']}
图像目录: {result['image_dir']}
位姿文件: {result['targets_file']}

标定板参数:
宽度内角点: {result['calibration_params']['corner_width']}
高度内角点: {result['calibration_params']['corner_height']}
方格尺寸: {result['calibration_params']['square_size']}m
        """
        
        self.result_text.setText(result_text)
        
        # 保存结果到类变量
        self.calibration_result = result
        
        # 启用保存和验证按钮
        self.save_result_btn.setEnabled(True)
        self.export_config_btn.setEnabled(True)
        self.verify_btn.setEnabled(True)
        
        # 更新按钮状态
        self.start_btn.setEnabled(True)
        self.calculate_btn.setEnabled(True)  # 恢复直接计算按钮
        self.stop_btn.setEnabled(False)
        self.home_btn.setEnabled(True)  # 恢复回到初始位置按钮
        
        # 设置完成状态的进度显示
        self.update_progress_display(result['poses_count'], result['poses_count'])
        
        # 标定完成后停止摄像头
        self.stop_camera()
        
        self.update_status("手眼标定完成！摄像头已关闭")

    def save_calibration_result(self):
        """保存标定结果到配置文件"""
        if not hasattr(self, 'calibration_result'):
            QMessageBox.warning(self, "警告", "没有可保存的标定结果")
            return
        
        # 保存到calibration_parameter.json配置文件
        config_path = os.path.join(
            os.path.dirname(os.path.dirname(current_dir)),
            "config", "calibration_parameter.json"
        )
        
        try:
            # 加载现有配置
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
            else:
                config = {"one": {}, "two": {}, "eyeinhand": {}}
            
            # 更新手眼标定结果
            config['eyeinhand']['RT_camera2end'] = self.calibration_result['RT_camera2end']
            
            # 保存配置文件
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            
            self.update_status(f"✅ 手眼标定结果已保存到 {config_path}")
            QMessageBox.information(self, "保存成功", f"手眼标定结果已保存到:\n{config_path}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存手眼标定结果失败:\n{str(e)}")

    def export_config(self):
        """导出配置文件"""
        if not hasattr(self, 'calibration_result'):
            return
        
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出配置文件", "calibration_parameter.json", "JSON Files (*.json)"
        )
        
        if file_path:
            try:
                # 更新配置文件格式
                config = {
                    "one": self.camera_params,
                    "eyeinhand": {
                        "RT_camera2end": self.calibration_result['RT_camera2end']
                    }
                }
                
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(config, f, indent=4, ensure_ascii=False)
                
                self.update_status(f"配置文件已导出到 {file_path}")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"导出配置文件失败:\n{str(e)}")
    
    def update_status(self, message):
        """更新状态信息"""
        self.status_text.append(f"[{np.datetime64('now', 's')}] {message}")
        self.status_text.ensureCursorVisible()
    
    def update_motors(self, motors_info):
        """更新电机连接信息"""
        self.motors_info = motors_info
        self.motors = motors_info # 保存实际的motor对象
        
        if motors_info:
            motor_count = len(motors_info)
            motor_ids = list(motors_info.keys())
            self.update_status(f"✅ 已连接 {motor_count} 个电机，ID: {motor_ids}")
            # 有电机连接时启用回到初始位置按钮
            self.home_btn.setEnabled(True)
        else:
            self.update_status("❌ 电机连接信息为空")
            # 无电机连接时禁用回到初始位置按钮
            self.home_btn.setEnabled(False)
    
    def clear_motors(self):
        """清空电机连接信息"""
        self.motors_info = None
        self.motors = {} # 清空实际的motor对象
        self.update_status("电机未连接")
        # 电机断开时禁用回到初始位置按钮
        self.home_btn.setEnabled(False)
    
    def showEvent(self, event):
        """窗口显示事件处理 - 每次显示时重新加载预设位置"""
        super().showEvent(event)
        
        # 每次显示窗口时重新加载预设位置
        try:
            self.load_preset_poses()
            
            # 更新预设位置组标题
            if hasattr(self, 'preset_group') and self.preset_group:
                self.preset_group.setTitle(f"🎯 预设采集位置 (共 {len(self.preset_poses)} 个)")
            
            # 刷新预设位置表格
            if hasattr(self, 'preset_table'):
                self.refresh_preset_table()
            
            # 重置进度显示为 0/总数
            if hasattr(self, 'update_progress_display'):
                self.update_progress_display(0, len(self.preset_poses))
            
            
        except Exception as e:
            print(f"⚠️ 刷新预设位置失败: {e}")
    
    def closeEvent(self, event):
        """窗口关闭事件处理"""
        # 停止摄像头
        self.stop_camera()
        
        # 停止标定线程
        if self.calibration_thread and self.calibration_thread.isRunning():
            self.calibration_thread.stop()
            self.calibration_thread.wait(3000)  # 等待最多3秒
        
        event.accept()

    def start_camera(self):
        """启动摄像头"""
        try:
            if self.camera_worker is not None:
                self.stop_camera()
            
            self.camera_worker = CameraWorker(camera_index=self.camera_index)
            self.camera_worker.frame_ready.connect(self.update_camera_frame)
            self.camera_worker.error.connect(self.on_camera_error)
            self.camera_worker.start_camera()
            
            self.camera_enabled = True
            self.camera_status_label.setText("📷 摄像头启动中...")
            self.camera_status_label.setStyleSheet("color: orange; font-weight: bold;")
            
        except Exception as e:
            self.camera_status_label.setText(f"❌ 摄像头启动失败")
            self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
            QMessageBox.warning(self, "错误", f"启动摄像头失败:\n{str(e)}")
    
    def stop_camera(self):
        """停止摄像头"""
        try:
            if self.camera_worker is not None:
                self.camera_worker.stop_camera()
                self.camera_worker = None
            
            self.camera_enabled = False
            self.camera_status_label.setText("📷 摄像头未启动")
            self.camera_status_label.setStyleSheet("color: gray; font-weight: bold;")
            
            # 清除摄像头显示
            if hasattr(self, 'camera_display_label'):
                self.camera_display_label.clear()
                self.camera_display_label.setText("📷\n摄像头未启动\n点击'开始采集'自动启动摄像头")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止摄像头失败:\n{str(e)}")
    
    @pyqtSlot(np.ndarray)
    def update_camera_frame(self, frame):
        """更新摄像头画面"""
        try:
            # 更新摄像头显示
            self.update_camera_display(frame)
            
            # 更新状态
            if self.camera_enabled:
                self.camera_status_label.setText("✅ 摄像头已就绪")
                self.camera_status_label.setStyleSheet("color: green; font-weight: bold;")
                
        except Exception as e:
            self.camera_status_label.setText("❌ 摄像头显示失败")
            self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
    
    @pyqtSlot(str)
    def on_camera_error(self, error_message):
        """处理摄像头错误"""
        self.camera_status_label.setText(f"❌ 摄像头错误")
        self.camera_status_label.setStyleSheet("color: red; font-weight: bold;")
        
        # 显示错误提示
        if hasattr(self, 'camera_display_label'):
            self.camera_display_label.clear()
            self.camera_display_label.setText(f"❌\n摄像头错误\n{error_message}")
        
        # 自动停止摄像头
        if self.camera_enabled:
            self.stop_camera()
        
        QMessageBox.warning(self, "摄像头错误", f"摄像头发生错误:\n{error_message}")
    
    def get_current_camera_frame(self):
        """获取当前摄像头画面"""
        if self.camera_worker is not None:
            return self.camera_worker.get_current_frame()
        return None
    
    def get_actual_angle(self, input_angle, motor_id=None):
        """根据减速比和方向设置计算实际发送给电机的角度"""
        # 获取对应电机的减速比和方向
        reducer_ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id) if motor_id else 1.0
        direction = self.motor_config_manager.get_motor_direction(motor_id) if motor_id else 1
        
        # 手眼标定中用户输入的是关节角度，需要乘以减速比得到电机端角度
        # 然后应用方向修正：正向=1，反向=-1
        motor_angle = input_angle * reducer_ratio * direction
        
        return motor_angle
    
    def move_to_home_position(self):
        """移动机械臂到初始位置（所有关节角度为0度）"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接机械臂！")
            return
        
        # 检查是否正在进行标定
        if self.calibration_thread and self.calibration_thread.isRunning():
            QMessageBox.warning(self, "警告", "手眼标定正在进行中，请先停止标定！")
            return
        
        # 定义初始位置：所有关节角度为0度
        home_angles = [0.0, 0.0, 0.0, 0.0, 0.0, 0.0]
        
        try:
            self.update_status("🏠 正在移动机械臂到初始位置...")
            
            # 暂时禁用按钮，防止重复操作
            self.home_btn.setEnabled(False)
            self.start_btn.setEnabled(False)
            # stop_btn保持禁用，因为没有在进行标定
            # self.stop_btn.setEnabled(False)  # 回到初始位置期间也禁用停止按钮
            
            # 运动参数
            max_speed = 500      # 最大速度500 RPM
            acceleration = 200    # 开始加速度200
            deceleration = 200    # 最后加速度200
            
            # 检测是否为Y板
            try:
                versions = set()
                for m in (self.motors or {}).values():
                    versions.add(str(getattr(m, 'drive_version', 'Y')).upper())
                is_y_board = (versions == {"Y"})
            except Exception:
                is_y_board = False
            
            success_count = 0
            if is_y_board:
                # Y板：一次性下发
                commands = []
                for j, angle in enumerate(home_angles):
                    motor_id = j + 1
                    if motor_id in self.motors:
                        try:
                            actual_angle = self.get_actual_angle(angle, motor_id)
                            motor = self.motors[motor_id]
                            func = motor.command_builder.position_mode_trapezoid(
                                position=actual_angle,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=True,
                                multi_sync=False
                            )
                            try:
                                from Control_SDK.Control_Core import ZDTCommandBuilder
                                single = ZDTCommandBuilder.build_single_command_bytes(motor_id, func)
                            except Exception:
                                single = [motor_id] + func
                            commands.append(single)
                        except Exception as motor_error:
                            self.update_status(f"❌ 电机 {motor_id} 参数构建失败: {str(motor_error)}")
                            self.home_btn.setEnabled(True)
                            self.start_btn.setEnabled(True)
                            return
                if not commands:
                    self.update_status("❌ 回到初始位置失败 - 无有效电机")
                    self.home_btn.setEnabled(True)
                    self.start_btn.setEnabled(True)
                    return
                try:
                    first_motor_id = list(self.motors.keys())[0]
                    first_motor = self.motors[first_motor_id]
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                    success_count = len(commands)
                    self.update_status("✅ 已下发Y42多电机命令，开始回到初始位置...")
                except Exception as e_y42:
                    self.update_status(f"❌ Y42多电机下发失败: {str(e_y42)}")
                    self.home_btn.setEnabled(True)
                    self.start_btn.setEnabled(True)
                    return
            else:
                # X板：逐电机multi_sync + 广播同步
                for j, angle in enumerate(home_angles):
                    motor_id = j + 1
                    if motor_id in self.motors:
                        try:
                            actual_angle = self.get_actual_angle(angle, motor_id)
                            motor = self.motors[motor_id]
                            motor.control_actions.move_to_position_trapezoid(
                                position=actual_angle,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=True,
                                multi_sync=True
                            )
                            success_count += 1
                        except Exception as motor_error:
                            self.update_status(f"❌ 电机 {motor_id} 设置失败: {str(motor_error)}")
                            self.home_btn.setEnabled(True)
                            self.start_btn.setEnabled(True)
                            return
            
            if success_count == 0:
                self.update_status("❌ 回到初始位置失败 - 没有电机成功设置")
                self.home_btn.setEnabled(True)
                self.start_btn.setEnabled(True)
                # stop_btn保持禁用，因为没有在进行标定
                return
            
            # 第二阶段（仅X板需要广播同步；Y板已一次性下发）
            if not is_y_board:
                try:
                    first_motor_id = list(self.motors.keys())[0]
                    first_motor = self.motors[first_motor_id]
                    broadcast_motor = first_motor.__class__(
                        motor_id=0,
                        interface_type=first_motor.interface_type,
                        shared_interface=True,
                        **first_motor.interface_kwargs
                    )
                    broadcast_motor.can_interface = first_motor.can_interface
                    broadcast_motor.control_actions.sync_motion()
                    self.update_status("✅ 机械臂开始移动到初始位置，请等待...")
                except Exception as sync_error:
                    self.update_status(f"❌ 同步执行失败: {str(sync_error)}")
                    self.home_btn.setEnabled(True)
                    self.start_btn.setEnabled(True)
                    return
            else:
                self.update_status("✅ 机械臂开始移动到初始位置，请等待...")
            
            # 使用定时器延迟恢复按钮状态，给机械臂足够的运动时间
            QTimer.singleShot(5000, self._on_home_movement_finished)  # 5秒后恢复
            
        except Exception as e:
            self.update_status(f"❌ 回到初始位置失败: {str(e)}")
            self.home_btn.setEnabled(True)
            self.start_btn.setEnabled(True)
            # stop_btn保持禁用，因为没有在进行标定
            # 取消阻塞弹窗
    
    def _on_home_movement_finished(self):
        """回到初始位置运动完成后的处理"""
        self.home_btn.setEnabled(True)
        self.start_btn.setEnabled(True)
        # stop_btn保持禁用，因为没有在进行标定
        self.update_status("🏠 机械臂已回到初始位置（所有关节0度）")
    
    def calculate_existing_data(self):
        """使用已有的图片和位姿数据直接进行手眼标定计算"""
        try:
            # 获取输出目录
            output_dir = self.output_dir_label.text()
            if not os.path.exists(output_dir):
                QMessageBox.warning(self, "警告", f"输出目录不存在: {output_dir}")
                return
            
            # 检查图片目录
            image_dir = os.path.join(output_dir, "eye_hand_calibration_image")
            if not os.path.exists(image_dir):
                QMessageBox.warning(self, "警告", f"图片目录不存在: {image_dir}")
                return
            
            # 检查位姿文件
            targets_file = os.path.join(output_dir, "targets.txt")
            if not os.path.exists(targets_file):
                QMessageBox.warning(self, "警告", f"位姿文件不存在: {targets_file}")
                return
            
            # 统计图片数量
            image_files = [f for f in os.listdir(image_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            image_count = len(image_files)
            
            # 读取位姿数据
            poses_data = []
            with open(targets_file, 'r') as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):  # 跳过空行和注释行
                        try:
                            pose_values = [float(x) for x in line.split(',')]
                            if len(pose_values) >= 6:  # 确保至少有6个值 (x,y,z,rx,ry,rz)
                                poses_data.append(pose_values)
                        except ValueError:
                            continue  # 跳过无法解析的行
            
            pose_count = len(poses_data)
            
            # 检查数据一致性
            if image_count == 0:
                QMessageBox.warning(self, "警告", f"图片目录中没有找到图片文件")
                return
            
            if pose_count == 0:
                QMessageBox.warning(self, "警告", f"位姿文件中没有找到有效的位姿数据")
                return
            
            if image_count != pose_count:
                reply = QMessageBox.question(
                    self, 
                    "数据不匹配", 
                    f"图片数量 ({image_count}) 与位姿数量 ({pose_count}) 不匹配。\n\n"
                    f"是否继续使用较少的数据进行标定？",
                    QMessageBox.Yes | QMessageBox.No,
                    QMessageBox.No
                )
                if reply == QMessageBox.No:
                    return
                
                # 使用较少的数据量
                data_count = min(image_count, pose_count)
                self.update_status(f"⚠️ 数据不匹配，将使用前 {data_count} 组数据进行标定")
            else:
                data_count = image_count
                self.update_status(f"✅ 找到 {data_count} 组匹配的图片和位姿数据")
            
            # 获取标定板参数
            corner_width = self.corner_width_spin.value()
            corner_height = self.corner_height_spin.value()
            square_size = self.square_size_spin.value()
            
            # 清空结果显示
            self.result_text.clear()
            self.update_progress_display(0, data_count)
            
            # 显示使用的参数
            self.update_status(f"标定板参数: {corner_width}×{corner_height} 内角点, 方格尺寸={square_size}m")
            self.update_status(f"开始使用已有数据进行手眼标定计算...")
            
            # 禁用按钮
            self.start_btn.setEnabled(False)
            self.calculate_btn.setEnabled(False)
            self.home_btn.setEnabled(False)
            
            # 启动计算线程
            self.calculation_thread = ExistingDataCalibrationThread(
                image_dir, targets_file, data_count, corner_width, corner_height, square_size, output_dir
            )
            self.calculation_thread.progress_updated.connect(self.update_progress_display)
            self.calculation_thread.message_updated.connect(self.update_status)
            self.calculation_thread.calibration_finished.connect(self.on_calibration_finished)
            
            self.calculation_thread.start()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动计算失败:\n{str(e)}")
            # 恢复按钮状态
            self.start_btn.setEnabled(True)
            self.calculate_btn.setEnabled(True)
            self.home_btn.setEnabled(bool(self.motors))
    
    def start_verification(self):
        """启动手眼标定精度验证"""
        if not hasattr(self, 'calibration_result') or not self.calibration_result:
            QMessageBox.warning(self, "警告", "请先完成手眼标定！")
            return
        
        if not self.motors:
            QMessageBox.warning(self, "警告", "请先连接机械臂！")
            return
        
        try:
            # 创建验证对话框
            verification_dialog = CalibrationVerificationDialog(
                self.calibration_result, 
                self.camera_params,
                self.motors,
                self.motor_config_manager,
                self.camera_index,
                self
            )
            verification_dialog.show()
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"启动验证失败:\n{str(e)}")
    

class CalibrationVerificationDialog(QDialog):
    """手眼标定验证对话框"""
    
    def __init__(self, calibration_result, camera_params, motors, motor_config_manager, camera_index, parent=None):
        super().__init__(parent)
        self.calibration_result = calibration_result
        self.camera_params = camera_params
        self.motors = motors
        self.motor_config_manager = motor_config_manager
        self.camera_index = camera_index
        
        # 验证数据
        self.point_measurements = []  # 存储测量点数据
        self.current_measurement = None  # 当前测量
        self.camera_worker = None
        
        # 运动学计算器
        self.kinematics = create_configured_kinematics()
        
        self.init_ui()
    
    def init_ui(self):
        """初始化验证对话框界面"""
        self.setWindowTitle("🔍 手眼标定精度验证")
        self.setModal(True)
        self.resize(1000, 900)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(10, 10, 10, 10)
        main_layout.setSpacing(10)
        
        # 顶部控制栏
        top_layout = QHBoxLayout()
        
        # 启动摄像头按钮
        self.start_camera_btn = QPushButton("📷 启动摄像头")
        self.start_camera_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; font-weight: bold; padding: 8px 16px; }")
        self.start_camera_btn.clicked.connect(self.start_camera_verification)
        top_layout.addWidget(self.start_camera_btn)
        
        # 位置控制
        top_layout.addWidget(QLabel("📍 选择位置:"))
        self.position_combo = QComboBox()
        self.position_combo.addItems([
            "当前位置", 
            "初始位置[0,0,0,0,90,0]", 
            "位置A[30,0,0,0,90,0]", 
            "位置B[-30,0,0,0,90,0]"
        ])
        self.position_combo.setMinimumWidth(200)
        top_layout.addWidget(self.position_combo)
        
        self.move_btn = QPushButton("🚀 移动")
        self.move_btn.setStyleSheet("QPushButton { background-color: #2196F3; color: white; font-weight: bold; padding: 8px 16px; }")
        self.move_btn.clicked.connect(self.move_to_selected_position)
        top_layout.addWidget(self.move_btn)
        
        top_layout.addStretch()
        main_layout.addLayout(top_layout)
        
        # 中间内容区域
        content_layout = QHBoxLayout()
        content_layout.setSpacing(15)
        
        # 左侧：摄像头显示（紧凑包装）
        camera_widget = QWidget()
        camera_widget.setFixedSize(650, 490)  # 刚好包含640*480 + 边距
        camera_layout = QVBoxLayout(camera_widget)
        camera_layout.setContentsMargins(5, 5, 5, 5)
        
        self.camera_label = QLabel()
        self.camera_label.setFixedSize(640, 480)
        self.camera_label.setStyleSheet("border: 2px solid #ddd; background-color: #f8f9fa;")
        self.camera_label.setAlignment(Qt.AlignCenter)
        self.camera_label.setText("📷 摄像头未启动\n点击启动摄像头后\n在画面中点击物体进行测量")
        self.camera_label.setScaledContents(False)
        self.camera_label.mousePressEvent = self.on_camera_click
        camera_layout.addWidget(self.camera_label)
        
        content_layout.addWidget(camera_widget)
        
        # 右侧：控制和状态面板
        right_panel = QWidget()
        right_panel.setFixedWidth(320)
        right_layout = QVBoxLayout(right_panel)
        right_layout.setSpacing(10)
        
        # 测量控制组
        measurement_group = QGroupBox("📍 测量控制")
        measurement_layout = QVBoxLayout(measurement_group)
        
        # 选择状态
        self.selection_status = QLabel("⚪ 未选择物体")
        self.selection_status.setStyleSheet("color: #666; font-weight: bold; padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
        measurement_layout.addWidget(self.selection_status)
        
        # 工作平面高度设置
        plane_layout = QHBoxLayout()
        plane_layout.addWidget(QLabel("工作平面Z(m):"))
        from PyQt5.QtWidgets import QDoubleSpinBox
        self.plane_z_spin = QDoubleSpinBox()
        self.plane_z_spin.setRange(-2.0, 2.0)
        self.plane_z_spin.setDecimals(4)
        self.plane_z_spin.setValue(0.0)
        self.plane_z_spin.setSingleStep(0.001)
        self.plane_z_spin.setMaximumWidth(120)
        plane_layout.addWidget(self.plane_z_spin)
        plane_layout.addStretch()
        measurement_layout.addLayout(plane_layout)

        # 记录测量点按钮
        self.record_point_btn = QPushButton("📍 记录测量点")
        self.record_point_btn.setEnabled(False)
        self.record_point_btn.setStyleSheet("""
            QPushButton {
                background-color: #4CAF50;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #45a049; }
            QPushButton:disabled { 
                background-color: #bbb; 
                color: #666; 
            }
        """)
        self.record_point_btn.clicked.connect(self.record_measurement_point)
        measurement_layout.addWidget(self.record_point_btn)
        
        # 计算误差按钮
        self.calculate_error_btn = QPushButton("📊 计算验证误差")
        self.calculate_error_btn.setEnabled(False)
        self.calculate_error_btn.setStyleSheet("""
            QPushButton {
                background-color: #9C27B0;
                color: white;
                font-weight: bold;
                padding: 12px;
                border-radius: 6px;
            }
            QPushButton:hover { background-color: #7B1FA2; }
            QPushButton:disabled { 
                background-color: #bbb; 
                color: #666; 
            }
        """)
        self.calculate_error_btn.clicked.connect(self.calculate_verification_error)
        measurement_layout.addWidget(self.calculate_error_btn)
        
        right_layout.addWidget(measurement_group)
        
        # 状态显示组
        status_group = QGroupBox("📊 实时状态")
        status_layout = QVBoxLayout(status_group)
        
        self.arm_status_label = QLabel("🦾 机械臂状态: 已连接, 6个关节")
        self.arm_status_label.setStyleSheet("color: #666; font-size: 11px; padding: 3px;")
        status_layout.addWidget(self.arm_status_label)
        
        self.camera_status_label = QLabel("📷 摄像头状态: 未启动")
        self.camera_status_label.setStyleSheet("color: #666; font-size: 11px; padding: 3px;")
        status_layout.addWidget(self.camera_status_label)
        
        self.progress_label = QLabel("📈 测量进度: 0/2")
        self.progress_label.setStyleSheet("color: #666; font-size: 11px; padding: 3px;")
        status_layout.addWidget(self.progress_label)
        
        right_layout.addWidget(status_group)
        right_layout.addStretch()
        
        content_layout.addWidget(right_panel)
        main_layout.addLayout(content_layout)
        
        # 底部：测量结果显示区域
        result_group = QGroupBox("📊 测量结果与误差分析")
        result_layout = QVBoxLayout(result_group)
        
        # 创建水平分割的结果显示
        results_h_layout = QHBoxLayout()
        
        # 测量信息
        self.measurement_info = QTextEdit()
        self.measurement_info.setMinimumHeight(120)
        self.measurement_info.setReadOnly(True)
        self.measurement_info.setFont(QFont("Consolas", 9))
        self.measurement_info.setStyleSheet("background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; padding: 5px;")
        self.measurement_info.setPlaceholderText("测量信息将在这里显示...")
        results_h_layout.addWidget(self.measurement_info)
        
        # 误差结果
        self.error_result = QTextEdit()
        self.error_result.setMinimumHeight(120)
        self.error_result.setReadOnly(True)
        self.error_result.setFont(QFont("Consolas", 9))
        self.error_result.setStyleSheet("background-color: #f9f9f9; border: 1px solid #ddd; border-radius: 4px; padding: 5px;")
        self.error_result.setPlaceholderText("误差分析将在这里显示...")
        results_h_layout.addWidget(self.error_result)
        
        result_layout.addLayout(results_h_layout)
        main_layout.addWidget(result_group)
        
        # 初始状态
        self.selected_pixel = None
        self.current_frame = None
        
        # 更新机械臂状态显示
        if self.motors:
            motor_count = len(self.motors)
            self.arm_status_label.setText(f"🦾 机械臂状态: 已连接 {motor_count} 个电机")
            self.arm_status_label.setStyleSheet("color: green; font-size: 11px; font-weight: bold;")
        else:
            self.arm_status_label.setText("🦾 机械臂状态: 未连接")
            self.arm_status_label.setStyleSheet("color: red; font-size: 11px; font-weight: bold;")
    

    
    def _is_y_board(self):
        """判断是否为Y板"""
        try:
            for motor in self.motors.values():
                # 检查是否有multi_motor_command方法
                if hasattr(motor, 'multi_motor_command'):
                    return True
            return False
        except Exception:
            return False
    
    def _build_single_command_for_y42(self, motor_id, func):
        """为Y42构建单个命令"""
        try:
            # 尝试使用ZDTCommandBuilder构建命令
            from Control_SDK.Control_Core.commands import ZDTCommandBuilder
            return ZDTCommandBuilder.build_single_command_bytes(motor_id, func)
        except Exception:
            # 回退到简单格式
            return [motor_id] + func
    
    def move_to_selected_position(self):
        """移动机械臂到选择的位置"""
        if not self.motors:
            QMessageBox.warning(self, "警告", "机械臂未连接！")
            return
        
        position_text = self.position_combo.currentText()
        
        # 定义预设位置
        positions = {
            "当前位置": None,  # 保持当前位置
            "初始位置[0,0,0,0,90,0]": [0, 0, 0, 0, 90, 0],
            "位置A[30,0,0,0,90,0]": [30, 0, 0, 0, 90, 0],
            "位置B[-30,0,0,0,90,0]": [-30, 0, 0, 0, 90, 0],
        }
        
        if position_text == "当前位置":
            self.measurement_info.append("💡 机械臂保持在当前位置")
            return
        
        target_angles = positions.get(position_text)
        if target_angles is None:
            QMessageBox.warning(self, "错误", "未知的位置选择！")
            return
        
        try:
            self.measurement_info.append(f"🚀 开始移动到: {position_text}")
            
            # 运动参数
            max_speed = 500
            acceleration = 200
            deceleration = 200
            is_absolute = True
            
            # 构建位置字典，只包含实际存在的电机
            positions_dict = {}
            selected_motors = []
            for i, angle in enumerate(target_angles):
                motor_id = i + 1
                if motor_id in self.motors:
                    positions_dict[motor_id] = angle
                    selected_motors.append((motor_id, self.motors[motor_id]))
            
            if not selected_motors:
                QMessageBox.warning(self, "错误", "没有找到可用的电机")
                return
            
            # 判断是否为Y板
            if self._is_y_board():
                # Y板：使用多电机命令一次性下发
                commands = []
                for motor_id, motor in selected_motors:
                    if motor_id in positions_dict:
                        input_position = positions_dict[motor_id]
                        actual_position = self.get_actual_angle(input_position, motor_id)
                        func = motor.command_builder.position_mode_trapezoid(
                            position=actual_position,
                            max_speed=max_speed,
                            acceleration=acceleration,
                            deceleration=deceleration,
                            is_absolute=is_absolute,
                            multi_sync=False
                        )
                        commands.append(self._build_single_command_for_y42(motor_id, func))
                
                if commands:
                    first_motor = selected_motors[0][1]
                    first_motor.multi_motor_command(commands, expected_ack_motor_id=1, wait_ack=False, mode='control')
                    self.measurement_info.append("✅ Y板多电机命令已下发")
                    
            else:
                # X板：多机同步标志 + 广播同步
                success_count = 0
                for motor_id, motor in selected_motors:
                    if motor_id in positions_dict:
                        try:
                            input_position = positions_dict[motor_id]
                            actual_position = self.get_actual_angle(input_position, motor_id)
                            
                            motor.control_actions.move_to_position_trapezoid(
                                position=actual_position,
                                max_speed=max_speed,
                                acceleration=acceleration,
                                deceleration=deceleration,
                                is_absolute=is_absolute,
                                multi_sync=True
                            )
                            success_count += 1
                        except Exception as motor_error:
                            print(f"电机 {motor_id} 设置失败: {motor_error}")
                            continue
                
                if success_count > 0:
                    # 发送同步运动命令
                    first_motor = selected_motors[0][1]
                    try:
                        interface_kwargs = getattr(first_motor, 'interface_kwargs', {})
                        broadcast_motor = first_motor.__class__(
                            motor_id=0,
                            interface_type=first_motor.interface_type,
                            shared_interface=True,
                            **interface_kwargs
                        )
                    except Exception:
                        broadcast_motor = first_motor.__class__(
                            motor_id=0,
                            interface_type=first_motor.interface_type,
                            shared_interface=True
                        )
                    
                    broadcast_motor.can_interface = first_motor.can_interface
                    broadcast_motor.control_actions.sync_motion()
                    self.measurement_info.append("✅ X板同步运动命令已发送")
                else:
                    QMessageBox.warning(self, "失败", "没有电机成功设置运动参数")
                    return
            
            self.measurement_info.append("⏳ 机械臂正在运动，请等待完成...")
            
        except Exception as e:
            error_msg = f"移动失败: {str(e)}"
            self.measurement_info.append(f"❌ {error_msg}")
            QMessageBox.critical(self, "错误", error_msg)
    
    def get_actual_angle(self, input_angle, motor_id):
        """根据减速比和方向计算实际电机角度"""
        ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id) if motor_id else 1.0
        direction = self.motor_config_manager.get_motor_direction(motor_id) if motor_id else 1
        return input_angle * ratio * direction
    
    def start_camera_verification(self):
        """启动摄像头进行验证"""
        try:
            if self.camera_worker is not None:
                self.stop_camera_verification()
            
            self.camera_worker = CameraWorker(camera_index=self.camera_index)
            self.camera_worker.frame_ready.connect(self.update_camera_frame)
            self.camera_worker.error.connect(self.on_camera_error)
            self.camera_worker.start_camera()
            
            self.start_camera_btn.setText("⏹️ 停止摄像头")
            self.start_camera_btn.clicked.disconnect()
            self.start_camera_btn.clicked.connect(self.stop_camera_verification)
            
            self.measurement_info.append("📷 摄像头已启动，请在图像中点击选择物体...")
            self.camera_status_label.setText("📷 摄像头状态: 启动中...")
            self.camera_status_label.setStyleSheet("color: orange; font-size: 11px; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动摄像头失败:\n{str(e)}")
            self.camera_status_label.setText("📷 摄像头状态: 启动失败")
            self.camera_status_label.setStyleSheet("color: red; font-size: 11px; font-weight: bold;")
    
    def stop_camera_verification(self):
        """停止摄像头验证"""
        try:
            if self.camera_worker is not None:
                self.camera_worker.stop_camera()
                self.camera_worker = None
            
            self.start_camera_btn.setText("📷 启动摄像头")
            self.start_camera_btn.clicked.disconnect()
            self.start_camera_btn.clicked.connect(self.start_camera_verification)
            
            self.camera_label.clear()
            self.camera_label.setText("📷 摄像头已停止\n点击启动按钮重新启动")
            
            self.camera_status_label.setText("📷 摄像头状态: 已停止")
            self.camera_status_label.setStyleSheet("color: gray; font-size: 11px;")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"停止摄像头失败:\n{str(e)}")
            self.camera_status_label.setText("📷 摄像头状态: 停止失败")
            self.camera_status_label.setStyleSheet("color: red; font-size: 11px; font-weight: bold;")
    
    @pyqtSlot(np.ndarray)
    def update_camera_frame(self, frame):
        """更新摄像头画面"""
        try:
            self.current_frame = frame.copy()
            
            # 如果有选中的像素点，在图像上画出标记
            display_frame = frame.copy()
            if self.selected_pixel is not None:
                px, py = self.selected_pixel
                cv2.circle(display_frame, (int(px), int(py)), 5, (0, 255, 0), 2)
                cv2.circle(display_frame, (int(px), int(py)), 10, (0, 255, 0), 1)
            
            # 直接缩放到640*480
            resized_frame = cv2.resize(display_frame, (640, 480))
            
            # 转换为Qt格式并显示
            rgb_frame = cv2.cvtColor(resized_frame, cv2.COLOR_BGR2RGB)
            height, width, channel = rgb_frame.shape
            bytes_per_line = 3 * width
            q_image = QImage(rgb_frame.data, width, height, bytes_per_line, QImage.Format_RGB888)
            pixmap = QPixmap.fromImage(q_image)
            
            # 直接设置固定尺寸的图像
            self.camera_label.setPixmap(pixmap)
            
            # 更新摄像头状态
            self.camera_status_label.setText("📷 摄像头状态: 正常运行")
            self.camera_status_label.setStyleSheet("color: green; font-size: 11px; font-weight: bold;")
                
        except Exception as e:
            self.measurement_info.append(f"❌ 摄像头画面更新失败: {str(e)}")
            self.camera_status_label.setText("📷 摄像头状态: 显示异常")
            self.camera_status_label.setStyleSheet("color: red; font-size: 11px; font-weight: bold;")
    
    @pyqtSlot(str)
    def on_camera_error(self, error_message):
        """处理摄像头错误"""
        self.measurement_info.append(f"❌ 摄像头错误: {error_message}")
        self.stop_camera_verification()
    
    def on_camera_click(self, event):
        """处理摄像头画面点击事件"""
        if self.current_frame is None:
            return
        
        # 获取点击位置（相对于固定尺寸640*480的显示标签）
        click_x = event.pos().x()
        click_y = event.pos().y()
        
        # 计算在原始图像中的实际像素坐标
        frame_height, frame_width = self.current_frame.shape[:2]
        
        # 计算缩放比例（从显示的640*480到原始图像尺寸）
        scale_x = frame_width / 640.0
        scale_y = frame_height / 480.0
        
        # 计算实际的像素坐标
        actual_x = int(click_x * scale_x)
        actual_y = int(click_y * scale_y)
        
        # 限制在原始图像范围内
        actual_x = max(0, min(actual_x, frame_width - 1))
        actual_y = max(0, min(actual_y, frame_height - 1))
        
        self.selected_pixel = (actual_x, actual_y)
        self.measurement_info.append(f"✅ 已选择像素点: ({actual_x}, {actual_y})")
        
        # 更新选择状态
        self.selection_status.setText(f"🎯 已选择: ({actual_x}, {actual_y})")
        self.selection_status.setStyleSheet("color: green; font-weight: bold; padding: 5px; border: 1px solid #4CAF50; border-radius: 3px;")
        
        # 启用记录按钮
        if len(self.point_measurements) < 2:
            self.record_point_btn.setEnabled(True)
    
    def pixel_to_world_coordinate(self, pixel_x, pixel_y, plane_z_m: float = 0.0):
        """将像素坐标转换为世界坐标
        使用射线与工作平面(Z=plane_z_m, 单位米)相交的方式估计深度，避免固定深度带来的系统性误差。
        """
        try:
            # 获取当前机械臂位置
            current_joint_angles = []
            for j in range(6):
                motor_id = j + 1
                if motor_id in self.motors:
                    try:
                        motor = self.motors[motor_id]
                        motor_position = motor.read_parameters.get_position()
                        
                        # 考虑减速比和方向
                        ratio = self.motor_config_manager.get_motor_reducer_ratio(motor_id)
                        direction = self.motor_config_manager.get_motor_direction(motor_id)
                        output_position = (motor_position * direction) / ratio
                        
                        current_joint_angles.append(output_position)
                    except Exception as e:
                        self.measurement_info.append(f"⚠️ 读取电机{motor_id}角度失败: {str(e)}")
                        return None
                else:
                    self.measurement_info.append(f"❌ 电机{motor_id}未连接")
                    return None
            
            # 计算当前末端执行器位姿
            end_pose = self.kinematics.get_end_effector_pose(current_joint_angles)
            position = end_pose['position']
            euler_angles = end_pose['euler_angles']
            
            # 构造末端执行器变换矩阵
            end_pose_matrix = np.eye(4)
            end_pose_matrix[:3, 3] = position
            
            # 将欧拉角转换为旋转矩阵 (ZYX顺序)
            rx, ry, rz = np.deg2rad(euler_angles[2]), np.deg2rad(euler_angles[1]), np.deg2rad(euler_angles[0])
            
            # 旋转矩阵计算
            Rx = np.array([[1, 0, 0], [0, np.cos(rx), -np.sin(rx)], [0, np.sin(rx), np.cos(rx)]])
            Ry = np.array([[np.cos(ry), 0, np.sin(ry)], [0, 1, 0], [-np.sin(ry), 0, np.cos(ry)]])
            Rz = np.array([[np.cos(rz), -np.sin(rz), 0], [np.sin(rz), np.cos(rz), 0], [0, 0, 1]])
            
            end_pose_matrix[:3, :3] = Rz @ Ry @ Rx
            
            # 使用手眼标定矩阵
            RT_camera2end = np.array(self.calibration_result['RT_camera2end'])
            RT_camera2end[0:3, 3] = RT_camera2end[0:3, 3] * 1000.0   #转成毫米

            # 像素坐标归一化成相机坐标系中的单位方向向量（Z=1）
            camera_matrix = np.array(self.camera_params['camera_matrix'], dtype=np.float64)
            fx, fy = camera_matrix[0, 0], camera_matrix[1, 1]
            cx, cy = camera_matrix[0, 2], camera_matrix[1, 2]

            # 像素去畸变 → 归一化方向
            u2, v2 = float(pixel_x), float(pixel_y)
            try:
                model = str(self.camera_params.get('model', 'pinhole')).lower()
                # 解析畸变系数两种格式
                D = self.camera_params.get('camera_distortion', None)
                dist_coeffs = None
                if D is not None:
                    if isinstance(D, list):
                        if len(D) > 0 and isinstance(D[0], list):
                            if len(D[0]) > 1:
                                dist_coeffs = np.array(D[0], dtype=np.float64)
                            else:
                                dist_coeffs = np.array([row[0] for row in D if len(row) > 0], dtype=np.float64)
                        else:
                            dist_coeffs = np.array(D, dtype=np.float64)
                if dist_coeffs is not None:
                    pts = np.array([[[pixel_x, pixel_y]]], dtype=np.float64)
                    if model == 'fisheye':
                        und = cv2.fisheye.undistortPoints(pts, camera_matrix, dist_coeffs, R=np.eye(3), P=camera_matrix)
                    else:
                        und = cv2.undistortPoints(pts, camera_matrix, dist_coeffs, P=camera_matrix)
                    u2, v2 = float(und[0, 0, 0]), float(und[0, 0, 1])
            except Exception:
                pass

            dir_cam = np.array([(u2 - cx) / fx, (v2 - cy) / fy, 1.0, 0.0], dtype=np.float64)

            # 将射线方向从相机坐标变换到末端坐标，再到世界坐标
            R_cam2end = np.eye(4)
            R_cam2end[:3, :3] = RT_camera2end[:3, :3]
            # 平移在方向向量上不生效
            dir_end = (R_cam2end @ dir_cam)[:3]

            # 相机在末端坐标系下的位置（mm）
            cam_in_end = RT_camera2end[:3, 3]

            # 转到世界坐标
            R_end2world = np.eye(4)
            R_end2world[:3, :3] = end_pose_matrix[:3, :3]
            dir_world = (R_end2world @ np.append(dir_end, 0.0))[:3]
            cam_in_world = (end_pose_matrix @ np.append(cam_in_end, 1.0))[:3]

            # 与平面 Z=plane_z_m 求交点：cam + t*dir，解 t = (plane_z - cam_z)/dir_z
            if abs(dir_world[2]) < 1e-6:
                return None
            t = (plane_z_m - cam_in_world[2]) / dir_world[2]
            world_coords = cam_in_world + t * dir_world
            
            return {
                'world_coords': world_coords,
                'joint_angles': current_joint_angles,
                'end_pose': position,
                'pixel_coords': (pixel_x, pixel_y),
                'camera_coords': None
            }
            
        except Exception as e:
            self.measurement_info.append(f"❌ 坐标转换失败: {str(e)}")
            return None
    
    def record_measurement_point(self):
        """记录当前测量点"""
        if self.selected_pixel is None:
            QMessageBox.warning(self, "警告", "请先在图像中点击选择物体位置！")
            return
        
        pixel_x, pixel_y = self.selected_pixel
        
        # 转换为世界坐标（米）
        plane_z = 0.0
        try:
            if hasattr(self, 'plane_z_spin') and self.plane_z_spin is not None:
                plane_z = float(self.plane_z_spin.value())
        except Exception:
            plane_z = 0.0
        result = self.pixel_to_world_coordinate(pixel_x, pixel_y, plane_z_m=plane_z)
        if result is None:
            QMessageBox.warning(self, "错误", "坐标转换失败！")
            return
        
        # 计算当前是第几个测量点
        point_index = len(self.point_measurements) + 1
        
        # 保存测量数据
        measurement_data = {
            'point_index': point_index,
            'world_coords': result['world_coords'],
            'joint_angles': result['joint_angles'],
            'end_pose': result['end_pose'],
            'pixel_coords': result['pixel_coords'],
            'camera_coords': result['camera_coords']
        }
        
        self.point_measurements.append(measurement_data)
        
        # 显示测量结果
        world_coords = result['world_coords']
        self.measurement_info.append(f"\n📍 测量点 {point_index} 记录完成:")
        self.measurement_info.append(f"   像素坐标: ({pixel_x}, {pixel_y})")
        self.measurement_info.append(f"   世界坐标: ({world_coords[0]:.2f}, {world_coords[1]:.2f}, {world_coords[2]:.2f}) mm")
        self.measurement_info.append(f"   关节角度: {[f'{a:.2f}°' for a in result['joint_angles']]}")
        
        # 更新按钮状态和进度显示
        progress = len(self.point_measurements)
        self.progress_label.setText(f"📈 测量进度: {progress}/2")
        
        if progress == 1:
            self.record_point_btn.setText("📍 记录第2个测量点")
            self.measurement_info.append("\n💡 请使用上方控制器移动机械臂到另一个能看到同一物体的位置，然后点击同一物体记录第2个测量点")
            self.progress_label.setStyleSheet("color: orange; font-size: 11px; font-weight: bold;")
        elif progress >= 2:
            self.record_point_btn.setEnabled(False)
            self.record_point_btn.setText("✅ 测量完成")
            self.calculate_error_btn.setEnabled(True)
            self.measurement_info.append("\n✅ 两个测量点都已记录，可以计算误差了")
            self.progress_label.setText("📈 测量进度: 2/2 ✅")
            self.progress_label.setStyleSheet("color: green; font-size: 11px; font-weight: bold;")
        
        # 清除选择状态，准备下一次选择
        self.selected_pixel = None
        self.selection_status.setText("⚪ 未选择物体")
        self.selection_status.setStyleSheet("color: #666; font-weight: bold; padding: 8px; border: 1px solid #ddd; border-radius: 4px; background-color: #f9f9f9;")
    
    def calculate_verification_error(self):
        """计算验证误差"""
        if len(self.point_measurements) < 2:
            QMessageBox.warning(self, "警告", "需要至少2个测量点才能计算误差！")
            return
        
        try:
            point1 = self.point_measurements[0]
            point2 = self.point_measurements[1]
            
            world_coords1 = np.array(point1['world_coords'])
            world_coords2 = np.array(point2['world_coords'])
            
            # 计算3D距离误差
            distance_error = np.linalg.norm(world_coords2 - world_coords1)
            
            # 计算各轴误差
            x_error = abs(world_coords2[0] - world_coords1[0])
            y_error = abs(world_coords2[1] - world_coords1[1])
            z_error = abs(world_coords2[2] - world_coords1[2])
            
            # 显示详细误差结果
            error_text = f"""
🔍 手眼标定精度验证结果:
==========================================

测量点1 世界坐标: ({world_coords1[0]:.3f}, {world_coords1[1]:.3f}, {world_coords1[2]:.3f}) mm
测量点2 世界坐标: ({world_coords2[0]:.3f}, {world_coords2[1]:.3f}, {world_coords2[2]:.3f}) mm

📊 误差分析:
- X轴误差: {x_error:.3f} mm
- Y轴误差: {y_error:.3f} mm  
- Z轴误差: {z_error:.3f} mm
- 总3D距离误差: {distance_error:.3f} mm

📈 精度评估:
"""
            
            if distance_error < 5.0:
                error_text += "✅ 优秀 (< 5mm) - 标定精度很高"
            elif distance_error < 10.0:
                error_text += "✅ 良好 (5-10mm) - 标定精度较好"
            elif distance_error < 20.0:
                error_text += "⚠️ 一般 (10-20mm) - 标定精度一般"
            else:
                error_text += "❌ 较差 (> 20mm) - 建议重新标定"
            
            error_text += f"\n\n💡 说明: 该误差是同一物体在两个不同视角下的世界坐标差异"
            
            self.error_result.setText(error_text)
            
            # 保存验证结果
            verification_result = {
                'point1_world': world_coords1.tolist(),
                'point2_world': world_coords2.tolist(),
                'distance_error': float(distance_error),
                'x_error': float(x_error),
                'y_error': float(y_error),
                'z_error': float(z_error),
                'measurements': self.point_measurements
            }
            
            self.verification_result = verification_result
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"计算误差失败:\n{str(e)}")
    



