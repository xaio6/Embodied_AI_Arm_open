# -*- coding: utf-8 -*-
"""
相机标定工具组件
支持单目相机标定和双目相机标定，包含照片采集功能
支持标准针孔模型和鱼眼模型
"""

import sys
import os
import time
import cv2
import numpy as np
import glob
import json
from PyQt5.QtWidgets import (QWidget, QHBoxLayout, QVBoxLayout, QGroupBox,
                             QPushButton, QLabel, QComboBox, QSpinBox, QDoubleSpinBox,
                             QLineEdit, QTextEdit, QTabWidget, QFormLayout,
                             QMessageBox, QTableWidget, QTableWidgetItem,
                             QCheckBox, QProgressBar, QSlider, QGridLayout,
                             QScrollArea, QFileDialog, QDialog, QSpacerItem,
                             QSizePolicy, QFrame, QHeaderView)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QThread, pyqtSlot
from PyQt5.QtGui import QFont, QPalette, QColor, QPixmap, QImage
import threading
from functools import partial

# 添加项目根目录到路径
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))
sys.path.insert(0, project_root)

# 添加Control_SDK目录到路径
control_sdk_dir = os.path.join(project_root, "Control_SDK")
sys.path.insert(0, control_sdk_dir)

try:
    from core.arm_core.One_Camera_Calibration import CameraCalibrator
    from core.arm_core.Two_Camera_Calibration import Two_Camera_Clibration
except ImportError:
    CameraCalibrator = None
    Two_Camera_Clibration = None

class CameraPreviewWorker(QThread):
    """相机预览工作线程"""
    
    frame_ready = pyqtSignal(np.ndarray)
    error = pyqtSignal(str)
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera_index = camera_index
        self._is_running = False
        self.cap = None
    
    def start_preview(self):
        """启动预览"""
        self._is_running = True
        self.start()
    
    def stop_preview(self):
        """停止预览"""
        print("正在停止预览线程...")
        self._is_running = False
        
        # 释放摄像头资源
        if hasattr(self, 'cap') and self.cap:
            try:
                self.cap.release()
                print("摄像头资源已释放")
            except Exception as e:
                print(f"释放摄像头资源时出错: {str(e)}")
        
        # 关闭OpenCV窗口
        try:
            cv2.destroyAllWindows()
        except:
            pass
        
        # 退出线程并等待
        try:
            self.quit()
            if not self.wait(2000):  # 等待2秒
                print("预览线程等待超时，强制终止")
                self.terminate()
                self.wait(1000)  # 再等待1秒
        except Exception as e:
            print(f"停止预览线程时出错: {str(e)}")
        
        print("预览线程停止完成")
    
    def run(self):
        """运行预览线程"""
        try:
            self.cap = cv2.VideoCapture(self.camera_index)
            if not self.cap.isOpened():
                self.error.emit(f"无法打开摄像头 {self.camera_index}")
                return
            
            # 设置摄像头参数（针对双目摄像头）
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
            
            # 获取实际设置的分辨率
            actual_width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            actual_height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            print(f"摄像头实际分辨率: {actual_width} x {actual_height}")
            
            consecutive_failures = 0  # 连续失败计数
            max_failures = 10  # 最大连续失败次数
            
            while self._is_running:
                # 在每次循环开始时检查停止标志
                if not self._is_running:
                    break
                    
                ret, frame = self.cap.read()
                if ret:
                    # 重置失败计数
                    consecutive_failures = 0
                    
                    # 输出实际画面尺寸用于调试
                    if hasattr(self, '_first_frame') is False:
                        print(f"实际获取的画面尺寸: {frame.shape[1]} x {frame.shape[0]}")
                        self._first_frame = True
                    
                    # 在发送信号前再次检查停止标志
                    if self._is_running:
                        self.frame_ready.emit(frame)
                else:
                    consecutive_failures += 1
                    if consecutive_failures >= max_failures:
                        if self._is_running:  # 只在仍在运行时发送错误信号
                            self.error.emit("摄像头连续读取失败，预览停止")
                        break
                    else:
                        # 偶发失败，继续尝试
                        if self._is_running:  # 只在仍在运行时打印错误
                            print(f"摄像头读取失败 ({consecutive_failures}/{max_failures})")
                
                # 使用更短的睡眠时间，更频繁地检查停止标志
                for i in range(33):
                    if not self._is_running:
                        break
                    self.msleep(1)  # 每次睡眠1ms，总共33ms
                
        except Exception as e:
            if self._is_running:  # 只在仍在运行时发送错误信号
                self.error.emit(f"预览线程错误: {str(e)}")
        finally:
            # 确保摄像头资源被释放
            if hasattr(self, 'cap') and self.cap:
                try:
                    self.cap.release()
                except:
                    pass
            print("摄像头预览线程已结束")

