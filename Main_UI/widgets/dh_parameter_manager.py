# -*- coding: utf-8 -*-
"""
DH参数管理器
统一管理机械臂的DH参数配置和设置界面
包含配置管理器和GUI设置对话框
"""

import os
import json
import numpy as np
from typing import Dict, Any, Optional, List
import logging

from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QPushButton, QLabel, QLineEdit, QCheckBox,
                             QTableWidget, QTableWidgetItem, QHeaderView,
                             QMessageBox, QSpacerItem, QSizePolicy, QTabWidget,
                             QFileDialog, QDoubleSpinBox, QComboBox, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QPixmap, QIcon


class NoWheelDoubleSpinBox(QDoubleSpinBox):
    """禁用鼠标滚轮的QDoubleSpinBox"""
    
    def wheelEvent(self, event):
        """重写滚轮事件，忽略滚轮操作"""
        # 忽略滚轮事件，不调用父类的wheelEvent
        event.ignore()

# 获取项目根目录
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(os.path.dirname(current_dir))


class DHConfigManager:
    """DH参数配置管理器"""
    
    def __init__(self, config_file_path=None):
        """
        初始化配置管理器
        
        Args:
            config_file_path: 配置文件路径，如果为None则使用默认路径
        """
        if config_file_path is None:
            # 使用项目根目录下的config文件夹
            config_dir = os.path.join(project_root, "config")
            self.config_file_path = os.path.join(config_dir, "dh_parameters_config.json")
        else:
            self.config_file_path = config_file_path
        
        # 默认DH参数配置（基于原MATLAB代码）
        self.default_config = {
            "dh_parameters": {
                "d": [160.4, 0.0, 0.0, 220.0, 0.0, 62.4],  # 连杆偏移参数 (mm)
                "a": [0.0, 0.0, 200.6, 23.5, 0.0, 0.0],    # 连杆长度参数 (mm)
                "alpha_deg": [0.0, -90.0, 0.0, -90.0, 90.0, -90.0]  # 连杆扭角参数 (度)
            },
            "joint_offsets": [0.0, 90.0, 0.0, 0.0, 0.0, 0.0],  # 关节角度偏转 (度)
            "joint_limits": {
                "1": [-180.0, 180.0],
                "2": [-180.0, 180.0], 
                "3": [-180.0, 180.0],
                "4": [-180.0, 180.0],
                "5": [-180.0, 180.0],
                "6": [-180.0, 180.0]
            },
            "angle_unit": "deg",
            "enable_offset": True,
            "description": "6DOF机械臂DH参数配置",
            "version": "1.0"
        }
        
        # 当前配置
        self.config = self.load_config()
    
    def load_config(self) -> Dict[str, Any]:
        """
        从文件加载配置
        
        Returns:
            配置字典
        """
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    # 确保配置完整
                    return self._ensure_complete_config(config)
            else:
                # 文件不存在，使用默认配置并保存
                self.save_config(self.default_config)
                return self.default_config.copy()
        except Exception as e:
            print(f"加载DH参数配置失败: {e}")
            return self.default_config.copy()
    
    def save_config(self, config: Dict[str, Any] = None) -> bool:
        """
        保存配置到文件
        
        Args:
            config: 要保存的配置，如果为None则保存当前配置
            
        Returns:
            是否保存成功
        """
        try:
            # 确保配置目录存在
            os.makedirs(os.path.dirname(self.config_file_path), exist_ok=True)
            
            save_config = config if config is not None else self.config
            
            with open(self.config_file_path, 'w', encoding='utf-8') as f:
                json.dump(save_config, f, ensure_ascii=False, indent=2)
            
            if config is not None:
                self.config = save_config.copy()
            
            return True
        except Exception as e:
            print(f"保存DH参数配置失败: {e}")
            return False
    
    def _ensure_complete_config(self, config: Dict[str, Any]) -> Dict[str, Any]:
        """
        确保配置完整，补充缺失的默认值
        
        Args:
            config: 输入配置
            
        Returns:
            完整的配置
        """
        complete_config = self.default_config.copy()
        
        # 更新DH参数
        if "dh_parameters" in config:
            complete_config["dh_parameters"].update(config["dh_parameters"])
        
        # 更新关节偏转
        if "joint_offsets" in config:
            complete_config["joint_offsets"] = config["joint_offsets"]
        
        # 更新关节限制
        if "joint_limits" in config:
            complete_config["joint_limits"].update(config["joint_limits"])
        
        # 更新其他设置
        for key in ["angle_unit", "enable_offset", "description", "version"]:
            if key in config:
                complete_config[key] = config[key]
        
        return complete_config
    
    def get_dh_parameters(self) -> Dict[str, List[float]]:
        """
        获取DH参数
        
        Returns:
            包含d, a, alpha的字典，其中alpha为弧度制
        """
        dh_params = self.config["dh_parameters"].copy()
        # 将角度转换为弧度
        dh_params["alpha"] = [np.deg2rad(angle) for angle in dh_params["alpha_deg"]]
        return dh_params
    
    def set_dh_parameters(self, d: List[float], a: List[float], alpha_deg: List[float]) -> None:
        """
        设置DH参数
        
        Args:
            d: 连杆偏移参数 (mm)
            a: 连杆长度参数 (mm)
            alpha_deg: 连杆扭角参数 (度)
        """
        if len(d) != 6 or len(a) != 6 or len(alpha_deg) != 6:
            raise ValueError("DH参数长度必须为6")
        
        self.config["dh_parameters"]["d"] = d
        self.config["dh_parameters"]["a"] = a
        self.config["dh_parameters"]["alpha_deg"] = alpha_deg
    
    def get_joint_offsets(self) -> List[float]:
        """
        获取关节角度偏转
        
        Returns:
            关节角度偏转列表 (度)
        """
        return self.config["joint_offsets"].copy()
    
    def set_joint_offsets(self, offsets: List[float]) -> None:
        """
        设置关节角度偏转
        
        Args:
            offsets: 关节角度偏转列表 (度)
        """
        if len(offsets) != 6:
            raise ValueError("关节偏转参数长度必须为6")
        
        self.config["joint_offsets"] = offsets
    
    def get_joint_limits(self) -> List[tuple]:
        """
        获取关节限制
        
        Returns:
            关节限制列表 [(min1,max1), (min2,max2), ...]
        """
        limits = []
        for i in range(1, 7):
            limit = self.config["joint_limits"].get(str(i), [-180.0, 180.0])
            limits.append(tuple(limit))
        return limits
    
    def set_joint_limits(self, limits: List[tuple]) -> None:
        """
        设置关节限制
        
        Args:
            limits: 关节限制列表 [(min1,max1), (min2,max2), ...]
        """
        if len(limits) != 6:
            raise ValueError("关节限制数量必须为6")
        
        for i, (min_limit, max_limit) in enumerate(limits, 1):
            self.config["joint_limits"][str(i)] = [float(min_limit), float(max_limit)]
    
    def get_single_joint_limit(self, joint_id: int) -> tuple:
        """
        获取单个关节的限制
        
        Args:
            joint_id: 关节ID (1-6)
            
        Returns:
            (最小角度, 最大角度)
        """
        limit = self.config["joint_limits"].get(str(joint_id), [-180.0, 180.0])
        return tuple(limit)
    
    def set_single_joint_limit(self, joint_id: int, min_limit: float, max_limit: float) -> None:
        """
        设置单个关节的限制
        
        Args:
            joint_id: 关节ID (1-6)
            min_limit: 最小角度
            max_limit: 最大角度
        """
        self.config["joint_limits"][str(joint_id)] = [float(min_limit), float(max_limit)]
    
    def is_offset_enabled(self) -> bool:
        """
        获取偏转是否启用
        
        Returns:
            是否启用偏转
        """
        return self.config.get("enable_offset", True)
    
    def set_offset_enabled(self, enabled: bool) -> None:
        """
        设置偏转是否启用
        
        Args:
            enabled: 是否启用偏转
        """
        self.config["enable_offset"] = enabled
    
    def get_angle_unit(self) -> str:
        """
        获取角度单位
        
        Returns:
            角度单位 ('deg' 或 'rad')
        """
        return self.config.get("angle_unit", "deg")
    
    def set_angle_unit(self, unit: str) -> None:
        """
        设置角度单位
        
        Args:
            unit: 角度单位 ('deg' 或 'rad')
        """
        if unit not in ['deg', 'rad']:
            raise ValueError("角度单位必须为 'deg' 或 'rad'")
        self.config["angle_unit"] = unit
    
    def reset_to_default(self) -> None:
        """重置为默认配置（硬编码当前参数）"""
        # 硬编码的默认DH参数配置
        hardcoded_default_config = {
            "dh_parameters": {
                "d": [160.4, 0.0, 0.0, 220.0, 0.0, 62.4],  # 连杆偏移参数 (mm)
                "a": [0.0, 0.0, 200.6, 23.5, 0.0, 0.0],    # 连杆长度参数 (mm)
                "alpha_deg": [0.0, -90.0, 0.0, -90.0, 90.0, -90.0]  # 连杆扭角参数 (度)
            },
            "joint_offsets": [0.0, 90.0, 0.0, 0.0, 0.0, 0.0],  # 关节角度偏转 (度)
            "joint_limits": {
                "1": [-180.0, 180.0],
                "2": [-180.0, 180.0], 
                "3": [-180.0, 180.0],
                "4": [-180.0, 180.0],
                "5": [-180.0, 180.0],
                "6": [-180.0, 180.0]
            },
            "angle_unit": "deg",
            "enable_offset": True,
            "description": "6DOF机械臂DH参数配置",
            "version": "1.0"
        }
        
        self.config = hardcoded_default_config
    
    def get_config_file_path(self) -> str:
        """获取配置文件路径"""
        return self.config_file_path
    
    def export_config(self, export_path: str) -> bool:
        """
        导出配置到指定路径
        
        Args:
            export_path: 导出文件路径
            
        Returns:
            是否导出成功
        """
        try:
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=2)
            return True
        except Exception as e:
            print(f"导出DH参数配置失败: {e}")
            return False
    
    def import_config(self, import_path: str) -> bool:
        """
        从指定路径导入配置
        
        Args:
            import_path: 导入文件路径
            
        Returns:
            是否导入成功
        """
        try:
            with open(import_path, 'r', encoding='utf-8') as f:
                imported_config = json.load(f)
            
            # 验证配置完整性
            complete_config = self._ensure_complete_config(imported_config)
            self.config = complete_config
            return True
        except Exception as e:
            print(f"导入DH参数配置失败: {e}")
            return False
    
    def validate_config(self) -> tuple:
        """
        验证当前配置的有效性
        
        Returns:
            (是否有效, 错误信息列表)
        """
        errors = []
        
        try:
            # 验证DH参数
            dh_params = self.config.get("dh_parameters", {})
            
            for param_name, expected_length in [("d", 6), ("a", 6), ("alpha_deg", 6)]:
                param_list = dh_params.get(param_name, [])
                if len(param_list) != expected_length:
                    errors.append(f"DH参数 {param_name} 长度应为{expected_length}，实际为{len(param_list)}")
            
            # 验证关节偏转
            joint_offsets = self.config.get("joint_offsets", [])
            if len(joint_offsets) != 6:
                errors.append(f"关节偏转参数长度应为6，实际为{len(joint_offsets)}")
            
            # 验证关节限制
            joint_limits = self.config.get("joint_limits", {})
            for i in range(1, 7):
                limit = joint_limits.get(str(i))
                if not limit or len(limit) != 2:
                    errors.append(f"关节{i}的限制参数格式错误")
                elif limit[0] >= limit[1]:
                    errors.append(f"关节{i}的最小限制({limit[0]})应小于最大限制({limit[1]})")
            
        except Exception as e:
            errors.append(f"配置验证过程中出错: {e}")
        
        return len(errors) == 0, errors