class CameraCalibrationWidget(QDialog):
    """相机标定工具组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("相机标定工具")
        self.setWindowFlags(Qt.Window)  # 使其成为独立窗口
        
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
        
        # 调整窗口大小，适应更多屏幕尺寸
        self.resize(1300, 950)
        # 设置最小尺寸
        self.setMinimumSize(800, 500)
        
        # 标定参数
        self.checkerboard_width = 9
        self.checkerboard_height = 6
        self.square_size = 22.0  # mm
        
        # 默认保存路径
        self.mono_save_path = "data/one_calibration_image"
        self.stereo_left_path = "data/two_calibration_image/left"
        self.stereo_right_path = "data/two_calibration_image/right"
        
        # 预览相关
        self.preview_worker = None
        self.preview_left_label = None
        self.preview_right_label = None
        
        # 标定数据
        self.calibration_results = {}
        self.captured_images = []  # 单目或双目右相机图片
        self.captured_left_images = []  # 双目左相机图片
        self.is_stereo_mode = False  # 标定模式标志
        
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        layout = QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)  # 减少间距
        
        # 创建相机选择区域
        self.create_camera_selection(layout)
        
        # 创建标签页
        self.create_tabs(layout)
        
        # 初始化标定模式提示
        self.on_calibration_mode_changed("单目标定")
    
    def create_camera_selection(self, parent_layout):
        """创建相机选择区域"""
        group = QGroupBox("相机选择")
        layout = QHBoxLayout(group)
        
        layout.addWidget(QLabel("选择相机:"))
        
        self.camera_combo = QComboBox()
        self.camera_combo.addItems(["相机 0", "相机 1", "相机 2"])
        layout.addWidget(self.camera_combo)
        
        # 状态指示器
        self.camera_status = QLabel("未连接")
        self.camera_status.setStyleSheet("color: red; font-weight: bold;")
        layout.addWidget(self.camera_status)
        
        # 预览按钮
        self.preview_btn = QPushButton("开始预览")
        self.preview_btn.clicked.connect(self.toggle_preview)
        layout.addWidget(self.preview_btn)
        
        layout.addStretch()
        parent_layout.addWidget(group)
    
    def create_tabs(self, parent_layout):
        """创建标签页"""
        self.tab_widget = QTabWidget()
        
        # 照片采集标签页
        self.capture_tab = self.create_capture_tab()
        self.tab_widget.addTab(self.capture_tab, "照片采集")
        
        # 单目标定标签页
        self.mono_calibration_tab = self.create_mono_calibration_tab()
        self.tab_widget.addTab(self.mono_calibration_tab, "单目标定")
        
        # 双目标定标签页
        self.stereo_calibration_tab = self.create_stereo_calibration_tab()
        self.tab_widget.addTab(self.stereo_calibration_tab, "双目标定")
        
        parent_layout.addWidget(self.tab_widget)
    
    def create_capture_tab(self):
        """创建照片采集标签页"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容widget
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 采集模式选择组
        mode_group = QGroupBox("采集模式选择")
        mode_layout = QFormLayout(mode_group)
        
        self.calibration_mode_combo = QComboBox()
        self.calibration_mode_combo.addItems(["单目标定", "双目标定"])
        self.calibration_mode_combo.currentTextChanged.connect(self.on_calibration_mode_changed)
        mode_layout.addRow("标定模式:", self.calibration_mode_combo)
        
        layout.addWidget(mode_group)
        
        # 预览显示组
        preview_group = QGroupBox("相机预览")
        preview_layout = QVBoxLayout(preview_group)
        
        # 创建水平布局来放置左右两个预览标签
        preview_h_layout = QHBoxLayout()
        
        # 左相机预览 - 增大尺寸
        self.preview_left_label = QLabel("左相机画面")
        self.preview_left_label.setMinimumSize(400, 300)  # 增大预览尺寸
        self.preview_left_label.setMaximumSize(400, 300)
        self.preview_left_label.setAlignment(Qt.AlignCenter)
        self.preview_left_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_left_label.setScaledContents(False)  # 禁用自动缩放内容
        preview_h_layout.addWidget(self.preview_left_label)
        
        # 右相机预览 - 增大尺寸
        self.preview_right_label = QLabel("右相机画面")
        self.preview_right_label.setMinimumSize(400, 300)  # 增大预览尺寸
        self.preview_right_label.setMaximumSize(400, 300)
        self.preview_right_label.setAlignment(Qt.AlignCenter)
        self.preview_right_label.setStyleSheet("border: 1px solid gray; background-color: #f0f0f0;")
        self.preview_right_label.setScaledContents(False)  # 禁用自动缩放内容
        preview_h_layout.addWidget(self.preview_right_label)
        
        preview_layout.addLayout(preview_h_layout)
        
        # 添加提示标签
        self.preview_info_label = QLabel("请点击'开始预览'查看相机画面。双目模式显示左右两个画面，单目模式只使用右侧画面。")
        self.preview_info_label.setWordWrap(True)
        self.preview_info_label.setStyleSheet("color: #666; font-size: 10px;")
        preview_layout.addWidget(self.preview_info_label)
        
        layout.addWidget(preview_group)
        
        # 照片查看和采集控制组合区域
        photos_control_group = QGroupBox("照片管理")
        photos_control_layout = QVBoxLayout(photos_control_group)
        
        # 照片采集控制区域（移到这里）
        capture_control_layout = QHBoxLayout()
        
        # 拍摄按钮和状态
        self.capture_btn = QPushButton("拍摄照片")
        self.capture_btn.setProperty("class", "success")
        self.capture_btn.clicked.connect(self.capture_image)
        capture_control_layout.addWidget(self.capture_btn)
        
        self.capture_status_label = QLabel("准备采集")
        capture_control_layout.addWidget(self.capture_status_label)
        
        # 采集统计
        self.capture_count_label = QLabel("已采集: 0 张")
        self.capture_count_label.setStyleSheet("font-weight: bold; color: #666;")
        capture_control_layout.addWidget(self.capture_count_label)
        
        capture_control_layout.addStretch()
        photos_control_layout.addLayout(capture_control_layout)
        
        # 照片列表和预览的水平布局
        photos_h_layout = QHBoxLayout()
        
        # 左侧：照片列表区域
        photos_list_container = QVBoxLayout()
        
        # 照片列表标题
        self.photos_list_label = QLabel("已拍摄照片:")
        photos_list_container.addWidget(self.photos_list_label)
        
        # 照片列表和按钮的水平布局
        photos_list_with_buttons = QHBoxLayout()
        
        # 照片列表（扩大尺寸）
        self.photos_list = QWidget()
        self.photos_list.setMaximumWidth(280)  # 增加宽度
        self.photos_list.setStyleSheet("border: 1px solid gray;")
        
        # 初始化照片列表布局
        initial_layout = QVBoxLayout(self.photos_list)
        initial_layout.addStretch()
        
        self.photos_scroll_area = QScrollArea()
        self.photos_scroll_area.setWidget(self.photos_list)
        self.photos_scroll_area.setWidgetResizable(True)
        self.photos_scroll_area.setMaximumWidth(300)  # 增加宽度
        self.photos_scroll_area.setMinimumHeight(250)  # 增加高度
        
        photos_list_with_buttons.addWidget(self.photos_scroll_area)
        
        # 按钮垂直布局，紧贴照片列表框
        buttons_layout = QVBoxLayout()
        
        # 删除按钮放在照片列表框右侧
        self.delete_selected_btn = QPushButton("删除选中")
        self.delete_selected_btn.setProperty("class", "warning")
        self.delete_selected_btn.clicked.connect(self.delete_selected_photos)
        self.delete_selected_btn.setMaximumWidth(80)
        self.delete_selected_btn.setMaximumHeight(30)
        buttons_layout.addWidget(self.delete_selected_btn)
        
        self.clear_all_btn = QPushButton("清空")
        self.clear_all_btn.setProperty("class", "danger")
        self.clear_all_btn.clicked.connect(self.clear_all_photos)
        self.clear_all_btn.setMaximumWidth(80)
        self.clear_all_btn.setMaximumHeight(30)
        buttons_layout.addWidget(self.clear_all_btn)
        
        # 添加伸缩空间，让按钮靠顶部
        buttons_layout.addStretch()
        
        photos_list_with_buttons.addLayout(buttons_layout)
        
        photos_list_container.addLayout(photos_list_with_buttons)
        
        photos_h_layout.addLayout(photos_list_container)
        
        # 右侧：照片预览
        preview_layout_v = QVBoxLayout()
        preview_layout_v.addWidget(QLabel("照片预览:"))
        
        self.photo_preview_label = QLabel("选择照片查看")
        self.photo_preview_label.setMinimumSize(350, 250)  # 调整预览尺寸与照片列表平衡
        self.photo_preview_label.setMaximumSize(350, 250)
        self.photo_preview_label.setAlignment(Qt.AlignCenter)
        self.photo_preview_label.setStyleSheet("border: 1px solid gray; background-color: #f8f8f8;")
        self.photo_preview_label.setScaledContents(False)  # 禁用自动缩放内容
        preview_layout_v.addWidget(self.photo_preview_label)
        
        photos_h_layout.addLayout(preview_layout_v)
        
        photos_control_layout.addLayout(photos_h_layout)
        layout.addWidget(photos_control_group)
        
        # 初始化照片选择相关
        self.selected_photo_indices = []
        self.photo_checkboxes = []
        
        # 将内容widget添加到滚动区域
        scroll_area.setWidget(widget)
        
        return scroll_area
    
    def create_mono_calibration_tab(self):
        """创建单目标定标签页"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容widget
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 单目标定参数设置组
        mono_params_group = QGroupBox("单目标定参数设置")
        mono_params_layout = QFormLayout(mono_params_group)
        
        # 相机模型选择
        self.mono_model_combo = QComboBox()
        self.mono_model_combo.addItems(["标准针孔模型 (pinhole)", "鱼眼模型 (fisheye)"])
        self.mono_model_combo.setCurrentIndex(0)  # 默认标准针孔模型
        self.mono_model_combo.setToolTip("选择相机模型类型：\n- 针孔模型：适用于标准相机\n- 鱼眼模型：适用于广角相机(105°等)\n\n⚠️ 重要：必须与实际相机类型一致")
        mono_params_layout.addRow("相机模型:", self.mono_model_combo)
        
        # 模型选择提示
        model_info_label = QLabel("📝 提示：相机模型选择会直接影响标定精度，请根据实际相机类型选择")
        model_info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px; background-color: #f0f8ff; border-left: 3px solid #007ACC;")
        model_info_label.setWordWrap(True)
        mono_params_layout.addRow("", model_info_label)
        
        self.mono_width_spinbox = QSpinBox()
        self.mono_width_spinbox.setRange(3, 20)
        self.mono_width_spinbox.setValue(self.checkerboard_width)
        mono_params_layout.addRow("棋盘格宽度(内角点):", self.mono_width_spinbox)
        
        self.mono_height_spinbox = QSpinBox()
        self.mono_height_spinbox.setRange(3, 20)
        self.mono_height_spinbox.setValue(self.checkerboard_height)
        mono_params_layout.addRow("棋盘格高度(内角点):", self.mono_height_spinbox)
        
        self.mono_square_size_spinbox = QDoubleSpinBox()
        self.mono_square_size_spinbox.setRange(1.0, 100.0)
        self.mono_square_size_spinbox.setValue(self.square_size)
        self.mono_square_size_spinbox.setSuffix(" mm")
        mono_params_layout.addRow("方格尺寸:", self.mono_square_size_spinbox)
        
        layout.addWidget(mono_params_group)
        
        # 参数应用按钮
        mono_apply_layout = QHBoxLayout()
        self.mono_apply_btn = QPushButton("应用参数设置")
        self.mono_apply_btn.setProperty("class", "primary")
        self.mono_apply_btn.clicked.connect(self.apply_mono_settings)
        mono_apply_layout.addWidget(self.mono_apply_btn)
        
        self.mono_reset_btn = QPushButton("重置为默认值")
        self.mono_reset_btn.clicked.connect(self.reset_mono_settings)
        mono_apply_layout.addWidget(self.mono_reset_btn)
        
        mono_apply_layout.addStretch()
        layout.addLayout(mono_apply_layout)
        
        # 单目标定控制组
        mono_group = QGroupBox("单目相机标定")
        mono_layout = QGridLayout(mono_group)
        
        self.mono_calibrate_btn = QPushButton("开始单目标定")
        self.mono_calibrate_btn.setProperty("class", "primary")
        self.mono_calibrate_btn.clicked.connect(self.run_mono_calibration)
        mono_layout.addWidget(self.mono_calibrate_btn, 0, 0)
        
        self.mono_save_btn = QPushButton("保存标定结果")
        self.mono_save_btn.clicked.connect(self.save_mono_results)
        mono_layout.addWidget(self.mono_save_btn, 0, 1)
        
        # 标定进度
        self.mono_progress = QProgressBar()
        mono_layout.addWidget(self.mono_progress, 1, 0, 1, 2)  # 调整colspan为2
        
        # 标定状态
        self.mono_status_label = QLabel("等待开始标定")
        mono_layout.addWidget(self.mono_status_label, 2, 0, 1, 2)  # 调整colspan为2
        
        layout.addWidget(mono_group)
        
        # 标定结果显示组
        results_group = QGroupBox("标定结果")
        results_layout = QVBoxLayout(results_group)
        
        self.mono_results_text = QTextEdit()
        self.mono_results_text.setMaximumHeight(200)  # 减小结果显示区域高度
        self.mono_results_text.setReadOnly(True)
        results_layout.addWidget(self.mono_results_text)
        
        layout.addWidget(results_group)
        
        # 将内容widget添加到滚动区域
        scroll_area.setWidget(widget)
        
        return scroll_area
    
    def create_stereo_calibration_tab(self):
        """创建双目标定标签页"""
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 创建内容widget
        widget = QWidget()
        layout = QVBoxLayout(widget)
        
        # 双目标定参数设置组
        stereo_params_group = QGroupBox("双目标定参数设置")
        stereo_params_layout = QFormLayout(stereo_params_group)
        
        # 相机模型选择
        self.stereo_model_combo = QComboBox()
        self.stereo_model_combo.addItems(["标准针孔模型 (pinhole)", "鱼眼模型 (fisheye)"])
        self.stereo_model_combo.setCurrentIndex(0)  # 默认标准针孔模型
        self.stereo_model_combo.setToolTip("选择相机模型类型：\n- 针孔模型：适用于标准相机\n- 鱼眼模型：适用于广角相机(105°等)\n\n⚠️ 重要：必须与实际相机类型一致")
        stereo_params_layout.addRow("相机模型:", self.stereo_model_combo)
        
        # 模型选择提示
        stereo_model_info_label = QLabel("📝 提示：相机模型选择会直接影响标定精度，请根据实际相机类型选择")
        stereo_model_info_label.setStyleSheet("color: #666; font-size: 10px; padding: 5px; background-color: #f0f8ff; border-left: 3px solid #007ACC;")
        stereo_model_info_label.setWordWrap(True)
        stereo_params_layout.addRow("", stereo_model_info_label)
        
        self.stereo_width_spinbox = QSpinBox()
        self.stereo_width_spinbox.setRange(3, 20)
        self.stereo_width_spinbox.setValue(self.checkerboard_width)
        stereo_params_layout.addRow("棋盘格宽度(内角点):", self.stereo_width_spinbox)
        
        self.stereo_height_spinbox = QSpinBox()
        self.stereo_height_spinbox.setRange(3, 20)
        self.stereo_height_spinbox.setValue(self.checkerboard_height)
        stereo_params_layout.addRow("棋盘格高度(内角点):", self.stereo_height_spinbox)
        
        self.stereo_square_size_spinbox = QDoubleSpinBox()
        self.stereo_square_size_spinbox.setRange(1.0, 100.0)
        self.stereo_square_size_spinbox.setValue(self.square_size)
        self.stereo_square_size_spinbox.setSuffix(" mm")
        stereo_params_layout.addRow("方格尺寸:", self.stereo_square_size_spinbox)
        
        layout.addWidget(stereo_params_group)
        
        # 参数应用按钮
        stereo_apply_layout = QHBoxLayout()
        self.stereo_apply_btn = QPushButton("应用参数设置")
        self.stereo_apply_btn.setProperty("class", "primary")
        self.stereo_apply_btn.clicked.connect(self.apply_stereo_settings)
        stereo_apply_layout.addWidget(self.stereo_apply_btn)
        
        self.stereo_reset_btn = QPushButton("重置为默认值")
        self.stereo_reset_btn.clicked.connect(self.reset_stereo_settings)
        stereo_apply_layout.addWidget(self.stereo_reset_btn)
        
        stereo_apply_layout.addStretch()
        layout.addLayout(stereo_apply_layout)
        
        # 双目相机标定控制组
        stereo_group = QGroupBox("双目相机标定")
        stereo_layout = QGridLayout(stereo_group)
        
        self.stereo_calibrate_btn = QPushButton("开始双目标定")
        self.stereo_calibrate_btn.setProperty("class", "primary")
        self.stereo_calibrate_btn.clicked.connect(self.run_stereo_calibration)
        stereo_layout.addWidget(self.stereo_calibrate_btn, 0, 0)
        
        self.stereo_save_btn = QPushButton("保存双目结果")
        self.stereo_save_btn.clicked.connect(self.save_stereo_results)
        stereo_layout.addWidget(self.stereo_save_btn, 0, 1)
        
        # 标定进度
        self.stereo_progress = QProgressBar()
        stereo_layout.addWidget(self.stereo_progress, 1, 0, 1, 2)  # 调整colspan为2
        
        # 标定状态
        self.stereo_status_label = QLabel("等待开始双目标定")
        stereo_layout.addWidget(self.stereo_status_label, 2, 0, 1, 2)  # 调整colspan为2
        
        layout.addWidget(stereo_group)
        
        # 双目标定结果显示组
        stereo_results_group = QGroupBox("双目标定结果")
        stereo_results_layout = QVBoxLayout(stereo_results_group)
        
        self.stereo_results_text = QTextEdit()
        self.stereo_results_text.setMaximumHeight(200)  # 减小结果显示区域高度
        self.stereo_results_text.setReadOnly(True)
        stereo_results_layout.addWidget(self.stereo_results_text)
        
        layout.addWidget(stereo_results_group)
        
        # 将内容widget添加到滚动区域
        scroll_area.setWidget(widget)
        
        return scroll_area
    
    def toggle_preview(self):
        """切换预览状态"""
        if self.preview_worker is None or not self.preview_worker.isRunning():
            self.start_preview()
        else:
            self.stop_preview()
    
    def start_preview(self):
        """开始预览"""
        try:
            camera_index = self.camera_combo.currentIndex()
            self.preview_worker = CameraPreviewWorker(camera_index)
            self.preview_worker.frame_ready.connect(self.update_preview)
            self.preview_worker.error.connect(self.on_preview_error)
            self.preview_worker.start_preview()
            
            self.preview_btn.setText("停止预览")
            self.camera_status.setText("已连接")
            self.camera_status.setStyleSheet("color: green; font-weight: bold;")
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"启动预览失败: {str(e)}")
    
    def stop_preview(self):
        """停止预览"""
        try:
            if self.preview_worker:
                print("正在停止摄像头预览...")
                self.preview_worker.stop_preview()
                self.preview_worker = None
                print("摄像头预览已停止")
        except Exception as e:
            print(f"停止预览时出错: {str(e)}")
            # 强制设置为None，避免悬挂引用
            self.preview_worker = None
        
        # 更新界面状态
        self.preview_btn.setText("开始预览")
        self.camera_status.setText("未连接")
        self.camera_status.setStyleSheet("color: red; font-weight: bold;")
        self.preview_left_label.setText("预览已停止")
        self.preview_right_label.setText("预览已停止")
    
    def load_existing_photos(self):
        """从文件夹加载已有的照片到内存"""
        try:
            if self.is_stereo_mode:
                # 双目模式：加载左右相机文件夹的照片
                self.captured_images.clear()
                self.captured_left_images.clear()
                
                if os.path.exists(self.stereo_left_path) and os.path.exists(self.stereo_right_path):
                    # 获取左右文件夹的图片文件（使用统一命名格式）
                    left_files = sorted([f for f in os.listdir(self.stereo_left_path) if f.startswith('img_') and f.endswith('.jpg')])
                    right_files = sorted([f for f in os.listdir(self.stereo_right_path) if f.startswith('img_') and f.endswith('.jpg')])
                    
                    # 加载配对的照片
                    pair_count = min(len(left_files), len(right_files))
                    for i in range(pair_count):
                        left_path = os.path.join(self.stereo_left_path, left_files[i])
                        right_path = os.path.join(self.stereo_right_path, right_files[i])
                        
                        # 读取图片到内存
                        left_img = cv2.imread(left_path)
                        right_img = cv2.imread(right_path)
                        
                        if left_img is not None and right_img is not None:
                            self.captured_left_images.append(left_img)
                            self.captured_images.append(right_img)
            else:
                # 单目模式：加载单目文件夹的照片
                self.captured_images.clear()
                self.captured_left_images.clear()  # 清空双目图片
                
                if os.path.exists(self.mono_save_path):
                    # 获取单目文件夹的图片文件
                    mono_files = sorted([f for f in os.listdir(self.mono_save_path) if f.startswith('mono_') and f.endswith('.jpg')])
                    
                    # 加载单目照片
                    for mono_file in mono_files:
                        mono_path = os.path.join(self.mono_save_path, mono_file)
                        mono_img = cv2.imread(mono_path)
                        
                        if mono_img is not None:
                            self.captured_images.append(mono_img)
                            
            print(f"已加载 {'双目' if self.is_stereo_mode else '单目'} 照片: {len(self.captured_images)} {'对' if self.is_stereo_mode else '张'}")
            
        except Exception as e:
            print(f"加载已有照片失败: {str(e)}")
    
    def on_calibration_mode_changed(self, mode):
        """标定模式切换处理"""
        self.is_stereo_mode = (mode == "双目标定")
        
        # 先加载对应模式的已有照片
        self.load_existing_photos()
        
        # 更新界面提示
        if self.is_stereo_mode:
            self.preview_info_label.setText("双目标定模式：显示左右两个画面，拍摄时保存左右两张照片")
            self.photos_list_label.setText("已拍摄双目照片:")
        else:
            self.preview_info_label.setText("单目标定模式：只使用右侧画面，拍摄时只保存右相机图片")
            self.photos_list_label.setText("已拍摄单目照片:")
        
        # 更新照片列表显示（根据模式切换）
        try:
            self.update_photos_list()
        except Exception as e:
            print(f"切换标定模式时更新照片列表失败: {str(e)}")
        
        # 更新采集计数显示
        self.update_capture_count()
    
    def update_preview(self, frame):
        """更新预览画面"""
        try:
            # 分离左右画面 (假设摄像头宽度为1280)
            if frame.shape[1] >= 1280:
                frame_L = frame[:, 0:640]  # 左侧画面
                frame_R = frame[:, 640:1280]  # 右侧画面
            else:
                # 如果不是双目摄像头，则左右显示相同画面
                frame_L = frame
                frame_R = frame
            
            # 转换左画面为Qt图像格式
            rgb_image_L = cv2.cvtColor(frame_L, cv2.COLOR_BGR2RGB)
            h_L, w_L, ch_L = rgb_image_L.shape
            bytes_per_line_L = ch_L * w_L
            qt_image_L = QImage(rgb_image_L.data, w_L, h_L, bytes_per_line_L, QImage.Format_RGB888)
            
            # 使用固定尺寸缩放左画面图像，避免越来越大
            pixmap_L = QPixmap.fromImage(qt_image_L)
            fixed_size_L = self.preview_left_label.minimumSize()
            if fixed_size_L.width() == 0 or fixed_size_L.height() == 0:
                fixed_size_L = self.preview_left_label.size()
            scaled_pixmap_L = pixmap_L.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 更新缩放尺寸
            self.preview_left_label.setPixmap(scaled_pixmap_L)
            
            # 转换右画面为Qt图像格式
            rgb_image_R = cv2.cvtColor(frame_R, cv2.COLOR_BGR2RGB)
            h_R, w_R, ch_R = rgb_image_R.shape
            bytes_per_line_R = ch_R * w_R
            qt_image_R = QImage(rgb_image_R.data, w_R, h_R, bytes_per_line_R, QImage.Format_RGB888)
            
            # 使用固定尺寸缩放右画面图像，避免越来越大
            pixmap_R = QPixmap.fromImage(qt_image_R)
            scaled_pixmap_R = pixmap_R.scaled(400, 300, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 更新缩放尺寸
            self.preview_right_label.setPixmap(scaled_pixmap_R)
            
        except Exception as e:
            self.on_preview_error(f"更新预览失败: {str(e)}")
    
    def on_preview_error(self, error_msg):
        """处理预览错误"""
        # 只在控制台输出错误信息，不显示弹窗，不停止预览
        print(f"摄像头预览警告: {error_msg}")
        # 移除错误弹窗和停止预览的逻辑，让预览继续运行
    
    def capture_image(self):
        """拍摄照片"""
        if not self.preview_worker or not self.preview_worker.isRunning():
            QMessageBox.warning(self, "警告", "请先开始相机预览")
            return
        
        try:
            # 从预览线程获取当前帧，避免创建新的摄像头实例
            if hasattr(self.preview_worker, 'cap') and self.preview_worker.cap is not None:
                ret, frame = self.preview_worker.cap.read()
            else:
                self.capture_status_label.setText("无法获取摄像头帧")
                self.capture_status_label.setStyleSheet("color: red;")
                return
            
            if ret:
                # 分离左右画面
                if frame.shape[1] >= 1280:
                    frame_L = frame[:, 0:640]  # 左侧画面
                    frame_R = frame[:, 640:1280]  # 右侧画面
                else:
                    # 如果不是双目摄像头，使用整个画面
                    frame_L = frame
                    frame_R = frame
                
                # 获取当前使用的参数（根据标定模式）
                if self.is_stereo_mode:
                    width = self.stereo_width_spinbox.value() if hasattr(self, 'stereo_width_spinbox') else self.checkerboard_width
                    height = self.stereo_height_spinbox.value() if hasattr(self, 'stereo_height_spinbox') else self.checkerboard_height
                else:
                    width = self.mono_width_spinbox.value() if hasattr(self, 'mono_width_spinbox') else self.checkerboard_width
                    height = self.mono_height_spinbox.value() if hasattr(self, 'mono_height_spinbox') else self.checkerboard_height
                
                if self.is_stereo_mode:
                    # 双目模式：检测左右画面的棋盘格
                    gray_L = cv2.cvtColor(frame_L, cv2.COLOR_BGR2GRAY)
                    gray_R = cv2.cvtColor(frame_R, cv2.COLOR_BGR2GRAY)
                    
                    ret_L, corners_L = cv2.findChessboardCorners(gray_L, (width, height), None)
                    ret_R, corners_R = cv2.findChessboardCorners(gray_R, (width, height), None)
                    
                    if ret_L and ret_R:
                        # 检测到完整棋盘格，自动保存
                        self.auto_save_stereo_images(frame_L, frame_R)
                        self.capture_status_label.setText("双目照片已自动保存 - 左右都检测到棋盘格")
                        self.capture_status_label.setStyleSheet("color: green;")
                    else:
                        self.capture_status_label.setText("未检测到完整棋盘格 - 照片未保存")
                        self.capture_status_label.setStyleSheet("color: red;")
                else:
                    # 单目模式：检测右画面的棋盘格
                    gray_R = cv2.cvtColor(frame_R, cv2.COLOR_BGR2GRAY)
                    ret_R, corners_R = cv2.findChessboardCorners(gray_R, (width, height), None)
                    
                    if ret_R:
                        # 检测到完整棋盘格，自动保存
                        self.auto_save_mono_image(frame_R)
                        self.capture_status_label.setText("单目照片已自动保存 - 检测到棋盘格")
                        self.capture_status_label.setStyleSheet("color: green;")
                    else:
                        self.capture_status_label.setText("未检测到棋盘格 - 照片未保存")
                        self.capture_status_label.setStyleSheet("color: red;")
                
                # 更新计数和照片列表
                self.update_capture_count()
                try:
                    self.update_photos_list()
                except Exception as e:
                    print(f"更新照片列表时出错: {str(e)}")
                    # 即使照片列表更新失败，也不影响拍摄功能
                
            else:
                QMessageBox.warning(self, "错误", "拍摄照片失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"拍摄照片时出错: {str(e)}")
    
    def get_next_file_index(self, folder_path, prefix):
        """获取文件夹中下一个可用的文件编号"""
        if not os.path.exists(folder_path):
            return 0
        
        files = [f for f in os.listdir(folder_path) if f.endswith('.jpg')]
        if not files:
            return 0
        
        # 提取现有文件的编号
        indices = []
        for file in files:
            try:
                if prefix == "stereo":
                    # 双目模式使用统一编号：img_001.jpg
                    if file.startswith('img_'):
                        index_str = file.replace('img_', '').replace('.jpg', '')
                        indices.append(int(index_str))
                else:
                    # 单目模式：mono_001.jpg
                    index_str = file.replace(prefix + '_', '').replace('.jpg', '')
                    indices.append(int(index_str))
            except ValueError:
                continue
        
        return max(indices) + 1 if indices else 0
    
    def auto_save_mono_image(self, image):
        """自动保存单目图片"""
        # 确保保存文件夹存在
        os.makedirs(self.mono_save_path, exist_ok=True)
        
        # 获取下一个可用的文件编号
        image_index = self.get_next_file_index(self.mono_save_path, "mono")
        filename = os.path.join(self.mono_save_path, f"mono_{image_index:03d}.jpg")
        
        # 保存图片
        cv2.imwrite(filename, image)
        
        # 添加到内存列表
        self.captured_images.append(image)
    
    def auto_save_stereo_images(self, left_image, right_image):
        """自动保存双目图片"""
        # 确保保存文件夹存在
        os.makedirs(self.stereo_left_path, exist_ok=True)
        os.makedirs(self.stereo_right_path, exist_ok=True)
        
        # 获取下一个可用的文件编号（使用统一编号格式）
        image_index = self.get_next_file_index(self.stereo_left_path, "stereo")
        # 双目标定要求左右文件夹中文件名相同
        left_filename = os.path.join(self.stereo_left_path, f"img_{image_index:03d}.jpg")
        right_filename = os.path.join(self.stereo_right_path, f"img_{image_index:03d}.jpg")
        
        # 保存图片
        cv2.imwrite(left_filename, left_image)
        cv2.imwrite(right_filename, right_image)
        
        # 添加到内存列表
        self.captured_left_images.append(left_image)
        self.captured_images.append(right_image)
    
    def update_capture_count(self):
        """更新采集计数显示"""
        if self.is_stereo_mode:
            # 双目模式：显示照片对数量（取左右照片的最小值）
            photo_pairs = min(len(self.captured_images), len(self.captured_left_images))
            count_text = f"已采集: {photo_pairs} 对"
        else:
            # 单目模式：显示单张照片数量
            count_text = f"已采集: {len(self.captured_images)} 张"
        self.capture_count_label.setText(count_text)
    
    def update_photos_list(self):
        """更新照片列表显示"""
        try:
            # 获取或创建布局
            if self.photos_list.layout() is None:
                # 如果没有布局，创建新的
                photos_layout = QVBoxLayout(self.photos_list)
            else:
                # 如果已有布局，清空现有内容但保留布局
                photos_layout = self.photos_list.layout()
                # 清除所有现有的子控件
                while photos_layout.count():
                    child = photos_layout.takeAt(0)
                    if child.widget():
                        child.widget().deleteLater()
            
            # 重新初始化照片复选框列表
            self.photo_checkboxes = []
            
            # 根据标定模式显示不同的照片列表
            if self.is_stereo_mode:
                # 双目模式：显示双目照片对
                photo_count = min(len(self.captured_images), len(self.captured_left_images))
                for i in range(photo_count):
                    checkbox = QCheckBox(f"双目照片对 {i+1:03d}")
                    checkbox.stateChanged.connect(self.on_photo_selection_changed)
                    checkbox.clicked.connect(partial(self.on_photo_clicked, i))
                    
                    self.photo_checkboxes.append(checkbox)
                    photos_layout.addWidget(checkbox)
            else:
                # 单目模式：显示单目照片
                for i in range(len(self.captured_images)):
                    checkbox = QCheckBox(f"单目照片 {i+1:03d}")
                    checkbox.stateChanged.connect(self.on_photo_selection_changed)
                    checkbox.clicked.connect(partial(self.on_photo_clicked, i))
                    
                    self.photo_checkboxes.append(checkbox)
                    photos_layout.addWidget(checkbox)
            
            # 添加弹性空间
            photos_layout.addStretch()
            
        except Exception as e:
            print(f"更新照片列表失败: {str(e)}")
    
    def on_photo_selection_changed(self):
        """照片选择状态改变"""
        self.selected_photo_indices = []
        for i, checkbox in enumerate(self.photo_checkboxes):
            if checkbox.isChecked():
                self.selected_photo_indices.append(i)
    
    def on_photo_clicked(self, index):
        """照片点击事件处理"""
        try:
            self.preview_photo(index)
        except Exception as e:
            print(f"照片点击预览失败 (索引 {index}): {str(e)}")
            self.photo_preview_label.setText(f"预览失败: {str(e)}")
    
    def preview_photo(self, index):
        """预览指定索引的照片"""
        if not (0 <= index < len(self.captured_images)):
            print(f"无效的照片索引: {index}")
            return
            
        try:
            if self.is_stereo_mode and index < len(self.captured_left_images):
                # 双目模式：显示左右图片
                left_img = self.captured_left_images[index]
                right_img = self.captured_images[index]
                
                # 确保图像有效
                if left_img is None or right_img is None:
                    self.photo_preview_label.setText("图像数据无效")
                    return
                
                # 调整图像尺寸使其一致
                h = min(left_img.shape[0], right_img.shape[0])
                left_resized = cv2.resize(left_img, (320, h))
                right_resized = cv2.resize(right_img, (320, h))
                
                # 将左右图片拼接显示
                combined_img = np.hstack((left_resized, right_resized))
                
                # 转换为Qt图像格式
                if len(combined_img.shape) == 3:
                    rgb_image = cv2.cvtColor(combined_img, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                else:
                    # 灰度图像处理
                    h, w = combined_img.shape
                    qt_image = QImage(combined_img.data, w, h, QImage.Format_Grayscale8)
                
                # 使用固定尺寸缩放图像，避免图像越来越大
                pixmap = QPixmap.fromImage(qt_image)
                if pixmap.isNull():
                    self.photo_preview_label.setText("图像转换失败")
                    return
                    
                # 固定预览尺寸，避免图像尺寸累积
                scaled_pixmap = pixmap.scaled(350, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 更新预览尺寸
                self.photo_preview_label.setPixmap(scaled_pixmap)
                
            else:
                # 单目模式：显示单张图片
                img = self.captured_images[index]
                
                # 确保图像有效
                if img is None:
                    self.photo_preview_label.setText("图像数据无效")
                    return
                
                # 转换为Qt图像格式
                if len(img.shape) == 3:
                    rgb_image = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                    h, w, ch = rgb_image.shape
                    bytes_per_line = ch * w
                    qt_image = QImage(rgb_image.data, w, h, bytes_per_line, QImage.Format_RGB888)
                else:
                    # 灰度图像处理
                    h, w = img.shape
                    qt_image = QImage(img.data, w, h, QImage.Format_Grayscale8)
                
                # 使用固定尺寸缩放图像，避免图像越来越大
                pixmap = QPixmap.fromImage(qt_image)
                if pixmap.isNull():
                    self.photo_preview_label.setText("图像转换失败")
                    return
                    
                # 固定预览尺寸，避免图像尺寸累积
                scaled_pixmap = pixmap.scaled(350, 250, Qt.KeepAspectRatio, Qt.SmoothTransformation)  # 更新预览尺寸
                self.photo_preview_label.setPixmap(scaled_pixmap)
                
        except Exception as e:
            error_msg = f"预览照片时出错: {str(e)}"
            print(error_msg)
            self.photo_preview_label.setText("预览失败")
            # 不再弹出错误对话框，只在控制台输出错误
    
    def delete_selected_photos(self):
        """删除选中的照片"""
        if not self.selected_photo_indices:
            QMessageBox.warning(self, "警告", "请先选择要删除的照片")
            return
        
        reply = QMessageBox.question(self, "确认删除", 
                                   f"确定要删除选中的 {len(self.selected_photo_indices)} 张照片吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # 按索引降序排列，从后往前删除
                for index in sorted(self.selected_photo_indices, reverse=True):
                    # 删除文件
                    if self.is_stereo_mode:
                        # 使用新的统一文件命名格式
                        left_filename = os.path.join(self.stereo_left_path, f"img_{index:03d}.jpg")
                        right_filename = os.path.join(self.stereo_right_path, f"img_{index:03d}.jpg")
                        
                        if os.path.exists(left_filename):
                            os.remove(left_filename)
                        if os.path.exists(right_filename):
                            os.remove(right_filename)
                        
                        # 从内存列表中删除
                        if index < len(self.captured_left_images):
                            del self.captured_left_images[index]
                    else:
                        mono_filename = os.path.join(self.mono_save_path, f"mono_{index:03d}.jpg")
                        if os.path.exists(mono_filename):
                            os.remove(mono_filename)
                    
                    # 从内存列表中删除
                    if index < len(self.captured_images):
                        del self.captured_images[index]
                
                # 重新命名剩余文件以保持连续编号
                self.renumber_saved_files()
                
                # 更新界面
                self.update_capture_count()
                try:
                    self.update_photos_list()
                except Exception as e:
                    print(f"删除照片后更新列表失败: {str(e)}")
                
                self.photo_preview_label.setText("选择照片查看")
                # 移除clear()调用，只设置提示文本
                
                QMessageBox.information(self, "删除成功", "选中的照片已删除")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"删除照片失败: {str(e)}")
    
    def clear_all_photos(self):
        """清空所有照片"""
        if not self.captured_images:
            QMessageBox.information(self, "提示", "没有照片可清空")
            return
        
        reply = QMessageBox.question(self, "确认清空", 
                                   f"确定要清空所有 {len(self.captured_images)} 张照片吗？",
                                   QMessageBox.Yes | QMessageBox.No)
        if reply == QMessageBox.Yes:
            try:
                # 删除文件夹中的所有文件
                if self.is_stereo_mode:
                    if os.path.exists(self.stereo_left_path):
                        for file in os.listdir(self.stereo_left_path):
                            if file.endswith('.jpg'):
                                os.remove(os.path.join(self.stereo_left_path, file))
                    
                    if os.path.exists(self.stereo_right_path):
                        for file in os.listdir(self.stereo_right_path):
                            if file.endswith('.jpg'):
                                os.remove(os.path.join(self.stereo_right_path, file))
                    
                    self.captured_left_images.clear()
                else:
                    if os.path.exists(self.mono_save_path):
                        for file in os.listdir(self.mono_save_path):
                            if file.endswith('.jpg'):
                                os.remove(os.path.join(self.mono_save_path, file))
                
                # 清空内存列表
                self.captured_images.clear()
                
                # 更新界面
                self.update_capture_count()
                try:
                    self.update_photos_list()
                except Exception as e:
                    print(f"清空照片后更新列表失败: {str(e)}")
                
                self.photo_preview_label.setText("选择照片查看")
                # 移除clear()调用，只设置提示文本
                
                QMessageBox.information(self, "清空成功", "所有照片已清空")
                
            except Exception as e:
                QMessageBox.critical(self, "错误", f"清空照片失败: {str(e)}")
    
    def renumber_saved_files(self):
        """重新编号保存的文件以保持连续性"""
        try:
            if self.is_stereo_mode:
                # 双目模式：重新编号左右文件（使用统一命名格式）
                left_files = [f for f in os.listdir(self.stereo_left_path) if f.startswith('img_') and f.endswith('.jpg')]
                right_files = [f for f in os.listdir(self.stereo_right_path) if f.startswith('img_') and f.endswith('.jpg')]
                
                left_files.sort()
                right_files.sort()
                
                # 重命名左相机文件
                for i, old_filename in enumerate(left_files):
                    old_path = os.path.join(self.stereo_left_path, old_filename)
                    new_filename = f"img_{i:03d}.jpg"
                    new_path = os.path.join(self.stereo_left_path, new_filename)
                    if old_path != new_path:
                        os.rename(old_path, new_path)
                
                # 重命名右相机文件
                for i, old_filename in enumerate(right_files):
                    old_path = os.path.join(self.stereo_right_path, old_filename)
                    new_filename = f"img_{i:03d}.jpg"
                    new_path = os.path.join(self.stereo_right_path, new_filename)
                    if old_path != new_path:
                        os.rename(old_path, new_path)
            else:
                # 单目模式：重新编号文件
                mono_files = [f for f in os.listdir(self.mono_save_path) if f.startswith('mono_') and f.endswith('.jpg')]
                mono_files.sort()
                
                for i, old_filename in enumerate(mono_files):
                    old_path = os.path.join(self.mono_save_path, old_filename)
                    new_filename = f"mono_{i:03d}.jpg"
                    new_path = os.path.join(self.mono_save_path, new_filename)
                    if old_path != new_path:
                        os.rename(old_path, new_path)
                        
        except Exception as e:
            print(f"重新编号文件失败: {str(e)}")
    
    def load_calibration_config(self):
        """加载标定配置文件"""
        config_path = "config/calibration_parameter.json"
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            else:
                # 如果文件不存在，返回默认结构
                return {
                    "one": {},
                    "two": {},
                    "eyeinhand": {}
                }
        except Exception as e:
            print(f"加载配置文件失败: {str(e)}")
            return {"one": {}, "two": {}, "eyeinhand": {}}
    
    def save_calibration_config(self, config):
        """保存标定配置文件"""
        config_path = "config/calibration_parameter.json"
        try:
            # 确保config目录存在
            os.makedirs("config", exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(config, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"保存配置文件失败: {str(e)}")
            return False
    
    def run_mono_calibration(self):
        """运行单目标定"""
        if not self.captured_images:
            QMessageBox.warning(self, "警告", "请先采集标定图片")
            return
        
        try:
            self.mono_status_label.setText("正在进行单目标定...")
            self.mono_progress.setValue(0)
            
            # 获取单目标定参数
            width = self.mono_width_spinbox.value()
            height = self.mono_height_spinbox.value()
            square_size = self.mono_square_size_spinbox.value()
            
            # 获取相机模型 - 确保选择与计算一致
            model_text = self.mono_model_combo.currentText()
            model = 'fisheye' if 'fisheye' in model_text.lower() else 'pinhole'
            
            self.mono_status_label.setText(f"正在使用{model_text}进行标定...")
            
            # 创建临时文件夹保存图片
            temp_folder = "temp_calibration_images"
            os.makedirs(temp_folder, exist_ok=True)
            
            # 保存图片到临时文件夹
            for i, image in enumerate(self.captured_images):
                filename = os.path.join(temp_folder, f"img_{i:03d}.jpg")
                cv2.imwrite(filename, image)
            
            self.mono_progress.setValue(30)
            
            # 运行标定
            calibrator = CameraCalibrator(
                w=width,
                h=height,
                square_size=square_size,
                images_path=os.path.join(temp_folder, "*.jpg"),
                model=model
            )
            
            self.mono_progress.setValue(60)
            
            ret, mtx, dist, u, v, processed_images, rvecs, tvecs, newcameramtx = \
                calibrator.run_calibration(
                    os.path.join(temp_folder, "*.jpg"),
                    width,
                    height,
                    square_size
                )
            
            self.mono_progress.setValue(90)
            
            # 保存结果
            self.calibration_results['mono'] = {
                'ret': ret,
                'camera_matrix': mtx,
                'distortion_coeffs': dist,
                'image_size': (u, v),
                'rvecs': rvecs,
                'tvecs': tvecs,
                'new_camera_matrix': newcameramtx,
                'model': model  # 保存模型类型
            }
            
            # 计算焦距的物理含义
            fx_pixels = mtx[0, 0]
            fy_pixels = mtx[1, 1]
            # 如果square_size单位是mm，那么焦距表示：每毫米对应多少像素
            # 对于640x480的图像，典型焦距应该在300-600像素范围内
            
            # 显示结果
            model_name = "鱼眼模型" if model == 'fisheye' else "标准针孔模型"
            result_text = f"""单目标定完成！

相机模型: {model_name}
标定精度 (RMS误差): {ret:.4f}

相机内参矩阵:
{mtx}

焦距分析:
- fx = {fx_pixels:.1f} 像素
- fy = {fy_pixels:.1f} 像素
- 视场角(水平): {np.rad2deg(2*np.arctan(u/2/fx_pixels)):.1f}°
- 视场角(垂直): {np.rad2deg(2*np.arctan(v/2/fy_pixels)):.1f}°

畸变系数:
{dist.flatten()}

图像尺寸: {u} x {v}

处理的图像数量: {len(rvecs)}

使用的标定参数:
- 棋盘格尺寸: {width} x {height}
- 方格大小: {square_size} mm (⚠️ 请确认实际测量值！)
- 相机模型: {model_name}

⚠️ 重要提醒：
如果方格尺寸输入错误，会直接影响焦距标定结果！
实际尺寸 / 输入尺寸 = 焦距误差倍数
"""
            self.mono_results_text.setText(result_text)
            self.mono_progress.setValue(100)
            self.mono_status_label.setText("单目标定完成")
            
            # 清理临时文件
            import shutil
            shutil.rmtree(temp_folder, ignore_errors=True)
            
            QMessageBox.information(self, "成功", f"单目标定完成！\n使用模型: {model_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"单目标定失败: {str(e)}")
            self.mono_status_label.setText("标定失败")
    
    def run_stereo_calibration(self):
        """运行双目标定"""
        # 检查自动保存的路径是否存在图片
        if not os.path.exists(self.stereo_left_path) or not os.path.exists(self.stereo_right_path):
            QMessageBox.warning(self, "警告", "请先拍摄双目标定图片")
            return
        
        # 检查是否有足够的图片
        left_images = [f for f in os.listdir(self.stereo_left_path) if f.endswith('.jpg')]
        right_images = [f for f in os.listdir(self.stereo_right_path) if f.endswith('.jpg')]
        
        if len(left_images) < 5 or len(right_images) < 5:
            QMessageBox.warning(self, "警告", f"图片数量不足，建议至少5对图片。当前：左{len(left_images)}张，右{len(right_images)}张")
            return
        
        try:
            self.stereo_status_label.setText("正在进行双目标定...")
            self.stereo_progress.setValue(0)
            
            # 获取双目标定参数
            width = self.stereo_width_spinbox.value()
            height = self.stereo_height_spinbox.value()
            square_size = self.stereo_square_size_spinbox.value()
            
            # 获取相机模型 - 确保选择与计算一致
            model_text = self.stereo_model_combo.currentText()
            model = 'fisheye' if 'fisheye' in model_text.lower() else 'pinhole'
            
            self.stereo_status_label.setText(f"正在使用{model_text}进行标定...")
            
            calibrator = Two_Camera_Clibration(
                w=width,
                h=height,
                square_size=square_size,
                leftpath=self.stereo_left_path,
                rightpath=self.stereo_right_path,
                model=model
            )
            
            self.stereo_progress.setValue(50)
            
            # 双目标定 - 处理不同返回值数量
            calibration_result = calibrator.calibration_run(width, height, square_size)
            
            if model == 'fisheye':
                # 鱼眼模型返回6个值：K1, D1, K2, D2, R, T
                if len(calibration_result) == 6:
                    cameraMatrix1, dist1, cameraMatrix2, dist2, R, T = calibration_result
                else:
                    raise ValueError(f"鱼眼双目标定返回值数量错误: {len(calibration_result)}")
            else:
                # 针孔模型返回6个值：cameraMatrix1, dist1, cameraMatrix2, dist2, R, T
                if len(calibration_result) == 6:
                    cameraMatrix1, dist1, cameraMatrix2, dist2, R, T = calibration_result
                else:
                    raise ValueError(f"针孔双目标定返回值数量错误: {len(calibration_result)}")
            
            self.stereo_progress.setValue(90)
            
            # 保存结果
            self.calibration_results['stereo'] = {
                'left_camera_matrix': cameraMatrix1,
                'left_distortion': dist1,
                'right_camera_matrix': cameraMatrix2,
                'right_distortion': dist2,
                'rotation_matrix': R,
                'translation_vector': T,
                'model': model  # 保存模型类型
            }
            
            # 显示结果
            model_name = "鱼眼模型" if model == 'fisheye' else "标准针孔模型"
            result_text = f"""双目标定完成！