class DHSettingsDialog(QDialog):
    """DH参数设置对话框"""
    
    # 定义信号，当配置发生变化时发出
    config_changed = pyqtSignal()
    
    def __init__(self, parent=None, config_manager=None):
        super().__init__(parent)
        self.config_manager = config_manager if config_manager else dh_config_manager
        self.init_ui()
        self.load_current_config()
    
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle("机械臂配置设置")
        self.setMinimumSize(950, 800)
        self.setModal(True)
        
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)
        
        # 标题
        title_label = QLabel("🔧 机械臂配置设置")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 说明信息
        info_label = QLabel(
            "💡 说明：\n"
            "• MDH参数：定义各关节的位置、长度和扭角参数\n"
            "• 关节角度偏转：用于校正关节零位与理论零位的偏差\n"
            "• 关节运动限制：设置各关节的安全运动范围限制\n"
            "• 配置将自动保存并应用到运动学计算、仿真和控制模块"
        )
        info_label.setStyleSheet("""
            QLabel {
                background-color: #f0f8ff;
                border: 1px solid #b0d4f1;
                border-radius: 5px;
                padding: 10px;
                color: #2c3e50;
                font-size: 13px;
            }
        """)
        info_label.setWordWrap(True)
        main_layout.addWidget(info_label)
        
        # 创建标签页
        self.tab_widget = QTabWidget()
        main_layout.addWidget(self.tab_widget)
        
        # MDH参数标签页
        self.create_dh_parameters_tab()
        
        # 关节角度偏转标签页
        self.create_joint_offsets_tab()
        
        # 关节运动限制标签页  
        self.create_joint_limits_tab()
        
        # 高级设置标签页
        self.create_advanced_settings_tab()
        
        # 按钮区域
        self.create_button_area(main_layout)
    
    def create_dh_parameters_tab(self):
        """创建MDH参数设置标签页"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        
        # MDH参数说明
        dh_info = QLabel(
            "MDH参数定义机械臂的运动学模型：\n"
            "• d (mm): 连杆偏移 - 沿z轴的距离\n"
            "• a (mm): 连杆长度 - 沿x轴的距离  \n"
            "• α (°): 连杆扭角 - 绕x轴的旋转角度"
        )
        dh_info.setStyleSheet("""
            QLabel {
                background-color: #fff8dc;
                border: 1px solid #ddd;
                border-radius: 5px;
                padding: 8px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        tab_layout.addWidget(dh_info)
        
        # 创建MDH参数表格
        dh_group = QGroupBox("📐 MDH参数配置")
        dh_layout = QVBoxLayout(dh_group)
        
        self.dh_table = QTableWidget()
        self.dh_table.setRowCount(3)  # 3行：d, a, alpha
        self.dh_table.setColumnCount(6)  # 6列：6个关节
        
        # 设置表头
        self.dh_table.setHorizontalHeaderLabels([f"Link{i+1}" for i in range(6)])
        self.dh_table.setVerticalHeaderLabels(["d (mm)", "a (mm)", "α (°)"])
        
        # 表格样式
        self.dh_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.dh_table.verticalHeader().setDefaultSectionSize(67)  
        self.dh_table.setAlternatingRowColors(True)
        self.dh_table.setMinimumHeight(255)
        
        # 初始化DH参数输入控件
        self.d_inputs = []
        self.a_inputs = []
        self.alpha_inputs = []
        
        for col in range(6):
             # d参数
             d_spin = NoWheelDoubleSpinBox()
             d_spin.setRange(-1000, 1000)
             d_spin.setDecimals(1)
             d_spin.setSuffix(" mm")
             self.dh_table.setCellWidget(0, col, d_spin)
             self.d_inputs.append(d_spin)
             
             # a参数
             a_spin = NoWheelDoubleSpinBox()
             a_spin.setRange(-1000, 1000)
             a_spin.setDecimals(1)
             a_spin.setSuffix(" mm")
             self.dh_table.setCellWidget(1, col, a_spin)
             self.a_inputs.append(a_spin)
             
             # alpha参数
             alpha_spin = NoWheelDoubleSpinBox()
             alpha_spin.setRange(-180, 180)
             alpha_spin.setDecimals(1)
             alpha_spin.setSuffix("°")
             self.dh_table.setCellWidget(2, col, alpha_spin)
             self.alpha_inputs.append(alpha_spin)
        
        dh_layout.addWidget(self.dh_table)
        tab_layout.addWidget(dh_group)
        
        # 预设DH参数按钮
        preset_layout = QHBoxLayout()
        preset_layout.addStretch()
        
        default_btn = QPushButton("🔄 恢复默认MDH参数")
        default_btn.clicked.connect(self.restore_default_dh_parameters)
        preset_layout.addWidget(default_btn)
        
        preset_layout.addStretch()
        tab_layout.addLayout(preset_layout)
        
        tab_layout.addStretch()
        self.tab_widget.addTab(tab_widget, "📐 MDH参数")
    
    def create_joint_offsets_tab(self):
        """创建关节偏转设置标签页"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        
        # 偏转说明
        offset_info = QLabel(
            "关节偏转用于校正真实机械臂与理论模型的偏差：\n"
            "• 偏转角度会在运动学计算中自动补偿\n"
            "• 正值表示逆时针偏转，负值表示顺时针偏转\n"
            "• 通常用于校正机械零位与理论零位的差异"
        )
        offset_info.setStyleSheet("""
            QLabel {
                background-color: #f0fff0;
                border: 1px solid #90EE90;
                border-radius: 5px;
                padding: 8px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        tab_layout.addWidget(offset_info)
        
        # 偏转设置组
        offset_group = QGroupBox("🔄 关节角度偏转设置")
        offset_layout = QVBoxLayout(offset_group)
        
        # 启用偏转复选框
        self.enable_offset_checkbox = QCheckBox("启用关节角度偏转")
        self.enable_offset_checkbox.setStyleSheet("font-weight: bold; color: #2c3e50;")
        offset_layout.addWidget(self.enable_offset_checkbox)
        
        # 创建偏转表格
        self.offset_table = QTableWidget()
        self.offset_table.setRowCount(1)
        self.offset_table.setColumnCount(6)
        
        self.offset_table.setHorizontalHeaderLabels([f"关节{i+1}" for i in range(6)])
        self.offset_table.setVerticalHeaderLabels(["偏转角度"])
        
        self.offset_table.verticalHeader().setDefaultSectionSize(67)
        self.offset_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.offset_table.setAlternatingRowColors(True)
        self.offset_table.setMinimumHeight(80)
        
        # 初始化偏转输入控件
        self.offset_inputs = []
        for col in range(6):
             offset_spin = NoWheelDoubleSpinBox()
             offset_spin.setRange(-180, 180)
             offset_spin.setDecimals(1)
             offset_spin.setSuffix("°")
             self.offset_table.setCellWidget(0, col, offset_spin)
             self.offset_inputs.append(offset_spin)
        
        offset_layout.addWidget(self.offset_table)
        tab_layout.addWidget(offset_group)
        
        # 偏转预设按钮
        offset_preset_layout = QHBoxLayout()
        offset_preset_layout.addStretch()
        
        clear_offsets_btn = QPushButton("🧹 清零所有偏转")
        clear_offsets_btn.clicked.connect(self.clear_all_offsets)
        offset_preset_layout.addWidget(clear_offsets_btn)
        
        default_offsets_btn = QPushButton("🔄 恢复默认偏转")
        default_offsets_btn.clicked.connect(self.restore_default_offsets)
        offset_preset_layout.addWidget(default_offsets_btn)
        
        offset_preset_layout.addStretch()
        tab_layout.addLayout(offset_preset_layout)
        
        tab_layout.addStretch()
        self.tab_widget.addTab(tab_widget, "🔄 角度偏转")
    
    def create_joint_limits_tab(self):
        """创建关节限制设置标签页"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        
        # 限制说明
        limit_info = QLabel(
            "关节限制定义各关节的运动范围：\n"
            "• 防止机械臂运动到危险位置\n"
            "• 在逆运动学和轨迹规划中自动检查\n"
            "• 建议根据机械臂实际情况设置合理范围"
        )
        limit_info.setStyleSheet("""
            QLabel {
                background-color: #ffe4e1;
                border: 1px solid #ffa07a;
                border-radius: 5px;
                padding: 8px;
                color: #2c3e50;
                font-size: 12px;
            }
        """)
        tab_layout.addWidget(limit_info)
        
        # 限制设置组
        limit_group = QGroupBox("⚠️ 关节运动限制设置")
        limit_layout = QVBoxLayout(limit_group)
        
        # 创建限制表格
        self.limit_table = QTableWidget()
        self.limit_table.setRowCount(2)
        self.limit_table.setColumnCount(6)
        
        self.limit_table.setHorizontalHeaderLabels([f"关节{i+1}" for i in range(6)])
        self.limit_table.setVerticalHeaderLabels(["最小角度", "最大角度"])
        
        self.limit_table.verticalHeader().setDefaultSectionSize(67)
        self.limit_table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.limit_table.setAlternatingRowColors(True)
        self.limit_table.setMinimumHeight(120)
        
        # 初始化限制输入控件
        self.min_limit_inputs = []
        self.max_limit_inputs = []
        
        for col in range(6):
             # 最小限制
             min_spin = NoWheelDoubleSpinBox()
             min_spin.setRange(-360, 360)
             min_spin.setDecimals(1)
             min_spin.setSuffix("°")
             self.limit_table.setCellWidget(0, col, min_spin)
             self.min_limit_inputs.append(min_spin)
             
             # 最大限制
             max_spin = NoWheelDoubleSpinBox()
             max_spin.setRange(-360, 360)
             max_spin.setDecimals(1)
             max_spin.setSuffix("°")
             self.limit_table.setCellWidget(1, col, max_spin)
             self.max_limit_inputs.append(max_spin)
        
        limit_layout.addWidget(self.limit_table)
        tab_layout.addWidget(limit_group)
        
        # 限制预设按钮
        limit_preset_layout = QHBoxLayout()
        limit_preset_layout.addStretch()
        
        unlimited_btn = QPushButton("♾️ 设为无限制(-180°~+180°)")
        unlimited_btn.clicked.connect(self.set_unlimited_range)
        limit_preset_layout.addWidget(unlimited_btn)
        
        safe_btn = QPushButton("🛡️ 设为安全范围(-90°~+90°)")
        safe_btn.clicked.connect(self.set_safe_range)
        limit_preset_layout.addWidget(safe_btn)
        
        limit_preset_layout.addStretch()
        tab_layout.addLayout(limit_preset_layout)
        
        tab_layout.addStretch()
        self.tab_widget.addTab(tab_widget, "⚠️ 运动限制")
    
    def create_advanced_settings_tab(self):
        """创建高级设置标签页"""
        tab_widget = QWidget()
        tab_layout = QVBoxLayout(tab_widget)
        
        # 高级设置组
        advanced_group = QGroupBox("🔬 高级设置")
        advanced_layout = QVBoxLayout(advanced_group)
        
        # 角度单位设置
        unit_layout = QHBoxLayout()
        unit_layout.addWidget(QLabel("角度单位："))
        self.angle_unit_combo = QComboBox()
        self.angle_unit_combo.addItems(["度 (deg)", "弧度 (rad)"])
        unit_layout.addWidget(self.angle_unit_combo)
        unit_layout.addStretch()
        advanced_layout.addLayout(unit_layout)
        
        # 配置信息
        info_layout = QVBoxLayout()
        info_layout.addWidget(QLabel("配置信息："))
        self.description_edit = QLineEdit()
        self.description_edit.setPlaceholderText("输入配置描述信息...")
        info_layout.addWidget(self.description_edit)
        advanced_layout.addLayout(info_layout)
        
        tab_layout.addWidget(advanced_group)
        
        # 导入导出组
        io_group = QGroupBox("💾 配置管理")
        io_layout = QVBoxLayout(io_group)
        
        io_btn_layout = QHBoxLayout()
        
        export_btn = QPushButton("📤 导出配置")
        export_btn.clicked.connect(self.export_config)
        io_btn_layout.addWidget(export_btn)
        
        import_btn = QPushButton("📥 导入配置")
        import_btn.clicked.connect(self.import_config)
        io_btn_layout.addWidget(import_btn)
        
        io_layout.addLayout(io_btn_layout)
        
        # 配置文件路径
        path_layout = QVBoxLayout()
        path_layout.addWidget(QLabel("配置文件路径："))
        self.config_path_label = QLabel()
        self.config_path_label.setStyleSheet("color: #666; font-size: 11px;")
        self.config_path_label.setWordWrap(True)
        path_layout.addWidget(self.config_path_label)
        io_layout.addLayout(path_layout)
        
        tab_layout.addWidget(io_group)
        
        tab_layout.addStretch()
        self.tab_widget.addTab(tab_widget, "🔬 高级设置")
    
    def create_button_area(self, parent_layout):
        """创建按钮区域"""
        button_layout = QHBoxLayout()
        
        button_layout.addStretch()
        
        # 重置按钮
        reset_btn = QPushButton("🔄 重置为默认")
        reset_btn.clicked.connect(self.reset_to_default)
        button_layout.addWidget(reset_btn)
        
        # 保存按钮
        save_btn = QPushButton("✅ 保存")
        save_btn.setStyleSheet("""
            QPushButton {
                background-color: #28a745;
                color: white;
                font-weight: bold;
                padding: 8px 16px;
            }
            QPushButton:hover {
                background-color: #218838;
            }
        """)
        save_btn.clicked.connect(self.save_config)
        button_layout.addWidget(save_btn)
        
        parent_layout.addLayout(button_layout)
    
    def load_current_config(self):
        """加载当前配置到界面"""
        try:
            # 加载DH参数
            dh_params = self.config_manager.get_dh_parameters()
            
            for i in range(6):
                self.d_inputs[i].setValue(dh_params["d"][i])
                self.a_inputs[i].setValue(dh_params["a"][i])
                # alpha是弧度制，需要转换为度
                self.alpha_inputs[i].setValue(np.rad2deg(dh_params["alpha"][i]))
            
            # 加载关节偏转
            offsets = self.config_manager.get_joint_offsets()
            for i in range(6):
                self.offset_inputs[i].setValue(offsets[i])
            
            # 加载偏转启用状态
            self.enable_offset_checkbox.setChecked(self.config_manager.is_offset_enabled())
            
            # 加载关节限制
            limits = self.config_manager.get_joint_limits()
            for i in range(6):
                self.min_limit_inputs[i].setValue(limits[i][0])
                self.max_limit_inputs[i].setValue(limits[i][1])
            
            # 加载高级设置
            angle_unit = self.config_manager.get_angle_unit()
            self.angle_unit_combo.setCurrentIndex(0 if angle_unit == "deg" else 1)
            
            description = self.config_manager.config.get("description", "")
            self.description_edit.setText(description)
            
            # 显示配置文件路径
            self.config_path_label.setText(self.config_manager.get_config_file_path())
            
            
        except Exception as e:
            QMessageBox.warning(self, "错误", f"加载配置失败：\n{str(e)}")
            print(f"❌ 加载机械臂配置失败: {e}")
    
    def save_config(self):
        """保存配置"""
        try:
            # 收集DH参数
            d_params = [self.d_inputs[i].value() for i in range(6)]
            a_params = [self.a_inputs[i].value() for i in range(6)]
            alpha_params = [self.alpha_inputs[i].value() for i in range(6)]  # 度制
            
            # 收集关节偏转
            offsets = [self.offset_inputs[i].value() for i in range(6)]
            
            # 收集关节限制
            limits = []
            for i in range(6):
                min_val = self.min_limit_inputs[i].value()
                max_val = self.max_limit_inputs[i].value()
                if min_val >= max_val:
                    QMessageBox.warning(self, "参数错误", f"关节{i+1}的最小限制({min_val}°)不能大于等于最大限制({max_val}°)")
                    return
                limits.append((min_val, max_val))
            
            # 设置配置
            self.config_manager.set_dh_parameters(d_params, a_params, alpha_params)
            self.config_manager.set_joint_offsets(offsets)
            self.config_manager.set_offset_enabled(self.enable_offset_checkbox.isChecked())
            self.config_manager.set_joint_limits(limits)
            
            # 高级设置
            angle_unit = "deg" if self.angle_unit_combo.currentIndex() == 0 else "rad"
            self.config_manager.set_angle_unit(angle_unit)
            
            self.config_manager.config["description"] = self.description_edit.text()
            
            # 保存到文件
            if self.config_manager.save_config():
                QMessageBox.information(self, "成功", "机械臂配置已成功保存！")
                
                # 发出配置改变信号
                self.config_changed.emit()
                
                self.accept()
            else:
                QMessageBox.critical(self, "错误", "保存配置失败！")
                
        except Exception as e:
            QMessageBox.critical(self, "错误", f"保存配置时出错：\n{str(e)}")
            print(f"❌ 保存机械臂配置失败: {e}")
    
    def reset_to_default(self):
        """重置为默认配置"""
        reply = QMessageBox.question(self, "确认重置", "确定要将所有参数重置为默认值吗？\n这将丢失当前所有设置。")
        if reply == QMessageBox.Yes:
            self.config_manager.reset_to_default()
            self.load_current_config()
            QMessageBox.information(self, "重置完成", "已重置为默认配置")
    
    def restore_default_dh_parameters(self):
        """恢复默认MDH参数"""
        reply = QMessageBox.question(self, "确认恢复", "确定要恢复默认MDH参数吗？")
        if reply == QMessageBox.Yes:
            default_config = self.config_manager.default_config
            dh_params = default_config["dh_parameters"]
            
            for i in range(6):
                self.d_inputs[i].setValue(dh_params["d"][i])
                self.a_inputs[i].setValue(dh_params["a"][i])
                self.alpha_inputs[i].setValue(dh_params["alpha_deg"][i])
    
    def restore_default_offsets(self):
        """恢复默认偏转"""
        default_offsets = self.config_manager.default_config["joint_offsets"]
        for i in range(6):
            self.offset_inputs[i].setValue(default_offsets[i])
    
    def clear_all_offsets(self):
        """清零所有偏转"""
        for i in range(6):
            self.offset_inputs[i].setValue(0.0)
    
    def set_unlimited_range(self):
        """设置无限制范围"""
        for i in range(6):
            self.min_limit_inputs[i].setValue(-180.0)
            self.max_limit_inputs[i].setValue(180.0)
    
    def set_safe_range(self):
        """设置安全范围"""
        for i in range(6):
            self.min_limit_inputs[i].setValue(-90.0)
            self.max_limit_inputs[i].setValue(90.0)
    
    def export_config(self):
        """导出配置"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出机械臂配置", "arm_config.json", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            if self.config_manager.export_config(file_path):
                QMessageBox.information(self, "导出成功", f"配置已导出到：\n{file_path}")
            else:
                QMessageBox.critical(self, "导出失败", "导出配置文件失败！")
    
    def import_config(self):
        """导入配置"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入机械臂配置", "", 
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            reply = QMessageBox.question(self, "确认导入", "导入配置将覆盖当前设置，是否继续？")
            if reply == QMessageBox.Yes:
                if self.config_manager.import_config(file_path):
                    self.load_current_config()
                    QMessageBox.information(self, "导入成功", "配置已成功导入！")
                else:
                    QMessageBox.critical(self, "导入失败", "导入配置文件失败！请检查文件格式。")


# 全局DH参数配置管理器实例
dh_config_manager = DHConfigManager()