相机模型: {model_name}

左相机内参矩阵:
{cameraMatrix1}

左相机畸变系数:
{dist1.flatten()}

右相机内参矩阵:
{cameraMatrix2}

右相机畸变系数:
{dist2.flatten()}

旋转矩阵 R:
{R}

平移向量 T:
{T.flatten()}

使用的标定参数:
- 棋盘格尺寸: {width} x {height}
- 方格大小: {square_size} mm
- 相机模型: {model_name}
- 左相机图片路径: {self.stereo_left_path}
- 右相机图片路径: {self.stereo_right_path}
"""
            self.stereo_results_text.setText(result_text)
            self.stereo_progress.setValue(100)
            self.stereo_status_label.setText("双目标定完成")
            
            QMessageBox.information(self, "成功", f"双目标定完成！\n使用模型: {model_name}")
            
        except Exception as e:
            QMessageBox.critical(self, "错误", f"双目标定失败: {str(e)}")
            self.stereo_status_label.setText("标定失败")
            print(f"双目标定详细错误: {e}")  # 添加详细错误输出
    
    def save_mono_results(self):
        """保存单目标定结果到配置文件"""
        if 'mono' not in self.calibration_results:
            QMessageBox.warning(self, "警告", "没有可保存的单目标定结果")
            return
        
        try:
            # 加载现有配置
            config = self.load_calibration_config()
            
            # 获取单目标定结果
            result = self.calibration_results['mono']
            
            # 转换numpy数组为Python列表（JSON可序列化）
            # 方案A：保存原始内参K，不保存newcameramtx
            camera_matrix = result['camera_matrix'].tolist()
            distortion_coeffs = result['distortion_coeffs'].tolist()
            
            # 更新配置文件的单目部分
            config['one'] = {
                'camera_matrix': camera_matrix,
                'camera_distortion': distortion_coeffs,
                'model': result.get('model', 'fisheye')  # 保存模型类型
            }
            
            # 保存配置文件
            if self.save_calibration_config(config):
                model_name = "鱼眼模型" if result.get('model') == 'fisheye' else "标准针孔模型"
                QMessageBox.information(self, "成功", f"单目标定结果已保存！\n\n相机模型: {model_name}\n配置文件: config/calibration_parameter.json\n\n⚠️ 注意: 请确保手眼标定使用相同的相机模型")
            else:
                QMessageBox.critical(self, "错误", "保存配置文件失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存单目标定结果失败: {str(e)}")
    
    def save_stereo_results(self):
        """保存双目标定结果到配置文件"""
        if 'stereo' not in self.calibration_results:
            QMessageBox.warning(self, "警告", "没有可保存的双目标定结果")
            return
        
        try:
            # 加载现有配置
            config = self.load_calibration_config()
            
            # 获取双目标定结果
            result = self.calibration_results['stereo']
            
            # 转换numpy数组为Python列表（JSON可序列化）
            left_camera_matrix = result['left_camera_matrix'].tolist()
            right_camera_matrix = result['right_camera_matrix'].tolist()
            left_distortion = result['left_distortion'].tolist()
            right_distortion = result['right_distortion'].tolist()
            rotation_matrix = result['rotation_matrix'].tolist()
            translation_vector = result['translation_vector'].flatten().tolist()
            
            # 更新配置文件的双目部分
            config['two'] = {
                'left_camera_matrix': left_camera_matrix,
                'right_camera_matrix': right_camera_matrix,
                'left_distortion': left_distortion,
                'right_distortion': right_distortion,
                'R': rotation_matrix,
                'T': translation_vector,
                'model': result.get('model', 'fisheye')  # 保存模型类型
            }
            
            # 保存配置文件
            if self.save_calibration_config(config):
                model_name = "鱼眼模型" if result.get('model') == 'fisheye' else "标准针孔模型"
                QMessageBox.information(self, "成功", f"双目标定结果已保存！\n\n相机模型: {model_name}\n配置文件: config/calibration_parameter.json\n\n⚠️ 注意: 请确保手眼标定使用相同的相机模型")
            else:
                QMessageBox.critical(self, "错误", "保存配置文件失败")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存双目标定结果失败: {str(e)}")
    
    def apply_mono_settings(self):
        """应用单目标定参数设置"""
        self.checkerboard_width = self.mono_width_spinbox.value()
        self.checkerboard_height = self.mono_height_spinbox.value()
        self.square_size = self.mono_square_size_spinbox.value()
        
        QMessageBox.information(self, "成功", "单目标定参数设置已应用")
    
    def reset_mono_settings(self):
        """重置单目标定参数为默认值"""
        self.mono_width_spinbox.setValue(9)
        self.mono_height_spinbox.setValue(6)
        self.mono_square_size_spinbox.setValue(22.0)
        
        QMessageBox.information(self, "成功", "单目标定参数已重置为默认值")
    
    def apply_stereo_settings(self):
        """应用双目标定参数设置"""
        self.checkerboard_width = self.stereo_width_spinbox.value()
        self.checkerboard_height = self.stereo_height_spinbox.value()
        self.square_size = self.stereo_square_size_spinbox.value()
        
        QMessageBox.information(self, "成功", "双目标定参数设置已应用")
    
    def reset_stereo_settings(self):
        """重置双目标定参数为默认值"""
        self.stereo_width_spinbox.setValue(9)
        self.stereo_height_spinbox.setValue(6)
        self.stereo_square_size_spinbox.setValue(22.0)
        
        QMessageBox.information(self, "成功", "双目标定参数已重置为默认值")
    
    def closeEvent(self, event):
        """关闭事件处理"""
        try:
            # 强制停止预览线程
            if self.preview_worker and self.preview_worker.isRunning():
                print("正在停止摄像头预览线程...")
                self.preview_worker._is_running = False  # 设置停止标志
                
                # 释放摄像头资源
                if hasattr(self.preview_worker, 'cap') and self.preview_worker.cap:
                    self.preview_worker.cap.release()
                
                # 关闭OpenCV窗口
                cv2.destroyAllWindows()
                
                # 等待线程结束，但设置超时
                self.preview_worker.quit()
                if not self.preview_worker.wait(3000):  # 等待3秒
                    print("预览线程超时，强制终止")
                    self.preview_worker.terminate()
                    self.preview_worker.wait(1000)  # 再等待1秒
                
                print("摄像头预览线程已停止")
            
            # 确保所有OpenCV窗口都关闭
            cv2.destroyAllWindows()
            
        except Exception as e:
            print(f"关闭时出现错误: {str(e)}")
        finally:
            # 无论如何都接受关闭事件
            event.accept()

if __name__ == "__main__":
    from PyQt5.QtWidgets import QApplication
    import sys
    
    app = QApplication(sys.argv)
    widget = CameraCalibrationWidget()
    widget.show()
    sys.exit(app.exec_()) 